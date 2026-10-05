// FF-P04-01 (D-NEW-001): Node-based behavioral driver for the vanilla-JS app
// shell (factory/intake/web/app.js).
//
// app.js is a plain browser script (no module system, no bundler, per the
// "extend vanilla JS in place" decision) that assumes `document`, `window`,
// `localStorage` and `fetch` globals. This driver hand-rolls just enough of
// those globals to load and exercise the real app.js source with Node's `vm`
// module -- the same spirit as factory/tests/helpers/worker_auth_driver.mjs,
// which hand-rolls mocks around the real Worker bundle rather than
// reimplementing its logic in a test language.
//
// It prints "PASS: <description>" / "FAIL: <description>" lines; the Python
// test file (factory/tests/test_intake_web_shell.py) shells out to this
// script and asserts on those lines. Exits non-zero if any check fails.

import { readFileSync } from "node:fs";
import vm from "node:vm";

const appJsPath = process.argv[2];
if (!appJsPath) {
  console.error("Usage: node app_shell_driver.mjs <path-to-app.js>");
  process.exit(2);
}

const results = [];
function record(ok, description) {
  results.push({ ok, description });
  console.log(`${ok ? "PASS" : "FAIL"}: ${description}`);
}

function assertTrue(cond, description) {
  record(!!cond, description);
}

function assertEqual(actual, expected, description) {
  record(actual === expected, `${description} (got ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)})`);
}

// ---------------------------------------------------------------------------
// Minimal DOM stub
// ---------------------------------------------------------------------------

function makeElement(id) {
  const classes = new Set();
  const attrs = {};
  const listeners = {};
  let _text = "";
  let _html = "";

  const el = {
    id: id || null,
    value: "",
    disabled: false,
    href: "",
    style: {},
    scrollTop: 0,
    scrollHeight: 0,
    _focusCalls: 0,

    classList: {
      add: (...cs) => cs.forEach((c) => classes.add(c)),
      remove: (...cs) => cs.forEach((c) => classes.delete(c)),
      contains: (c) => classes.has(c),
      toggle: (c, force) => {
        const has = classes.has(c);
        const want = force === undefined ? !has : force;
        if (want) classes.add(c);
        else classes.delete(c);
        return want;
      },
    },

    setAttribute(name, val) {
      attrs[name] = String(val);
    },
    getAttribute(name) {
      return name in attrs ? attrs[name] : null;
    },
    removeAttribute(name) {
      delete attrs[name];
    },

    addEventListener(type, fn) {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    removeEventListener(type, fn) {
      if (!listeners[type]) return;
      listeners[type] = listeners[type].filter((f) => f !== fn);
    },
    dispatchEvent(evt) {
      (listeners[evt.type] || []).slice().forEach((fn) => fn(evt));
    },
    click() {
      el.dispatchEvent({ type: "click", preventDefault() {} });
    },
    focus() {
      el._focusCalls += 1;
      document.activeElement = el;
    },
  };

  Object.defineProperty(el, "textContent", {
    get() {
      return _text;
    },
    set(v) {
      _text = String(v);
      // Approximate real innerHTML serialization of a text-only node.
      _html = _text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    },
  });
  Object.defineProperty(el, "innerHTML", {
    get() {
      return _html;
    },
    set(v) {
      _html = String(v);
    },
  });

  return el;
}

// Elements that index.html gives `class="... hidden"` by default. The
// stub has no HTML parser, so it must seed the same starting state the
// real page would -- otherwise modal/page visibility checks start from the
// wrong baseline (e.g. a modal that should start closed would read as
// already open).
const INITIALLY_HIDDEN_IDS = new Set([
  "chat-section",
  "success-section",
  "history-section",
  "settings-section",
  "voice-indicator",
  "text-input-area",
  "help-modal",
  "repo-modal",
]);

const elementRegistry = new Map();
const documentListeners = {};

const document = {
  activeElement: null,
  title: "",
  getElementById(id) {
    if (!elementRegistry.has(id)) {
      const el = makeElement(id);
      if (INITIALLY_HIDDEN_IDS.has(id)) el.classList.add("hidden");
      elementRegistry.set(id, el);
    }
    return elementRegistry.get(id);
  },
  createElement(_tag) {
    return makeElement(null);
  },
  addEventListener(type, fn) {
    (documentListeners[type] = documentListeners[type] || []).push(fn);
  },
  removeEventListener(type, fn) {
    if (!documentListeners[type]) return;
    documentListeners[type] = documentListeners[type].filter((f) => f !== fn);
  },
  dispatchEvent(evt) {
    (documentListeners[evt.type] || []).slice().forEach((fn) => fn(evt));
  },
};

let _hash = "";
const windowListeners = {};
const window = {
  location: {
    get hash() {
      return _hash;
    },
    set hash(v) {
      const newHash = v.startsWith("#") ? v : "#" + v;
      if (newHash === _hash) return;
      _hash = newHash;
      (windowListeners["hashchange"] || []).slice().forEach((fn) => fn({ type: "hashchange" }));
    },
  },
  addEventListener(type, fn) {
    (windowListeners[type] = windowListeners[type] || []).push(fn);
  },
  removeEventListener(type, fn) {
    if (!windowListeners[type]) return;
    windowListeners[type] = windowListeners[type].filter((f) => f !== fn);
  },
  close() {},
};

const localStorageData = new Map();
const localStorage = {
  getItem(key) {
    return localStorageData.has(key) ? localStorageData.get(key) : null;
  },
  setItem(key, value) {
    localStorageData.set(key, String(value));
  },
  removeItem(key) {
    localStorageData.delete(key);
  },
  clear() {
    localStorageData.clear();
  },
};

// fetch stub: canned responses keyed by a simple predicate list, mutable per
// test section below.
let fetchHandler = async () => {
  throw new Error("fetch called with no handler installed for this check");
};
async function fetch(url, options) {
  return fetchHandler(url, options);
}

const consoleStub = console;

const sandbox = {
  document,
  window,
  localStorage,
  fetch,
  console: consoleStub,
  alert: (msg) => {
    sandbox.__lastAlert = msg;
  },
  setTimeout,
  Set,
  Map,
  JSON,
  Date,
  // version.js is a separate <script> in the real page (index.html loads it
  // before app.js); app.js only calls updateVersionFooter() from a
  // DOMContentLoaded listener, so a no-op stub is enough for this driver.
  updateVersionFooter: () => {},
  globalThis: undefined, // filled in below once context exists
};
sandbox.globalThis = sandbox;

const context = vm.createContext(sandbox);

const source = readFileSync(appJsPath, "utf8");
try {
  vm.runInContext(source, context, { filename: appJsPath });
} catch (error) {
  console.error("FAIL: app.js loaded without throwing");
  console.error(error);
  process.exit(1);
}
record(true, "app.js loaded without throwing in the Node harness");

const shell = sandbox.__DFACTORY_SHELL__;
assertTrue(!!shell, "app.js exposes __DFACTORY_SHELL__ test hooks");
if (!shell) {
  console.log("Cannot continue without shell hooks.");
  process.exit(1);
}

const { Router, AppShellState, pageSections, elements, helpModalController, repoModalController } = shell;

function visiblePages() {
  return Object.entries(pageSections)
    .filter(([, el]) => el && !el.classList.contains("hidden"))
    .map(([key]) => key);
}

// ---------------------------------------------------------------------------
// 1. Route navigation (hash changes trigger view updates)
// ---------------------------------------------------------------------------

assertEqual(Router.getCurrentRoute(), "/", "initial route resolves to '/'");
assertEqual(visiblePages().join(","), "hero", "only the hero page is visible on initial load");

Router.navigate("/conversation");
assertEqual(Router.getCurrentRoute(), "/conversation", "navigate('/conversation') updates current route");
assertEqual(visiblePages().join(","), "chat", "navigating to /conversation shows only the chat page");
assertEqual(elements.navConversation.getAttribute("aria-current"), "page", "nav-conversation gets aria-current=page");
assertEqual(elements.navHome.getAttribute("aria-current"), null, "nav-home loses aria-current when on /conversation");

Router.navigate("/history");
assertEqual(visiblePages().join(","), "history", "navigating to /history shows only the history page");

Router.navigate("/settings");
assertEqual(visiblePages().join(","), "settings", "navigating to /settings shows only the settings page");

// Simulate a browser back/forward button or manually-edited URL: set the
// hash directly (not via Router.navigate) and rely on the hashchange
// listener registered by Router.start().
window.location.hash = "#/conversation";
assertEqual(visiblePages().join(","), "chat", "manually setting location.hash fires hashchange and updates the view");

// Unknown route falls back to "/" via the notFound handler.
window.location.hash = "#/does-not-exist";
assertEqual(Router.getCurrentRoute(), "/", "unknown route redirects to '/' via notFound handler");
assertEqual(visiblePages().join(","), "hero", "notFound redirect shows the hero page");
assertEqual(
  AppShellState.getState().activeRoute,
  "/",
  "notFound's reentrant redirect persists the final route, not the stale not-found path"
);

// ---------------------------------------------------------------------------
// 2. State persistence and recovery
// ---------------------------------------------------------------------------

Router.navigate("/settings");
const persistedRaw = localStorage.getItem("dfactory_ui_state");
assertTrue(!!persistedRaw, "UI state is persisted to localStorage under dfactory_ui_state");
let persisted = null;
try {
  persisted = JSON.parse(persistedRaw);
} catch (e) {
  persisted = null;
}
assertEqual(persisted && persisted.activeRoute, "/settings", "persisted UI state records the active route");
assertEqual(AppShellState.getState().activeRoute, "/settings", "AppShellState.getState() reflects the active route in memory");

// Recovery: a fresh AppShellState.load() call (simulating a reload that
// re-runs this same bootstrap code) should recover whatever is in
// localStorage, even when it disagrees with current in-memory state. Write
// storage directly (bypassing setActiveRoute, which would also persist and
// defeat the point of this check) to simulate "this is a new page load and
// memory hasn't caught up yet".
localStorage.setItem("dfactory_ui_state", JSON.stringify({ activeRoute: "/history" }));
const recovered = AppShellState.load();
assertEqual(recovered.activeRoute, "/history", "AppShellState.load() recovers the persisted route from localStorage");
// Restore storage to match current in-memory state for the checks that follow.
Router.navigate("/settings");

// Conversation session/draft storage keys must remain untouched by the
// shell's own state key (regression guard for FF-P04-01 scope).
assertEqual(localStorage.getItem("dfactory_session_id"), null, "shell state does not touch dfactory_session_id");
assertEqual(localStorage.getItem("dfactory_draft"), null, "shell state does not touch dfactory_draft");

// ---------------------------------------------------------------------------
// 3. Keyboard navigation flows (Escape closes modals, Tab is trapped)
// ---------------------------------------------------------------------------

Router.navigate("/"); // reset to a known page
elements.helpBtn.focus(); // simulate the user having focused the trigger button
helpModalController.open();
assertTrue(!elements.helpModal.classList.contains("hidden"), "opening the help modal removes .hidden");
assertEqual(document.activeElement, elements.helpCloseBtn, "opening the help modal focuses its only focusable control");

document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });
assertTrue(elements.helpModal.classList.contains("hidden"), "Escape closes the open help modal");
assertEqual(document.activeElement, elements.helpBtn, "closing the help modal restores focus to the trigger button");

repoModalController.open();
assertEqual(document.activeElement, elements.existingRepoUrl, "opening the repo modal focuses its first focusable field");

// Tab from the last focusable should wrap to the first (focus trap).
document.activeElement = elements.repoModalCloseBtn;
document.dispatchEvent({ type: "keydown", key: "Tab", shiftKey: false, preventDefault() {} });
assertEqual(document.activeElement, elements.existingRepoUrl, "Tab on the last modal control wraps focus to the first");

// Shift+Tab from the first focusable should wrap to the last.
document.activeElement = elements.existingRepoUrl;
document.dispatchEvent({ type: "keydown", key: "Tab", shiftKey: true, preventDefault() {} });
assertEqual(document.activeElement, elements.repoModalCloseBtn, "Shift+Tab on the first modal control wraps focus to the last");

document.dispatchEvent({ type: "keydown", key: "Escape", preventDefault() {} });
assertTrue(elements.repoModal.classList.contains("hidden"), "Escape closes the open repo modal");

// ---------------------------------------------------------------------------
// 4. Focus management on route change
// ---------------------------------------------------------------------------

Router.navigate("/conversation");
assertTrue(elements.chatSection._focusCalls > 0, "navigating to /conversation calls focus() on the chat section container");

Router.navigate("/history");
assertTrue(elements.historySection._focusCalls > 0, "navigating to /history calls focus() on the history section container");

// ---------------------------------------------------------------------------
// 5. Regression: existing conversation-submission flow still works
// ---------------------------------------------------------------------------

// Reset conversation-side localStorage + shell route before the regression check.
localStorage.removeItem("dfactory_session_id");
localStorage.removeItem("dfactory_draft");
Router.navigate("/");

let conversationCreatePosted = false;
let messagePosted = null;
let textResponseRequested = null;

fetchHandler = async (url, options) => {
  if (String(url).endsWith("/conversations") && options && options.method === "POST") {
    conversationCreatePosted = true;
    return {
      ok: true,
      json: async () => ({ conversation: { id: "conv-123" } }),
    };
  }
  if (String(url).includes("/messages") && options && options.method === "POST") {
    messagePosted = JSON.parse(options.body);
    return { ok: true, json: async () => ({ ok: true }) };
  }
  if (String(url).includes("/text-response") && options && options.method === "POST") {
    textResponseRequested = JSON.parse(options.body);
    return { ok: true, json: async () => ({ response: "Thanks, got it." }) };
  }
  throw new Error(`Unexpected fetch in regression check: ${url}`);
};

document.dispatchEvent({ type: "DOMContentLoaded" });

elements.textBtn.click();
// startTextMode's fetch chain is async; wait a tick for the promise chain.
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));

assertTrue(conversationCreatePosted, "regression: clicking 'Type your idea instead' still POSTs /conversations");
assertEqual(localStorage.getItem("dfactory_session_id"), "conv-123", "regression: conversation id is still persisted to dfactory_session_id");
assertEqual(Router.getCurrentRoute(), "/conversation", "regression: starting text mode still routes to the conversation page");
assertTrue(!elements.chatSection.classList.contains("hidden"), "regression: chat section is visible after starting text mode");
assertTrue(elements.heroSection.classList.contains("hidden"), "regression: hero section is hidden after starting text mode");

elements.textInput.value = "I need a dashboard for tracking project progress";
elements.sendBtn.click();
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));

assertTrue(!!messagePosted, "regression: sendTextMessage still POSTs the user message to /messages");
assertEqual(messagePosted && messagePosted.text, "I need a dashboard for tracking project progress", "regression: posted message text matches the textarea value");
assertTrue(!!textResponseRequested, "regression: sendTextMessage still requests /text-response for the AI reply");
assertTrue(elements.messagesContainer.innerHTML.includes("Thanks, got it."), "regression: AI response is rendered into the messages container");
assertEqual(elements.textInput.value, "", "regression: the text input is cleared after sending");

// Enter-to-send still works (existing keypress-based shortcut).
let secondMessagePosted = null;
fetchHandler = async (url, options) => {
  if (String(url).includes("/messages") && options && options.method === "POST") {
    secondMessagePosted = JSON.parse(options.body);
    return { ok: true, json: async () => ({ ok: true }) };
  }
  if (String(url).includes("/text-response")) {
    return { ok: true, json: async () => ({ response: "Got it." }) };
  }
  throw new Error(`Unexpected fetch: ${url}`);
};
elements.textInput.value = "A second message sent via Enter";
elements.textInput.dispatchEvent({ type: "keypress", key: "Enter" });
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));
await new Promise((resolve) => setTimeout(resolve, 0));
assertEqual(secondMessagePosted && secondMessagePosted.text, "A second message sent via Enter", "regression: pressing Enter in the textarea still sends the message");

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

const failed = results.filter((r) => !r.ok);
if (failed.length === 0) {
  console.log(`All ${results.length} checks passed.`);
  process.exit(0);
} else {
  console.log(`${failed.length} of ${results.length} checks FAILED.`);
  process.exit(1);
}

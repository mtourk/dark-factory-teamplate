/**
 * Dark Factory Phase 17.0 — Feature Intake Frontend
 *
 * Handles:
 * - Conversation lifecycle (draft → file → success)
 * - Voice input (Gemini Live)
 * - Text input fallback
 * - Issue preview generation
 * - GitHub filing
 * - Local storage persistence
 */

const WORKER_URL = "https://dark-factory-intake.mohammad-tourk.workers.dev";
const STORAGE_KEY_SESSION = "dfactory_session_id";
const STORAGE_KEY_DRAFT = "dfactory_draft";
// FF-P04-01 (D-NEW-001): app-shell UI state (active route). Separate key from the
// conversation session/draft above — the shell's own persistence must never interact
// with the conversation-submission flow's storage.
const STORAGE_KEY_UI_STATE = "dfactory_ui_state";

// ============ State ============

let state = {
  conversationId: null,
  messages: [],
  draftIssue: {
    title: "",
    description: "",
    acceptanceCriteria: [],
    nonGoals: [],
    constraints: [],
    dataBehavior: "",
    errorHandling: "",
  },
  isVoiceActive: false,
  isFiled: false,
  repoUrl: "",
  issueUrl: "",
  issueNumber: null,
  selectedRepoUrl: null, // Repo URL to use for filing
};

// ============ DOM Elements ============

const elements = {
  heroSection: document.getElementById("hero-section"),
  chatSection: document.getElementById("chat-section"),
  successSection: document.getElementById("success-section"),
  messagesContainer: document.getElementById("messages-container"),
  voiceBtn: document.getElementById("voice-btn"),
  textBtn: document.getElementById("text-btn"),
  voiceIndicator: document.getElementById("voice-indicator"),
  recordingText: document.getElementById("recording-text"),
  textInputArea: document.getElementById("text-input-area"),
  textInput: document.getElementById("text-input"),
  sendBtn: document.getElementById("send-btn"),
  issueTitle: document.getElementById("issue-title"),
  issueDescription: document.getElementById("issue-description"),
  issueAcceptance: document.getElementById("issue-acceptance"),
  issueNonGoals: document.getElementById("issue-non-goals"),
  issueConstraints: document.getElementById("issue-constraints"),
  editIssueBtn: document.getElementById("edit-issue-btn"),
  fileIssueBtn: document.getElementById("file-issue-btn"),
  saveDraftBtn: document.getElementById("save-draft-btn"),
  successMessage: document.getElementById("success-message"),
  issueLink: document.getElementById("issue-link"),
  newIntakeBtn: document.getElementById("new-intake-btn"),
  helpBtn: document.getElementById("help-btn"),
  helpModal: document.getElementById("help-modal"),
  helpCloseBtn: document.getElementById("help-close-btn"),
  closeBtn: document.getElementById("close-btn"),
  // Repo modal elements
  repoModal: document.getElementById("repo-modal"),
  existingRepoUrl: document.getElementById("existing-repo-url"),
  useExistingBtn: document.getElementById("use-existing-btn"),
  newRepoName: document.getElementById("new-repo-name"),
  createRepoBtn: document.getElementById("create-repo-btn"),
  repoModalCloseBtn: document.getElementById("repo-modal-close-btn"),
  // App-shell navigation + pages (FF-P04-01)
  navHome: document.getElementById("nav-home"),
  navConversation: document.getElementById("nav-conversation"),
  navHistory: document.getElementById("nav-history"),
  navSettings: document.getElementById("nav-settings"),
  historySection: document.getElementById("history-section"),
  settingsSection: document.getElementById("settings-section"),
};

// ============================================================================
// ============ Application Shell: Router + State (FF-P04-01) ================
// ============================================================================
//
// Per D-NEW-001 (decided: extend vanilla JS in place rather than adopt a
// framework), this is a *minimal*, hand-rolled hash router and a tiny
// observable state container. No build step, no dependencies. Future pages
// (FF-P05-01 idea intake, FF-P06-01 voice, FF-P13-02 critics/decision,
// FF-P17-01 monitoring, FF-P18-01 notifications) should each:
//
//   1. Add a <section id="...-section" class="page-section hidden" tabindex="-1">
//      to index.html (see history-section/settings-section for the placeholder
//      pattern) and register it in `pageSections` below.
//   2. Call `Router.register("/your-route", () => showPage("yourKey"))`.
//   3. Add a <a class="nav-link" href="#/your-route" data-route="/your-route">
//      to #app-nav if it should be reachable from the primary nav.
//
// Router: a plain object literal (module-pattern IIFE) that maps a normalized
// hash path ("/", "/conversation", ...) to a zero-arg handler. `navigate()`
// updates `location.hash` (so the URL is always a valid deep link / is
// bookmarkable / supports browser back-forward) AND resolves synchronously
// (handlers do not wait for the async `hashchange` event), so callers can
// rely on the DOM being updated immediately after `navigate()` returns. The
// `hashchange` listener re-resolves for the back/forward-button and
// manually-edited-URL cases; `resolve()` is idempotent so double-invocation
// (sync + event) is harmless.
const Router = (() => {
  const routes = {};
  let notFoundHandler = null;
  let currentRoute = null;

  function normalizeHash(hash) {
    let h = (hash || "").replace(/^#/, "");
    if (!h.startsWith("/")) h = "/" + h;
    if (h.length > 1 && h.endsWith("/")) h = h.slice(0, -1);
    return h || "/";
  }

  function currentPath() {
    return normalizeHash(window.location.hash);
  }

  function register(path, handler) {
    routes[path] = handler;
  }

  function setNotFound(handler) {
    notFoundHandler = handler;
  }

  function resolve() {
    const path = currentPath();
    currentRoute = path;
    const handler = routes[path] || notFoundHandler;
    if (typeof handler === "function") handler(path);
    // Re-read `currentRoute` (not the locally-captured `path`) before
    // persisting: a notFound handler typically calls navigate() again
    // reentrantly, which mutates `currentRoute` to the redirected-to route
    // before this line runs. Persisting the stale `path` here would record
    // the invalid pre-redirect route instead of where the app actually
    // ended up.
    AppShellState.setActiveRoute(currentRoute);
    return currentRoute;
  }

  function navigate(path) {
    const normalized = normalizeHash(path);
    if (currentPath() !== normalized) {
      window.location.hash = normalized;
    }
    // Always resolve synchronously too, so DOM updates happen before
    // navigate() returns regardless of hashchange event timing.
    resolve();
  }

  function start() {
    window.addEventListener("hashchange", resolve);
    resolve();
  }

  function getCurrentRoute() {
    return currentRoute;
  }

  return { register, setNotFound, navigate, start, resolve, getCurrentRoute, normalizeHash };
})();

// AppShellState: the shell's own tiny state container (distinct from the
// conversation `state` object above). Tracks only what the shell itself
// needs — currently just the active route — and persists it to localStorage
// so a hard reload of a hash-less URL restores the last page the user was
// on. This is intentionally minimal: conversation data stays in `state`
// and on the Worker/D1, never here.
const AppShellState = (() => {
  let shellState = { activeRoute: "/" };
  const subscribers = new Set();

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_UI_STATE);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.activeRoute === "string") {
          shellState = { ...shellState, ...parsed };
        }
      }
    } catch (error) {
      console.warn("Failed to restore UI state:", error);
    }
    return shellState;
  }

  function setActiveRoute(route) {
    shellState = { ...shellState, activeRoute: route };
    try {
      localStorage.setItem(STORAGE_KEY_UI_STATE, JSON.stringify(shellState));
    } catch (error) {
      console.warn("Failed to persist UI state:", error);
    }
    subscribers.forEach((fn) => fn(shellState));
  }

  function getState() {
    return shellState;
  }

  function subscribe(fn) {
    subscribers.add(fn);
    return () => subscribers.delete(fn);
  }

  return { load, setActiveRoute, getState, subscribe };
})();

// Every top-level "page" the shell currently knows about. One of these is
// visible at a time; `showPage()` is the single place that enforces that.
const pageSections = {
  hero: elements.heroSection,
  chat: elements.chatSection,
  success: elements.successSection,
  history: elements.historySection,
  settings: elements.settingsSection,
};

const navLinkByRoute = {
  "/": elements.navHome,
  "/conversation": elements.navConversation,
  "/history": elements.navHistory,
  "/settings": elements.navSettings,
};

function showPage(name) {
  Object.entries(pageSections).forEach(([key, el]) => {
    if (!el) return;
    if (key === name) el.classList.remove("hidden");
    else el.classList.add("hidden");
  });

  updateNavActiveState(Router.getCurrentRoute());

  // Focus management: move focus to the newly-shown page's own container so
  // assistive tech announces the view change (route change == page change).
  const shown = pageSections[name];
  if (shown && typeof shown.focus === "function") {
    shown.focus();
  }
}

function updateNavActiveState(route) {
  Object.entries(navLinkByRoute).forEach(([path, link]) => {
    if (!link) return;
    if (path === route) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

// ---- Modal focus trap + Escape-to-close (keyboard nav + a11y basics) ----
//
// Each modal gets an ordered list of its own focusable elements (explicit,
// not queried from the DOM, since this file doesn't use querySelectorAll
// anywhere else). open() remembers what was focused before opening and
// restores it on close(); handleTab() cycles focus within the modal so Tab
// never escapes to the page behind it while the modal is open.
function createModal(modalEl, getFocusables) {
  let previouslyFocused = null;

  function isOpen() {
    return !!modalEl && !modalEl.classList.contains("hidden");
  }

  function open() {
    if (!modalEl) return;
    previouslyFocused = document.activeElement;
    modalEl.classList.remove("hidden");
    const focusables = getFocusables().filter((el) => el && !el.disabled);
    if (focusables[0] && typeof focusables[0].focus === "function") {
      focusables[0].focus();
    }
  }

  function close() {
    if (!modalEl) return;
    modalEl.classList.add("hidden");
    if (previouslyFocused && typeof previouslyFocused.focus === "function") {
      previouslyFocused.focus();
    }
    previouslyFocused = null;
  }

  function handleTab(event) {
    const focusables = getFocusables().filter((el) => el && !el.disabled);
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return { open, close, isOpen, handleTab };
}

const helpModalController = createModal(elements.helpModal, () => [elements.helpCloseBtn]);
const repoModalController = createModal(elements.repoModal, () => [
  elements.existingRepoUrl,
  elements.useExistingBtn,
  elements.newRepoName,
  elements.createRepoBtn,
  elements.repoModalCloseBtn,
]);

function getOpenModal() {
  if (repoModalController.isOpen()) return repoModalController;
  if (helpModalController.isOpen()) return helpModalController;
  return null;
}

// Single global keydown handler: Escape closes whichever modal is open
// (minimum required shortcut), Tab is trapped within it. Outside of a
// modal, Tab falls through to normal browser focus order — every
// interactive element in this app is a native <button>/<a>/<input>/
// <textarea>, so no extra JS is needed for plain Tab navigation.
document.addEventListener("keydown", (event) => {
  const modal = getOpenModal();
  if (!modal) return;

  if (event.key === "Escape") {
    event.preventDefault();
    modal.close();
    return;
  }

  if (event.key === "Tab") {
    modal.handleTab(event);
  }
});

// ---- Route table ----
Router.register("/", () => showPage("hero"));
Router.register("/conversation", () => showPage("chat"));
Router.register("/success", () => showPage("success"));
Router.register("/history", () => showPage("history"));
Router.register("/settings", () => showPage("settings"));
Router.setNotFound(() => Router.navigate("/"));

// ---- Bootstrap the shell ----
// If the URL has no hash yet, fall back to the last-visited route (if any)
// before the router's first resolve, so a bare reload restores context.
// An explicit hash in the URL always wins over the stored one.
(function bootstrapShell() {
  AppShellState.load();
  const hasExplicitHash = !!window.location.hash && window.location.hash !== "#";
  if (!hasExplicitHash) {
    const restoredRoute = AppShellState.getState().activeRoute;
    if (restoredRoute && restoredRoute !== "/") {
      window.location.hash = Router.normalizeHash(restoredRoute);
    }
  }
  Router.start();
})();

// ============ Initialization ============

async function init() {
  console.log("Initializing Dark Factory Intake...");

  // Restore session from localStorage
  const savedSessionId = localStorage.getItem(STORAGE_KEY_SESSION);
  if (savedSessionId) {
    state.conversationId = savedSessionId;
    await loadConversation();
  }

  // Event listeners
  elements.voiceBtn.addEventListener("click", startVoice);
  elements.textBtn.addEventListener("click", startTextMode);
  elements.sendBtn.addEventListener("click", sendTextMessage);
  elements.textInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendTextMessage();
  });

  // Primary nav: anchors update location.hash natively on click/Enter; the
  // Router's own "hashchange" listener (registered in bootstrapShell) does
  // the rest, so no click handlers are needed here.

  elements.fileIssueBtn.addEventListener("click", fileIssue);
  elements.editIssueBtn.addEventListener("click", editIssue);
  elements.saveDraftBtn.addEventListener("click", saveDraft);
  elements.newIntakeBtn.addEventListener("click", resetIntake);

  // Repo modal listeners
  elements.useExistingBtn.addEventListener("click", async () => {
    const url = elements.existingRepoUrl.value.trim();
    if (!url) {
      alert("Please enter a repository URL");
      return;
    }
    state.selectedRepoUrl = url;
    repoModalController.close();
    await fileIssueToRepo();
  });
  elements.existingRepoUrl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      elements.useExistingBtn.click();
    }
  });

  elements.createRepoBtn.addEventListener("click", async () => {
    const name = elements.newRepoName.value.trim();
    if (!name) {
      alert("Please enter a repository name");
      return;
    }
    elements.createRepoBtn.textContent = "Creating...";
    elements.createRepoBtn.disabled = true;
    try {
      const response = await fetch(`${WORKER_URL}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!response.ok) throw new Error("Failed to create repo");
      const data = await response.json();
      state.selectedRepoUrl = data.repo.html_url;
      repoModalController.close();
      await fileIssueToRepo();
    } catch (error) {
      alert(`Error creating repo: ${error.message}`);
    } finally {
      elements.createRepoBtn.textContent = "Create New Repo";
      elements.createRepoBtn.disabled = false;
    }
  });
  elements.newRepoName.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      elements.createRepoBtn.click();
    }
  });

  elements.repoModalCloseBtn.addEventListener("click", () => {
    repoModalController.close();
  });

  elements.helpBtn.addEventListener("click", () => helpModalController.open());
  elements.helpCloseBtn.addEventListener("click", () => helpModalController.close());
  elements.closeBtn.addEventListener("click", () => window.close());
}

// ============ Conversation Loading ============

async function loadConversation() {
  if (!state.conversationId) return;

  try {
    const response = await fetch(`${WORKER_URL}/conversations/${state.conversationId}`);
    if (response.ok) {
      const data = await response.json();
      state.messages = data.messages || [];
      renderMessages();
      showChatSection();
    }
  } catch (error) {
    console.error("Failed to load conversation:", error);
  }
}

// ============ Voice Input ============

async function startVoice() {
  if (state.conversationId) {
    console.log("Conversation already active, switching to voice...");
    elements.textInputArea.classList.add("hidden");
    elements.voiceIndicator.classList.remove("hidden");
    startGeminiLive();
    return;
  }

  // Create new conversation
  try {
    const response = await fetch(`${WORKER_URL}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    if (!response.ok) throw new Error("Failed to create conversation");

    const data = await response.json();
    state.conversationId = data.conversation.id;
    localStorage.setItem(STORAGE_KEY_SESSION, state.conversationId);

    showChatSection();
    startGeminiLive();
  } catch (error) {
    alert(`Error: ${error.message}`);
  }
}

async function startGeminiLive() {
  if (!state.conversationId) return;

  elements.voiceIndicator.classList.remove("hidden");
  elements.recordingText.textContent = "Requesting microphone...";

  try {
    // Get ephemeral Gemini token
    const tokenResponse = await fetch(
      `${WORKER_URL}/conversations/${state.conversationId}/gemini-token`,
      { method: "POST" }
    );

    if (!tokenResponse.ok) throw new Error("Failed to get Gemini token");

    const { token } = await tokenResponse.json();
    elements.recordingText.textContent = "Recording...";

    // Open Gemini Live WebSocket/stream
    // This is a simplified placeholder — actual implementation uses the Gemini WebSocket API
    // In a real implementation, this would establish a WebSocket with Gemini's servers
    // using the ephemeral token and stream audio/responses back and forth
    console.log("Gemini Live session established (placeholder)");

    // For now, simulate with a timer
    await simulateGeminiConversation();
  } catch (error) {
    alert(`Error: ${error.message}`);
    elements.voiceIndicator.classList.add("hidden");
  }
}

async function simulateGeminiConversation() {
  // Placeholder: simulate a Gemini conversation
  // In production, this would be a real WebSocket with audio streaming
  const questions = [
    "Tell me about the feature you'd like to build.",
    "Who will be using this? Just you or others?",
    "What's the main pain point you're trying to solve?",
    "How will you know when this is working correctly?",
  ];

  for (const question of questions) {
    await addMessage("ai", question);

    // Simulate user response
    const userResponses = [
      "A dashboard for tracking project progress",
      "Multiple team members",
      "We waste time manually collecting status updates",
      "All team members can see real-time updates without asking",
    ];

    await new Promise((resolve) => setTimeout(resolve, 2000));
    await addMessage("user", userResponses[questions.indexOf(question)]);
  }

  elements.voiceIndicator.classList.add("hidden");
  elements.textInputArea.classList.remove("hidden");
  elements.recordingText.textContent = "Recording...";
  addMessage("ai", "I think I have enough information. Would you like me to draft the issue?");
}

// ============ Text Input ============

function startTextMode() {
  if (state.conversationId) {
    elements.textInputArea.classList.remove("hidden");
    elements.voiceBtn.style.display = "none";
    elements.textBtn.style.display = "none";
    return;
  }

  // Create new conversation
  fetch(`${WORKER_URL}/conversations`, { method: "POST" })
    .then((r) => r.json())
    .then((data) => {
      state.conversationId = data.conversation.id;
      localStorage.setItem(STORAGE_KEY_SESSION, state.conversationId);
      showChatSection();
      elements.textInputArea.classList.remove("hidden");
      elements.textInput.focus();
    })
    .catch((error) => alert(`Error: ${error.message}`));
}

async function sendTextMessage() {
  const text = elements.textInput.value.trim();
  if (!text) return;

  await addMessage("user", text);
  elements.textInput.value = "";

  // Get AI response from Worker
  elements.sendBtn.disabled = true;
  elements.sendBtn.textContent = "Thinking...";

  try {
    const response = await fetch(
      `${WORKER_URL}/conversations/${state.conversationId}/text-response`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `Server error: ${response.status}`);
    }

    const data = await response.json();
    await addMessage("ai", data.response);
  } catch (error) {
    console.error("Error getting AI response:", error);
    const errorMsg = error.message.includes("429") || error.message.includes("503")
      ? "The AI service is experiencing high demand. Please wait a moment and try again."
      : "Sorry, I had trouble generating a response. Please try again.";
    await addMessage("ai", errorMsg);
  } finally {
    elements.sendBtn.disabled = false;
    elements.sendBtn.textContent = "Send";
  }
}

// ============ Message Handling ============

async function addMessage(role, text) {
  if (role === "user") {
    try {
      const response = await fetch(
        `${WORKER_URL}/conversations/${state.conversationId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        }
      );

      if (!response.ok) throw new Error("Failed to save message");
    } catch (error) {
      console.error("Error saving message:", error);
    }
  }

  const msg = { role, text, timestamp: new Date().toISOString() };
  state.messages.push(msg);
  renderMessages();
  updateIssueDraft(text, role);
}

function renderMessages() {
  elements.messagesContainer.innerHTML = state.messages
    .map(
      (msg) => `
    <div class="message ${msg.role}">
      <div>
        <div class="message-bubble">${escapeHtml(msg.text)}</div>
        <div class="message-timestamp">${new Date(msg.timestamp).toLocaleTimeString()}</div>
      </div>
    </div>
  `
    )
    .join("");

  // Auto-scroll to bottom
  elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

// ============ Issue Draft ============

function updateIssueDraft(text, role) {
  if (role === "user") return;

  // Simple heuristic: parse AI responses for issue data
  // In production, this would be smarter / use extraction prompts

  if (text.toLowerCase().includes("acceptance")) {
    state.draftIssue.acceptanceCriteria.push(text);
  }
  if (text.toLowerCase().includes("constraint")) {
    state.draftIssue.constraints.push(text);
  }

  if (!state.draftIssue.title && state.messages.length > 2) {
    // Use first user message as title
    const firstUser = state.messages.find((m) => m.role === "user");
    if (firstUser) {
      state.draftIssue.title =
        firstUser.text.substring(0, 60) +
        (firstUser.text.length > 60 ? "..." : "");
    }
  }

  renderIssueDraft();
}

function renderIssueDraft() {
  elements.issueTitle.value = state.draftIssue.title;
  elements.issueDescription.value =
    state.messages
      .filter((m) => m.role === "user")
      .map((m) => m.text)
      .join("\n\n") || "";
  elements.issueAcceptance.value = state.draftIssue.acceptanceCriteria.join("\n");
  elements.issueNonGoals.value = state.draftIssue.nonGoals.join("\n");
  elements.issueConstraints.value = state.draftIssue.constraints.join("\n");
}

function editIssue() {
  // Make fields editable
  [
    elements.issueTitle,
    elements.issueDescription,
    elements.issueAcceptance,
    elements.issueNonGoals,
    elements.issueConstraints,
  ].forEach((el) => {
    el.removeAttribute("readonly");
  });

  elements.editIssueBtn.textContent = "✓ Done Editing";
  elements.editIssueBtn.onclick = () => {
    [
      elements.issueTitle,
      elements.issueDescription,
      elements.issueAcceptance,
      elements.issueNonGoals,
      elements.issueConstraints,
    ].forEach((el) => {
      el.setAttribute("readonly", "");
    });
    elements.editIssueBtn.textContent = "✏️ Edit";
    elements.editIssueBtn.onclick = editIssue;
  };
}

function saveDraft() {
  const draft = {
    conversationId: state.conversationId,
    messages: state.messages,
    draftIssue: state.draftIssue,
  };
  localStorage.setItem(STORAGE_KEY_DRAFT, JSON.stringify(draft));
  alert("Draft saved! You can resume this conversation later.");
}

// ============ Filing Issue ============

async function fileIssue() {
  if (!state.draftIssue.title) {
    alert("Please fill in a title before filing.");
    return;
  }

  // Clear previous selection and show repo modal
  state.selectedRepoUrl = null;
  elements.existingRepoUrl.value = "";
  elements.newRepoName.value = "";
  repoModalController.open();
}

async function fileIssueToRepo() {
  if (!state.selectedRepoUrl) {
    alert("No repository selected.");
    return;
  }

  elements.fileIssueBtn.textContent = "Filing...";
  elements.fileIssueBtn.disabled = true;

  try {
    const response = await fetch(`${WORKER_URL}/conversations/${state.conversationId}/file-issue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_url: state.selectedRepoUrl,
        title: elements.issueTitle.value,
        description: elements.issueDescription.value,
        acceptance_criteria: elements.issueAcceptance.value
          .split("\n")
          .filter((l) => l.trim()),
        non_goals: elements.issueNonGoals.value.split("\n").filter((l) => l.trim()),
        constraints: elements.issueConstraints.value.split("\n").filter((l) => l.trim()),
      }),
    });

    if (!response.ok) throw new Error("Failed to file issue");

    const data = await response.json();
    state.isFiled = true;
    state.issueUrl = data.issue.html_url;
    state.issueNumber = data.issue.number;

    showSuccessSection();
  } catch (error) {
    alert(`Error filing issue: ${error.message}`);
    elements.fileIssueBtn.textContent = "📤 File Issue";
    elements.fileIssueBtn.disabled = false;
  }
}

// ============ UI State ============
//
// These three functions are the pre-existing entry points the conversation
// flow calls to switch "pages". They now delegate to the Router (FF-P04-01)
// instead of toggling .hidden directly, so every page transition is also a
// valid, bookmarkable URL — but the resulting visible DOM state is
// unchanged: showChatSection() still ends with hero hidden/chat visible,
// showSuccessSection() still ends with chat hidden/success visible (and now
// also hides history/settings, which didn't exist before and are therefore
// never a regression), resetIntake() still ends back at the hero section.

function showChatSection() {
  Router.navigate("/conversation");
}

function showSuccessSection() {
  Router.navigate("/success");

  elements.successMessage.textContent = `✅ Issue #${state.issueNumber} filed and ready for implementation!`;
  elements.issueLink.href = state.issueUrl;
  elements.issueLink.textContent = `View on GitHub (#${state.issueNumber}) →`;
}

function resetIntake() {
  state = {
    conversationId: null,
    messages: [],
    draftIssue: {
      title: "",
      description: "",
      acceptanceCriteria: [],
      nonGoals: [],
      constraints: [],
      dataBehavior: "",
      errorHandling: "",
    },
    isVoiceActive: false,
    isFiled: false,
    repoUrl: "",
    issueUrl: "",
    issueNumber: null,
  };

  localStorage.removeItem(STORAGE_KEY_SESSION);
  localStorage.removeItem(STORAGE_KEY_DRAFT);

  Router.navigate("/");
}

// ============ Utilities ============

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Start the app
document.addEventListener("DOMContentLoaded", init);
document.addEventListener("DOMContentLoaded", updateVersionFooter);

// Test hook (FF-P04-01): exposes the shell internals to the Node-based driver
// used by factory/tests/test_intake_web_shell.py
// (factory/tests/helpers/app_shell_driver.mjs). This is a no-op in the
// browser — nothing reads this global outside the test harness.
if (typeof globalThis !== "undefined") {
  globalThis.__DFACTORY_SHELL__ = {
    Router,
    AppShellState,
    pageSections,
    showPage,
    helpModalController,
    repoModalController,
    elements,
    getState: () => state,
  };
}

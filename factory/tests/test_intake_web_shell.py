"""
FF-P04-01 (D-NEW-001): Responsive application shell for factory/intake/web.

D-NEW-001 decided to extend the existing vanilla-JS frontend in place rather
than adopt a framework, so factory/intake/web/app.js grew a minimal
hash-based router (Router), a tiny observable UI-state container
(AppShellState), a generic page-visibility switch (showPage) and a reusable
modal focus-trap (createModal) -- all hand-rolled, no build step, no new
dependencies.

This test file has two tiers:

1. Static/structural checks (always run, no skip) directly against the
   checked-in source of app.js/index.html/style.css. These catch regressions
   in the pre-existing conversation-submission flow (function names, fetch
   endpoints, storage keys) and confirm the new shell markup/CSS exists,
   without needing a JS runtime.

2. Behavioral checks that shell out to Node (same pattern as
   test_intake_worker_auth.py) and run
   factory/tests/helpers/app_shell_driver.mjs, which loads the real app.js
   in a hand-rolled DOM/window/localStorage stub and exercises routing,
   state persistence/recovery, keyboard navigation (Escape + Tab-trap), focus
   management on route change, and the full conversation-submission flow
   end-to-end (regression). Skipped (not failed) if Node.js isn't available.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parents[2] / "factory" / "intake" / "web"
APP_JS = WEB_DIR / "app.js"
INDEX_HTML = WEB_DIR / "index.html"
STYLE_CSS = WEB_DIR / "style.css"
DRIVER_SCRIPT = Path(__file__).resolve().parent / "helpers" / "app_shell_driver.mjs"


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.fixture(scope="module")
def app_js_text() -> str:
    return APP_JS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def index_html_text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def style_css_text() -> str:
    return STYLE_CSS.read_text(encoding="utf-8")


# ============================================================================
# Tier 1: static/structural checks (no Node required)
# ============================================================================


class TestNoRegressionInExistingConversationFlow:
    """FF-P04-01 must extend app.js in place, not rewrite it: every
    pre-existing public function, constant and endpoint the conversation
    flow depends on must still be present with its original name/shape."""

    def test_worker_url_and_storage_keys_unchanged(self, app_js_text):
        assert 'const WORKER_URL = "https://dark-factory-intake.mohammad-tourk.workers.dev";' in app_js_text
        assert 'const STORAGE_KEY_SESSION = "dfactory_session_id";' in app_js_text
        assert 'const STORAGE_KEY_DRAFT = "dfactory_draft";' in app_js_text

    def test_shell_storage_key_is_a_new_distinct_key(self, app_js_text):
        """The new shell state must not reuse or collide with the
        conversation session/draft keys."""
        assert 'const STORAGE_KEY_UI_STATE = "dfactory_ui_state";' in app_js_text
        assert "dfactory_ui_state" != "dfactory_session_id"
        assert "dfactory_ui_state" != "dfactory_draft"

    @pytest.mark.parametrize(
        "signature",
        [
            "async function init()",
            "async function loadConversation()",
            "async function startVoice()",
            "async function startGeminiLive()",
            "async function simulateGeminiConversation()",
            "function startTextMode()",
            "async function sendTextMessage()",
            "async function addMessage(role, text)",
            "function renderMessages()",
            "function updateIssueDraft(text, role)",
            "function renderIssueDraft()",
            "function editIssue()",
            "function saveDraft()",
            "async function fileIssue()",
            "async function fileIssueToRepo()",
            "function showChatSection()",
            "function showSuccessSection()",
            "function resetIntake()",
            "function escapeHtml(text)",
        ],
    )
    def test_original_function_signatures_still_present(self, app_js_text, signature):
        assert signature in app_js_text, f"Expected unchanged signature {signature!r} in app.js"

    @pytest.mark.parametrize(
        "endpoint_fragment",
        [
            "`${WORKER_URL}/conversations`",
            "`${WORKER_URL}/conversations/${state.conversationId}`",
            "`${WORKER_URL}/conversations/${state.conversationId}/gemini-token`",
            "`${WORKER_URL}/conversations/${state.conversationId}/text-response`",
            "`${WORKER_URL}/conversations/${state.conversationId}/messages`",
            "`${WORKER_URL}/conversations/${state.conversationId}/file-issue`",
            "`${WORKER_URL}/projects`",
        ],
    )
    def test_worker_fetch_endpoints_unchanged(self, app_js_text, endpoint_fragment):
        assert endpoint_fragment in app_js_text, f"Expected unchanged Worker endpoint {endpoint_fragment!r}"

    def test_enter_to_send_shortcut_preserved(self, app_js_text):
        assert '"keypress"' in app_js_text and "sendTextMessage()" in app_js_text

    def test_business_logic_sections_not_removed(self, app_js_text):
        for heading in [
            "============ Voice Input ============",
            "============ Text Input ============",
            "============ Message Handling ============",
            "============ Issue Draft ============",
            "============ Filing Issue ============",
        ]:
            assert heading in app_js_text


class TestRouterAndStateModulesExist:
    def test_router_module_defined(self, app_js_text):
        assert "const Router = (() => {" in app_js_text
        for member in ["register", "navigate", "start", "resolve", "getCurrentRoute", "normalizeHash", "setNotFound"]:
            assert re.search(rf"\bfunction {member}\(", app_js_text), f"Router.{member} not found"

    def test_app_shell_state_module_defined(self, app_js_text):
        assert "const AppShellState = (() => {" in app_js_text
        for member in ["load", "setActiveRoute", "getState", "subscribe"]:
            assert re.search(rf"\bfunction {member}\(", app_js_text), f"AppShellState.{member} not found"

    def test_core_routes_registered(self, app_js_text):
        for route in ["/", "/conversation", "/success", "/history", "/settings"]:
            assert f'Router.register("{route}"' in app_js_text, f"Route {route!r} not registered"
        assert "Router.setNotFound(" in app_js_text

    def test_show_page_is_the_single_visibility_switch(self, app_js_text):
        assert "function showPage(name)" in app_js_text
        # Business-flow functions must drive visibility through the router,
        # not by touching classList directly (that was the pre-shell pattern).
        assert 'Router.navigate("/conversation")' in app_js_text
        assert 'Router.navigate("/success")' in app_js_text
        assert 'Router.navigate("/")' in app_js_text


class TestKeyboardAndFocusManagement:
    def test_modal_focus_trap_present(self, app_js_text):
        assert "function createModal(modalEl, getFocusables)" in app_js_text
        assert "function handleTab(event)" in app_js_text

    def test_escape_closes_modals(self, app_js_text):
        assert '"Escape"' in app_js_text
        assert "modal.close()" in app_js_text

    def test_tab_trap_wired_to_global_keydown(self, app_js_text):
        assert 'document.addEventListener("keydown"' in app_js_text
        assert "modal.handleTab(event)" in app_js_text

    def test_focus_moved_on_page_show(self, app_js_text):
        # showPage() must call .focus() on the shown section (route-change
        # focus management), not just toggle classes.
        match = re.search(r"function showPage\(name\) \{.*?\n\}", app_js_text, re.DOTALL)
        assert match, "showPage() body not found"
        assert "shown.focus()" in match.group(0) or ".focus()" in match.group(0)


class TestIndexHtmlShellMarkup:
    def test_skip_link_present(self, index_html_text):
        assert 'class="skip-link"' in index_html_text
        assert 'href="#main-content"' in index_html_text

    def test_primary_nav_present_with_four_routes(self, index_html_text):
        assert '<nav id="app-nav" class="app-nav" aria-label="Primary">' in index_html_text
        for nav_id, href in [
            ("nav-home", 'href="#/"'),
            ("nav-conversation", 'href="#/conversation"'),
            ("nav-history", 'href="#/history"'),
            ("nav-settings", 'href="#/settings"'),
        ]:
            assert f'id="{nav_id}"' in index_html_text
            assert href in index_html_text

    def test_history_and_settings_placeholder_pages_exist_and_start_hidden(self, index_html_text):
        for section_id in ["history-section", "settings-section"]:
            match = re.search(rf'<section id="{section_id}"[^>]*>', index_html_text)
            assert match, f"{section_id} not found"
            assert "hidden" in match.group(0)
            assert "page-section" in match.group(0)

    def test_existing_pages_still_present_and_tagged_page_section(self, index_html_text):
        for section_id in ["hero-section", "chat-section", "success-section"]:
            match = re.search(rf'<section id="{section_id}"[^>]*>', index_html_text)
            assert match, f"{section_id} not found"
            assert "page-section" in match.group(0)
            assert 'tabindex="-1"' in match.group(0)

    def test_chat_and_success_sections_still_start_hidden(self, index_html_text):
        for section_id in ["chat-section", "success-section"]:
            match = re.search(rf'<section id="{section_id}"[^>]*>', index_html_text)
            assert "hidden" in match.group(0)

    def test_hero_section_still_starts_visible(self, index_html_text):
        match = re.search(r'<section id="hero-section"[^>]*>', index_html_text)
        assert match
        assert "hidden" not in match.group(0)

    def test_version_and_app_scripts_still_loaded_in_order(self, index_html_text):
        version_idx = index_html_text.index('<script src="version.js">')
        app_idx = index_html_text.index('<script src="app.js">')
        assert version_idx < app_idx, "version.js must load before app.js (app.js calls updateVersionFooter)"


class TestResponsiveCss:
    def test_braces_balanced(self, style_css_text):
        """Regression guard for a real pre-existing bug: style.css had one
        more '}' than '{' (a stray extra closing brace after .repo-divider),
        which this change fixes while adding the shell's own rules."""
        assert style_css_text.count("{") == style_css_text.count("}")

    def test_mobile_first_breakpoint_present(self, style_css_text):
        assert "@media (max-width: 640px)" in style_css_text

    def test_desktop_multi_pane_breakpoint_present(self, style_css_text):
        assert "@media (min-width: 1024px)" in style_css_text
        desktop_block = style_css_text[style_css_text.index("@media (min-width: 1024px)"):]
        assert "grid-template-columns" in desktop_block
        assert "grid-template-areas" in desktop_block

    def test_nav_link_and_page_section_rules_present(self, style_css_text):
        assert ".app-nav" in style_css_text
        assert ".nav-link" in style_css_text
        assert '.nav-link[aria-current="page"]' in style_css_text
        assert ".page-section.hidden" in style_css_text

    def test_sr_only_and_skip_link_utilities_present(self, style_css_text):
        assert ".sr-only" in style_css_text
        assert ".skip-link" in style_css_text


# ============================================================================
# Tier 2: behavioral checks via the Node driver (routing/state/keyboard/focus
# flows, plus an end-to-end regression check of the conversation flow)
# ============================================================================

pytestmark_node = pytest.mark.skipif(
    not _node_available(),
    reason="Node.js is required to run the app-shell behavioral driver",
)


@pytest.fixture(scope="module")
def driver_run() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(DRIVER_SCRIPT), str(APP_JS)],
        capture_output=True,
        text=True,
    )


@pytestmark_node
def test_driver_all_checks_pass(driver_run: subprocess.CompletedProcess):
    assert driver_run.returncode == 0, (
        f"app-shell driver failed:\nstdout:\n{driver_run.stdout}\nstderr:\n{driver_run.stderr}"
    )
    assert "checks passed" in driver_run.stdout


@pytestmark_node
@pytest.mark.parametrize(
    "expected_pass",
    [
        # Route navigation
        "initial route resolves to '/'",
        "only the hero page is visible on initial load",
        "navigate('/conversation') updates current route",
        "navigating to /conversation shows only the chat page",
        "nav-conversation gets aria-current=page",
        "navigating to /history shows only the history page",
        "navigating to /settings shows only the settings page",
        "manually setting location.hash fires hashchange and updates the view",
        "unknown route redirects to '/' via notFound handler",
        # State persistence and recovery
        "UI state is persisted to localStorage under dfactory_ui_state",
        "persisted UI state records the active route",
        "AppShellState.load() recovers the persisted route from localStorage",
        "shell state does not touch dfactory_session_id",
        "shell state does not touch dfactory_draft",
        # Keyboard navigation flows
        "opening the help modal removes .hidden",
        "opening the help modal focuses its only focusable control",
        "Escape closes the open help modal",
        "closing the help modal restores focus to the trigger button",
        "opening the repo modal focuses its first focusable field",
        "Tab on the last modal control wraps focus to the first",
        "Shift+Tab on the first modal control wraps focus to the last",
        "Escape closes the open repo modal",
        # Focus management on route change
        "navigating to /conversation calls focus() on the chat section container",
        "navigating to /history calls focus() on the history section container",
        # Regression: existing conversation-submission flow
        "regression: clicking 'Type your idea instead' still POSTs /conversations",
        "regression: conversation id is still persisted to dfactory_session_id",
        "regression: starting text mode still routes to the conversation page",
        "regression: chat section is visible after starting text mode",
        "regression: sendTextMessage still POSTs the user message to /messages",
        "regression: sendTextMessage still requests /text-response for the AI reply",
        "regression: AI response is rendered into the messages container",
        "regression: the text input is cleared after sending",
        "regression: pressing Enter in the textarea still sends the message",
    ],
)
def test_specific_behavior(driver_run: subprocess.CompletedProcess, expected_pass: str):
    assert f"PASS: {expected_pass}" in driver_run.stdout, (
        f"Missing expected PASS line: {expected_pass!r}\nFull output:\n{driver_run.stdout}\n{driver_run.stderr}"
    )


@pytestmark_node
def test_phase04_01_gate_app_shell_operational(driver_run: subprocess.CompletedProcess):
    """
    FF-P04-01 Gate: responsive application shell (routing, state,
    keyboard/focus) is operational and the existing conversation-submission
    flow has no regression.
    """
    assert driver_run.returncode == 0, driver_run.stdout + driver_run.stderr
    assert re.search(r"All \d+ checks passed\.", driver_run.stdout), driver_run.stdout
    print("✓ Phase 04-01 Gate: app shell routing/state/keyboard/focus verified, no regression in conversation flow.")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

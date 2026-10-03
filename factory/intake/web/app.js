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

const WORKER_URL = "https://intake.ollama.mtourk.com";
const STORAGE_KEY_SESSION = "dfactory_session_id";
const STORAGE_KEY_DRAFT = "dfactory_draft";

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
};

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

  elements.fileIssueBtn.addEventListener("click", fileIssue);
  elements.editIssueBtn.addEventListener("click", editIssue);
  elements.saveDraftBtn.addEventListener("click", saveDraft);
  elements.newIntakeBtn.addEventListener("click", resetIntake);

  elements.helpBtn.addEventListener("click", () =>
    elements.helpModal.classList.remove("hidden")
  );
  elements.helpCloseBtn.addEventListener("click", () =>
    elements.helpModal.classList.add("hidden")
  );
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

  // Simulate AI response (in production, this would call Gemini API)
  setTimeout(() => {
    addMessage("ai", "Thanks for that input. Can you tell me more about the constraints?");
  }, 500);
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

  // TODO: select repo (or default to first project)
  const repoUrl = "https://github.com/mtourk/test-project"; // Placeholder

  elements.fileIssueBtn.textContent = "Filing...";
  elements.fileIssueBtn.disabled = true;

  try {
    const response = await fetch(`${WORKER_URL}/conversations/${state.conversationId}/file-issue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_url: repoUrl,
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

function showChatSection() {
  elements.heroSection.classList.add("hidden");
  elements.chatSection.classList.remove("hidden");
}

function showSuccessSection() {
  elements.chatSection.classList.add("hidden");
  elements.successSection.classList.remove("hidden");

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

  elements.heroSection.classList.remove("hidden");
  elements.chatSection.classList.add("hidden");
  elements.successSection.classList.add("hidden");
}

// ============ Utilities ============

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Start the app
document.addEventListener("DOMContentLoaded", init);

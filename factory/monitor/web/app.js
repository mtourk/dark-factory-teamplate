/**
 * Dark Factory — Ollama Monitor (Phase 18+)
 *
 * Polls the intake Worker's /ollama/status and /ollama/history endpoints to show:
 * - Live status: is Ollama reachable, what's loaded, is a request currently in flight
 * - Full history: every past request logged to the ollama_requests table
 *
 * Reuses the same Worker as the intake app (it owns the D1 database and the
 * server-side fetch to ollama.mtourk.com) — this page is read-only against it.
 */

const WORKER_URL = "https://dark-factory-intake.mohammad-tourk.workers.dev";
const STATUS_POLL_MS = 3000;
const HISTORY_PAGE_SIZE = 25;

let historyOffset = 0;
let historyTotal = 0;
let autoRefreshTimer = null;

const el = {
  statusDot: document.getElementById("status-dot"),
  statusReachable: document.getElementById("status-reachable"),
  statusLoaded: document.getElementById("status-loaded"),
  statusGenerating: document.getElementById("status-generating"),
  statusUpdated: document.getElementById("status-updated"),
  autoRefreshCheckbox: document.getElementById("auto-refresh-checkbox"),
  currentRequest: document.getElementById("current-request"),
  currentModel: document.getElementById("current-model"),
  currentStarted: document.getElementById("current-started"),
  currentElapsed: document.getElementById("current-elapsed"),
  currentPrompt: document.getElementById("current-prompt"),

  refreshHistoryBtn: document.getElementById("refresh-history-btn"),
  historyEmpty: document.getElementById("history-empty"),
  historyBody: document.getElementById("history-body"),
  prevPageBtn: document.getElementById("prev-page-btn"),
  nextPageBtn: document.getElementById("next-page-btn"),
  paginationInfo: document.getElementById("pagination-info"),

  detailModal: document.getElementById("detail-modal"),
  detailCloseBtn: document.getElementById("detail-close-btn"),
  detailId: document.getElementById("detail-id"),
  detailModel: document.getElementById("detail-model"),
  detailStatus: document.getElementById("detail-status"),
  detailStarted: document.getElementById("detail-started"),
  detailCompleted: document.getElementById("detail-completed"),
  detailDuration: document.getElementById("detail-duration"),
  detailPrompt: document.getElementById("detail-prompt"),
  detailResponse: document.getElementById("detail-response"),
  detailError: document.getElementById("detail-error"),
};

// ============ Init ============

function init() {
  refreshStatus();
  refreshHistory();

  el.refreshHistoryBtn.addEventListener("click", refreshHistory);
  el.prevPageBtn.addEventListener("click", () => {
    historyOffset = Math.max(0, historyOffset - HISTORY_PAGE_SIZE);
    refreshHistory();
  });
  el.nextPageBtn.addEventListener("click", () => {
    historyOffset += HISTORY_PAGE_SIZE;
    refreshHistory();
  });
  el.detailCloseBtn.addEventListener("click", () => el.detailModal.classList.add("hidden"));
  el.detailModal.addEventListener("click", (e) => {
    if (e.target === el.detailModal) el.detailModal.classList.add("hidden");
  });
  el.autoRefreshCheckbox.addEventListener("change", restartAutoRefresh);

  restartAutoRefresh();
}

function restartAutoRefresh() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  if (el.autoRefreshCheckbox.checked) {
    autoRefreshTimer = setInterval(refreshStatus, STATUS_POLL_MS);
  }
}

// ============ Status ============

async function refreshStatus() {
  try {
    const response = await fetch(`${WORKER_URL}/ollama/status`);
    if (!response.ok) throw new Error(`Status ${response.status}`);
    const data = await response.json();
    renderStatus(data);
  } catch (error) {
    console.error("Failed to fetch Ollama status:", error);
    el.statusDot.className = "status-dot down";
    el.statusReachable.textContent = "Error";
    el.statusUpdated.textContent = `Failed to reach monitor API: ${error.message}`;
  }
}

function renderStatus(data) {
  el.statusReachable.textContent = data.reachable ? "Yes" : "No";

  const models = (data.loaded_models || []).map((m) => m.name || m.model).filter(Boolean);
  el.statusLoaded.textContent = models.length ? models.join(", ") : "(none loaded)";

  el.statusGenerating.textContent = data.is_generating ? "Yes" : "No";

  if (!data.reachable) {
    el.statusDot.className = "status-dot down";
  } else if (data.is_generating) {
    el.statusDot.className = "status-dot busy";
  } else {
    el.statusDot.className = "status-dot ok";
  }

  if (data.is_generating && data.current_request) {
    el.currentRequest.classList.remove("hidden");
    const req = data.current_request;
    el.currentModel.textContent = req.model || "—";
    el.currentStarted.textContent = formatTimestamp(req.started_at);
    el.currentElapsed.textContent = formatElapsed(req.started_at);
    el.currentPrompt.textContent = req.prompt_text || "—";
  } else {
    el.currentRequest.classList.add("hidden");
  }

  el.statusUpdated.textContent = `Last checked: ${new Date().toLocaleTimeString()}`;
}

function formatElapsed(startedAtIso) {
  const started = new Date(startedAtIso + (startedAtIso.endsWith("Z") ? "" : "Z"));
  const seconds = Math.max(0, Math.round((Date.now() - started.getTime()) / 1000));
  return `${seconds}s`;
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  return d.toLocaleString();
}

// ============ History ============

async function refreshHistory() {
  el.refreshHistoryBtn.disabled = true;
  el.refreshHistoryBtn.textContent = "Loading…";

  try {
    const response = await fetch(
      `${WORKER_URL}/ollama/history?limit=${HISTORY_PAGE_SIZE}&offset=${historyOffset}`
    );
    if (!response.ok) throw new Error(`Status ${response.status}`);
    const data = await response.json();
    historyTotal = data.total || 0;
    renderHistory(data.requests || []);
    renderPagination();
  } catch (error) {
    console.error("Failed to fetch Ollama history:", error);
    el.historyBody.innerHTML = "";
    el.historyEmpty.textContent = `Failed to load history: ${error.message}`;
    el.historyEmpty.classList.remove("hidden");
  } finally {
    el.refreshHistoryBtn.disabled = false;
    el.refreshHistoryBtn.textContent = "↻ Refresh";
  }
}

function renderHistory(requests) {
  if (!requests.length) {
    el.historyBody.innerHTML = "";
    el.historyEmpty.textContent = "No requests logged yet.";
    el.historyEmpty.classList.remove("hidden");
    return;
  }

  el.historyEmpty.classList.add("hidden");

  el.historyBody.innerHTML = requests
    .map(
      (req, i) => `
    <tr data-index="${i}">
      <td>${formatTimestamp(req.started_at)}</td>
      <td><span class="badge ${req.status}">${req.status}</span></td>
      <td>${escapeHtml(req.model || "—")}</td>
      <td><span class="cell-truncate">${escapeHtml(req.prompt_text || "—")}</span></td>
      <td><span class="cell-truncate">${escapeHtml(req.response_text || req.error_message || "—")}</span></td>
      <td>${req.duration_ms != null ? `${req.duration_ms} ms` : "—"}</td>
    </tr>
  `
    )
    .join("");

  el.historyBody.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => showDetail(requests[Number(row.dataset.index)]));
  });
}

function renderPagination() {
  const start = historyOffset + 1;
  const end = Math.min(historyOffset + HISTORY_PAGE_SIZE, historyTotal);
  el.paginationInfo.textContent = historyTotal
    ? `${start}–${end} of ${historyTotal}`
    : "0 of 0";

  el.prevPageBtn.disabled = historyOffset === 0;
  el.nextPageBtn.disabled = end >= historyTotal;
}

function showDetail(req) {
  el.detailId.textContent = req.id || "—";
  el.detailModel.textContent = req.model || "—";
  el.detailStatus.textContent = req.status || "—";
  el.detailStarted.textContent = formatTimestamp(req.started_at);
  el.detailCompleted.textContent = formatTimestamp(req.completed_at);
  el.detailDuration.textContent = req.duration_ms != null ? `${req.duration_ms} ms` : "—";
  el.detailPrompt.textContent = req.prompt_text || "—";
  el.detailResponse.textContent = req.response_text || "—";
  el.detailError.textContent = req.error_message || "—";
  el.detailModal.classList.remove("hidden");
}

// ============ Utilities ============

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

document.addEventListener("DOMContentLoaded", init);

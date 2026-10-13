/**
 * Dark Factory — AI Request Monitor
 *
 * Polls the intake Worker's provider-neutral /ai/status and /ai/history endpoints.
 * It displays requests routed through OmniRoute, including requested/actual model,
 * provider metadata when supplied, prompts, responses, usage, and failures.
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
  detailProvider: document.getElementById("detail-provider"),
  detailRequestedModel: document.getElementById("detail-requested-model"),
  detailRequestType: document.getElementById("detail-request-type"),
  detailUsage: document.getElementById("detail-usage"),
  detailCost: document.getElementById("detail-cost"),
  detailGatewayLatency: document.getElementById("detail-gateway-latency"),
  detailFallbackAttempts: document.getElementById("detail-fallback-attempts"),
  detailCacheHit: document.getElementById("detail-cache-hit"),
  detailGatewayRequestId: document.getElementById("detail-gateway-request-id"),
  detailGatewayVersion: document.getElementById("detail-gateway-version"),
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
    const response = await fetch(`${WORKER_URL}/ai/status`);
    if (!response.ok) throw new Error(`Status ${response.status}`);
    const data = await response.json();
    renderStatus(data);
  } catch (error) {
    console.error("Failed to fetch AI monitor status:", error);
    el.statusDot.className = "status-dot down";
    el.statusReachable.textContent = "Error";
    el.statusUpdated.textContent = `Failed to reach monitor API: ${error.message}`;
  }
}

function renderStatus(data) {
  el.statusReachable.textContent = "Connected";
  el.statusLoaded.textContent = String(data.total_requests ?? 0);
  el.statusGenerating.textContent = data.is_processing ? "Yes" : "No";

  if (data.is_processing) {
    el.statusDot.className = "status-dot busy";
  } else {
    el.statusDot.className = "status-dot ok";
  }

  if (data.is_processing && data.current_request) {
    el.currentRequest.classList.remove("hidden");
    const req = data.current_request;
    el.currentModel.textContent = req.actual_model || req.requested_model || "—";
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
      `${WORKER_URL}/ai/history?limit=${HISTORY_PAGE_SIZE}&offset=${historyOffset}`
    );
    if (!response.ok) throw new Error(`Status ${response.status}`);
    const data = await response.json();
    historyTotal = data.total || 0;
    renderHistory(data.requests || []);
    renderPagination();
  } catch (error) {
    console.error("Failed to fetch AI request history:", error);
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
      <td>${escapeHtml([req.provider, req.actual_model || req.requested_model].filter(Boolean).join(" / ") || "—")}</td>
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
  el.detailModel.textContent = req.actual_model || req.requested_model || "—";
  if (el.detailProvider) el.detailProvider.textContent = req.provider || "Not supplied by gateway";
  if (el.detailRequestedModel) el.detailRequestedModel.textContent = req.requested_model || "—";
  if (el.detailRequestType) el.detailRequestType.textContent = req.request_type || "—";
  if (el.detailUsage) el.detailUsage.textContent = [req.input_tokens != null ? `Input ${req.input_tokens}` : null, req.output_tokens != null ? `Output ${req.output_tokens}` : null].filter(Boolean).join(" / ") || "Not supplied";
  if (el.detailCost) el.detailCost.textContent = req.cost_usd != null ? req.cost_usd : "Not supplied";
  if (el.detailGatewayLatency) el.detailGatewayLatency.textContent = req.gateway_latency_ms != null ? `${req.gateway_latency_ms} ms` : "Not supplied";
  if (el.detailFallbackAttempts) el.detailFallbackAttempts.textContent = req.fallback_attempts != null ? String(req.fallback_attempts) : "Not supplied";
  if (el.detailCacheHit) el.detailCacheHit.textContent = req.cache_hit == null ? "Not supplied" : (req.cache_hit ? "Yes" : "No");
  if (el.detailGatewayRequestId) el.detailGatewayRequestId.textContent = req.gateway_request_id || "Not supplied";
  if (el.detailGatewayVersion) el.detailGatewayVersion.textContent = req.gateway_version || "Not supplied";
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

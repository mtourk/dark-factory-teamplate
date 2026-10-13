/**
 * Dark Factory Intake Worker — Main Entry Point
 *
 * Phase 17.0 backend: handles feature discovery conversations, GitHub repo creation,
 * and issue filing. Runs entirely on Cloudflare infrastructure.
 *
 * Routes:
 * - POST /conversations - start a new discovery session
 * - GET /conversations/:id - fetch a conversation and its history
 * - POST /conversations/:id/messages - add a user message
 * - POST /conversations/:id/text-response - get AI response for text message
 * - POST /conversations/:id/gemini-token - mint ephemeral Gemini Live token
 * - POST /conversations/:id/file-issue - file the discovered issue
 * - POST /projects - create a new project repository
 * - GET /pending-profiles - list profiles awaiting local sync
 * - POST /pending-profiles/:id/sync-confirmed - mark profile synced
 * - GET /ollama/status - live Ollama status (loaded models + any in-flight request)
 * - GET /ollama/history - paginated history of past Ollama requests
 *
 * Auth (FF-P03-01, D-NEW-002 Option A — Cloudflare Access only):
 * - Mutating routes (POST /conversations, /projects, /messages, /file-issue,
 *   /text-response) require a verified Cf-Access-Jwt-Assertion header.
 * - All monitoring routes (/ai/status, /ai/history, /ollama/status,
 *   /ollama/history) require verified Access because they expose prompts
 *   or responses. Only GET /version remains public for basic uptime checks.
 * - See verifyAccessJwt() below. No per-user D1 profile lookup yet (Phase 04+).
 *
 * Secrets (Cloudflare Worker environment):
 * - GITHUB_REPO_CREATE_TOKEN: narrow GitHub PAT for repo creation
 * - GEMINI_API_KEY: Gemini API key (never exposed to browser)
 *
 * Database (D1):
 * - conversations, messages, pending_profiles, ollama_requests tables
 *
 * CORS: allow-listed origins only (factory.mtourk.com for the intake UI,
 * monitor.mtourk.com for the provider-neutral AI request monitor).
 */

import IntakeDB from "./db";
import GeminiIntegration from "./gemini";
import GitHubIntegration from "./github";
import { AIPlatformError, getAIPlatformTextResponse } from "./ai-platform";

export interface Env {
  DB: D1Database;
  GITHUB_REPO_CREATE_TOKEN: string;
  GEMINI_API_KEY: string;
  ENVIRONMENT: string;
  GITHUB_ORG: string;
  OLLAMA_URL?: string;
  OLLAMA_MODEL?: string;
  AI_PLATFORM_BASE_URL?: string;
  AI_PLATFORM_API_KEY?: string;
  AI_PLATFORM_MODEL?: string;
  AI_PLATFORM_ALLOWED_MODELS?: string;
  AI_PLATFORM_TIMEOUT_SECONDS?: string;
  VERSION?: string;
  DEPLOYED_AT?: string;
  // FF-P03-01 / D-NEW-002 (Option A: Cloudflare Access only).
  // AUD of the Cloudflare Access Application fronting this Worker/Pages (dashboard-provided).
  CLOUDFLARE_ACCESS_AUD: string;
  // Team domain (the `<team>` in `<team>.cloudflareaccess.com`) used to fetch the Access JWKS.
  CLOUDFLARE_ACCESS_TEAM_DOMAIN?: string;
}

// Each frontend gets its own hostname (one-hostname-one-resource, see ADR-007 §3).
// Add new origins here as new Pages projects are attached — never widen this to "*".
const ALLOWED_ORIGINS = ["https://factory.mtourk.com", "https://monitor.mtourk.com"];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": ALLOWED_ORIGINS[0],
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Content-Type": "application/json",
};

function resolveCorsOrigin(request: Request): string {
  const origin = request.headers.get("Origin") || "";
  return ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
}

// ============ Cloudflare Access authentication (FF-P03-01, D-NEW-002 Option A) ============
//
// Option A: Cloudflare Access fronts the Worker/Pages and attaches a signed JWT
// (`Cf-Access-Jwt-Assertion`) to every request it routes through. We verify that
// JWT ourselves (rather than trusting the header blindly) so a request that
// reaches the Worker directly — bypassing Access — can't forge the header.
//
// This phase only verifies identity (signature + audience + expiry) and allows
// the request through. It does NOT look up or create a per-user D1 profile
// (that's Phase 04+) and does NOT do token masking (that's Phase 03-02).
//
// Reference: https://developers.cloudflare.com/cloudflare-one/identity/authorization-policy/verify-jwt/

interface AccessJwtResult {
  valid: boolean;
  email?: string;
  error?: string;
}

type RouteMatcher = { method: string; pattern: RegExp };

// Mutating routes: must present a verified Cloudflare Access identity.
const ROUTES_REQUIRING_AUTH: RouteMatcher[] = [
  { method: "POST", pattern: /^\/conversations$/ },
  { method: "POST", pattern: /^\/projects$/ },
  { method: "POST", pattern: /^\/conversations\/([^/]+)\/file-issue$/ },
  { method: "POST", pattern: /^\/conversations\/([^/]+)\/messages$/ },
  { method: "POST", pattern: /^\/conversations\/([^/]+)\/text-response$/ },
  // All request-monitoring endpoints expose prompts, responses, or provider telemetry.
  { method: "GET", pattern: /^\/ai\/status$/ },
  { method: "GET", pattern: /^\/ai\/history$/ },
  { method: "GET", pattern: /^\/ollama\/status$/ },
  { method: "GET", pattern: /^\/ollama\/history$/ },
];

// Only non-sensitive health/history compatibility endpoints remain public.
// AI request status/history contain complete prompts and responses and must be
// protected by a verified Cloudflare Access identity.
const ROUTES_PUBLIC: RouteMatcher[] = [
  { method: "GET", pattern: /^\/version$/ },
];

function matchesRoute(method: string, path: string, routes: RouteMatcher[]): boolean {
  return routes.some((route) => route.method === method && route.pattern.test(path));
}

function routeRequiresAuth(method: string, path: string): boolean {
  if (matchesRoute(method, path, ROUTES_PUBLIC)) {
    return false;
  }
  return matchesRoute(method, path, ROUTES_REQUIRING_AUTH);
}

// Cached across requests within the same Worker isolate so we don't fetch the
// JWKS on every request. Cold starts always re-fetch.
let cachedAccessJwks: { keys: JsonWebKey[] } | null = null;
let cachedAccessJwksAt = 0;
const ACCESS_JWKS_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

async function fetchAccessJwks(env: Env): Promise<{ keys: JsonWebKey[] }> {
  const now = Date.now();
  if (cachedAccessJwks && now - cachedAccessJwksAt < ACCESS_JWKS_CACHE_TTL_MS) {
    return cachedAccessJwks;
  }

  if (!env.CLOUDFLARE_ACCESS_TEAM_DOMAIN) {
    throw new Error("CLOUDFLARE_ACCESS_TEAM_DOMAIN not configured");
  }

  const certsUrl = `https://${env.CLOUDFLARE_ACCESS_TEAM_DOMAIN}.cloudflareaccess.com/cdn-cgi/access/certs`;
  const response = await fetch(certsUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch Access JWKS (${response.status})`);
  }

  const jwks = (await response.json()) as { keys: JsonWebKey[] };
  cachedAccessJwks = jwks;
  cachedAccessJwksAt = now;
  return jwks;
}

function base64UrlToUint8Array(base64Url: string): Uint8Array {
  const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
  const padding = base64.length % 4 === 0 ? "" : "=".repeat(4 - (base64.length % 4));
  const binary = atob(base64 + padding);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function base64UrlDecodeToString(base64Url: string): string {
  return new TextDecoder().decode(base64UrlToUint8Array(base64Url));
}

/**
 * Verify the `Cf-Access-Jwt-Assertion` header Cloudflare Access attaches to
 * every request it routes through. Checks signature (via the Access team's
 * published JWKS), audience (CLOUDFLARE_ACCESS_AUD), and expiry.
 */
async function verifyAccessJwt(request: Request, env: Env): Promise<AccessJwtResult> {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token) {
    return { valid: false, error: "Missing Cf-Access-Jwt-Assertion header" };
  }

  if (!env.CLOUDFLARE_ACCESS_AUD) {
    return { valid: false, error: "CLOUDFLARE_ACCESS_AUD not configured on Worker" };
  }

  const parts = token.split(".");
  if (parts.length !== 3) {
    return { valid: false, error: "Malformed JWT (expected 3 segments)" };
  }
  const [headerB64, payloadB64, signatureB64] = parts;

  let header: { kid?: string; alg?: string };
  let payload: { aud?: string | string[]; exp?: number; email?: string };
  try {
    header = JSON.parse(base64UrlDecodeToString(headerB64));
    payload = JSON.parse(base64UrlDecodeToString(payloadB64));
  } catch {
    return { valid: false, error: "Malformed JWT (header/payload not valid JSON)" };
  }

  try {
    const jwks = await fetchAccessJwks(env);
    const matchingKey = jwks.keys.find((k) => (k as { kid?: string }).kid === header.kid);
    if (!matchingKey) {
      return { valid: false, error: "No matching Access signing key for JWT kid" };
    }

    const cryptoKey = await crypto.subtle.importKey(
      "jwk",
      matchingKey,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"]
    );

    const signature = base64UrlToUint8Array(signatureB64);
    const signedInput = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
    const signatureValid = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5",
      cryptoKey,
      signature,
      signedInput
    );

    if (!signatureValid) {
      return { valid: false, error: "Invalid JWT signature" };
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    return { valid: false, error: `JWT signature verification failed: ${msg}` };
  }

  const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!audiences.includes(env.CLOUDFLARE_ACCESS_AUD)) {
    return { valid: false, error: "JWT audience does not match CLOUDFLARE_ACCESS_AUD" };
  }

  const nowSeconds = Math.floor(Date.now() / 1000);
  if (typeof payload.exp === "number" && payload.exp < nowSeconds) {
    return { valid: false, error: "JWT expired" };
  }

  return { valid: true, email: payload.email };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const corsOrigin = resolveCorsOrigin(request);

    if (request.method === "OPTIONS") {
      return new Response("OK", {
        headers: { ...CORS_HEADERS, "Access-Control-Allow-Origin": corsOrigin },
      });
    }

    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    // FF-P03-01 / D-NEW-002 (Option A): gate every mutating route behind a
    // verified Cloudflare Access identity before it reaches a handler.
    // Read-only/health routes (ROUTES_PUBLIC) are intentionally skipped.
    if (routeRequiresAuth(method, path)) {
      const auth = await verifyAccessJwt(request, env);
      if (!auth.valid) {
        const unauthorized = json(
          { error: `Unauthorized: ${auth.error || "invalid Cloudflare Access identity"}` },
          401
        );
        unauthorized.headers.set("Access-Control-Allow-Origin", corsOrigin);
        return unauthorized;
      }
    }

    let response: Response;
    try {
      // Route dispatcher
      if (path === "/conversations" && method === "POST") {
        response = await handleCreateConversation(env);
      } else if (path === "/version" && method === "GET") {
        response = await handleGetVersion(env);
      } else if (path === "/ollama/status" && method === "GET") {
        response = await handleOllamaStatus(env);
      } else if (path === "/ollama/history" && method === "GET") {
        response = await handleOllamaHistory(env, request);
      } else if (path === "/ai/status" && method === "GET") {
        response = await handleAIStatus(env);
      } else if (path === "/ai/history" && method === "GET") {
        response = await handleAIHistory(env, request);
      } else if (/^\/conversations\/([^/]+)$/.test(path) && method === "GET") {
        response = await handleGetConversation(env, path.match(/^\/conversations\/([^/]+)$/)![1]);
      } else if (/^\/conversations\/([^/]+)\/messages$/.test(path) && method === "POST") {
        response = await handlePostMessage(env, path.match(/^\/conversations\/([^/]+)\/messages$/)![1], request);
      } else if (/^\/conversations\/([^/]+)\/gemini-token$/.test(path) && method === "POST") {
        response = await handleMintGeminiToken(env, path.match(/^\/conversations\/([^/]+)\/gemini-token$/)![1]);
      } else if (/^\/conversations\/([^/]+)\/file-issue$/.test(path) && method === "POST") {
        response = await handleFileIssue(env, path.match(/^\/conversations\/([^/]+)\/file-issue$/)![1], request);
      } else if (path === "/projects" && method === "POST") {
        response = await handleCreateProject(env, request);
      } else if (path === "/pending-profiles" && method === "GET") {
        response = await handleListPendingProfiles(env);
      } else if (/^\/pending-profiles\/([^/]+)\/sync-confirmed$/.test(path) && method === "POST") {
        response = await handleMarkProfileSynced(env, path.match(/^\/pending-profiles\/([^/]+)\/sync-confirmed$/)![1]);
      } else if (/^\/conversations\/([^/]+)\/text-response$/.test(path) && method === "POST") {
        response = await handleTextResponse(env, path.match(/^\/conversations\/([^/]+)\/text-response$/)![1], request);
      } else {
        response = notFound();
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("Worker error:", errorMsg, error);
      response = json({ error: errorMsg }, 500);
    }

    response.headers.set("Access-Control-Allow-Origin", corsOrigin);
    return response;
  },
};

// ============ Handlers ============

async function handleGetVersion(env: Env): Promise<Response> {
  const version = env.VERSION || "unknown";
  const deployed_at = env.DEPLOYED_AT || new Date().toISOString();
  return json({ version, deployed_at });
}

async function handleCreateConversation(env: Env): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const conversation = await db.createConversation();
  return json({ conversation }, 201);
}

async function handleGetConversation(env: Env, conversationId: string): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const conversation = await db.getConversation(conversationId);

  if (!conversation) {
    return json({ error: "Conversation not found" }, 404);
  }

  const messages = await db.getMessages(conversationId);

  return json({ conversation, messages });
}

async function handlePostMessage(
  env: Env,
  conversationId: string,
  request: Request
): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const body = await request.json() as any;

  if (!body.text) {
    return json({ error: "Message text required" }, 400);
  }

  // Verify conversation exists
  const conversation = await db.getConversation(conversationId);
  if (!conversation) {
    return json({ error: "Conversation not found" }, 404);
  }

  // Add user message
  const message = await db.addMessage(conversationId, "user", body.text);

  return json({ message }, 201);
}

async function handleMintGeminiToken(env: Env, conversationId: string): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const conversation = await db.getConversation(conversationId);

  if (!conversation) {
    return json({ error: "Conversation not found" }, 404);
  }

  const gemini = new GeminiIntegration(env.GEMINI_API_KEY, env.OLLAMA_URL, env.OLLAMA_MODEL);
  const tokenResponse = await gemini.createEphemeralToken();

  return json(tokenResponse);
}

async function handleFileIssue(
  env: Env,
  conversationId: string,
  request: Request
): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const body = await request.json() as any;

  if (!body.repo_url || !body.title) {
    return json({ error: "repo_url and title required" }, 400);
  }

  const conversation = await db.getConversation(conversationId);
  if (!conversation) {
    return json({ error: "Conversation not found" }, 404);
  }

  // Extract owner/repo from URL
  const repoMatch = body.repo_url.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (!repoMatch) {
    return json({ error: "Invalid GitHub repo URL" }, 400);
  }

  const [, owner, repoName] = repoMatch;
  const repo = `${owner}/${repoName}`;

  const github = new GitHubIntegration(env.GITHUB_REPO_CREATE_TOKEN, owner);

  try {
    // Ensure labels exist
    await github.ensureLabelsExist(repo);

    // Get full conversation history to include in the issue
    const allMessages = await db.getMessages(conversationId);

    // File the issue
    const issue = await github.fileFeatureIssue(repo, body.title, {
      description: body.description,
      acceptanceCriteria: body.acceptance_criteria,
      nonGoals: body.non_goals,
      constraints: body.constraints,
      rawConversation: allMessages,
    });

    // Update conversation to filed status
    const updated = await db.fileConversation(
      conversationId,
      body.repo_url,
      issue.number,
      issue.html_url
    );

    return json({ conversation: updated, issue });
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error("File issue error:", errorMsg, error);
    return json({ error: `Failed to file issue: ${errorMsg}` }, 500);
  }
}

async function handleCreateProject(env: Env, request: Request): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const body = await request.json() as any;

  if (!body.name) {
    return json({ error: "Project name required" }, 400);
  }

  const github = new GitHubIntegration(env.GITHUB_REPO_CREATE_TOKEN, env.GITHUB_ORG);

  // Create the repository
  const repo = await github.createProjectRepository(body.name);

  // Create labels
  await github.ensureLabelsExist(repo.full_name);

  // Record in pending_profiles for local sync
  const profile = await db.createPendingProfile(
    body.name,
    repo.html_url,
    repo.owner,
    repo.name
  );

  return json({ repo, profile }, 201);
}

async function handleListPendingProfiles(env: Env): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const profiles = await db.getPendingProfiles(true); // unsyncedOnly = true
  return json({ profiles });
}

async function handleMarkProfileSynced(env: Env, profileId: string): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const profile = await db.markProfileSynced(profileId);
  return json({ profile });
}

async function handleTextResponse(
  env: Env,
  conversationId: string,
  request: Request
): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const body = await request.json() as any;

  if (!body.text) {
    return json({ error: "Message text required" }, 400);
  }

  // Verify conversation exists
  const conversation = await db.getConversation(conversationId);
  if (!conversation) {
    return json({ error: "Conversation not found" }, 404);
  }

  // Get full conversation history and route text only through the shared AI Platform.
  // No Gemini/Ollama fallback is permitted for text discovery.
  const messages = await db.getMessages(conversationId);
  const allMessages = [...messages, { role: "user", text: body.text }];

  const systemPrompt = GeminiIntegration.getDiscoverySystemPrompt();
  const promptText = JSON.stringify([
    { role: "system", content: systemPrompt },
    ...allMessages.map((message) => ({
      role: message.role === "user" ? "user" : "assistant",
      content: message.text,
    })),
  ]);
  const requestedModel = env.AI_PLATFORM_MODEL?.trim() || "unconfigured";
  const startedAt = Date.now();
  // Fail closed if monitoring cannot persist the request: the goal is a complete,
  // auditable history, not an AI call that silently bypasses Monitor.
  const aiRequest = await db.createAIRequest({
    conversationId,
    requestType: "text-discovery",
    requestedModel,
    promptText,
  });

  try {
    const result = await getAIPlatformTextResponse(
      {
        baseUrl: env.AI_PLATFORM_BASE_URL,
        apiKey: env.AI_PLATFORM_API_KEY,
        model: env.AI_PLATFORM_MODEL,
        allowedModels: env.AI_PLATFORM_ALLOWED_MODELS,
        timeoutSeconds: env.AI_PLATFORM_TIMEOUT_SECONDS,
      },
      allMessages.map((message) => ({ role: message.role, text: message.text })),
      systemPrompt
    );
    await db.completeAIRequest({
      id: aiRequest.id,
      actualModel: result.actualModel,
      provider: result.provider,
      responseText: result.content,
      durationMs: Date.now() - startedAt,
      inputTokens: result.inputTokens,
      outputTokens: result.outputTokens,
      costUsd: result.costUsd,
      gatewayLatencyMs: result.gatewayLatencyMs,
      fallbackAttempts: result.fallbackAttempts,
      cacheHit: result.cacheHit,
      gatewayRequestId: result.gatewayRequestId,
      gatewayVersion: result.gatewayVersion,
      rawMetadata: JSON.stringify(result.rawMetadata),
    });
    return json({ response: result.content, request_id: aiRequest.id });
  } catch (error) {
    const safeMessage = error instanceof AIPlatformError
      ? error.message
      : "AI Platform request failed.";
    try {
      await db.failAIRequest(aiRequest.id, safeMessage, Date.now() - startedAt);
    } catch {
      console.error("Could not finalize AI request monitoring record.");
    }
    if (error instanceof AIPlatformError) {
      return json({ error: error.message, request_id: aiRequest.id }, error.statusCode);
    }
    console.error("AI Platform text request failed unexpectedly.");
    return json({ error: safeMessage, request_id: aiRequest.id }, 502);
  }
}

/** Provider-neutral monitoring status for Monitor.mtourk.com. */
async function handleAIStatus(env: Env): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const [pendingRequest, lastRequest, total] = await Promise.all([
    db.getPendingAIRequest(),
    db.getLastAIRequest(),
    db.getAIRequestHistoryCount(),
  ]);
  return json({
    service: "AI Request Monitor",
    total_requests: total,
    is_processing: !!pendingRequest,
    current_request: pendingRequest,
    last_request: lastRequest,
  });
}

/** Paginated provider-neutral AI request history, newest first. */
async function handleAIHistory(env: Env, request: Request): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const url = new URL(request.url);
  const limit = Math.min(Math.max(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 1), 200);
  const offset = Math.max(parseInt(url.searchParams.get("offset") || "0", 10) || 0, 0);
  const [requests, total] = await Promise.all([
    db.getAIRequestHistory(limit, offset),
    db.getAIRequestHistoryCount(),
  ]);
  return json({ requests, total, limit, offset });
}

/**
 * Live Ollama status for the monitoring dashboard (monitor.mtourk.com, Phase 18+).
 *
 * Combines two signals:
 * - Ollama's own /api/ps (what's actually loaded in memory right now)
 * - Our own ollama_requests log (whether a request we initiated is still in flight,
 *   since /api/ps alone doesn't tell you if a response is being generated for *us*)
 */
async function handleOllamaStatus(env: Env): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const OLLAMA_URL = "https://ollama.mtourk.com";

  let reachable = false;
  let loadedModels: unknown[] = [];
  try {
    const psResponse = await fetch(`${OLLAMA_URL}/api/ps`);
    if (psResponse.ok) {
      const psData = (await psResponse.json()) as any;
      loadedModels = psData.models || [];
      reachable = true;
    }
  } catch (error) {
    console.warn(`Ollama /api/ps check failed: ${error instanceof Error ? error.message : String(error)}`);
  }

  const [pendingRequest, lastRequest] = await Promise.all([
    db.getPendingOllamaRequest(),
    db.getLastOllamaRequest(),
  ]);

  return json({
    reachable,
    loaded_models: loadedModels,
    is_generating: !!pendingRequest,
    current_request: pendingRequest,
    last_request: lastRequest,
  });
}

/** Paginated history of past Ollama requests, newest first. */
async function handleOllamaHistory(env: Env, request: Request): Promise<Response> {
  const db = new IntakeDB(env.DB);
  const url = new URL(request.url);
  const limit = Math.min(Math.max(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 1), 200);
  const offset = Math.max(parseInt(url.searchParams.get("offset") || "0", 10) || 0, 0);

  const [requests, total] = await Promise.all([
    db.getOllamaHistory(limit, offset),
    db.getOllamaHistoryCount(),
  ]);

  return json({ requests, total, limit, offset });
}

// ============ Utilities ============

function json(data: any, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: CORS_HEADERS,
  });
}

function notFound(): Response {
  return json({ error: "Not found" }, 404);
}

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
 * Secrets (Cloudflare Worker environment):
 * - GITHUB_REPO_CREATE_TOKEN: narrow GitHub PAT for repo creation
 * - GEMINI_API_KEY: Gemini API key (never exposed to browser)
 *
 * Database (D1):
 * - conversations, messages, pending_profiles, ollama_requests tables
 *
 * CORS: allow-listed origins only (factory.mtourk.com for the intake UI,
 * monitor.mtourk.com for the Ollama monitoring dashboard added in Phase 18+)
 */

import IntakeDB from "./db";
import GeminiIntegration from "./gemini";
import GitHubIntegration from "./github";

export interface Env {
  DB: D1Database;
  GITHUB_REPO_CREATE_TOKEN: string;
  GEMINI_API_KEY: string;
  ENVIRONMENT: string;
  GITHUB_ORG: string;
  OLLAMA_URL?: string;
  OLLAMA_MODEL?: string;
  VERSION?: string;
  DEPLOYED_AT?: string;
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

  // Debug: check if secrets exist
  const hasGeminiKey = !!env.GEMINI_API_KEY;
  if (!hasGeminiKey) {
    console.error("GEMINI_API_KEY is missing from env:", Object.keys(env));
    return json({ error: "GEMINI_API_KEY secret not configured", debug: { keys: Object.keys(env) } }, 500);
  }

  // Get full conversation history
  const messages = await db.getMessages(conversationId);

  // Add the user's message to the history
  const allMessages = [...messages, { role: "user", text: body.text }];

  // Get Gemini response (prefers local Ollama; db + conversationId let it log to ollama_requests
  // for the monitoring dashboard — see handleOllamaStatus/handleOllamaHistory below)
  const gemini = new GeminiIntegration(env.GEMINI_API_KEY, env.OLLAMA_URL, env.OLLAMA_MODEL);
  const responseText = await gemini.getDiscoveryResponse(
    allMessages.map((m) => ({ role: m.role, text: m.text })),
    db,
    conversationId
  );

  return json({ response: responseText });
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

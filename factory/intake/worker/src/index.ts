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
 *
 * Secrets (Cloudflare Worker environment):
 * - GITHUB_REPO_CREATE_TOKEN: narrow GitHub PAT for repo creation
 * - GEMINI_API_KEY: Gemini API key (never exposed to browser)
 *
 * Database (D1):
 * - conversations, messages, pending_profiles tables
 *
 * CORS: enabled for frontend (https://9404a979.dark-factory-intake.pages.dev)
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
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "https://factory.mtourk.com",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Content-Type": "application/json",
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") {
      return new Response("OK", { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    try {
      // Route dispatcher
      if (path === "/conversations" && method === "POST") {
        return await handleCreateConversation(env);
      }

      const conversationMatch = path.match(/^\/conversations\/([^/]+)$/);
      if (conversationMatch && method === "GET") {
        return await handleGetConversation(env, conversationMatch[1]);
      }

      const messageMatch = path.match(/^\/conversations\/([^/]+)\/messages$/);
      if (messageMatch && method === "POST") {
        return await handlePostMessage(env, messageMatch[1], request);
      }

      const tokenMatch = path.match(/^\/conversations\/([^/]+)\/gemini-token$/);
      if (tokenMatch && method === "POST") {
        return await handleMintGeminiToken(env, tokenMatch[1]);
      }

      const fileMatch = path.match(/^\/conversations\/([^/]+)\/file-issue$/);
      if (fileMatch && method === "POST") {
        return await handleFileIssue(env, fileMatch[1], request);
      }

      if (path === "/projects" && method === "POST") {
        return await handleCreateProject(env, request);
      }

      if (path === "/pending-profiles" && method === "GET") {
        return await handleListPendingProfiles(env);
      }

      const syncMatch = path.match(/^\/pending-profiles\/([^/]+)\/sync-confirmed$/);
      if (syncMatch && method === "POST") {
        return await handleMarkProfileSynced(env, syncMatch[1]);
      }

      const responseMatch = path.match(/^\/conversations\/([^/]+)\/text-response$/);
      if (responseMatch && method === "POST") {
        return await handleTextResponse(env, responseMatch[1], request);
      }

      return notFound();
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error("Worker error:", errorMsg, error);
      return json({ error: errorMsg }, 500);
    }
  },
};

// ============ Handlers ============

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

  const gemini = new GeminiIntegration(env.GEMINI_API_KEY);
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

    // File the issue
    const issue = await github.fileFeatureIssue(repo, body.title, {
      description: body.description,
      acceptanceCriteria: body.acceptance_criteria,
      nonGoals: body.non_goals,
      constraints: body.constraints,
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

  // Get Gemini response
  const gemini = new GeminiIntegration(env.GEMINI_API_KEY);
  const responseText = await gemini.getDiscoveryResponse(
    allMessages.map((m) => ({ role: m.role, text: m.text }))
  );

  return json({ response: responseText });
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

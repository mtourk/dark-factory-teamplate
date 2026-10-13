/**
 * Dark Factory Intake Worker — Database Layer (D1)
 *
 * Handles all conversation, message, and pending profile queries.
 * Keeps SQL separate from business logic.
 */

export interface Conversation {
  id: string;
  status: "draft" | "filed" | "completed";
  created_at: string;
  updated_at: string;
  issue_number?: number;
  repo_url?: string;
  issue_url?: string;
  title?: string;
  description?: string;
  acceptance_criteria?: string;
  non_goals?: string;
  constraints?: string;
  data_needed?: string;
  error_handling?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "ai";
  text: string;
  timestamp: string;
  token_count?: number;
}

export interface PendingProfile {
  id: string;
  name: string;
  repo_url: string;
  owner: string;
  repo_name: string;
  created_at: string;
  synced: boolean;
  synced_at?: string;
  error?: string;
}

export interface OllamaRequest {
  id: string;
  conversation_id?: string | null;
  model: string;
  status: "pending" | "success" | "error";
  prompt_text: string;
  prompt_length?: number;
  response_text?: string;
  response_length?: number;
  error_message?: string;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
}

export interface AIRequest {
  id: string;
  conversation_id?: string | null;
  request_type: string;
  requested_model: string;
  actual_model?: string | null;
  provider?: string | null;
  status: "pending" | "success" | "error";
  prompt_text: string;
  prompt_length?: number;
  response_text?: string | null;
  response_length?: number | null;
  error_message?: string | null;
  started_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  cost_usd?: string | null;
  gateway_latency_ms?: number | null;
  fallback_attempts?: number;
  cache_hit?: number | null;
  gateway_request_id?: string | null;
  gateway_version?: string | null;
  raw_metadata?: string | null;
}

export class IntakeDB {
  constructor(private db: D1Database) {}

  // === Conversations ===

  async createConversation(): Promise<Conversation> {
    const result = await this.db
      .prepare(
        `
        INSERT INTO conversations (status, title)
        VALUES ('draft', NULL)
        RETURNING *
      `
      )
      .first();
    return result as unknown as Conversation;
  }

  async getConversation(id: string): Promise<Conversation | null> {
    const result = await this.db
      .prepare("SELECT * FROM conversations WHERE id = ?")
      .bind(id)
      .first();
    return (result as unknown as Conversation) || null;
  }

  async updateConversationDraft(
    id: string,
    data: Partial<Conversation>
  ): Promise<Conversation> {
    const updates: string[] = [];
    const values: unknown[] = [];

    for (const [key, value] of Object.entries(data)) {
      if (
        [
          "title",
          "description",
          "acceptance_criteria",
          "non_goals",
          "constraints",
          "data_needed",
          "error_handling",
        ].includes(key)
      ) {
        updates.push(`${key} = ?`);
        values.push(value);
      }
    }

    updates.push("updated_at = ?");
    values.push(new Date().toISOString());
    values.push(id);

    const result = await this.db
      .prepare(
        `
        UPDATE conversations
        SET ${updates.join(", ")}
        WHERE id = ? AND status = 'draft'
        RETURNING *
      `
      )
      .bind(...values)
      .first();

    return result as unknown as Conversation;
  }

  async fileConversation(
    id: string,
    repoUrl: string,
    issueNumber: number,
    issueUrl: string
  ): Promise<Conversation> {
    const result = await this.db
      .prepare(
        `
        UPDATE conversations
        SET status = 'filed', repo_url = ?, issue_number = ?, issue_url = ?, updated_at = ?
        WHERE id = ?
        RETURNING *
      `
      )
      .bind(repoUrl, issueNumber, issueUrl, new Date().toISOString(), id)
      .first();
    return result as unknown as Conversation;
  }

  // === Messages ===

  async addMessage(
    conversationId: string,
    role: "user" | "ai",
    text: string
  ): Promise<Message> {
    const result = await this.db
      .prepare(
        `
        INSERT INTO messages (conversation_id, role, text)
        VALUES (?, ?, ?)
        RETURNING *
      `
      )
      .bind(conversationId, role, text)
      .first();
    return result as unknown as Message;
  }

  async getMessages(conversationId: string): Promise<Message[]> {
    const results = await this.db
      .prepare("SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC")
      .bind(conversationId)
      .all();
    return (results.results || []) as unknown as Message[];
  }

  // === Pending Profiles ===

  async createPendingProfile(
    name: string,
    repoUrl: string,
    owner: string,
    repoName: string
  ): Promise<PendingProfile> {
    const result = await this.db
      .prepare(
        `
        INSERT INTO pending_profiles (name, repo_url, owner, repo_name)
        VALUES (?, ?, ?, ?)
        RETURNING *
      `
      )
      .bind(name, repoUrl, owner, repoName)
      .first();
    return this._parseProfile(result);
  }

  async getPendingProfiles(unsyncedOnly = true): Promise<PendingProfile[]> {
    const query = unsyncedOnly
      ? "SELECT * FROM pending_profiles WHERE synced = 0 ORDER BY created_at ASC"
      : "SELECT * FROM pending_profiles ORDER BY created_at DESC";

    const results = await this.db.prepare(query).all();
    return (results.results || []).map((r) => this._parseProfile(r));
  }

  async markProfileSynced(id: string): Promise<PendingProfile> {
    const result = await this.db
      .prepare(
        `
        UPDATE pending_profiles
        SET synced = 1, synced_at = ?
        WHERE id = ?
        RETURNING *
      `
      )
      .bind(new Date().toISOString(), id)
      .first();
    return this._parseProfile(result);
  }

  async recordProfileSyncError(id: string, error: string): Promise<PendingProfile> {
    const result = await this.db
      .prepare(
        `
        UPDATE pending_profiles
        SET error = ?
        WHERE id = ?
        RETURNING *
      `
      )
      .bind(error, id)
      .first();
    return this._parseProfile(result);
  }

  private _parseProfile(row: any): PendingProfile {
    return {
      ...row,
      synced: Boolean(row.synced),
    };
  }

    // === Provider-neutral AI Request Monitoring ===

  async createAIRequest(input: {
    conversationId: string | null;
    requestType: string;
    requestedModel: string;
    promptText: string;
  }): Promise<AIRequest> {
    const result = await this.db.prepare(`
      INSERT INTO ai_requests
        (conversation_id, request_type, requested_model, status, prompt_text, prompt_length)
      VALUES (?, ?, ?, 'pending', ?, ?)
      RETURNING *
    `).bind(
      input.conversationId,
      input.requestType,
      input.requestedModel,
      input.promptText,
      input.promptText.length
    ).first();
    return result as unknown as AIRequest;
  }

  async completeAIRequest(input: {
    id: string;
    actualModel: string | null;
    provider: string | null;
    responseText: string;
    durationMs: number;
    inputTokens: number | null;
    outputTokens: number | null;
    costUsd: string | null;
    gatewayLatencyMs: number | null;
    fallbackAttempts: number;
    cacheHit: boolean | null;
    gatewayRequestId: string | null;
    gatewayVersion: string | null;
    rawMetadata: string;
  }): Promise<void> {
    await this.db.prepare(`
      UPDATE ai_requests
      SET status = 'success', actual_model = ?, provider = ?, response_text = ?,
          response_length = ?, completed_at = ?, duration_ms = ?, input_tokens = ?,
          output_tokens = ?, cost_usd = ?, gateway_latency_ms = ?, fallback_attempts = ?,
          cache_hit = ?, gateway_request_id = ?, gateway_version = ?, raw_metadata = ?
      WHERE id = ?
    `).bind(
      input.actualModel, input.provider, input.responseText, input.responseText.length,
      new Date().toISOString(), input.durationMs, input.inputTokens, input.outputTokens,
      input.costUsd, input.gatewayLatencyMs, input.fallbackAttempts,
      input.cacheHit === null ? null : Number(input.cacheHit), input.gatewayRequestId,
      input.gatewayVersion, input.rawMetadata, input.id
    ).run();
  }

  async failAIRequest(id: string, errorMessage: string, durationMs: number): Promise<void> {
    await this.db.prepare(`
      UPDATE ai_requests
      SET status = 'error', error_message = ?, completed_at = ?, duration_ms = ?
      WHERE id = ?
    `).bind(errorMessage, new Date().toISOString(), durationMs, id).run();
  }

  async getAIRequestHistory(limit = 50, offset = 0): Promise<AIRequest[]> {
    const result = await this.db.prepare(`
      SELECT id, conversation_id, request_type, requested_model, actual_model, provider,
             status, prompt_text, prompt_length, response_text, response_length, error_message,
             started_at, completed_at, duration_ms, input_tokens, output_tokens, cost_usd,
             gateway_latency_ms, fallback_attempts, cache_hit, gateway_request_id, gateway_version, raw_metadata
      FROM ai_requests ORDER BY started_at DESC LIMIT ? OFFSET ?
    `).bind(limit, offset).all();
    return (result.results || []) as unknown as AIRequest[];
  }

  async getAIRequestHistoryCount(): Promise<number> {
    const result = await this.db.prepare("SELECT COUNT(*) AS count FROM ai_requests").first();
    return ((result as any)?.count as number) ?? 0;
  }

  async getPendingAIRequest(): Promise<AIRequest | null> {
    const result = await this.db.prepare(
      "SELECT * FROM ai_requests WHERE status = 'pending' ORDER BY started_at DESC LIMIT 1"
    ).first();
    return (result as unknown as AIRequest) || null;
  }

  async getLastAIRequest(): Promise<AIRequest | null> {
    const result = await this.db.prepare(
      "SELECT * FROM ai_requests ORDER BY started_at DESC LIMIT 1"
    ).first();
    return (result as unknown as AIRequest) || null;
  }

  // === Ollama Request Monitoring (Phase 18+) ===

  async createOllamaRequest(
    conversationId: string | null,
    model: string,
    promptText: string
  ): Promise<OllamaRequest> {
    const result = await this.db
      .prepare(
        `
        INSERT INTO ollama_requests (conversation_id, model, status, prompt_text, prompt_length)
        VALUES (?, ?, 'pending', ?, ?)
        RETURNING *
      `
      )
      .bind(conversationId, model, promptText, promptText.length)
      .first();
    return result as unknown as OllamaRequest;
  }

  async completeOllamaRequest(
    id: string,
    responseText: string,
    durationMs: number
  ): Promise<OllamaRequest> {
    const result = await this.db
      .prepare(
        `
        UPDATE ollama_requests
        SET status = 'success', response_text = ?, response_length = ?, completed_at = ?, duration_ms = ?
        WHERE id = ?
        RETURNING *
      `
      )
      .bind(responseText, responseText.length, new Date().toISOString(), durationMs, id)
      .first();
    return result as unknown as OllamaRequest;
  }

  async failOllamaRequest(
    id: string,
    errorMessage: string,
    durationMs: number
  ): Promise<OllamaRequest> {
    const result = await this.db
      .prepare(
        `
        UPDATE ollama_requests
        SET status = 'error', error_message = ?, completed_at = ?, duration_ms = ?
        WHERE id = ?
        RETURNING *
      `
      )
      .bind(errorMessage, new Date().toISOString(), durationMs, id)
      .first();
    return result as unknown as OllamaRequest;
  }

  async getOllamaHistory(limit = 50, offset = 0): Promise<OllamaRequest[]> {
    const results = await this.db
      .prepare(
        `
        SELECT * FROM ollama_requests
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
      `
      )
      .bind(limit, offset)
      .all();
    return (results.results || []) as unknown as OllamaRequest[];
  }

  async getOllamaHistoryCount(): Promise<number> {
    const result = await this.db.prepare("SELECT COUNT(*) as count FROM ollama_requests").first();
    return ((result as any)?.count as number) ?? 0;
  }

  async getPendingOllamaRequest(): Promise<OllamaRequest | null> {
    const result = await this.db
      .prepare(
        "SELECT * FROM ollama_requests WHERE status = 'pending' ORDER BY started_at DESC LIMIT 1"
      )
      .first();
    return (result as unknown as OllamaRequest) || null;
  }

  async getLastOllamaRequest(): Promise<OllamaRequest | null> {
    const result = await this.db
      .prepare("SELECT * FROM ollama_requests ORDER BY started_at DESC LIMIT 1")
      .first();
    return (result as unknown as OllamaRequest) || null;
  }
}

export default IntakeDB;

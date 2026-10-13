/**
 * Provider-neutral text client for the shared AI Platform (OmniRoute).
 *
 * This client deliberately has no provider-specific fallback and performs no
 * automatic retries. A failed or disallowed route must fail closed; it must
 * never silently route text requests to Gemini or another provider.
 */

export interface AIPlatformConfig {
  baseUrl?: string;
  apiKey?: string;
  model?: string;
  allowedModels?: string;
  timeoutSeconds?: string;
}

export interface AIPlatformMessage {
  role: string;
  text: string;
}

export interface AIPlatformTextResult {
  content: string;
  requestedModel: string;
  actualModel: string | null;
  provider: string | null;
  inputTokens: number | null;
  outputTokens: number | null;
  promptText: string;
  rawMetadata: Record<string, unknown>;
}

export class AIPlatformError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string
  ) {
    super(message);
    this.name = "AIPlatformError";
  }
}

const DEFAULT_TIMEOUT_SECONDS = 60;
const MIN_TIMEOUT_SECONDS = 5;
const MAX_TIMEOUT_SECONDS = 120;

function resolveConfiguration(config: AIPlatformConfig): {
  endpoint: string;
  apiKey: string;
  model: string;
  timeoutMs: number;
} {
  const baseUrl = config.baseUrl?.trim();
  const apiKey = config.apiKey?.trim();
  const model = config.model?.trim();
  const allowedModels = (config.allowedModels || "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);

  if (!baseUrl || !apiKey || !model || allowedModels.length === 0) {
    throw new AIPlatformError(
      503,
      "AI Platform is not configured. Contact the application administrator."
    );
  }

  if (!allowedModels.includes(model)) {
    throw new AIPlatformError(
      503,
      "The configured AI Platform model is not in the approved model allow-list."
    );
  }

  let parsedBaseUrl: URL;
  try {
    parsedBaseUrl = new URL(baseUrl);
  } catch {
    throw new AIPlatformError(503, "AI Platform configuration is invalid.");
  }

  if (
    parsedBaseUrl.protocol !== "https:" ||
    parsedBaseUrl.username ||
    parsedBaseUrl.password ||
    parsedBaseUrl.search ||
    parsedBaseUrl.hash
  ) {
    throw new AIPlatformError(503, "AI Platform must use a valid HTTPS base URL.");
  }

  const configuredTimeout = config.timeoutSeconds?.trim();
  const timeoutSeconds = configuredTimeout
    ? Number(configuredTimeout)
    : DEFAULT_TIMEOUT_SECONDS;

  if (
    !Number.isInteger(timeoutSeconds) ||
    timeoutSeconds < MIN_TIMEOUT_SECONDS ||
    timeoutSeconds > MAX_TIMEOUT_SECONDS
  ) {
    throw new AIPlatformError(
      503,
      `AI Platform timeout must be an integer between ${MIN_TIMEOUT_SECONDS} and ${MAX_TIMEOUT_SECONDS} seconds.`
    );
  }

  return {
    endpoint: `${baseUrl.replace(/\/+$/, "")}/v1/chat/completions`,
    apiKey,
    model,
    timeoutMs: timeoutSeconds * 1000,
  };
}

/**
 * Send the feature-discovery conversation to the shared AI Platform.
 * Upstream error bodies are never returned to the browser or written to logs.
 */
export async function getAIPlatformTextResponse(
  config: AIPlatformConfig,
  messages: AIPlatformMessage[],
  systemPrompt: string,
  fetcher: typeof fetch = globalThis.fetch
): Promise<AIPlatformTextResult> {
  const resolved = resolveConfiguration(config);
  const controller = new AbortController();
  const startedAt = Date.now();
  const timeout = setTimeout(() => controller.abort(), resolved.timeoutMs);

  const chatMessages = [
    { role: "system", content: systemPrompt },
    ...messages.map((message) => ({
      role: message.role === "user" ? "user" : "assistant",
      content: message.text,
    })),
  ];
  const promptText = JSON.stringify(chatMessages);

  try {
    const response = await fetcher(resolved.endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${resolved.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: resolved.model,
        messages: chatMessages,
        temperature: 0.7,
        stream: false,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      // Keep the public response sanitized; never echo upstream error bodies.
      console.warn("AI Platform request failed", {
        status: response.status,
        duration_ms: Date.now() - startedAt,
      });
      const statusCode = response.status === 429 ? 503 : 502;
      throw new AIPlatformError(
        statusCode,
        response.status === 429
          ? "AI Platform is rate-limited or its quota is exhausted. No fallback was attempted."
          : `AI Platform request failed (upstream status ${response.status}). No fallback was attempted.`
      );
    }

    let payload: any;
    try {
      payload = await response.json();
    } catch {
      throw new AIPlatformError(502, "AI Platform returned an invalid response.");
    }

    const content = payload?.choices?.[0]?.message?.content;
    if (typeof content !== "string" || content.length === 0) {
      throw new AIPlatformError(502, "AI Platform response did not contain assistant text.");
    }

    const usage = payload?.usage && typeof payload.usage === "object" ? payload.usage : {};
    const actualModel = typeof payload?.model === "string" ? payload.model : null;
    const provider = typeof payload?.provider === "string"
      ? payload.provider
      : typeof payload?.metadata?.provider === "string"
        ? payload.metadata.provider
        : null;

    return {
      content,
      requestedModel: resolved.model,
      actualModel,
      provider,
      inputTokens: Number.isFinite(usage.prompt_tokens) ? Number(usage.prompt_tokens) : null,
      outputTokens: Number.isFinite(usage.completion_tokens) ? Number(usage.completion_tokens) : null,
      promptText,
      rawMetadata: {
        id: typeof payload?.id === "string" ? payload.id : null,
        model: actualModel,
        provider,
        usage: Object.keys(usage).length ? usage : null,
      },
    };
  } catch (error) {
    if (error instanceof AIPlatformError) {
      throw error;
    }
    if (controller.signal.aborted) {
      throw new AIPlatformError(504, "AI Platform request timed out.");
    }
    console.warn("AI Platform request could not be completed", {
      duration_ms: Date.now() - startedAt,
    });
    throw new AIPlatformError(502, "AI Platform is unreachable. No fallback was attempted.");
  } finally {
    clearTimeout(timeout);
  }
}

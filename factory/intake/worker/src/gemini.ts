/**
 * Dark Factory Intake Worker — Gemini Live Integration + Local LLM Support
 *
 * Handles:
 * 1. Text discovery responses: prefers local Ollama (no API cost), falls back to Gemini
 * 2. Voice ephemeral token minting: uses Gemini Live (no local alternative for real-time audio)
 *
 * Per ADR-005, long-lived API keys live only as Cloudflare Worker secrets;
 * tokens are short-lived (1 hour) and minted on-demand.
 * The frontend never sees the API key.
 */

export interface GeminiTokenResponse {
  token: string;
  expires_at: string;
  model: string;
}

export class GeminiIntegration {
  private apiKey: string;
  private readonly OLLAMA_URL = "https://ollama.mtourk.com"; // Ollama exposed via Cloudflare tunnel
  private readonly OLLAMA_MODEL = "neural-chat"; // Lightweight model for discovery; adjust as needed

  // Gemini as fallback for text, primary for voice
  private readonly DEFAULT_MODEL = "gemini-3.5-flash";
  private readonly FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3-flash",
    "gemini-2.5-flash",
  ];

  constructor(apiKey: string) {
    if (!apiKey) {
      throw new Error("GEMINI_API_KEY secret not configured");
    }
    this.apiKey = apiKey;
  }

  /**
   * Mint an ephemeral Gemini Live session token.
   *
   * Gemini Live requires:
   * 1. A valid API key (held by the Worker, never exposed)
   * 2. A request to the session creation endpoint
   * 3. Return token + expiry to the frontend
   *
   * The frontend uses this token to establish a WebSocket with Gemini's infrastructure.
   * Token is valid for 1 hour.
   */
  async createEphemeralToken(): Promise<GeminiTokenResponse> {
    const endpoint = "https://generativelanguage.googleapis.com/v1alpha/sessions/create";

    const requestBody = {
      display_name: "Dark Factory Feature Discovery",
    };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-goog-api-key": this.apiKey,
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Gemini API error: ${response.status} ${error}`);
      }

      const data = (await response.json()) as any;

      if (!data.session?.name) {
        throw new Error("No session token returned from Gemini API");
      }

      // Extract token from full session name (format: "projects/.../sessions/...")
      const token = data.session.name.split("/").pop();

      // Calculate expiry (Gemini Live tokens are 1 hour)
      const expiresAt = new Date(Date.now() + 60 * 60 * 1000);

      return {
        token,
        expires_at: expiresAt.toISOString(),
        model: this.DEFAULT_MODEL,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to mint Gemini token: ${errorMsg}`);
    }
  }

  /**
   * Get a text response from Gemini for a feature discovery conversation.
   *
   * Strategy: Try local Ollama first (instant, free, no rate limits).
   * Fall back to Gemini if Ollama is unavailable.
   *
   * Takes the full conversation history and asks for the next response.
   * This keeps the conversation contextual and natural.
   */
  async getDiscoveryResponse(messages: Array<{ role: string; text: string }>): Promise<string> {
    // Try local Ollama first (preferred: no API costs, no rate limits, full control)
    try {
      return await this.getDiscoveryResponseFromOllama(messages);
    } catch (ollamaError) {
      console.warn(`Ollama failed: ${ollamaError instanceof Error ? ollamaError.message : String(ollamaError)}. Falling back to Gemini...`);
      // Fall back to Gemini if Ollama unavailable
      return await this.getDiscoveryResponseFromGemini(messages);
    }
  }

  /**
   * Call local Ollama server for discovery responses.
   * Ollama must be accessible via tunnel (e.g., cloudflare-workers-localhost).
   */
  private async getDiscoveryResponseFromOllama(messages: Array<{ role: string; text: string }>): Promise<string> {
    // Format as Ollama expects (simple message list)
    const ollamaMessages = messages.map((msg) => ({
      role: msg.role === "user" ? "user" : "assistant",
      content: msg.text,
    }));

    try {
      const response = await fetch(`${this.OLLAMA_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.OLLAMA_MODEL,
          messages: ollamaMessages,
          system: GeminiIntegration.getDiscoverySystemPrompt(),
          stream: false,
        }),
      });

      if (!response.ok) {
        throw new Error(`Ollama returned ${response.status}`);
      }

      const data = (await response.json()) as any;
      if (!data.message?.content) {
        throw new Error("No response content from Ollama");
      }

      return data.message.content;
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      throw new Error(`Local Ollama unavailable (${this.OLLAMA_URL}): ${errorMsg}`);
    }
  }

  /**
   * Call Gemini API for discovery responses (fallback if Ollama unavailable).
   * Implements retry logic with fallback models for rate limiting and service errors.
   */
  private async getDiscoveryResponseFromGemini(messages: Array<{ role: string; text: string }>): Promise<string> {
    // Format messages for Gemini API (convert "user"/"ai" to "user"/"model")
    const formattedMessages = messages.map((msg) => ({
      role: msg.role === "user" ? "user" : "model",
      parts: [{ text: msg.text }],
    }));

    const modelsToTry = [this.DEFAULT_MODEL, ...this.FALLBACK_MODELS];
    let lastError: Error | null = null;

    for (const model of modelsToTry) {
      try {
        const endpoint = `https://generativelanguage.googleapis.com/v1/models/${model}:generateContent`;

        const response = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-goog-api-key": this.apiKey,
          },
          body: JSON.stringify({
            system_instruction: {
              parts: [
                {
                  text: GeminiIntegration.getDiscoverySystemPrompt(),
                },
              ],
            },
            contents: formattedMessages,
            generation_config: {
              temperature: 0.7,
              // Removed max_output_tokens limit to allow full responses without truncation
            },
          }),
        });

        // Retry on rate limit or service unavailable
        if (response.status === 429 || response.status === 503) {
          const error = await response.text();
          console.warn(`Model ${model} returned ${response.status}, trying next fallback...`);
          lastError = new Error(`${response.status}: ${error}`);
          continue; // Try next model
        }

        if (!response.ok) {
          const error = await response.text();
          throw new Error(`Gemini API error: ${response.status} ${error}`);
        }

        const data = (await response.json()) as any;

        if (!data.candidates?.[0]?.content?.parts?.[0]?.text) {
          throw new Error("No response text from Gemini API");
        }

        return data.candidates[0].content.parts[0].text;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        // Continue to next model
        if (model !== modelsToTry[modelsToTry.length - 1]) {
          console.warn(`Model ${model} failed, trying next fallback...`);
        }
      }
    }

    // All models failed
    const errorMsg = lastError?.message || "All Gemini models failed";
    throw new Error(`Failed to get Gemini response: ${errorMsg}`);
  }

  /**
   * Build the system prompt for Gemini discovery.
   *
   * This prompt structures the conversation around Dark Factory's BMAD taxonomy:
   * - Actors: who uses this, and what permissions are involved
   * - Action: what exactly should happen
   * - Context: why do you need this
   * - Acceptance criteria: how will you know it works
   * - Non-goals: what should NOT be included
   * - Constraints: performance, compatibility, etc.
   * - Data behavior: what data is read/written, retention, encryption
   * - Error handling: what happens if things fail
   * - Preconditions/postconditions: what must be true before/after
   */
  static getDiscoverySystemPrompt(): string {
    return `You are a feature discovery specialist for the Dark Factory, an autonomous software engineering system.

Your role: conduct a natural, conversational interview to clarify a feature request into a well-structured GitHub issue.

You will ask about:

1. **ACTORS**: "Who will use this? Just you, or other people/systems?"
2. **ACTION**: "What exactly should happen? Describe it as a concrete behavior."
3. **CONTEXT**: "Why do you need this? What pain point does it solve?"
4. **ACCEPTANCE CRITERIA**: "How will you know it's working? What must be true?"
5. **NON-GOALS**: "What should this NOT do? Any scope limits?"
6. **CONSTRAINTS**: "Any performance, compatibility, or compliance requirements?"
7. **DATA BEHAVIOR**: "What data is read or written? Any retention or privacy rules?"
8. **ERROR HANDLING**: "What should happen if things fail?"
9. **PRECONDITIONS**: "What must already be true for this to start?"
10. **POSTCONDITIONS**: "What must be true after this is complete?"

Guide the conversation naturally—don't ask all 10 at once. Start with ACTION and CONTEXT, then probe deeper based on their answers.

After 8–10 exchanges (or when the user says "that's it"), summarize what you heard and ask: "Does that capture it?"

Once confirmed, you STOP asking questions. The user's next message will trigger the GitHub issue filing.

Format matters: structure the issue body with these exact headers so the Dark Factory's downstream BMAD analyzer recognizes them:
- "Acceptance Criteria:" (bulleted list)
- "Non-Goals:" (bulleted list)
- "Constraints:" (bulleted list)
- etc.

Be conversational, empathetic, and concise. This is a discovery tool, not a form.`;
  }
}

export default GeminiIntegration;

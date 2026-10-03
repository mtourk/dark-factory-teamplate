/**
 * Dark Factory Intake Worker — Gemini Live Integration
 *
 * Handles minting ephemeral Gemini Live tokens.
 * Per ADR-005, the long-lived API key lives only as a Cloudflare Worker secret;
 * tokens are short-lived (1 hour) and minted on-demand for each session.
 * The frontend never sees the API key.
 */

export interface GeminiTokenResponse {
  token: string;
  expires_at: string;
  model: string;
}

export class GeminiIntegration {
  private apiKey: string;

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
        model: "gemini-2.0-flash-exp", // or latest available
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      throw new Error(`Failed to mint Gemini token: ${errorMsg}`);
    }
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

# Intake Discovery → Implementation Handoff (ADR-XXX)

**Date:** 2026-10-04  
**Status:** Accepted  
**Scope:** Phase 17–18 intake worker → local factory runner integration

## Problem

The intake worker (Phase 17) discovers features via conversational discovery with the 7B model (fast, low cost, good for clarification). Once discovered, the issue is filed on GitHub with structured BMAD fields (Acceptance Criteria, Non-Goals, Constraints, etc.).

However, the **local factory runner** (Phase 18+, implementation) that later picks up the `factory:ready` issue to generate code only had access to the summarized BMAD fields. The full context and reasoning from the discovery conversation was lost, forcing the 32B model to re-derive why each decision was made from scratch.

Additionally, there was no signal for the local runner to know **which model** to use (7B vs 32B) when processing the issue.

## Solution

### 1. Full Conversation Context in Issue Body

When filing a feature issue, the intake worker now appends the complete raw discovery conversation as a **"Raw Discovery Conversation"** section at the end of the issue body:

```markdown
## Raw Discovery Conversation

**User:** I need a dashboard to monitor my deployments.

**AI:** I understand you want a dashboard. What information is most important to see at a glance?

**User:** Status of each service, deployment timestamps, and failure logs if anything went wrong.

**AI:** Great. How many services are we talking about, and what's the expected frequency of deployments?

...

```

This preserves the full reasoning context for the 32B model to refer to later.

### 2. Model Selection Labels

Each filed issue now includes **three labels**:

| Label | Purpose |
|-------|---------|
| `factory:ready` | Issue is eligible for implementation (discovery phase complete) |
| `model:discovery-7b` | This issue was discovered via 7B model (traceability) |
| `model:implementation-32b` | Use 32B model for code generation (signals to local runner) |

The `model:implementation-32b` label tells the local factory runner to extract the 32B model name from the environment or default config (e.g., `qwen2.5-coder:32b`) and use it when calling Ollama for code generation.

### 3. No Timeout Risk for Large Models

The local factory runner calls Ollama directly via `http://localhost:11434/api/chat` (or custom tunnel). This is **not** routed through Cloudflare's edge — it's a direct API call to the local Ollama instance. Therefore:

- No 524 timeout (Cloudflare worker deadline)
- No request size limits (Cloudflare Worker payload limits)
- Can safely use 30B–70B models without timing out

Per ADR-§10 and master plan: builder may not delete/weaken tests, but it **can** use larger, more capable models since there's no infrastructure latency penalty.

## Implementation

### Intake Worker Changes (factory/intake/worker)

**File: `src/github.ts`**

1. Added `Message` interface export:
   ```typescript
   export interface Message {
     id: string;
     conversation_id: string;
     role: "user" | "ai";
     text: string;
     timestamp: string;
     token_count?: number;
   }
   ```

2. Updated `fileFeatureIssue()` signature to accept `rawConversation`:
   ```typescript
   async fileFeatureIssue(
     repo: string,
     title: string,
     bmadStructured: {
       // ... existing fields
       rawConversation?: Message[];
     }
   ): Promise<GithubIssue>
   ```

3. Updated issue labels:
   ```typescript
   labels: ["factory:ready", "model:discovery-7b", "model:implementation-32b"],
   ```

4. Updated `_formatBMADIssueBody()` to include conversation:
   ```typescript
   if (bmad.rawConversation && bmad.rawConversation.length > 0) {
     lines.push("## Raw Discovery Conversation");
     lines.push("");
     for (const msg of bmad.rawConversation) {
       const role = msg.role === "user" ? "**User:**" : "**AI:**";
       lines.push(`${role} ${msg.text}`);
       lines.push("");
     }
   }
   ```

**File: `src/index.ts`**

1. Updated `handleFileIssue()` to fetch full conversation history:
   ```typescript
   // Get full conversation history to include in the issue
   const allMessages = await db.getMessages(conversationId);

   // File the issue
   const issue = await github.fileFeatureIssue(repo, body.title, {
     description: body.description,
     acceptanceCriteria: body.acceptance_criteria,
     nonGoals: body.non_goals,
     constraints: body.constraints,
     rawConversation: allMessages,  // ← NEW
   });
   ```

### Local Factory Runner Changes (future: factory/implementation/)

When the local runner processes an issue labeled `model:implementation-32b`:

1. Extract `model:implementation-32b` label
2. Parse label to get model name: `qwen2.5-coder:32b` (default env or config)
3. Pass `model_name` to Ollama API calls
4. The 32B model has access to both:
   - Structured BMAD fields (in markdown headers)
   - Raw discovery conversation (in "Raw Discovery Conversation" section)

Example Ollama call (pseudocode):
```python
response = ollama.chat(
    model="qwen2.5-coder:32b",
    messages=[
        {"role": "system", "content": "You are a code generator..."},
        {"role": "user", "content": "Issue body (with full conversation + BMAD)..."}
    ],
)
```

## Benefits

| Benefit | Reason |
|---------|--------|
| **Full context** | 32B model sees discovery reasoning, not just structured summary |
| **Model routing** | Labels make it clear which model to use for each phase |
| **Traceability** | `model:discovery-7b` + `model:implementation-32b` log model choice |
| **No timeout risk** | Local Ollama calls don't hit Cloudflare Worker 30s/524 deadlines |
| **Better code gen** | 32B model can reference discovery context to justify design choices |

## Alternatives Considered

1. **Store conversation in separate database table:** Could query at implementation time, but labels + issue body is self-contained and doesn't require cross-service lookups.
2. **Use `model:*` labels only, store model map in config:** Requires external config; embedding in labels keeps everything in Git.
3. **Strip conversation if too long:** GitHub issue body has a ~65KB limit. Most conversations are 2–5KB; if needed, truncate oldest messages.

## Testing

- [ ] File a feature via intake worker; verify issue includes "Raw Discovery Conversation" section
- [ ] Verify `model:implementation-32b` label is present
- [ ] Local factory runner reads label and routes to correct model
- [ ] 32B model can reference conversation context in generated code

## References

- **ADR-005:** API keys in Cloudflare Worker secrets, tokens minted on-demand
- **ADR-§10:** Builder constraints (can't delete tests, but no latency penalty for larger models)
- **Master Plan §10:** Builder envelope spec
- **Phase 17:** Intake Worker (discovery + issue filing)
- **Phase 18+:** Local factory runner (implementation + code generation)

# Phase 17.0 — Architecture Q&A

Answers to: factory invocation after filing, BMAD + Gemini, text transcripts, and persistence/database.

---

## 1. After the Issue is Filed, How Does the Factory Start Implementing?

**Short answer: filing the issue doesn't "start" anything by itself — it just makes the issue *eligible*. Something still has to notice it and claim it. That "something" is Phase 4 (Backlog Scheduler), and it hasn't been built yet.**

I checked the actual code: `factory/backlog/scheduler.py` already has the eligibility logic (`is_eligible()` — checks `factory:ready` label, not claimed/blocked/quarantined, emergency stop inactive) and deterministic priority ordering. But the thing that *calls* this scheduler on a loop — the actual trigger — is still a stub in `factory/cli.py` ("not yet implemented (Phase 4 backlog scheduler)"). We're currently at Phase 1 of the master plan; Phase 4 hasn't been built.

So this is a real open question, not something already decided. Three ways to invoke it, once Phase 4 is built:

| Option | How it works | Resource use | Responsiveness |
|---|---|---|---|
| **A. Local polling loop (recommended)** | Windows Task Scheduler runs `factory run --claim` every 2–5 min. Checks GitHub for `factory:ready` issues, claims one if eligible, kicks off the full run, exits when idle. | Low — brief wake-ups, not an always-on process | 2–5 min delay |
| **B. Always-on local daemon** | A long-running Python process on your machine, polling continuously. | Medium — one process running 24/7 (lighter than Ollama itself, but still "always on") | Near-instant |
| **C. Event-driven via webhook + tunnel** | GitHub Action fires on `issues.labeled` → calls a Cloudflare Worker → Worker pushes through the same tunnel we just proved works → wakes a local listener → `factory run` starts immediately. | Low (idle until woken) but **most complex** — reuses the tunnel pattern, needs a tiny local listener process | Near-instant |

**Why it has to be local at all:** the actual work (git worktrees at `C:\Factory\worktrees\...`, Ollama inference, file edits) runs on your machine per ADR-001 — that can't move to Cloudflare. Only the *trigger* can be made more or less immediate.

**My recommendation:** Option A for now. It's the simplest, matches "low complexity," and a 2–5 min delay before the factory picks up a new issue is a non-issue in practice (building/testing/reviewing a feature takes much longer than that). Option C is a nice idea for later — notably, it reuses the exact tunnel pattern we just validated — but it's extra moving parts for a benefit (instant vs. 5-min delay) that doesn't matter much here.

---

## 2. Can Gemini Be "Backed Up" With the BMAD Method? Can BMAD Drive the Chat?

**Yes — and this project already has the right hook for it.**

I found `factory/analysis/bmad.py` — the factory already has a `BMADRequirement` structure with specific fields: `actors`, `action`, `context`, `acceptance_criteria`, `non_goals`, `constraints`, `data_needed`, `errors`, `preconditions`, `postconditions`. Right now this runs **after** filing, server-side, using the local model, to turn a raw issue into a structured spec.

**The idea:** give Gemini Live's system prompt that *same* BMAD taxonomy, so instead of a freeform chat, the discovery conversation is explicitly structured around those fields:

```
Gemini's internal checklist during discovery:
☐ actors        → "Who uses this? Just you, or other people too?"
☐ action        → "What exactly should happen?"
☐ context       → "Why do you need this? What's the pain point?"
☐ acceptance    → "How will you know it's working?"
☐ non_goals     → "What should this NOT do?"
☐ constraints   → "Any performance/compatibility requirements?"
☐ data_needed   → "What data does this read or write?"
☐ errors        → "What should happen if it fails?"
```

Then, when filing the GitHub Issue, format the body with headers that **exactly match** what `BMADDiscovery.discover_from_issue()` already parses: `Acceptance Criteria:`, `Non-Goals:` / `Out of Scope:`, etc. That means the chat-side structuring and the backend's own parsing speak the same vocabulary — nothing is wasted or duplicated.

**Important boundary (and this is already written into ADR-005 and Phase 17's checklist):** Gemini's BMAD-flavored interview produces a well-structured **draft**. It does not replace the factory's own BMAD discovery + isolated critics (Phase 7), which still re-runs independently, server-side, on the local model, after filing. That's intentional — it's the same "discovery-only, not authoritative" boundary that keeps the cloud model out of anything that actually matters for correctness. The practical benefit: because Gemini already resolved ambiguities in conversation, the backend critics should have far fewer `open_questions` / `strategic_ambiguities` to escalate.

**Voice vs. text — same thing.** Whether the user is speaking or typing, Gemini is running the same BMAD-structured interview; voice is just the input modality.

---

## 3. Can the User *Read* What Gemini Says, Not Just Hear It?

**Yes, by default — no extra engineering needed.**

The Gemini Live API natively streams a **text transcript alongside the audio**, both directions:
- Transcript of what *you* said (speech-to-text, generated as you talk)
- Transcript of what *Gemini* said (matches the spoken audio response)

This is exactly what populates the chat bubbles in the page design I showed you — every voice exchange already becomes a text message in the conversation log. You never lose anything by using voice; it's always also text.

---

## 4. Where Is the Conversation Stored? Do We Need a Database?

**Yes, we need somewhere durable — browser memory alone won't survive you closing the tab or coming back on another day.**

What needs to persist:
- Every message (who said it, what they said, timestamp)
- The evolving draft issue (title, description, acceptance criteria, etc.)
- Status: draft / filed / issue number & link once filed

**Recommendation: Cloudflare D1** (serverless SQLite, lives entirely inside Cloudflare — zero local footprint).

Why D1 over the alternatives:

| Option | Fit |
|---|---|
| **Cloudflare D1 (recommended)** | Free tier: 5GB storage, 5M reads/day, 100k writes/day — massive headroom for a single-user intake tool. Simple relational tables (conversations, messages). The Worker reads/writes directly. Nothing runs on your machine. |
| Cloudflare KV | Simpler (just key→value), but worse for listing/querying past drafts for a dashboard — would need to serialize/deserialize whole conversation blobs every time. |
| Durable Objects | Great for holding the *live* WebSocket session open during an active voice call, but adds a layer of complexity we don't need yet. Can be introduced later if real-time session handling becomes a bottleneck — D1 alone is fine to start. |
| Local SQLite (reuse factory's `factory/state.py` DB) | Wrong fit — that database is the factory's own run/claim state, lives on your machine, and ties the web page's database access to your laptop being on. Defeats the "low local footprint" goal. |

**How "resume later" works with D1:**
1. When a conversation starts, the Worker creates a row in a `conversations` table (id, status=`draft`, created_at) and stores a `session_id` in the browser (localStorage — not sensitive, just a pointer).
2. Every message is appended to a `messages` table (conversation_id, role, text, timestamp).
3. When the user returns, the page checks localStorage for a `session_id` → asks the Worker to fetch that conversation from D1 → renders the full history → lets them continue where they left off.
4. A simple "Your drafts" list (query D1 for all `status=draft` conversations) covers the case where localStorage is cleared or they're on a different device — not identity-secure, but fine for a single-user internal tool. If this ever needs to be multi-user or public-facing, we'd add real auth at that point (not needed for Phase 17.0).

---

## Summary of Decisions to Confirm

1. **Invocation:** Option A (polling loop via Task Scheduler, 2–5 min) — recommended, unless you want near-instant (Option C, reusing the tunnel).
2. **BMAD in chat:** Yes — Gemini's discovery prompt is built from the existing `BMADRequirement` fields; issue body headers match what the backend already parses. Backend BMAD + critics still re-run independently after filing (ADR-005 boundary unchanged).
3. **Transcripts:** Already free with Gemini Live — no extra design needed.
4. **Database:** Cloudflare D1, two tables (`conversations`, `messages`), accessed only by the Worker. Browser holds a non-sensitive `session_id` pointer in localStorage for resuming.

Let me know if any of these should change, otherwise this is enough to start sketching the actual file/data structure for the build.

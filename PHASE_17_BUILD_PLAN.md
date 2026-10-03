# Phase 17.0 — Build Plan

Answers to the 3 open questions, plus the new "create a brand-new project" flow you raised.

---

## 1. File Structure (Decided)

Three different runtimes are involved — Python (existing factory), a static frontend, and a Cloudflare Worker (JS/TS). They need separate homes, grouped under one folder so Phase 17 stays self-contained:

```
factory/intake/
  channels.py          # Python: RawIntakeMessage, ChannelAdapter interface (shared across web/Telegram/email later)
  web/                 # Cloudflare Pages — static frontend (HTML/CSS/JS), deployed as-is
    index.html
    app.js
    style.css
  worker/              # Cloudflare Worker — backend (TypeScript), separate deployable unit
    src/
      index.ts         # Request router
      gemini.ts         # Mint ephemeral Gemini Live tokens
      github.ts         # Create repo / file issue / add labels
      db.ts              # D1 queries (conversations, messages, pending_profiles)
    wrangler.toml       # Worker config (D1 binding, secrets declared, not stored here)
    package.json
```

**Why this shape:** `factory/intake/` stays the single home for "how a requirement enters the factory," matching the checklist's existing plan. `web/` and `worker/` are separate because they deploy independently (Pages vs. Workers are different Cloudflare products with their own `wrangler` commands), but living under the same parent keeps them easy to find together.

---

## 2. The "Brand-New Project" Flow (New Ground — Here's the Design)

You described: user has a project *idea* (not an existing repo) → system creates a new GitHub repo → factory implements requirements into it.

I checked the existing code: `factory/profiles.py` and `factory/deploy/target_repo_setup.py` **both assume the repo already exists** — `create_profile()` just parses a GitHub URL you already have. Creating the repo itself is genuinely new functionality. Here's how it fits:

### The Flow
```
1. User (web page): "I have a new project idea: a recipe-sharing app"
2. Gemini Live discovery conversation (BMAD-structured, as already designed)
3. User confirms project name (e.g. "recipe-sharer") — suggested from the idea, editable
4. Worker creates the GitHub repo (private, seeded with starter template — per your answers above)
5. Worker files the first issue (factory:ready) on that new repo
6. Worker records a "pending profile" row in D1: {name: "recipe-sharer", repo_url: "...", synced: false}
7. [Separate, local] Next time the local polling loop (Option A from the invocation doc) wakes up,
   it also checks the Worker for pending profiles, creates the local profile file automatically,
   marks it synced
8. From here on, the factory operates on this new repo exactly like any other profile
```

### Where the GitHub Token for Repo Creation Lives

**This is a new secret-custody decision — answering your "can it be stored in the user profile?" question directly: no, it can't live in the profile.**

Profiles (`profiles/<name>.yml`) are deliberately secret-free local files (per ADR-003/004) — they just *name* a repo, they never hold credentials. And the repo-creation step happens in the **Worker** (cloud-side), which has no access to your local filesystem at all. So the token has to live where the Worker can reach it:

- **New secret: `GITHUB_REPO_CREATE_TOKEN`** — stored as a Cloudflare Worker secret (same custody pattern as the Gemini key: never reaches the browser, never written to a local file).
- **Scope:** as narrow as GitHub allows — a fine-grained PAT limited to "Administration: write" (create repos) + "Issues: write" + "Metadata: read" on your account. This is deliberately a *different, more narrowly scoped* credential than your personal `gh auth login` session, which the local factory continues to use for its own day-to-day git/PR operations (unchanged).
- **This is worth a short ADR addendum** once we build it — it's the same spirit as ADR-005 (narrow, single-purpose, cloud-held secret) but for GitHub instead of Gemini. I'll draft that alongside the implementation.

### What *Does* Get Stored in the Profile

Once the repo exists, the profile file stores exactly what profiles already store — non-secret identity:
```yaml
name: recipe-sharer
target_repo:
  owner: mtourk
  name: recipe-sharer
  url: https://github.com/mtourk/recipe-sharer
```
Nothing new here — this is just `create_profile()` being called automatically instead of by hand.

### New Repo Content (Per Your Answer)

Seeded starter template, not empty. Concretely, on creation the Worker:
1. Creates the repo from a **template repository** (GitHub supports "generate from template" natively via API) — I'd suggest a small `dark-factory-starter` template repo containing: minimal `package.json`, `README.md`, basic folder layout, and `.github/workflows/deploy.yml` already in place (the exact file that `target_repo_setup.py` currently has to sync in after the fact — seeding it at creation skips that step entirely for new projects).
2. Falls back to "create empty + push starter files via API" if template-repo generation isn't available on your account tier (GitHub's template feature works the same on free/private repos, so this is a backup path, not the expected one).

---

## 3. Updated Database Shape (D1)

One more table beyond the two from the architecture doc:

```sql
conversations (id, status, created_at, issue_number, repo_url)
messages (id, conversation_id, role, text, timestamp)
pending_profiles (id, name, repo_url, created_at, synced BOOLEAN DEFAULT FALSE)
```

The local polling loop's job grows slightly: each wake-up, it now does two things —
1. Check `pending_profiles` where `synced = false` → create local profile, mark synced
2. Check GitHub for `factory:ready` issues → claim next eligible one (as already planned)

Both are quick HTTPS calls; no new infrastructure needed beyond what's already planned.

---

## 4. Build Order (Logical Sequence)

1. **D1 schema** — the 3 tables above (`conversations`, `messages`, `pending_profiles`)
2. **Worker skeleton** — routes for: start conversation, post message, mint Gemini token, create repo + file issue, list pending profiles (for the local sync step)
3. **Web frontend** — the page design already agreed (voice button, chat, collapsible issue preview)
4. **Local sync addition** — small addition to the (not-yet-built) Phase 4 polling loop to pull pending profiles
5. **New ADR** — document the `GITHUB_REPO_CREATE_TOKEN` custody decision
6. **Starter template repo** — the `dark-factory-starter` scaffold referenced above

This is a reasonable order because each step is independently testable before the next depends on it (D1 before Worker, Worker before frontend, etc.).

---

## Open Question Before I Start Building

**Do you already have (or want to create) the GitHub account/org structure for these new project repos** — i.e., should new repos always land under your personal GitHub account (same one `investisor` and this factory repo live under), or could some land under a different org later? I'll assume **same account, always**, unless you tell me otherwise — this keeps the token scope simplest.

If that assumption is fine, I'll start with step 1 (D1 schema) and work down the list.

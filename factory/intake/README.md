# Phase 17.0 — Multi-Channel Intake

**Status:** In development  
**Scope:** Web page (HTML/CSS/JS) + Cloudflare Worker backend + D1 database  
**Goal:** Feature intake via web voice/chat discovery → auto-file GitHub Issue → ready for factory to implement

---

## Architecture Overview

```
User's browser                          Cloudflare                            Your machine
┌─────────────────┐                     ┌─────────────────┐
│  Pages frontend │────WebSocket───────→│  Worker backend │
│  (intake.mtourk │  (Gemini Live)     │  (Node/TS)      │
│   .com)         │                     │                 │
│                 │                     │  • Gemini token │───→ (stores key securely)
│  • Voice btn    │                     │  • GitHub API   │
│  • Chat bubbles │                     │  • D1 queries   │
│  • Issue draft  │←──────Stream────────│                 │
│                 │                     └─────────────────┘
└─────────────────┘                              ↓
                                         ┌─────────────────┐
                                         │  D1 Database    │
                                         │  (SQLite)       │
                                         │                 │
                                         │ • conversations │
                                         │ • messages      │
                                         │ • pending_...   │
                                         │   profiles      │
                                         └─────────────────┘
                                                  ↓
                                         ┌─────────────────┐
                                         │  GitHub API     │
                                         │  • Create repos │
                                         │  • File issues  │
                                         │  • Add labels   │
                                         └─────────────────┘
                                                  ↓
                                         ┌─────────────────┐
                                         │ New GitHub repo │
                                         │ + factory:ready │
                                         │ issue           │
                                         └─────────────────┘
                                                  ↓
                                         ┌─────────────────┐
                                         │  Local polling  │
                                         │  loop (Phase 4) │
                                         │  picks it up &  │
                                         │  claims issue   │
                                         └─────────────────┘
```

---

## Directory Structure

```
factory/intake/
├── channels.py                 # RawIntakeMessage + ChannelAdapter interface
├── local_sync.py               # Local profile sync (runs in polling loop)
├── worker/                     # Cloudflare Worker backend
│   ├── wrangler.toml           # Worker config + D1 binding
│   ├── package.json
│   ├── tsconfig.json
│   ├── schema.sql              # D1 schema (3 tables)
│   └── src/
│       ├── index.ts            # Main Worker, request router
│       ├── db.ts               # D1 queries (IntakeDB class)
│       ├── gemini.ts           # Gemini Live token minting
│       └── github.ts           # GitHub repo creation & issue filing
└── web/                        # Cloudflare Pages frontend
    ├── index.html
    ├── app.js                  # Main app logic (vanilla JS)
    └── style.css               # Styling (light + dark mode)
```

---

## Core Features (17.0)

### 1. Voice Discovery (Gemini Live)

- User clicks "🎤 Start voice conversation"
- Browser requests microphone access
- Worker mints an **ephemeral Gemini Live token** (1 hour, never exposed to browser)
- Frontend opens Gemini Live WebSocket → real-time voice conversation
- Gemini's system prompt uses **BMAD taxonomy** (actors, acceptance criteria, constraints, etc.)
- Conversation auto-saves to D1 after each exchange
- User can resume from browser (localStorage session ID) or different device (via D1 lookup)

### 2. Text Fallback

- "Type your idea instead" for accessibility or quiet environments
- Same BMAD-structured conversation flow, just typed
- Same D1 persistence

### 3. Issue Preview

- Auto-updates as conversation evolves
- Shows: title (editable), description, acceptance criteria, non-goals, constraints
- Headers match what `factory/analysis/bmad.py` already parses:
  - "Acceptance Criteria:"
  - "Non-Goals:"
  - "Constraints:"
  - etc.
- User can review, edit manually, save draft, or file immediately

### 4. GitHub Filing

- Creates a **new private repository** (seeded with starter template)
- Files a feature issue with `factory:ready` label
- Issue body is pre-formatted with BMAD sections
- Records the new repo in `pending_profiles` table for local sync
- Shows success page with link to GitHub

### 5. Local Profile Sync

- Runs as part of Phase 4 polling loop (TBD)
- Or manually: `python -m factory.intake.local_sync`
- Fetches `pending_profiles` from Worker (where `synced=false`)
- Creates `profiles/<name>.yml` locally for each
- Marks them synced so polling loop knows not to retry
- Example: user creates "recipe-sharer" repo via web → Worker records pending → next polling wake creates `profiles/recipe-sharer.yml` → factory can now claim issues from that repo

---

## Database Schema (D1)

### conversations

```sql
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  status TEXT CHECK (status IN ('draft', 'filed', 'completed')),
  created_at TEXT,
  updated_at TEXT,
  issue_number INTEGER,
  repo_url TEXT,
  issue_url TEXT,
  title TEXT,
  description TEXT,
  acceptance_criteria TEXT,
  non_goals TEXT,
  constraints TEXT,
  data_needed TEXT,
  error_handling TEXT
);
```

**Lifecycle:**
1. Created with status='draft' when user starts voice/text
2. Messages appended to messages table
3. Title/description auto-updated from conversation
4. On "File Issue": status='filed', issue_number + repo_url + issue_url set
5. Factory claims the GitHub issue, implements → issue closed → status='completed' (future enhancement)

### messages

```sql
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT REFERENCES conversations(id),
  role TEXT CHECK (role IN ('user', 'ai')),
  text TEXT,
  timestamp TEXT,
  token_count INTEGER
);
```

**Role:**
- `user`: actual user input (voice transcribed or typed)
- `ai`: Gemini response

**Token count:** for tracking quota usage (optional, for monitoring).

### pending_profiles

```sql
CREATE TABLE pending_profiles (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE,
  repo_url TEXT UNIQUE,
  owner TEXT,
  repo_name TEXT,
  created_at TEXT,
  synced BOOLEAN,
  synced_at TEXT,
  error TEXT
);
```

**Lifecycle:**
1. Created when Worker successfully creates a new GitHub repo
2. `synced=0` initially
3. Local polling loop (Phase 4) picks it up
4. Creates `profiles/<name>.yml` locally
5. Worker is notified → `synced=1`, `synced_at` set
6. If error during local creation → error field populated for debugging

---

## Worker API Endpoints

All endpoints return JSON. CORS enabled for `https://intake.ollama.mtourk.com`.

### POST /conversations

Create a new discovery conversation.

**Response:**
```json
{
  "conversation": {
    "id": "abc123...",
    "status": "draft",
    "created_at": "2026-10-03T..."
  }
}
```

### GET /conversations/:id

Fetch a conversation and its message history.

**Response:**
```json
{
  "conversation": { ... },
  "messages": [
    { "id": "...", "role": "user", "text": "...", "timestamp": "..." },
    { "id": "...", "role": "ai", "text": "...", "timestamp": "..." }
  ]
}
```

### POST /conversations/:id/messages

Add a user message (typically called automatically after user input).

**Body:**
```json
{ "text": "Tell me more about constraints..." }
```

**Response:**
```json
{ "message": { "id": "...", "conversation_id": "...", "role": "user", "text": "..." } }
```

### POST /conversations/:id/gemini-token

Mint an ephemeral Gemini Live token. (Called by frontend when user clicks voice button.)

**Response:**
```json
{
  "token": "...",
  "expires_at": "2026-10-03T...",
  "model": "gemini-2.0-flash-exp"
}
```

### POST /conversations/:id/file-issue

File the discovered issue to a GitHub repo.

**Body:**
```json
{
  "repo_url": "https://github.com/mtourk/recipe-sharer",
  "title": "Build a project dashboard",
  "description": "...",
  "acceptance_criteria": ["...", "..."],
  "non_goals": ["..."],
  "constraints": ["..."]
}
```

**Response:**
```json
{
  "conversation": { "id": "...", "status": "filed", "issue_number": 42, ... },
  "issue": { "number": 42, "title": "...", "html_url": "..." }
}
```

### POST /projects

Create a new GitHub repository (for a new project idea).

**Body:**
```json
{ "name": "recipe-sharer" }
```

**Response:**
```json
{
  "repo": {
    "name": "recipe-sharer",
    "full_name": "mtourk/recipe-sharer",
    "html_url": "https://github.com/mtourk/recipe-sharer",
    "private": true,
    "owner": "mtourk"
  },
  "profile": {
    "id": "...",
    "name": "recipe-sharer",
    "repo_url": "https://github.com/mtourk/recipe-sharer",
    "synced": false
  }
}
```

### GET /pending-profiles

List unsynced pending profiles.

**Response:**
```json
{
  "profiles": [
    {
      "id": "...",
      "name": "recipe-sharer",
      "repo_url": "https://github.com/...",
      "owner": "mtourk",
      "repo_name": "recipe-sharer",
      "created_at": "...",
      "synced": false
    }
  ]
}
```

### POST /pending-profiles/:id/sync-confirmed

Mark a profile as locally synced.

**Response:**
```json
{ "profile": { "id": "...", "synced": true, "synced_at": "..." } }
```

---

## Secrets (Cloudflare Worker)

Configured as Cloudflare Worker secrets (never in wrangler.toml):

| Secret | Purpose | Holder | Exposure |
|--------|---------|--------|----------|
| `GEMINI_API_KEY` | Long-lived Gemini API key | Worker only | Never reaches browser or local process |
| `GITHUB_REPO_CREATE_TOKEN` | Fine-grained GitHub PAT (repo creation + issues) | Worker only | Never reaches browser or local process |

**Key custody (per ADR-005/ADR-003):**
- Both secrets live as Cloudflare Worker environment variables
- GitHub Actions owns credentials for deployments (separate from this)
- No secret ever reaches the browser, local filesystem, or logs

---

## Frontend (Pages)

**URL:** `https://intake.ollama.mtourk.com`  
**Built with:** HTML + CSS + vanilla JavaScript (no framework)  
**Dependencies:** None (uses native Web APIs: Fetch, localStorage, Web Audio)

**Key JS behaviors:**
- Voice button opens Gemini Live (via ephemeral token from Worker)
- Text input sends via POST /conversations/:id/messages
- Messages auto-append to chat area (localStorage + D1)
- Issue preview auto-updates from conversation (heuristic + Gemini)
- "File Issue" → Worker creates GitHub issue → success page

**localStorage keys:**
- `dfactory_session_id`: current conversation ID (for resuming)
- `dfactory_draft`: full draft state (for offline save)
- `dfactory_ui_state`: app-shell UI state (active route only — see below)

### App Shell (FF-P04-01, D-NEW-001: extend vanilla JS in place)

`app.js` grew a small, dependency-free shell on top of the existing
conversation logic — no framework, no build step, no rewrite of the existing
code:

- **`Router`** — a hash-based client-side router (`#/`, `#/conversation`,
  `#/success`, `#/history`, `#/settings`). `Router.register(path, handler)`
  wires a route to a handler, `Router.navigate(path)` updates
  `window.location.hash` and resolves it, and `Router.start()` listens for
  `hashchange` (covers back/forward and manually-edited URLs) and resolves
  the initial route on load. `Router.setNotFound(handler)` controls the
  fallback for unknown hashes (redirects to `/`). The existing
  `showChatSection()` / `showSuccessSection()` / `resetIntake()` functions
  now call `Router.navigate(...)` instead of touching `classList` directly,
  so the conversation flow's resulting DOM state is unchanged.
- **`AppShellState`** — a tiny observable state container, independent of
  the conversation `state` object, persisting only `{ activeRoute }` to its
  own `dfactory_ui_state` localStorage key (never the existing
  `dfactory_session_id` / `dfactory_draft` keys) so a page reload reopens on
  the last-visited route.
- **`showPage(name)`** — the single place that toggles `.hidden` across all
  page sections (hero/chat/success/history/settings), sets `aria-current`
  on the matching nav link, and calls `.focus()` on the shown section's
  container (it has `tabindex="-1"`) so assistive tech announces the route
  change.
- **`createModal(modalEl, getFocusables)`** — a small reusable focus-trap
  factory used for both the help and repo modals: `Escape` closes whichever
  modal is open and restores focus to its trigger button; `Tab`/`Shift+Tab`
  cycle and wrap focus within the modal's focusable controls instead of
  escaping into the page behind it.

Responsive layout is mobile-first CSS (Flexbox) with a `@media (max-width:
640px)` compaction pass and a `@media (min-width: 1024px)` CSS Grid sidebar
layout (nav becomes a left rail); no Bootstrap/Tailwind/framework was added.

Covered by `factory/tests/test_intake_web_shell.py` (routing, state
persistence/recovery, keyboard navigation, focus management, and a full
regression pass of the pre-existing conversation-submission flow via
`factory/tests/helpers/app_shell_driver.mjs`).

---

## Testing Checklist

- [ ] Voice discovery conversation flows through 8–10 exchanges
- [ ] Text input works as fallback
- [ ] Conversation persists in D1 across browser reloads
- [ ] Issue preview auto-generates with extracted BMAD fields
- [ ] "File Issue" creates a GitHub issue with `factory:ready` label
- [ ] New repo is seeded with starter template (not empty)
- [ ] Pending profile is recorded and marked synced after local sync
- [ ] Gemini key is never exposed to browser (check Network tab, logs, localStorage)
- [ ] GitHub token scoped narrowly (verify PAT settings)
- [ ] CORS works for Pages ↔ Worker
- [ ] Mobile UI works (responsive layout, touch-friendly buttons)
- [ ] Help modal and state transitions work

---

## Integration Points (Future)

**Phase 17.1 (Telegram):**
- Bot API long-polling → RawIntakeMessage via TelegramChannelAdapter
- Voice notes transcribed via Gemini
- Progress pushed as replies in originating chat

**Phase 17.2 (Email):**
- IMAP polling → RawIntakeMessage via EmailChannelAdapter
- Attachments uploaded to R2 (Cloudflare object storage, optional)
- Replies sent as thread replies

**Phase 17.3 (WhatsApp):**
- Cloud API webhook (via tunnel) → RawIntakeMessage
- Same Gemini-structured discovery flow

**Phase 4 (Polling Loop):**
- Calls `factory.intake.local_sync.LocalProfileSync.sync_all()` on each wake-up
- Creates local profiles for any pending repos
- Factory then claims `factory:ready` issues as normal

---

## Security Boundaries

✅ **Verified:**
- Gemini API key stored only in Worker environment, never in code/localStorage/network
- GitHub token stored only in Worker environment, never exposed to browser
- BMAD-structured issue body ensures downstream factory validates independently
- Conversation data in D1 is encrypted at rest (Cloudflare default)
- D1 queries are parameterized (no SQL injection vectors)
- Frontend is static Pages (no server-side code execution)

⚠ **Assumptions:**
- Cloudflare account is secure (2FA, no leaked credentials)
- Browser environment is trusted (no malware intercepting localStorage)
- GitHub token is revoked if Worker is compromised

---

## Next Steps (after 17.0 approval)

1. **Deploy Worker + D1 schema**
   ```bash
   cd factory/intake/worker
   wrangler deploy --env production
   wrangler d1 migrations apply dark-factory-intake --env production
   ```

2. **Deploy Pages**
   ```bash
   wrangler pages deploy factory/intake/web --project dark-factory-intake
   ```

3. **Test end-to-end**
   - Open `https://intake.ollama.mtourk.com`
   - Run voice/text discovery
   - File a test issue
   - Verify it lands in GitHub with `factory:ready` label

4. **Manual profile sync (test)**
   ```bash
   python -m factory.intake.local_sync
   ```

5. **Integrate with Phase 4 polling loop** (once Phase 4 is built)
   - Call `local_sync.LocalProfileSync.sync_all()` on each wake-up

---

## Docs & References

- **ADR-004:** Profiles supersede fixed target repo (background context)
- **ADR-005:** Gemini Live as discovery-only exception (boundary enforcement)
- **PHASE_17_UX_BRAINSTORM.md:** Original UI/UX design
- **PHASE_17_PAGE_DESIGN.md:** Visual layout details
- **PHASE_17_BUILD_PLAN.md:** Architecture decisions (file structure, secrets, DB shape)
- **factory/analysis/bmad.py:** BMAD discovery structure (what we structure conversations around)
- **factory/backlog/scheduler.py:** Eligibility + priority ordering (why `factory:ready` label matters)

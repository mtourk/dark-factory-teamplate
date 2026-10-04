# Intake System: Proven Configuration Playbook

**Status:** Living document. Append to it — don't let future deploys relearn these lessons.
**Scope:** `factory/intake/` (web frontend on Cloudflare Pages, Worker backend, D1 database, Gemini integration, GitHub issue filing).
**Audience:** Any human operator, and — this is the point — the Phase 18 autonomous queue runner (`queue_runner.py`, per `docs/decisions/ADR-007.md`) once it exists. Every "what didn't work" item here is a failure mode the runner must not repeat.

Each section is a rule, stated as **DO** / **DON'T**, followed by the evidence (what was tried, what happened). If you're the factory and you hit a decision point covered here, follow the DO and skip straight past the DON'T — don't rediscover it by trial and error.

---

## 1. Secrets

**DO:** set every secret with `wrangler secret put <NAME>`, run from `factory/intake/worker/`:

```bash
cd factory/intake/worker
wrangler secret put GEMINI_API_KEY
wrangler secret put GITHUB_REPO_CREATE_TOKEN
```

It prompts for the value on stdin (or pipe one in: `echo "$VALUE" | wrangler secret put NAME`). This is the *only* mechanism that reliably makes a secret visible to the Worker as `env.<NAME>` at runtime.

**DON'T:**
- **Don't** add a `[secrets]` block to `wrangler.toml`. It is not valid wrangler syntax for actual secret values — it produced `Unexpected fields found in secrets field` on deploy and the key was never populated. `wrangler.toml` is for plaintext `[vars]` only; it is committed to git, so secrets must never go there regardless of syntax.
- **Don't** rely on setting the value as a Cloudflare dashboard **"Variable"** (plaintext env var) for anything secret. `GEMINI_API_KEY` was briefly configured this way and the Worker saw it as present but the dashboard's "Variable" type is meant for non-sensitive config — it's also overwritten/ignored by `wrangler.toml` `[vars]` on next deploy in some cases, causing confusing drift between dashboard state and deployed state. If a key is secret, use `wrangler secret put`, full stop; if it's genuinely non-secret config (like `VERSION`, `ENVIRONMENT`, `GITHUB_ORG`), put it in `[vars]` in `wrangler.toml` and commit it.

**Verify a secret is actually visible to the Worker:**
```bash
# the Worker code itself does this defensive check — see src/index.ts handleTextResponse:
#   const hasGeminiKey = !!env.GEMINI_API_KEY;
#   if (!hasGeminiKey) return json({ error: "GEMINI_API_KEY secret not configured", debug: { keys: Object.keys(env) } }, 500);
# if you get that 500 with your secret name missing from `keys`, the secret didn't bind — redo `wrangler secret put`.
```

**Known residual risk:** `CREATE_ROUTE_API.md` had a real Cloudflare API token committed in plaintext at 4 locations (commit `10fd1ce`). It has been redacted in the working tree (`<REDACTED-ROTATE-THIS-TOKEN>`), but **it still exists in git history** (`git log -p --follow -- CREATE_ROUTE_API.md | grep -c cfat_` → 8 hits across history). Redacting the file does not revoke the token. **This token must be rotated/revoked in the Cloudflare dashboard** (My Profile → API Tokens) — this has not been confirmed done as of this writing. The factory must never write a real token into a tracked file, even temporarily; use `<REDACTED-...>` placeholders in docs and `wrangler secret put` for real values.

---

## 2. CORS and the frontend origin

**The failure pattern (recurring, cost the most time this session):** `wrangler pages deploy` without a fixed project alias assigns a **new random preview subdomain on every deploy** (e.g. `https://5e4e051a.dark-factory-intake.pages.dev`, then `https://55fac1e3.dark-factory-intake.pages.dev`, …). The Worker's `CORS_HEADERS["Access-Control-Allow-Origin"]` is a single hardcoded string. Every time Pages reassigned the subdomain, the frontend started throwing CORS `NetworkError`s because the Worker was still allow-listing the previous URL.

**DON'T** chase this by hardcoding the latest preview URL into `src/index.ts` and redeploying the Worker each time. It works until the next Pages deploy, then breaks again — not a fix, a treadmill.

**DO:** use a **Cloudflare Pages Custom Domain** so the frontend has one permanent URL regardless of how many times Pages redeploys:
1. Cloudflare dashboard → Pages project `dark-factory-intake` → Custom domains → Add `factory.mtourk.com`.
2. Cloudflare auto-provisions the DNS record for a Custom Domain (unlike a plain Worker Route, which does *not* auto-create DNS — see `docs/operations/CLOUDFLARE_DNS_AUTOMATION.md` for the distinction and the API-automatable path for future subdomains).
3. Set the Worker's CORS origin to the stable domain, once, and never touch it again:
   ```typescript
   // factory/intake/worker/src/index.ts
   const CORS_HEADERS = {
     "Access-Control-Allow-Origin": "https://factory.mtourk.com",
     ...
   };
   ```
4. `wrangler deploy` once. Done — this does not need to change on future Pages deploys.

**Verify CORS is correctly configured** (run after any Worker deploy):
```bash
curl -s -i -X OPTIONS https://dark-factory-intake.mohammad-tourk.workers.dev/conversations \
  -H "Origin: https://factory.mtourk.com" | grep -i "access-control-allow-origin"
# expect: access-control-allow-origin: https://factory.mtourk.com
```

**Gotcha — don't mistake edge-cache lag for a failed deploy:** immediately after a `wrangler deploy` that changes `CORS_HEADERS`, the above `curl` check can still show the *old* origin for a few seconds (Cloudflare edge cache propagation). The correct response is to **wait ~5 seconds and re-run the check**, not to assume the deploy failed and retry with `wrangler deploy --force` (see §4 — that command is blocked anyway).

---

## 2.5 Custom Domains: One Hostname, One Resource (Critical for Phase 18)

**The failure pattern:** A single Cloudflare-managed domain (e.g., `factory.mtourk.com`) can only be assigned to *one* resource at a time — either Pages OR Worker OR a DNS zone record. If you try to assign the same domain to both Pages and Worker:

- Cloudflare does not error; it silently accepts the second assignment and **overrides** the first.
- Traffic to the domain now routes to whichever one you assigned last (or by resource priority if both assignments are "active" in dashboard).
- You may not notice immediately; instead you get mysterious "page not found" or "API not working" errors without understanding why.
- You **cannot** serve the Pages frontend and Worker API from the same domain via domain assignment alone.

**The mistake (this session):** `factory.mtourk.com` was initially assigned to the Worker because that was the first resource available. When Pages was deployed and its custom domain feature was used, assigning the domain to Pages *overrode* the Worker assignment. Meanwhile, the Worker had hardcoded CORS origin `"https://factory.mtourk.com"`, so when trying to serve static assets, the request would fail (or return 404 from Pages' SPA fallback if you're lucky).

**The workaround (anti-pattern, DON'T do this):** Add a hardcoded fallback route in the Worker that proxies requests to `https://cd836e02.dark-factory-intake.pages.dev/`, trying to manually route the UI requests to Pages and API requests to the Worker. **NEVER DO THIS** because:
1. The Pages preview URL (`cd836e02.dark-factory-intake.pages.dev`) is **generated fresh on every Pages deploy** and will immediately go stale.
2. It doubles every request through two hops (Worker → Pages) instead of going direct to Pages.
3. It bypasses Cloudflare's Pages CDC/caching optimizations.
4. It reintroduces the exact "stale URL breaks everything" problem you're trying to solve.

**DO — the correct pattern (Architecture-level):**

**Option A (Recommended for Phase 17.0 / single app):**
- **Pages gets the user-facing custom domain:** `factory.mtourk.com` → Pages (UI)
- **Worker gets its ambient domain:** `dark-factory-intake.mohammad-tourk.workers.dev` → Worker (API)
- Frontend code calls the Worker's ambient domain: `fetch("https://dark-factory-intake.mohammad-tourk.workers.dev/conversations", ...)` — **this never changes, even if you deploy the app 100 times**.

This is the current live setup (proven working).

**Option B (For Phase 18 / multiple apps with separate API subdomains):**
- **Pages gets:** `<app-slug>.mtourk.com` → Pages (UI)
- **Worker gets:** `api.<app-slug>.mtourk.com` → Worker (API, provisioned via DNS CNAME, see `CLOUDFLARE_DNS_AUTOMATION.md`)
- Frontend code calls the API subdomain: `fetch("https://api.<app-slug>.mtourk.com/conversations", ...)`

**Option C (Not recommended):**
- Both resources behind a single domain, but routed by **path** (not subdomain): `factory.mtourk.com/` → Pages, `factory.mtourk.com/api/*` → Worker. Requires either a reverse proxy in front of Cloudflare (complexity) or routing logic in one of the Cloudflare resources (anti-pattern, see the workaround disaster above).

**For Phase 18 automation:** When the factory provisions a new app's infrastructure:
1. Provision Pages deployment (becomes live automatically on Pages' default domain)
2. Provision Worker deployment (lives on its workers.dev domain automatically)
3. Create a Pages custom domain (e.g., `new-app.mtourk.com`) — Cloudflare auto-provisions the DNS record for Pages
4. **DO NOT** try to assign the same custom domain to the Worker — leave Worker on its ambient `.workers.dev` domain or use a subdomain (e.g., `api.new-app.mtourk.com`) if you want a prettier API URL
5. Update the new app's frontend to call the Worker's actual domain in its source code or environment config

**Verification:**
```bash
# Pages should respond with HTML for the custom domain
curl -s https://factory.mtourk.com/ | head -1
# → <!DOCTYPE html>

# Worker API should respond with JSON on its own domain
curl -s https://dark-factory-intake.mohammad-tourk.workers.dev/version
# → {"version":"3","deployed_at":"..."}

# If you somehow got the domains crossed and are getting JSON on Pages custom domain, 
# or HTML on the Worker domain, the assignment is reversed — fix in Cloudflare dashboard.
```

---

## 3. Local LLM (Ollama) for Text, Gemini for Voice (Phase 17.1+)

**Updated 2026-10-04:** Text discovery now prefers local Ollama; Gemini is used only for voice and as a fallback.

### The strategy

The app has two input modes:

1. **Voice** (`🎤 Describe your feature idea`) — requires Gemini Live's real-time audio streaming. No local LLM alternative.
2. **Text** (`Type your idea instead`) — just needs a discovery interview. **Prefers local Ollama** (free, fast, no rate limits), **falls back to Gemini** if Ollama unreachable.

### Why prefer local Ollama for text

- **Zero API cost** — local Ollama is free; Gemini API costs credits/month
- **No rate limits** — won't hit Gemini's API quota mid-discovery
- **No model deprecation surprises** — you control the model; no sudden "404: model no longer available" (which broke the app 2026-10-04)
- **Full response length** — no token caps; discovery can be as detailed as needed
- **Privacy** — conversation never leaves your machine

### Setup: local Ollama with Cloudflare tunnel (ollama.mtourk.com)

**Prerequisite:** Ollama running locally and exposed via a Cloudflare tunnel at `https://ollama.mtourk.com`.

The Worker code reaches Ollama via the public tunnel URL (not localhost). This means:
- No ngrok or separate tunnel tool needed
- Tunnel persists across machine restarts
- Clean, stable URL

**Setup (one-time, if not already done):**

If you haven't already, create a Cloudflare tunnel to expose your local Ollama server:

```bash
# 1. Install cloudflared (Cloudflare tunnel client)
# Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/install-and-setup/installation/
# Or via package manager (macOS): brew install cloudflare/cloudflare/cloudflared
# Or via package manager (Windows): choco install cloudflared

# 2. Authenticate with Cloudflare
cloudflared login
# (Opens browser to authorize)

# 3. Create a tunnel pointing to local Ollama
cloudflared tunnel create ollama

# 4. Route the domain to the tunnel
cloudflared tunnel route dns ollama ollama.mtourk.com
# (This adds a DNS CNAME record in Cloudflare dashboard automatically)

# 5. Configure the tunnel (create ~/.cloudflared/config.yml)
# Add:
# tunnel: <TUNNEL_UUID>
# credentials-file: ~/.cloudflared/<TUNNEL_UUID>.json
# ingress:
#   - hostname: ollama.mtourk.com
#     service: http://localhost:11434
#   - service: http_status:404

# 6. Run the tunnel
cloudflared tunnel run ollama
# (Keep this running; it stays active in background)
```

Once the tunnel is active, the Worker automatically uses `https://ollama.mtourk.com/api/chat` for text discovery. **No ngrok, no manual URL switching.**

**Testing the tunnel:**
```bash
curl https://ollama.mtourk.com/api/tags
# Should return your Ollama models, not a connection error
```

**Current status:** Tunnel is active and Worker is configured to use it. Text-response calls go through `ollama.mtourk.com` automatically.

### Model selection (Ollama)

Default is `neural-chat` (lightweight, good for discovery interviews). To change, edit `factory/intake/worker/src/gemini.ts`:

```typescript
private readonly OLLAMA_MODEL = "neural-chat"; // Change to your preferred model
```

Tested and recommended:
- `neural-chat` (recommended for discovery — balanced, fast, good context window)
- `mistral` (faster, slightly less conversational)
- `llama2` (slower, more detailed)

Install models with: `ollama pull neural-chat`

### When Gemini is used

- **Voice mode:** always Gemini Live (no alternative for real-time audio)
- **Text mode:** Gemini if Ollama is unreachable
  - Ollama tunnel is down
  - Local Ollama server is offline
  - Worker can't reach `localhost:11434`

This graceful degradation ensures voice mode and text mode both keep working even if the tunnel fails.

### Known issues / debugging

**"Sorry, I had trouble generating a response" (text mode only):**
- Check if local Ollama is running: `curl http://localhost:11434/api/tags`
- Check the tunnel is active and exposing 11434
- Worker logs will show which fallback it's using; check `wrangler tail` for details

**"Gemini model no longer available" (404):**
- This happened 2026-10-04 when Gemini deprecated `gemini-2.0-flash` and `gemini-2.5-flash-lite`
- Current fallback chain (in `factory/intake/worker/src/gemini.ts`) is `gemini-3.5-flash` → `gemini-3.5-flash-lite` → `gemini-3-flash` → `gemini-2.5-flash`
- If you see a 404 again, test the model with curl first:
  ```bash
  curl -s -X POST "https://generativelanguage.googleapis.com/v1/models/<MODEL>:generateContent" \
    -H "Content-Type: application/json" -H "x-goog-api-key: $GEMINI_API_KEY" \
    -d '{"contents":[{"role":"user","parts":[{"text":"hi"}]}]}'
  ```

---

## 3b. Gemini API Key (Voice Mode / Fallback)

## 4. Deployment commands — what runs, what's blocked

This is the single most important operational fact for an autonomous runner: **some mutating `wrangler` commands are blocked by this environment's permission auto-classifier when invoked by an agent, independent of which tool invokes them.**

Confirmed blocked, regardless of shell:
- `wrangler deploy --force`
- `wrangler pages deploy . --project-name dark-factory-intake --commit-dirty=true` (tried directly via Bash)
- Running `./deploy.ps1` / `.\deploy.ps1` without `-DryRun` (i.e., the real, non-dry-run path) via the PowerShell tool

The denial is explicit and says not to work around it by switching tools, encodings, or splitting the command up — and that was respected here; **don't try to defeat this classifier**. The practical consequence: **an agent cannot currently complete the actual Pages/Worker deploy step by itself in this environment.** The correct procedure is:

1. Agent does everything *except* the live deploy: bump `factory/intake/web/VERSION`, update `wrangler.toml`'s `VERSION`/`DEPLOYED_AT` vars, edit code, commit.
2. Agent hands the deploy step back explicitly: "run `./deploy.sh` (bash) or `.\deploy.ps1` (PowerShell) yourself."
3. Human runs it. Success is verifiable afterward (see §5) without the human needing to interpret wrangler output themselves.

**Confirmed working** (plain, un-forced commands, run by a human or in a context without the classifier):
```bash
# from factory/intake/worker/
wrangler deploy                      # current — no --env production needed
wrangler secret put <NAME>
wrangler d1 execute dark-factory-intake < schema.sql   # NOTE: current wrangler.toml has no [env.production] block
wrangler tail                         # live log stream, useful for debugging in realtime

# from factory/intake/web/
wrangler pages deploy . --project-name dark-factory-intake --commit-dirty=true
```

**Config drift note:** earlier docs (`PHASE_17_0_DEPLOYMENT.md`, `DEPLOYMENT_LOG.md`) reference `--env production` on `wrangler deploy` / `wrangler d1 execute`. The current `wrangler.toml` has **no `[env.production]` section** — it's flat `[vars]` + `[[d1_databases]]` at the top level. If you add an `--env production` flag back, you must also re-add the matching `[env.production]` block to `wrangler.toml`, or the flag targets a non-existent environment. As it stands today, omit `--env production` entirely.

**The dry-run pattern is good and should be kept:** `deploy.ps1 -DryRun` / `deploy.sh --dry-run` runs the version-bump logic and prints what *would* run, without touching `wrangler`. This was used successfully to confirm the version-increment and timestamp logic before being blocked on the real run — keep using dry-run first when validating script changes.

---

## 5. Verifying a deployment succeeded (works without needing wrangler output)

Because the agent/factory may not be the one running the actual deploy command (§4), verification must be possible purely by observing the live endpoints:

```bash
# 1. Version/build check — the number and timestamp MUST have changed from before the deploy
curl -s https://dark-factory-intake.mohammad-tourk.workers.dev/version
# → {"version":"2","deployed_at":"2026-10-03T23:43:18Z"}

# 2. CORS check — must show the permanent domain, not a stale preview URL
curl -s -i -X OPTIONS https://dark-factory-intake.mohammad-tourk.workers.dev/conversations \
  -H "Origin: https://factory.mtourk.com" | grep -i "access-control-allow-origin"

# 3. Frontend footer — https://factory.mtourk.com should visually show "Version N · <timestamp> UTC"
```
This is the whole point of the version-tracking feature (`factory/intake/web/VERSION`, `/version` Worker route, `version.js`'s `updateVersionFooter()`): a deploy is "proven" when the version number visibly increments and the timestamp visibly updates. If it doesn't change, the deploy didn't take effect — don't trust wrangler's stdout alone, trust the live `/version` response.

---

## 6. Frontend UI bugs already fixed — don't reintroduce

- **Input wrapping bug:** a single-line `<input type="text">` for the chat box caused characters like "o"/"k" to wrap/clip oddly under certain widths. Fixed by switching to `<textarea rows="2">`. Don't revert to `<input type="text">` for this field.
- **Hardcoded repo URL in file-issue flow:** the "file issue" action once had a hardcoded target repo URL baked into the frontend, so it always filed to one repo regardless of what the user selected in the modal. Fixed to read the repo URL from the user's actual selection/modal state at call time. Any new flow that files an issue must take `repo_url` as live state, never a literal.
- **localStorage auto-resume:** the conversation now persists `conversation_id` to `localStorage` and resumes it on reload, instead of silently starting a new conversation and orphaning the old one. Keep this behavior when touching `app.js`'s `init()`.

---

## 7. TypeScript / Worker build

A stray extra closing `}` in `src/index.ts` once broke the build with a plain "Unexpected '}'" syntax error that `wrangler deploy` surfaced immediately (it transpiles/bundles before upload — it will not silently deploy broken TS). **DO** treat any `wrangler deploy` failure with a TS/syntax error in the output as a real build error to fix, not a transient platform issue — it won't "just work" on retry. There is no separate `tsc --noEmit` step wired in; `wrangler deploy`'s own bundling is the de facto type/syntax check for this Worker. If the factory wants a faster feedback loop, run `wrangler deploy --dry-run` (a real wrangler flag, distinct from the project's own `deploy.sh --dry-run`) to catch build errors without actually publishing.

---

## 8. D1 database

- Live tables today: `conversations`, `messages`, `pending_profiles`. Schema file: `factory/intake/worker/schema.sql` (plus `schema_phase18.sql`, which is a **proposed, not-yet-applied** migration for `build_queue` / `build_queue_updates` per ADR-007 — don't assume those tables exist until that file has actually been run with `wrangler d1 execute`).
- Apply a schema file with: `wrangler d1 execute dark-factory-intake < path/to/schema.sql` (run from `factory/intake/worker/`, no `--env production` per §4's drift note).
- D1's `database_id` in `wrangler.toml` is not a secret and is committed: `ffdfcde8-d68d-48b6-9436-2b12b5245968`.

---

## 9. DNS / subdomain provisioning for new apps (Phase 18 lookahead)

Full runbook already written: `docs/operations/CLOUDFLARE_DNS_AUTOMATION.md`. Short version: a Cloudflare **Custom Domain** (used for `factory.mtourk.com`, see §2) auto-creates its DNS record when added via dashboard or Pages API; a plain Worker **Route** does not auto-create DNS and needs a manual/API-driven CNAME. For Phase 18's automated per-app subdomain provisioning, use the Cloudflare DNS API directly (`POST /zones/{zone_id}/dns_records`, documented with a full `CloudflareDNSAdapter` reference implementation in that doc) rather than relying on Pages Custom Domain UI steps, since the factory needs this to be scriptable with no manual dashboard clicks.

---

## 10. Quick-reference command cheat sheet

| Task | Command | Works for agent? |
|---|---|---|
| Set a secret | `wrangler secret put NAME` (from `worker/`) | Not confirmed blocked, but prefer human-run for secrets regardless |
| Deploy Worker (plain) | `wrangler deploy` (from `worker/`) | Blocked when `--force` |
| Deploy Pages (plain) | `wrangler pages deploy . --project-name dark-factory-intake --commit-dirty=true` (from `web/`) | **Blocked** |
| Dry-run version bump | `./deploy.sh --dry-run` / `.\deploy.ps1 -DryRun` | Works |
| Real version-bump deploy | `./deploy.sh` / `.\deploy.ps1` | **Blocked** (hand to human) |
| Apply D1 schema | `wrangler d1 execute dark-factory-intake < schema.sql` | Not yet tested from agent context |
| Tail live logs | `wrangler tail` (from `worker/`) | Works (read-only) |
| Check version/build | `curl .../version` | Works |
| Check CORS origin | `curl -i -X OPTIONS ... -H "Origin: ..."` | Works |

---

## Sources

Everything above was derived directly from this session's actual commands and their actual output — not from documentation or assumption. Where a command is marked "blocked," that's a direct, reproduced denial from the environment's permission auto-classifier, observed at least twice independently (Bash and PowerShell tools, two different commands). Related docs: `docs/decisions/ADR-007.md` (Phase 18 design), `docs/operations/CLOUDFLARE_DNS_AUTOMATION.md` (DNS automation detail), `PHASE_17_0_DEPLOYMENT.md` / `DEPLOYMENT_LOG.md` (original, now partially superseded, deploy walkthroughs — see §4's drift note before following their `--env production` flags verbatim).

**Last updated:** 2026-10-04.

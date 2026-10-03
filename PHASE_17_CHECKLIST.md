# Phase 17.0 Pre-Deployment Checklist

## Code Review ✅

- [x] Worker backend (TypeScript)
  - [x] Request routing complete
  - [x] D1 queries implemented + typed
  - [x] Gemini token minting implemented
  - [x] GitHub API calls implemented
  - [x] Error handling throughout

- [x] Frontend (HTML/CSS/JS)
  - [x] UI sections complete (hero, chat, success)
  - [x] Voice button wired
  - [x] Text input wired
  - [x] Issue preview auto-updates
  - [x] Mobile responsive
  - [x] localStorage persistence

- [x] Python modules
  - [x] Channel adapters defined
  - [x] RawIntakeMessage interface
  - [x] LocalProfileSync utility
  - [x] Type hints throughout

- [x] Documentation
  - [x] README (comprehensive)
  - [x] Deployment guide (step-by-step)
  - [x] ADR-006 (security decision)
  - [x] Inline code comments

## Architecture Decisions ✅

- [x] **Secrets:** Cloudflare Worker environment only (not wrangler.toml)
- [x] **Database:** D1 with 3 tables (conversations, messages, pending_profiles)
- [x] **Frontend:** Vanilla JS (no framework)
- [x] **Discovery:** BMAD-structured Gemini conversation
- [x] **GitHub:** Fine-grained PAT (new, separate from factory's daily creds)
- [x] **Repos:** Private + seeded with starter template
- [x] **Sync:** Polling loop integration (Phase 4 TBD, manual for now)

## Security Review ✅

- [x] Long-lived secrets never in source code
- [x] D1 queries parameterized (no SQL injection)
- [x] CORS restricted to Pages frontend
- [x] Issue body uses parser-friendly headers
- [x] Frontend is static (no server code execution)
- [x] localStorage has no sensitive data
- [x] ADR-006 decision documented

## Before You Deploy

### Secrets Prepared?
- [ ] GitHub PAT created (fine-grained, scope: repo admin + issues + metadata)
- [ ] Gemini API key obtained
- [ ] Both values saved somewhere safe (NOT in code)

### Cloudflare Account Ready?
- [ ] Logged into Cloudflare dashboard
- [ ] `wrangler` CLI installed locally (`npm install -g wrangler`)
- [ ] `wrangler login` completed

### Worker Configuration?
- [ ] `factory/intake/worker/wrangler.toml` ready to edit (D1 database_id will be filled after creation)
- [ ] Reviewed route settings (production environment)

### Pages Configuration?
- [ ] Reviewed `factory/intake/web/app.js` Worker URL constant (will be filled after Worker deploy)

## Deployment Order (MUST follow)

1. **Step 1: Create D1 database**
   - [ ] `wrangler d1 create dark-factory-intake`
   - [ ] Copy `database_id` to `wrangler.toml`

2. **Step 2: Add Cloudflare secrets**
   - [ ] Dashboard → Workers → Secrets
   - [ ] Add `GEMINI_API_KEY`
   - [ ] Add `GITHUB_REPO_CREATE_TOKEN`

3. **Step 3: Deploy Worker**
   - [ ] `cd factory/intake/worker`
   - [ ] `npm install`
   - [ ] `wrangler deploy --env production`
   - [ ] Copy Worker URL

4. **Step 4: Apply D1 schema**
   - [ ] `wrangler d1 migrations apply dark-factory-intake --env production`

5. **Step 5: Update & deploy Pages**
   - [ ] Update `factory/intake/web/app.js` with Worker URL
   - [ ] `cd factory/intake/web`
   - [ ] `wrangler pages deploy . --project dark-factory-intake`
   - [ ] Note Pages URL

6. **Step 6: Update CORS (if needed)**
   - [ ] If Pages URL is custom (not `pages.dev`), update `src/index.ts` CORS header
   - [ ] Redeploy Worker

## Testing After Deployment

### 1. Page Loads ✓
- [ ] Open Pages URL in browser
- [ ] See "Dark Factory — Feature Intake" header
- [ ] See 🎤 button + text

### 2. Voice Flow ✓
- [ ] Click 🎤
- [ ] Chat section appears
- [ ] Message exchange happens (simulated, currently)
- [ ] Issue preview populates

### 3. Text Flow ✓
- [ ] Reload page
- [ ] Click "Type your idea instead"
- [ ] Type message
- [ ] Response appears

### 4. File Issue ✓
- [ ] After exchanges, click "📤 File Issue"
- [ ] Check GitHub — new repo should exist
- [ ] Check issue in that repo — should have `factory:ready` label
- [ ] Note issue number

### 5. Local Sync ✓
- [ ] `python -m factory.intake.local_sync`
- [ ] Should sync the new profile
- [ ] Check `profiles/` — new YAML file should exist
- [ ] Verify it contains correct repo URL

### 6. No Secrets Exposed ✓
- [ ] Open browser DevTools → Network tab
- [ ] Check all requests to Worker
- [ ] Confirm no Gemini key or GitHub token in request bodies
- [ ] Confirm no secrets in browser console
- [ ] Confirm no secrets in localStorage

## Rollback Plan

If something breaks:

```bash
# Undo Pages deployment
wrangler pages rollback --project dark-factory-intake

# Undo Worker deployment
wrangler rollback --env production

# Or start fresh
wrangler pages projects delete dark-factory-intake
wrangler d1 delete dark-factory-intake --env production
```

## Post-Deployment

- [ ] Document deployment date + URLs in a notes file
- [ ] Test with a real project idea (not just test)
- [ ] Set calendar reminder for GitHub PAT rotation (90 days)
- [ ] Monitor Cloudflare usage (free tier should be more than enough)
- [ ] (Optional) Set up Cloudflare Access if you want to restrict who can access

## Go/No-Go Decision

**Ready to deploy?**
- [ ] All boxes above checked
- [ ] All secrets prepared
- [ ] Deployment order understood
- [ ] Testing plan ready

**Decision: GO / NO-GO**

_______________________________________________

(Sign here when ready)


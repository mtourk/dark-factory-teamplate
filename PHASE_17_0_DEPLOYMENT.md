# Phase 17.0 Deployment Guide

**Audience:** You (deploying to your Cloudflare account)  
**Time estimate:** 30–45 minutes  
**Prerequisites:**
- Cloudflare account (free or paid)
- GitHub account with repo creation permission
- Gemini API key (get from console.cloud.google.com)
- Node.js 18+ installed locally (for `wrangler` CLI)

---

## Step 1: Prepare Secrets

### 1a. GitHub Fine-Grained PAT

Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens

**Create token with:**
- Name: `cloudflare-repo-creation`
- Expiration: 90 days (or your preferred cadence)
- Permissions:
  - Repository: Administration (write) — allows creating repos
  - Repository: Contents (read) — allows reading repo (for seeding)
  - Repository: Issues (write) — allows filing issues
  - Account: Metadata (read) — allows checking username

Copy the token value (you'll need it in Step 2).

### 1b. Gemini API Key

1. Go to [Google AI Studio](https://ai.google.dev/aistudio)
2. Click "Get API key"
3. Create or select a project
4. Copy the API key (you'll need it in Step 2)

---

## Step 2: Set Up Cloudflare

### 2a. Create D1 Database

```bash
# Install wrangler (if not already installed)
npm install -g wrangler

# Authenticate to Cloudflare
wrangler login

# Create D1 database
cd factory/intake/worker
wrangler d1 create dark-factory-intake
```

**Save the `database_id`** shown in the output. You'll add it to `wrangler.toml` in the next step.

### 2b. Update wrangler.toml

Edit `factory/intake/worker/wrangler.toml` and fill in:

```toml
[[d1_databases]]
binding = "DB"
database_name = "dark-factory-intake"
database_id = "YOUR_DATABASE_ID_HERE"  # ← Paste from Step 2a

# For production environment
[env.production.d1_databases]
binding = "DB"
database_name = "dark-factory-intake"
database_id = "YOUR_DATABASE_ID_HERE"  # ← Same ID
```

### 2c. Add Secrets to Cloudflare

Via the Cloudflare dashboard:

1. Go to **Workers** → **Secrets** (or find the settings for `dark-factory-intake` worker)
2. Click **Add secret**
3. Name: `GEMINI_API_KEY`
   Value: (paste your Gemini API key from 1b)
4. Click **Add secret** again
5. Name: `GITHUB_REPO_CREATE_TOKEN`
   Value: (paste your GitHub PAT from 1a)

**Note:** Don't put these in `wrangler.toml` — only as runtime secrets on Cloudflare.

---

## Step 3: Deploy Worker

```bash
cd factory/intake/worker

# Install dependencies
npm install

# Deploy to production
wrangler deploy --env production
```

Expected output:
```
✓ Uploaded dark-factory-intake (...)
✓ Published to https://dark-factory-intake.{your-subdomain}.workers.dev
```

**Copy the Worker URL** (you'll need it to update the frontend in Step 4).

### 3a. Apply D1 Schema

```bash
# Apply migrations
wrangler d1 migrations apply dark-factory-intake --env production
```

If you haven't set up migrations yet, run the schema manually:

```bash
wrangler d1 execute dark-factory-intake --env production < schema.sql
```

---

## Step 4: Deploy Pages Frontend

The Pages frontend needs to know the Worker URL (from Step 3).

### 4a. Update Worker URL in app.js

Edit `factory/intake/web/app.js` and update the `WORKER_URL` constant:

```javascript
// Line 8 (approximately)
const WORKER_URL = "https://dark-factory-intake.{your-subdomain}.workers.dev";
// ↓ should be
const WORKER_URL = "https://YOUR_WORKER_URL_FROM_STEP_3";
```

### 4b. Deploy Pages

```bash
cd factory/intake/web
wrangler pages deploy . --project dark-factory-intake
```

If the project doesn't exist, wrangler will create it.

Expected output:
```
✓ Deployment complete
Project name: dark-factory-intake
Deployment ID: abc123...
✓ Deployment URL: https://dark-factory-intake.pages.dev
```

**Copy the Pages URL.**

### 4c. Update CORS in Worker

The Worker's CORS headers currently hardcode the Pages URL. If you got a different URL, update `factory/intake/worker/src/index.ts`:

```typescript
// Line 16
const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "https://intake.ollama.mtourk.com",  // ← Update this
  // ...
};
```

Change to your actual Pages URL, then redeploy the Worker:

```bash
cd factory/intake/worker
wrangler deploy --env production
```

---

## Step 5: Test End-to-End

### 5a. Open the Page

Visit your Pages URL from Step 4b (e.g., `https://dark-factory-intake.pages.dev`).

You should see:
- Header: "Dark Factory — Feature Intake"
- Large 🎤 voice button
- "Describe your feature idea" text

### 5b. Try Voice (Simulated)

Click the 🎤 button.

**Expected:**
- "Start voice conversation" → chat section appears
- Animated voice indicator
- Simulated Gemini responses (currently hardcoded conversation in the placeholder `simulateGeminiConversation()` function — real Gemini Live requires additional setup)

### 5c. Try Text Fallback

Reload the page, click "Type your idea instead":
- Chat section appears
- Text input ready
- Type something → simulated AI response

### 5d. File an Issue

After a few exchanges:
- Issue preview should populate with title/description
- Click "📤 File Issue"
- Should see success page with GitHub link

**Check GitHub:**
- New private repo should exist: `https://github.com/YOUR_ORG/test-project` (or whatever name you typed)
- An issue should be in that repo with `factory:ready` label

### 5e. Test Local Sync

```bash
# From the repo root
python -m factory.intake.local_sync
```

**Expected output:**
```
Fetching pending profiles from Intake Worker...
Found 1 pending profile(s).
  Creating local profile: test-project
    Repository: https://github.com/YOUR_ORG/test-project
  ✓ Profile created at profiles/test-project.yml
  ✓ Synced test-project

Sync complete: 1/1 profiles synced.
```

**Check local:**
```bash
ls profiles/test-project.yml
cat profiles/test-project.yml
# Should see a valid profile YAML
```

---

## Step 6: Integrate with Phase 4 Polling Loop (Optional)

Once Phase 4 is built, add this to the polling loop:

```python
# In factory's polling loop code
from factory.intake.local_sync import LocalProfileSync

syncer = LocalProfileSync()
syncer.sync_all()
```

This ensures that any new repos created via the web UI are automatically available to the factory.

---

## Troubleshooting

### "Secrets not working" / 401 Errors

- Verify secrets are added to Cloudflare (not in `wrangler.toml`)
- Redeploy Worker after adding secrets: `wrangler deploy --env production`

### "Database not found"

- Confirm `database_id` is correct in `wrangler.toml`
- Run migrations: `wrangler d1 migrations apply dark-factory-intake --env production`

### "CORS error in browser console"

- Check `CORS_HEADERS["Access-Control-Allow-Origin"]` matches your Pages URL
- Update `src/index.ts` and redeploy Worker

### "Can't file issues" / 401 from GitHub

- Verify GitHub PAT secret is correct (no typos)
- Check PAT permissions (needs repo admin + issues)
- Try revoking and creating a new PAT

### "Gemini token fails"

- Verify `GEMINI_API_KEY` secret is correct
- Check your Gemini quota hasn't been exceeded
- Visit [Google Cloud Console](https://console.cloud.google.com) to verify API is enabled

### "localStorage not persisting"

- Make sure browser allows localStorage (not in private/incognito mode)
- Clear browser cache and retry

---

## Monitoring & Maintenance

### Check Worker Logs

```bash
wrangler tail dark-factory-intake --env production
```

### Check D1 Database

```bash
wrangler d1 execute dark-factory-intake --env production < schema.sql
```

Or query via dashboard:

```bash
wrangler d1 query dark-factory-intake "SELECT COUNT(*) FROM conversations;" --env production
```

### Rotate Secrets (Recommended Every 90 Days)

1. Create a new GitHub PAT (same settings as before)
2. Update secret on Cloudflare: Workers → Secrets → Edit `GITHUB_REPO_CREATE_TOKEN`
3. Paste new token
4. Redeploy Worker: `wrangler deploy --env production`
5. Revoke old PAT on GitHub

---

## Rollback

If something goes wrong:

```bash
# Undeploy Worker
wrangler deployments list
wrangler rollback --env production

# Undeploy Pages
wrangler pages rollback --project dark-factory-intake
```

Or delete and start over:

```bash
# Delete Pages project
wrangler pages projects delete dark-factory-intake

# Delete D1 database
wrangler d1 delete dark-factory-intake --env production
```

---

## Next Steps

After deployment:

1. **Test with a real project idea** — go through the full flow (voice/text → file issue → verify GitHub)
2. **Test resume** — close browser, reopen, see if you can resume a draft
3. **Verify security** — open browser DevTools Network tab, confirm no secrets are transmitted
4. **Document your URLs** — save Worker URL and Pages URL somewhere safe
5. **(Future) Integrate Phase 4** — once Phase 4 backlog scheduler is built, add local sync call
6. **(Future) Telegram/Email** — Phase 17.1+ can reuse the Worker endpoints and D1 schema

---

## Support

If deployment fails:
- Check Cloudflare dashboard → Workers → Logs
- Review error messages in `wrangler` output
- Verify all prerequisites (Node.js version, Cloudflare auth, secrets set)
- Check firewall/VPN isn't blocking Cloudflare API

Good luck! 🚀

# Phase 17.0 Deployment — Step-by-Step Live Log

**Date:** 2026-10-03  
**Status:** DEPLOYING  
**Your role:** Execute commands, report output

---

## Step 1: Create D1 Database

**What to do:**
```bash
cd factory/intake/worker
wrangler d1 create dark-factory-intake
```

**Expected output:**
```
✓ Created new D1 database dark-factory-intake
  Database ID: abc123def456...
```

**After you run it:**
- Paste the full output here
- The `database_id` line is crucial — we need that value

---

## Step 2: Update wrangler.toml

Once you have the database_id, edit `factory/intake/worker/wrangler.toml`:

Find these lines:
```toml
[[d1_databases]]
binding = "DB"
database_name = "dark-factory-intake"
database_id = ""
```

Replace with your actual database_id:
```toml
[[d1_databases]]
binding = "DB"
database_name = "dark-factory-intake"
database_id = "YOUR_DATABASE_ID_HERE"
```

Also update the production environment section:
```toml
[env.production.d1_databases]
binding = "DB"
database_name = "dark-factory-intake"
database_id = "YOUR_DATABASE_ID_HERE"
```

Then run:
```bash
git add factory/intake/worker/wrangler.toml
git commit -m "config: D1 database_id configured"
```

---

## Step 3: Add Cloudflare Secrets

Go to Cloudflare Dashboard → Workers & Pages → dark-factory-intake (or create the project)

Look for **Settings** → **Secrets**

Add two secrets:

1. **GEMINI_API_KEY**
   - Paste your Gemini API key value

2. **GITHUB_REPO_CREATE_TOKEN**
   - Paste your GitHub fine-grained PAT value

✅ Confirm both are added (you should see them listed)

---

## Step 4: Deploy Worker

Run:
```bash
cd factory/intake/worker
npm install
wrangler deploy --env production
```

**Expected output:**
```
✓ Uploaded dark-factory-intake
✓ Published to https://dark-factory-intake.abc123xyz.workers.dev
```

**Save the Worker URL** — you'll need it for the next step.

---

## What happens next?

Once you've completed these 4 steps, reply with:
1. D1 database_id
2. Confirmation secrets were added
3. Worker deployment output (URL)

Then we'll move to Step 5 (apply DB schema) + Step 6 (deploy Pages).

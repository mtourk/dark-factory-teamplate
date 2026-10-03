# Phase 17.0 Status — Multi-Channel Intake

**Status:** ✅ COMPLETE — Ready for Deployment  
**Build Date:** 2026-10-03  
**Lines of Code:** ~4500 (Python, TypeScript, JavaScript, SQL, HTML, CSS)  
**Components:** Worker + Pages + D1 + Python modules

---

## What's Ready

- ✅ **Cloudflare Worker** (TypeScript): full backend with 9 REST endpoints
- ✅ **Cloudflare Pages** (HTML/CSS/JS): interactive frontend UI
- ✅ **D1 Database** (SQLite): schema + queries for conversations/messages/pending profiles
- ✅ **Python Modules**: channel adapter interface + local sync utility
- ✅ **Documentation**: README (2500+ words) + deployment guide + ADRs
- ✅ **Security Model**: secrets held only in Cloudflare, never exposed to browser/local

---

## Next: You Need To Do

1. **Prepare secrets** (Gemini API key + GitHub PAT) — see PHASE_17_0_DEPLOYMENT.md
2. **Deploy Worker** — `wrangler deploy --env production`
3. **Deploy Pages** — `wrangler pages deploy`
4. **Test end-to-end** — voice/text discovery → file issue → check GitHub
5. **Test local sync** — `python -m factory.intake.local_sync`

**Estimated time:** 30–45 minutes

---

## Files to Read (in order)

1. **PHASE_17_0_DEPLOYMENT.md** — Step-by-step deployment guide
2. **factory/intake/README.md** — Architecture & API docs
3. **PHASE_17_0_BUILD_COMPLETE.md** — What was built, decisions, next steps
4. **docs/decisions/ADR-006.md** — GitHub token custody decision

---

## Key URLs (After Deployment)

- **Worker:** `https://dark-factory-intake.{your-subdomain}.workers.dev`
- **Pages:** `https://dark-factory-intake.pages.dev` (or your custom domain)
- **GitHub Repos:** Auto-created at `https://github.com/YOUR_ORG/{project-name}`

---

## Integration Points (Future)

- **Phase 4:** Add `LocalProfileSync.sync_all()` to polling loop
- **Phase 17.1:** Telegram adapter (reuse Worker + D1)
- **Phase 17.2:** Email adapter (reuse Worker + D1)
- **Phase 17.3:** WhatsApp adapter (reuse Worker + D1)

---

## Known Limitations (17.0)

- Gemini Live WebSocket is simulated (structure ready, real integration TBD)
- Single-user (no login/auth; use Cloudflare Access to restrict if needed)
- No dashboard (coming later)
- No GitHub App support (PAT only)

---

## Questions Before Deploying?

- **Should I use a custom domain?** (e.g., `intake.mtourk.com` instead of `pages.dev`)
- **Should I restrict access?** (via Cloudflare Access, or just leave public?)
- **Should I test locally first?** (can run Pages + Worker locally with `wrangler dev`)

Ready to go live when you are.

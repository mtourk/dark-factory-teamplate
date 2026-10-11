# AI Platform Read-Only Audit — 2026-10-11

**Scope:** repository configuration and public documentation only.
**Mode:** read-only. No production credentials used; no DNS, Cloudflare, Oracle Cloud, Docker, database, or deployment changes made.
**Important limitation:** this document does not establish the live health or configuration of `llm.mtourk.com`, `monitor.mtourk.com`, `factory.mtourk.com`, or any Oracle Cloud VM. The current tool session has no connected Cloudflare/OCI control-plane action available, and public URL retrieval did not return usable page content. Treat live service state as **unverified**, not as confirmed down.

## Executive summary

The next priority is to stabilize the shared AI Platform and OmniRoute independently of Feature Factory. Static repository evidence confirms the existing Feature Factory Worker configuration still contains legacy Ollama references and a placeholder Cloudflare Access audience value. These are repository-state findings, not proof of what is currently deployed.

OmniRoute's public documentation describes an OpenAI-compatible API, API-key controls, request logs, usage tracking, and provider routing/fallback features. These capabilities should be verified against the exact deployed version and settings before building duplicate platform services around them.

## Findings

| ID | Area | Evidence observed | Status | Impact / next action |
|---|---|---|---|---|
| AUD-01 | Product boundary | ADR-009 and the AI Platform master plan define OmniRoute as the shared LLM gateway and Feature Factory as one independent client. | Merged in PR #2 on 2026-10-11 | Preserve this boundary in all later implementation work. |
| AUD-02 | Factory Worker config | `factory/intake/worker/wrangler.toml` on `main` still sets `OLLAMA_URL=https://ollama.mtourk.com` and an `CLOUDFLARE_ACCESS_AUD` placeholder beginning with `TODO`. | Verified in repository; deployed state unverified | Do not migrate or deploy this Worker until Access configuration and runtime settings are verified. Remove legacy Ollama dependency only in a later, reviewed code change. |
| AUD-03 | Factory auth | `factory/intake/worker/src/index.ts` uses a list of routes requiring Cloudflare Access JWT verification, with selected GET endpoints deliberately public. | Verified in repository; correctness/live Access policy unverified | Audit every route and ensure public routes are explicitly allow-listed and safe; test preflight, public intake, and protected management endpoints. |
| AUD-04 | OmniRoute capabilities | Public OmniRoute documentation describes API-key management, request logs, usage/cost analytics, provider/model routing, and media-related endpoints/features. | Documented by upstream project; exact deployment version/config unverified | Inventory the deployed version and built-in capabilities first; prefer built-in functions over duplicate routing/analytics services. |
| AUD-05 | Free-only spend guard | No evidence from this read-only repository review proves that the live OmniRoute instance restricts every client to free-eligible routes or blocks paid fallback. | Unverified | Treat FREE_ONLY as a required acceptance test, not an assumed existing capability. Determine whether OmniRoute policies can enforce it; add an external guard only if needed. |
| AUD-06 | Domain reachability | A public page fetch for the three known hostnames did not return usable page content in this audit session. | Inconclusive | This is not proof of downtime: Access, browser-only UI, networking, or the retrieval tool may prevent access. Verify from the actual deployment/control plane. |
| AUD-07 | Cloudflare / Oracle Cloud | No connected Cloudflare or Oracle Cloud management action was available in this audit session. | Blocked for live verification | User must provide an authorized read-only route (e.g. connect the relevant account integration or share sanitized screenshots/exports). Do not request or paste secrets into chat or GitHub. |
| AUD-08 | Monitoring | The existing Factory monitor is Ollama-centric and should not be treated as the shared AI Platform observability system. | Previously identified in repository review; live state unverified | First inventory OmniRoute's own logs/usage telemetry, then design a small platform-level correlation layer only for gaps. |
| AUD-09 | Cloudflare Preview build | User-provided build log from 2026-10-11 14:37 UTC shows Cloudflare ran `pip install .` at repository root; Hatchling then failed because root `pyproject.toml` declares `readme = "README.md"`, but no root `README.md` exists in the repository at the time of the failed build. The actual Worker package is under `factory/intake/worker/` and has its own `package.json` and `wrangler.toml`. | Root cause of the reported build failure verified from log + repository files; Cloudflare project settings themselves not inspected | This appears to be a Worker build-root/autodetection mismatch, not a failure in PR #2's documentation. Inspect the Cloudflare Workers build configuration and set the project/root directory to `factory/intake/worker` (or otherwise configure the intended Worker build explicitly), then rerun Preview. Do not add a dummy root README merely to make the unintended Python package install proceed. |
| AUD-10 | Client API contract | Drafted `docs/platform/AI-PLATFORM-CLIENT-CONTRACT-v0.1.md` with candidate request shape, auth/isolation requirements, FREE_ONLY policy, error handling, telemetry and acceptance tests. Exact deployed paths and enforcement remain unverified. | Draft documented; not production-verified | Use this as a reviewable proposal. Verify it against the deployed OmniRoute version and settings before adopting it or integrating any client. |

## Cloudflare Preview build follow-up

The failed Preview build is explained by the supplied log: Cloudflare's build environment selected Python packaging at the repository root and invoked `pip install .`. Root `pyproject.toml` declares `readme = "README.md"`, but a root `README.md` was absent from the repository at the time of the failed build. Meanwhile, the Cloudflare Worker has its own `package.json` and `wrangler.toml` in `factory/intake/worker/`.

**Recommended remediation (not performed by this audit):** inspect the Cloudflare Workers Builds settings for this project and point its root directory/build configuration at `factory/intake/worker`, using the repository's intended Worker build/deploy setup. Then rerun the Preview build. Do not create a placeholder root README just to suppress this error; that would let the wrong root-level Python install proceed without proving the Worker is being built correctly. This diagnosis is based on the provided log and repository files; the Cloudflare dashboard configuration has not been inspected, and no configuration or deployment was changed.

## Platform stabilization gates

Do not connect production Feature Factory traffic until evidence exists for all applicable gates:

1. **Identity and access:** dashboard/admin access is protected; client API keys are required for proxy endpoints; keys can be scoped/revoked; browser code does not contain server credentials.
2. **Route and spend policy:** a known list of allowed free-tier routes/models exists; paid routes and paid fallback are explicitly blocked unless the owner opts in; test requests confirm the behavior.
3. **Health and reliability:** document the actual deployment version, readiness endpoint, restart behavior, storage persistence, backups, timeout limits, retry/fallback behavior, and recovery after upstream rate limits.
4. **Telemetry:** request logs show application/client identity, model/route when available, latency, status, usage, and correlation ID. Prompt/response visibility is authenticated, access-controlled, redacted, and retention-limited. Never store private chain-of-thought or secrets.
5. **Independent client test:** a minimal client unrelated to Feature Factory can call the shared API contract using a dedicated key.
6. **Rollback:** exact deployed image/version/digest, configuration backup, data backup, and tested rollback instructions are documented before any production change.

## Evidence required to complete the live audit

Collect sanitized evidence (never secrets or full API keys):

- OCI: VM state, region/shape, attached storage and backups, security-list/NSG ingress summary, and where the service is actually running.
- OmniRoute: version/image tag or digest, base URL, API authentication mode, whether `REQUIRE_API_KEY` is enabled, health/readiness output, configured route/model names, and redacted settings relevant to fallback.
- Spend: evidence that free-only routes are enforced and a paid route cannot be selected by fallback; use a safe test key and a non-production test where possible.
- Cloudflare: Access application/policy summary and DNS/proxy status for the relevant hostnames; never export token values.
- Observability: sample redacted request log with status, model/route, latency, usage, and client attribution.
- Operations: restart/backup/rollback procedure and whether the persistent data directory survives container replacement.

## Next action

The first draft of the versioned client contract is now at `docs/platform/AI-PLATFORM-CLIENT-CONTRACT-v0.1.md`. Review and verify it against the actual deployed OmniRoute API before implementation. Complete the read-only live audit before implementing a new proxy, duplicating OmniRoute dashboards, changing Worker authentication, creating/rotating secrets, or deploying. Cloudflare/OCI control-plane verification remains blocked in this tool session; the reported Preview build still needs a root-directory/build-configuration check and rerun. In parallel, contract tests may be developed against a local mock/staging endpoint, clearly labelled as unverified against production.


## Post-audit deployment evidence — 2026-10-11

After the initial audit was written, the owner supplied a Cloudflare build/deploy log showing a successful deployment of the Worker from the repository's `main` branch.

- Worker name: `dark-factory-teamplate`
- Worker URL reported by Wrangler: `https://dark-factory-teamplate.mohammad-tourk.workers.dev`
- Deployment version ID: `46914773-0485-4444-9d88-aa620e51529a`
- D1 binding reported during deployment: `DB` → `dark-factory-intake` (database ID `ffdfcde8-d68d-48b6-9436-2b12b5245968`)
- Result: Wrangler reported deployment success.

This confirms that a deployment completed; it does **not** by itself verify the live Access application/policy, the placeholder Access audience value, or the security and behavior of every Worker route. Those items remain deferred for later review, per the owner's current priority. Do not interpret the deployment log as evidence that the shared AI Platform API contract has been validated against OmniRoute.

The earlier Cloudflare Preview build issue is separate: the supplied successful deploy log shows a Worker deployment, but does not establish that the PR's Preview build settings are correctly configured. The Worker package is under `factory/intake/worker/`; inspect the Cloudflare Builds root/build configuration and rerun Preview when convenient. Do not add a dummy root README merely to hide an incorrect root-level Python package install.

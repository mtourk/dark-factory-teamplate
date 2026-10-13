# Feature Factory → AI Platform text migration

## Scope

The text discovery endpoint is being changed to call the shared AI Platform at `https://llm.mtourk.com` through the OpenAI-compatible chat-completions contract. Gemini Live remains the voice-token provider for this phase.

## Required Worker configuration before Preview/runtime testing

Configure these values in the Worker environment using Cloudflare's secret/variable settings. Do not commit or share the key value.

| Setting | Type | Requirement |
|---|---|---|
| `AI_PLATFORM_BASE_URL` | Variable | `https://llm.mtourk.com` |
| `AI_PLATFORM_API_KEY` | Secret | Dedicated Feature Factory client key issued by OmniRoute |
| `AI_PLATFORM_MODEL` | Variable | Exact model alias verified on the deployed OmniRoute instance |
| `AI_PLATFORM_ALLOWED_MODELS` | Variable | Comma-separated exact allow-list of aliases verified as free-eligible and permitted for this client |
| `AI_PLATFORM_TIMEOUT_SECONDS` | Variable | Integer from 5 to 120; recommended starting point: `60` |

The application fails closed if any required setting is missing, or if the configured model is not in the client-side allow-list. The allow-list is a secondary safeguard; it does not prove that OmniRoute blocks paid routes or paid fallback.

## Monitor integration

- Apply `factory/intake/worker/migrations/0001_ai_requests.sql` to the existing `dark-factory-intake` D1 database before deploying the Worker.
- The migration creates a separate `ai_requests` table and intentionally leaves historical `ollama_requests` rows untouched.
- The text-response handler records the full prompt message list, requested model, response/error, timing, and OmniRoute response telemetry when present.
- Monitor uses the new `GET /ai/status` and `GET /ai/history` endpoints. The old `/ollama/*` endpoints remain available for historical compatibility.
- OmniRoute response headers are the source of truth for actual provider/model, token counts, reported cost, latency, cache hit, fallback attempts, request ID, and gateway version. Fields remain blank when the gateway does not provide them.
- Request history contains full prompts and responses. The Worker now requires a verified Cloudflare Access JWT for `/ai/status`, `/ai/history`, `/ollama/status`, and `/ollama/history`; only `/version` remains public among the health/monitoring endpoints.
- **Hostname blocker to resolve before testing the browser UI:** both `factory/intake/web/app.js` and `factory/monitor/web/app.js` currently call `https://dark-factory-intake.mohammad-tourk.workers.dev` directly. That hostname is not automatically protected just because `monitor.mtourk.com` has an Access application. Create/verify a custom API hostname routed to this Worker and protected by Cloudflare Access, then update both frontends to call that hostname. Do not invent a hostname or switch back to public monitoring endpoints as a workaround.
- Configure Cloudflare Access for `monitor.mtourk.com` and the custom API hostname used by browser requests. Confirm the Access Application AUD and team domain match the Worker variables. CORS alone is not access control.
- Until that Access configuration and frontend hostname change are complete, Monitor requests to protected history/status endpoints are expected to fail; a `401` is intentional fail-closed behavior.

## Behavior

- Text discovery uses only the AI Platform adapter.
- There is no fallback to Gemini, Ollama, or a provider-direct API for text.
- The adapter makes one request and does not retry automatically.
- Upstream error bodies and authorization values are not returned to the browser.
- Gemini Live token minting is unchanged and still requires `GEMINI_API_KEY`.
- The legacy `/ollama/status` and `/ollama/history` monitoring routes are not removed in this migration.

## Verification gate — not yet production-approved

1. Verify the exact deployed OmniRoute version, chat-completions path, Bearer-key authentication, and model alias.
2. Verify server-side OmniRoute policy rejects paid-only routes and disables paid fallback for the dedicated client key.
3. Create/verify a custom API hostname routed to this Worker and protected by Cloudflare Access; update both frontend `WORKER_URL` constants to it. Configure Access for Monitor and the API hostname, verify the Access AUD/team-domain values, and confirm unauthenticated calls to all four monitoring endpoints return `401`.
4. Apply the D1 migration in a controlled step, then set the five Worker settings above in a non-production/Preview environment. Never paste the secret into GitHub, chat, or build logs.
5. Run Worker CI and the unit tests, including the OmniRoute telemetry-header assertions.
6. Test a valid request and inspect OmniRoute's request/usage records to confirm the actual route was free.
7. Test a disallowed model, missing/invalid key, quota exhaustion, timeout, malformed response, and upstream 5xx.
8. Only after these checks, review rollback and explicitly approve a production deployment.

A passing local mock test or GitHub build is not evidence that the deployed OmniRoute route is free or that its live configuration enforces the policy.
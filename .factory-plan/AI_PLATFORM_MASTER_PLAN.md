# AI Platform Master Plan — OmniRoute-centered shared service

**Status:** Initial workstream definition; read-only audit must precede implementation.
**Decision authority:** docs/decisions/ADR-009-ai-platform-boundary.md
**Related:** docs/decisions/ADR-008-cloud-first-release.md, .factory-plan/decisions.yml

## 1. Mission and boundary

Build a stable shared AI Platform that can serve multiple independent applications. OmniRoute is the LLM routing gateway, not the entire platform by itself. The Dark/Feature Factory is one client, not the platform owner.

```text
                  Independent client applications
          ┌────────────────┬─────────────────┬─────────────────┐
          │ Feature Factory│ Translation app │ Image/media app │
          └────────┬───────┴────────┬────────┴────────┬────────┘
                   └────────────────┼────────────────┘
                                    │ stable client API
                         ┌──────────▼──────────┐
                         │ Shared AI Platform  │
                         │ auth/client policy  │
                         │ cost + route policy │
                         │ telemetry/redaction │
                         │ health + operations │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │      OmniRoute      │
                         │ external LLM router │
                         └──────────┬──────────┘
                                    │
                         Eligible configured model providers
```

This diagram is a target boundary, not a claim that these components already exist or are deployed.

## 2. Non-goals for the initial stabilization release

- Do not build the Feature Factory workflow inside the AI Platform.
- Do not modify the OmniRoute repository.
- Do not add a custom quota-intelligence engine or another LLM router unless an audit proves OmniRoute cannot meet a required capability.
- Do not require a local laptop, Ollama, or Cloudflare Tunnel.
- Do not allow paid model usage silently. FREE_ONLY is the default until explicitly changed by the owner.
- Do not assume an LLM endpoint is sufficient for arbitrary image conversion/transformation. Image jobs may need separate non-LLM services.
- Do not change DNS, rotate/create secrets, provision infrastructure, apply migrations, or deploy production services during the read-only audit.

## 3. Platform acceptance gates

A gate is not passed merely because a config file or dashboard exists; it needs repeatable evidence.

1. **Inventory:** identify the actual OmniRoute deployment, version, reachable endpoints, authentication boundary, model aliases, configured providers, and existing health/metrics capabilities without exposing secrets.
2. **Client contract:** document a stable API base URL, supported request/response shapes, error semantics, timeouts, streaming behavior if needed, request IDs, and client identity. Keep provider names out of client business logic.
3. **Security:** all non-public routes require authentication; credentials are never embedded in browser code or committed to the repository; least-privilege client credentials and redaction are defined.
4. **Cost and routing policy:** FREE_ONLY default, explicit allow-list of eligible routes/models, bounded retries, no uncontrolled retry storms, and no silent paid fallback.
5. **Failure and recovery:** provider exhaustion, gateway outage, timeout, malformed response, and rate limiting have defined errors and retry rules. Durable client workflows pause safely when no eligible route remains.
6. **Observability:** record client/application ID, request/correlation ID, route/model when available, duration, outcome, retry/failover, and usage metadata when available. Prompt/response visibility is authenticated and redacted. Never log private chain-of-thought.
7. **Operations:** health/readiness checks, alertable failures, configuration validation, rollback procedure, and an evidence-backed deployment checklist.
8. **Client isolation:** a platform test or simple independent sample client can call the service without loading or depending on Factory-specific data models.
9. **Adoption:** only after gates 1–8 are verified should Feature Factory be migrated to the shared contract.

## 4. Workstream backlog

| ID | Work item | Status | Depends on |
|---|---|---|---|
| AI-PLATFORM-01 | Read-only inventory of OmniRoute and related cloud services/configuration | in_progress (live cloud portion blocked) | — |
| AI-PLATFORM-02 | Define API contract, client identity, auth and policy boundaries | draft created; pending endpoint/config verification | AI-PLATFORM-01 |
| AI-PLATFORM-03 | Build reproducible health, security, FREE_ONLY, timeout/retry and failure tests | not_started | AI-PLATFORM-02 |
| AI-PLATFORM-04 | Establish redacted per-client telemetry and operational runbook | not_started | AI-PLATFORM-01, AI-PLATFORM-02 |
| AI-PLATFORM-05 | Verify stable deployment, rollback and recovery without production changes during audit | not_started | AI-PLATFORM-03, AI-PLATFORM-04 |
| AI-PLATFORM-06 | Integrate Feature Factory as a client through the shared contract | not_started | AI-PLATFORM-05 |
| AI-PLATFORM-07 | Add translation and image/multimodal clients based on explicit capability needs | not_started | AI-PLATFORM-05 |

## 5. Immediate next action: read-only audit and contract verification

A draft client contract now exists at `docs/platform/AI-PLATFORM-CLIENT-CONTRACT-v0.1.md`. It is a proposal only; exact deployed endpoint behavior and FREE_ONLY enforcement remain unverified. The live cloud audit remains in progress, with Cloudflare/OCI control-plane verification blocked until an authorized read-only route is available.

Collect evidence for:
- OmniRoute repository/service ownership and current deployment location;
- current API URL, auth mode, version/health endpoints, model aliases/routes (never print secret values);
- upstream provider configuration and whether FREE_ONLY/no-paid-spend is enforceable today;
- timeouts, retry/failover behavior, rate-limit/quota handling;
- request logging, client attribution, prompt/response retention and redaction;
- Cloudflare and Oracle VM roles as they actually exist, without making changes;
- available tests, CI checks, and a safe non-production test path.

Classify each finding as verified, unverified, missing, or blocked. Do not infer live deployment health from repository configuration alone. The audit must not print credentials or copy them into issues, logs, or generated artifacts.

## 6. Relationship to Feature Factory

The existing Feature Factory Worker and its Ollama-centric monitor are Factory-owned components. They are not automatically the shared AI Platform. In a later integration, Factory code should call a small provider-neutral client adapter configured with the platform endpoint and client identity. Its workflow, D1 state, feature backlog, and run monitoring remain Factory concerns; platform-level telemetry can be correlated by request ID and surfaced in Factory UI where appropriate.

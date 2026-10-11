# Cloud-first architecture baseline and migration checklist

**Decision authority:** `docs/decisions/ADR-008-cloud-first-release.md`  
**Effective date:** 2026-10-11  
**Scope:** Documentation and backlog reconciliation only. This does not claim any deployment, DNS change, secret rotation, or runtime implementation has occurred.

## Binding Release 1 baseline

Release 1 runs entirely on cloud infrastructure. The Feature Factory must not depend on the user's Windows laptop, a local Ollama process, or a Cloudflare Tunnel for model inference or core product availability.

- **Cloudflare Workers/Pages:** portal, APIs, authentication boundary, D1 persistence, request/queue state, and suitable edge endpoints.
- **OmniRoute:** existing external LLM routing gateway. The Factory calls it through a provider-neutral adapter. Do not change the OmniRoute repository as part of this work.
- **Oracle Cloud VM:** candidate host for always-on components that cannot or should not run in Workers. Confirm OmniRoute's actual deployment, security, and resource requirements before moving or provisioning anything.
- **LLM providers:** cloud providers only for Release 1. Free-tier-first routing; no silent paid spend. Cloud-to-cloud failover may be used where OmniRoute is configured to support it.
- **Monitoring:** authenticated dashboard for Factory requests and cloud model calls, including outcomes, latency, route/model when known, retries, and redacted visible prompts/responses. Never store private chain-of-thought or unredacted credentials.
- **GitHub:** source of truth for code, plan, review, and release workflow.

## Current hostname intent (not a DNS change)

| Hostname | Intended role | Guardrail |
|---|---|---|
| `factory.mtourk.com` | Feature Factory portal | Keep as the user-facing intake surface |
| `llm.mtourk.com` | OmniRoute API endpoint and/or admin UI | Do not expose an admin UI publicly without authentication; API endpoint and UI may need separate paths or hostnames |
| `monitor.mtourk.com` | Factory and LLM observability | Authenticate; redact secrets before storing/displaying prompts and responses |
| `ollama.mtourk.com` | Retire or repurpose as neutral health/status endpoint later | No local Tunnel dependency; do not change DNS until target is verified |

These are intentions, not verified deployment state. Existing records may remain untouched while architecture and configuration are audited.

## Migration sequence

1. Reconcile plan and decisions; do not implement new features against contradictory local-first instructions.
2. Audit Worker/Pages code, D1 schema, Cloudflare resources, OmniRoute deployment/configuration, Oracle VM availability, and current DNS records using read-only inspection.
3. Define one configurable OmniRoute base URL and credential reference for the Factory Worker; keep provider names out of agent business logic.
4. Define cloud-only retry/failover and FREE_ONLY behavior. If no eligible route remains, persist a paused/retryable run state.
5. Ensure all Factory-originated model calls pass through the observable gateway boundary. Add correlation IDs and structured call events.
6. Update monitoring to read those events from the cloud data store. Redact credentials and secret-like values before persistence and UI display.
7. Implement/verify the BMAD one-question conversation against the same cloud LLM adapter.
8. Add cloud-only integration tests, failure/retry tests, and monitoring redaction tests.
9. Reassess local LLM fallback only after the cloud path is reliable; adding it later must not require changing agent logic.

## Explicit non-goals for this migration

- No edits to the OmniRoute repository.
- No Cloudflare DNS changes or Tunnel activation.
- No new Oracle VM provisioning until read-only audit confirms the required placement.
- No production deploy or schema migration in this documentation change.
- No local Ollama fallback in Release 1.
- No automatic paid-model usage.
- No claim that current hostnames/services are healthy or deployed.

## Source-of-truth reconciliation

This document and ADR-008 override conflicting older plan language that requires local Ollama as the primary engine, prohibits cloud routing, mandates local Tunnel connectivity, or requires local fallback in Release 1. The long-term API-first/provider-neutral design remains valid; implementation details are narrowed for Release 1 to the existing OmniRoute gateway unless an evidence-based decision supersedes this ADR.

Keep these artifacts consistent before implementation resumes: `New_FEATURE_FACTORY_MASTER_PLAN.md`, `.factory-plan/MASTER_IMPLEMENTATION_PLAN.md`, `.factory-plan/decisions.yml`, `.factory-plan/backlog.yml`, `.factory-plan/dependency-graph.yml`, `.factory-plan/implementation-status.yml`, and `.factory-plan/blockers.yml`.

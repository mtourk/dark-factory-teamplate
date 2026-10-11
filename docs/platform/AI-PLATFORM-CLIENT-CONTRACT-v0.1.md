# AI Platform Client Contract — v0.1 (Draft)

**Status:** Proposal for review; not an implementation guarantee.
**Decision authority:** `docs/decisions/ADR-009-ai-platform-boundary.md`
**Related:** `docs/decisions/ADR-008-cloud-first-release.md`, `.factory-plan/AI_PLATFORM_MASTER_PLAN.md`
**Last updated:** 2026-10-11

## 1. Purpose

Define the minimum provider-neutral contract that independent applications can use to call the shared AI Platform. Feature Factory is one client; translation and future media-enabled applications must not depend on Factory-specific schemas or workflows.

This document is a design contract only. It does not claim that every behavior below is currently enforced by the deployed OmniRoute instance. The exact deployed API paths, model aliases, authentication settings, and spend controls must be verified before adoption.

## 2. Boundary and deployment approach

- OmniRoute remains the external LLM routing gateway.
- Prefer its existing OpenAI-compatible API and built-in controls where they meet the contract; do not build a second proxy/router or duplicate dashboards without evidence of a gap.
- Client applications must use a small shared client adapter/configuration convention, not call provider APIs directly.
- The logical platform boundary includes client identity, allowed model/route policy, spend restrictions, safe retries/timeouts, redacted telemetry, and operations.
- Cloud-first is the initial approach. A local LLM fallback is out of scope for the first release.

## 3. Client configuration

Each client should receive configuration through its server-side runtime environment or secret manager:

| Setting | Requirement |
|---|---|
| `AI_PLATFORM_BASE_URL` | HTTPS base URL for the approved platform endpoint; no provider-specific URL in business logic |
| `AI_PLATFORM_API_KEY` | Dedicated, revocable credential for this client; never committed to source or exposed to browser code |
| `AI_PLATFORM_ALLOWED_MODELS` | Optional client-side validation allow-list; server-side enforcement is still required |
| `AI_PLATFORM_TIMEOUT_SECONDS` | Explicit bounded timeout selected for the operation |
| `AI_PLATFORM_ENVIRONMENT` | Environment label such as `dev`, `staging`, or `production`; never use it as an authorization control |

Do not copy keys between applications by default. A leaked or retired client key should be revocable without rotating unrelated clients.

## 4. Request contract

### Initial synchronous text generation

The candidate initial operation is an OpenAI-compatible chat-completions request:

- Method: `POST`
- Candidate path: `/v1/chat/completions`
- Authentication: `Authorization: Bearer <client-key>`
- Content type: `application/json`
- Required inputs: approved `model` alias and `messages`
- Optional inputs: bounded `temperature`, `max_tokens`, and other explicitly supported parameters
- Response: normalized assistant output plus usage metadata when available

**Verification gate:** confirm the deployed OmniRoute version accepts this exact path, authentication header, request shape, and model aliases before marking it supported. Do not infer support from generic OpenAI compatibility claims alone.

### Client metadata

Where the gateway supports safe metadata or headers, clients should send a stable application identifier and a unique request/correlation ID. Use non-secret values such as `X-Client-Application: feature-factory` and `X-Request-ID: <random-id>` only after confirming the gateway accepts/preserves them. Do not invent a custom header dependency before testing it.

## 5. Authentication and isolation

1. All server-to-server requests use HTTPS and a dedicated client credential.
2. No server credential may appear in browser bundles, public configuration, logs, screenshots, issues, or committed files.
3. Credentials must be revocable and scoped as narrowly as the gateway allows.
4. Unauthorized and forbidden requests must fail closed; clients must not retry indefinitely or fall back to an unauthenticated/provider-direct request.
5. Client attribution must be visible in approved telemetry. If OmniRoute cannot associate keys with clients, record this as a platform gap before multi-client production adoption.

## 6. FREE_ONLY spend policy

FREE_ONLY is the default acceptance requirement, not a claim about the current deployment.

- Maintain an explicit allow-list of verified free-eligible model/route aliases.
- Reject unknown or disallowed aliases before sending a request whenever enforcement can be placed at a trusted boundary.
- Disable paid fallback and automatic route substitution unless the owner explicitly approves a different policy.
- Treat provider quota exhaustion, rate limiting, or all-free-routes-unavailable as a clear failure. Do not silently switch to a paid model.
- Verify behavior with a safe test client and inspect the resulting route/usage records. A successful response alone does not prove the route was free.
- Keep provider pricing and free-tier eligibility evidence dated because provider terms and quotas can change.

If OmniRoute cannot enforce this policy for the deployed version, document the gap and design the smallest trusted enforcement layer only after confirming the limitation. Do not build a second router pre-emptively.

## 7. Error and retry semantics

Client adapters should normalize failures into these categories while preserving the upstream status and request ID when safe:

| Category | Expected client behavior |
|---|---|
| Invalid request / unsupported model | Do not retry automatically; surface a sanitized validation error |
| Authentication / authorization failure | Do not retry; alert on repeated failures without logging the key |
| Rate limit / free-tier quota exhausted | Bounded backoff only where retry is appropriate; never switch to a paid route |
| Timeout | Apply a bounded retry policy only for operations safe to retry; use request IDs to aid diagnosis |
| Gateway or provider unavailable | Fail clearly after bounded attempts; do not create retry storms |
| Unknown upstream error | Return a sanitized error and correlation ID; never expose credentials or internal stack traces |

Retries must be bounded, jittered where appropriate, and limited by an overall request deadline. For non-idempotent operations, do not retry unless idempotency behavior is known.

## 8. Streaming and non-text capabilities

- Streaming is not required for v0.1; add it only after confirming end-to-end support and defining disconnect/cancellation behavior.
- Embeddings, image generation, image transformation, speech, and other media operations are separate capabilities. Do not assume chat-completions covers them.
- Each additional capability needs its own request/response schema, allowed-route policy, limits, and tests before a client depends on it.

## 9. Telemetry and privacy

Record only what is needed for operations and cost control:

- client/application ID and correlation ID;
- approved route/model alias, when available;
- timestamp, latency, outcome/status, retry/failover count;
- usage/cost metadata when provided by the gateway.

Never log API keys, authorization headers, or other secrets. Prompt/response capture must be disabled by default unless there is a documented need, access control, redaction, and retention policy. Never collect private chain-of-thought.

## 10. Minimum acceptance tests before production adoption

1. Missing, invalid, and revoked keys fail closed.
2. One approved free route succeeds and its actual route/usage can be inspected.
3. Disallowed and paid-only routes are rejected.
4. Free-route exhaustion does not trigger paid fallback.
5. 429, timeout, malformed response, and 5xx cases produce bounded, sanitized failures.
6. Correlation IDs and client identity appear in approved logs without secrets.
7. A minimal client unrelated to Feature Factory can use the contract.
8. A rollback path and credential-revocation procedure are documented.

Tests may begin against a local mock or staging endpoint, but must be labelled separately from tests against the actual deployed service.

## 11. Open verification items

- Confirm deployed OmniRoute version/image and exact API paths.
- Confirm auth mode, API-key scope/revocation, and client attribution.
- Confirm model aliases and prove FREE_ONLY/no-paid-fallback enforcement.
- Confirm timeouts, retries, streaming support, request IDs, usage fields, and log redaction.
- Confirm the Cloudflare Worker Preview build root is configured for `factory/intake/worker`; the reported failure came from a root-level Python package install and does not prove the Worker build succeeds.

Until these items are verified, this contract remains a proposal and must not be treated as production-ready implementation documentation.

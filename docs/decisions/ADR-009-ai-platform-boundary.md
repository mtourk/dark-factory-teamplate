# ADR-009: Separate the shared AI Platform from the Feature Factory

- **Status:** Accepted
- **Date:** 2026-10-11
- **Related:** ADR-008, D-NEW-005, D-NEW-006, D-NEW-007

## Context

The Dark/Feature Factory is one application that needs AI capabilities. It is not the owner of, or synonymous with, the shared AI Platform. The platform must also support independent future applications such as text translation, image/multimodal workflows, and other LLM-enabled tools.

The immediate priority is to make OmniRoute and the shared platform stable, secure, observable, and cost-controlled before moving Feature Factory traffic onto it. A Factory-specific Worker, database schema, or dashboard must not become the implicit shared platform contract.

## Decision

1. **Two independent products/workstreams.** The AI Platform has its own scope, acceptance criteria, operational boundary, and roadmap. Feature Factory has its own product workflow and consumes the platform as a client.
2. **OmniRoute is the shared routing gateway.** The platform exposes a stable, provider-neutral API contract to client applications and uses the existing external OmniRoute service for LLM routing. Do not modify the OmniRoute repository as part of the Feature Factory repository.
3. **Client applications are independent.** Feature Factory, translation apps, and future applications integrate as separate clients. They must not depend on Factory-specific D1 tables, conversation models, queue semantics, or UI.
4. **Platform responsibilities.** The platform workstream defines and verifies authentication/client access, model and route policy, FREE_ONLY defaults with no silent paid spend, timeouts and bounded retries, request correlation, usage/outcome/latency telemetry, redaction, and health/readiness checks. Place each responsibility at the narrowest correct boundary; do not duplicate capabilities already reliably provided by OmniRoute.
5. **Media capability is explicit.** Text LLM requests, multimodal model requests, and non-LLM image-processing jobs are different capabilities. Do not promise image conversion or image transformation merely because an LLM gateway exists. Add suitable model/service adapters behind explicit contracts when a real use case requires them.
6. **Observability is platform-oriented.** Platform telemetry must be attributable to a client/application and request, and must capture route/model when available, latency, outcome, retry/failover, and safe-to-display prompt/response content where policy permits. Redact secrets and sensitive credentials; never record private chain-of-thought. Prompt/response retention and access must be deliberate and authenticated.
7. **Adoption gate.** Do not migrate Feature Factory production traffic until the shared contract, auth, spend policy, failure behavior, telemetry, and deployment/rollback checks are verified.
8. **No operational changes from this ADR.** It authorizes documentation and planning only. It does not authorize DNS changes, secret creation/rotation, provisioning, schema migrations, or production deployments.

## Initial workstream order

1. Inventory and read-only audit of OmniRoute and existing AI-related services/configuration.
2. Define the shared platform API contract, client identity model, policy boundaries, and what OmniRoute already provides.
3. Establish reproducible health, routing, auth, spend-guard, failure/recovery, and observability checks.
4. Stabilize and verify the platform before connecting Feature Factory.
5. Integrate Feature Factory through the same client contract; preserve its own business workflow and data model.
6. Add translation, image/multimodal, and other apps as independent clients only when their required capabilities are identified.

## Acceptance checks

- A diagram and API contract distinguish platform infrastructure from client applications.
- Platform requirements can be tested without running the Feature Factory workflow.
- A client can be added without changing Factory-specific tables or code paths.
- FREE_ONLY/no-silent-paid behavior and failure/recovery behavior are observable and testable.
- Telemetry identifies client and request without exposing credentials or private chain-of-thought.
- The OmniRoute dependency is treated as external and is not modified by this repository's changes.

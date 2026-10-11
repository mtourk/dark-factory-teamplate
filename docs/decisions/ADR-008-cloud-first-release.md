# ADR-008: Cloud-first release; local LLM deferred

- **Status:** Accepted for Release 1; local fallback remains a future option
- **Date:** 2026-10-11
- **Related:** D-NEW-004, D-NEW-005, FF-P00-03

## Decision

1. Release 1 runs cloud-only. No local laptop, Ollama process, or Cloudflare Tunnel is required.
2. Use the existing external OmniRoute service as the provider-routing boundary. Feature Factory agents use a provider-neutral adapter; do not modify the OmniRoute repository.
3. Cloud-to-cloud failover is permitted only when configured and within policy. FREE_ONLY is the default; no silent paid usage.
4. If no eligible cloud route remains, preserve the run and pause/retry it safely. Do not fall back to local Ollama in Release 1.
5. Local LLM remains a future optional provider behind the same adapter; it is deferred, not removed from the long-term architecture.
6. Do not add an in-process LiteLLM SDK or custom quota-intelligence layer in Release 1 unless an evidenced requirement shows OmniRoute cannot meet the need.
7. Monitor Factory-originated cloud model calls, outcomes, latency, route/model when available, retries, and visible prompt/response data after secret redaction. Never store private chain-of-thought.
8. Cloudflare remains the portal/API/D1 layer. Oracle Cloud VM is a candidate for always-on components after read-only audit; no provisioning or DNS changes are authorized by this decision.
9. Hostname intent remains provisional: factory.mtourk.com for the portal, llm.mtourk.com for OmniRoute API/admin UI only with appropriate authentication, monitor.mtourk.com for authenticated observability, and ollama.mtourk.com may later be retired or repurposed as a neutral status hostname. Do not change DNS as part of this decision.

## Consequences

This supersedes D-NEW-004's local-only execution and narrows D-NEW-005 for Release 1: OmniRoute is the external gateway, local fallback is deferred, and durable pause/retry replaces fallback to a local model when all cloud routes fail. The long-term API-first/provider-neutral direction remains.

## Acceptance checks

- The main plan, decision register, backlog, dependency graph, and status file agree that Release 1 is cloud-only.
- No Release 1 task requires a local Ollama tunnel.
- OmniRoute remains an external dependency and is not modified.
- Paid model usage remains opt-in.
- Cloud-route failure leaves a durable, visible, resumable state.

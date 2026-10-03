# Decisions and Architecture Decision Records (ADRs)

**Project:** dark-factory-teamplate (FactoryFlow orchestrator)  
**Authority:** DARK_FACTORY_BUILD_PROMPT.md §6  
**Index updated:** 2026-10-03 during Phase 1

## Purpose

This file indexes all strategic, architectural, and operational decisions made during factory implementation. Each decision is recorded in a separate ADR file following the template below. Decisions are immutable records; changes require a new ADR that supersedes the prior one.

**Policy:**
- Strategic decisions and business ambiguity escalations are logged here
- Technical decisions covered by the master plan are implemented without separate ADR (execute Phase N, no vote)
- All ADRs link to evidence: master plan section, threat model, phase deliverable, or issue discussion
- ADRs block auto-merge if they modify protected paths or authority
- Raw conversations are never used as decisions; only approved ADRs count

---

## ADR Template

```markdown
# ADR-NNN: [Title]

## Date
YYYY-MM-DD

## Status
- PROPOSED — awaiting decision
- APPROVED — decision made
- SUPERSEDED by ADR-NNN — replaced
- IMPLEMENTED — code deployed

## Decision
[Concise summary of what was decided and why]

## Context
[Background: master plan section, threat model concern, blocked issue, etc.]

## Options Considered
1. [Option A] — [trade-offs]
2. [Option B] — [trade-offs]
3. [Option C] — [trade-offs]

## Rationale
[Why this option was chosen, evidence, impact]

## Consequences
[What changes as a result; implementation phase; risks accepted]

## Evidence
- Linked issue: [GitHub URL or issue title]
- Master plan: [section reference]
- Threat model: [threat category if applicable]
- Phase: [which phase implements this decision]

## Author
[Who made the decision and when; e.g., autonomous Phase 7 synthesis, user input, etc.]
```

---

## Current ADRs

### Phase 1 Decisions

#### ADR-001: Single Model (qwen2.5-coder:32b) for All Roles

**Status:** APPROVED (user decision, Phase 1)

**Decision:**
Use one Ollama model (qwen2.5-coder:32b, Q4 quantization) for all factory roles (router, analyst, builder, reviewer) instead of multi-model setup (§8 baseline: 7b/14b/32b/30b variants).

**Context:**
- Master plan §1 specifies "Do not assume the largest model is operationally best"
- Plan §8 recommends benchmark candidates: 7b (router), 14b (analyst/builder), 32b (candidate), 30b (reviewer)
- User's hardware: 32 GB RAM, 0 dedicated VRAM, sequential inference
- Qwen2.5-coder:32b estimated ~18–20 GB RAM (Q4 quantization)
- Trade-off: operational simplicity vs. specialized role performance

**Options Considered:**
1. Multi-model (7b+14b+32b+30b) — better specialized performance, complex switching, more memory churn
2. Single 32b model (chosen) — simpler config, all roles use same context, ~18–20 GB RAM
3. Single 14b model — faster inference, lower capability, weaker for reviewer

**Rationale:**
- Single model avoids complexity of model-switching logic (Phase 6)
- 32b is capable enough for all roles while fitting in RAM with margin
- Simpler benchmarking story (one model to tune, one baseline to record)
- User expressed preference for "biggest possible option that fits" (simplicity over optimization)

**Consequences:**
- Phase 6 Model Gateway: all roles alias to qwen2.5-coder:32b
- Phase 3: `pyproject.toml` lists one model dependency (Ollama pull target)
- Phase 8: OPA policy treats all roles with same resource constraints
- Benchmarking: measure this single model's latency, memory, capability across all tasks
- Risk: if 32b is too slow for high-volume issue triage, fallback to 14b documented in Phase 6

**Evidence:**
- User input: "I want only 1 model to run the entire system, the biggest possible option"
- Master plan §8: benchmark candidates with tradeoffs noted
- Phase 6 deliverable: benchmark harness records performance
- Hardware: 32 GB RAM, 0 VRAM (constraint)

**Author:**
User decision during Phase 1 prerequisite questions (2026-10-03)

---

#### ADR-002: Target Repository is Separate Project (investisor)

**Status:** SUPERSEDED by ADR-004 (was: APPROVED, user decision, Phase 1)

**Decision:**
Dark Factory orchestrator repo (dark-factory-teamplate) implements the factory framework. The first workload is the separate investisor repository (https://github.com/mtourk/investisor). Factory does not manage itself initially; it manages investisor starting Phase 16 (end-to-end acceptance).

**Context:**
- Master plan §5 specifies "GitHub Issues as primary backlog"
- User choice in prerequisite questions: "Factory manages another project"
- User provided investisor repo URL

**Options Considered:**
1. Factory manages itself (meta: issues in dark-factory-teamplate drive factory development) — intentional loop, forces real adoption proof, complex governance
2. Factory manages separate project (chosen) — clear separation of concerns, factory code doesn't interfere with workload
3. Factory is a library only (no autonomous loop) — easier to test, but defeats purpose

**Rationale:**
- Separation of concerns: factory codebase remains stable while investisor workload drives real acceptance tests
- Clear traceability: investisor issues become the true acceptance criteria (Phase 16)
- Easier to debug: factory problems don't hide in investisor issues
- Can scale to multiple projects later (factory framework reused)

**Consequences:**
- Phase 4: Backlog scheduler points to investisor repo (configured URL)
- Phase 12: Branch protection and labels created on investisor, not dark-factory-teamplate
- Phase 13: Cloudflare deploy targets investisor
- Phase 16: End-to-end loop closes investisor issues, selects next investisor item
- Risk: Investisor repo must be ready with issues labeled `factory:ready` before Phase 16

**Evidence:**
- User choice: "Factory manages another project"
- Investisor URL provided: https://github.com/mtourk/investisor
- Master plan §4 (FactoryFlow as orchestrator, not integrated with target)

**Author:**
User decision during Phase 1 prerequisite questions (2026-10-03)

---

#### ADR-003: Cloudflare Secrets Stored Only in GitHub Actions

**Status:** APPROVED (user decision, Phase 1)

**Decision:**
Cloudflare Account ID and API Token will be stored only in GitHub Actions repository secrets (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN). These credentials will never be stored locally in `.env`, Windows Credential Manager, or any file on the developer machine.

**Context:**
- Master plan §6 specifies "secrets never exposed to models"
- Master plan §15 "GitHub Actions owns Cloudflare secrets. Models and local processes may not read them."
- Phase 13 (Cloudflare preview/production) requires secrets for wrangler deploy
- User choice: "GitHub Actions + env vars only"
- Security concern: local storage increases exfiltration risk

**Options Considered:**
1. Local `.env` file — simple, but committed risk if gitignore fails
2. Windows Credential Manager — native Windows security, but local access risk
3. GitHub Actions secrets only (chosen) — strongest isolation, secrets never touch dev machine

**Rationale:**
- GitHub Actions provides native secret management with OIDC token exchange
- Secrets are not available to local model or manual process
- Reduces local credential exposure attack surface
- Aligns with master plan §15 (secrets management policy)

**Consequences:**
- Phase 3: Factory code contains no credential logic (GitHub Actions inject via env)
- Phase 13: GitHub workflow receives secrets as env vars during deploy step
- Phase 13: Verification: confirm secrets not logged by GitHub Actions (e.g., with `##[debug]` blocks)
- Local testing: Phase 13 can be tested via preview, but production deploy requires GitHub Actions
- Risk: Lost GitHub credentials or token exposure would require rotation (mitigated by GitHub's token rotation UI)

**Evidence:**
- Master plan §15: "GitHub Actions owns Cloudflare secrets"
- Master plan §6.6: secrets storage policy
- User choice: "GitHub Actions + env vars only"
- Phase 13 deliverable: `.github/workflows/deploy.yml`

**Author:**
User decision during Phase 1 prerequisite questions (2026-10-03)

---

### Post-Phase-13 Decisions

#### ADR-004: Target Repository is Configurable via `profiles/` (Supersedes ADR-002)

**Status:** APPROVED (user decision) — SUPERSEDES ADR-002

**Decision:**
The factory is a reusable template/engine, built once and run against many future projects. There is no single "target repository." Each managed project is a *profile* (`profiles/<name>.yml` — see `factory/profiles.py`), naming a target repo and an optional Cloudflare project reference. Profiles hold no secrets; credentials for a profile's target repo live only as GitHub Actions repository secrets on that repo (ADR-003 still holds, now per-profile instead of singular).

**Context:**
- ADR-002 named investisor as "the" target repository for the factory's first (and, as written, only) workload.
- User correction (two escalating messages): "investisor repo should not be a static part of this dark factory, it was given as an example... this project is allowed to be configurable"; then: "my goal is to make this factory as a template, and i will have multiple project[s]... the goal is to make this factory once, and then reuse it with every future project."
- Master plan §17 (Repository structure) already names `profiles` as a top-level directory the finished factory repo must contain — this ADR formalizes what the master plan anticipated.

**Options Considered:**
1. Keep investisor hardcoded (ADR-002 as written) — rejected by user, contradicts "built once, reused" goal.
2. One `FactoryConfig` object accepting any single repo per run (first fix attempted) — accepts arbitrary repos, but still models only one project at a time with no durable multi-project registry; insufficient for "I will have multiple projects."
3. `profiles/` directory, one file per managed project, selected via `--profile`/`FACTORY_PROFILE`/implicit-single-profile resolution (chosen) — matches master plan §17, supports N concurrent/future projects without touching orchestration code.

**Rationale:**
- Existing adapters (`GitHubAdapter(owner, repo)`, `CloudflareAdapter`) were already built repo-agnostic; only a profile-selection layer was missing.
- Profiles are secret-free and safe to commit, keeping the ADR-003 secret boundary intact per project.

**Consequences:**
- `factory/config/` (a colliding package from the first fix attempt) removed; `factory/profiles.py` is the one profile model.
- `factory/cli.py` gained a global `--profile` option and a `profile create|list|show` command group.
- `.factory/workflows/deploy.yml` and `factory/deploy/target_repo_setup.py` no longer reference investisor as an example target.
- IMPLEMENTATION_CHECKLIST.md's "Target Project" line updated to point here instead of naming investisor.
- Phase 16 (end-to-end acceptance) still needs *a* profile to run against — investisor remains a perfectly valid first profile, it is simply no longer special-cased in code.

**Evidence:**
- User: "investisor repo should not be a static part of this dark factory, it was given as an example"
- User: "my goal is to make this factory as a template... reuse it with every future project"
- Master plan §17: repository structure names `profiles` explicitly
- Phase: implemented in the Phase 13 redesign commit ("Phase 13 Redesign: profiles/ as the reusable multi-project mechanism")

**Author:**
User decision, post-Phase-13 course correction (2026-10-03)

---

#### ADR-005: Gemini Live as a Scoped, Discovery-Only Exception to ADR-001

**Status:** APPROVED (user decision)

**Decision:**
Phase 17 (Multi-Channel Intake, extension) uses Google's Gemini Live API for the pre-filing requirement-discovery conversation only — a live, voice-capable, back-and-forth clarification dialogue that runs *before* a GitHub Issue exists. This is an explicit, narrow exception to ADR-001 ("one local model for all factory roles"): once the conversation produces a requirement draft and an Issue is filed, every downstream phase (BMAD critics, implementation, review, deployment) remains exactly as local-only as ADR-001 requires. Gemini is never used for any role inside the existing pipeline.

The Gemini API key is held as a Cloudflare Worker secret. The Worker's only responsibility is minting short-lived ephemeral Gemini Live session tokens on request; the long-lived key never reaches the browser, never reaches a local file, and is never logged — the same custody discipline ADR-003 established for Cloudflare/GitHub credentials, applied to a new secret type via the mechanism already trusted in this project (a managed platform secret store, not local storage).

**Context:**
- User wants multi-channel requirement intake (web, Telegram, email, WhatsApp) with full conversational clarification before anything is filed, and specifically wants voice input to be a live conversation (not record-then-transcribe), using Gemini Live, for which the user already holds an API key.
- ADR-001 established local-only inference as a project-wide default; introducing any cloud model is a precedent change and was raised explicitly for user confirmation rather than assumed.
- Clarification strategy chosen by user: full chat/voice back-and-forth (as opposed to filing immediately and relying solely on Phase 7's existing decision-required escalation).

**Options Considered:**
1. Local-only discovery (local Whisper for transcription + the local qwen2.5-coder model for clarifying dialogue) — preserves ADR-001 with zero exceptions, but no live voice conversation and weaker conversational quality on a non-GPU laptop; rejected by user in favor of Gemini Live.
2. Gemini Live for discovery only (chosen) — live, natural voice clarification; cloud exception scoped tightly to the one stage that happens before any Issue/code exists.
3. Gemini (or another cloud model) used more broadly inside the pipeline — rejected; would contradict ADR-001's rationale (secrets/data exposure, hardware-forced locality) for no corresponding benefit, since discovery is the only stage that benefits from live voice.
4. Key custody: embed key in client-side JS — rejected, violates the project's standing secret-custody rule (ADR-003) the moment the page is reachable by anything other than literally only the owner's own browser process.
5. Key custody: full audio relay through the local backend — viable, simpler trust story, but adds a local relay hop; not chosen because the user specified Cloudflare-backed custody.
6. Key custody: Cloudflare Worker mints short-lived ephemeral tokens, key stored as a Worker secret (chosen) — browser streams audio directly to Gemini using the ephemeral token; the long-lived key never leaves Cloudflare's secret store.

**Rationale:**
- Scoping the exception to "pre-filing discovery only" keeps ADR-001's actual guarantee intact where it matters: no business logic, code, or review decision is ever made by anything other than the local model.
- Phase 7's decision-required escalation and the Gemini discovery conversation operate at different moments (before vs. after Issue filing) and are complementary, not duplicative — Phase 17 does not build a second in-flight-ambiguity engine.
- Cloudflare Worker secret custody reuses a mechanism this project already trusts (ADR-003's platform-secret-store pattern) instead of inventing a new one for Gemini specifically.

**Consequences:**
- Phase 17 (IMPLEMENTATION_CHECKLIST.md) deliverables include a Cloudflare Worker (token minter) as part of the web intake channel.
- The secret-leak test pattern established for Cloudflare/GitHub tokens (`redact_for_logging`, `assert_adapter_holds_no_secret`) must be extended to cover the Gemini key when Phase 17 is implemented.
- If Gemini Live's ephemeral-token mechanism turns out not to support the assumed flow at implementation time, this ADR's custody section will need a follow-up ADR; the discovery-only scope boundary does not depend on that detail and holds regardless.
- Design-only as of this ADR; no code has been written for Phase 17.

**Evidence:**
- User: "google gemini live, I already have the api key it can be a live conversation"
- User: "Full chat back-and-forth" (clarification strategy)
- User: "Yes, discovery-only exception" (ADR-001 scoping)
- User: "as a variable on cloudflare" (key custody)
- Master plan §6.6 / ADR-003: secrets live only in a managed platform secret store, never locally
- Phase: Phase 17 (Multi-Channel Intake, extension)

**Author:**
User decision, collaborative brainstorm per explicit request (2026-10-03)

---

## Pending Decisions (Strategic Ambiguity)

None at Phase 1. Candidates will emerge during phases if business meaning is unclear:
- Phase 7: Critic findings classified as `strategic_ambiguity` are escalated here
- Phase 11: Reviewer findings that conflict with intent are escalated here
- Phase 14: Recovery procedures not in master plan are escalated here

---

## Decision Log (as Decisions Arise)

This section will be updated chronologically as new ADRs are created during phases 2–16.

---

*Index created: 2026-10-03 during Phase 1  
Authority: DARK_FACTORY_BUILD_PROMPT.md §6 (decisions escalation policy)  
Next review: After Phase 7 (requirement challenge may surface strategic ambiguity)*

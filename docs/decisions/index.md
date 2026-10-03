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

**Status:** APPROVED (user decision, Phase 1)

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

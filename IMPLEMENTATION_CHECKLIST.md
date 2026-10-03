# Dark Factory Implementation Checklist

**Project:** dark-factory-teamplate (orchestrator)  
**Target Project:** Configurable per `profiles/` (see ADR-004) — investisor was Phase 1's illustrative example only, not a fixed target  
**Started:** 2026-10-03  
**Authority:** DARK_FACTORY_MASTER_PLAN.md (binding)  
**Build Prompt:** DARK_FACTORY_BUILD_PROMPT.md  

## Phase 1: Audit and Threat Model

### Deliverables
- [ ] `docs/audit/prerequisite-report.md` — environment, tooling, dependencies
- [ ] `docs/audit/repository-report.md` — repo structure, git state, remote config
- [ ] `docs/threat-model.md` — security, isolation, leakage boundaries
- [ ] `docs/decisions/index.md` — decision log and registry
- [ ] `THIRD_PARTY_NOTICES.md` — licensing and attribution

### Secondary Checks
- [ ] Read DARK_FACTORY_MASTER_PLAN.md completely (done)
- [ ] Verify Windows 11 + PowerShell 7 environment (done)
- [ ] Confirm Git remote points to correct repo (done)
- [ ] Verify tooling baseline (Python 3.12, uv, gh, ollama, opa, wrangler)
- [ ] Check GitHub authentication status (pending: `gh auth login`)
- [ ] Verify Cloudflare credentials will not be stored locally
- [ ] Confirm target repo (investisor) accessibility

### Gate
- [ ] All audit docs written and reviewed
- [ ] No blocking prerequisites remain (gh auth is user-driven, deferred)
- [ ] Protected paths identified
- [ ] Threat model covers leakage boundaries
- [ ] Commit: "Phase 1: Audit, threat model, implementation checklist"

---

## Phase 2: Contracts and Schemas

### Deliverables
- [ ] `factory/schemas/workflow.schema.json` — workflow YAML structure
- [ ] `factory/schemas/context_manifest.schema.json` — context package metadata
- [ ] `factory/schemas/evidence_manifest.schema.json` — evidence traceability
- [ ] `factory/schemas/decision.schema.json` — strategic decision record
- [ ] `factory/schemas/requirement.schema.json` — compiled intent structure
- [ ] Unit tests for all schemas (Pydantic validation)

### Secondary Checks
- [ ] Each schema has examples/fixtures
- [ ] Schema tests cover positive/negative cases
- [ ] No schema mutation allowed in Phase 3+

### Gate
- [ ] All schemas have tests and pass
- [ ] Commit: "Phase 2: Contracts and schemas"

---

## Phase 3: FactoryFlow Core

### Deliverables
- [ ] `pyproject.toml` with `uv` dependency manifest
  - Python 3.12, Typer, Pydantic, SQLAlchemy, Jinja2, PyYAML, aiofiles, httpx, etc.
- [ ] `factory/cli.py` — Typer CLI with commands from §4.2
- [ ] `factory/state.py` — SQLite schema and migrations
- [ ] `factory/config.py` — YAML workflow definitions and runtime config
- [ ] `factory/models.py` — Pydantic models for projects, runs, stages
- [ ] `factory/__main__.py` — CLI entry point
- [ ] Test coverage: unit tests for state, config, models

### Secondary Checks
- [ ] SQLite schema supports resumption (run_id, stage, attempts recorded)
- [ ] Migrations are reversible
- [ ] Typer CLI works with `python -m factory --help`

### Gate
- [ ] `factory doctor` reports system state
- [ ] `factory init` creates project structure
- [ ] All Phase 3 tests pass
- [ ] Commit: "Phase 3: FactoryFlow core, CLI, state"

---

## Phase 4: Backlog Scheduler

### Deliverables
- [ ] `factory/backlog/scheduler.py` — eligibility check, atomic claim, lease recovery
- [ ] `factory/backlog/claim.py` — claim record with heartbeat, stale detection
- [ ] GitHub API adapter: list issues, apply labels, read/modify branch protection
- [ ] Deterministic priority order (per §5): security → critical → high → normal → low
- [ ] `factory queue` command: list eligible items with claim status
- [ ] `factory schedule` internal: claim next eligible, start run
- [ ] Tests: eligibility filtering, claim races, stale recovery, priority order

### Secondary Checks
- [ ] Labels configured on investisor: `factory:ready`, `priority:*`, `factory:claimed`, etc.
- [ ] GitHub branch protection rules documented (will set in Phase 12)
- [ ] Lease TTL and heartbeat interval configured

### Gate
- [ ] `factory queue` lists eligible issues on investisor
- [ ] Atomic claim prevents race conditions (test with concurrent claims)
- [ ] Stale claim recovery detects and recovers local/remote state drift
- [ ] All Phase 4 tests pass
- [ ] Commit: "Phase 4: Backlog scheduler, claims, eligibility"

---

## Phase 5: Context Broker and Leakage Tests

### Deliverables
- [ ] `factory/context/broker.py` — context package assembly and isolation
- [ ] Context classes (§6.1):
  - Immutable governance (protected paths, merge/deploy policy)
  - Certified project knowledge (requirements, ADRs, contracts, glossary)
  - Run-shared approved artifacts (compiled intent, assurance, plan, criteria, evidence)
  - Role-private data (conversations, notes, exploration)
  - Restricted assurance (sealed tests, mutations, rubrics, policies, secrets)
  - Ephemeral (reasoning, unverified summaries)
- [ ] Context manifest schema and validation
- [ ] Role-scoped context packages for analyst, critic, planner, builder, repairer, reviewer
- [ ] Leakage tests:
  - [ ] Builder cannot read sealed tests
  - [ ] Reviewer cannot read builder chat or repair logs
  - [ ] Sealed-to-builder boundary enforced
  - [ ] Run-to-run boundary enforced
  - [ ] Project-to-project boundary enforced
- [ ] Directory isolation: `C:\Factory\worktrees\RUN-*\shared`, `*-private`

### Secondary Checks
- [ ] Each context package includes metadata hash and policy decision record
- [ ] Missing metadata causes fail-closed rejection (test this)
- [ ] Unauthorized access logged and raises exception

### Gate
- [ ] All leakage tests pass (all 5 boundaries verified)
- [ ] Builder session cannot import sealed test module
- [ ] Reviewer session initialized with approved-only context
- [ ] Commit: "Phase 5: Context broker, isolation, leakage tests"

---

## Phase 6: Model Gateway and Benchmark Suite

### Deliverables
- [ ] `factory/gateway/ollama_gateway.py` — unified Ollama inference interface
- [ ] Model aliases configuration: all roles → `qwen2.5-coder:32b` (single model choice)
- [ ] Gateway responsibilities:
  - Fresh sessions (new API call per role + run)
  - Context limit enforcement (8192 tokens initially)
  - Timeout and cancellation
  - Structured-output validation (JSON schema)
  - Tool normalization
  - Telemetry logging (prompt tokens, completion tokens, latency)
  - Retry policy (exponential backoff, max 3 attempts)
  - Redaction of secrets from logs
- [ ] Benchmark harness: measure load time, first-token latency, throughput, peak memory, pagefile growth
- [ ] Fake model for unit tests (deterministic responses, no Ollama required)
- [ ] Real model smoke tests: router, analyst, builder, reviewer roles
- [ ] Performance baseline recorded (model size, quantization, resource usage)

### Secondary Checks
- [ ] No direct Ollama calls outside gateway (search and enforce)
- [ ] Gateway logs include model name, role, tokens, latency per call
- [ ] Retry logic tested with simulated failures
- [ ] Memory measurement captures peak committed memory and pagefile

### Gate
- [ ] `ollama list` shows qwen2.5-coder:32b available
- [ ] Gateway smoke test passes (real model responses logged)
- [ ] Benchmark logs recorded in `docs/benchmarks/baseline.md`
- [ ] All Phase 6 tests pass
- [ ] Commit: "Phase 6: Model gateway, benchmarking, baseline"

---

## Phase 7: BMAD and Isolated Requirement Challenge

### Deliverables
- [ ] `factory/analysis/bmad.py` — BMAD discovery, clarification, specification
- [ ] `factory/analysis/critics.py` — isolated critic agents:
  - Product Critic (user-visible meaning, entitlement, scope)
  - Domain-Rule Critic (business rules, domain calculation)
  - Testability Critic (acceptance criteria, observability)
  - Security/Permissions Critic (actors, data, access control)
  - Contradiction Critic (requirement conflicts, contradictions)
  - Operational-Recovery Critic (failure modes, recovery)
- [ ] Critic architecture:
  - Fresh session per critic (separate conversation)
  - Narrow rubric + output schema
  - No cross-critic memory sharing
  - Finding includes: role, category, statement, evidence, severity, resolution class
- [ ] Classification logic (§7):
  - `evidence_resolvable` — derive from authoritative project source
  - `delegated_technical` — decide under approved policy
  - `reversible` — choose repository-consistent option, record it
  - `strategic_ambiguity` — escalate for human decision
  - `invalid` — reject with source-backed reason
- [ ] Challenge gate: actors, permissions, errors, data, preconditions, postconditions, acceptance, non-goals, contradictions, requirement-to-evidence mapping complete; no unsupported business decision remains
- [ ] Tests: verify critics receive correct context, findings classified correctly, majority vote never used

### Secondary Checks
- [ ] No critic finding uses model confidence/agreement as authority
- [ ] All strategic_ambiguity findings escalate (not auto-decided)
- [ ] Critic contexts tested for unauthorized leakage

### Gate
- [ ] Challenge gate logic implemented and tested
- [ ] Mock issue processed through BMAD → critics → synthesis (dry run)
- [ ] All findings classified; strategic ambiguities identified
- [ ] Commit: "Phase 7: BMAD, isolated critics, requirement synthesis"

---

## Phase 8: Tool Authorization and Worktrees

### Deliverables
- [ ] `factory/tools/authorized_ops.py` — named operation broker
  - `read_file`, `search_code`, `write_file`, `apply_patch`
  - `format`, `lint`, `typecheck`, `build`, `test`, `security_check`
  - `git_status`, `git_diff`, `git_commit`, `git_push`, `git_branch`
  - Prohibited: unrestricted PowerShell, dependency install, directory delete, migration, auth, secrets
- [ ] `factory/policy/opa_broker.py` — OPA policy evaluation
  - Input: project/run/role, operation, command template, cwd, paths, network, secret, expected side effect
  - Output: approve/deny with rationale
  - Stored policy: `factory-control/policies/*.rego`
- [ ] Worktree manager: `C:\Factory\worktrees\RUN-<id>`, branch `factory/RUN-<id>-<slug>`
  - Never modify primary checkout
  - Never reuse worktree
  - Protected paths (governance, control data, production workflows, env, authority, secrets)
  - Protected-path changes cannot auto-merge
- [ ] ACL configuration for worktree directory (optional: restricted account)
- [ ] Tests:
  - Restricted operation denied (e.g., `rm -rf`)
  - Allowed operation approved and executed
  - OPA policy evaluates correctly
  - Worktree created/cleaned properly
  - SHA mismatch detected

### Secondary Checks
- [ ] Protected paths: `.factory-control/`, `.factory/`, `DARK_FACTORY_*.md`, `IMPLEMENTATION_CHECKLIST.md`, `factory/`, `docs/decisions/`, `THIRD_PARTY_NOTICES.md`
- [ ] Exit code alone never trusted; postconditions verified (file hash, git commit, etc.)
- [ ] No raw shell access; all commands go through broker

### Gate
- [ ] Worktree created, build/test/git commands restricted and approved
- [ ] Protected-path change detection working
- [ ] All Phase 8 tests pass
- [ ] Commit: "Phase 8: Tool authorization, OPA, worktrees"

---

## Phase 9: Sealed QA and Mutation Testing

### Deliverables
- [ ] `factory/qa/sealed_specs.py` — hidden acceptance specifications
- [ ] `factory/qa/mutation_tester.py` — mutation testing framework
- [ ] Sealed test storage: `factory-control/sealed/test_*.json` (hidden from builder)
- [ ] Mutation definitions: `factory-control/mutations/rule_*.json` (hidden from builder)
- [ ] Verification order (§11):
  1. Format
  2. Lint
  3. Type check
  4. Build
  5. Unit
  6. Component
  7. Contract
  8. Integration
  9. Secret scan
  10. Static security
  11. Dependency scan
  12. Mutation testing
  13. Runtime scenarios
  14. Sealed acceptance
  15. Accessibility (if applicable)
  16. Visual regression (if applicable)
  17. Performance (if applicable)
- [ ] Builder sees only: observable failure envelope, allowed fix scope, attempt number
- [ ] Builder cannot: delete/weaken/skip/exclude failing tests, modify sealed tests, replace behavior with mocks
- [ ] Deterministic failures override LLM, urgency, or retry exhaustion
- [ ] Tests: sealed confidentiality (builder cannot read), deterministic failure stops repair

### Secondary Checks
- [ ] Mutation survival measured; weak mutations recorded as passing (expected)
- [ ] False-positive mutations eliminated before builder sees results
- [ ] Sealed test format is JSON with observable failure pattern only

### Gate
- [ ] Sealed test created for mock requirement
- [ ] Builder repair loop receives only envelope, not internal test logic
- [ ] Mutation testing produces actionable diff report
- [ ] Commit: "Phase 9: Sealed QA, mutation testing, verification order"

---

## Phase 10: Implementation, Verification, and Repair

### Deliverables
- [ ] `factory/builder/builder.py` — implementation agent harness
- [ ] `factory/verification/verifier.py` — verification runner
- [ ] `factory/repair/repairer.py` — bounded repair (max 3 cycles)
- [ ] Implementation flow:
  - Receive compiled intent, approved plan, acceptance criteria, allowed paths
  - Generate code in worktree using Aider adapter
  - Run verification suite (Phase 9 order)
  - Collect failures and attempt count
- [ ] Repair loop:
  - Input: category, logs, expected/actual, allowed/prohibited paths, attempt, previous patch digest
  - Limit: 3 cycles max
  - Stop conditions: business meaning changed, protected path touched, resources exhausted, strategic ambiguity, repo state differs
- [ ] Stall diagnosis (§12):
  - Repeating same failure twice → fresh diagnosis session
  - Competing hypotheses, rank with evidence
  - Smallest reversible experiment
  - Stop if evidence doesn't improve
- [ ] Aider integration: subprocess management, output parsing, tool use
- [ ] Tests: mock issue → implementation → verification → pass/fail paths

### Secondary Checks
- [ ] Attempt counter and digest tracked in SQLite
- [ ] Repair never modifies sealed tests or skips deterministic failures
- [ ] Stall detection has logging and evidence capture

### Gate
- [ ] Mock issue implemented and verified
- [ ] Repair cycle bounded and logged
- [ ] Stall detector triggered and stopped correctly
- [ ] Commit: "Phase 10: Implementation, verification, bounded repair"

---

## Phase 11: Independent Review

### Deliverables
- [ ] `factory/review/reviewer.py` — fresh SHA-bound review agent
- [ ] Reviewer session: fresh, context compiled by orchestrator (not builder)
- [ ] Review includes:
  - Requirements coverage
  - Architecture and design
  - Permissions and security
  - Error handling and data behavior
  - Scope and non-goals
  - Tests (unit, integration, mutation, sealed)
  - Recovery and documentation
  - Evidence manifest
- [ ] Output: pass/fail/decision, reviewed base/head SHA, findings, evidence gaps, protected-path status
- [ ] Auto-merge prerequisites (§14):
  - No unresolved business decisions
  - Valid intent and authority
  - All checks pass
  - Sealed and mutation pass
  - Independent review pass
  - Protected paths unchanged
  - Preview pass
  - No conflict
  - Valid evidence
  - Reviewed SHA equals head SHA (exact SHA binding)
- [ ] Tests: reviewer rejects weaker mutation, catches missing test, verifies evidence traceability

### Secondary Checks
- [ ] Reviewer context package excludes builder chat, scratch, repair logs, secrets
- [ ] SHA mismatch between reviewed and merged SHA detected and blocks merge

### Gate
- [ ] Mock PR reviewed and verdict recorded
- [ ] Evidence manifest completeness verified
- [ ] SHA binding enforced
- [ ] Commit: "Phase 11: Independent review, SHA binding"

---

## Phase 12: GitHub PR and Auto-Merge

### Deliverables
- [ ] `factory/github/github_adapter.py` — GitHub API integration
- [ ] GitHub operations:
  - Create branch `factory/RUN-<id>-<slug>`
  - Push commits to branch
  - Open PR with body including compiled intent, requirements, evidence summary
  - Publish required status checks (16 unique names per §14):
    - `factory/intent` — intent validation
    - `factory/authority` — protected paths, merge policy
    - `factory/protected-paths` — no governance changes
    - `factory/format` — code formatting
    - `factory/lint` — linting
    - `factory/typecheck` — type checking
    - `factory/build` — build pass
    - `factory/unit` — unit tests
    - `factory/contract` — contract tests
    - `factory/integration` — integration tests
    - `factory/security` — security checks (secrets, static)
    - `factory/mutation` — mutation survival
    - `factory/sealed-qa` — sealed acceptance
    - `factory/review` — independent review
    - `factory/preview` — preview deploy
    - `factory/evidence` — evidence manifest valid
- [ ] Branch protection rules:
  - Require all 16 status checks
  - Require code review (manual or auto-set by policy)
  - Block force-push
  - Require branches up to date
- [ ] Auto-merge configuration:
  - Never used for governance changes
  - Only after all checks pass
  - SHA must match reviewed SHA
  - Enable via API (no admin bypass)
- [ ] Tests: PR creation, check publishing, auto-merge enabled/disabled correctly

### Secondary Checks
- [ ] No direct push to main
- [ ] All status checks have meaningful names (searchable, debugging)
- [ ] Auto-merge never applies to protected-path changes

### Gate
- [ ] Mock PR created with all 16 checks
- [ ] Auto-merge enabled only after all checks pass and reviewer approves
- [ ] Auto-merge disabled if SHA drifts from reviewed
- [ ] Commit: "Phase 12: GitHub PR, auto-merge, required checks"

---

## Phase 13: Cloudflare Preview and Production

### Deliverables
- [ ] `factory/deploy/cloudflare_adapter.py` — Wrangler integration
- [ ] Deployment flow:
  - After PR merge to main, GitHub Actions deploys via Wrangler
  - Cloudflare secrets stored in GitHub Actions (never locally)
  - Deploy to preview (PR) before merge
  - Deploy to production after main merge
- [ ] Preview deployment (Phase 12):
  - Generate preview URL
  - Run smoke tests (critical browser/API behavior)
  - Record preview result in evidence manifest
- [ ] Production deployment (Phase 14):
  - Verify deployed version matches main SHA
  - Verify critical health/behavior
  - Record production validation in evidence
- [ ] GitHub Actions workflow: `.github/workflows/deploy.yml`
  - Trigger: PR merge to main
  - Secret injection: CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
  - Wrangler deploy
  - Health check
- [ ] Tests: mock deploy, health check pass/fail paths
- [x] `profiles/` directory (§17): per-managed-project configuration
  - `factory/profiles.py` — Profile, TargetRepository, CloudflareProjectRef,
    list/load/save/create/resolve_active_profile
  - Secret-free by construction; secrets live only as GitHub Actions secrets
    on each profile's target repo (`factory/deploy/target_repo_setup.py`)
  - CLI: `factory profile create|list|show`, global `--profile` option
  - Factory is built once and reused unmodified across every future project

### Secondary Checks
- [ ] Cloudflare secrets not logged or exposed
- [ ] Preview URL accessible and health-checked
- [ ] Rollback decision documented (never auto-invent rollback)

### Gate
- [ ] GitHub Actions workflow created and tested
- [ ] Cloudflare account ID and token stored in repo secrets
- [ ] Mock deploy to preview succeeds
- [ ] Production validation harness ready
- [x] Factory is target-repo-agnostic via `profiles/` — no hardcoded project
- [ ] Commit: "Phase 13: Cloudflare preview/production deploy"

---

## Phase 14: Recovery and Emergency Controls

### Deliverables
- [ ] `factory/recovery/quarantine.py` — incident quarantine logic
- [ ] `factory/recovery/emergency_stop.py` — emergency stop mechanism
- [ ] Recovery flow (§15):
  - If deployment or smoke validation fails:
    - Pause new merges
    - Record bad SHA and deployment info
    - Follow only declared recovery
    - Verify last-known-good state
    - Resume only when production is known
  - Never invent destructive migration rollback
  - Never continue merging while production state unknown
- [ ] Emergency stop:
  - `factory emergency-stop` command
  - Blocks new issue claims
  - Disables pending auto-merges
  - Logs reason and timestamp
  - Requires explicit `factory resume` to clear
- [ ] Stale deployment detection:
  - Poll production version (from headers, API, etc.)
  - Compare to expected SHA
  - Raise alert if unknown
- [ ] Tests: quarantine on bad deployment, resume on healthy state, emergency stop blocks new work

### Secondary Checks
- [ ] Recovery procedures are deterministic and policy-defined
- [ ] Emergency stop reason is logged and searchable

### Gate
- [ ] Mock bad deployment triggers quarantine
- [ ] Emergency stop prevents new claims
- [ ] Explicit resume clears stop
- [ ] Commit: "Phase 14: Recovery, emergency controls, quarantine"

---

## Phase 15: Evidence and Learning

### Deliverables
- [ ] `factory/evidence/graph.py` — evidence graph linking
- [ ] `factory/evidence/manifest.py` — evidence manifest per run
- [ ] `factory/learning/memory.py` — certified lesson promotion
- [ ] Evidence traceability (§16):
  - Requirement → implementation (commit)
  - Requirement → public tests
  - Requirement → sealed summary
  - Requirement → mutation result
  - Requirement → security results
  - Requirement → independent review
  - Requirement → preview result
  - Requirement → production validation
- [ ] Evidence manifest includes:
  - SHAs (base, head, deployed)
  - Requirements demonstrated
  - Gates and checks passed
  - Context package IDs and hashes
  - Policy decisions and exceptions
  - Unresolved questions
  - Preview and production results
- [ ] Certified lesson workflow:
  - Agent proposes candidate lesson
  - Evidence validation and contradiction check
  - Policy approval
  - Cross-run retrieval returns certified lessons (not raw chat)
- [ ] Tests: evidence graph completeness, lesson promotion validated

### Secondary Checks
- [ ] Missing evidence manifest prevents auto-merge (double-check in Phase 12)
- [ ] Raw conversations never stored as certified memory
- [ ] Lessons searchable and traceable to source evidence

### Gate
- [ ] Evidence manifest created for mock run
- [ ] No valid evidence means no auto-merge (test failure mode)
- [ ] Commit: "Phase 15: Evidence graph, learning, certified memory"

---

## Phase 16: End-to-End Autonomous Acceptance

### Deliverables
- [ ] Real eligible issue from investisor repo with `factory:ready` label
- [ ] Full end-to-end flow:
  - Claim issue atomically
  - BMAD analysis → isolated critics → synthesis
  - Decision classification (no unsupported business decisions)
  - Context-isolated implementation (builder fresh session)
  - Sealed QA and verification
  - Bounded repair (if needed)
  - Fresh SHA-bound review
  - GitHub PR with all 16 checks
  - Preview deployment and smoke test
  - Auto-merge after all checks pass
  - Production deployment and validation
  - Issue closure
  - Next-item selection
- [ ] Emergency stop: verify factory refuses new merges during stop
- [ ] Governance refusal: verify factory refuses to modify DARK_FACTORY_MASTER_PLAN.md or IMPLEMENTATION_CHECKLIST.md via normal workflow
- [ ] Full evidence and report recorded
- [ ] Retrospective: model performance, resource usage, time-to-close

### Secondary Checks
- [ ] All phases 1–15 operational
- [ ] No human decision needed (or strategic ambiguity properly escalated)
- [ ] Production health confirmed
- [ ] Next issue claimed automatically

### Gate
- [ ] Real issue closed with evidence trail
- [ ] Factory selects next eligible item
- [ ] Emergency stop works
- [ ] Governance self-protection works
- [ ] Final commit: "Phase 16: End-to-end autonomous acceptance"

---

## Overall Gates

### Per-Phase Gate (each phase)
1. ✓ Run phase tests
2. ✓ Secondary consistency check against DARK_FACTORY_MASTER_PLAN.md
3. ✓ Inspect git diff and protected paths
4. ✓ Update this checklist
5. ✓ Update ADRs, threat model, license records
6. ✓ Record commands, outcomes, remaining risks
7. ✓ Commit only passing work (phase-specific message)
8. ✓ Do not start next phase if gate fails

### Definition of Done (Phase 16 completion)
- ✓ Native PowerShell UX (no Ubuntu/Docker required)
- ✓ Local gateway operational
- ✓ Sequential inference (one model, qwen2.5-coder:32b)
- ✓ Deterministic backlog
- ✓ Claims and recovery working
- ✓ BMAD + isolated critics operational
- ✓ Evidence-based synthesis (no majority vote)
- ✓ Strategic decision path (escalation working)
- ✓ Context manifests and fresh sessions
- ✓ Builder/reviewer isolation verified
- ✓ Sealed confidentiality verified
- ✓ Worktree/protected-path controls working
- ✓ Verification, bounded repair, stall detection working
- ✓ SHA-bound independent review working
- ✓ Required checks and non-bypass auto-merge working
- ✓ Cloudflare preview and production working
- ✓ Recovery/quarantine/emergency controls working
- ✓ Evidence graph and issue closure working
- ✓ End-to-end autonomous loop passes (real issue, investisor repo)

---

## Status Summary

**Current Phase:** 1 (Audit and Threat Model)  
**Model Download:** In progress (qwen2.5-coder:32b)  
**GitHub Auth:** Pending (user will run `gh auth login`)  
**Target Repo:** Configurable per `profiles/` (ADR-004) — not a fixed repo  
**Cloudflare:** Account ID and API Token received (will configure in Phase 13)  
**Remaining Prerequisites:** gh auth, per-profile repo labels configured (Phase 4, per profile)

---

## Phase 17: Multi-Channel Intake (extension, post-master-plan)

**Added:** 2026-10-03, by explicit user request — brainstormed collaboratively, not part of the original 16-phase master plan. Design-only until the user approves implementation; see ADR-004/ADR-005 for the decisions behind it.

**Why:** every prior phase assumes a requirement already exists as a GitHub Issue. Phase 17 is the "front door" that lets a requirement arrive as a web form submission, a live voice conversation, a Telegram message, an email, or (later) a WhatsApp message, and resolves it into a well-formed `factory:ready` Issue — without changing anything in Phases 1–16.

### Deliverables

- [ ] `factory/intake/` — Channel Adapter interface: normalizes any channel into a `RawIntakeMessage` (sender id, text, media, channel)
- [ ] Sender allow-list enforcement (reject unknown senders on every channel before any GitHub/profile action)
- [ ] Profile resolution: map an intake message to an existing profile, or route brand-new-repo setup to the web channel only (never accept credentials via chat/email/voice)
- [ ] State-transition notifier: watches existing GitHub label/state transitions (Coleam-style visible state, already produced by Phases 4/12/14/15) and pushes a short message to the originating channel plus updates the web dashboard
- [ ] **Phase 17.0 — Web page (primary interface)**
  - Profile select/create UI (wraps existing `factory profile create/list/show`)
  - Discovery conversation: Gemini Live (voice) or typed chat, full back-and-forth clarification (per ADR-005) until the spec converges
  - Files the resulting draft as a GitHub Issue (`factory:ready`) on the resolved profile's target repo
  - Live dashboard: run state, evidence, decision history, per profile
  - Gemini API key held as a Cloudflare Worker secret; the Worker's only job is minting short-lived ephemeral Gemini Live tokens — the long-lived key never reaches the browser or any local file (per ADR-005)
- [ ] **Phase 17.1 — Telegram adapter**
  - Bot API long-polling (no public endpoint required)
  - Text and voice-note input; voice notes also go through the Gemini Live discovery flow
  - Progress pushed as replies in the originating chat
- [ ] **Phase 17.2 — Email adapter**
  - IMAP polling (no public endpoint required)
  - Longer-form specs and attachments; progress replies sent as thread replies (best-effort; email is not a "continuous" medium)
- [ ] **Phase 17.3 — WhatsApp adapter**
  - Official Cloud API, requires a public HTTPS webhook (tunnel) — deferred until 17.0–17.2 prove the pattern
- [ ] Tests: allow-list rejection, profile resolution (existing/ambiguous/new), notifier fan-out to origin channel, and a secret-leak guard (no GitHub/Cloudflare/Gemini credential ever appears in a chat transcript, log, or browser-reachable response)

### Secondary Checks

- [ ] No channel can create or modify a profile's secrets — only the web page's one-time setup flow can
- [ ] Gemini Live is used only for pre-filing discovery; nothing downstream of Issue creation uses a cloud model (ADR-005 boundary holds)
- [ ] Phase 7's existing decision-required escalation still handles in-flight ambiguity; Phase 17 does not duplicate it

### Gate

- [ ] Web intake (text or Gemini Live voice) produces a well-formed `factory:ready` Issue on the correct profile's repo
- [ ] Progress is pushed to the originating channel and visible on the web dashboard for the same run
- [ ] No secret (GitHub, Cloudflare, or Gemini) ever reaches a chat transcript, email, log, or client-side JS
- [ ] Commit: "Phase 17.0: Multi-channel intake — web page and Gemini Live discovery"

---

## Phase 18: Autonomous Intake-to-Deploy Pipeline (extension, post-Phase-17)

**Added:** 2026-10-04, by explicit user request. Design-only until the user approves implementation; see ADR-007 for the full decision record (queue schema, local build loop, new-app deploy credential, secret-sharing model, tracking-issue design).

**Why:** Phase 17.0 files a well-formed Issue but nothing consumes it. This phase is what makes "the factory starts working once an issue is submitted" literally true — it is also the phase that finally gives Phase 4's `BacklogScheduler` and the implementation `ImplementationOrchestrator` a real execution context, scoped to issues arriving through web intake.

### Deliverables

- [ ] **Phase 18.0 — Queue schema + Worker API**
  - Apply `factory/intake/worker/schema_phase18.sql` (`build_queue` table) to the live D1 database
  - `POST /conversations/:id/file-issue` also inserts a `build_queue` row (status `queued`)
  - New routes: `GET /build-queue` (list, for the runner and for display), `POST /build-queue/:id/claim` (conditional, single-flight — see ADR-007), `POST /build-queue/:id/progress`, `GET /build-queue/:id` (polled by the web UI)
- [ ] **Phase 18.1 — Local queue runner** (`factory/intake/queue_runner.py`, new)
  - Polls `GET /build-queue?status=queued`, claims the oldest row, processes exactly one job at a time end to end before claiming the next
  - Resolves/creates the profile via the existing `LocalProfileSync` (`factory/intake/local_sync.py`) — its first real caller
  - Drives the existing `ImplementationOrchestrator` (`factory/implementation/orchestrator.py`) and `BacklogScheduler` (`factory/backlog/scheduler.py`) through implementation/test/review
  - Reports step-by-step progress via `POST /build-queue/:id/progress` after every phase transition
  - Resolves `factory/cli.py`'s `run`/`queue`/`pause`/`resume` placeholders (currently "not yet implemented (Phase 4 backlog scheduler)")
- [ ] **Phase 18.2 — New-app deploy automation**
  - On `needs_new_app = true`: `wrangler deploy` using the operator's own already-authenticated local CLI session (no new secret stored or minted — ADR-007 §3)
  - Attach a Cloudflare Custom Domain at `<project-slug>.mtourk.com` (auto-provisions its own DNS record on the existing `mtourk.com` zone — no manual DNS step)
  - Report the final live URL via the progress endpoint on `done`
  - New app's Worker receives no copy of `GEMINI_API_KEY`/`GITHUB_REPO_CREATE_TOKEN`; capability is shared by calling back into the central Intake Worker, never by copying secrets (ADR-007 §4)
- [ ] **Phase 18.3 — Existing-repo edit/deploy flag**
  - Repo-selection modal gains an "Also deploy after this change" checkbox (default off) for the existing-repo path
  - When checked, deploy runs against that repo's existing Worker (via its `profiles/<name>.yml`), not a new subdomain
- [ ] **Phase 18.4 — Dark Factory tracking issue**
  - Filing an issue on a target repo also files a lightweight, non-claimable tracking issue on `dark-factory-teamplate` itself, cross-linked by URL, closed automatically when the `build_queue` row reaches `done`/`failed` (ADR-007 §5 — does not reopen ADR-002/004)
- [ ] **Phase 18.5 — Progress UI + mid-flight amendments**
  - Web app's success screen replaced by a status screen polling `GET /build-queue/:id`: current step, done/remaining steps, final URL or PR link once `done`
  - An **"Add Detail"** panel visible while the job is in-flight (`claimed`–`deploying`) lets the user append clarifications/acceptance criteria/constraints without interrupting the current job
  - New Worker endpoint: `POST /build-queue/:id/append-detail` receives the text, appends it as a GitHub comment on the issue, records it in `build_queue_updates` for audit
  - Queue runner reads the full GitHub issue (body + fresh comments) at the start of each phase transition, so user amendments automatically flow into the next critic/builder run without requiring a restart or priority bump
- [ ] Tests: single-flight claim correctness (two concurrent claim attempts on one row), queue runner failure path (leaves profile/branch intact, reports `failed`, does not auto-retry), secret-leak guard extended to confirm the new app's Worker never receives `GEMINI_API_KEY`/`GITHUB_REPO_CREATE_TOKEN`, mid-flight amendments are captured + posted as GitHub comments + flow into the runner's next phase transition

### Secondary Checks

- [ ] Editing an existing repo never uses the ambient-CLI deploy path's credential model exception — it continues through that repo's own GitHub Actions secrets per ADR-003/004, unchanged
- [ ] Only one `build_queue` row is ever in a non-terminal state at a time (enforced at the DB level, not just by runner convention)
- [ ] `dark-factory-teamplate`'s own tracking issues are never claimed by the queue runner (ADR-002/004 boundary holds)

### Gate

- [ ] Filing an issue (new repo, "needs new app") results, with zero further manual steps, in a live `https://<slug>.mtourk.com` URL reported back through the progress endpoint
- [ ] Filing an issue against an existing repo with "also deploy" unchecked results in a PR, not a deploy
- [ ] A second issue filed while the first is still processing is visibly `queued`, not started, and begins only after the first reaches `done`/`failed`
- [ ] The web UI shows current step + done/remaining steps for an in-flight job, polling only — no new inbound exposure for the local machine
- [ ] Commit: "Phase 18.0: Build queue + local queue runner — autonomous intake-to-deploy pipeline"

---

*Last updated: 2026-10-04 — added Phase 18 (ADR-007); added `docs/operations/INTAKE_DEPLOYMENT_PLAYBOOK.md` (proven commands + known-blocked commands for the factory to follow)*

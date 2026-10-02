# Windows-Native Autonomous Local Dark Factory

## 0. Authority of this plan

This file is the binding implementation specification for a reusable Windows-native, local-LLM software factory. The implementation agent must read it completely before changing the repository. When instructions conflict, the stricter rule for isolation, evidence, non-bypassable controls, or production safety wins.

The finished factory continuously selects eligible GitHub Issues, challenges and compiles requirements, implements changes, validates them, opens pull requests, enables auto-merge after all required checks pass, deploys through Cloudflare, validates production, records evidence, and selects the next eligible item. Human involvement is limited to strategic product choices, missing or contradictory business rules, new legal or licensing commitments, governance changes, and incidents without an approved recovery path.

## 1. Fixed environment

```yaml
host:
  os: Windows 11
  shell: PowerShell 7
  terminal: Windows Terminal
  editor: Visual Studio Code
  laptop: HP EliteBook 8 G1i 16
  cpu: Intel Core Ultra 7 265H
  ram_gb: 32
  gpu: Intel Arc 140T integrated
  dedicated_vram_gb: 0
local_inference:
  runtime: Ollama for Windows
  cloud_fallback: prohibited
  initial_context_tokens: 8192
  experimental_context_tokens: 16384
  maximum_heavy_sessions: 1
  q4_32b: benchmark_candidate
  q5_32b: experimental_only
  q8_32b: prohibited_initially
containers:
  required_for_factory: false
  install_silently: prohibited
```

The system must optimize for sequential inference because the model, Windows, browser tests, IDE, and tooling share 32 GB RAM. It must not assume the largest model is operationally best. Role assignments are selected by benchmarks.

## 2. Non-negotiable outcomes

The completed factory must:

1. Run through PowerShell on Windows 11.
2. Require no Ubuntu installation and no always-running Docker service.
3. Use a small Python orchestrator called FactoryFlow.
4. Use GitHub Issues as the primary backlog.
5. Use BMAD-style discovery and specification.
6. Use selected gstack-style challenge and review roles.
7. Use DUBS-style sealed acceptance testing.
8. Use OctopusGarden-style bounded repair and stall diagnosis.
9. Use Coleam-style GitHub state, stop control, and immutable governance.
10. Use Nick Fujita-style PRD challenge, QA runbooks, traceability, ADRs, and delivery reports.
11. Isolate every role in a fresh model session with a role-scoped context package.
12. Auto-merge only the exact independently reviewed commit after all required checks pass.
13. Deploy from `main`, validate production, close the issue, and select the next item.
14. Stop new merges while production state is unknown.
15. Refuse to modify its own protected authority through a normal feature workflow.

## 3. Architecture

```text
GitHub backlog or factory feature command
  -> deterministic eligibility and atomic claim
  -> BMAD requirement draft
  -> isolated requirement critics
  -> evidence-based synthesis and Intent Compiler
  -> delegated-authority and assurance routing
  -> sealed QA design before implementation
  -> role-scoped Builder context
  -> Aider + Ollama implementation in Git worktree
  -> deterministic verification and bounded repair
  -> fresh independent Reviewer context
  -> GitHub PR and Cloudflare preview
  -> preview acceptance and required checks
  -> GitHub auto-merge for reviewed SHA
  -> production deployment and validation
  -> evidence, report, retrospective
  -> close item and claim next eligible item
```

### 3.1 Framework responsibilities

- **BMAD concepts:** discovery, clarification, project context, specification, architecture exploration, story decomposition, and acceptance criteria. BMAD does not own process persistence, merge authority, retries, or deployment.
- **gstack concepts:** selective product, engineering, design, developer-experience, security, test, QA, release, retrospective, and benchmark perspectives. Do not run every role on every item.
- **DUBS concepts:** sealed-envelope tests, builder/QA separation, express/full lanes, checkpoints, and bounded hardening.
- **OctopusGarden concepts:** specification preflight, holdout scenarios, runtime validation, structured failure feedback, stall detection, and wonder/reflect diagnosis. Probabilistic scores never override deterministic failures.
- **Coleam concepts:** GitHub labels as visible state, separate triage/build/validation contexts, stop control, immutable governance, decision log, and automated merge through non-bypassable gates.
- **Nick Fujita concepts:** PRD challenge, QA runbooks, bidirectional coverage, independent review, browser acceptance, ADRs, and Feature Delivery Reports.

Do not vendor whole upstream repositories. Before adapting any code, prompt, configuration, or template, identify the exact source and version, read its license, record attribution, and choose dependency, adaptation, reimplementation, or rejection. Update `THIRD_PARTY_NOTICES.md` and `.factory/vendor/manifest.yml`.

## 4. FactoryFlow orchestrator

### 4.1 Technology

```yaml
language: Python 3.12
package_manager: uv
cli: Typer
validation: Pydantic
workflow_definition: YAML
state: SQLite
templating: Jinja2
subprocess: asyncio
shell: PowerShell 7
policy: Open Policy Agent
telemetry: OpenTelemetry-compatible
```

### 4.2 Commands

```powershell
factory doctor
factory init
factory feature "<goal>"
factory express "<small change>"
factory run
factory run -Once
factory pause
factory resume-queue
factory emergency-stop
factory queue
factory status
factory status -RunId <id>
factory resume -RunId <id>
factory stop -RunId <id>
factory validate -RunId <id>
factory report -RunId <id>
factory benchmark
factory learn -RunId <id>
factory decisions
factory decide -DecisionId <id> -Option <option>
```

### 4.3 Workflow primitives

Implement only: `command`, `function`, `agent`, `decision`, `conditional`, `command_group`, `bounded_loop`, `external_check`, and `terminal`.

Every stage declares input schema, output schema, timeout, maximum attempts, context policy, and transitions for success, failure, and decision-required.

### 4.4 Durable state

SQLite records project, issue, run, workflow version, stage, attempts, model and digest, session and context package IDs, tool policy decisions, worktree, branch, base/head SHA, tests, repair count, PR, preview, deployment, production validation, decisions, evidence, pause, stop, and quarantine.

A resumed run must verify real Git/GitHub/deployment state and must not repeat a consequential action without an idempotency check.

### 4.5 Do not build in version 1

Do not build a web dashboard, Kubernetes support, distributed workers, a visual workflow designer, plugin marketplace, cloud-model routing, parallel heavy agents, multi-user authentication, or self-modifying policies. These consume effort and memory without improving the first complete autonomous delivery loop.

## 5. Backlog and scheduler

An item is eligible when it is open, labeled `factory:ready`, not claimed/blocked/quarantined/decision-required, has resolved dependencies, does not conflict with active scope, and emergency stop is inactive.

Deterministic order:

1. Approved production security and defect work according to policy.
2. `priority:critical`.
3. `priority:high`.
4. `priority:normal`.
5. `priority:low`.
6. Creation order as tie-breaker.

Models must not reprioritize the backlog.

Claims include run ID, issue, branch, lease owner/status/heartbeat, and affected scopes. Stale claim recovery must inspect the local worktree, remote branch, PR, reviewed SHA, merge state, deployment, and production state.

`factory run` continues until no eligible items remain, emergency stop is active, production state is unknown, resources are unsafe, or GitHub/Ollama is unavailable beyond retry policy. An item needing a business decision moves to `factory:decision-required`; its claim is released; another eligible item is selected.

## 6. Context management and isolation

### 6.1 Context classes

1. Immutable governance: authority, protected paths, merge and deployment policy.
2. Certified project knowledge: approved requirements, ADRs, contracts, glossary, security rules, dependencies, accepted delivery reports.
3. Run-shared approved artifacts: compiled intent, assurance classification, approved plan, public criteria, objective evidence.
4. Role-private data: each role's conversation, scratch notes, exploration, and abandoned options.
5. Restricted assurance data: sealed tests, mutation definitions, rubrics, policies, and secrets.
6. Ephemeral data: temporary reasoning and unverified summaries.

### 6.2 Fresh sessions

Every model call is identified by:

```text
project_id + run_id + role + session_id
```

A new role means a new API conversation, system prompt, context package, private directory, and session ID. The same underlying model may be reused, but conversation state may not be reused.

### 6.3 Context manifests

Every package includes package ID, project, run, role, session, source artifact IDs and hashes, explicit exclusions, policy decision, and timestamp. Missing metadata causes fail-closed rejection.

### 6.4 Builder package

Include compiled intent, approved plan, public acceptance criteria, relevant code/contracts/ADRs, and allowed/prohibited paths. Exclude hidden tests, mutation definitions, reviewer rubric, other conversations, governance internals, and secrets.

### 6.5 Reviewer package

The orchestrator, never the builder, compiles reviewer context from the original issue, compiled intent, approved requirements, ADRs, base/head SHA, final diff, changed files, objective test/security/mutation summaries, preview result, and evidence manifest.

Exclude builder chat, scratch notes, reasoning, self-review, repair conversations, persuasive builder summary, hidden-test source, and secrets.

### 6.6 Storage

```text
C:\Factory  worktrees\RUN-...  runs\RUN-...\shared  runs\RUN-...nalyst-private  runs\RUN-...uilder-private  runs\RUN-...eviewer-private  control\sealed  control\mutations  controlubrics  control\policies  control\secrets```

Use a dedicated non-administrator Windows account where feasible. Deny builder access to control data, personal directories, browser profiles, SSH keys, and secrets.

### 6.7 Long-term memory

Agents can propose candidate lessons but cannot write certified knowledge directly. Promotion requires evidence validation, contradiction check, and policy approval. Cross-run retrieval returns certified lessons, never raw conversations.

### 6.8 Mandatory leakage tests

Test builder-to-reviewer, reviewer-to-builder, sealed-to-builder, run-to-run, and project-to-project boundaries. Unauthorized context access must fail loudly and record a policy violation.

## 7. Requirement challenge without routine human review

After BMAD drafts a specification, start separate sessions for Product Critic, Domain-Rule Critic, Testability Critic, Security/Permissions Critic, Contradiction Critic, and Operational-Recovery Critic when relevant.

Critics receive the original issue, relevant certified knowledge, the draft, a narrow rubric, and an output schema. They do not receive each other's private reasoning.

Each finding includes role, category, statement, evidence sources, severity, and resolution class.

Do not use majority vote. Classify findings as:

- `evidence_resolvable`: derive from authoritative project source.
- `delegated_technical`: decide under approved engineering policy.
- `reversible`: choose repository-consistent option and record it.
- `strategic_ambiguity`: request human decision.
- `invalid`: reject with source-backed reason.

Every autonomous business decision must cite an authoritative project source. Model confidence and agent agreement are not authority. If approved sources are silent on user-visible meaning, entitlement, domain calculation, pricing, strategic scope, or irreversible behavior, mark `strategic_ambiguity`.

The challenge gate passes only when actors, permissions, errors, data behavior, preconditions, postconditions, observable acceptance criteria, non-goals, contradictions, and requirement-to-evidence mapping are complete and no unsupported business decision remains.

## 8. Model gateway and benchmarking

All inference passes through one gateway. No skill calls Ollama directly. The gateway owns model aliases, fresh sessions, context limits, timeouts, cancellation, structured-output validation, tool normalization, telemetry, redaction, and retry limits.

Initial benchmark candidates:

```yaml
router: qwen2.5-coder:7b
analyst: qwen2.5-coder:14b
planner_candidate: qwen3:30b
builder_default: qwen2.5-coder:14b
builder_candidate: qwen2.5-coder:32b
reviewer_candidate: qwen3:30b
structured_tool_candidate: gpt-oss:20b
```

Measure load time, first token, throughput, peak committed memory, pagefile growth, JSON/tool validity, requirement accuracy, edits, tests, repair, permission reasoning, unsupported assumptions, public and sealed success, policy violations, and human corrections.

Promote a model only when accepted-task quality justifies resource cost.

## 9. Tool authorization

Never expose unrestricted PowerShell. Expose named operations such as read/search/write/apply-patch, format, lint, typecheck, build, tests, security checks, Git status/diff/commit.

Dependency install, directory deletion, migration, network access, authentication, workflow, deployment, and protected-path changes are restricted operations.

Every consequential action is evaluated by OPA using project/run/role, operation, command template, working directory, paths, network, secret requirement, and expected side effect.

Never trust exit code alone. Verify the resulting file hash, Git commit, PR head, auto-merge state, deployment version, or health result.

## 10. Worktrees and protected boundaries

Every run uses `C:\Factory\worktrees\RUN-<id>` and branch `factory/RUN-<id>-<slug>`. Never modify the primary checkout, reuse a worktree, or delete evidence before durability is confirmed.

Worktrees are not security sandboxes. Combine them with a restricted account, ACLs, command broker, OPA, and allowed write roots.

Protected paths include factory governance, control data, production workflows, environment files, authority code, emergency-stop scripts, and secret configuration. A protected-path change may not auto-merge.

## 11. Sealed QA and verification

Create hidden acceptance specifications before implementation. Keep them out of builder-readable storage. Builder receives only an observable failure envelope, allowed fix scope, and attempt number.

Verification order:

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
15. Accessibility
16. Visual regression
17. Performance when relevant

Deterministic failures cannot be overridden by an LLM, urgency, retry exhaustion, or builder explanation.

The builder may not delete/weaken/skip/exclude failing tests, modify sealed tests, or replace final integration behavior with mocks merely to pass.

## 12. Repair and stall recovery

Default maximum repair cycles: 3. Repeating the same failure twice without measurable progress triggers stall diagnosis.

Repair input is limited to category, relevant logs, expected/actual behavior, allowed/prohibited paths, attempt, and previous patch digest.

Stop when a fix changes business meaning, touches protected paths, exhausts resources, introduces strategic ambiguity, or repository state differs from recorded state.

On stall, start a fresh diagnosis session, generate competing hypotheses, rank with evidence, execute the smallest reversible experiment, and stop if evidence does not improve.

## 13. Independent review

Reviewer session is fresh and SHA-bound. Review requirements, architecture, permissions, security, errors, data, scope, tests, mutation survival, false-pass risk, dependencies, recovery, documentation, and evidence.

Output includes pass/fail/decision status, reviewed base/head SHA, findings, covered requirements, evidence gaps, and protected-path status. Auto-merge requires current PR SHA to equal reviewed SHA.

## 14. GitHub and auto-merge

Use labels for ready, claimed, analyzing, decision-required, planning, implementing, verifying, repairing, reviewing, preview, auto-merge, deploying, validating-production, delivered, blocked, failed, and quarantined.

Required checks must have unique names for intent, authority, protected paths, format, lint, typecheck, build, unit, contract, integration, secret/static/dependency security, mutation, sealed QA, independent review, preview, preview smoke, and evidence manifest.

Auto-merge prerequisites: no unresolved business decisions, valid intent, authority allows, all checks pass, sealed and mutation pass, independent review pass, protected paths unchanged, preview pass, no conflict, valid evidence, and reviewed SHA equals head SHA.

Never push directly to `main`, never use admin bypass, never modify branch protection, and never auto-merge governance changes.

## 15. Cloudflare delivery and recovery

GitHub Actions owns Cloudflare secrets. Models and local processes may not read them. PR preview must pass before auto-merge. Push to `main` triggers production.

After deployment, verify deployed version, health, critical browser/API behavior, and project-specific invariants.

If deployment or smoke validation fails, pause new merges, record bad SHA/deployment, follow only declared recovery, verify last-known-good state, and resume only when production is known. Never invent destructive migration rollback.

## 16. Evidence graph

Link every requirement to implementation, public tests, sealed summary, mutation, security, review, preview, and production validation. The evidence manifest records SHAs, requirements demonstrated, gates, context packages, policy decisions, exceptions, unresolved questions, preview, and production.

No valid evidence manifest means no auto-merge.

## 17. Repository structure

Create root governance and documentation files, `.factory` configuration/contracts/governance/workflows/prompts/skills/templates/vendor, `.factory-control` sealed/mutation/rubrics/evidence/decisions, `factory` modules for CLI/scheduler/backlog/workflow/state/intent/routing/context/gateway/harness/policy/worktrees/verification/sealed QA/review/GitHub/deployment/recovery/evidence/telemetry/learning, profiles, scripts, tests, and GitHub workflows.

## 18. Implementation phases and gates

Execute sequentially:

1. Audit and threat model
2. Contracts and schemas
3. FactoryFlow core
4. Backlog scheduler
5. Context Broker and leakage tests
6. Model gateway and benchmarks
7. BMAD and isolated requirement challenge
8. Tool authorization and worktrees
9. Sealed QA
10. Implementation, verification, repair
11. Independent review
12. GitHub PR and auto-merge
13. Cloudflare preview and production
14. Recovery and emergency controls
15. Evidence and learning
16. End-to-end autonomous acceptance

Each phase requires documented deliverables, tests, secondary consistency check, protected-path review, checklist update, and passing commit before proceeding.

## 19. Required factory tests

Include unit, schema contract, workflow transition, SQLite recovery, claim race, context boundary, role-memory leakage, sealed confidentiality, OPA, worktree, protected path, Aider adapter, Ollama gateway, fake model, real local model smoke, GitHub adapter, SHA mismatch, Cloudflare static, production quarantine, emergency stop, and end-to-end acceptance tests.

Mocks are allowed for unit and contract tests, not as substitutes for final end-to-end acceptance.

## 20. Explicit mistakes to avoid and why

- Do not share chat history across roles: it contaminates independence.
- Do not use one agent for plan/build/test/approval: interpretation errors propagate.
- Do not expose hidden tests: the builder can overfit.
- Do not let the builder prepare reviewer context: it can frame the evidence.
- Do not decide business questions by majority vote: similar agents share bias.
- Do not treat confidence as authority: it does not create missing product truth.
- Do not allow raw shell: worktrees do not prevent host access.
- Do not trust zero exit code: side effects can be missing or wrong.
- Do not retry indefinitely: loops waste resources and can oscillate.
- Do not weaken tests: it creates false confidence.
- Do not merge a different SHA: evidence would not match shipped code.
- Do not use admin bypass: trust controls must be non-bypassable.
- Do not auto-merge governance changes: the factory cannot rewrite its authority.
- Do not continue while production is unknown: later changes compound incidents.
- Do not store raw chats as memory: unsupported assumptions become persistent.
- Do not let models reprioritize backlog: priority is business policy.
- Do not silently install Docker/VMs: RAM and capabilities are constrained.
- Do not declare completion from documentation: the live autonomous path must pass.

## 21. Definition of Done

Completion requires successful demonstration of native PowerShell UX, no required Ubuntu/Docker, local gateway, sequential inference, deterministic backlog, claims/recovery, BMAD specification, isolated critics, evidence-based synthesis, strategic decision path, context manifests, fresh sessions, builder/reviewer isolation, sealed confidentiality, worktree/protected paths, verification, bounded repair, SHA-bound review, required checks, non-bypass auto-merge, Cloudflare preview, production validation, recovery/quarantine, evidence graph, issue close and next selection, emergency stop, and governance-refusal behavior.

## 22. Execution discipline

For every phase: read requirements, inspect state, update checklist, implement smallest coherent increment, test, perform secondary consistency check, record commands/outcomes, commit only passing work, update ADRs/threat model, and proceed only after gate success. Ask the human only for genuine strategic/business or immutable-governance decisions.

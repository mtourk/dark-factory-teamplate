# Feature Factory — Master Implementation Plan

**Source documents:** `New_FEATURE_FACTORY_MASTER_PLAN.md`, `New_FEATURE_FACTORY_EXECUTION_PROMPT.md`
**Audit date:** 2026-10-05
**Companion artifacts (machine-readable, kept consistent with this file):**
`implementation-status.yml`, `backlog.yml`, `dependency-graph.yml`, `decisions.yml`,
`blockers.yml`, `verification-index.yml`, `execution-journal.md`, `phases/phase-00..20-*.yml`

This file is the narrative read of the audit. Every claim below is backed by a file:line citation
or a test result recorded in one of the YAML artifacts above — nothing here is asserted without
that backing. Status taxonomy throughout: `not_started`, `partially_implemented`,
`implemented_unverified`, `verified_complete`, `blocked` (per master plan §0.1).

---

## 1. Headline finding

The repository is a real, working implementation of the **old** plan
(`DARK_FACTORY_MASTER_PLAN.md`'s GitHub-issue-driven local factory loop), not of the new plan. The
new plan asks for a second plane entirely — a Cloud Product Plane (portal, D1, Worker APIs,
Gemini voice, BMAD conversation UI, queue/monitoring/decision pages) — that mostly does not exist
yet, plus corrections to the Local Factory Plane where it already exists but was built for a
different (issue-driven, non-conversational) intake model.

Three things make this better news than "start over," and the plan below is built around them:

1. **Several Local Factory Plane modules are genuinely solid and directly reusable as-is**:
   `factory/profiles.py`, `factory/implementation/workspace.py`, `factory/sealed_qa/runner.py`,
   and the dynamically profile-driven `factory run` CLI are all `verified_complete` with 38
   passing automated tests between them (see `verification-index.yml`). None of this needs to be
   rebuilt for the new plan — it needs to be *driven by* the new Cloud Product Plane instead of by
   a human running the CLI against a GitHub issue.
2. **Several framework-shaped modules exist but were never wired in** — `factory/context/broker.py`
   (context isolation), `factory/analysis/critics.py` (the 6 requirement critics),
   `factory/review/independent.py` (SHA-bound independent review). These are not dead ends; they
   are correctly designed scaffolding that the new plan's orchestration needs to finally call.
3. **Three real violations of the new plan's own rules are already happening**, not just risked:
   Gemini is answering BMAD questions on Ollama timeout (`FB-02`), the code-gen builder bypasses
   context isolation and reads the raw discovery conversation (`FB-07`), and the GitHub
   auto-merge call omits the exact-SHA parameter it's supposed to enforce (confirmed gap, see
   `FF-P15-01`). These must be *fixed*, not merely noted, before the phases that depend on them can
   be called complete.

**Guiding principle for everything below, taken directly from master plan §0:** migrate, don't
rewrite. Nothing working is deleted merely to match a preferred structure. Where old-plan code
already does what the new plan needs, it is extended or re-wired, not replaced.

---

## 2. What's already done (verified, with evidence)

| Area | Evidence | Status |
|---|---|---|
| Dynamic, profile-driven `factory run` CLI | `factory/cli.py`; 15 passing tests in `test_cli_run.py` | `verified_complete` (`FF-P19-01`) |
| Profile system (multi-project, no hardcoding) | `factory/profiles.py`; 5 tests in `test_profiles.py` | `verified_complete` (`FF-P12-01`) |
| Workspace preparation (clone/checkout) | `factory/implementation/workspace.py`; 7 tests | `verified_complete` (`FF-P12-01`) |
| Sealed QA verification runner | `factory/sealed_qa/runner.py`; 11 tests in `test_sealed_qa_runner.py` | `verified_complete` (`FF-P14-01`) |
| Gemini ephemeral-token minting (voice boundary pattern) | `factory/intake/worker/src/gemini.ts:56-99` | `implemented_unverified`, architecturally correct per ADR-005 |
| GitHub repo/label creation | `factory/intake/worker/src/github.ts:65-117,192-234` | `implemented_unverified`, real working API calls |
| Context isolation mechanism (hashing, exclusions, tamper detection) | `factory/context/broker.py:81-99,196-311,341-393` | `implemented_unverified`, correct but never called |
| Bounded repair cycle | `factory/implementation/repair.py:76,118-123` | `verified_complete`, correctly enforces `MAX_REPAIR_CYCLES=3` |
| SHA-bound review gate logic | `factory/review/independent.py:95-100,305-344` | `implemented_unverified`, correct but never wired into orchestrator |
| Deploy post-check (version/health) | `factory/deploy/cloudflare_adapter.py:211-291` | `implemented_unverified` |

Full detail and file:line citations for all 29 audited items: `implementation-status.yml`.

---

## 3. What's broken right now (not just missing — actively wrong)

These three must be fixed early; several later phases depend on the fix, not just on the feature
existing.

1. **FB-02 — Gemini answers BMAD questions.** `factory/intake/worker/src/gemini.ts:216-321`
   (`getDiscoveryResponseFromGemini`, `getDiscoverySystemPrompt`) runs whenever local Ollama
   times out — the common case on current hardware per
   `docs/operations/INTAKE_DEPLOYMENT_PLAYBOOK.md`. This violates §4.2 and critical mistake #3
   outright, today, for every conversation that has hit the fallback. **Fix:** delete the
   reasoning path; replace the timeout fallback with a queued retry or an explicit "model busy"
   state, never a cloud-LLM substitution. See `blockers.yml:FB-02`.
2. **FB-07 — Builder bypasses context isolation.** `factory/implementation/builder.py:44,490-495`
   feeds the raw discovery Q&A transcript directly into the code-generation prompt, never calling
   `ContextBroker`. This violates §11 and critical mistake #10. **Fix:** remove
   `BuilderInput.raw_conversation`; route through `ContextBroker.assemble_role_context()` instead;
   add a regression test asserting the builder prompt never contains literal discovery-message
   text. See `blockers.yml:FB-07`.
3. **Confirmed correctness gap — auto-merge omits `sha=`.**
   `factory/backlog/github_adapter.py:316-340` (`enable_auto_merge`) calls
   `PUT .../pulls/{pr}/merge` without GitHub's optional `sha=` parameter, so exact-SHA enforcement
   (§15, critical mistake #15) is not actually applied at the real API call site, even though the
   surrounding gate logic in `auto_merge.py` is correct. **Fix:** pass `sha=` from the validated
   `ReviewContext`. Tracked under `FF-P15-01` in `verification-index.yml`.

A fourth already-realized issue, lower urgency but real: Ollama is exposed over a public tunnel
(`ollama.mtourk.com`) from Phase 17/18 development, violating §14/critical mistake #9. Its fix is
folded into the auth decision track (§4 below) rather than tracked as its own code change, since
taking the tunnel down is the natural first consequence of standing up real portal auth.

---

## 4. Decisions — all four now resolved (2026-10-05)

All four decisions were open as of the Phase 00 audit; the user decided all four on 2026-10-05,
all choosing Option A (recorded in full, with the user's exact wording, in `decisions.yml`):

| ID | Decision | Chosen | What it unblocked |
|---|---|---|---|
| `D-NEW-002` | Auth model for the portal | **A**: Cloudflare Access only, no custom auth code — user's explicit reason: "I need this to be simple." (Agent had recommended hybrid Option C; user chose simplicity instead — can revisit later if per-user state is needed.) | `FF-P03-01` (now implemented_unverified, commit `7c854a2`) → `FF-P04-01`, `FF-P07-01`, `FF-P09-01/02` |
| `D-NEW-004` | Where BMAD reasoning runs | **A**: Local-Ollama-routed | `FF-P07-01` (still `not_started`/blocked on `FB-04` — decision alone doesn't build the engine) |
| `D-NEW-001` | Frontend stack for `factory/intake/web` | **A**: Extend vanilla JS in place | `FF-P04-01` (now the next eligible item) |
| `D-NEW-003` | Where cloud-side secret values live | **A**: Cloudflare Workers Secrets | `FF-P03-02` |

With all four decided, the gating that blocked Phases 03/04/07/09 on a human choice is gone.
What's left on each is implementation work and the human-only dashboard/credential steps noted
in `blockers.yml` (`FB-10`, `FB-08`, `FB-01`) — not further decisions.

---

## 5. The 21-phase roadmap, status at a glance

Phase titles and deliverables are copied verbatim from master plan §16. Full per-item status
lives in `phases/phase-NN-*.yml`; this is the overview.

| # | Phase | Overall status | Blocking on |
|---|---|---|---|
| 00 | Repository and deployment audit | `verified_complete` | — (this document) |
| 01 | Configuration and installation portability | `not_started` | nothing — can start anytime |
| 02 | D1 schema and migrations | `partially_implemented` | `FB-05` (apply unapplied migrations) |
| 03 | Authentication, admin, profiles, secret settings | `partially_implemented` | `FF-P03-01` code shipped & tested (commit `7c854a2`); `FB-10` (Access Application dashboard step, human), `FB-01` (token rotation, human) |
| 04 | Responsive application shell | `not_started` — now the next eligible item | nothing (dependency `FF-P03-01` and decision `D-NEW-001` both resolved) |
| 05 | Idea drafts and text intake | `partially_implemented` | `FF-P04-01` |
| 06 | Gemini voice integration | `blocked` | `FB-02` (must be fixed, not just noted) |
| 07 | BMAD conversation service | `not_started` | `FB-04`, `D-NEW-004`, `FF-P03-01` |
| 08 | Live requirement/acceptance draft | `partially_implemented` | `FF-P07-01` |
| 09 | Repository selection and creation | `partially_implemented` | `FF-P03-02` |
| 10 | Cloudflare project/resource provisioning | `not_started` | `FB-06`, `FF-P09-02` |
| 11 | Cloud-local queue and connectivity | `not_started` | `FB-05` |
| 12 | FactoryFlow and local gateway integration | `partially_implemented` | `FB-07` resolved (commit `a6d24e8d`, 2026-10-05); `FB-09` (newly found: `ContextBroker` itself has 3 bugs, fix in progress) |
| 13 | Critics, decision agent, and decision page | `partially_implemented` | `FF-P12-02`, `FF-P04-01` |
| 14 | Sealed QA, verification, repair, reviewer | `partially_implemented` | wiring independent review into orchestrator |
| 15 | GitHub PR, preview, auto-merge | `partially_implemented` | `sha=` fix (§3 above), `FF-P14-03` |
| 16 | Production deployment and recovery | `partially_implemented` | `FB-08` (human-gated deploy) |
| 17 | Monitoring and controls | `not_started` | `FB-08`, `FF-P11-01`, `FF-P04-01` |
| 18 | Notifications and request lifecycle | `not_started` | `FF-P11-01`, `FF-P04-01` |
| 19 | Status-driven self-continuation | `partially_implemented` | — (CLI layer done; cloud layer not started) |
| 20 | Full pilot on existing repository | `not_started` | everything above |

---

## 6. Execution strategy: three parallel tracks

The dependency graph (`dependency-graph.yml`) shows the work is not one long chain — three tracks
can proceed independently once their respective decisions land, then converge at Phase 20.

**Track A — Portal & conversation (the product surface).**
`D-NEW-002` decided → `FF-P03-01` (auth) → `FF-P04-01` (app shell) → in parallel: `FF-P05-01`
(text intake), `FF-P06-01` (voice, after `FB-02` fixed), and — gated by `D-NEW-004` —
`FF-P07-01` (BMAD engine) → `FF-P08-01` (live draft) → `FF-P09-01/02` (repo selection/creation,
also gated by `FF-P03-02`/secrets decision) → `FF-P10-01` (Cloudflare provisioning).

**Track B — Local factory correctness (fixing what's wired wrong).**
Independent of Track A. Fix `FB-07` (context isolation in `builder.py`) → wire `ContextBroker`
into the orchestrator generally → wire `factory/analysis/critics.py` and
`factory/review/independent.py` into `run_full_cycle` (closing the `FF-P13-01`/`FF-P14-03` gaps)
→ fix the `sha=` omission in `enable_auto_merge()` → `FF-P15-01` real exact-SHA auto-merge.

**Track C — Queue, monitoring, deploy (connecting the planes).**
Apply the unapplied D1 migrations (`FB-05`) → `FF-P11-01` (queue/connectivity) → `FF-P17-01`
(monitoring/admin controls) and `FF-P18-01` (notifications), both also needing `FF-P04-01` from
Track A. `FF-P16-01` (production deploy) sits downstream of Track B's merge work and remains
partially human-gated per `FB-08` regardless of what else is finished.

**Convergence — Phase 20 full pilot** requires every track's listed items at
`verified_complete`: it is the end-to-end proof, not a phase with its own independent code.

This is also exactly the order `backlog.yml`'s `next_eligible_item` logic will keep selecting from
as items get resolved — `FF-P03-01` is first because it is the highest-priority item with zero
unmet dependencies today.

---

## 7. How completion is enforced (per execution prompt)

Per `New_FEATURE_FACTORY_EXECUTION_PROMPT.md`'s completion gate and this plan's own
`verification-index.yml`, no item moves to `verified_complete` without: working code, passing
acceptance criteria, passing tests, a security/context-boundary check where relevant, an entry in
`verification-index.yml`, updated docs, an updated dependency graph, and the next item identified
— and the current item's status is committed before starting the next one. The 38 passing tests
already in the repo are the only hard evidence backing any `verified_complete` claim made in this
audit; every other `verified_complete` marking in `implementation-status.yml` is explicitly an
audit-deliverable claim about this audit's own accuracy, not a claim that the audited feature
itself is finished — `verification-index.yml`'s `summary:` block states this distinction
explicitly so it can't be misread later.

---

## 8. Status as of 2026-10-05 (post-decisions) and immediate next steps

All four original decisions are made; the three originally-parallel tracks the user asked for are
done and independently re-verified (not just agent-reported):

- **FF-P03-01 (auth)** — `implemented_unverified`, commit `7c854a2`, 11/11 tests passing.
- **FB-07 (context isolation in builder.py)** — `resolved`, commit `a6d24e8d`, 5/5 new tests
  passing, no regressions in the 29-test builder suite.
- **FB-05 (D1 migrations)** — `resolved`, `schema_phase18.sql` applied to production D1.

Two new items surfaced while finishing that work (neither existed at Phase 00 audit time):

- **`FB-09`** — `ContextBroker.assemble_role_context()` has 3 pre-existing validation bugs and
  raises for every role. Not a decision; a fix is in progress (dispatched 2026-10-05).
- **`FB-10`** — the real Cloudflare Access Application still needs creating in the Cloudflare
  dashboard before `FF-P03-01` is actually live in production (human-only step, like `FB-01`'s
  token rotation and `FB-08`'s deploy gating).

**Next steps:**
1. **No decision needed, in progress:** fix `FB-09` (`ContextBroker`'s three bugs) — agent
   dispatched, not yet complete.
2. **No decision needed, next eligible item per `backlog.yml`:** `FF-P04-01`, the application
   shell (D-NEW-001 extend-vanilla-JS approach), now unblocked since `FF-P03-01` has shipped.
3. **No decision needed, parallelizable:** `FF-P07-01` (BMAD engine, D-NEW-004 local-Ollama-
   routed) is also now unblocked by `FF-P03-01`, but still gated by `FB-04` (no real engine code
   exists yet) — this is a build task, not a decision wait.
4. **Human action, not agent-executable, no urgency tied to a phase:** rotate the leaked
   Cloudflare token (`FB-01`); create the Cloudflare Access Application (`FB-10`).

This plan, and the YAML artifacts it summarizes, are the standing source of truth for the
project. Per the execution prompt's resume protocol, any future session should read
`implementation-status.yml` and `backlog.yml` first, confirm `next_eligible_item` is still
accurate, and continue from there rather than re-auditing from scratch.

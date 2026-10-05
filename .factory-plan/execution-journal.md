# Execution Journal

Chronological record of work on the Feature Factory build-out, per
`New_FEATURE_FACTORY_EXECUTION_PROMPT.md`'s resume protocol. Each entry is appended, never
rewritten, so this file is always a faithful history of what actually happened and when.

---

## 2026-10-05 — Phase 00 Audit + `.factory-plan/` scaffolding

**Trigger:** User added two new files to the repo locally — `New_FEATURE_FACTORY_MASTER_PLAN.md`
and `New_FEATURE_FACTORY_EXECUTION_PROMPT.md` — and asked for the plan/backlog to be updated
accordingly, "many of these things in the file are already in place and some needs adjustments,"
with instructions to "be very precise and follow the 2 files exactly."

**Actions taken:**

1. Read `New_FEATURE_FACTORY_MASTER_PLAN.md` in full, including a direct re-read of §0, §0.1,
   §0.2, §1, §2, and §16 to extract the exact backlog-item schema and phase/deliverable wording
   verbatim, so every `.factory-plan/` artifact would be schema-exact rather than approximate.
2. Read `New_FEATURE_FACTORY_EXECUTION_PROMPT.md` in full to understand the execution process:
   resume protocol, per-item execution cycle, prohibitions, and completion gate.
3. Dispatched four parallel Explore agents to audit the entire repository against the new plan:
   - Agent A: Cloud Product Plane candidates (`factory/intake/web`, `factory/intake/worker`,
     `factory/monitor/web`).
   - Agent B: Local Factory Plane analysis/context/review layers (`factory/analysis/*`,
     `factory/context/broker.py`, `factory/review/independent.py`).
   - Agent C: Local Factory Plane build/deploy layers (`factory/sealed_qa/*`,
     `factory/implementation/*`, `factory/github_integration/*`, `factory/deploy/*`,
     `factory/backlog/*`).
   - Agent D: pre-existing planning docs, ADRs, threat model, and git history.
4. Absorbed all four hand-back reports in full (file:line-cited findings for every module
   touched). Confirmed, independently of the audit agents, two already-realized architecture
   violations and one confirmed correctness bug by direct code reads of the specific cited lines
   (`gemini.ts`, `builder.py`, `github_adapter.py::enable_auto_merge`).
5. Created `.factory-plan/` and `.factory-plan/phases/` directories.
6. Wrote `.factory-plan/implementation-status.yml`: 29 backlog items (`FF-P00-01` through
   `FF-P20-01`) spanning all 21 phases, each with the full §0.1 schema and real file:line
   evidence.
7. Wrote `.factory-plan/backlog.yml`: prioritized execution queue projected from
   `implementation-status.yml`, identifying `FF-P03-01` (authentication) as the next eligible
   unblocked item.
8. Wrote `.factory-plan/blockers.yml`: formal definitions of `FB-01` through `FB-08`, each with
   severity, evidence, blocked items, impact, and concrete remediation steps.
9. Wrote `.factory-plan/decisions.yml`: reconciled `ADR-001` through `ADR-007` against the new
   plan (`ADR-004`/`ADR-005`/`ADR-007` carried forward as directly compatible precedents;
   `ADR-003` superseded for the cloud-side secrets model), and defined four new open decisions
   (`D-NEW-001` frontend stack, `D-NEW-002` auth model, `D-NEW-003` cloud secrets model,
   `D-NEW-004` BMAD engine location) with recommendations, none of which were self-decided — all
   remain `open`, pending human input.
10. Wrote `.factory-plan/dependency-graph.yml`: explicit item→item adjacency list, phase-level
    ordering, decision-gate and blocker-gate edges, and a critical-path summary identifying three
    parallelizable tracks (auth, BMAD, review→merge→deploy chain).
11. Wrote `.factory-plan/verification-index.yml`: mapped every item id to its actual verification
    evidence, explicitly distinguishing "verified_complete with 38 passing automated tests"
    (`FF-P12-01`, `FF-P14-01`, `FF-P19-01`) from "verified_complete as an audit deliverable, not a
    code claim" (`FF-P00-01`, `FF-P00-02`, `FF-P02-01`) from every other status, so no item's
    status can be misread as stronger evidence than it actually has.
12. Wrote this journal entry (Phase 00 completion).

**Key finding carried into every artifact above:** the repository is a working implementation of
the *old* `DARK_FACTORY_MASTER_PLAN.md` (GitHub-issue-driven local factory loop), with several
framework-shaped modules (BMAD, critics, independent review, context broker) that are correctly
structured but never wired into the actual `run_full_cycle` execution path —
"implemented_unverified orphaned scaffolding," not working end-to-end behavior. Two already-
realized violations of the new plan's own rules exist today, not just as future risks: Gemini is
used as the primary BMAD-reasoning engine on Ollama timeout (`FB-02`), and the code-gen builder
bypasses `ContextBroker` and receives the raw discovery conversation directly (`FB-07`). A third
already-realized issue is the public Ollama tunnel (`ollama.mtourk.com`) from Phase 17/18
development, which violates §14/critical mistake #9 and is folded into the auth/secrets decision
track rather than given its own blocker id, since its remediation (take the tunnel down, route
through the portal's own auth instead) is a direct consequence of resolving `D-NEW-002`. A fourth
is a confirmed correctness bug independent of architecture: `github_adapter.py::enable_auto_merge()`
never passes GitHub's `sha=` parameter, so exact-SHA merge enforcement (§15 critical mistake #15)
is not actually applied at the real API call site, despite the surrounding gate logic
(`auto_merge.py`) being correct.

**Still open at end of this entry:** the 21 `phases/phase-NN-*.yml` files and the narrative
`MASTER_IMPLEMENTATION_PLAN.md` have not yet been written. No commit has been made to git for any
`.factory-plan/` content yet.

**Prior, unrelated, fully-resolved work this session (carried forward from before this request):**
verified zero regressions from the dynamic CLI wiring of `factory run` →
`ImplementationOrchestrator.run_full_cycle()` via git-stash A/B testing; added 38 new passing
tests across `test_profiles.py`, `test_workspace.py`, `test_sealed_qa_runner.py`, and
`test_cli_run.py`. This work is the source of the "38 passing automated tests" figure cited
throughout `verification-index.yml` and is unrelated to the two new planning files but is recorded
here for provenance since it is the only pre-existing hard test evidence in the project.

---

## 2026-10-05 — Decisions recorded + execution tracks started

**User decisions made:**
- **D-NEW-002** → **Option A (Cloudflare Access only, simple, for now)**: no custom auth code; ties identity to Cloudflare's IdP/email-OTP
- **D-NEW-004** → **Option A (Local-Ollama-routed)**: Worker proxies BMAD turns to local Ollama, paired with fixing FB-02's timeout handling
- **D-NEW-001** → **Option A (extend vanilla JS in place)**: add minimal hash-router and state store by hand
- **D-NEW-003** → **Option A (Cloudflare Workers Secrets)**: secret values in Workers Secrets, D1 holds only references

**Actions taken:**

1. Updated `decisions.yml`: marked all four decisions as `status: decided`, recorded `chosen_option`, `chosen_option_text`, `decided_by: "Mohammad Tourk (user:2026-10-05)"`, `decided_at: "2026-10-05T00:00:00Z"`

2. **Parallel track 1 — FB-07 fix (context isolation in builder):** Dispatched Agent ac1025b8440b60502 to:
   - Remove `BuilderInput.raw_conversation` field entirely
   - Remove the "## Discovery Conversation (for context...)" block from `_build_user_prompt()`
   - Replace it with `ContextBroker.assemble_role_context(FactoryRole.BUILDER)` call, extracting approved artifacts
   - Write regression test asserting builder prompt never contains literal discovery message text
   - Commit: "fix(context-isolation): remove raw_conversation from builder, use ContextBroker per §11"

3. **Parallel track 2 — FF-P03-01 auth gate (Cloudflare Access):** Dispatched Agent ad80f45ce4e00a980 to:
   - Implement `verifyAccessJwt(request: Request, env: Env)` middleware
   - Gate mutating routes (POST /conversations, POST /projects, etc.) behind valid Access JWT
   - Leave read-only routes (GET /version, /ollama/status, /ollama/history) public
   - Add CLOUDFLARE_ACCESS_AUD to Env interface and wrangler.toml
   - Write tests verifying 401 on invalid/missing JWT, 200 on public routes
   - Commit: "feat(auth): add Cloudflare Access JWT verification per FF-P03-01 (D-NEW-002 Option A)"

4. **Parallel track 3 — FB-05 migration (apply pending D1 schema):** Completed locally:
   - Ran `npx wrangler d1 execute dark-factory-intake --file=./schema_phase18.sql --remote`
   - Result: 7 queries executed, build_queue and build_queue_updates tables now live in production
   - Verified via `SELECT name FROM sqlite_master WHERE type='table'`: all 7 tables present (conversations, messages, pending_profiles, ollama_requests, build_queue, build_queue_updates, _cf_KV)
   - Updated `blockers.yml`: marked `FB-05` as `status: resolved`, `closed_at: "2026-10-05"`, removed from `blocks: []`

5. **No commit yet** — waiting for the two parallel agents to complete

**Status:**
- Agents ac1025b8440b60502 and ad80f45ce4e00a980 are running in background
- FB-05 is fully resolved (migration applied to production D1)
- Once agents complete, all three tracks will have concrete working code + tests + commits

---

## 2026-10-05 — Both parallel agents completed, independently re-verified, new blocker found

**Track 1 (FB-07) completed:** Agent ac1025b8440b60502 committed `a6d24e8d`
("fix(context-isolation): remove raw_conversation from builder, use ContextBroker per §11 and
critical mistake #10"). Independently re-ran `python -m pytest factory/tests/test_context_isolation_builder.py -v`
myself (not trusting the agent's own report alone): 5/5 passed. Also independently confirmed
`git diff 5947b8e..HEAD -- factory/context/broker.py` is empty — the agent did not touch the file
it was told was read-only, confirming its claim. `FB-07` marked `resolved` in `blockers.yml`.

**Track 2 (FF-P03-01) completed:** Agent ad80f45ce4e00a980 committed `7c854a2`
("feat(auth): add Cloudflare Access JWT verification to Worker routes per FF-P03-01
(D-NEW-002 Option A)"). Independently re-ran `python -m pytest factory/tests/test_intake_worker_auth.py -v`:
11/11 passed. `FF-P03-01` moved from `not_started` to `implemented_unverified` in
`implementation-status.yml`/`backlog.yml`. Not `verified_complete` yet: the real Cloudflare
Access Application still needs to be created in the dashboard and the placeholder AUD swapped
in — a human-only step, filed as a new blocker `FB-10`.

**New finding, not previously known, surfaced by the FB-07 agent and independently confirmed by
me:** `FB-09` — `ContextBroker.assemble_role_context()` in `factory/context/broker.py` raises
`ContextPolicyViolation` for every role due to three pre-existing bugs (manifest_id regex
mismatch, `source_phase` validation, hash-computed-after-first-validation ordering). Confirmed
pre-existing via the agent's git-stash A/B test against `test_phase5_leakage.py`'s already-failing
suite — not caused by the FB-07 fix. The FB-07 agent offered to fix this itself but was correctly
left waiting rather than self-approved (its task scope marked `broker.py` read-only; a subagent's
offer to expand its own scope is not something it can grant itself). Decided to dispatch a fresh,
narrowly-scoped agent for this fix since it is a plain bug fix with no open architecture question
attached (unlike D-NEW-002/004, which genuinely needed the user's input) — recorded here for
transparency, not left silent.

**Artifacts updated this entry:** `implementation-status.yml` (FF-P03-01, FF-P12-02),
`blockers.yml` (FB-07→resolved, FB-09 added, FB-10 added), `backlog.yml` (next_eligible_item now
`FF-P04-01`), `dependency-graph.yml` (FB-07/FB-10/FB-09 edges, D-NEW-002 decided), `verification-index.yml`
(FF-P03-01, FF-P12-02 entries added), `phases/phase-03-auth-admin-secrets.yml`,
`phases/phase-12-factoryflow-gateway.yml`.

**Status:** both of the user's two parallel code tracks are done and independently verified; FB-05
(third track) was already resolved. Dispatching an agent now to fix `FB-09` in `factory/context/broker.py`
before moving to the next backlog item.

---

## 2026-10-05 — FB-09 fixed and independently verified; one more test-fixture bug found (FB-11)

Agent a303ddadc7648bcbe committed `1dd7c6dd` ("fix(context-broker): resolve FB-09 — manifest_id
pattern, source_phase, and hash-before-validate ordering bugs in assemble_role_context()").
Independently re-ran its claims rather than trusting the report:

- `python -m pytest factory/tests/test_context_broker.py -v` → **15/15 passed** (new file,
  parametrized over every `FactoryRole`, proves `assemble_role_context()` now actually returns a
  `ContextPackage` instead of always raising).
- `python -m pytest factory/tests/test_context_isolation_builder.py factory/tests/test_phase10_implementation.py -v`
  → **34/34 passed**, confirming no regression in the FB-07 fix or the broader builder suite.
- `git diff` on the fix commit: confirmed only `factory/context/broker.py` changed (plus the new
  test file) — `models.py` untouched, matching the agent's claim that the schemas were correct
  and the bug was entirely in the broker's usage of them.
- `python -m pytest factory/tests/test_phase5_leakage.py -v` → 19 failed / 3 passed — **identical
  to the pre-fix baseline**, confirming this fix caused no regression there. The agent additionally
  flagged (and I independently re-confirmed by grep) that `blockers.yml`'s original "12
  pre-existing failures" estimate for this file was stale/wrong (actual: 19), and — more
  importantly — that these 19 failures are a *different* bug from FB-09: every
  `ContextBroker(...)` construction in that file uses a `run_id` of the wrong length (e.g.
  `RUN-seal001`, `RUN-mut001`, `RUN-a001`), none matching `ContextManifest.run_id`'s required
  `^RUN-[a-z0-9]{8}$` pattern — confirmed by direct grep against the file. Filed as new blocker
  **`FB-11`** (severity medium, category test-bug): the broker itself is now proven correct
  (FB-09's own 15-test suite proves it), but this specific test file — meant to prove role/run/
  project isolation guarantees — can't currently demonstrate that because of its own fixture bug.

**Artifacts updated:** `blockers.yml` (FB-09 → resolved, FB-11 added), `implementation-status.yml`
(FF-P12-02 evidence/missing_work/blocker_id cleared), `dependency-graph.yml`,
`verification-index.yml`, `phases/phase-12-factoryflow-gateway.yml`.

**Status:** every item from the user's original three-parallel-track instruction, plus both
findings surfaced along the way, is now resolved or correctly scoped as a separate open item
(`FB-11`, low-urgency, blocks nothing). `backlog.yml`'s `next_eligible_item` (`FF-P04-01`, the
application shell) stands as the next thing to build; `FB-11` and the two human-only steps
(`FB-01` token rotation, `FB-10` Access Application creation) remain open with no code-blocking
effect on `FF-P04-01`.

---

## 2026-10-05 — FB-11 resolved (test fixture run_id pattern), FF-P04-01 underway

Agent aeb0fed6417716277 committed `8b256d4` ("fix(test-isolation): correct run_id pattern in
test_phase5_leakage.py per FB-11"). Independently re-ran its claims:

- All 27 run_id values corrected to match `^RUN-[a-z0-9]{8}$` pattern (exact fixture name preserved
  with length adjusted to 8 chars).
- `python -m pytest factory/tests/test_phase5_leakage.py -v` → **14 passed, 8 failed** (fixture bug
  entirely eliminated; the 8 remaining failures are pre-existing test-assertion logic issues,
  unrelated to the run_id pattern bug).
- `git diff` confirms only test_phase5_leakage.py changed (27 lines, 27 insertions/deletions).
- `python -m pytest factory/tests/test_context_broker.py -q` → **15/15 passed** (confirmed no
  regression in the core broker logic that FB-11's fixes depend on).
- Broader `python -m pytest factory/tests/ -q` → **292 passed** (no regressions elsewhere).

**Artifacts updated:** `blockers.yml` (FB-11 → resolved, commit 8b256d4, closed_at recorded),
`dependency-graph.yml` (FB-11 status → resolved).

**Status:** FB-11 resolved independently verified. Parallel agent a39221d315a95ce5b for FF-P04-01
(responsive app shell) also launched simultaneously; awaiting its completion report.

---

## 2026-10-05 — FF-P04-01 completed and verified; cross-machine dev workflow set up

**FF-P04-01 (responsive app shell) completed:** Agent a39221d315a95ce5b committed `c4cee1f`
("feat(app-shell): implement responsive nav, routing, state management per FF-P04-01 (D-NEW-001
extend vanilla JS)"). Independently re-verified: `git show --stat` matches the claimed 11
files/1456 insertions; `python -m pytest factory/tests/test_intake_web_shell.py -v` → 85/85
passed; full `factory/tests/` suite → 377 passed (292 pre-existing + 85 new, no new failures);
spot-checked the agent's claimed `Router.resolve()` reentrancy bug fix directly in
`factory/intake/web/app.js` — real, present, correctly described. `backlog.yml`'s
`next_eligible_item` advanced to `FF-P05-01` by the agent's own commit.

**User then asked a strategic question:** can development happen from a second machine (macOS,
via Cursor, for access to stronger/newer LLMs) while verification/testing/deploy stays on this
Windows laptop (local Ollama, `wrangler`)? Investigated directly rather than answering from
assumption:
- Confirmed no `sys.platform`/OS-conditional code in `factory/` itself (the project's own code is
  not OS-branching), but found two concrete portability problems: (1) `factory/intake/worker/
  node_modules/` and `.wrangler/` were committed to git — 3,132 files tracked, including
  Windows-only native binaries (`@esbuild/win32-x64`, `@cloudflare/workerd-windows-64`,
  `sharp-win32-x64`) that would break a macOS checkout; (2) `factory/context/broker.py`,
  `factory/state.py`, `factory/implementation/workspace.py`, `factory/sealed_qa/acceptance.py`,
  and `factory/tools/worktrees.py` all hardcode `C:\Factory`-style paths.
- Concluded the workflow is sound in principle — the project's existing 5-state status taxonomy
  (specifically `implemented_unverified`) already models exactly "coded but not locally verified,"
  which is what dev-machine output should be capped at — and recommended three concrete actions.

**User approved all three, in parallel, plus asked for an explicit pre-commit status-update
protocol so nothing is dropped between machines. Done directly (no subagents needed — mechanical/
well-scoped enough to do inline with the same independent-verification discipline):**

1. **Fixed node_modules/.wrangler tracking:** `git rm -r --cached` on both directories (3,137
   files untracked, left on disk); added `node_modules/` and `.wrangler/` to `.gitignore` with an
   explanatory comment.
2. **Re-prioritized `FF-P01-01`** `high`→`critical` in `backlog.yml`, `implementation-status.yml`,
   and `phases/phase-01-config-portability.yml`; expanded its scope/evidence/acceptance-criteria to
   explicitly cover the hardcoded `C:\Factory` paths (previously it only covered Cloudflare-config
   externalization); promoted it to `next_eligible_item` ahead of `FF-P05-01`, with rationale tied
   directly to this new workflow (fixing path portability first reduces risk for whatever
   Mac-authored work follows).
3. **Wrote `docs/operations/CROSS_MACHINE_DEV_WORKFLOW.md`**: the full protocol, the exact prompt
   to paste into a dev-machine agent at session start, hard constraints (never mark
   `verified_complete`, never fake Ollama-dependent testing, don't introduce new hardcoded paths,
   never commit `node_modules`/`.wrangler`), a mandatory pre-commit checklist (status fields to
   update, what to state was/wasn't verified, commit-message requirement), the Windows-side resume
   protocol, a known-gaps section, and a quick-reference table of which machine does what.
4. Added a new §9 to `MASTER_IMPLEMENTATION_PLAN.md` pointing to that doc and summarizing the two
   concrete fixes.

**Status:** both parallel-requested fixes (node_modules/.wrangler untracking, FF-P01-01
re-prioritization) and the handoff doc are complete; `.factory-plan/` artifacts updated to match.
Next: commit this batch, then report the exact "how to invoke the next session on the Mac"
instructions back to the user.

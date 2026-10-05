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

# Cross-Machine Development Workflow

**Status:** Living document. Append to it — don't let future sessions relearn these lessons.
**Scope:** Developing against the `.factory-plan/` backlog from a machine that cannot run the
full verification stack (no local Ollama, possibly a different OS — e.g. macOS via Cursor),
while verification/testing/deploy stays on the primary Windows laptop (local Ollama models,
`wrangler`, the full `pytest` suite).
**Audience:** Any human operator, and any agent (Cursor, Claude Code, etc.) picking up work on
either machine. If you are an agent reading this because you were just asked to continue the
Feature Factory build-out, read this file in full before touching anything.

**Why this exists:** the Feature Factory backlog is big enough that development is faster with
two machines in rotation — one with access to stronger/newer LLMs for authoring and review (e.g.
a Mac running Cursor), one that holds the actual test/runtime prerequisites (local Ollama models,
Windows-specific paths, `wrangler` deploy credentials). Git is the only handoff mechanism between
them. This file defines the protocol so nothing silently gets marked more "done" than it is.

---

## 1. The model

- **Git + `.factory-plan/*.yml` is the single source of truth.** Not Slack, not memory, not a
  chat transcript — the YAML artifacts (`implementation-status.yml`, `backlog.yml`,
  `dependency-graph.yml`, `blockers.yml`, `verification-index.yml`) and `execution-journal.md`.
  Whoever picks up next (human or agent, on either machine) reads these first.
- **The existing 5-state status taxonomy already supports this split** — nothing new was
  invented:
  - `not_started` → `implemented_unverified` → `verified_complete` is the normal path.
  - **A dev-machine session (no local Ollama/Windows/wrangler access) may only move an item as
    far as `implemented_unverified`.** It must never write `verified_complete` for anything it
    could not actually run end-to-end.
  - The verification-capable machine (this Windows laptop) is the only one that promotes an item
    to `verified_complete`, and only after independently re-running the tests itself — per this
    project's standing "evidence over claims" discipline (see `execution-journal.md`'s entries:
    every subagent/session's self-report has always been independently re-verified before being
    trusted, never taken at face value — this applies across machines exactly the same way it
    applies across agents).
- **Ollama is local-only** (`http://localhost:11434`, see `factory/cli.py`,
  `factory/gateway/ollama_gateway.py`, `factory/implementation/builder.py`). A dev machine has no
  route to it except the already-flagged-insecure public tunnel
  (`https://ollama.mtourk.com`, tied to blocker `FB-02`). **Do not use that tunnel as a substitute
  for local testing** — it's a known violation already queued for remediation, not a sanctioned
  bypass.

---

## 2. What to paste into the dev-machine agent (Cursor, Claude Code, etc.) at the start of a session

```
Read .factory-plan/execution-journal.md's most recent entries, then
.factory-plan/implementation-status.yml and .factory-plan/backlog.yml. Confirm backlog.yml's
next_eligible_item is still accurate given the current state of the repo (git log, git status).

Implement that item. You do NOT have local Ollama, Windows-specific paths, or wrangler deploy
credentials on this machine — you cannot fully verify your own work. Follow
docs/operations/CROSS_MACHINE_DEV_WORKFLOW.md section 3 (hard constraints) and section 4
(mandatory pre-commit checklist) exactly. Cap your own status claim at `implemented_unverified`,
never `verified_complete`. Write tests even if you can't run all of them locally — note in your
commit and in execution-journal.md exactly which verification steps you could not perform and why.

When done: update the relevant .factory-plan/*.yml files per the schema already in use (follow
the pattern of existing entries, don't invent new fields), append an execution-journal.md entry,
commit, and push.
```

---

## 3. Hard constraints for dev-machine (e.g. macOS/Cursor) sessions

1. **Never mark anything `verified_complete`.** The ceiling is `implemented_unverified`. This is
   not a formality — the next machine trusts this field to decide whether re-testing is required.
2. **Never attempt to exercise Ollama/BMAD-dependent code paths as "testing."** There is no
   legitimate local substitute on a machine without the model running. If a feature genuinely
   needs that to be verified, say so explicitly and leave it unverified — don't fake it with a
   mock and call it proof.
3. **Don't introduce new hardcoded Windows paths**, and watch for existing ones. `factory/context/
   broker.py`, `factory/state.py`, `factory/implementation/workspace.py`,
   `factory/sealed_qa/acceptance.py`, and `factory/tools/worktrees.py` currently hardcode
   `C:\Factory`-style paths (tracked as the critical half of `FF-P01-01` — see
   `implementation-status.yml`). If your backlog item touches any of these files, either route
   through `factory/profiles.py`'s existing profile mechanism or flag the conflict rather than
   guessing at a Windows path you can't verify.
4. **Never commit `node_modules/` or `.wrangler/`.** Both are now gitignored (fixed 2026-10-05 —
   they were previously, wrongly, committed: 3,132 files including Windows-only native binaries
   like `@esbuild/win32-x64` and `@cloudflare/workerd-windows-64`, which is exactly the kind of
   silent cross-platform breakage this workflow exists to prevent). Run your own `npm install` per
   machine; never try to reuse another machine's `node_modules`.
5. **Node-based tests you *can* run and should**: the esbuild+Node-driver pattern
   (`factory/tests/helpers/worker_auth_driver.mjs`, `factory/tests/helpers/app_shell_driver.mjs`)
   drives real bundled TypeScript/JS and works on any OS with Node installed. If your item touches
   `factory/intake/worker/` or `factory/intake/web/`, run these — they're genuine evidence, not a
   substitute for the Windows-side `pytest` pass, but real evidence nonetheless. Say which you ran.
6. **Python tests**: most of `factory/tests/` (pytest, pydantic-based) are OS-portable in
   principle, except for the hardcoded-path files in constraint 3. If you have Python available
   and can run them, do — it's still not a substitute for the full Windows-side pass (which also
   covers Ollama-dependent behavior), but it narrows what the Windows side needs to re-check.
7. **Stay in scope.** Pick exactly `next_eligible_item` (or whatever the human explicitly asked
   for) — don't opportunistically touch unrelated files, and don't self-approve scope expansion
   (if you find something that needs fixing outside your assigned item, flag it as a new blocker
   in `blockers.yml`, don't just fix it — see `execution-journal.md`'s existing precedent for how
   discovered-but-out-of-scope findings get recorded as new `FB-NN` entries, not silently patched).

---

## 4. Mandatory pre-commit checklist (dev machine)

**Before every commit**, confirm all of the following are true, then say so explicitly in the
commit message:

- [ ] The relevant `.factory-plan/implementation-status.yml` entry's `status` is
      `implemented_unverified` (never `verified_complete`), with `last_updated_at`/
      `last_updated_by` set.
- [ ] `verification_evidence` lists exactly what you *did* run (e.g. "Node driver: 41/41 checks
      passed") and, just as importantly, states what you could **not** run and why (e.g. "Full
      pytest suite not run — no Python/Ollama on this machine; defer to Windows-side session").
- [ ] `backlog.yml`'s matching queue entry and `next_eligible_item`/rationale are updated if your
      work changes what's unblocked next.
- [ ] `dependency-graph.yml` and the relevant `phases/phase-NN-*.yml` reflect the new status.
- [ ] `execution-journal.md` has a new entry (never edit old entries) stating what was done, what
      was verified vs. deferred, and explicitly: **"needs full verification on the Windows
      machine before being marked verified_complete."**
- [ ] The commit message itself states the item id and ends with "VERIFICATION DEFERRED TO
      WINDOWS SESSION — not independently re-tested beyond what's listed above," so this is
      visible in `git log` even without opening the YAML.
- [ ] No `node_modules/`, `.wrangler/`, `.env`, or `*.db` file is staged (check `git status`
      before committing — these should already be gitignored, but verify).

This checklist exists so that **nothing is dropped silently**: if a dev-machine session is
interrupted, or its own report is wrong, the Windows-side session can reconstruct exactly what
still needs testing purely by reading these fields — it never has to guess or re-derive it.

---

## 5. What the Windows-side session does on resume

1. `git pull`.
2. Read `execution-journal.md`'s latest entries and `implementation-status.yml` for any item
   whose `status: implemented_unverified` and whose evidence says "verification deferred" —
   that's the queue of things to independently check first, before picking up anything new.
3. For each such item: independently re-run whatever its `verification_commands` list, plus
   anything the dev-machine session said it *couldn't* run (full `pytest` suite, Ollama-dependent
   paths, `wrangler dev`/`wrangler deploy`). Never take the dev-machine report at face value — same
   discipline already applied to every subagent in this project's history.
4. Only after that independent pass succeeds: flip `status` to `verified_complete`, fill in
   `verification_evidence` with the actual command output, update `verification-index.yml`.
5. If verification finds a real problem the dev-machine session missed (common, since it couldn't
   test the Ollama/Windows-path-dependent half): fix it directly if it's a plain bug, or file it as
   a new `FB-NN` blocker if it needs a decision — same as this project's existing practice for any
   other discovered issue.
6. Deploy (`wrangler deploy`, D1 migrations, etc.) only happens from this machine, after
   verification passes.
7. Commit the verification results and any fixes, push.
8. Update `backlog.yml`'s `next_eligible_item` for whichever machine picks up next.

---

## 6. Known gaps as of 2026-10-05 (don't rediscover these by trial and error)

- **`FF-P01-01`** (config/installation portability) was re-prioritized `high` → `critical` and
  made `next_eligible_item` specifically because of this workflow: `factory/context/broker.py`,
  `factory/state.py`, `factory/implementation/workspace.py`, `factory/sealed_qa/acceptance.py`,
  and `factory/tools/worktrees.py` all hardcode `C:\Factory`-style paths. Until this is fixed,
  avoid picking backlog items that touch those files from a non-Windows machine — the risk isn't
  that the code won't compile, it's that a Mac session would have no way to notice it baked in a
  Windows-only assumption.
- **`node_modules/`/`.wrangler/` were committed to git** (fixed 2026-10-05 — see the commit that
  added the `.gitignore` entries). If you're resuming from a clone made *before* that fix, run
  `git pull` first; don't manually delete `node_modules` before pulling or you'll fight git over
  file deletions it doesn't know about yet.
- **Ollama tunnel (`ollama.mtourk.com`) is a known, already-flagged security gap** (`FB-02`'s
  broader context) — present for development convenience, not a sanctioned way to test
  Ollama-dependent behavior from a dev machine. Don't build new reliance on it.

---

## 7. Quick reference: who does what

| | Dev machine (e.g. macOS/Cursor) | Verification machine (this Windows laptop) |
|---|---|---|
| Pick next item | Yes, from `backlog.yml` | Yes, if dev machine isn't active |
| Write code + tests | Yes | Yes |
| Run Node-driver tests | Yes (OS-portable) | Yes |
| Run full `pytest` suite | If available, as extra evidence — not a substitute | **Authoritative** |
| Test Ollama/BMAD-dependent behavior | **No** — no route to local Ollama | **Authoritative** |
| `wrangler deploy` / D1 migrations | No | Yes |
| Mark `verified_complete` | **Never** | Yes, after independent re-verification |
| Mark `implemented_unverified` | Yes | Yes |

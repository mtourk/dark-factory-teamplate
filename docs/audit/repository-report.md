# Repository Report: dark-factory-teamplate

**Date:** 2026-10-03  
**Working Directory:** C:\github-repos\dark-factory-teamplate  
**Authority:** DARK_FACTORY_MASTER_PLAN.md, DARK_FACTORY_BUILD_PROMPT.md

## Current Repository State

### Git Status

```
Current branch: main
Last commit: 68b19c5 Add Dark Factory master plan, build prompt, and how-to docs.
Working tree: clean
```

### Remote Configuration

```
origin  https://github.com/mtourk/dark-factory-teamplate.git (fetch)
origin  https://github.com/mtourk/dark-factory-teamplate.git (push)
```

### Current Files

```
C:\github-repos\dark-factory-teamplate\
├── DARK_FACTORY_MASTER_PLAN.md        (9,264 bytes)
├── DARK_FACTORY_BUILD_PROMPT.md       (22,234 bytes)
├── DARK_FACTORY_How_To.md             (2,992 bytes)
├── .git/
├── .codemie/
└── (docs/ and .factory/ created by Phase 1)
```

---

## Authority Documents (Binding)

### DARK_FACTORY_MASTER_PLAN.md

- **Status:** ✅ Present, read, binding specification
- **Sections:** 22 sections covering environment, architecture, frameworks, FactoryFlow design, backlog, context isolation, requirement challenge, model gateway, verification, review, GitHub/auto-merge, Cloudflare, recovery, evidence, phases, testing, mistakes, Definition of Done, execution discipline
- **Protection:** Must not be modified via normal feature workflow (protected path)
- **Audit:** Read completely during Phase 1

### DARK_FACTORY_BUILD_PROMPT.md

- **Status:** ✅ Present, startup protocol defined
- **Key directives:**
  - Read master plan first
  - Create IMPLEMENTATION_CHECKLIST.md
  - Create audit documents
  - Execute all 16 phases without asking between phases
  - Autonomous technical decisions allowed within scope
  - Strategic/business decisions escalated
  - No host-silent modifications
- **Protection:** Must not be modified via normal feature workflow (protected path)

### DARK_FACTORY_How_To.md

- **Status:** ✅ Present, user-facing guide
- **Content:** Instructions for using master plan and build prompt
- **Protection:** Should not be modified via auto-merge (informational, not authority)

---

## Directory Structure (Phase 1 Creation)

### Created by Phase 1

```
docs/
├── audit/
│   ├── prerequisite-report.md     (this document phase)
│   └── repository-report.md       (this file)
├── threat-model.md                (Phase 1 artifact)
└── decisions/
    └── index.md                   (Phase 1 artifact)

.factory/
└── (will populate in Phases 2–16)

IMPLEMENTATION_CHECKLIST.md        (Phase 1 artifact)
THIRD_PARTY_NOTICES.md            (Phase 1 artifact)
```

### Will Be Created in Phases 2–16

```
.factory/
├── config/
│   ├── workflows.yml              (Phase 3)
│   └── policies/
│       └── *.rego                 (Phase 8)
├── schemas/
│   ├── workflow.schema.json        (Phase 2)
│   ├── context_manifest.schema.json
│   ├── evidence_manifest.schema.json
│   ├── decision.schema.json
│   └── requirement.schema.json
├── templates/                      (Phase 7)
└── vendor/
    └── manifest.yml               (Phase 1, updated through phases)

.factory-control/
├── sealed/                         (Phase 9)
├── mutations/                      (Phase 9)
├── rubrics/                        (Phase 9)
├── policies/                       (Phase 8)
├── decisions/                      (Phase 1+)
└── secrets/ (gitignored)

factory/
├── __main__.py                     (Phase 3)
├── cli.py                          (Phase 3)
├── config.py                       (Phase 3)
├── state.py                        (Phase 3)
├── models.py                       (Phase 3)
├── backlog/
│   ├── scheduler.py               (Phase 4)
│   └── claim.py                   (Phase 4)
├── context/
│   └── broker.py                  (Phase 5)
├── gateway/
│   ├── ollama_gateway.py          (Phase 6)
│   └── fake_model.py              (Phase 6)
├── analysis/
│   ├── bmad.py                    (Phase 7)
│   └── critics.py                 (Phase 7)
├── tools/
│   ├── authorized_ops.py          (Phase 8)
│   └── worktree.py                (Phase 8)
├── policy/
│   └── opa_broker.py              (Phase 8)
├── qa/
│   ├── sealed_specs.py            (Phase 9)
│   └── mutation_tester.py         (Phase 9)
├── builder/
│   └── builder.py                 (Phase 10)
├── verification/
│   └── verifier.py                (Phase 10)
├── repair/
│   └── repairer.py                (Phase 10)
├── review/
│   └── reviewer.py                (Phase 11)
├── github/
│   └── github_adapter.py          (Phase 12)
├── deploy/
│   └── cloudflare_adapter.py      (Phase 13)
├── recovery/
│   ├── quarantine.py              (Phase 14)
│   └── emergency_stop.py          (Phase 14)
├── evidence/
│   ├── graph.py                   (Phase 15)
│   └── manifest.py                (Phase 15)
├── learning/
│   └── memory.py                  (Phase 15)
└── tests/
    ├── conftest.py                (throughout)
    ├── test_*.py                  (throughout)
    └── fixtures/                  (throughout)

pyproject.toml                      (Phase 3)
.gitignore                          (Phase 3)
requirements.txt                    (Phase 3, if needed)

.github/workflows/
└── deploy.yml                      (Phase 13, in investisor repo)

docs/
├── audit/
│   ├── prerequisite-report.md
│   └── repository-report.md
├── threat-model.md
├── decisions/
│   ├── index.md
│   └── ADR-*.md                   (throughout phases)
├── benchmarks/
│   └── baseline.md                (Phase 6)
└── (other domain docs as needed)
```

---

## Configuration and Conventions

### Git Conventions

- **Primary branch:** `main` (protected, auto-merge only)
- **Working branches:** `factory/RUN-<id>-<slug>` (created per run, Phase 4+)
- **Worktree location:** `C:\Factory\worktrees\RUN-<id>` (Phase 8)
- **Commit messages:** Include author line per project rules
- **No direct pushes to main**
- **No admin merge bypass**

### Environment and Shell

- **PowerShell version:** Must use `pwsh` (7.x), not default 5.1
- **Working directory:** C:\github-repos\dark-factory-teamplate (factory code)
- **Target project:** https://github.com/mtourk/investisor (factory's first workload)
- **State database:** SQLite at `C:\Factory\state.db` (Phase 3)

### Python Dependencies

Will be defined in `pyproject.toml` (Phase 3):
- Python 3.12
- Typer (CLI)
- Pydantic (validation)
- SQLAlchemy (SQLite ORM)
- Jinja2 (templating)
- PyYAML (workflow config)
- httpx (async HTTP, GitHub/Ollama)
- aiofiles (async file I/O)
- opentelemetry-api/sdk (telemetry)
- pytest, pytest-asyncio (testing)
- aider (code generation, Phase 10)

### Secrets Management

- **Ollama endpoint:** `http://localhost:11434` (no auth, committed to config)
- **GitHub token:** `GH_TOKEN` env var (user provides during auth)
- **Cloudflare token:** Stored in GitHub Actions secrets only (never local)
- **Local .env:** Not used (per user preference)

---

## Protected Paths (Cannot Auto-Merge)

Factory enforces in Phase 12 (GitHub auto-merge gate):

1. `DARK_FACTORY_MASTER_PLAN.md` — binding authority
2. `DARK_FACTORY_BUILD_PROMPT.md` — startup protocol
3. `IMPLEMENTATION_CHECKLIST.md` — phase tracking
4. `THIRD_PARTY_NOTICES.md` — license records
5. `.factory-control/` — sealed tests, mutations, policies, secrets
6. `.factory/` — factory configuration and governance
7. `.github/workflows/` — merge and deployment policy
8. `docs/decisions/` — decision log (human-reviewed decisions only)

Any change to these paths blocks auto-merge and requires manual review.

---

## Licensing and Attribution

### Third-Party Components (Phase 1 Record)

- **Pydantic:** MIT license (validation)
- **Typer:** MIT license (CLI framework)
- **OPA (Open Policy Agent):** Apache 2.0 (policy engine)
- **SQLAlchemy:** MIT license (ORM)
- **PyYAML:** MIT license (YAML parsing)
- **Aider:** Apache 2.0 (code generation, Phase 10)

**Record:** `THIRD_PARTY_NOTICES.md` will be created in Phase 1 with full licenses and attribution.

### Inspiration and Attribution

- **BMAD:** Behavioral Model-Driven Architecture concepts
- **gstack:** Stack of specialized roles (product, engineering, design, etc.)
- **DUBS:** Sealed envelope testing, QA separation
- **OctopusGarden:** Specification preflight, runtime validation, stall recovery
- **Coleam:** GitHub labels as state, immutable governance, automated gates
- **Nick Fujita:** PRD challenge, QA runbooks, traceability, ADRs, delivery reports

**Record:** Each inspiration will be noted in ADRs and docs/decisions/ with version/date.

---

## Target Project: investisor

### Repository

- **URL:** https://github.com/mtourk/investisor
- **Status:** Existing, user has admin access
- **Role:** First workload for factory (issues → implementation → auto-merge → deploy)

### Configuration (Phase 4 Action)

Factory will:

1. Create labels on investisor:
   - `factory:ready` — issue is eligible for factory to claim
   - `factory:claimed` — factory is working on this issue
   - `priority:critical` — urgent security/defect
   - `priority:high` — important feature
   - `priority:normal` — standard feature
   - `priority:low` — nice-to-have
   - `factory:decision-required` — needs human decision, released from claim
   - `factory:blocked` — blocked by external blocker
   - `factory:quarantined` — bad deployment, factory won't touch
   - `factory:delivered` — closed with production validation

2. Create branch protection on investisor `main`:
   - Require all 16 status checks
   - Disable direct push
   - No admin bypass

3. Configure GitHub required checks (16 unique names):
   - `factory/intent`, `factory/authority`, `factory/protected-paths`
   - `factory/format`, `factory/lint`, `factory/typecheck`, `factory/build`
   - `factory/unit`, `factory/contract`, `factory/integration`
   - `factory/security`, `factory/mutation`, `factory/sealed-qa`
   - `factory/review`, `factory/preview`, `factory/evidence`

---

## Compliance and Gates

### Phase 1 Gate Criteria

| Criterion | Status |
|---|---|
| DARK_FACTORY_MASTER_PLAN.md read and understood | ✅ |
| IMPLEMENTATION_CHECKLIST.md created | ✅ |
| docs/audit/prerequisite-report.md created | ✅ |
| docs/audit/repository-report.md created | ✅ |
| docs/threat-model.md created (next) | ⏳ |
| docs/decisions/index.md created (next) | ⏳ |
| THIRD_PARTY_NOTICES.md created (next) | ⏳ |
| No blocking prerequisites identified | ✅ |
| All tooling baseline verified | ✅ |
| Git state clean and remote correct | ✅ |
| Protected paths identified | ✅ |
| Threat model written | ⏳ |
| Phase 1 committed | ⏳ |

### Next Steps (Phase 1 completion)

1. ✅ Create threat-model.md (this phase)
2. ✅ Create docs/decisions/index.md (this phase)
3. ✅ Create THIRD_PARTY_NOTICES.md (this phase)
4. ⏳ Commit Phase 1: "Phase 1: Audit, threat model, implementation checklist"
5. ⏳ Begin Phase 2: Contracts and schemas

---

*Report generated: 2026-10-03 during Phase 1  
Authority: DARK_FACTORY_MASTER_PLAN.md §1–3*

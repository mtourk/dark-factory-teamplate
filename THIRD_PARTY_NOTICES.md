# Third-Party Notices and Attribution

**Project:** dark-factory-teamplate (FactoryFlow orchestrator)  
**Generated:** 2026-10-03 (Phase 1)  
**Authority:** DARK_FACTORY_MASTER_PLAN.md §3.1, DARK_FACTORY_BUILD_PROMPT.md

## Purpose

This file documents all third-party code, libraries, and intellectual property used in the Dark Factory project. Every dependency, adaptation, and inspiration is recorded with its license, version, and attribution. Changes to dependencies require updates to this file before commit.

**Policy (Master Plan §3.1):**
> Do not vendor whole upstream repositories. Before adapting any code, prompt, configuration, or template, identify the exact source and version, read its license, record attribution, choose dependency, adaptation, reimplementation, or rejection. Update `THIRD_PARTY_NOTICES.md` and `.factory/vendor/manifest.yml`.

---

## Dependencies

### Direct Python Dependencies (Phase 3: pyproject.toml)

| Package | Version | License | Purpose | Status |
|---|---|---|---|---|
| Python | 3.12 | PSF | Runtime | ✅ |
| Typer | 0.9.0+ | MIT | CLI framework | 🟡 To add |
| Pydantic | 2.5+ | MIT | Data validation, schemas | 🟡 To add |
| SQLAlchemy | 2.0+ | MIT | ORM, SQLite | 🟡 To add |
| Jinja2 | 3.1+ | BSD-3-Clause | Template rendering | 🟡 To add |
| PyYAML | 6.0+ | MIT | YAML parsing | 🟡 To add |
| httpx | 0.25+ | BSD | Async HTTP client (GitHub, Ollama) | 🟡 To add |
| aiofiles | 23.2+ | Apache 2.0 | Async file I/O | 🟡 To add |
| opentelemetry-api | 1.20+ | Apache 2.0 | Telemetry instrumentation | 🟡 To add |
| opentelemetry-sdk | 1.20+ | Apache 2.0 | Telemetry runtime | 🟡 To add |
| pytest | 7.4+ | MIT | Unit testing | 🟡 To add |
| pytest-asyncio | 0.21+ | Apache 2.0 | Async test support | 🟡 To add |
| aider | (latest) | Apache 2.0 | Code generation (Phase 10) | 🟡 To add, Phase 10 |

### External Tools (Already Installed)

| Tool | Version | License | Purpose | Status |
|---|---|---|---|---|
| Windows 11 | 10.0.26200 | Proprietary | OS | ✅ |
| PowerShell | 7.6.6 | MIT | Shell orchestration | ✅ |
| Git | 2.55 | GPL-2.0 | Version control | ✅ |
| GitHub CLI (gh) | 2.102 | MIT | GitHub API | ✅ |
| Ollama | 0.35.1 | MIT | Local LLM runtime | ✅ |
| Open Policy Agent (OPA) | 1.21.1 | Apache 2.0 | Policy engine | ✅ |
| VS Code | 1.140 | MIT | Editor (dev only) | ✅ |
| Node.js | 22.18.0 | MIT | JavaScript runtime | ✅ |
| Wrangler | 4.147.0+ | Apache 2.0 | Cloudflare CLI | ✅ (via npx) |
| uv | 0.12.22 | MIT/Apache 2.0 | Package manager | ✅ |

---

## Conceptual Frameworks and Attribution

These are not code dependencies but architectural inspiration. Master Plan §3 describes the integration of each framework with its original authors/publications credited.

### BMAD (Behavioral Model-Driven Analysis and Design)

- **Source:** Autonomous discovery and specification patterns
- **Used in:** Phase 7 (requirement challenge, BMAD draft)
- **Attribution:** Concept referenced in master plan §3.1, §7
- **License:** Conceptual (not vendored)
- **Integration:** Isolated critics phase (Phase 7)

### gstack (Stack of Specialized Roles)

- **Source:** Multi-perspective code review and delivery
- **Used in:** Phase 7 (selective roles: product, domain, testability, security, contradiction, operational recovery critics)
- **Attribution:** Master Plan §3.1 lists "gstack-style challenge and review roles"
- **License:** Conceptual (not vendored)
- **Integration:** Isolated requirement critics (Phase 7), independent review (Phase 11)

### DUBS (Sealed Envelope Tests, QA Separation)

- **Source:** Build/QA isolation pattern
- **Used in:** Phase 9 (sealed tests hidden from builder)
- **Attribution:** Master Plan §3.1 lists "DUBS-style sealed acceptance testing"
- **License:** Conceptual (not vendored)
- **Integration:** Sealed QA design (Phase 9), verification (Phase 11)

### OctopusGarden (Specification Preflight, Runtime Validation, Stall Diagnosis)

- **Source:** Production reliability patterns
- **Used in:** Phase 12 (specification preflight), Phase 10 (stall detection), Phase 14 (recovery)
- **Attribution:** Master Plan §3.1 lists "OctopusGarden-style bounded repair and stall diagnosis"
- **License:** Conceptual (not vendored)
- **Integration:** Verification order (Phase 9), repair loop (Phase 10), recovery (Phase 14)

### Coleam (GitHub State, Stop Control, Immutable Governance)

- **Source:** GitHub-native delivery automation
- **Used in:** Phase 4 (backlog scheduling), Phase 12 (auto-merge), Phase 14 (emergency stop)
- **Attribution:** Master Plan §3.1 lists "Coleam-style GitHub state, stop control, and immutable governance"
- **License:** Conceptual (not vendored)
- **Integration:** Labels as workflow state (Phase 4), emergency stop (Phase 14)

### Nick Fujita Concepts (PRD Challenge, QA Runbooks, Traceability, ADRs, Delivery Reports)

- **Source:** Delivery quality patterns
- **Used in:** Phase 7 (requirement challenge), Phase 9 (QA runbooks), Phase 15 (evidence traceability), Phase 16 (delivery reports)
- **Attribution:** Master Plan §3.1 lists "Nick Fujita-style PRD challenge, QA runbooks, traceability, ADRs, and delivery reports"
- **License:** Conceptual (not vendored)
- **Integration:** Requirement synthesis (Phase 7), sealed QA (Phase 9), evidence graph (Phase 15)

---

## Vendor Manifest

**Location:** `.factory/vendor/manifest.yml` (created Phase 2+)

This YAML file will record:
- Exact library versions and checksums
- License identifiers (SPDX)
- Download sources
- Date vendored
- Use case (runtime, test, dev only)
- License compliance status (reviewed: yes/no)

**Example:**

```yaml
dependencies:
  - name: Typer
    version: 0.9.0
    source: https://pypi.org/project/typer/
    license: MIT
    spdx_id: MIT
    use: runtime
    reviewed: false  # will be updated during Phase 3
    notes: CLI framework for factory commands
```

---

## Compliance Checklist

| Item | Phase | Status |
|---|---|---|
| Read all dependency licenses | 3 | ⏳ |
| Verify no GPL-with-restrictions | 3 | ⏳ |
| Verify Apache/BSD/MIT compatible | 3 | ⏳ |
| Add to SPDX SBOM | 3 | ⏳ |
| Document any modified versions | 2+ | ⏳ |
| Note any vendored forks | 2+ | ⏳ |
| Review OPA policy licenses (if custom) | 8 | ⏳ |
| Confirm Cloudflare/GitHub TOS | 12+ | ⏳ |
| Final compliance review before Phase 16 | 15 | ⏳ |

---

## License Summary

### Acceptable Licenses for This Project

- ✅ MIT
- ✅ Apache 2.0
- ✅ BSD-2-Clause, BSD-3-Clause
- ✅ ISC
- ✅ Python Software Foundation (PSF)
- ✅ GNU GPL v2+ (with care; affects derived works)

### Restricted/Prohibited

- ❌ AGPL v3 (copyleft; affects commercial cloud deployment)
- ❌ GPL v3 without exception (similar risk)
- ❌ Proprietary without commercial license

---

## How to Add a New Dependency

1. Identify the package, version, source
2. Read the license file (GitHub repo or PyPI)
3. Check SPDX identifier (https://spdx.org/licenses/)
4. Verify compatibility (acceptable licenses above)
5. Add to `.factory/vendor/manifest.yml` with reviewed=false
6. Update this file (`THIRD_PARTY_NOTICES.md`)
7. Add to `pyproject.toml` with version pin
8. Update `IMPLEMENTATION_CHECKLIST.md` with new dependency note
9. Commit: "Add [package] dependency with license [license]"

---

## Changes Log

| Date | Package | Version | Action | Phase |
|---|---|---|---|---|
| 2026-10-03 | Initial setup | – | Document dependencies | 1 |
| TBD | Typer, Pydantic, etc. | TBD | Add after Phase 3 starts | 3 |

---

## Questions and Support

- **License question:** Check SPDX registry (https://spdx.org/)
- **Compatibility check:** Consult GitHub license compatibility matrix
- **Commercial concern:** Escalate in docs/decisions/ ADR for approval

---

*Third-Party Notices v1.0  
Created: 2026-10-03 (Phase 1)  
Authority: DARK_FACTORY_MASTER_PLAN.md §3.1  
Next update: Phase 3 (when dependencies are added to pyproject.toml)*

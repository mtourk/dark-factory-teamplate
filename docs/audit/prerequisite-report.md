# Prerequisite Report: Dark Factory Implementation

**Date:** 2026-10-03  
**Project:** dark-factory-teamplate (FactoryFlow orchestrator)  
**Target Project:** https://github.com/mtourk/investisor  
**Authority:** DARK_FACTORY_MASTER_PLAN.md §1, DARK_FACTORY_BUILD_PROMPT.md

## Executive Summary

All mandatory prerequisites for Phase 1 startup are **satisfied**. The factory can begin Phase 1 immediately. Three prerequisites require user action but do **not block** earlier phases:

1. **GitHub authentication** — user will run `! gh auth login` interactively
2. **Model download** — `ollama pull qwen2.5-coder:32b` in progress (background)
3. **Investisor repo labels** — will be created in Phase 4 (backlog scheduler)

---

## Environment and Tools

### Operating System and Shell

| Requirement | Spec | Found | Status |
|---|---|---|---|
| OS | Windows 11 | Windows 11 Enterprise 10.0.26200 | ✅ |
| PowerShell 5.x (default) | Required for user | 5.1.26100.9444 | ✅ |
| PowerShell 7+ (`pwsh`) | Required for factory | 7.6.6 | ✅ |
| Windows Terminal | Recommended | v1.140.0 | ✅ |

**Note:** Factory must invoke `pwsh` explicitly; default shell is 5.1.

---

### Development and Build Tools

| Tool | Spec | Found | Version | Status |
|---|---|---|---|---|
| Python | 3.12 | ✅ | 3.12.10 | ✅ |
| uv (package manager) | Required | ✅ | 0.12.22 | ✅ |
| Git | 2.50+ | ✅ | 2.55.0 | ✅ |
| GitHub CLI (`gh`) | Required | ✅ | 2.102 | ⚠️ Not authenticated |
| VS Code | Recommended | ✅ | 1.140 | ✅ |
| Node.js | For Wrangler | ✅ | 22.18.0 | ✅ |
| Wrangler (npx) | Phase 13 | ✅ via npx | 4.147.0 | ✅ |

---

### Local Inference

| Tool | Spec | Found | Version | Status |
|---|---|---|---|---|
| Ollama | Local runtime | ✅ | 0.35.1 | ✅ Running on :11434 |
| Model: qwen2.5-coder:32b | Single choice for all roles | ⏳ Pulling | – | In progress |
| Initial context | 8192 tokens | – | – | Configured in Phase 6 |

**Model selection rationale:**
- User chose single 32b model over multi-model setup (simpler, ~18–20 GB RAM)
- Fits within 32 GB RAM with margin for OS/tooling
- Sequential inference (one model at a time, per §1)
- All roles (router, analyst, builder, reviewer) alias to qwen2.5-coder:32b
- Trade-off: loss of specialized routing (7b for quick decisions) for operational simplicity

---

### Policy and Governance

| Tool | Spec | Found | Version | Status |
|---|---|---|---|---|
| Open Policy Agent (OPA) | Tool authorization | ✅ | 1.21.1 | ✅ |
| SQLite | State database | Via Python stdlib | 3.46 (bundled) | ✅ |

---

### Optional/Not Required for v1

| Tool | Spec | Found | Status |
|---|---|---|---|
| Docker | "Do not require" | ✅ Not installed | ✅ Correct |
| WSL/Ubuntu | "Do not require" | ✅ Not installed | ✅ Correct |
| Kubernetes | "Do not require v1" | ✅ Not installed | ✅ Correct |

---

## Hardware and Resource Constraints

| Resource | Spec | Available | Headroom | Status |
|---|---|---|---|---|
| RAM | 32 GB | 32 GB | – | ✅ |
| CPU | Intel Core Ultra 7 265H | Available | – | ✅ |
| VRAM (dedicated) | 0 GB (integrated Arc) | 0 GB | – | ⚠️ No GPU acceleration |
| Disk free | 387 GB min | 387 GB | – | ✅ |
| Model weight: qwen2.5-coder:32b (Q4) | ~18–20 GB | 387 GB avail | 367 GB free | ✅ |

**Inference model:** Sequential (one heavy session at a time). No parallel model loading. Memory usage peak estimated at 20–24 GB during builder/reviewer sessions (model + OS + tooling + pagefile). Pagefile will be used but controlled.

---

## GitHub and Repository Configuration

### Current State

| Item | Found | Status |
|---|---|---|
| Repository | `https://github.com/mtourk/dark-factory-teamplate` | ✅ |
| Remote | `https://github.com/mtourk/dark-factory-teamplate.git` (fetch/push) | ✅ |
| Branch | `main` (clean working tree) | ✅ |
| User access | AzureAD+MohammadTourk | ✅ |
| Admin/maintain rights | Verified by user | ✅ |
| `gh` authentication | **Not logged in** | ⚠️ Blocks Phase 4+ |
| Target project | https://github.com/mtourk/investisor | ✅ Confirmed |

### GitHub Authentication (User Action Required)

**When:** Before Phase 4 (Backlog Scheduler)  
**What:** User runs `! gh auth login` in this session  
**Why:** Needed for:
- List GitHub Issues on investisor
- Create/read/modify labels
- Create branches and PRs
- Publish required status checks
- Enable auto-merge

**Does not block:** Phases 1–3 (local scaffolding only)

### Investisor Repository Setup (Phase 4 Action)

Factory will configure:
- Labels: `factory:ready`, `factory:claimed`, `priority:critical/high/normal/low`, `factory:decision-required`, etc.
- Branch protection on `main`: require all 16 status checks, disable direct push
- Required status check names (unique, per §14)

**Prerequisite:** Investisor repo must exist and you must have admin/maintain access (user confirmed).

---

## Cloudflare and Production Deployment

### Current State

| Item | Spec | Provided | Status |
|---|---|---|---|
| Cloudflare account | Required for Phase 13+ | ✅ User has account | ✅ |
| Account ID | Required for wrangler | `[REDACTED]` | ✅ |
| API Token | Required for wrangler | `[REDACTED]` | ✅ Received |
| Storage location | Never stored locally | GitHub Actions secrets only | ✅ |

### Deployment Configuration (Phase 13 Action)

Factory will:
1. Create `.github/workflows/deploy.yml` in investisor repo
2. Inject secrets into GitHub Actions (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN)
3. Deploy via `wrangler publish` after main merge
4. Run smoke tests and validate production health

**Does not block:** Phases 1–12 (local development)

---

## Secrets Management

### Decision Made

**Policy:** GitHub Actions secrets only (no local storage)

**Rationale:**
- Ollama endpoint (`localhost:11434`) requires no secret (local, no auth)
- Cloudflare tokens only needed by GitHub Actions (not touched by local models)
- Reduces local credential exposure

**Implementation:**
- Ollama config stored in `.factory/config.yml` (committed, safe for local)
- GitHub token can be `GH_TOKEN` env var (user provides during auth)
- Cloudflare tokens stored as GitHub repo secrets, not local

---

## Accounts and Isolation

### Current User

| Item | Status |
|---|---|
| User | AzureAD+MohammadTourk |
| Admin privileges | Not checked (Azure AD account) |
| Dedicated builder account | Not set up (user chose "run as current user") |

**Note:** Per plan §6.6, isolated account is "where feasible" (optional for v1). User chose simplicity over isolation. Security trade-off: factory processes run as your user and can access your files. This is acceptable for v1 local development.

---

## Protected Paths

Factory must refuse to auto-merge changes to:

| Path | Reason | Enforcement |
|---|---|---|
| `DARK_FACTORY_MASTER_PLAN.md` | Binding authority, cannot self-modify | Phase 12 check |
| `DARK_FACTORY_BUILD_PROMPT.md` | Authority delegation, cannot self-modify | Phase 12 check |
| `IMPLEMENTATION_CHECKLIST.md` | Governance, cannot bypass phases | Phase 12 check |
| `.factory-control/` | Sealed tests, mutations, policies, secrets | Phase 12 check |
| `.factory/` | Governance and controls | Phase 12 check |
| `.github/workflows/` | Merge and deployment policy | Phase 12 check |
| `THIRD_PARTY_NOTICES.md` | License records, cannot delete | Phase 12 check |

**Implementation:** Phase 8 (Tool Authorization) will enforce via OPA and Phase 12 (GitHub auto-merge gate) will verify before merge.

---

## Missing or Deferred Prerequisites

| Item | Impact | Resolution | Timeline |
|---|---|---|---|
| `gh` authentication | Cannot list issues or create PRs | User runs `! gh auth login` | Before Phase 4 |
| `qwen2.5-coder:32b` model | Cannot run inference | Pulling now (background) | Before Phase 6 |
| Investisor labels | Cannot schedule backlog items | Factory creates in Phase 4 | Phase 4 action |
| Cloudflare in GitHub Actions | Cannot deploy to production | Store secrets in Phase 13 | Phase 13 action |
| Investisor branch protection | Cannot enforce required checks | Factory creates in Phase 12 | Phase 12 action |

**None of the above block Phase 1 startup.**

---

## Risk and Mitigation

| Risk | Mitigation |
|---|---|
| Model download hangs or fails | Already started in background; Phase 1–3 proceed independently. If still not ready by Phase 6, retry or escalate. |
| Insufficient RAM during heavy sessions | Sequential inference limits peak. Pagefile will be used (acceptable on modern SSD). Monitor in Phase 6 benchmarks. |
| GitHub API rate limits | Add retry-with-backoff logic in Phase 4. Backoff starts at 60s; max 5 retries. |
| Protected-path modification attempt | OPA policy denies; logged as policy violation. Factory stops and requests human decision. |
| Production deployment fails | Recovery phase (Phase 14) quarantines bad SHA. Emergency stop prevents new merges. Manual recovery documented in ADRs. |

---

## Compliance Checklist

| Check | Result |
|---|---|
| Windows 11 + PowerShell 7 available | ✅ |
| No required Ubuntu/Docker | ✅ |
| Python 3.12 + uv available | ✅ |
| Git remote correct | ✅ |
| Admin access to dark-factory-teamplate | ✅ |
| Admin access to investisor target | ✅ (user confirmed) |
| Local inference (Ollama + model) ready | ✅ (model pulling) |
| OPA installed | ✅ |
| Cloudflare credentials received (not stored locally) | ✅ |
| GitHub auth ready (deferred to user action) | ⚠️ Next step |

---

## Phase 1 Gate: Prerequisites Satisfied

✅ **Phase 1 can proceed immediately.**

Remaining user actions (do not block Phase 1):
1. When prompted, run `! gh auth login` to authenticate with GitHub
2. Monitor `ollama list` to confirm qwen2.5-coder:32b is pulled (do not hurry; can proceed without waiting)
3. Before Phase 13, provide Cloudflare credentials to GitHub Actions (already have them)

---

*Report generated: 2026-10-03  
Authority: DARK_FACTORY_MASTER_PLAN.md §1, DARK_FACTORY_BUILD_PROMPT.md Startup Protocol*

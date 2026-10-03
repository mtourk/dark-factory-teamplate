# Threat Model: Dark Factory Autonomous Delivery

**Date:** 2026-10-03  
**Project:** dark-factory-teamplate (FactoryFlow orchestrator for investisor)  
**Authority:** DARK_FACTORY_MASTER_PLAN.md, DARK_FACTORY_BUILD_PROMPT.md

## Overview

This threat model identifies security, isolation, and operational risks in a Windows-native, local-LLM autonomous delivery factory. The model operates on a single developer machine (HP EliteBook, 32 GB RAM, Intel Arc integrated GPU). The factory selects GitHub Issues from the investisor repository, analyzes requirements, implements changes, runs verification, deploys to Cloudflare, and closes issues — all without human code review intervention (but with governance gates).

**Scope:** Phases 1–16 of the factory implementation, with emphasis on:
- Context leakage between roles (builder/reviewer isolation)
- Unauthorized access to sealed tests and hidden acceptance criteria
- Model prompt injection and jailbreak attempts
- Local file and credential exposure
- Uncontrolled test weakening (deterministic verification bypass)
- Production deployment incidents (bad SHA, health failures)
- Self-modification of governance (factory modifying its own authority)

**Out of scope:** Network security, GitHub compromise, Cloudflare account theft (assumed secure). Threat model focuses on factory design and local operation.

---

## Assets and Trust Boundaries

### High-Value Assets

| Asset | Owner | Sensitivity | Protection |
|---|---|---|---|
| DARK_FACTORY_MASTER_PLAN.md | Factory authority | Binding | Protected path; cannot auto-merge changes |
| DARK_FACTORY_BUILD_PROMPT.md | Factory authority | Binding | Protected path; cannot auto-merge changes |
| Sealed test definitions | QA/factory | Confidential | Hidden from builder, stored in .factory-control/ |
| Mutation definitions | QA/factory | Confidential | Hidden from builder, stored in .factory-control/ |
| GitHub API token (GH_TOKEN) | User/GitHub | Secret | Env var only; never logged or committed |
| Cloudflare API token | User/Cloudflare | Secret | GitHub Actions secrets only; never touched locally |
| Compiled intent (per run) | Factory/run | Internal | Shared across roles; certified by challenge phase |
| Builder conversation history | Builder role | Private | Locked to builder session; not passed to reviewer |
| Reviewer context package | Reviewer role | Private | Assembled by orchestrator; fresh session per run |
| Independent review findings | Reviewer role | Trusted | Linked to exact head SHA; cannot change after record |
| Investisor repository | Target project | Operational | Auto-merge blocked on protected paths in investisor |

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│ Developer Machine (Windows 11, 32 GB RAM)                           │
│                                                                     │
│ ┌────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│ │  FactoryFlow   │  │   Ollama Model   │  │  Git Worktrees    │  │
│ │  (CLI, state,  │  │ (qwen2.5:32b)    │  │  (C:\Factory\...) │  │
│ │   orchestr.)   │  │                  │  │                    │  │
│ └────────────────┘  └──────────────────┘  └────────────────────┘  │
│                                                                     │
│   [Shared: compiled intent, approved ADRs, evidence]               │
│   [Private: builder chat, sealed tests, reviewer context]          │
│                                                                     │
└────────┬────────────────────────────────────────┬──────────────────┘
         │                                        │
         │ (HTTPS, GitHub OAuth)                  │
         │                                        │
    ┌────▼────────────────────────┐  ┌───────────▼─────────────────┐
    │ GitHub (investisor repo)    │  │ Cloudflare (preview/prod)   │
    │ - Issues, labels, PRs       │  │ - Deployment secrets (GH)   │
    │ - Branch protection rules   │  │ - Health checks             │
    │ - Required checks, auto-mer │  │ - Production state          │
    └────────────────────────────┘  └─────────────────────────────┘
```

---

## Threat Categories and Mitigations

### 1. Context Leakage Between Roles

**Threat:** Builder sees sealed tests, mutation definitions, or reviewer context. Reviewer sees builder scratch notes or repair logs. Competitor models share training state across roles.

**Severity:** HIGH (violates §6.2, §6.5 isolation principles)

**Attack vectors:**
- Builder agent passed entire `.factory-control/` directory
- Reviewer context package includes builder conversation history
- Same model session reused for builder and reviewer (shared memory)
- Shared directory permissions allow cross-role file access

**Mitigations:**
- [ ] Phase 5: Context Broker enforces role-scoped directories (builder cannot import sealed module)
- [ ] Phase 5: Leakage tests verify builder cannot read sealed test paths
- [ ] Phase 6: Fresh session per role (new API call, no conversation reuse)
- [ ] Phase 11: Reviewer context assembled by orchestrator only; builder chat excluded
- [ ] Phase 8: Worktree ACLs (if feasible) restrict builder/reviewer access to each other's private dirs
- [ ] Phase 5: All leakage test failures cause fail-closed rejection

**Residual risk:** If file permissions misconfigured, cross-role access still possible on shared NTFS volume. Mitigation: test access explicitly in Phase 5.

---

### 2. Test Weakening and Deterministic Failure Override

**Threat:** Builder modifies, deletes, or weakens failing tests to force a pass. Model decides "let's skip this check" against policy.

**Severity:** HIGH (violates §11, §20 test integrity)

**Attack vectors:**
- Builder receives verification failure, comments out test in a "fix"
- Builder suggests test is "false positive" and model agrees to skip
- Builder replaces integration test with mock to pass faster
- OPA policy too permissive; allows test modification

**Mitigations:**
- [ ] Phase 9: Sealed tests stored outside builder's allowed write roots
- [ ] Phase 10: Builder repair input limited to category, logs, attempt, allowed/prohibited paths (no direct test access)
- [ ] Phase 8: OPA policy explicitly denies test deletion/modification for builder role
- [ ] Phase 11: Reviewer verifies all tests still present and unchanged from sealed definition
- [ ] Phase 10: Repair loop tracks attempt and patch digest; repeating same failure triggers stall detection

**Residual risk:** If allowed-write-roots misconfigured, builder could modify tests in-place. Mitigation: Phase 11 reviewer independently validates test presence.

---

### 3. Sealed Test Exposure

**Threat:** Builder reads `factory-control/sealed/` and overfits implementation to pass hidden tests, defeating mutation/acceptance testing.

**Severity:** CRITICAL (violates §9 sealed QA principle)

**Attack vectors:**
- Factory context package includes sealed test paths
- Sealed test directory has lax file permissions
- Builder logs include failure envelope content that reveals test logic
- Model queries filesystem directly and finds hidden tests

**Mitigations:**
- [ ] Phase 5: Context Broker excludes sealed test storage from builder context manifests
- [ ] Phase 9: Sealed tests stored in separate `.factory-control/sealed/` directory outside builder working root
- [ ] Phase 9: Builder failure envelope includes only observable behavior pattern, not internal test logic
- [ ] Phase 5: Leakage test: Builder session cannot import sealed test module (must fail)
- [ ] Phase 8: OPA policy denies builder read access to `.factory-control/sealed/`
- [ ] Phase 10: Builder repair input redacts internal test definitions

**Residual risk:** If builder somehow locates sealed file and reads it, entire acceptance testing can be circumvented. Mitigation: Phase 5 and 11 enforce strict boundary verification.

---

### 4. Prompt Injection and Adversarial Model Input

**Threat:** GitHub Issue contains prompt injection attempting to:
- Disable verification ("skip tests")
- Exfiltrate sealed tests ("list sealed/ files")
- Modify governance ("remove protected path rule")
- Force code change ("inject this backdoor")

**Severity:** MEDIUM-HIGH (depends on model robustness and policy enforcement)

**Attack vectors:**
- Malicious issue title/description with injection payloads
- Issue references external URL with adversarial prompts
- Requirement "contains a test that fails on purpose" triggers repair loop that ignores real bugs
- Critic receives contradictory requirements and picks the adversarial one

**Mitigations:**
- [ ] Phase 5: Compiled intent is derived from issue + BMAD analysis + critic synthesis, not direct issue text
- [ ] Phase 7: Critics classify findings with evidence sources; no bare model judgment
- [ ] Phase 8: OPA policy is declarative Rego, not model-controlled
- [ ] Phase 10: Builder repair loop has bounded cycles; stall detection halts on suspicious patterns
- [ ] Phase 11: Reviewer independently re-reads original issue and compares to compiled intent; injection attempt would be flagged as contradiction
- [ ] All model calls sanitize logs; injection payloads redacted before telemetry

**Residual risk:** Highly sophisticated prompt injection could still influence model reasoning. Mitigation: Phase 11 reviewer is independent witness.

---

### 5. Unauthorized Credential Exposure

**Threat:** GitHub token, Cloudflare token, or Ollama endpoint details leaked to logs, stored in committed files, or passed to untrusted services.

**Severity:** CRITICAL (violates §6.6, exposes user credentials)

**Attack vectors:**
- GH_TOKEN echoed in subprocess stdout, captured in logs
- Cloudflare token mistakenly added to `.env` and committed
- Ollama endpoint URL includes embedded credentials (none in this setup, but pattern risk)
- Model verbose logging includes full HTTP headers with Authorization tokens
- Error stack trace includes secrets

**Mitigations:**
- [ ] Phase 3: Secrets management policy: GH_TOKEN env var only, never logged
- [ ] Phase 13: Cloudflare token stored in GitHub Actions secrets (never local)
- [ ] Phase 3: Ollama config stores plain `http://localhost:11434` (no credentials needed)
- [ ] Phase 6: Gateway redaction logic scrubs Authorization headers from logs
- [ ] Phase 3: .gitignore includes `.env`, `*.secrets`, `*.key`, `*.token` patterns
- [ ] Phase 10: Builder error logs sanitized before storage

**Residual risk:** Malicious prompt could trick model into logging secrets. Mitigation: Runtime log redaction catches most patterns; audit logs for accidental leaks.

---

### 6. Uncontrolled Self-Modification (Factory Modifies Governance)

**Threat:** Factory implementation modifies DARK_FACTORY_MASTER_PLAN.md, DARK_FACTORY_BUILD_PROMPT.md, or IMPLEMENTATION_CHECKLIST.md through auto-merge, bypassing authority.

**Severity:** CRITICAL (violates §14, §20 self-modification prohibition)

**Attack vectors:**
- Feature request: "Simplify Phase 3 requirements" → factory auto-merges simplification
- Bug fix: "Disable sealed test check to speed up verification" → factory merges
- Performance tuning: "Skip mutation testing" → factory auto-merges
- Legitimate change to authority accidentally pushed to main and merged

**Mitigations:**
- [ ] Phase 12: GitHub auto-merge gate checks if diff touches protected paths
- [ ] Phase 12: Protected paths include `DARK_FACTORY_*.md` and `IMPLEMENTATION_CHECKLIST.md`
- [ ] Phase 12: If protected path detected, auto-merge is **disabled** regardless of check status
- [ ] Phase 8: OPA policy denies tool operations on protected paths
- [ ] Phase 16: End-to-end test verifies factory refuses to auto-merge governance change
- [ ] Commit: Only humans can modify protected paths (commits require human approval, not auto-merge)

**Residual risk:** If protected-path list incomplete or incorrectly deployed, factory could modify itself. Mitigation: Phase 11 reviewer manually checks diff for protected-path changes.

---

### 7. Production Deployment Incident (Bad SHA, Health Failure)

**Threat:** Factory merges a bad commit or deploys failing code to production, leaving production in unknown state. Factory continues merging new items, compounding incident.

**Severity:** CRITICAL (violates §15, §20 production safety)

**Attack vectors:**
- Sealed tests pass but production health check fails (bad acceptance test)
- Deployment succeeds but rolled back by Cloudflare policy (unknown state)
- Reviewer misses critical bug; production fails on first real traffic
- Verification gap: local tests pass but production behavior differs (environment variance)

**Mitigations:**
- [ ] Phase 14: Emergency stop (`factory emergency-stop`) blocks new merges when production state unknown
- [ ] Phase 14: After deployment, factory polls production version (Cloudflare headers or API)
- [ ] Phase 14: If deployed version ≠ expected SHA, factory quarantines bad deployment
- [ ] Phase 14: Quarantine prevents new merges; requires explicit recovery procedure (no auto-rollback)
- [ ] Phase 13: Smoke tests verify critical endpoints after deploy
- [ ] Phase 15: Evidence manifest records production validation result (passed/failed/unknown)
- [ ] Phase 11: Reviewer explicitly checks sealed acceptance and mutation test reports

**Residual risk:** If smoke test suite is weak, bad deployment could pass validation. Mitigation: Phase 9 mutation testing catches weak smoke tests.

---

### 8. Race Condition in Claim and Stale Lease Recovery

**Threat:** Two factory runs simultaneously claim the same GitHub Issue, or a stale claim is not detected and recovered, leading to duplicate work or lost progress.

**Severity:** MEDIUM (violates §5 atomic claim principle)

**Attack vectors:**
- Two instances of factory run simultaneously claim same issue
- Run crashes without heartbeat update; stale claim not detected
- Claim recovery detects local branch but not remote state (divergence)
- SQLite lock contention causes race on claim record insert

**Mitigations:**
- [ ] Phase 4: Claim includes atomic database insert + GitHub label add (not idempotent; fails if already claimed)
- [ ] Phase 4: SQLite write-ahead logging and explicit locks prevent race
- [ ] Phase 4: Heartbeat updated every 30s by active run; stale detection checks TTL
- [ ] Phase 4: Stale claim recovery inspects local worktree, remote branch, PR, merge state, deployment state, production state
- [ ] Phase 4: Recovery prefers remote truth (GitHub state of record)
- [ ] Phase 5: Claim leakage test verifies concurrent claims fail deterministically

**Residual risk:** If heartbeat update fails silently, stale claim might not be detected until long delay. Mitigation: Phase 4 includes aggressive timeout (60s).

---

### 9. Context Package Metadata Tampering or Loss

**Threat:** Context manifest is modified, deleted, or corrupted, causing unauthorized context access or evidence loss.

**Severity:** HIGH (violates §6.3, §6.5 isolation and evidence principles)

**Attack vectors:**
- Agent repairs context manifest to hide policy violation
- Manifest hash computed incorrectly, allowing forge
- Manifest file deleted; "forgotten" context remains in memory
- Manifest missing required fields (e.g., exclusions, policy decision)

**Mitigations:**
- [ ] Phase 5: Context manifest includes immutable hash of included artifacts
- [ ] Phase 5: Missing metadata causes fail-closed rejection (no permissive fallback)
- [ ] Phase 5: All context package assembly logged to SQLite with timestamps
- [ ] Phase 15: Evidence manifest includes context package ID and hash; broken hash blocks auto-merge
- [ ] Phase 5: Manifest validation explicitly checks required fields (source IDs, hashes, policy, timestamp)
- [ ] Phase 5: Leakage test verifies corrupted manifest is rejected

**Residual risk:** If hash algorithm is weak, manifest forgery still possible. Mitigation: Use SHA-256 (not MD5).

---

### 10. Model Hallucination in Requirement Synthesis

**Threat:** Isolated critics analyze requirements and model "fills in the gaps" with unsupported assumptions. Factory implements the hallucination, shipping wrong behavior.

**Severity:** MEDIUM (violates §7 strategic ambiguity principle)

**Attack vectors:**
- Domain-Rule Critic sees "calculate ROI" but no formula defined; model assumes linear formula
- Product Critic assumes user entitlement based on hallucinated competitor behavior
- Security Critic speculates on permission rules not in any source document
- No contradiction critic catches the unsupported assumption

**Mitigations:**
- [ ] Phase 7: Every finding includes evidence source (authoritative project document)
- [ ] Phase 7: Findings classified as `strategic_ambiguity` if no authoritative source exists
- [ ] Phase 7: Model confidence and agent agreement are **not** authority
- [ ] Phase 7: Contradiction critic explicitly checks for unsupported business decisions
- [ ] Phase 7: Challenge gate passes only if all business-visible decisions are sourced
- [ ] Phase 7: Tests verify critics reject hallucinated findings with "source not found" reason

**Residual risk:** Critic might hallucinate a plausible-sounding source. Mitigation: Phase 7 tests include adversarial "fake source" to catch this.

---

### 11. Insufficient Permission Control (Builder Executes Prohibited Operations)

**Threat:** Builder (or reviewer) runs a prohibited operation (install dependency, delete directory, authenticate, modify workflow) due to overly permissive OPA policy or missing tool validation.

**Severity:** HIGH (violates §9 tool authorization principle)

**Attack vectors:**
- OPA policy allows all `git` operations (should restrict to read/status/commit/push, not delete history)
- Tool broker fails to validate path; builder deletes arbitrary files
- Builder somehow invokes PowerShell directly (workaround to broker)
- Repair loop grants exception for specific operation; exception persists to next run

**Mitigations:**
- [ ] Phase 8: OPA policy explicitly defines allowed operations (whitelist, not blacklist)
- [ ] Phase 8: Tool broker checks operation against policy before execution
- [ ] Phase 8: Prohibited operations include: install/uninstall, shell (unrestricted), auth, secret management, workflow changes
- [ ] Phase 8: All tool calls logged with policy decision and result
- [ ] Phase 8: Tests verify prohibited operations are denied
- [ ] Phase 10: Repair loop logged separately; exceptions not granted across runs
- [ ] Phase 8: No unrestricted PowerShell exposed; only named operations

**Residual risk:** If OPA policy accidentally grants overly broad permission (e.g., `git *`), violation still possible. Mitigation: Policy review in Phase 8 gate.

---

### 12. Incomplete Evidence or False Evidence Trail

**Threat:** Evidence manifest is incomplete, missing links, or contains false evidence (test passed but was mocked). Reviewer relies on false evidence and approves bad code.

**Severity:** HIGH (violates §11, §15, §20 evidence integrity)

**Attack vectors:**
- Sealed test result not recorded in evidence (forgotten)
- Mutation testing report fabricated or modified
- Test run timestamp is stale (reused from previous run)
- Security scan skipped and not logged as exception
- Preview deployment not validated; evidence falsely claims success

**Mitigations:**
- [ ] Phase 15: Evidence manifest schema requires: SHAs, requirements, gates, checks, tests, mutations, security, review, preview, deployment
- [ ] Phase 15: Missing field causes validation failure (fail-closed)
- [ ] Phase 15: Evidence timestamps verified against actual test runs (recorded in Phase 10/11)
- [ ] Phase 11: Reviewer independently verifies test artifacts (cannot be fabricated in memory)
- [ ] Phase 15: Tests verify incomplete evidence manifest blocks auto-merge
- [ ] Phase 16: End-to-end test includes evidence validation gate

**Residual risk:** If test artifacts (logs, reports) are modified after evidence record, trust is broken. Mitigation: Immutable artifact storage (e.g., git commit, timestamp).

---

### 13. GitHub State Drift and Merge Conflict

**Threat:** Local state (worktree, branch, PR) diverges from GitHub remote. Factory attempts to merge wrong SHA or PR conflicts with main.

**Severity:** MEDIUM (violates §11 SHA binding)

**Attack vectors:**
- Human pushes to factory branch (race)
- Main moves forward; factory branch has diverged
- GitHub rebase required but factory doesn't check
- Factory rebases and changes SHA; auto-merge still references old SHA

**Mitigations:**
- [ ] Phase 11: Reviewer binds approval to exact head SHA
- [ ] Phase 12: Auto-merge checks that current PR head SHA equals reviewed SHA
- [ ] Phase 12: If SHA mismatch detected, auto-merge is **disabled**
- [ ] Phase 4: Claim includes lock on branch name; other processes cannot push
- [ ] Phase 11: Reviewer checks git log to ensure no rebases occurred
- [ ] Phase 12: GitHub auto-merge engine provides native merge conflict detection

**Residual risk:** If factory rebases branch without reviewer awareness, SHA changes and auto-merge fails. Mitigation: Factory never rebases (always merge-commit or fast-forward).

---

## Incident Response and Recovery

### Emergency Stop

**Command:** `factory emergency-stop [--reason "human description"]`

**Effects:**
- Blocks new issue claims (scheduler stops at next check-in)
- Disables pending auto-merges (GitHub API call)
- Records reason and timestamp in SQLite and logs
- Operator notified via logs

**Recovery:**
```
factory queue
# Review quarantined runs and bad deployments
factory resume
# Explicitly clears stop flag
```

### Stall Detection and Diagnosis

**Trigger:** Repair cycle repeats same failure twice without measurable progress

**Response:**
- [ ] Fresh diagnostic session started
- [ ] Competing hypotheses ranked with evidence
- [ ] Smallest reversible experiment executed
- [ ] If evidence doesn't improve, stop (do not loop indefinitely)

### Production Quarantine

**Trigger:** Deployment fails or smoke test fails

**Response:**
- [ ] Bad SHA recorded in SQLite quarantine table
- [ ] New issue claims paused (emergency-stop implicit)
- [ ] Logs reference recovery procedure (in ADRs, not auto-invent)
- [ ] Manual recovery required: verify last-known-good state, approved recovery steps, explicit resume

---

## Assumptions and Limitations

| Assumption | Rationale | Mitigation |
|---|---|---|
| Ollama service is running and responsive | Local model must be available | Monitored in Phase 3 healthcheck |
| GitHub API rate limits are respected | Prevent 429 errors blocking deployment | Retry-with-backoff in Phase 4 |
| Cloudflare account/API token are valid | Deployment depends on valid creds | Tested in Phase 13 smoke test |
| File permissions allow factory access to worktrees | Factory must read/write code | Verified in Phase 8 |
| Main branch is protected and cannot accept direct push | Security boundary | GitHub branch protection rules |
| Investisor repo is not compromised | Assume normal Git integrity | Evidence chain links to GitHub SHA |
| Model inference is deterministic or seeds are logged | Reproducibility | Seed recorded in run record |
| Developer machine is not malware-infected | Local security assumed | Out of scope (general Windows security) |

---

## Test Cases (Phase 1 Deliverables)

Each threat above will have corresponding unit/integration tests:

| Threat | Test Phase | Test Case |
|---|---|---|
| Context leakage | 5 | Builder cannot read sealed test import |
| Test weakening | 11 | Reviewer detects deleted test in diff |
| Sealed test exposure | 5 | Sealed file access denied to builder |
| Prompt injection | 7 | Injection payload classified as invalid (no source) |
| Credential exposure | 6 | GH_TOKEN not in subprocess stdout |
| Self-modification | 16 | Protected-path change blocks auto-merge |
| Bad deployment | 14 | Quarantine prevents next merge |
| Claim race | 4 | Concurrent claims fail deterministically |
| Context metadata tampering | 5 | Corrupted manifest rejected |
| Hallucination | 7 | Unsupported assumption classified as strategic_ambiguity |
| Prohibited operation | 8 | Delete operation denied by OPA |
| False evidence | 15 | Incomplete manifest blocks auto-merge |
| SHA drift | 12 | SHA mismatch disables auto-merge |

---

## Residual Risk Acceptance

**Accepted:**

1. **Model hallucination** — Residual despite critics; Phase 7 challenge gate limits but doesn't eliminate. Mitigation: Phase 11 reviewer catches during review.
2. **File permission misconfiguration** — Potential for cross-role access on shared volume. Mitigation: Phase 5 leakage tests verify boundary.
3. **Sophisticated prompt injection** — Could still influence model reasoning. Mitigation: Phase 11 independent reviewer as witness.
4. **Weak smoke tests** — Could miss production bugs. Mitigation: Phase 9 mutation testing catches weak tests.

**Not accepted (must mitigate):**

1. **Credential exposure** — Mitigated by redaction and env-only storage.
2. **Self-modification** — Mitigated by protected-path gate in auto-merge.
3. **Test weakening** — Mitigated by sealed storage and leakage tests.
4. **Sealed test exposure** — Mitigated by context isolation and Phase 5 verification.

---

## Recommendations for Production

1. **Monitor resource usage** in Phase 6 benchmarks; adjust model if pagefile thrashing occurs.
2. **Audit log access** to protected paths in Phase 8; catch misconfiguration early.
3. **Run threat model review** before Phase 13 (production deployment); ensure all gates are enforced.
4. **Implement intrusion detection** on `.factory-control/` directory; alert if unauthorized access attempted.
5. **Test emergency stop** monthly; verify it blocks new merges and is easy to invoke.

---

*Threat Model Version 1.0  
Generated: 2026-10-03  
Authority: DARK_FACTORY_MASTER_PLAN.md, DARK_FACTORY_BUILD_PROMPT.md  
Next Review: After Phase 8 (Tool Authorization and OPA policy implementation)*

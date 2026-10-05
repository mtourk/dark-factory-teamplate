# Execution Prompt: Audit, Backlog, Implement, Verify, and Resume

You are the principal engineer coordinating completion of this repository.

The repository contains `FEATURE_FACTORY_MASTER_PLAN.md`. It is the binding product and implementation specification. Some features may already be implemented. Your first responsibility is not to rewrite the system. Your first responsibility is to establish exactly what exists, what is incomplete, what is missing, and what is verified.

## 1. Mandatory first actions

1. Read `FEATURE_FACTORY_MASTER_PLAN.md` completely.
2. Inspect every relevant repository area, existing database migrations, Worker routes, frontend pages, local FactoryFlow services, GitHub workflows, tests, configuration, and documentation.
3. Inspect deployed-resource configuration only through existing safe interfaces. Do not expose secrets.
4. Create or update:
   - `.factory-plan/implementation-status.yml`
   - `.factory-plan/backlog.yml`
   - `.factory-plan/dependency-graph.yml`
   - `.factory-plan/decisions.yml`
   - `.factory-plan/blockers.yml`
   - `.factory-plan/execution-journal.md`
   - `.factory-plan/verification-index.yml`
5. Convert every phase and deliverable in the master plan into uniquely identified backlog items.
6. Mark each item `not_started`, `partially_implemented`, `implemented_unverified`, `verified_complete`, or `blocked`.
7. Cite repository paths, tests, deployed objects, and commands as status evidence.
8. Never mark an item complete merely because a file or page exists.
9. Build the dependency graph and select the first highest-priority unblocked incomplete item.
10. Implement only that item, verify it, update status/evidence/journal, commit the status update, then select the next item.

Do not ask for confirmation between ordinary implementation items. Continue until no eligible item remains, a genuine blocker is reached, or an emergency stop is active.

## 2. Resume protocol

At every start or restart:

1. Read `.factory-plan/implementation-status.yml`.
2. Compare recorded status with repository and deployment reality.
3. Repair stale or incorrect status entries.
4. Check for an active item and its last safe checkpoint.
5. Resume that item if safe; otherwise select the next eligible item.
6. Never redo `verified_complete` work unless evidence is invalid or regression tests fail.
7. Before exiting or stopping, record the exact next action.

The plan files are part of the implementation and must be committed continuously.

## 3. Product boundary

Build the complete first release described in the master plan:

- responsive portal;
- single-user/admin profile;
- text and voice idea intake;
- Gemini transcription and TTS only;
- local Ollama + BMAD reasoning;
- one multiple-choice question at a time;
- live editable specification and acceptance criteria;
- existing/new GitHub repository flows;
- repository/project/backlog/milestone/resource/subdomain creation;
- D1-backed durable queue;
- local Windows factory processing one request at a time;
- isolated decision and review agents;
- monitoring and admin controls;
- autonomous PR/preview/auto-merge/deployment/production validation;
- durable implementation status and continuation.

## 4. Strict Gemini boundary

Gemini may handle microphone audio, automatic-language transcription, audio transport, and speech synthesis from supplied text. Gemini must not analyze requirements or generate conversational content.

Required path:

```text
microphone -> Gemini transcript -> editable text -> local Ollama + BMAD
-> local response text -> display -> optional Gemini TTS
```

Never store raw audio. Never send repository code or BMAD context to Gemini. Never put a long-lived Gemini key in browser code.

## 5. BMAD conversation behavior

Ask exactly one primary question at a time. Provide numbered multiple-choice options plus free text. Always include an option permitting the factory to use its best judgment for that topic. Record such choices as user-delegated assumptions.

Do not enforce a fixed question count. Continue until the quality gate passes or assumptions are delegated. Update and autosave the visible draft and acceptance criteria after every accepted answer. Submission requires an explicit user click.

## 6. Context and subagent isolation

Every model role uses a new session identified by project, run, role, and session ID. Never pass raw chats between analyst, critics, decision agent, builder, repairer, sealed QA, or reviewer.

The reviewer receives only objective artifacts built by the orchestrator. The builder never sees hidden tests or reviewer rubrics. The decision agent receives requirements, certified knowledge, ADRs, options, and evidence, but no builder private memory.

Every context package requires a manifest, hashes, explicit exclusions, and a policy decision. Unauthorized access fails closed.

## 7. Secret handling

The user may enter GitHub, Gemini, Cloudflare, and other provider credentials through settings. Treat them as secrets, not ordinary profile data.

Never store secret values in raw D1 columns, prompts, transcripts, model responses, logs, monitoring pages, or downloadable artifacts. Store secret references and masked metadata. Never expose secrets to Ollama or subagents.

The user's request to store prompts and responses as raw unencrypted text applies only to non-secret content.

## 8. Decision authority

The isolated decision agent may make technical and product decisions and log all of them with sources, alternatives, criticality, reversibility, and confidence. However, it may not bypass immutable governance, protected paths, secret boundaries, required checks, or production safety.

Display decisions in the web portal and allow review/override. If policy determines execution cannot safely continue, block only that run and process the next queued request.

## 9. Monitoring requirements

Implement admin-only views for queue, request detail, live stage, role, model, repository, branch, tests, repairs, PR, preview, deployment, decisions, prompts, visible responses, tokens, context use, timings, CPU, RAM, GPU/shared memory when available, Ollama, tunnel, and connectivity.

Never display or store private reasoning. If a metric cannot be measured, display `not_available`; never invent it.

Implement controls for reorder, pause, resume, stop, retry, cancel, disable auto-merge, and emergency stop.

## 10. Autonomous delivery rules

The factory may create repositories, project resources, D1/KV/R2 bindings, DNS records, milestones, issues, branches, PRs, previews, and production deployments under configured authority.

It must use idempotency keys for every resource creation. It must never create a duplicate resource on retry. It must never automatically delete a subdomain or project resource.

Use GitHub required checks and exact-SHA auto-merge. Never push directly to `main`, use administrator bypass, remove required checks, or auto-merge governance changes.

After merge, validate production. Stop new merges while production state is unknown.

## 11. Per-item execution cycle

For every backlog item in `.factory-plan/backlog.yml`:

1. Confirm dependencies are verified complete.
2. Set status to `in_progress` by recording it in the item's metadata/journal.
3. Record current repository/deployment baseline.
4. Implement the smallest coherent scope satisfying that item.
5. Run listed verification commands.
6. Run a secondary consistency check against the master plan.
7. Record paths, commits, tests, screenshots or deployment evidence as appropriate.
8. Set final status.
9. Update dependency graph and next action.
10. Commit implementation and status together.
11. Only then move to the next item.

If interrupted, the next agent must be able to resume without guessing.

## 12. Prohibitions

Never:

- replace working code simply to match a preferred stack without migration justification;
- mark unverified implementation complete;
- start the next plan item before committing status;
- lose the exact next action on shutdown;
- treat API keys as user login;
- store raw provider tokens;
- let Gemini answer BMAD questions;
- store raw audio;
- ask multiple primary BMAD questions in one turn;
- expose Ollama publicly or to the browser;
- share private agent memory;
- expose sealed tests;
- display chain-of-thought;
- fabricate unavailable metrics;
- allow unlimited repair cycles;
- weaken tests to obtain a pass;
- merge a SHA different from the reviewed SHA;
- use admin merge bypass;
- continue merging during unknown production state;
- automatically delete DNS, repositories, or Cloudflare data;
- silently install Docker, Ubuntu, or a VM.

## 13. Future-scope protection

Do not implement teams/organizations, shared ideas, attachments, multiple factory machines, additional Git providers, automatic resource deletion, downloadable reports, additional UI languages, quotas/billing, or cloud LLM fallback in release 1. Record them under the Future Ideas section only.

## 14. Completion gate

Do not declare completion until:

- every current-scope plan item is `verified_complete` or has an explicit approved blocker;
- the implementation status matches the repository and deployment;
- all required automated suites pass;
- an existing-repository pilot completes by both text and voice intake;
- BMAD questions, draft review, queue, local execution, monitoring, decisions, PR, preview, auto-merge, production validation, issue completion, and next-item behavior work end to end;
- restart/resume has been tested from durable status;
- future items are separated and not mixed into current release.

Begin now by reading `FEATURE_FACTORY_MASTER_PLAN.md`, then perform the implementation audit. Do not ask for confirmation between backlog items.

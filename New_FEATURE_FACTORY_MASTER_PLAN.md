# Autonomous Feature Factory Portal and Local Dark Factory

## 0. Authority, audit-first execution, and continuation contract

This document is the authoritative product, architecture, security, implementation, and acceptance plan for the complete Feature Factory system.

The implementation team or implementation agent MUST NOT assume the repository is empty. Some elements may already exist. Before adding or changing implementation, it MUST:

1. Read this entire document.
2. Inspect the repository, database schema, deployed Cloudflare resources, GitHub workflows, local Windows services, and current UI.
3. Map every requirement in this plan to one of five statuses:
   - `not_started`
   - `partially_implemented`
   - `implemented_unverified`
   - `verified_complete`
   - `blocked`
4. Create or update a durable project-plan backlog inside the repository.
5. Record evidence for each status. Never mark an item complete because a similarly named file exists.
6. Select the first unblocked, highest-priority item whose dependencies are complete.
7. Implement and verify only that item.
8. Update its status, evidence, test results, decisions, and next item before starting another item.
9. Commit the updated project status with the implementation.
10. On restart, read the project status and resume from the first incomplete eligible item without redoing verified work.

### 0.1 Mandatory repository planning artifacts

The repository MUST contain:

```text
.factory-plan/
├── MASTER_IMPLEMENTATION_PLAN.md
├── implementation-status.yml
├── backlog.yml
├── dependency-graph.yml
├── decisions.yml
├── blockers.yml
├── execution-journal.md
├── verification-index.yml
└── phases/
    ├── phase-00-audit.yml
    ├── phase-01-foundations.yml
    └── ...
```

`implementation-status.yml` is the machine-readable source of truth for resumability.

Each implementation item MUST contain:

```yaml
id: FF-PORTAL-001
phase: portal-foundation
title: Portal application shell
status: partially_implemented
priority: critical
dependencies: []
repository_paths: []
existing_evidence: []
missing_work: []
acceptance_criteria: []
verification_commands: []
verification_evidence: []
last_updated_at: null
last_updated_by: null
next_action: null
blocker_id: null
```

### 0.2 Completion discipline

An item is `verified_complete` only when:

- its code/configuration exists;
- its acceptance criteria pass;
- relevant automated tests pass;
- security and context-boundary checks pass;
- evidence is recorded in `verification-index.yml`;
- the repository documentation is updated;
- the item and dependency graph are updated;
- the next eligible item is identified.

No agent may move to the next item until the current item's status update is committed.

---

# 1. Product vision

Build a single-user, administrator-controlled web product that converts ideas into deployed software.

The product has two major planes:

1. **Cloud Product Plane**
   - web portal;
   - user/profile/settings;
   - text and voice idea intake;
   - BMAD-powered requirements conversation;
   - draft specification and acceptance review;
   - repository selection or creation;
   - queue and status persistence;
   - monitoring and decision pages;
   - Cloudflare D1 data;
   - Cloudflare Worker APIs;
   - Cloudflare Tunnel integration status.

2. **Local Factory Plane**
   - Windows-native FactoryFlow orchestrator;
   - native Ollama model gateway;
   - BMAD analysis;
   - isolated critics and decision agents;
   - code generation through Aider or a compatible harness;
   - tests, hidden QA, independent review;
   - GitHub repository creation and delivery;
   - Cloudflare project/resource/DNS creation;
   - preview/production deployment;
   - production validation;
   - continuous queue processing.

### 1.1 End-to-end user journey

```text
Login
→ Dashboard
→ New Idea
→ type text or speak
→ Gemini transcription only
→ user edits transcript
→ cloud LLM gateway (OmniRoute) + BMAD asks one multiple-choice question
→ user answers with option number or text/voice
→ acceptance criteria and specification update after each answer
→ conversation continues until BMAD quality gate passes or user selects
  “Use your best judgment and assumptions”
→ user reviews editable specification
→ user chooses existing repository or new repository
→ user configures repository/project/deployment attributes
→ user clicks Submit
→ request enters queue
→ local laptop claims it when online
→ autonomous feature factory executes
→ monitoring page shows stages, model, prompts, outputs and metrics
→ decisions are logged and prioritized by criticality
→ factory opens PR, previews, auto-merges, deploys and validates
→ idea/request becomes completed
```

---

# 2. Fixed environment and constraints

```yaml
host:
  os: Windows 11
  shell: PowerShell 7
  laptop: HP EliteBook 8 G1i 16
  cpu: Intel Core Ultra 7 265H
  system_ram_gb: 32
  gpu: Intel Arc 140T integrated
  dedicated_vram_gb: 0
local_inference:
  runtime: Ollama for Windows
  cloud_fallback: cloud_provider_failover_only
  local_llm_fallback: deferred_until_after_release_1
  concurrency: 1 active implementation
  initial_context_tokens: 8192
  experimental_context_tokens: 16384
cloud:
  platform: Cloudflare
  database: D1
  api: Workers + TypeScript
  domain_zone: mtourk.com
source_control:
  provider: GitHub only
first_release_scope: complete target
pilot: existing repository
```

The factory MUST process only one active implementation because the local model shares 32 GB RAM with Windows and test tooling. Queued requests may be unlimited in the database.

---

# 3. Selected architecture decisions

## 3.1 Frontend

Use **React + Vite + TypeScript** with **shadcn/ui + Tailwind CSS**.

Rationale:

- well suited to an interactive dashboard and chat workflow;
- straightforward Cloudflare deployment;
- component primitives for forms, tables, dialogs, drawers, badges, timelines, command menus, and responsive layouts;
- avoids coupling the factory portal to a server-side framework while the backend already uses a Cloudflare Worker.

The UI must be responsive for desktop and mobile. Desktop is primary for monitoring, but all core user actions must remain usable on mobile.

## 3.2 Backend

Use Cloudflare Worker + TypeScript. All environment-specific values must be externalized.

Required configuration layers:

```text
config/defaults.json
config/schema.json
wrangler.jsonc or wrangler.toml
Cloudflare environment variables
Cloudflare secrets
D1 bindings
per-installation setup record
```

No repository URL, Worker name, D1 ID, GitHub owner, Cloudflare account, tunnel name, zone, or domain may be hardcoded.

## 3.3 Authentication

An API token is not a user-authentication design.

For release 1, use a simple administrator-created single-user authentication flow. Preferred implementation:

1. Cloudflare Access protects the portal if available in the current environment.
2. The application maintains its own `users` profile record and admin flag.
3. If Cloudflare Access is not currently implemented, the audit must create a blocking security item rather than silently treating a GitHub or Cloudflare PAT as a login credential.

Provider tokens are integrations, not login credentials.

## 3.4 Secrets

Never store GitHub PATs, Gemini keys, Cloudflare tokens, or tunnel credentials as raw values in D1 or prompt logs.

The UI may collect/update them, but the backend must write them to an approved secret store or Cloudflare secret binding and store only secret metadata/reference in D1:

```yaml
provider: github
reference: secret-ref-id
masked_hint: "github_pat_...abcd"
created_at: ...
last_validated_at: ...
permissions_summary: ...
```

Although prompts and model responses are stored as requested, secrets MUST be detected in integration fields and excluded from prompts, transcripts, model context, logs, and monitoring output.

## 3.5 Cloud/local communication

Preferred initial design:

```text
Portal submits request to Worker/D1
→ local FactoryFlow polls D1-backed jobs API over outbound HTTPS
→ FactoryFlow atomically claims one job
→ local system posts events/status/results back to Worker
→ web portal reads status from D1/Worker
```

Cloudflare Tunnel is used for admin diagnostics or local callback functionality only when required. The laptop does not need open inbound ports for normal queue processing.

Offline behavior: requests remain queued in D1 and begin processing when the local factory resumes.

---

# 4. Gemini voice boundary

Gemini is a voice transport service, not the reasoning engine.

## 4.1 Allowed Gemini responsibilities

- receive microphone audio;
- automatically detect spoken language;
- transcribe speech to text;
- return transcription to the portal;
- synthesize supplied response text to audio;
- transport audio events.

## 4.2 Forbidden Gemini responsibilities

Gemini must not:

- analyze the idea;
- generate requirements;
- ask BMAD questions from its own reasoning;
- choose answers;
- generate acceptance criteria;
- decide implementation;
- receive repository source code;
- act as factory reviewer.

## 4.3 Required voice flow

```text
Browser microphone
→ Gemini transcription session
→ finalized text transcript
→ transcript displayed and editable
→ user confirms/sends
→ local Ollama model + BMAD processes text
→ local model produces response text
→ response displayed
→ optional Gemini TTS speaks the exact supplied response
```

Raw audio must never be stored. Final and edited transcripts are stored until soft-deleted by the user.

The system need not display partial reasoning or token-by-token model generation. It may show processing state, then render the completed question/answer.

## 4.4 API-key handling

The browser must not receive a long-lived Gemini API key. The backend must issue an appropriate short-lived voice session credential or proxy the session according to the selected Gemini integration. The implementation audit must verify the currently used integration against current official Gemini documentation.

---

# 5. Requirements conversation and BMAD interaction

## 5.1 One-question protocol

To avoid long turns and timeouts, BMAD interaction asks exactly one primary question at a time.

Every normal question must provide multiple-choice options:

```yaml
question_id: Q-001
question: "Who should be able to use this feature?"
options:
  - id: 1
    text: "Only the project owner"
  - id: 2
    text: "All authenticated users"
  - id: 3
    text: "Selected users"
  - id: 4
    text: "Use your best judgment"
allow_free_text: true
```

The user may answer by:

- entering the option number;
- entering free text;
- speaking, with Gemini converting speech to text.

Every question set must include a visible option equivalent to:

> Use your best judgment and assumptions; stop asking about this topic.

Selecting it grants delegated assumption authority for that topic. The system must record the assumption, rationale, reversibility, and source as user-delegated, not as an established business fact.

## 5.2 No fixed question limit

The conversation continues until:

- the requirements quality gate passes;
- no required question remains;
- or the user delegates assumptions for remaining topics.

Only one outstanding question may be active at once.

## 5.3 Live draft

After every accepted answer, update and persist the current draft:

- title;
- summary;
- problem;
- business value;
- target users;
- functional requirements;
- non-functional requirements;
- acceptance criteria;
- assumptions;
- non-goals;
- risks;
- repository mode;
- deployment target;
- priority.

The user may edit any field. Autosave every change with debounce and optimistic concurrency. Preserve only the current draft for release 1, but record submitted versions and later change requests as run records.

## 5.4 Submission

The request remains `draft` until the user explicitly clicks Submit.

Submission requires:

- requirement quality gate passed or delegated assumptions recorded;
- repository mode selected;
- repository/project name confirmed;
- required integration credentials validated;
- deployment target confirmed;
- acceptance criteria non-empty;
- user confirmation that submission authorizes repository/resource creation.

After submission, create a queued factory request and prevent silent mutation. Subsequent edits create a change revision and may trigger stop/replan if execution has started.

---

# 6. Portal information architecture

## 6.1 Login

- protected sign-in;
- show service health when local factory is offline;
- no provider token fields on login.

## 6.2 Dashboard

- New Idea action;
- user drafts;
- submitted requests;
- status summaries;
- decision-required alerts;
- completed projects;
- local factory online/offline indicator.

## 6.3 New Idea

- text entry;
- microphone action;
- transcription editor;
- repository mode section;
- generated project/repository/subdomain suggestions;
- initial priority;
- save draft.

## 6.4 Requirements Conversation

- one BMAD question;
- numbered choices;
- free-text/voice answer;
- acceptance-criteria panel updated after each answer;
- requirements completeness indicator;
- delegated-assumption option;
- conversation history;
- no private reasoning display.

## 6.5 Acceptance Review

Editable sections for all required final attributes. Show warnings for delegated assumptions, missing credentials, destructive resource plans, and unsupported project profiles.

## 6.6 Request Details

Display creator, creation/submission timestamps, priority, repository, project, requirements, criteria, assumptions, decisions, stages, evidence, PR, previews, production URL, and status history.

## 6.7 Factory Monitor, admin only

Table of all requests with:

- order;
- user;
- title;
- priority;
- queue/running status;
- current stage;
- current role;
- active model;
- elapsed time;
- repository and branch;
- test status;
- repair attempt;
- PR;
- preview;
- deployment;
- decision count and highest criticality.

Admin controls:

- reorder queued items;
- pause queue;
- resume queue;
- stop active run;
- retry failed stage;
- cancel request;
- disable/enable auto-merge for run;
- emergency stop;
- inspect full prompts and responses;
- inspect resource metrics.

Do not display or store private chain-of-thought. Show structured decisions, evidence, model inputs/outputs, tool events, and summaries only.

## 6.8 Decision Queue

Show all decisions sorted by criticality, then time. Include decision class, options, selected decision, sources, reversibility, status, run, and impact.

The decision agent may make all decision classes autonomously because the user requested this. However:

- every decision must be logged;
- critical/irreversible/product/governance/legal decisions must be highlighted;
- the system should support review and later override;
- governance controls still forbid the factory from changing its own protected authority through an ordinary run.

If a decision is later marked human-required by policy or cannot be safely executed, the affected run is blocked and the queue continues.

## 6.9 User Profile

- name;
- email;
- company;
- preferred language;
- GitHub identity;
- integration status;
- idea/project list;
- soft-deletion actions;
- secret update actions.

## 6.10 Repository Settings

- existing/new repository mode;
- GitHub owner;
- repository URL;
- generated/editable repository name;
- visibility;
- project profile;
- default branch;
- tokens and validation status;
- Cloudflare account/zone/tunnel configuration references;
- domain/subdomain;
- deployment settings.

---

# 7. Data model in Cloudflare D1

Use Wrangler D1 migrations. The exact existing schema must be audited and migrated rather than replaced blindly.

Required logical entities:

```text
users
user_profiles
integration_secret_refs
ideas
idea_drafts
conversations
conversation_messages
transcripts
requirements_snapshots
acceptance_criteria
repositories
projects
project_resources
factory_requests
queue_entries
runs
run_stages
agent_sessions
context_packages
model_calls
tool_calls
test_results
decisions
artifacts
evidence_manifests
deployments
notifications
system_metrics
status_events
soft_deletions
configuration_profiles
```

## 7.1 Core fields

Every user-owned business record includes `id`, `user_id`, `created_at`, `updated_at`, and `deleted_at` where soft deletion applies.

Every run record includes request, project, repository, current state, current stage, active lease, base/head SHA, PR, queue position, retry/repair counters, and stop/quarantine flags.

Every model call stores:

- run/stage/session/role;
- model and digest;
- prompt text;
- response text;
- input/output token counts when available;
- context token usage;
- load duration;
- first-token latency;
- total duration;
- generation rate;
- outcome;
- context-package ID.

Never store private model reasoning. Store only visible response text and structured artifacts.

## 7.2 Retention

Run metadata, prompts, responses, transcripts, metrics, decisions, and evidence are retained indefinitely unless soft-deleted by the user. Soft deletion hides and excludes records from active retrieval but preserves relational integrity. Raw audio is never stored.

---

# 8. Queue and local connectivity

## 8.1 Queue semantics

Default user-created order is submission order. Users may set priority. Admin may reorder queue explicitly.

Only one request can be `running` locally. Others remain queued. The queue is durable in D1 and survives laptop restarts.

## 8.2 Claim protocol

The local FactoryFlow agent:

1. authenticates to the Worker jobs API;
2. checks emergency stop and local capacity;
3. requests the next eligible queue item;
4. atomically claims it with a lease;
5. sends heartbeat;
6. updates stages/events;
7. releases or completes claim.

Lease recovery must inspect local worktree, GitHub branch/PR/SHA, preview, merge, and deployment before restarting.

## 8.3 Request edits

- Queued request edit: update draft/submission revision and re-evaluate queue metadata.
- Running request edit: create a new revision, pause current run at a safe boundary, invalidate downstream context/evidence, and replan from the earliest affected stage.
- Cancel queued request: mark canceled.
- Cancel running request: stop processes, disable pending auto-merge, preserve evidence, mark canceled.

## 8.4 Cloudflare Tunnel

Use Cloudflare Tunnel for secure admin/local diagnostics or callbacks where necessary. Normal operation should prefer outbound polling so the laptop does not need a public inbound service.

---

# 9. GitHub integration

GitHub only. Existing repositories are authorized by the requesting user's PAT for release 1. Prefer fine-grained PATs with least permissions. Never expose PAT to the local model or store it as plain D1 text.

## 9.1 Existing repository

Validate:

- repository exists;
- token owner can access it;
- required content/issues/workflow/PR permissions exist;
- default branch and rules are readable;
- project can configure required checks and auto-merge, or record a blocker.

## 9.2 New repository

On final submission:

- create a private repository under the requesting user;
- use generated/editable name;
- initialize selected profile;
- generate README, architecture, tests, CI/CD, factory config, security, and governance;
- create complete backlog split into milestones;
- configure branch protection/checks/auto-merge;
- create project resources;
- configure preview and production;
- create subdomain;
- record all resources.

## 9.3 Project profiles

- React/Vite web application;
- Cloudflare Worker service;
- React + Worker full application;
- language-agnostic existing repository.

## 9.4 Backlog generation

For a new project, generate:

- milestones;
- architecture/foundation issues;
- user-facing feature issues;
- quality/security issues;
- deployment/operations issues;
- dependencies and priorities;
- acceptance criteria per issue.

Backlog issues created by the factory become eligible only when their dependencies and milestone policy allow.

---

# 10. Cloudflare resources, DNS, and deployment

The installation configuration must dynamically identify account, Worker, D1, repositories, tunnel, zone, and defaults.

## 10.1 New project resources

Create automatically when needed:

- Worker/Pages or Workers Assets project;
- D1 database;
- KV namespace;
- R2 bucket;
- other approved Cloudflare binding;
- preview deployment;
- production deployment;
- DNS record under `mtourk.com`;
- subdomain `app-name.mtourk.com`.

Resource creation must be idempotent and recorded in `project_resources`.

## 10.2 Naming

Generate repository/project/subdomain names from accepted title. User can edit before submission. DNS collision adds numeric suffix. Archived projects keep their subdomain until manual admin cleanup.

## 10.3 Preview

Use Cloudflare-generated preview URLs. Preview acceptance must pass before auto-merge.

## 10.4 Production

Merge to `main` triggers production deployment. Validate deployed version, health, core browser path, API contracts, and project-specific invariants. Unknown production state pauses all new merges.

---

# 11. Local FactoryFlow, agents, and context isolation

Retain all context-management constraints from the factory plan:

- fresh session for every role;
- `project_id + run_id + role + session_id` identity;
- role-scoped private storage;
- context-package manifests and hashes;
- no raw conversation sharing;
- builder cannot access sealed tests;
- reviewer cannot access builder memory;
- orchestrator builds reviewer package from objective artifacts;
- long-term memory accepts only certified evidence-backed lessons;
- cross-run and cross-project leakage tests fail closed.

## 11.1 Requirement critics

Separate sessions:

- Product;
- Domain Rules;
- Testability;
- Security/Permissions;
- Contradiction;
- Operations/Recovery.

Findings are classified, not majority-voted.

## 11.2 Decision agent

Use the same local model in a fresh isolated session.

Input:

- original requirement;
- certified project knowledge;
- ADRs;
- options;
- evidence;
- consequences;
- builder memory excluded.

Output:

- decision;
- decision class;
- criticality;
- sources;
- constraints;
- alternatives;
- reversibility;
- confidence;
- human/blocking status.

All decisions are stored and visible in the portal. Decisions may be autonomous, but protected-governance policy still cannot be bypassed.

---

# 12. Monitoring and observability

## 12.1 Event model

FactoryFlow emits typed events to Worker/D1:

- request claimed;
- stage started/completed/failed;
- agent session started/completed;
- context package built;
- model call completed;
- tool authorized/executed;
- test result;
- repair attempt;
- decision;
- Git commit/PR/check;
- preview/deployment;
- production validation;
- queue item completed/canceled.

## 12.2 Metrics

Show:

- prompt/response/context tokens;
- model load;
- first-token latency;
- total generation duration;
- generation rate;
- stage/run durations;
- CPU;
- RAM;
- Intel GPU/shared-memory where available;
- Ollama health and active model;
- queue depth;
- D1/Worker connectivity;
- tunnel status.

If a metric is unavailable from a runtime, display `not_available`, never fabricate it.

## 12.3 Prompt/response history

Admin may view full visible prompts and full visible responses. Secrets and credentials are redacted. No private reasoning is stored or displayed.

---

# 13. Notifications

Web-only notifications for:

- decision logged/required;
- request blocked;
- stage failure;
- delivery failure;
- production incident;
- successful completion;
- cancellation;
- laptop/factory offline or restored.

Routine stage progress appears in monitoring rather than intrusive notifications.

---

# 14. Security and privacy controls

Despite the requested simple single-user release, implement minimum safe controls:

- authenticated portal;
- administrator authorization server-side;
- CSRF/origin protection;
- secure cookies;
- rate limiting;
- input validation;
- secret-store references;
- token masking;
- no raw audio retention;
- no private reasoning storage;
- no secrets in model prompts;
- no direct browser-to-Ollama access;
- no direct public Ollama endpoint;
- outbound authenticated local worker connection;
- protected factory governance;
- audit-style status events even if an immutable audit log is not required.

The user's choice of raw, unencrypted prompt/response storage applies to non-secret text only. Provider tokens remain secret.

---

# 15. Autonomous delivery workflow

1. Claim request.
2. Resolve repository mode.
3. For new project, provision repository/resources and create milestone backlog.
4. Build certified project context.
5. Run BMAD requirement preflight.
6. Run isolated critics.
7. Compile intent and delegated assumptions.
8. Select assurance workflow.
9. Design public and sealed QA before implementation.
10. Create isolated worktree.
11. Implement through controlled harness.
12. Run checks in deterministic order.
13. Repair within bounded cycles.
14. Run fresh independent review bound to SHA.
15. Push branch and open PR.
16. Deploy preview and validate.
17. Ensure required checks and evidence manifest pass.
18. Enable auto-merge for exact SHA, never admin bypass.
19. Deploy production from `main`.
20. Validate production.
21. Mark request complete.
22. Update implementation status and project backlog.
23. Clean up safe temporary resources.
24. Claim next queued request.

---

# 16. Implementation phases for this enhanced product

Every phase begins with audit of existing implementation. The agent must create individual backlog items for every listed deliverable and preserve statuses.

## Phase 00: Repository and deployment audit

- inspect existing portal, Worker, D1, migrations, routes, authentication, monitoring, local factory, GitHub workflows, Cloudflare resources;
- map existing code to this plan;
- create implementation status and dependency graph;
- do not delete working implementation merely to match preferred structure;
- identify migration strategy.

## Phase 01: Configuration and installation portability

- dynamic installation configuration;
- JSON schema validation;
- environment profiles;
- existing Worker/repository/D1 references;
- portable bootstrap;
- secret references;
- configuration UI.

## Phase 02: D1 schema and migrations

- audit current schema;
- create forward migrations;
- entities and indexes;
- soft-delete behavior;
- queue/lease consistency;
- migration verification/rollback policy.

## Phase 03: Authentication, admin, profiles, secret settings

- single-user/admin-created auth;
- server-side authorization;
- profile fields;
- integration secret update and validation;
- token masking;
- no PAT-as-login.

## Phase 04: Responsive application shell

- React/Vite/TypeScript;
- shadcn/Tailwind;
- desktop/mobile navigation;
- route guards;
- loading/error/offline states;
- accessibility baseline.

## Phase 05: Idea drafts and text intake

- New Idea page;
- autosave;
- multilingual text accepted;
- repository mode;
- generated/editable names;
- priority;
- validation.

## Phase 06: Gemini voice integration

- microphone permission and state;
- transcription with automatic language detection;
- editable transcript;
- no raw audio storage;
- local response text to TTS;
- no Gemini reasoning;
- API-key/session security;
- voice error and retry handling.

## Phase 07: BMAD conversation service

- one-question protocol;
- numbered choices;
- free-text and voice answers;
- delegated-assumption option;
- quality gate;
- completed-response rendering;
- conversation persistence;
- timeouts/recovery.

## Phase 08: Live requirement/acceptance draft

- editable specification;
- acceptance update after each answer;
- autosave;
- completeness state;
- submission validation;
- submitted immutability/revisions.

## Phase 09: Repository selection and creation

- existing repository authorization/testing;
- PAT secret handling;
- new repository creation;
- private default;
- project profiles;
- generated/editable names;
- initial backlog/milestones;
- required checks and factory config.

## Phase 10: Cloudflare project/resource provisioning

- D1/KV/R2/Worker resources as needed;
- resource idempotency;
- Preview and production;
- `app-name.mtourk.com` DNS;
- collision suffix;
- no automatic deletion;
- resource inventory.

## Phase 11: Cloud-local queue and connectivity

- D1-backed jobs API;
- outbound local polling;
- atomic claim/lease/heartbeat/recovery;
- laptop offline queueing;
- Cloudflare Tunnel health and optional callback;
- one active run.

## Phase 12: FactoryFlow and local gateway integration

- connect submitted requests to local FactoryFlow;
- Ollama gateway;
- model aliases/benchmarks;
- context packages;
- worktrees;
- controlled tools;
- status events.

## Phase 13: Critics, decision agent, and decision page

- isolated critics;
- decision-agent session;
- decision criticality;
- logging and portal display;
- review/override behavior;
- blocked item handling while queue continues.

## Phase 14: Sealed QA, verification, repair, reviewer

- hidden test storage;
- failure envelopes;
- deterministic checks;
- mutation testing;
- bounded repair;
- fresh reviewer;
- SHA binding;
- evidence.

## Phase 15: GitHub PR, preview, auto-merge

- push/open PR;
- required checks;
- preview;
- exact-SHA auto-merge;
- no admin bypass;
- governance change blocking.

## Phase 16: Production deployment and recovery

- deploy from `main`;
- production checks;
- last-known-good;
- quarantine;
- recovery;
- stop new merges on unknown state.

## Phase 17: Monitoring and controls

- admin request table/detail;
- live stage/model/status;
- prompt/response view;
- token/performance/system metrics;
- pause/stop/retry/cancel/reorder/emergency/auto-merge control;
- indefinite retention.

## Phase 18: Notifications and request lifecycle

- web notifications;
- queued edit;
- running revision/replan;
- cancellation;
- offline/online;
- completion.

## Phase 19: Status-driven self-continuation

- implementation-status UI/file consistency;
- backlog selection from project plan;
- per-item status commit before next item;
- restart recovery;
- partial implementation detection;
- verification evidence.

## Phase 20: Full pilot on existing repository

- create idea by text;
- create idea by voice;
- complete BMAD questions;
- submit against existing repo;
- queue/offline/claim;
- implement;
- monitor;
- decisions;
- PR/preview/merge/deploy;
- validate;
- completion;
- next item.

---

# 17. Acceptance suites

Required suites:

- authentication/authorization;
- secret boundary;
- responsive UI;
- draft autosave;
- multilingual text;
- voice transcription/TTS boundary;
- one-question BMAD;
- delegated assumptions;
- editable acceptance criteria;
- repository authorization/creation;
- Cloudflare resource idempotency;
- DNS collision;
- queue order/admin reorder;
- offline recovery;
- one-run concurrency;
- context isolation;
- hidden QA confidentiality;
- decision logging;
- monitoring metrics;
- cancellation and revisions;
- exact-SHA auto-merge;
- production recovery;
- soft deletion;
- status-driven resume;
- complete existing-repo pilot.

---

# 18. Future ideas, explicitly excluded from current implementation

- organizations and teams;
- shared ideas/projects;
- invitations/open signup;
- file/image/PDF/design attachments;
- multiple local factory machines;
- other Git providers;
- automatic domain/resource cleanup;
- downloadable reports;
- additional UI languages;
- project-level quotas and billing;
- hosted/cloud LLM fallback.

Future items must be recorded separately and must not block release 1.

---

# 19. Critical mistakes to avoid

1. Do not treat provider API keys as user authentication.
2. Do not place long-lived Gemini keys in browser code.
3. Do not allow Gemini to generate BMAD answers.
4. Do not send audio to the factory or store raw audio.
5. Do not ask multiple BMAD questions in one turn.
6. Do not lose draft edits or overwrite concurrent user changes.
7. Do not mutate a submitted request silently.
8. Do not store PATs/tokens in D1 raw text or monitoring logs.
9. Do not expose Ollama publicly or directly to the browser.
10. Do not share agent private memory or reviewer/builder history.
11. Do not let full prompt visibility reveal secrets.
12. Do not fabricate unavailable token or GPU metrics.
13. Do not create duplicate Cloudflare resources on retry.
14. Do not delete DNS/resources automatically.
15. Do not auto-merge a different SHA than reviewed.
16. Do not bypass required checks.
17. Do not continue merging when production is unknown.
18. Do not mark plan items complete without verification evidence.
19. Do not start the next project-plan item before status is committed.
20. Do not restart implementation from scratch after interruption; resume from durable status.

---

# 20. Final Definition of Done

The complete product is done when:

- single-user/admin authentication is safe;
- profiles/settings work;
- text and multilingual input work;
- Gemini transcription and TTS work within the strict boundary;
- raw audio is not stored;
- BMAD asks one multiple-choice question at a time;
- live draft and acceptance criteria update and save;
- user can submit explicitly;
- existing and new GitHub repositories work;
- new repos/resources/backlogs/milestones/subdomains are created;
- Cloudflare D1/Worker configuration is portable;
- local laptop pulls durable queued jobs;
- monitoring shows all requested data except private reasoning;
- admin queue controls work;
- decisions use fresh memory and are logged by criticality;
- local context isolation and sealed QA pass;
- autonomous implementation, review, PR, preview, merge, deployment, and validation pass;
- production recovery/quarantine works;
- implementation plan status can recover after interruption;
- an existing-repository pilot passes end to end;
- future ideas are separated from current scope.


---

# Binding architecture amendment — Release 1 is cloud-only (2026-10-11)

**Read first:** `.factory-plan/CLOUD_FIRST_MIGRATION.md` and `docs/decisions/ADR-008-cloud-first-release.md`.

This amendment takes precedence over conflicting instructions in this older plan, including the fixed-environment block in §2 and any journey, phase, queue, monitoring, or deployment text that makes a local Windows machine, local Ollama, or Cloudflare Tunnel a Release 1 dependency.

For Release 1, model inference runs through the existing external OmniRoute gateway. Agents use a provider-neutral adapter and must not implement provider-specific fallback. Cloud-to-cloud routing is permitted only within configured policy; the default is free-tier-only with no silent paid spend. If all eligible cloud routes fail or are exhausted, persist the request/run and pause or retry it safely. Local Ollama is deferred as a future optional provider and is not part of the initial critical path.

Cloudflare remains the portal/API/D1 layer. Oracle Cloud VM is a candidate for always-on services that do not fit Workers constraints, but no VM migration, DNS change, Tunnel change, or production deployment is implied by this documentation amendment. OmniRoute is an external dependency and its repository must not be modified as part of this work.

The hostname roles and observability requirements are defined in `.factory-plan/CLOUD_FIRST_MIGRATION.md`. Existing DNS/resource state must be audited read-only before any infrastructure mutation. See ADR-008 for decision context and acceptance checks.

# Dark Feature Factory
# Advanced API-First LLM Architecture Migration Plan

## ROLE

Act as a **Principal AI Systems Architect, Agentic Systems Engineer, LLM Infrastructure Engineer, Distributed Systems Engineer, and Senior Full-Stack Engineer**.

You are working on an existing **Dark Feature Factory** project that is intended to operate as an autonomous software-engineering factory.

The factory should eventually be capable of taking a software feature or requirement and autonomously performing activities such as:

```text
Requirement
    ↓
Analysis
    ↓
Clarification / Planning
    ↓
Architecture
    ↓
Task decomposition
    ↓
Implementation
    ↓
Testing
    ↓
Debugging
    ↓
Code review
    ↓
Validation
    ↓
Documentation
    ↓
Git / PR / Delivery
```

The project was initially designed around a **locally hosted LLM**.

That architectural decision is now being reconsidered because the available hardware is not sufficient to make local inference the primary engine for the quality, reasoning capability, context size, latency, and concurrency required by the factory.

Current laptop:

```text
HP EliteBook 8 G1i 16
Intel Core Ultra 7 265H
32 GB RAM
Intel Arc 140T graphics
```

The current implementation uses the local LLM as the primary provider and falls back to Gemini when the local model fails.

The target architecture must reverse this relationship.

The factory should become:

```text
API-FIRST
MULTI-PROVIDER
MULTI-MODEL
MULTI-KEY
FREE-TIER-AWARE
QUOTA-AWARE
FAILURE-AWARE
CONTEXT-AWARE
MEMORY-AWARE
TASK-AWARE
CAPABILITY-AWARE
COST-SAFE
PRIVACY-AWARE
OBSERVABLE
RESUMABLE
```

The local LLM should remain available as an optional provider/fallback, but must no longer be the architectural foundation.

---

# 1. MOST IMPORTANT OBJECTIVE

Do NOT simply replace:

```text
Local LLM
```

with:

```text
Gemini API
```

The required architectural change is much larger.

Build or adopt a reusable **LLM Gateway / Router architecture** that allows the Dark Feature Factory to communicate with an abstract LLM interface while the underlying infrastructure determines:

```text
which provider
which account
which API key
which model
which capability
which quota
which fallback
which retry strategy
```

The Feature Factory agents must NOT contain provider-specific fallback logic.

Agents should be able to say:

```text
"I need a strong coding/reasoning model capable of tool calling and structured output."
```

They should NOT say:

```text
"Call Gemini. If it fails, call Mistral. If that fails, call ZAI."
```

That responsibility belongs to the LLM infrastructure.

---

# 2. IMPORTANT EXISTING PROJECT AUDIT

Before making architectural changes, inspect the entire existing project.

Do not assume anything about the implementation.

Inspect:

- repository structure
- backend
- frontend
- database
- orchestration
- agents
- agent state
- memory
- task management
- LLM abstraction
- local model
- Gemini integration
- prompts
- tools
- MCP if present
- function calling
- structured output
- streaming
- retries
- fallback
- logging
- configuration
- Docker
- environment variables
- Git integration
- tests
- CI/CD
- documentation
- backlog
- TODOs
- unfinished features

---

# 3. TRACE THE CURRENT LLM EXECUTION PATH

Determine the actual current execution path.

Produce a concrete call graph.

For example, if that is what the code actually does:

```text
Feature
   ↓
Orchestrator
   ↓
Agent
   ↓
LLM abstraction
   ↓
Local LLM
   ↓
failure
   ↓
Gemini
```

But do not assume this.

Find the actual implementation.

Identify:

- every place an LLM is invoked
- every direct provider invocation
- every local model invocation
- every Gemini invocation
- every retry
- every fallback
- every prompt construction
- every place conversation history is assembled
- every place agent state is stored
- every place tool output is stored
- every place failures are handled

---

# 4. AUDIT CURRENT AGENTS

For every agent currently implemented, determine:

```text
Agent name
Purpose
Input
Output
Tools
Expected model capability
Context requirements
Memory requirements
State
Dependencies
Failure behavior
Retry behavior
Current LLM provider
```

Build a table.

Example:

```text
Agent            Task             Capability       Context      Tools
----------------------------------------------------------------------
Planner          planning        reasoning        medium       yes
Coder            coding          coding           large        yes
Reviewer         review           reasoning/code   large        yes
Debugger         debugging        reasoning/code   large        yes
Summarizer       summarization    fast             medium       no
```

Do not invent these values.

Derive them from the actual implementation.

---

# 5. AUDIT EXISTING AGENT MEMORY

This is a critical requirement.

Determine whether the current system already has:

- conversation history
- agent state
- task state
- workflow state
- persistent memory
- short-term memory
- long-term memory
- tool history
- execution checkpoints
- Git state
- file state
- intermediate results
- reasoning summaries
- task completion markers

If memory exists, understand its exact implementation.

If memory does not exist, design it.

The system must NOT depend on a model remembering information merely because it was present in a previous LLM conversation.

The source of truth must be application state.

---

# 6. CORE PRINCIPLE: MODELS ARE REPLACEABLE WORKERS

A critical architectural principle is:

> **An LLM model is a replaceable execution worker, not the owner of task state.**

If:

```text
Agent A
   ↓
Gemini
```

fails halfway through a task and the system switches to:

```text
Agent A
   ↓
Mistral
```

the new model must not be expected to magically know what happened.

Instead, the application must reconstruct the task from durable state.

---

# 7. REQUIRED TASK CHECKPOINTING

Every meaningful agent operation must have a checkpoint.

Example:

```text
Task:
Implement authentication

Steps:

1. Analyze existing authentication
   status = completed

2. Identify affected files
   status = completed

3. Design implementation
   status = completed

4. Modify auth service
   status = completed

5. Modify frontend
   status = IN_PROGRESS

6. Run tests
   status = pending

7. Fix failures
   status = pending

8. Review
   status = pending
```

If the LLM fails during step 5:

```text
provider = Gemini
model = X
key = Y
failure = quota exhausted
```

the next model must resume at:

```text
Step 5
```

not restart at step 1.

---

# 8. MODEL FALLBACK MUST BE STATE-AWARE

Do NOT implement fallback as:

```text
try model A
catch
    call model B with same prompt
```

That is insufficient for an autonomous software factory.

Instead:

```text
Agent
 ↓
Task State
 ↓
Checkpoint
 ↓
LLM Attempt
 ↓
failure
 ↓
persist failure
 ↓
persist partial result
 ↓
persist current step
 ↓
select replacement model
 ↓
reconstruct context
 ↓
resume task
```

---

# 9. EXACT RESUME SEMANTICS

Every LLM request must have a unique:

```text
request_id
attempt_id
task_id
agent_id
workflow_id
checkpoint_id
```

When an attempt fails, persist:

```text
provider
credential
model
timestamp
failure_type
HTTP status
provider error
retry-after
tokens consumed
estimated tokens
partial output
tool calls
tool results
current task step
current checkpoint
```

Then the next model receives a reconstructed execution state.

---

# 10. AGENT HANDOFF CONTEXT

When switching from one model to another, construct a **handoff package**.

Example:

```text
AGENT HANDOFF

Workflow:
WF-123

Task:
Implement OAuth login

Agent:
Coder

Current step:
Modify backend authentication service

Completed:
- analyzed existing auth
- identified AuthService.ts
- identified UserRepository.ts
- designed OAuth flow

Already changed:
- UserRepository.ts

Current files:
- AuthService.ts
- UserRepository.ts
- routes/auth.ts

Previous model result:
...

Last successful tool execution:
...

Last failed operation:
...

Failure:
Gemini quota exhausted

Remaining work:
- modify AuthService.ts
- add OAuth callback
- update routes
- run tests
- fix failures
- review changes

Constraints:
...

Expected deliverable:
...

Do not repeat:
- repository analysis
- completed implementation
- completed tool calls
```

This is extremely important.

The new model should receive **state**, not merely a transcript.

---

# 11. CONTEXT MANAGEMENT MUST BE A FIRST-CLASS SUBSYSTEM

Design a dedicated:

```text
Context Manager
```

Do not allow every agent to simply send the entire conversation/history to the LLM.

The Context Manager must decide what information is relevant.

---

# 12. CONTEXT LAYERS

Design context in layers.

### Layer 1 — System Context

Stable factory instructions.

Examples:

```text
agent identity
safety rules
coding standards
tool usage rules
```

### Layer 2 — Workflow Context

```text
workflow objective
workflow state
overall requirements
acceptance criteria
```

### Layer 3 — Agent Context

```text
agent role
agent responsibilities
agent constraints
agent current objective
```

### Layer 4 — Task Context

```text
current task
subtasks
dependencies
completed steps
remaining steps
```

### Layer 5 — Repository Context

```text
relevant files
Git state
recent changes
architecture
dependencies
tests
```

### Layer 6 — Tool Context

Only relevant tool results.

### Layer 7 — Memory Context

Relevant persistent memories and decisions.

### Layer 8 — Handoff Context

Information from previous model attempts.

### Layer 9 — Current Request

The immediate instruction to the model.

---

# 13. CONTEXT BUDGETING

Before every request calculate:

```text
system tokens
workflow tokens
agent tokens
task tokens
repository tokens
memory tokens
tool tokens
handoff tokens
current request tokens
+
expected output tokens
```

Then verify:

```text
total <= model context window
```

If not:

```text
compress
summarize
retrieve selectively
remove irrelevant history
or choose a larger-context model
```

Do not blindly truncate from the beginning.

The Context Manager must preserve:

```text
current task
constraints
acceptance criteria
recent changes
current errors
unfinished work
important decisions
```

---

# 14. CONTEXT PRIORITY

Define a priority system.

For example:

```text
P0:
system constraints
current task
current failure
acceptance criteria

P1:
current files
recent changes
current tool results
agent state

P2:
workflow history
architecture decisions

P3:
older conversation

P4:
irrelevant history
```

When context must be reduced, remove lower-priority information first.

---

# 15. CONTEXT SUMMARIZATION

Do not summarize everything continuously.

Create targeted summaries:

```text
Task Summary
Agent Summary
Repository Summary
Decision Summary
Failure Summary
Handoff Summary
```

Each summary should be independently replaceable.

For example:

```text
task_summary
architecture_summary
implementation_summary
testing_summary
```

---

# 16. AGENT MEMORY ARCHITECTURE

Design two different concepts:

## Working Memory

Short-lived state required for the current task.

Examples:

```text
current objective
current files
recent tool calls
current errors
current reasoning summary
current implementation state
```

## Persistent Memory

Information useful beyond the current task.

Examples:

```text
architecture decisions
project conventions
known provider limitations
coding conventions
stable project facts
```

Do not put everything into persistent memory.

---

# 17. MEMORY MUST NOT BECOME A GIANT CHAT HISTORY

The memory system should be structured.

Potential entities:

```text
Memory
MemoryType
MemoryScope
MemoryImportance
MemorySource
MemoryTimestamp
MemoryConfidence
```

Example scopes:

```text
global
project
repository
workflow
task
agent
```

---

# 18. MEMORY RETRIEVAL

Before invoking a model:

```text
current task
   ↓
retrieve relevant memories
   ↓
rank relevance
   ↓
apply token budget
   ↓
inject into context
```

Do not inject the entire memory database.

---

# 19. MODEL SWITCHING AND MEMORY

When switching models:

```text
Model A
 ↓
writes durable task state
 ↓
writes handoff summary
 ↓
writes relevant memory
 ↓
failure
 ↓
Model B
 ↓
retrieves state
 ↓
retrieves handoff
 ↓
retrieves relevant memory
 ↓
continues
```

This is the mechanism that makes provider switching reliable.

---

# 20. DO NOT DEPEND ON MODEL-SPECIFIC MEMORY

Never assume:

```text
Gemini conversation state
```

will be available to:

```text
Mistral
```

or:

```text
ZAI
```

The application owns the memory.

---

# 21. LLM GATEWAY

Investigate adopting an existing open-source LLM gateway instead of implementing one from scratch.

Strong candidates to evaluate include:

- Bifrost
- LiteLLM
- New API
- Portkey Gateway
- Helicone AI Gateway

Do not assume one is correct.

Evaluate them against the actual requirements and codebase.

The gateway should ideally provide:

```text
provider abstraction
multi-provider routing
multi-key management
retry
fallback
rate limits
health
circuit breaker
model routing
usage tracking
OpenAI-compatible API
local provider support
```

---

# 22. IMPORTANT: FREE-TIER AWARENESS IS A SEPARATE PROBLEM

Do NOT assume the selected gateway automatically understands:

> "How much free quota is left on this particular provider account?"

This is a distinct architectural problem.

The target architecture should therefore include a middle layer such as:

```text
Free-Tier Intelligence Layer
```

or:

```text
Free Quota Controller
```

or another appropriate abstraction.

Determine the best name after inspecting the selected gateway.

---

# 23. FREE-TIER INTELLIGENCE LAYER

Its purpose is to answer:

```text
Can this request safely be executed using free capacity?
```

It should maintain:

```text
provider
account
credential
model
quota_type
limit
used
remaining
reset_at
last_verified
source
confidence
```

---

# 24. FREE-TIER QUOTA SOURCES

Quota information may come from several sources:

### A. Provider API

Best case.

Example:

```text
provider usage endpoint
```

### B. Provider response headers

Example:

```text
remaining requests
retry-after
rate-limit-reset
```

### C. Provider dashboard/API

If accessible and permitted.

### D. Runtime observations

Example:

```text
429 quota exceeded
```

### E. Token accounting

When no official quota endpoint exists.

### F. Static catalog information

Such as:

```text
100 requests/day
```

from the external free-LLM catalog.

But this must be treated as metadata, not authoritative runtime state.

---

# 25. QUOTA CONFIDENCE

Every quota value should have a confidence/source.

For example:

```text
OFFICIAL_API
OFFICIAL_HEADER
OFFICIAL_DOCUMENTATION
RUNTIME_OBSERVED
USER_CONFIGURED
ESTIMATED
UNKNOWN
```

Example:

```text
Gemini Key #2

Remaining:
Unknown

Last observed:
429 quota exceeded

Confidence:
RUNTIME_OBSERVED

Cooldown:
Until 03:00
```

This is much safer than pretending the application knows the exact remaining quota.

---

# 26. QUOTA TYPES

Support different quota dimensions:

```text
RPM
RPD
TPM
TPD
monthly tokens
daily tokens
credits
neurons
requests
concurrency
provider-specific units
```

Do not normalize everything into tokens.

Maintain provider-specific dimensions.

---

# 27. FREE-TIER CATALOG INTEGRATION

Investigate:

https://github.com/mnfst/awesome-free-llm-apis

Use it as a provider/model discovery source.

Inspect:

```text
README
data.json
provider APIs
inference providers
model metadata
rate limits
free-tier information
scripts
update mechanisms
```

Do not make the Dark Feature Factory depend on the GitHub repository being available at runtime.

Instead:

```text
External Catalog
      ↓
Catalog Importer
      ↓
Normalized Provider Registry
      ↓
Manual Review / Overrides
      ↓
Runtime Router
```

---

# 28. PROVIDER DISCOVERY LIFECYCLE

New provider:

```text
DISCOVERED
   ↓
VALIDATING
   ↓
REVIEWED
   ↓
AVAILABLE
   ↓
ENABLED
```

Do not automatically trust newly discovered providers.

---

# 29. FREE-TIER FAILURE LOGGING

This is extremely important.

Even if the system cannot know the exact quota remaining, it must learn from failures.

Every provider failure should create an event:

```text
ProviderFailureEvent
```

with:

```text
provider
account
credential
model
timestamp
request_id
HTTP status
error code
error message
failure classification
retry-after
quota-related?
tokens consumed
```

---

# 30. FAILURE CLASSIFICATION

At minimum distinguish:

```text
AUTHENTICATION_FAILURE
AUTHORIZATION_FAILURE
RATE_LIMIT
DAILY_QUOTA_EXHAUSTED
MONTHLY_QUOTA_EXHAUSTED
TOKEN_QUOTA_EXHAUSTED
CONCURRENCY_LIMIT
MODEL_UNAVAILABLE
REGION_RESTRICTION
PROVIDER_OUTAGE
NETWORK_ERROR
TIMEOUT
INVALID_REQUEST
CONTEXT_TOO_LARGE
CONTENT_FILTER
STRUCTURED_OUTPUT_FAILURE
TOOL_CALL_FAILURE
UNKNOWN
```

---

# 31. FAILURE LEARNING

If:

```text
Gemini Key 1
429
quota exceeded
```

the system should immediately update:

```text
Key 1
status = QUOTA_EXHAUSTED
```

and stop wasting requests on it.

If:

```text
Mistral Key 2
429
retry-after = 45 seconds
```

set:

```text
cooldown_until = now + 45s
```

If:

```text
401 invalid key
```

do not retry repeatedly.

Disable the key until the user fixes it.

---

# 32. RESUME FROM FAILURE

Suppose:

```text
Agent:
Coder

Task:
Implement payment service

Model:
Gemini

Progress:
70%

Gemini:
quota exhausted
```

The next provider must receive:

```text
Current task state
+
completed work
+
modified files
+
current Git diff
+
last successful operation
+
failed operation
+
remaining work
+
acceptance criteria
+
relevant memory
+
relevant repository context
```

Then:

```text
Mistral
```

continues from 70%.

It must NOT restart from 0%.

---

# 33. PARTIAL OUTPUT HANDLING

If an LLM produces partial output before failure, determine whether it is usable.

For example:

```text
stream started
 ↓
model produced 3,000 tokens
 ↓
connection failed
```

Persist the partial output if available.

Classify it:

```text
COMPLETE
PARTIAL
INVALID
UNKNOWN
```

Never automatically treat partial generated code as completed work.

Validate it first.

---

# 34. TOOL CALL CONTINUITY

If the failed model already executed:

```text
tool A
tool B
tool C
```

the replacement model must know:

```text
tool A → completed
tool B → completed
tool C → failed
```

It should not repeat tool A/B unless explicitly necessary.

This is especially important for:

- file modifications
- Git operations
- test execution
- shell commands
- database migrations
- external API calls

---

# 35. IDEMPOTENCY

Any tool/action that may be retried must have an idempotency strategy.

Example:

```text
create file
```

must not blindly create it twice.

Example:

```text
database migration
```

must not be executed twice.

Example:

```text
Git commit
```

must not create duplicate commits because a model switched.

Design this at the workflow/tool layer.

---

# 36. CHECKPOINT AFTER SIDE EFFECTS

After significant side effects:

```text
file modification
test execution
migration
Git change
dependency installation
```

persist a checkpoint.

This allows safe model switching.

---

# 37. TASK STATE MACHINE

Design an explicit state machine.

For example:

```text
CREATED
 ↓
PLANNING
 ↓
READY
 ↓
RUNNING
 ↓
CHECKPOINTED
 ↓
RUNNING
 ↓
COMPLETED
```

Failure states:

```text
RETRYING
WAITING_FOR_PROVIDER
WAITING_FOR_QUOTA
WAITING_FOR_USER
FAILED
```

---

# 38. MODEL ATTEMPT STATE

Each LLM attempt should have:

```text
PENDING
RUNNING
SUCCEEDED
FAILED
CANCELLED
RATE_LIMITED
QUOTA_EXHAUSTED
TIMED_OUT
```

The task state must remain separate from the attempt state.

---

# 39. DO NOT CONFUSE PROVIDER FAILURE WITH TASK FAILURE

Example:

```text
Gemini failed
```

does NOT mean:

```text
Task failed
```

It means:

```text
Attempt failed
Task remains resumable
```

This distinction must exist in the data model.

---

# 40. TASK CHECKPOINT DATA MODEL

Design something similar to:

```text
TaskCheckpoint

id
workflow_id
task_id
agent_id

step_id
step_status

created_at
updated_at

input_state
output_state

completed_actions
pending_actions

current_files
modified_files

git_commit
git_diff_hash

context_snapshot
memory_snapshot
handoff_summary

last_successful_operation
current_operation

resume_instructions
```

Do not necessarily use this exact schema; adapt to the existing application.

---

# 41. AGENT RUN DATA MODEL

Potential structure:

```text
AgentRun

id
agent_id
task_id
workflow_id

model
provider
credential

started_at
finished_at

status

attempt_number

input_tokens
output_tokens

failure_reason

checkpoint_id
```

---

# 42. LLM REQUEST DATA MODEL

Potential structure:

```text
LLMRequest

request_id
workflow_id
task_id
agent_id
attempt_id

provider
credential
model

task_type

context_tokens
input_tokens
expected_output_tokens

actual_output_tokens

started_at
completed_at

status

fallback_reason
```

---

# 43. ROUTING DECISION LOG

Every routing decision should be explainable.

Example:

```text
RoutingDecision

Request:
REQ-123

Required capabilities:
coding
tool_calling
128k context

Rejected:
Gemini Key 1
Reason: quota exhausted

Rejected:
Mistral Key 2
Reason: context too small

Rejected:
ZAI Key 1
Reason: temporarily rate limited

Selected:
Mistral Key 3

Reason:
capability match
free quota available
healthy
lowest estimated cost
priority 2
```

This will be invaluable for debugging the factory.

---

# 44. MODEL CAPABILITY REGISTRY

Create a registry containing:

```text
model
provider

context_window

reasoning
coding
tool_calling
structured_output
vision
audio

streaming

quality_tier
speed_tier
```

The router should never select a model that cannot satisfy the task.

---

# 45. TASK REQUIREMENTS

Every agent task should specify requirements such as:

```text
required_context
required_capabilities
preferred_quality
max_latency
max_tokens
tool_calling_required
structured_output_required
free_only
privacy_level
```

---

# 46. ROUTING ALGORITHM

Build a candidate set:

```text
All providers
 ↓
enabled?
 ↓
provider available?
 ↓
region allowed?
 ↓
model supports required capabilities?
 ↓
context sufficient?
 ↓
credential healthy?
 ↓
quota available?
 ↓
concurrency available?
 ↓
privacy policy allowed?
 ↓
candidate
```

Then score candidates using:

```text
task compatibility
quality
free capacity
priority
health
latency
recent failure rate
context
```

---

# 47. FREE QUOTA SHOULD INFLUENCE ROUTING

Example:

```text
Provider A:
free capacity 5%

Provider B:
free capacity 80%

Provider C:
free capacity 40%
```

If all three are equally capable, the router should avoid unnecessarily consuming Provider A's final 5%.

But if Provider A is significantly better for the current task, it may still be selected.

The policy must be configurable.

---

# 48. QUOTA RESERVATION

Consider concurrent requests.

Example:

```text
Remaining free quota:
10,000 tokens

Agent A:
expected 7,000

Agent B:
expected 6,000
```

Do not allow both to believe the full 10,000 is available.

Design:

```text
quota reservation
atomic accounting
queue
lock
```

appropriate to the current architecture.

---

# 49. EXPECTED TOKEN BUDGET

Before sending a request estimate:

```text
input tokens
expected output tokens
```

Then:

```text
expected_total
```

Compare against quota.

If insufficient:

```text
skip provider
```

or:

```text
compress context
```

or:

```text
choose another model
```

---

# 50. CONTEXT ADAPTATION PER MODEL

If:

```text
Task context = 100k tokens
```

and candidate model supports:

```text
32k
```

do not send it.

Instead:

```text
retrieve relevant subset
summarize
compress
or choose another model
```

---

# 51. CONTEXT CACHE

Investigate caching:

```text
repository summaries
architecture summaries
dependency analysis
file summaries
task summaries
model-independent context
```

Avoid regenerating the same summaries with expensive/free-tier tokens.

---

# 52. MODEL-INDEPENDENT STATE

Persist state in a model-neutral format.

Do not store critical state only as natural-language conversation.

For example:

Bad:

```text
"The agent previously said it changed AuthService..."
```

Better:

```json
{
  "files_modified": [
    "src/auth/AuthService.ts"
  ],
  "tests": {
    "status": "pending"
  },
  "current_step": "implement_oauth_callback"
}
```

Natural-language summaries can supplement structured state.

They should not replace it.

---

# 53. REPOSITORY STATE AS SOURCE OF TRUTH

For software engineering tasks, Git and filesystem state are critical.

The system should be able to reconstruct:

```text
HEAD commit
current branch
working tree
changed files
diff
tests
build state
```

The next model should receive a repository snapshot or relevant diff rather than trusting the previous model's description.

---

# 54. AGENT MEMORY + GIT + CHECKPOINT

These three systems should work together:

```text
                 TASK
                  |
       +----------+----------+
       |          |          |
      Git       State      Memory
       |          |          |
       +----------+----------+
                  |
              Handoff
                  |
              New Model
```

This is the foundation of reliable model switching.

---

# 55. PROVIDER GATEWAY EVALUATION

Evaluate these projects:

```text
Bifrost
LiteLLM
New API
Portkey Gateway
Helicone AI Gateway
```

For each inspect:

- source code
- license
- architecture
- provider support
- model routing
- key routing
- retry
- fallback
- quota
- rate limits
- budgets
- observability
- dashboard
- Docker
- database
- Redis
- extensibility
- API compatibility
- local models
- active maintenance
- release activity

Do not choose based solely on README marketing language.

---

# 56. GATEWAY SELECTION CRITERIA

The selected gateway must be evaluated against:

```text
multi-provider
multi-key
provider health
key health
fallback
retry
routing
rate limits
concurrency
token tracking
model capabilities
OpenAI compatibility
local LLM
self-hosting
security
extensibility
license
```

Then evaluate:

```text
Free-tier integration effort
```

separately.

---

# 57. DO NOT FORCE FREE-TIER LOGIC INTO THE GATEWAY

Unless the selected gateway already provides an appropriate extension mechanism, keep:

```text
Gateway
```

and:

```text
Free-Tier Intelligence
```

separate.

Architecture:

```text
                    Dark Feature Factory
                             |
                             v
                    LLM Orchestration
                             |
                             v
                    Free-Tier Controller
                             |
                             v
                         LLM Gateway
                             |
              +--------------+--------------+
              |              |              |
           Provider A     Provider B     Provider C
```

Or, if the gateway provides hooks:

```text
Orchestrator
     |
Gateway
     |
Quota Policy Plugin
     |
Provider
```

Choose based on actual gateway capabilities.

---

# 58. PROVIDER ADAPTERS

For providers not supported by the selected gateway:

implement adapters only where necessary.

Do not build adapters for every provider upfront.

Prioritize providers that:

1. have useful free tiers
2. are available in the user's region
3. support required capabilities
4. provide acceptable privacy
5. support coding/reasoning
6. have reliable APIs

---

# 59. EXTERNAL PROVIDER CATALOG

Use:

https://github.com/mnfst/awesome-free-llm-apis

as a discovery/catalog source.

Do not treat it as a guaranteed source of truth.

Provider availability and limits must be validated.

---

# 60. PROVIDER POLICY

Each provider should have:

```text
enabled
free_only
allowed_regions
privacy_level
allowed_task_types
blocked_task_types
allowed_models
blocked_models
max_daily_usage
max_monthly_usage
```

---

# 61. PRIVACY-AWARE ROUTING

Define task privacy levels:

```text
PUBLIC
INTERNAL
CONFIDENTIAL
SENSITIVE
```

Providers should have corresponding policies.

Example:

```text
PUBLIC code
→ external provider allowed

CONFIDENTIAL code
→ only approved providers

SENSITIVE credentials
→ never external
```

---

# 62. SECRET REDACTION

Before external execution:

scan for:

```text
API keys
passwords
tokens
private keys
certificates
.env values
cloud credentials
database credentials
```

Do not send them to free providers.

---

# 63. PROVIDER DATA POLICY

Track:

```text
training usage
retention
logging
data residency
opt-out
free-tier data policy
```

This becomes part of routing.

---

# 64. $0 SAFETY MODE

The default mode must be:

```text
FREE_ONLY = true
```

If all free capacity is unavailable:

```text
DO NOT silently spend money.
```

Instead:

```text
try another compatible free provider
or
try local provider
or
pause task
or
ask user
```

---

# 65. GLOBAL COST POLICY

Support:

```text
FREE_ONLY
USER_APPROVED_PAID
UNRESTRICTED
```

Default:

```text
FREE_ONLY
```

---

# 66. LOCAL MODEL FALLBACK

The local model should be available when:

```text
all compatible cloud providers exhausted
network unavailable
privacy policy requires local execution
user explicitly selects local
```

However, determine whether its quality is sufficient for each task.

Do not assume local inference is a viable fallback for every agent.

---

# 67. LOCAL MODEL AS TASK-SPECIFIC PROVIDER

Potentially allow:

```text
simple classification → local
code formatting → local
summarization → local
complex architecture → cloud
```

based on actual benchmarking.

---

# 68. OBSERVABILITY

Every request must be traceable.

At minimum:

```text
workflow_id
task_id
agent_id
request_id
attempt_id

provider
credential
model

timestamp
latency

input_tokens
output_tokens

status

failure
fallback_reason
routing_reason
```

---

# 69. REQUEST TRACE

Example UI:

```text
Workflow #123
  |
  +-- Planner
  |     |
  |     +-- Gemini / Key 1
  |           SUCCESS
  |
  +-- Coder
        |
        +-- Gemini / Key 2
        |      QUOTA EXHAUSTED
        |
        +-- Mistral / Key 1
               SUCCESS
```

---

# 70. FAILURE ANALYTICS

Dashboard should show:

```text
429 count
quota failures
auth failures
timeouts
provider outages
model failures
fallback count
successful fallback count
average retries
```

---

# 71. PROVIDER CAPACITY DASHBOARD

Display:

```text
Provider
Model
Key
Health
Last used
Requests
Input tokens
Output tokens
Estimated free quota
Known free quota
Quota confidence
Reset time
Cooldown
```

---

# 72. API KEY UI

Allow:

```text
Add key
Remove key
Enable/disable
Reorder
Test
View status
View usage
View failures
Reset health
```

Never expose the full secret.

---

# 73. PROVIDER UI

Allow:

```text
Enable
Disable
Priority
Allowed models
Routing strategy
Privacy policy
Free-tier policy
Quota override
```

---

# 74. MODEL UI

Allow:

```text
Enable
Disable
Priority
Capabilities
Context window
Task profiles
Experimental
Fallback eligibility
```

---

# 75. ROUTING EXPLANATION

For every request the user should be able to answer:

> Why was this provider/model/key selected?

Example:

```text
Selected:
Mistral / Key 2

Because:
✓ coding capability
✓ tool calling
✓ context sufficient
✓ free quota available
✓ provider healthy
✓ priority 2

Rejected:
Gemini / Key 1
→ quota exhausted

Rejected:
Gemini / Key 2
→ rate limited

Rejected:
Local
→ lower capability for requested reasoning task
```

---

# 76. TESTING

Create:

## Unit tests

- routing
- quotas
- failure classification
- context budgeting
- memory retrieval
- checkpointing
- handoff creation

## Integration tests

- gateway
- providers
- database
- quota layer
- memory

## E2E

```text
feature
→ planner
→ coder
→ provider failure
→ fallback
→ resume
→ tests
→ review
```

---

# 77. FAILURE SIMULATION

Must simulate:

```text
429
401
403
404
500
502
timeout
connection reset
quota exhausted
context too large
malformed JSON
tool failure
provider unavailable
```

Verify that the factory resumes correctly.

---

# 78. CRITICAL FALLBACK TEST

Create an automated test:

```text
1. Start a coding task.
2. Model A completes steps 1-3.
3. Model A modifies two files.
4. Model A begins step 4.
5. Force quota exhaustion.
6. Model A fails.
7. Persist checkpoint.
8. Select Model B.
9. Reconstruct context.
10. Model B resumes step 4.
11. Model B must not repeat steps 1-3.
12. Model B must know the modified files.
13. Model B must know the failure.
14. Model B completes remaining work.
15. Tests pass.
```

This test is mandatory.

---

# 79. SECOND CRITICAL TEST

Test:

```text
Model A:
partial streaming output

then network failure

Model B:
resume
```

Verify that partial output is not incorrectly treated as completed work.

---

# 80. THIRD CRITICAL TEST

Test concurrent quota consumption:

```text
remaining = 10,000

Agent A reserves 7,000
Agent B requests 6,000
```

Verify the system prevents unsafe oversubscription.

---

# 81. FOURTH CRITICAL TEST

Test:

```text
Provider A:
all keys exhausted

Provider B:
available

Provider C:
available

Local:
available
```

Verify:

```text
A skipped
B selected according to routing policy
```

and no unnecessary calls are sent to A.

---

# 82. FIFTH CRITICAL TEST

Test:

```text
Provider A:
free quota unknown
```

Verify the system behaves according to a configurable conservative policy.

It must not falsely claim:

```text
remaining = 100%
```

---

# 83. CONTEXT TESTING

Create tests for:

```text
small context
large context
context overflow
context compression
memory retrieval
handoff reconstruction
model with smaller context
model with larger context
```

---

# 84. AGENT MEMORY TESTING

Verify that after switching providers:

```text
completed decisions
architecture decisions
file changes
task state
test results
known errors
```

remain available.

---

# 85. MIGRATION STRATEGY

Do not rewrite the entire Feature Factory.

Use incremental migration.

Recommended conceptual phases:

## Phase 0 — Discovery

Audit everything.

## Phase 1 — State foundation

Make tasks/checkpoints durable.

## Phase 2 — Agent memory

Formalize memory and context.

## Phase 3 — LLM abstraction

Hide provider-specific clients.

## Phase 4 — Gateway

Introduce Bifrost/LiteLLM/etc.

## Phase 5 — Existing provider migration

Move local + Gemini behind gateway.

## Phase 6 — Usage/observability

Record every request and token.

## Phase 7 — Free-Tier Intelligence

Add quota state and failure learning.

## Phase 8 — Multi-key routing

Enable multiple credentials.

## Phase 9 — Intelligent model routing

Add capability-aware selection.

## Phase 10 — Context optimization

Reduce token consumption.

## Phase 11 — Agent handoff

Make provider switching resumable.

## Phase 12 — UI

Provider/key/quota dashboard.

## Phase 13 — Catalog

Integrate free-LLM catalog.

## Phase 14 — Optimization

Benchmark and optimize.

Adapt these phases after inspecting the existing implementation.

---

# 86. BACKLOG RECONCILIATION

Inspect all existing backlog items.

For each:

```text
Existing task
```

classify:

```text
KEEP
MODIFY
MERGE
DEFER
REMOVE
REPLACE
```

Do not create duplicate tasks.

---

# 87. NEW IMPLEMENTATION BACKLOG

Create detailed tasks.

Each task must include:

```text
ID
Title
Description
Dependencies
Affected components
Expected implementation
Acceptance criteria
Testing requirements
Priority
Complexity
```

Example:

```text
LLM-STATE-001

Title:
Introduce durable task checkpoints

Description:
Persist the current agent step, completed actions,
modified files, Git state, and remaining work.

Acceptance criteria:
- every agent step can be checkpointed
- task survives process restart
- failed LLM attempt leaves a resumable state
- next agent can reconstruct state
```

---

# 88. QUESTIONS TO ASK THE USER

Only ask questions after inspecting the implementation.

Do not ask questions that the code already answers.

Ask only questions that materially affect architecture.

Examples:

### Free-tier policy

- Must paid usage remain strictly disabled?
- Should the factory pause when no free provider is available?
- Should local inference be the final fallback?

### Provider accounts

- Are multiple keys from separate legitimate accounts expected?
- Should keys be managed only locally or by multiple users?

### Privacy

- Which repositories/data may be sent to external free providers?
- Should certain projects be local-only?

### Memory

- How persistent should project memory be?
- Should architectural decisions survive indefinitely?

### Concurrency

- How many agents may execute simultaneously?

### Reliability

- How long can a task wait for quota reset?

### User intervention

- Should the factory automatically wait for a quota reset?
- Or immediately move to another provider?

Do not ask all of these automatically. Ask only the ones the repository cannot answer.

---

# 89. REQUIRED ARCHITECTURE DELIVERABLE

Before implementing anything, produce:

## A. Current architecture diagram

## B. Current LLM call graph

## C. Current agent graph

## D. Current state/memory model

## E. Current backlog map

## F. Gateway comparison

Compare:

```text
Bifrost
LiteLLM
New API
Portkey
Helicone
```

## G. Selected gateway

Explain why it fits the actual project.

## H. Free-Tier Intelligence architecture

Explain exactly how it integrates with the selected gateway.

## I. Context architecture

Explain context lifecycle.

## J. Agent memory architecture

Explain persistent and working memory.

## K. Checkpoint/resume architecture

Explain how a failed model can be replaced without restarting the task.

## L. Failure state machine

Show provider failure → fallback → resume.

## M. Database model

Show entities and relationships.

## N. UI

Show the required screens.

## O. Implementation backlog

Detailed and dependency ordered.

## P. Open questions

Only unresolved architectural decisions.

---

# 90. REQUIRED FINAL BEHAVIOR

The resulting system must support a scenario like:

```text
User:
"Implement feature X."
```

Then:

```text
Planner
 ↓
Provider A / Model X
 ↓
planning completed
 ↓
checkpoint
 ↓
Coder
 ↓
Provider A / Model X
 ↓
implementation started
 ↓
files modified
 ↓
checkpoint
 ↓
Provider A returns:
429 / quota exhausted
 ↓
failure recorded
 ↓
provider/key marked unavailable
 ↓
routing engine selects Provider B
 ↓
context manager reconstructs context
 ↓
memory manager retrieves relevant memory
 ↓
checkpoint restored
 ↓
handoff context generated
 ↓
Provider B continues from exact failed step
 ↓
implementation completed
 ↓
checkpoint
 ↓
tests
 ↓
review
 ↓
delivery
```

The replacement model must understand:

```text
WHAT THE TASK IS
WHAT HAS ALREADY BEEN DONE
WHAT FILES CHANGED
WHAT DECISIONS WERE MADE
WHAT FAILED
WHY THE PREVIOUS MODEL FAILED
WHAT REMAINS
WHAT IT MUST NOT REPEAT
WHAT THE ACCEPTANCE CRITERIA ARE
```

without depending on the previous model's hidden conversation state.

---

# 91. FINAL ARCHITECTURAL PRINCIPLE

The final system should have these clear responsibilities:

```text
                 DARK FEATURE FACTORY
                         |
                 Workflow Orchestrator
                         |
             +-----------+-----------+
             |                       |
        Context Manager        Agent Memory
             |                       |
             +-----------+-----------+
                         |
                   Task State
                         |
                   LLM Gateway
                         |
               Routing / Scheduling
                         |
              Free-Tier Intelligence
                         |
          +--------------+--------------+
          |              |              |
       Provider A     Provider B     Provider C
          |              |              |
       Key 1..N       Key 1..N       Key 1..N
          |
      Local LLM
```

The **Workflow Orchestrator** owns:

```text
what needs to happen
```

The **Task State / Checkpoint system** owns:

```text
where we are
```

The **Context Manager** owns:

```text
what information the model needs
```

The **Memory system** owns:

```text
what the factory should remember
```

The **LLM Gateway** owns:

```text
how to communicate with providers
```

The **Router** owns:

```text
which model/provider/key should execute the request
```

The **Free-Tier Intelligence layer** owns:

```text
how much free capacity is believed to remain
```

The **Failure Manager** owns:

```text
what failed and how the system should react
```

The **Checkpoint/Resume system** owns:

```text
how another model continues from the exact point of failure
```

This separation is mandatory.

Do not collapse all of these responsibilities into a single "LLM service."

---

# 92. ULTIMATE SUCCESS CRITERIA

The architectural migration is successful only when all of the following are true:

### Provider independence

Agents do not know provider-specific details.

### API-first

Cloud APIs are the normal execution path.

### Local support

Local LLM remains available as a provider.

### Multi-provider

Multiple providers can coexist.

### Multi-key

Multiple credentials per provider are supported.

### Intelligent routing

Model selection depends on task requirements.

### Free-tier awareness

The system tracks known and estimated free capacity.

### Failure learning

Quota/rate-limit failures change routing behavior.

### No accidental spending

Free-only mode never silently moves to paid usage.

### Context management

The system sends only the context required for the current task.

### Agent memory

Important information survives model changes.

### Checkpointing

Every meaningful task step can be resumed.

### Model switching

A failed model can be replaced without restarting the task.

### Tool continuity

Previous tool calls and side effects are preserved.

### Repository continuity

Git/filesystem state is part of the task state.

### Observability

Every routing decision is explainable.

### Security

API keys and sensitive code are protected.

### Extensibility

A new provider can be added without rewriting the factory.

### Maintainability

The solution remains a modular system rather than a giant collection of provider-specific fallback code.

---

# 93. DO NOT IMPLEMENT UNTIL THIS IS SATISFIED

Before writing implementation code:

1. Audit the existing repository.
2. Audit existing agents.
3. Audit existing memory.
4. Audit existing context handling.
5. Audit existing task state.
6. Audit current LLM integration.
7. Audit current fallback behavior.
8. Audit existing backlog.
9. Evaluate open-source gateway candidates.
10. Select the gateway based on actual project compatibility.
11. Design the Free-Tier Intelligence layer.
12. Design checkpoint/resume.
13. Design context management.
14. Design agent memory.
15. Design failure classification.
16. Design quota-aware routing.
17. Reconcile the existing backlog.
18. Produce the complete implementation plan.
19. Ask only the remaining questions that require human decisions.

Only after these steps should implementation begin.
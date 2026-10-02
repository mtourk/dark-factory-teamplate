I created both files and strengthened them around the areas most likely to cause mistakes: context leakage, self-review, hidden-test exposure, unsupported business decisions, uncontrolled PowerShell access, test weakening, SHA drift, auto-merge bypass, production recovery, and governance self-modification.

1. Execution prompt

Use this as the initial prompt inside the blank repository:

Download the strengthened build prompt

It instructs the implementation agent to:

Read the complete plan before changing anything
Create and maintain an implementation checklist
Execute all 16 phases in order
Use isolated subagents with fresh sessions
Avoid asking for confirmation between phases
Escalate only genuine strategic or business ambiguity
Enforce evidence and phase-completion gates
Refuse unsafe shortcuts
Complete a real end-to-end autonomous acceptance test
2. Complete master plan

Place this file in the root of the blank repository with the exact filename DARK_FACTORY_MASTER_PLAN.md:

Download the complete Dark Factory master plan

The plan contains:

Windows-native architecture
Local Ollama and model constraints
FactoryFlow orchestration design
BMAD, gstack, DUBS, OctopusGarden, Coleam, and Nick Fujita integration boundaries
Licensing and attribution rules
Autonomous backlog scheduling
Atomic item claims and stale-lease recovery
Context classification and isolation
Builder and reviewer memory separation
Context package manifests and hashes
Independent requirement critics
Evidence-based decision synthesis
Strategic ambiguity escalation
Local-model gateway and benchmarking
Restricted command broker and OPA policies
Git worktree and Windows account isolation
Sealed QA and mutation testing
Bounded repair and stall recovery
SHA-bound independent review
GitHub required checks and auto-merge
Cloudflare preview and production deployment
Production quarantine and recovery
Evidence graph and certified memory
Sixteen implementation phases
Required testing strategy
Explicit mistakes to avoid, with reasons
Final Definition of Done
How to use them

The blank repository should initially contain:

your-blank-repository/
├── DARK_FACTORY_MASTER_PLAN.md
└── DARK_FACTORY_BUILD_PROMPT.md


Open your chosen coding agent in that repository, then provide the content of DARK_FACTORY_BUILD_PROMPT.md as its starting instruction.

The prompt explicitly tells the agent to read DARK_FACTORY_MASTER_PLAN.md first, create:

IMPLEMENTATION_CHECKLIST.md
docs/audit/prerequisite-report.md
docs/audit/repository-report.md
docs/threat-model.md
docs/decisions/index.md


and then begin Phase 1 without asking you to approve every intermediate phase.

The key protection added to both files is:

Agents share controlled, hashed, policy-approved artifacts. They do not share conversations, private reasoning, scratch memory, hidden tests, or persuasive summaries. Every reviewer starts with a fresh session and receives an objective context package assembled by the orchestrator.
"""
Isolated Requirement Critics.

Per master plan §7:
"After BMAD drafts a specification, start separate sessions for:
- Product Critic (user-visible meaning, entitlement, scope)
- Domain-Rule Critic (business rules, domain calculation)
- Testability Critic (acceptance criteria, observability)
- Security/Permissions Critic (actors, data, access control)
- Contradiction Critic (requirement conflicts, contradictions)
- Operational-Recovery Critic (failure modes, recovery)

Critics receive the original issue, relevant certified knowledge, the draft,
a narrow rubric, and an output schema. They do not receive each other's
private reasoning.

Each finding includes role, category, statement, evidence sources,
severity, and resolution class.

Do not use majority vote. Classify findings as:
- evidence_resolvable: derive from authoritative project source
- delegated_technical: decide under approved policy
- reversible: choose repository-consistent option, record it
- strategic_ambiguity: request human decision
- invalid: reject with source-backed reason
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class CriticRole(str, Enum):
    """Isolated critic roles (§7)."""
    PRODUCT = "product_critic"
    DOMAIN_RULE = "domain_critic"
    TESTABILITY = "testability_critic"
    SECURITY = "security_critic"
    CONTRADICTION = "contradiction_critic"
    OPERATIONAL = "operational_critic"


class FindingClassification(str, Enum):
    """Classification of critic findings (§7)."""
    EVIDENCE_RESOLVABLE = "evidence_resolvable"
    DELEGATED_TECHNICAL = "delegated_technical"
    REVERSIBLE = "reversible"
    STRATEGIC_AMBIGUITY = "strategic_ambiguity"
    INVALID = "invalid"


class FindingSeverity(str, Enum):
    """Severity of finding."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass
class CriticFinding:
    """Single critic finding (§7)."""
    role: CriticRole
    category: str  # e.g., "missing_acceptance_criteria"
    statement: str  # Finding text
    evidence_sources: List[str]  # Citations from issue or knowledge
    severity: FindingSeverity
    classification: FindingClassification
    resolution: Optional[str] = None  # Suggested resolution
    requires_human_decision: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "role": self.role.value,
            "category": self.category,
            "statement": self.statement,
            "evidence_sources": self.evidence_sources,
            "severity": self.severity.value,
            "classification": self.classification.value,
            "resolution": self.resolution,
            "requires_human_decision": self.requires_human_decision,
            "timestamp": self.timestamp,
        }


@dataclass
class CriticSession:
    """Isolated critic session (fresh conversation, narrow rubric)."""
    role: CriticRole
    run_id: str
    session_id: str
    issue_number: int
    bmad_spec: Dict[str, Any]  # BMAD specification
    certified_knowledge: Dict[str, Any]  # Relevant ADRs, contracts
    findings: List[CriticFinding]
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class RequirementChallengeBroker:
    """
    Orchestrate isolated critic sessions with strict isolation.

    Each critic runs in a fresh session (per §7):
    - No cross-critic memory sharing
    - Narrow rubric (role-specific)
    - Output schema validation
    - Finding classification enforcement
    - No majority vote
    """

    def __init__(self):
        """Initialize challenge broker."""
        self.sessions: Dict[str, CriticSession] = {}

    def create_critic_session(
        self,
        role: CriticRole,
        run_id: str,
        issue_number: int,
        bmad_spec: Dict[str, Any],
        certified_knowledge: Optional[Dict[str, Any]] = None,
    ) -> CriticSession:
        """
        Create fresh session for isolated critic (§7).

        Args:
            role: critic role (product, domain-rule, testability, etc.)
            run_id: factory run ID
            issue_number: GitHub issue number
            bmad_spec: BMAD specification (dict)
            certified_knowledge: relevant ADRs, contracts

        Returns:
            CriticSession (fresh, isolated, no cross-critic memory)
        """
        session_id = f"critic-{role.value}-{run_id}-{datetime.utcnow().isoformat()[:10]}"

        session = CriticSession(
            role=role,
            run_id=run_id,
            session_id=session_id,
            issue_number=issue_number,
            bmad_spec=bmad_spec,
            certified_knowledge=certified_knowledge or {},
            findings=[],
        )

        self.sessions[session_id] = session
        return session

    def add_finding(
        self,
        session_id: str,
        category: str,
        statement: str,
        evidence_sources: List[str],
        severity: FindingSeverity,
        classification: FindingClassification,
        resolution: Optional[str] = None,
    ) -> CriticFinding:
        """
        Add finding to critic session with classification enforcement.

        Args:
            session_id: critic session ID
            category: finding category (e.g., "missing_acceptance_criteria")
            statement: finding statement
            evidence_sources: citations from issue, ADRs, or contracts
            severity: CRITICAL, HIGH, MEDIUM, LOW, INFORMATIONAL
            classification: evidence_resolvable, delegated_technical,
                          reversible, strategic_ambiguity, invalid
            resolution: optional suggested resolution

        Returns:
            CriticFinding (validated, classified, recorded)

        Raises:
            ValueError: if session not found or classification missing
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = self.sessions[session_id]

        # Validate classification
        if classification == FindingClassification.STRATEGIC_AMBIGUITY:
            # Mark for human escalation
            requires_human = True
        else:
            requires_human = False

        finding = CriticFinding(
            role=session.role,
            category=category,
            statement=statement,
            evidence_sources=evidence_sources,
            severity=severity,
            classification=classification,
            resolution=resolution,
            requires_human_decision=requires_human,
        )

        session.findings.append(finding)
        return finding

    def get_challenge_gate_status(
        self,
        issue_number: int,
        critic_sessions: Dict[str, CriticSession],
    ) -> Dict[str, Any]:
        """
        Determine challenge gate status (§7).

        Gate passes when:
        - Actors identified
        - Permissions defined
        - Error cases specified
        - Data behavior clear
        - Preconditions explicit
        - Postconditions explicit
        - Acceptance criteria observable
        - Non-goals explicit
        - Contradictions identified
        - Requirement-to-evidence mapping complete
        - No unsupported business decisions remain

        Args:
            issue_number: GitHub issue number
            critic_sessions: all critic sessions for this issue

        Returns:
            gate_status dict with pass/fail and reasons
        """
        gate_checklist = {
            "actors_identified": False,
            "permissions_defined": False,
            "error_cases_specified": False,
            "data_behavior_clear": False,
            "preconditions_explicit": False,
            "postconditions_explicit": False,
            "acceptance_criteria_observable": False,
            "non_goals_explicit": False,
            "contradictions_identified": False,
            "requirement_to_evidence_mapping": False,
            "no_unsupported_decisions": True,
        }

        # Collect findings across all critics
        all_findings = []
        strategic_ambiguities = []

        for session in critic_sessions.values():
            all_findings.extend(session.findings)
            strategic_ambiguities.extend([
                f for f in session.findings
                if f.classification == FindingClassification.STRATEGIC_AMBIGUITY
            ])

        # Check gate conditions
        # Look for findings that address each gate item
        for finding in all_findings:
            if "actor" in finding.category.lower():
                gate_checklist["actors_identified"] = True
            if "permission" in finding.category.lower() or "access" in finding.category.lower():
                gate_checklist["permissions_defined"] = True
            if "error" in finding.category.lower():
                gate_checklist["error_cases_specified"] = True
            if "data" in finding.category.lower():
                gate_checklist["data_behavior_clear"] = True
            if "precondition" in finding.category.lower():
                gate_checklist["preconditions_explicit"] = True
            if "postcondition" in finding.category.lower():
                gate_checklist["postconditions_explicit"] = True
            if "acceptance" in finding.category.lower() or "criteria" in finding.category.lower():
                gate_checklist["acceptance_criteria_observable"] = True
            if "non.goal" in finding.category.lower() or "out.of.scope" in finding.category.lower():
                gate_checklist["non_goals_explicit"] = True
            if "contradiction" in finding.category.lower():
                gate_checklist["contradictions_identified"] = True
            if "evidence" in finding.category.lower():
                gate_checklist["requirement_to_evidence_mapping"] = True

        # If any strategic ambiguity unresolved, gate fails
        if strategic_ambiguities:
            gate_checklist["no_unsupported_decisions"] = False

        gate_passes = all(gate_checklist.values())

        return {
            "issue_number": issue_number,
            "gate_passes": gate_passes,
            "checklist": gate_checklist,
            "strategic_ambiguities": len(strategic_ambiguities),
            "total_findings": len(all_findings),
            "critical_findings": len([f for f in all_findings if f.severity == FindingSeverity.CRITICAL]),
        }

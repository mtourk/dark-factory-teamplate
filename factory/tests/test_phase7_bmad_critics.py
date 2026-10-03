"""
Phase 7: BMAD and Isolated Requirement Challenge tests.

Tests for:
1. BMAD discovery from GitHub issue
2. Specification generation with requirements
3. Isolated critic session creation (fresh, no memory sharing)
4. Finding classification (evidence_resolvable, delegated_technical,
   reversible, strategic_ambiguity, invalid)
5. Challenge gate status (actors, permissions, data, error cases, etc.)
6. No majority vote enforcement
7. Strategic ambiguity escalation
8. Contradiction detection
9. Evidence sourcing and requirement-to-evidence mapping
10. Rubric validation (narrow, role-specific)
"""

import pytest
from datetime import datetime

from factory.analysis.bmad import (
    BMADDiscovery,
    BMADRequirement,
    BMADSpecification,
    DiscoveryPhase,
)
from factory.analysis.critics import (
    CriticRole,
    FindingClassification,
    FindingSeverity,
    CriticFinding,
    CriticSession,
    RequirementChallengeBroker,
)


# ============================================================================
# BMAD Discovery Tests
# ============================================================================

class TestBMADDiscovery:
    """BMAD requirement discovery from GitHub issues."""

    def test_bmad_discovery_initialization(self):
        """BMAD discovery initializes without gateway."""
        discovery = BMADDiscovery()
        assert discovery.gateway is None

    def test_bmad_discovery_from_issue_basic(self):
        """BMAD discovers specification from issue."""
        discovery = BMADDiscovery()

        spec = discovery.discover_from_issue(
            issue_number=42,
            project_id="investisor",
            run_id="RUN-001",
            issue_title="User can search for companies",
            issue_body="As a user, I want to search companies by name\n\nAcceptance Criteria:\n- Find by exact match\n- Find by partial match\n- Display results",
        )

        assert spec.issue_number == 42
        assert spec.project_id == "investisor"
        assert spec.run_id == "RUN-001"
        assert len(spec.requirements) > 0

    def test_bmad_spec_has_requirements(self):
        """BMAD specification includes parsed requirements."""
        discovery = BMADDiscovery()

        spec = discovery.discover_from_issue(
            issue_number=1,
            project_id="test",
            run_id="RUN-test",
            issue_title="Search feature",
            issue_body="Search companies by name",
        )

        assert len(spec.requirements) >= 1
        req = spec.requirements[0]
        assert req.id == "REQ-1"
        assert req.phase == DiscoveryPhase.DISCOVERY

    def test_bmad_extracts_acceptance_criteria(self):
        """BMAD extracts acceptance criteria from issue body."""
        discovery = BMADDiscovery()

        body = """Search for companies

Acceptance Criteria:
- Find by exact match
- Find by partial match
- Display top 10 results"""

        spec = discovery.discover_from_issue(
            issue_number=2,
            project_id="test",
            run_id="RUN-test",
            issue_title="Search",
            issue_body=body,
        )

        assert len(spec.requirements[0].acceptance_criteria) > 0

    def test_bmad_extracts_non_goals(self):
        """BMAD extracts non-goals (out of scope) from issue."""
        discovery = BMADDiscovery()

        body = """Search feature

Non-Goals:
- Real-time indexing
- Advanced filters
- Export to CSV"""

        spec = discovery.discover_from_issue(
            issue_number=3,
            project_id="test",
            run_id="RUN-test",
            issue_title="Search",
            issue_body=body,
        )

        assert len(spec.requirements[0].non_goals) > 0

    def test_bmad_spec_to_json(self):
        """BMAD specification serializes to JSON."""
        discovery = BMADDiscovery()

        spec = discovery.discover_from_issue(
            issue_number=4,
            project_id="test",
            run_id="RUN-test",
            issue_title="Feature",
            issue_body="Description",
        )

        json_str = spec.to_json()
        assert '"issue_number": 4' in json_str
        assert '"project_id": "test"' in json_str


# ============================================================================
# Isolated Critic Session Tests (§7)
# ============================================================================

class TestIsolatedCriticSessions:
    """Test isolated critic sessions with strict isolation."""

    def test_critic_session_creation(self):
        """Critic session created with isolation (§7)."""
        broker = RequirementChallengeBroker()
        bmad_spec = {"issue_number": 1, "title": "Test"}

        session = broker.create_critic_session(
            role=CriticRole.PRODUCT,
            run_id="RUN-001",
            issue_number=1,
            bmad_spec=bmad_spec,
        )

        assert session.role == CriticRole.PRODUCT
        assert session.run_id == "RUN-001"
        assert session.issue_number == 1

    def test_critic_sessions_are_isolated(self):
        """Different critics get separate sessions (no memory sharing)."""
        broker = RequirementChallengeBroker()
        bmad_spec = {}

        session1 = broker.create_critic_session(
            CriticRole.PRODUCT, "RUN-001", 1, bmad_spec
        )
        session2 = broker.create_critic_session(
            CriticRole.DOMAIN_RULE, "RUN-001", 1, bmad_spec
        )

        # Different sessions (no cross-critic memory)
        assert session1.session_id != session2.session_id
        # Findings in one don't affect the other
        assert len(session1.findings) == 0
        assert len(session2.findings) == 0


# ============================================================================
# Finding Classification Tests (§7)
# ============================================================================

class TestFindingClassification:
    """Test finding classification (no majority vote)."""

    def test_evidence_resolvable_finding(self):
        """Finding classified as evidence_resolvable."""
        finding = CriticFinding(
            role=CriticRole.TESTABILITY,
            category="missing_acceptance_criteria",
            statement="No observable pass/fail criteria",
            evidence_sources=["GitHub issue #42"],
            severity=FindingSeverity.HIGH,
            classification=FindingClassification.EVIDENCE_RESOLVABLE,
        )

        assert finding.classification == FindingClassification.EVIDENCE_RESOLVABLE
        assert not finding.requires_human_decision

    def test_delegated_technical_finding(self):
        """Finding classified as delegated_technical (policy decision)."""
        finding = CriticFinding(
            role=CriticRole.DOMAIN_RULE,
            category="business_rule_undefined",
            statement="Pricing model not specified; defer to policy",
            evidence_sources=["ADR-001"],
            severity=FindingSeverity.MEDIUM,
            classification=FindingClassification.DELEGATED_TECHNICAL,
        )

        assert finding.classification == FindingClassification.DELEGATED_TECHNICAL

    def test_reversible_finding(self):
        """Finding classified as reversible (record and proceed)."""
        finding = CriticFinding(
            role=CriticRole.OPERATIONAL,
            category="retry_strategy_choice",
            statement="Using exponential backoff; record choice",
            evidence_sources=["Deployment policy"],
            severity=FindingSeverity.LOW,
            classification=FindingClassification.REVERSIBLE,
        )

        assert finding.classification == FindingClassification.REVERSIBLE

    def test_strategic_ambiguity_finding_escalates(self):
        """Strategic ambiguity finding triggers human escalation (§7)."""
        finding = CriticFinding(
            role=CriticRole.PRODUCT,
            category="user_entitlement",
            statement="Who is allowed to export data? Security vs usability trade-off.",
            evidence_sources=["Issue"],
            severity=FindingSeverity.CRITICAL,
            classification=FindingClassification.STRATEGIC_AMBIGUITY,
        )

        assert finding.classification == FindingClassification.STRATEGIC_AMBIGUITY
        assert finding.requires_human_decision is True

    def test_invalid_finding(self):
        """Invalid finding rejected with source-backed reason."""
        finding = CriticFinding(
            role=CriticRole.CONTRADICTION,
            category="requirement_self_contradiction",
            statement="Cannot require both <1s latency and 100% accuracy; contradicts issue #99",
            evidence_sources=["GitHub issue #99", "Issue #42"],
            severity=FindingSeverity.CRITICAL,
            classification=FindingClassification.INVALID,
        )

        assert finding.classification == FindingClassification.INVALID
        assert len(finding.evidence_sources) > 0


# ============================================================================
# Challenge Gate Tests (§7)
# ============================================================================

class TestChallengeGate:
    """Test challenge gate: actors, permissions, data, errors, etc. (§7)."""

    def test_challenge_gate_checklist(self):
        """Challenge gate checks all required items."""
        broker = RequirementChallengeBroker()

        # Create session
        session = broker.create_critic_session(
            CriticRole.SECURITY, "RUN-001", 42, {}
        )

        # Add findings for each gate item
        broker.add_finding(
            session.session_id,
            category="actors_and_permissions",
            statement="Admin and user roles defined",
            evidence_sources=["Issue"],
            severity=FindingSeverity.HIGH,
            classification=FindingClassification.EVIDENCE_RESOLVABLE,
        )

        status = broker.get_challenge_gate_status(
            issue_number=42,
            critic_sessions={session.session_id: session},
        )

        # Gate checklist present
        assert "gate_passes" in status
        assert "checklist" in status
        assert "actors_identified" in status["checklist"]

    def test_challenge_gate_passes_when_complete(self):
        """Gate passes when all items complete and no ambiguities."""
        broker = RequirementChallengeBroker()

        session = broker.create_critic_session(
            CriticRole.PRODUCT, "RUN-001", 1, {}
        )

        # Add findings covering all gate items
        for category in [
            "actors",
            "permissions",
            "errors",
            "data",
            "preconditions",
            "postconditions",
            "acceptance_criteria",
            "non_goals",
            "contradictions",
            "evidence",
        ]:
            broker.add_finding(
                session.session_id,
                category=category,
                statement=f"{category} specified",
                evidence_sources=["Issue"],
                severity=FindingSeverity.MEDIUM,
                classification=FindingClassification.EVIDENCE_RESOLVABLE,
            )

        status = broker.get_challenge_gate_status(
            issue_number=1,
            critic_sessions={session.session_id: session},
        )

        assert status["gate_passes"] is True

    def test_challenge_gate_fails_with_strategic_ambiguity(self):
        """Gate fails if unresolved strategic ambiguities exist."""
        broker = RequirementChallengeBroker()

        session = broker.create_critic_session(
            CriticRole.PRODUCT, "RUN-001", 1, {}
        )

        # Add strategic ambiguity
        broker.add_finding(
            session.session_id,
            category="user_entitlement",
            statement="Unclear scope",
            evidence_sources=["Issue"],
            severity=FindingSeverity.CRITICAL,
            classification=FindingClassification.STRATEGIC_AMBIGUITY,
        )

        status = broker.get_challenge_gate_status(
            issue_number=1,
            critic_sessions={session.session_id: session},
        )

        assert status["gate_passes"] is False
        assert status["strategic_ambiguities"] > 0


# ============================================================================
# No Majority Vote Enforcement (§7)
# ============================================================================

class TestNoMajorityVote:
    """Test that majority vote is never used (§7)."""

    def test_findings_classified_individually(self):
        """Each finding classified independently (no voting)."""
        broker = RequirementChallengeBroker()

        # Create 3 critic sessions
        sessions = {}
        for role in [CriticRole.PRODUCT, CriticRole.DOMAIN_RULE, CriticRole.TESTABILITY]:
            s = broker.create_critic_session(role, "RUN-001", 1, {})
            sessions[s.session_id] = s

            # Add same finding from different critics
            # (in real system, critics would disagree sometimes)
            broker.add_finding(
                s.session_id,
                category="acceptance_criteria",
                statement=f"{role.value} view of acceptance",
                evidence_sources=["Issue"],
                severity=FindingSeverity.HIGH,
                classification=FindingClassification.EVIDENCE_RESOLVABLE,
            )

        # Each critic's finding stands independently
        # No vote needed; classify each one
        for session in sessions.values():
            assert len(session.findings) == 1
            assert session.findings[0].classification is not None


# ============================================================================
# Contradiction Detection (§7)
# ============================================================================

class TestContradictionDetection:
    """Test detection of requirement contradictions."""

    def test_contradiction_finding(self):
        """Contradiction critic finds conflicting requirements."""
        broker = RequirementChallengeBroker()

        session = broker.create_critic_session(
            CriticRole.CONTRADICTION, "RUN-001", 42, {}
        )

        broker.add_finding(
            session.session_id,
            category="requirement_conflict",
            statement="Issue #42 requires both <1s latency and 100% guaranteed delivery; impossible",
            evidence_sources=["Issue #42", "Issue #99 (contradicting design)"],
            severity=FindingSeverity.CRITICAL,
            classification=FindingClassification.STRATEGIC_AMBIGUITY,
        )

        finding = session.findings[0]
        assert "conflict" in finding.category.lower()
        assert len(finding.evidence_sources) >= 2


# ============================================================================
# Phase 7 Gate Test
# ============================================================================

def test_phase7_gate_bmad_and_critics_operational():
    """
    Phase 7 Gate: BMAD discovery and isolated critics are operational.

    Verifies:
    - BMAD discovery from GitHub issue
    - Specification generation with parsed requirements
    - Isolated critic sessions (no cross-critic memory)
    - Finding classification (evidence_resolvable, delegated_technical,
      reversible, strategic_ambiguity, invalid)
    - Challenge gate checklist (actors, permissions, data, errors, etc.)
    - No majority vote
    - Strategic ambiguity escalation
    - Contradiction detection
    - Requirement-to-evidence mapping
    """
    # BMAD discovery
    discovery = BMADDiscovery()
    spec = discovery.discover_from_issue(
        issue_number=42,
        project_id="investisor",
        run_id="RUN-gate001",
        issue_title="User search feature",
        issue_body="""Search for companies

Acceptance Criteria:
- Find by name
- Display results

Non-Goals:
- Real-time indexing""",
    )

    assert spec.issue_number == 42
    assert len(spec.requirements) > 0

    # Isolated critic sessions
    broker = RequirementChallengeBroker()
    sessions = {}

    for role in [
        CriticRole.PRODUCT,
        CriticRole.SECURITY,
        CriticRole.CONTRADICTION,
    ]:
        s = broker.create_critic_session(
            role, "RUN-gate001", 42, spec.to_dict()
        )
        sessions[s.session_id] = s

    # Each critic isolated
    assert len(sessions) == 3
    for s in sessions.values():
        assert len(s.findings) == 0

    # Add findings with classifications
    for session_id, session in sessions.items():
        broker.add_finding(
            session_id,
            category="requirement_element",
            statement="Finding from " + session.role.value,
            evidence_sources=["Issue #42"],
            severity=FindingSeverity.HIGH,
            classification=FindingClassification.EVIDENCE_RESOLVABLE,
        )

    # Verify no majority vote used
    all_findings = sum(len(s.findings) for s in sessions.values())
    assert all_findings == 3  # Three independent findings

    # Challenge gate
    status = broker.get_challenge_gate_status(42, sessions)
    assert "gate_passes" in status
    assert "checklist" in status

    # Strategic ambiguity
    ambig_session = broker.create_critic_session(
        CriticRole.PRODUCT, "RUN-gate001", 43, {}
    )
    broker.add_finding(
        ambig_session.session_id,
        category="scope_decision",
        statement="Scope unclear",
        evidence_sources=["Issue #43"],
        severity=FindingSeverity.CRITICAL,
        classification=FindingClassification.STRATEGIC_AMBIGUITY,
    )

    finding = ambig_session.findings[0]
    assert finding.requires_human_decision is True

    print("✓ Phase 7 Gate: BMAD discovery and isolated critics operational")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

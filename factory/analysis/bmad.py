"""
BMAD (Business Model Analysis and Discovery).

Per master plan §7:
"Use BMAD-style discovery and specification.
BMAD concepts: discovery, clarification, project context, specification,
architecture exploration, story decomposition, and acceptance criteria.
BMAD does not own process persistence, merge authority, retries, or deployment."

BMAD generates a draft specification from:
1. Original issue (GitHub issue text, labels, metadata)
2. Certified project knowledge (ADRs, contracts, glossary, domain rules)
3. Compiled intent (from backlog selection context)

Output: structured specification for isolated critic review.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


class DiscoveryPhase(str, Enum):
    """BMAD discovery phase."""
    DISCOVERY = "discovery"  # Explore requirements space
    CLARIFICATION = "clarification"  # Resolve ambiguities
    SPECIFICATION = "specification"  # Formalize as spec
    DECOMPOSITION = "decomposition"  # Break into stories
    ARCHITECTURE = "architecture"  # Design approach


@dataclass
class BMADRequirement:
    """Single requirement from BMAD discovery."""
    id: str
    phase: DiscoveryPhase
    actors: List[str]  # Who performs action
    action: str  # What they do
    context: str  # Why / when
    acceptance_criteria: List[str]  # Observable success
    non_goals: List[str]  # Explicitly out of scope
    constraints: List[str]  # Technical/business constraints
    data_needed: Dict[str, str]  # Data flows
    errors: List[str]  # Error cases
    preconditions: List[str]  # Must be true before
    postconditions: List[str]  # Must be true after
    source: str  # Which part of issue/knowledge


@dataclass
class BMADSpecification:
    """BMAD draft specification for critic review."""
    issue_number: int
    project_id: str
    run_id: str
    issue_title: str
    issue_body: str
    certified_knowledge_summary: str  # Relevant ADRs, contracts
    requirements: List[BMADRequirement]
    architecture_notes: str
    story_breakdown: List[str]  # Proposed decomposition
    open_questions: List[str]  # Ambiguities to resolve
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "issue_number": self.issue_number,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "issue_title": self.issue_title,
            "issue_body": self.issue_body,
            "certified_knowledge_summary": self.certified_knowledge_summary,
            "requirements": [asdict(r) for r in self.requirements],
            "architecture_notes": self.architecture_notes,
            "story_breakdown": self.story_breakdown,
            "open_questions": self.open_questions,
            "generated_at": self.generated_at,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


class BMADDiscovery:
    """
    BMAD discovery engine: transform issue into structured specification.

    Phases:
    1. Discovery — explore requirement space, extract key concepts
    2. Clarification — resolve ambiguities, identify data flows
    3. Specification — formalize as structured requirements
    4. Decomposition — break into cohesive stories
    5. Architecture — sketch technical approach
    """

    def __init__(self, gateway=None):
        """
        Initialize BMAD discovery.

        Args:
            gateway: optional model gateway for LLM-assisted analysis
                    (Phase 7 uses gateway for deeper discovery)
        """
        self.gateway = gateway

    def discover_from_issue(
        self,
        issue_number: int,
        project_id: str,
        run_id: str,
        issue_title: str,
        issue_body: str,
        certified_knowledge: Optional[Dict[str, Any]] = None,
    ) -> BMADSpecification:
        """
        Discover and specify requirements from GitHub issue (MVP).

        Args:
            issue_number: GitHub issue number
            project_id: factory project ID
            run_id: factory run ID
            issue_title: issue title
            issue_body: issue description
            certified_knowledge: ADRs, contracts, glossary

        Returns:
            BMADSpecification (structured draft for critic review)
        """
        # Simple heuristic parsing for MVP (real version would use LLM)
        requirements = []

        # Parse acceptance criteria from issue body
        acceptance_criteria = []
        non_goals = []
        open_questions = []

        if "Acceptance Criteria:" in issue_body:
            ac_section = issue_body.split("Acceptance Criteria:")[1].split("\n\n")[0]
            acceptance_criteria = [
                line.strip().lstrip("- ")
                for line in ac_section.split("\n")
                if line.strip().startswith("-")
            ]

        if "Non-Goals:" in issue_body or "Out of Scope:" in issue_body:
            ng_marker = "Non-Goals:" if "Non-Goals:" in issue_body else "Out of Scope:"
            ng_section = issue_body.split(ng_marker)[1].split("\n\n")[0]
            non_goals = [
                line.strip().lstrip("- ")
                for line in ng_section.split("\n")
                if line.strip().startswith("-")
            ]

        if "Questions:" in issue_body or "?" in issue_body:
            # Naïve: any line with ? is a question
            open_questions = [
                line.strip()
                for line in issue_body.split("\n")
                if "?" in line and line.strip()
            ][:3]  # Limit to 3

        # Create primary requirement
        primary_req = BMADRequirement(
            id="REQ-1",
            phase=DiscoveryPhase.DISCOVERY,
            actors=["user", "system"],
            action=issue_title,
            context=issue_body[:200] if issue_body else "",
            acceptance_criteria=acceptance_criteria or [issue_title],
            non_goals=non_goals,
            constraints=[],
            data_needed={},
            errors=[],
            preconditions=[],
            postconditions=[],
            source="GitHub issue",
        )
        requirements.append(primary_req)

        # Summarize certified knowledge
        knowledge_summary = "Certified knowledge available: ADRs, contracts"
        if certified_knowledge:
            if certified_knowledge.get("adrs"):
                knowledge_summary += f" ({len(certified_knowledge['adrs'])} ADRs)"
            if certified_knowledge.get("contracts"):
                knowledge_summary += f" ({len(certified_knowledge['contracts'])} contracts)"

        spec = BMADSpecification(
            issue_number=issue_number,
            project_id=project_id,
            run_id=run_id,
            issue_title=issue_title,
            issue_body=issue_body,
            certified_knowledge_summary=knowledge_summary,
            requirements=requirements,
            architecture_notes="Architecture TBD by critics and planners",
            story_breakdown=[issue_title],
            open_questions=open_questions,
            generated_at=datetime.utcnow().isoformat(),
        )

        return spec

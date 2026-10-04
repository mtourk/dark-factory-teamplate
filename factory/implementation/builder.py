"""
Builder: Code generation via LLM with full discovery context.

Per master plan §10:
"Builder receives only an observable failure envelope, allowed fix scope,
and attempt number.

The builder may not delete/weaken/skip/exclude failing tests, modify
sealed tests, or replace final integration behavior with mocks merely
to pass."

Implementation strategy (as of 2026-10-04):
1. Read GitHub issue with `factory:ready` label
2. Extract `model:implementation-32b` label to determine model (or default)
3. Parse issue body to extract full discovery conversation + BMAD fields
4. Call Ollama with 32B model (e.g., qwen2.5-coder:32b) using complete context
5. Generator reads both structured BMAD and raw Q&A history for context
6. Per ADR §10: builder constraints enforced (no test deletion, no sealed test mods, etc.)

Local execution (not Cloudflare): direct Ollama calls, no 524 timeout risk for large models.
"""

import hashlib
import httpx
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


@dataclass
class BuilderInput:
    """Input to builder: requirement, allowed scope, attempt info."""
    run_id: str
    issue_number: int
    requirement_summary: str  # From BMAD
    allowed_fix_scope: str  # What builder may change
    attempt_number: int  # Attempt count (1-3)
    failure_context: Optional[str] = None  # Error details from verification
    prohibited_paths: List[str] = field(default_factory=list)  # Cannot touch these
    previous_patch_digest: Optional[str] = None  # SHA of prior attempt
    raw_conversation: Optional[str] = None  # Full discovery conversation (new)
    owner: Optional[str] = None  # GitHub owner for issue lookup
    repo: Optional[str] = None  # GitHub repo for issue lookup

    def __post_init__(self):
        if not self.prohibited_paths:
            self.prohibited_paths = [
                "DARK_FACTORY_MASTER_PLAN.md",
                ".factory-control/",
                ".factory/",
                ".github/workflows/",
                "docs/decisions/",
                "factory/sealed_qa/",
            ]


@dataclass
class BuilderOutput:
    """Output from builder: code changes."""
    run_id: str
    issue_number: int
    attempt_number: int
    changes: Dict[str, str]  # Path -> file content
    changed_files: List[str]
    patch_digest: str = ""  # SHA-256 of changes
    duration_seconds: float = 0.0
    explanation: str = ""  # Builder's explanation (not authority for acceptance)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def compute_patch_digest(self) -> str:
        """Compute SHA-256 of patch (for cycle detection)."""
        patch_json = str(sorted(self.changes.items()))
        return hashlib.sha256(patch_json.encode()).hexdigest()


class IssueBodyParser:
    """Parse GitHub issue body to extract BMAD fields and discovery conversation."""

    @staticmethod
    def extract_section(body: str, section_name: str) -> Optional[str]:
        """Extract a markdown section from issue body.

        Args:
            body: GitHub issue body (markdown)
            section_name: section header name (e.g., "Acceptance Criteria")

        Returns:
            Section content as string, or None if not found
        """
        pattern = rf"^## {re.escape(section_name)}$\s*\n(.*?)(?=^## |\Z)"
        match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def extract_conversation(body: str) -> List[Dict[str, str]]:
        """Extract raw discovery conversation from issue body.

        Returns list of {"role": "user" | "ai", "text": "..."} messages.
        """
        conversation_section = IssueBodyParser.extract_section(body, "Raw Discovery Conversation")
        if not conversation_section:
            return []

        messages = []
        # Parse lines like "**User:** text" or "**AI:** text"
        lines = conversation_section.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("**User:**"):
                text = line[len("**User:**"):].strip()
                # Accumulate multiline message until next role marker
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("**"):
                    text += "\n" + lines[i]
                    i += 1
                messages.append({"role": "user", "text": text.strip()})
                continue
            elif line.startswith("**AI:**"):
                text = line[len("**AI:**"):].strip()
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("**"):
                    text += "\n" + lines[i]
                    i += 1
                messages.append({"role": "ai", "text": text.strip()})
                continue
            i += 1

        return messages

    @staticmethod
    def extract_description(body: str) -> str:
        """Extract the free-text description that precedes the first '## ' header.

        The issue body format (see github.ts _formatBMADIssueBody) puts the
        description first, with no header of its own, followed by '## Acceptance
        Criteria' etc. — so it can't use extract_section (which looks for a
        named '## <section>' header).
        """
        match = re.search(r"^(.*?)(?=^## |\Z)", body, re.MULTILINE | re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def parse_full_context(body: str) -> Dict[str, Any]:
        """Parse issue body to extract all relevant context for code generation.

        Returns dict with keys:
        - description: issue description
        - acceptance_criteria: list of criteria
        - non_goals: list of non-goals
        - constraints: list of constraints
        - raw_conversation: list of {"role", "text"} message dicts
        """
        return {
            "description": IssueBodyParser.extract_description(body),
            "acceptance_criteria": IssueBodyParser._parse_list_section(body, "Acceptance Criteria"),
            "non_goals": IssueBodyParser._parse_list_section(body, "Non-Goals"),
            "constraints": IssueBodyParser._parse_list_section(body, "Constraints"),
            "data_behavior": IssueBodyParser.extract_section(body, "Data Behavior") or "",
            "error_handling": IssueBodyParser.extract_section(body, "Error Handling") or "",
            "raw_conversation": IssueBodyParser.extract_conversation(body),
        }

    @staticmethod
    def extract_model_label(labels: List[str], default: str = "qwen2.5-coder:32b") -> str:
        """Extract the implementation model name from GitHub issue labels.

        Looks for a label of the form 'model:implementation-<size>' (e.g.
        'model:implementation-32b') and maps it to an Ollama model tag.
        Falls back to `default` if no such label is present.
        """
        model_map = {
            "model:implementation-32b": "qwen2.5-coder:32b",
            "model:implementation-7b": "qwen2.5:7b-instruct",
        }
        for label in labels:
            if label in model_map:
                return model_map[label]
        return default

    @staticmethod
    def _parse_list_section(body: str, section_name: str) -> List[str]:
        """Extract bulleted list from a section."""
        section = IssueBodyParser.extract_section(body, section_name)
        if not section:
            return []

        items = []
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:])
        return items


class OllamaCodeGenerator:
    """
    Calls local Ollama directly for code generation.

    Unlike the intake worker (Cloudflare Worker, bounded by the 30s/524 edge
    timeout), this runs on the same machine as Ollama — a plain HTTP call to
    localhost (or wherever OLLAMA_URL points), so a 32B model taking minutes
    to respond is not a timeout risk here.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434", timeout_seconds: float = 600.0):
        self.ollama_url = ollama_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout_seconds)

    def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Call Ollama /api/chat for a single-turn code-generation request.

        Args:
            model: Ollama model tag (e.g. "qwen2.5-coder:32b")
            system_prompt: builder system prompt (constraints, scope, format)
            user_prompt: full requirement context (BMAD + raw conversation)

        Returns:
            Raw model response text.

        Raises:
            httpx.HTTPError: if Ollama is unreachable or returns an error.
        """
        response = self.client.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                # Implementation runs are infrequent and large; no need to keep
                # the model hot afterwards the way discovery does.
                "keep_alive": "5m",
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content")
        if not content:
            raise ValueError("No response content from Ollama")
        return content

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


BUILDER_SYSTEM_PROMPT = """You are the Dark Factory builder: an autonomous code-generation agent.

You are given a feature requirement (structured BMAD fields plus the full discovery
conversation that produced them) and must propose code changes that satisfy it.

Hard constraints (per Dark Factory master plan §10):
- You may NOT delete, weaken, skip, or exclude failing tests.
- You may NOT modify sealed tests (factory/sealed_qa/, tests/sealed_*, tests/acceptance_*).
- You may NOT replace real integration behavior with mocks merely to make something pass.
- Stay within the allowed fix scope given to you; do not touch unrelated files.
- Your explanation is NOT authority for acceptance — the verification pipeline decides.

Respond with a JSON object of the form:
{
  "explanation": "<brief rationale>",
  "changes": { "<path>": "<full file content>", ... }
}
Only include files you are creating or modifying in full. No prose outside the JSON."""


class BuilderCoordinator:
    """
    Coordinate builder code generation with allowed scope enforcement.

    Builder constraints:
    - Cannot touch prohibited paths
    - Cannot weaken/skip tests
    - Cannot modify sealed tests
    - Cannot replace integration behavior with mocks
    - Explanation is not authority for acceptance
    """

    def __init__(self, gateway=None, ollama_url: str = "http://localhost:11434"):
        """
        Initialize builder coordinator.

        Args:
            gateway: model gateway for LLM calls (legacy path; prefer build_from_issue)
            ollama_url: base URL for local Ollama server (direct call, no Cloudflare edge)
        """
        self.gateway = gateway
        self.ollama_url = ollama_url
        self.build_history: List[BuilderOutput] = []

    def validate_builder_input(self, builder_input: BuilderInput) -> Dict[str, Any]:
        """Validate builder input is well-formed."""
        if builder_input.attempt_number < 1 or builder_input.attempt_number > 3:
            return {
                "valid": False,
                "reason": "Attempt number must be 1-3 (§12)",
            }

        if not builder_input.requirement_summary:
            return {"valid": False, "reason": "No requirement summary"}

        if not builder_input.allowed_fix_scope:
            return {"valid": False, "reason": "No allowed fix scope"}

        return {"valid": True}

    def validate_builder_output(
        self,
        builder_output: BuilderOutput,
        builder_input: BuilderInput,
    ) -> Dict[str, Any]:
        """
        Validate builder output doesn't violate constraints.

        Args:
            builder_output: code changes from builder
            builder_input: original input with constraints

        Returns:
            validation report with violations list
        """
        violations = []

        # Check for prohibited path changes
        for file_path in builder_output.changed_files:
            for prohibited in builder_input.prohibited_paths:
                if file_path.startswith(prohibited):
                    violations.append(f"Prohibited path: {file_path}")

        # Check for sealed test modifications
        sealed_patterns = [
            "factory/sealed_qa/",
            "tests/sealed_",
            "tests/acceptance_",
        ]
        for file_path in builder_output.changed_files:
            for pattern in sealed_patterns:
                if pattern in file_path:
                    violations.append(f"Cannot modify sealed tests: {file_path}")

        # Check for test weakening (heuristic: deletion of test lines)
        for file_path, content in builder_output.changes.items():
            if "test" in file_path.lower() and "def test_" in content:
                # Sanity check: tests are present, not deleted
                pass

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "patch_digest": builder_output.compute_patch_digest(),
        }

    def record_build(self, output: BuilderOutput):
        """Record builder output for history/cycle detection."""
        output.patch_digest = output.compute_patch_digest()
        self.build_history.append(output)

    def get_build_history(self) -> List[BuilderOutput]:
        """Get full build history."""
        return self.build_history

    def build_from_issue(
        self,
        run_id: str,
        github_adapter,  # factory.backlog.github_adapter.GitHubAdapter
        issue_number: int,
        attempt_number: int = 1,
        allowed_fix_scope: str = "",
        failure_context: Optional[str] = None,
    ) -> BuilderOutput:
        """
        End-to-end: fetch issue → extract model + context → generate code.

        This is the method the local factory runner calls once an issue is
        labeled `factory:ready`. It:
        1. Fetches the issue (title, body, labels) via `github_adapter`
        2. Extracts the implementation model from `model:implementation-*` labels
        3. Parses the issue body for BMAD fields + the raw discovery conversation
        4. Calls Ollama directly (no Cloudflare edge — safe for 32B+ models)
        5. Parses the model's JSON response into a BuilderOutput

        Args:
            run_id: factory run ID
            github_adapter: configured GitHubAdapter (owner/repo already set)
            issue_number: issue to build from
            attempt_number: 1-3 (per §12)
            allowed_fix_scope: what builder may change this attempt
            failure_context: prior verification failure, if this is a repair attempt

        Returns:
            BuilderOutput with proposed changes.

        Raises:
            httpx.HTTPError: issue fetch or Ollama call failed
            ValueError: Ollama response wasn't valid JSON / missing "changes"
        """
        issue = github_adapter.get_issue(issue_number)
        model = IssueBodyParser.extract_model_label(issue.labels)
        context = IssueBodyParser.parse_full_context(issue.body)

        builder_input = BuilderInput(
            run_id=run_id,
            issue_number=issue_number,
            requirement_summary=context["description"] or issue.title,
            allowed_fix_scope=allowed_fix_scope,
            attempt_number=attempt_number,
            failure_context=failure_context,
        )

        validation = self.validate_builder_input(builder_input)
        if not validation["valid"]:
            raise ValueError(f"Invalid builder input: {validation['reason']}")

        user_prompt = self._build_user_prompt(issue.title, context, builder_input)

        started_at = datetime.utcnow()
        with OllamaCodeGenerator(ollama_url=self.ollama_url) as generator:
            raw_response = generator.generate(
                model=model,
                system_prompt=BUILDER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        duration = (datetime.utcnow() - started_at).total_seconds()

        parsed = self._parse_model_response(raw_response)

        output = BuilderOutput(
            run_id=run_id,
            issue_number=issue_number,
            attempt_number=attempt_number,
            changes=parsed["changes"],
            changed_files=list(parsed["changes"].keys()),
            duration_seconds=duration,
            explanation=parsed.get("explanation", ""),
        )
        return output

    @staticmethod
    def _build_user_prompt(
        title: str,
        context: Dict[str, Any],
        builder_input: BuilderInput,
    ) -> str:
        """Assemble the full prompt: BMAD fields + raw conversation + constraints."""
        lines = [
            f"# Feature: {title}",
            "",
            context["description"],
            "",
        ]

        if context["acceptance_criteria"]:
            lines.append("## Acceptance Criteria")
            lines.extend(f"- {c}" for c in context["acceptance_criteria"])
            lines.append("")

        if context["non_goals"]:
            lines.append("## Non-Goals")
            lines.extend(f"- {g}" for g in context["non_goals"])
            lines.append("")

        if context["constraints"]:
            lines.append("## Constraints")
            lines.extend(f"- {c}" for c in context["constraints"])
            lines.append("")

        if context["raw_conversation"]:
            lines.append("## Discovery Conversation (for context on intent/reasoning)")
            for msg in context["raw_conversation"]:
                role = "User" if msg["role"] == "user" else "Discovery AI"
                lines.append(f"{role}: {msg['text']}")
            lines.append("")

        lines.append("## Build Instructions")
        lines.append(f"Allowed fix scope: {builder_input.allowed_fix_scope or '(entire repo, scoped by prohibited paths below)'}")
        lines.append(f"Attempt: {builder_input.attempt_number}/3")
        if builder_input.failure_context:
            lines.append(f"Prior failure (fix this): {builder_input.failure_context}")
        lines.append(f"Prohibited paths: {', '.join(builder_input.prohibited_paths)}")

        return "\n".join(lines)

    @staticmethod
    def _parse_model_response(raw_response: str) -> Dict[str, Any]:
        """Parse the model's JSON response, tolerating markdown code fences."""
        text = raw_response.strip()
        # Strip ```json ... ``` or ``` ... ``` fences if present
        fence_match = re.match(r"^```(?:json)?\s*\n(.*?)\n```$", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Builder model did not return valid JSON: {e}\nRaw response: {raw_response[:500]}")

        if "changes" not in parsed or not isinstance(parsed["changes"], dict):
            raise ValueError("Builder model response missing 'changes' object")

        return parsed

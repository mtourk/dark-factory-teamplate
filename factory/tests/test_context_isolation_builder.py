"""
Regression test for FB-07: context isolation violation in builder.py.

Master plan §11 / critical mistake #10: the builder must never receive the
raw discovery conversation (or any other role's private memory). Context
reaches the builder only through `ContextBroker.assemble_role_context()`,
which hands back a sanitized, role-scoped `ContextPackage`.

Before the fix:
- `BuilderInput.raw_conversation` existed as a field.
- `BuilderCoordinator._build_user_prompt()` appended the full raw discovery
  Q&A (parsed straight out of the GitHub issue body) into the code-gen
  prompt under a "## Discovery Conversation" heading.
- `factory/context/broker.py` / `ContextBroker.assemble_role_context()` was
  never called from builder.py at all.

After the fix:
- `BuilderInput` has no `raw_conversation` field.
- `_build_user_prompt()` no longer touches `context["raw_conversation"]`.
- `_build_user_prompt()` calls `ContextBroker.assemble_role_context(FactoryRole.BUILDER)`
  and only pulls the sanitized "approved_plan" / "compiled_intent" artifacts
  out of the returned `ContextPackage`.

These tests assert the raw discovery text (a distinctive sentinel phrase)
is never present in the generated prompt, even though it is present in the
`context` dict handed to `_build_user_prompt` (mirroring what
`IssueBodyParser.parse_full_context()` would hand it from a real issue
body) -- i.e. the isolation is enforced by the builder, not by the absence
of the data upstream.
"""

from unittest.mock import patch

import pytest

from factory.implementation.builder import BuilderInput, BuilderCoordinator
from factory.context.broker import ContextPolicyViolation


# A distinctive phrase that would only appear if the raw discovery Q&A
# leaked into the builder prompt. Chosen to be unlikely to collide with any
# BMAD field, system prompt, or build-instruction boilerplate text.
RAW_DISCOVERY_SENTINEL = "ZEBRA-NEBULA-7729 the password reset token must be stored in the private discovery notes only"

ACCEPTANCE_CRITERION = "User can reset their password via a one-time emailed link"


def _context_with_raw_conversation() -> dict:
    """Build a `context` dict shaped like IssueBodyParser.parse_full_context()'s
    output, including a raw discovery conversation that contains the sentinel.
    """
    return {
        "description": "Add password reset flow.",
        "acceptance_criteria": [ACCEPTANCE_CRITERION],
        "non_goals": ["Not implementing SSO"],
        "constraints": ["Must not log plaintext tokens"],
        "data_behavior": "",
        "error_handling": "",
        "raw_conversation": [
            {"role": "user", "text": f"Here's the internal plan: {RAW_DISCOVERY_SENTINEL}"},
            {"role": "ai", "text": "Understood, I will keep that in mind for the design."},
        ],
    }


def _builder_input(**overrides) -> BuilderInput:
    defaults = dict(
        run_id="RUN-fb07test",
        issue_number=101,
        requirement_summary="Password reset",
        allowed_fix_scope="src/auth/",
        attempt_number=1,
    )
    defaults.update(overrides)
    return BuilderInput(**defaults)


class _FakeRoleContext:
    """Stand-in for the ContextPackage returned by assemble_role_context()."""

    def __init__(self, shared_artifacts: dict):
        self.shared_artifacts = shared_artifacts


class TestBuilderInputHasNoRawConversation:
    def test_raw_conversation_field_removed(self):
        """BuilderInput must not expose a raw_conversation field at all."""
        builder_input = _builder_input()
        assert not hasattr(builder_input, "raw_conversation")

        # Also assert it can't sneak back in as a constructor kwarg.
        with pytest.raises(TypeError):
            BuilderInput(
                run_id="RUN-x",
                issue_number=1,
                requirement_summary="r",
                allowed_fix_scope="s",
                attempt_number=1,
                raw_conversation="leaked discovery text",
            )


class TestBuildUserPromptIsolatesRawConversation:
    """Core FB-07 regression coverage."""

    def test_prompt_never_contains_raw_discovery_text(self):
        """Even though the context dict carries a raw discovery conversation
        (as a real issue body would produce), the assembled prompt must
        never contain that raw text."""
        context = _context_with_raw_conversation()
        builder_input = _builder_input()

        # Broker call fails closed (matches real current broker behavior
        # for an unseeded run) -- builder must not fall back to raw data.
        with patch(
            "factory.implementation.builder.ContextBroker.assemble_role_context",
            side_effect=ContextPolicyViolation("no shared artifacts seeded for this run"),
        ):
            prompt = BuilderCoordinator._build_user_prompt(
                "Password reset feature", context, builder_input
            )

        assert RAW_DISCOVERY_SENTINEL not in prompt
        assert "Discovery Conversation" not in prompt
        assert "discovery notes" not in prompt

    def test_prompt_contains_sanitized_acceptance_criteria(self):
        """The sanitized BMAD acceptance criteria must still reach the builder."""
        context = _context_with_raw_conversation()
        builder_input = _builder_input()

        with patch(
            "factory.implementation.builder.ContextBroker.assemble_role_context",
            side_effect=ContextPolicyViolation("no shared artifacts seeded for this run"),
        ):
            prompt = BuilderCoordinator._build_user_prompt(
                "Password reset feature", context, builder_input
            )

        assert ACCEPTANCE_CRITERION in prompt
        assert "## Acceptance Criteria" in prompt

    def test_prompt_uses_context_broker_sanitized_artifacts(self):
        """When the broker successfully assembles a package, only its
        'approved_plan' / 'compiled_intent' artifacts are surfaced -- and the
        raw conversation is still excluded."""
        context = _context_with_raw_conversation()
        builder_input = _builder_input()

        fake_package = _FakeRoleContext(
            shared_artifacts={
                "compiled_intent": {"summary": "Password reset via emailed one-time link"},
                "approved_plan": {"steps": ["Generate token", "Email link", "Verify on redeem"]},
                # Even if other keys leaked into shared_artifacts upstream,
                # the builder must only ever read approved_plan/compiled_intent.
                "builder_chat": {"should": "never be read by builder.py"},
            }
        )

        with patch(
            "factory.implementation.builder.ContextBroker.assemble_role_context",
            return_value=fake_package,
        ):
            prompt = BuilderCoordinator._build_user_prompt(
                "Password reset feature", context, builder_input
            )

        assert RAW_DISCOVERY_SENTINEL not in prompt
        assert "## Compiled Intent (sanitized, via ContextBroker)" in prompt
        assert "Password reset via emailed one-time link" in prompt
        assert "## Approved Plan (sanitized, via ContextBroker)" in prompt
        assert "Generate token" in prompt
        # Only approved_plan/compiled_intent are pulled -- nothing else from
        # shared_artifacts should be rendered.
        assert "should" not in prompt
        assert "never be read by builder.py" not in prompt

    def test_build_from_issue_passes_no_raw_conversation_to_prompt(self):
        """End-to-end sanity: build_from_issue's own BuilderInput construction
        has no raw_conversation to pass through in the first place."""
        import inspect

        from factory.implementation.builder import BuilderCoordinator as BC

        source = inspect.getsource(BC.build_from_issue)
        assert "raw_conversation" not in source

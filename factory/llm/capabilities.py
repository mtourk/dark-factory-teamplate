"""
Task requirements + capability vocabulary (FF-P22-01, plan §44-45).

An agent states its needs with a TaskRequirements; the gateway/router matches
those against each model's capabilities so it never selects a model that cannot
satisfy the task. The capability *registry* (per-model capability data) lands in
FF-P22-02; this module defines the shared vocabulary and the request shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Capability(str, Enum):
    """Capabilities a task may require and a model may provide."""
    REASONING = "reasoning"
    CODING = "coding"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    FAST = "fast"


class PrivacyLevel(str, Enum):
    """Task privacy classification (plan §61). Routing may restrict providers
    by privacy level; the default policy applies no gating beyond always-on
    secret redaction (D-NEW-005: 'No restriction needed')."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SENSITIVE = "sensitive"


@dataclass
class TaskRequirements:
    """What a task needs from a model (plan §45).

    Defaults encode D-NEW-005: FREE_ONLY by default, INTERNAL privacy, balanced
    quality. The gateway filters candidates to those that satisfy these.
    """
    required_capabilities: List[Capability] = field(default_factory=list)
    min_context_tokens: int = 0
    preferred_quality: str = "balanced"  # "fast" | "balanced" | "high"
    tool_calling_required: bool = False
    structured_output_required: bool = False
    free_only: bool = True
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    max_output_tokens: Optional[int] = None

    def effective_capabilities(self) -> List[Capability]:
        """Required capabilities, including those implied by the boolean flags."""
        caps = list(self.required_capabilities)
        if self.tool_calling_required and Capability.TOOL_CALLING not in caps:
            caps.append(Capability.TOOL_CALLING)
        if self.structured_output_required and Capability.STRUCTURED_OUTPUT not in caps:
            caps.append(Capability.STRUCTURED_OUTPUT)
        return caps

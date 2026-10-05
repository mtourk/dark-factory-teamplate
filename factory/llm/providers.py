"""
Model candidate registry (FF-P22-01, plan §44).

A ModelCandidate is everything the gateway needs to call one model via LiteLLM
and to decide whether it satisfies a task. For FF-P22-01 the registry is a
static, config-driven default (Gemini cloud + local Ollama) ordered API-first
with local as fallback (D-NEW-005). A durable, DB-backed provider/credential +
capability registry with multi-key support replaces this default in FF-P22-02.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Set

from factory.llm.capabilities import Capability

# Config via env so operators can retarget without code changes; FF-P22-02 moves
# this into the durable provider registry + profiles.
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
# LiteLLM model ids. Overridable via env; defaults are conservative, current
# free-tier-capable choices. The exact Gemini id is easy to change here or via
# FACTORY_CLOUD_MODEL without touching the gateway.
DEFAULT_CLOUD_MODEL = os.environ.get("FACTORY_CLOUD_MODEL", "gemini/gemini-2.5-flash")
DEFAULT_LOCAL_MODEL = os.environ.get("FACTORY_LOCAL_MODEL", "ollama/qwen2.5-coder:32b")
# Env var holding the Gemini API key (matches the existing intake worker secret).
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"


@dataclass
class ModelCandidate:
    """One concrete model the gateway may call, with routing metadata."""
    model: str                      # LiteLLM model id, e.g. "gemini/gemini-2.5-flash"
    provider: str                   # "gemini" | "ollama" | ...
    kind: str                       # "cloud" | "local"
    capabilities: Set[Capability] = field(default_factory=set)
    context_window: int = 8192
    is_free: bool = True
    api_key_env: Optional[str] = None   # env var holding the key (cloud); never the value
    api_base: Optional[str] = None      # for local/self-hosted providers
    quality_tier: str = "balanced"      # "fast" | "balanced" | "high"
    priority: int = 100                 # lower = preferred

    def has_key(self) -> bool:
        """True if this candidate is usable now (local always; cloud needs a key)."""
        if self.kind == "local":
            return True
        if self.api_key_env is None:
            return True
        return bool(os.environ.get(self.api_key_env))

    def satisfies(self, capabilities, min_context_tokens: int = 0, free_only: bool = True) -> bool:
        """Whether this candidate meets the given capability/context/free gate."""
        if free_only and not self.is_free:
            return False
        if min_context_tokens and self.context_window < min_context_tokens:
            return False
        return all(cap in self.capabilities for cap in capabilities)


def default_candidates(
    ollama_url: Optional[str] = None,
    cloud_model: Optional[str] = None,
    local_model: Optional[str] = None,
) -> List[ModelCandidate]:
    """The default API-first candidate list: cloud (Gemini) first, local last.

    This encodes D-NEW-005: cloud APIs are the normal path and local Ollama is
    the fallback used automatically when free cloud capacity is unavailable.
    """
    ollama_url = ollama_url or DEFAULT_OLLAMA_URL
    cloud_model = cloud_model or DEFAULT_CLOUD_MODEL
    local_model = local_model or DEFAULT_LOCAL_MODEL

    return [
        ModelCandidate(
            model=cloud_model,
            provider="gemini",
            kind="cloud",
            capabilities={
                Capability.REASONING,
                Capability.CODING,
                Capability.TOOL_CALLING,
                Capability.STRUCTURED_OUTPUT,
                Capability.FAST,
            },
            context_window=1_000_000,
            is_free=True,
            api_key_env=GEMINI_API_KEY_ENV,
            quality_tier="balanced",
            priority=10,
        ),
        ModelCandidate(
            model=local_model,
            provider="ollama",
            kind="local",
            capabilities={Capability.REASONING, Capability.CODING},
            context_window=32_768,
            is_free=True,
            api_base=ollama_url,
            quality_tier="balanced",
            priority=90,
        ),
    ]

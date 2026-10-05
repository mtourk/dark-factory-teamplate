"""
Provider-agnostic LLM layer (FF-P22-01, decisions.yml:D-NEW-005).

Agents describe *what they need* (TaskRequirements) and call the LLMGateway;
they never name a provider, key, or model. The gateway resolves a concrete
provider/model/credential and executes via the LiteLLM Python SDK in-process,
falling back across candidates on failure. Capability-/quota-aware routing,
multi-key credentials, and free-tier intelligence are layered on in later
phases (FF-P22-02/FF-P24-01/FF-P25-01); this package defines the stable
agent-facing contract and the basic candidate-fallback execution.
"""

from factory.llm.capabilities import Capability, PrivacyLevel, TaskRequirements
from factory.llm.gateway import LLMGateway, LLMGatewayError, LLMResponse
from factory.llm.providers import ModelCandidate, default_candidates

__all__ = [
    "Capability",
    "PrivacyLevel",
    "TaskRequirements",
    "LLMGateway",
    "LLMGatewayError",
    "LLMResponse",
    "ModelCandidate",
    "default_candidates",
]

"""
LLMGateway: the provider-agnostic entry point agents call (FF-P22-01).

Resolves a concrete model/provider/credential from a TaskRequirements and
executes via the LiteLLM Python SDK in-process, falling back across candidates
on failure. It records a routing log (which candidates were tried/rejected and
why) so every selection is explainable (plan §43/§75). Full capability-/quota-
aware scoring, multi-key credentials, and free-tier learning are added in later
phases; this is the stable contract + basic ordered fallback.

LiteLLM is imported lazily inside the call so importing this module (and the
rest of the factory) never requires litellm to be installed, and tests can
inject a fake `completion_fn`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from factory.llm.capabilities import TaskRequirements
from factory.llm.providers import ModelCandidate, default_candidates

_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|token|password|secret)\s*[:=]\s*\S+"
)


def redact_secrets(text: str) -> str:
    """Best-effort redaction of key/token-like substrings for safe logging."""
    if not text:
        return text
    return _SECRET_PATTERN.sub(r"\1=<redacted>", text)


def classify_exception(exc: Exception) -> str:
    """Minimal failure classification for fallback decisions (plan §30).

    Full classification + learning is FF-P24-01; this is enough for the gateway
    to log *why* a candidate was skipped and to drive basic fallback.
    """
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "rate" in name or "ratelimit" in name or "429" in msg or "rate limit" in msg:
        return "RATE_LIMIT"
    if "quota" in msg or "resource_exhausted" in msg or "insufficient_quota" in msg:
        return "QUOTA_EXHAUSTED"
    if "auth" in name or "401" in msg or "api key" in msg or "unauthorized" in msg or "permission" in msg:
        return "AUTH"
    if "timeout" in name or "timed out" in msg or "timeout" in msg:
        return "TIMEOUT"
    if "connect" in name or "connection" in msg or "unreachable" in msg or "refused" in msg:
        return "NETWORK"
    if "notfound" in name or "404" in msg or "model" in msg and "not" in msg:
        return "MODEL_UNAVAILABLE"
    if "contextwindow" in name or "context length" in msg or "too long" in msg or "context_length" in msg:
        return "CONTEXT_TOO_LARGE"
    return "UNKNOWN"


@dataclass
class LLMResponse:
    """Normalized result of a successful LLM call."""
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 1
    routing_log: List[dict] = field(default_factory=list)


class LLMGatewayError(RuntimeError):
    """Raised when every candidate failed. Carries the per-candidate attempts."""

    def __init__(self, message: str, attempts: List[dict]):
        super().__init__(message)
        self.attempts = attempts


def _extract_content_and_usage(response) -> tuple:
    """Pull (text, input_tokens, output_tokens) from a LiteLLM response or a
    fake that mimics its shape (object-style or dict-style)."""
    # Object-style (litellm.ModelResponse / OpenAI-compatible).
    try:
        choice = response.choices[0]
        message = getattr(choice, "message", None) or choice["message"]
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        in_tok = getattr(usage, "prompt_tokens", None) if usage is not None else None
        out_tok = getattr(usage, "completion_tokens", None) if usage is not None else None
        if in_tok is None and isinstance(usage, dict):
            in_tok = usage.get("prompt_tokens")
            out_tok = usage.get("completion_tokens")
        return content, int(in_tok or 0), int(out_tok or 0)
    except (AttributeError, KeyError, IndexError, TypeError):
        pass
    # Dict-style fallback.
    if isinstance(response, dict):
        choices = response.get("choices") or [{}]
        content = (choices[0].get("message") or {}).get("content")
        usage = response.get("usage") or {}
        return content, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)
    raise ValueError("Unrecognized LLM response shape")


class LLMGateway:
    """Provider-agnostic LLM gateway over LiteLLM (in-process)."""

    def __init__(
        self,
        candidates: Optional[List[ModelCandidate]] = None,
        completion_fn: Optional[Callable[..., object]] = None,
    ):
        """
        Args:
            candidates: ordered candidate models; defaults to the API-first
                default (Gemini cloud -> local Ollama fallback).
            completion_fn: callable with litellm.completion's signature. Injected
                by tests; when None the real litellm SDK is imported lazily.
        """
        self.candidates = candidates if candidates is not None else default_candidates()
        self._completion_fn = completion_fn

    def _litellm_completion(self, **kwargs):
        import litellm  # lazy: importing the gateway never requires litellm
        return litellm.completion(**kwargs)

    def select_candidates(
        self,
        requirements: TaskRequirements,
        model_hint: Optional[str] = None,
    ) -> List[ModelCandidate]:
        """Candidates that satisfy the requirements and have a usable credential,
        ordered by priority. A model_hint (e.g. an Ollama tag from an issue
        label) promotes a matching candidate to the front."""
        caps = requirements.effective_capabilities()
        usable = [
            c for c in self.candidates
            if c.satisfies(caps, requirements.min_context_tokens, requirements.free_only)
            and c.has_key()
        ]
        usable.sort(key=lambda c: c.priority)
        if model_hint:
            hint = model_hint.strip()
            usable.sort(key=lambda c: 0 if (hint in c.model or c.model.endswith(hint)) else 1)
        return usable

    def complete(
        self,
        *,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        role: Optional[str] = None,
        run_id: Optional[str] = None,
        requirements: Optional[TaskRequirements] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Execute a completion, falling back across candidates on failure.

        Provide either `messages` (OpenAI-format) or `system_prompt`/`user_prompt`.
        `model` is an optional hint (not a mandate). Raises LLMGatewayError if
        every candidate fails or none are usable.
        """
        requirements = requirements or TaskRequirements()
        if messages is None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt or ""})

        candidates = self.select_candidates(requirements, model_hint=model)
        completion = self._completion_fn or self._litellm_completion

        routing_log: List[dict] = []
        if not candidates:
            raise LLMGatewayError(
                "No usable LLM candidate (none satisfy the requirements or hold a credential). "
                "If all free cloud capacity is unavailable, ensure a local Ollama model is reachable.",
                routing_log,
            )

        for cand in candidates:
            kwargs = {"model": cand.model, "messages": messages, "stream": False}
            if cand.api_base:
                kwargs["api_base"] = cand.api_base
            if cand.api_key_env:
                key = os.environ.get(cand.api_key_env)
                if key:
                    kwargs["api_key"] = key
            if requirements.max_output_tokens:
                kwargs["max_tokens"] = requirements.max_output_tokens
            try:
                response = completion(**kwargs)
                text, in_tok, out_tok = _extract_content_and_usage(response)
                if not text:
                    raise ValueError("Empty response content")
                routing_log.append({"model": cand.model, "provider": cand.provider, "result": "selected"})
                return LLMResponse(
                    text=text,
                    provider=cand.provider,
                    model=cand.model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    attempts=len(routing_log),
                    routing_log=routing_log,
                )
            except Exception as exc:  # noqa: BLE001 - classify and fall back
                routing_log.append({
                    "model": cand.model,
                    "provider": cand.provider,
                    "result": "rejected",
                    "failure": classify_exception(exc),
                    "detail": redact_secrets(str(exc))[:300],
                })
                continue

        raise LLMGatewayError(
            f"All {len(candidates)} LLM candidate(s) failed for role={role} run={run_id}.",
            routing_log,
        )

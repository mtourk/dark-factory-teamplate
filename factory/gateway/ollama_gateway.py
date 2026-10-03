"""
Ollama Model Gateway: unified inference interface with isolation and telemetry.

Per master plan §6.3:
"Model gateway:
- Fresh sessions (new API call per role + run)
- Context limit enforcement (8192 tokens initially)
- Timeout and cancellation
- Structured-output validation (JSON schema)
- Tool normalization
- Telemetry logging (prompt tokens, completion tokens, latency)
- Retry policy (exponential backoff, max 3 attempts)
- Redaction of secrets from logs"

All roles → qwen2.5-coder:32b (ADR-001: single model for all roles).
"""

import asyncio
import json
import time
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

try:
    import httpx
except ImportError:
    httpx = None


logger = logging.getLogger(__name__)


# ============================================================================
# Model Configuration
# ============================================================================

class ModelRole(str, Enum):
    """Factory roles and their model assignments (ADR-001)."""
    ANALYST = "analyst"
    PRODUCT_CRITIC = "product_critic"
    DOMAIN_CRITIC = "domain_critic"
    TESTABILITY_CRITIC = "testability_critic"
    SECURITY_CRITIC = "security_critic"
    CONTRADICTION_CRITIC = "contradiction_critic"
    OPERATIONAL_CRITIC = "operational_critic"
    PLANNER = "planner"
    BUILDER = "builder"
    REPAIRER = "repairer"
    SEALED_QA = "sealed_qa"
    REVIEWER = "reviewer"
    ORCHESTRATOR = "orchestrator"


# All roles use the same model (ADR-001)
MODEL_ALIASES = {role.value: "qwen2.5-coder:32b" for role in ModelRole}


# ============================================================================
# Telemetry and Logging
# ============================================================================

@dataclass
class InferenceMetrics:
    """Inference metrics for telemetry and benchmarking."""
    role: str
    run_id: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    first_token_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    retry_count: int = 0
    success: bool = True
    error_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON logging."""
        return {
            "role": self.role,
            "run_id": self.run_id,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "first_token_ms": round(self.first_token_ms, 2),
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "success": self.success,
            "error_reason": self.error_reason,
        }


# ============================================================================
# Ollama Gateway
# ============================================================================

class OllamaGateway:
    """
    Unified Ollama inference gateway with isolation, telemetry, and retry logic.

    Each call creates a fresh session (per §6.3):
    - New HTTP conversation per role + run
    - Context limit enforcement (8192 tokens)
    - Timeout and cancellation support
    - Structured output validation
    - Telemetry logging (tokens, latency)
    - Exponential backoff retries (max 3)
    - Secret redaction
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        context_limit: int = 8192,
        timeout_seconds: int = 300,
        max_retries: int = 3,
    ):
        """
        Initialize gateway.

        Args:
            base_url: Ollama server URL
            context_limit: max tokens per request
            timeout_seconds: request timeout
            max_retries: max retry attempts on failure
        """
        self.base_url = base_url
        self.context_limit = context_limit
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.metrics: List[InferenceMetrics] = []

    async def infer(
        self,
        role: str,
        run_id: str,
        prompt: str,
        model: Optional[str] = None,
        structured_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Fresh inference call (new session per role + run, §6.3).

        Args:
            role: factory role (determines model via MODEL_ALIASES)
            run_id: run ID for telemetry
            prompt: user prompt
            model: optional model override (default from MODEL_ALIASES[role])
            structured_schema: JSON schema for structured output validation
            tools: optional tool definitions for normalization

        Returns:
            {"response": str, "tokens": {...}, "metrics": InferenceMetrics}

        Raises:
            RuntimeError: if all retries exhausted or model unavailable
        """
        model = model or MODEL_ALIASES.get(role, "qwen2.5-coder:32b")
        metrics = InferenceMetrics(role=role, run_id=run_id, model=model)

        # Validate context limit
        prompt_truncated = self._truncate_to_token_limit(prompt)

        # Retry loop with exponential backoff
        for attempt in range(self.max_retries):
            try:
                metrics.retry_count = attempt
                start_time = time.time()

                # Fresh session (no persistent connection reuse per role+run)
                async with httpx.AsyncClient() as client:
                    response = await self._call_ollama(
                        client,
                        model,
                        prompt_truncated,
                        tools,
                    )

                end_time = time.time()
                metrics.latency_ms = (end_time - start_time) * 1000
                metrics.success = True

                # Parse response
                text = response.get("response", "")
                usage = response.get("usage", {})
                metrics.prompt_tokens = usage.get("prompt_tokens", 0)
                metrics.completion_tokens = usage.get("completion_tokens", 0)
                metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens

                # Validate structured output if schema provided
                if structured_schema:
                    text = self._validate_structured_output(
                        text, structured_schema
                    )

                # Log telemetry
                self.metrics.append(metrics)
                logger.info(f"Inference OK: {json.dumps(metrics.to_dict())}")

                return {
                    "response": text,
                    "tokens": {
                        "prompt": metrics.prompt_tokens,
                        "completion": metrics.completion_tokens,
                        "total": metrics.total_tokens,
                    },
                    "metrics": metrics,
                }

            except Exception as e:
                metrics.success = False
                metrics.error_reason = str(e)

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Inference failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    # All retries exhausted
                    logger.error(f"Inference failed after {self.max_retries} retries: {e}")
                    self.metrics.append(metrics)
                    raise RuntimeError(
                        f"Model inference failed after {self.max_retries} retries: {e}"
                    ) from e

    async def _call_ollama(
        self,
        client: "httpx.AsyncClient",
        model: str,
        prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Make fresh Ollama API call (fresh session per call per §6.3).

        Args:
            client: httpx async client
            model: model name
            prompt: prompt text
            tools: optional tools

        Returns:
            Ollama API response dict

        Raises:
            httpx.RequestError: on network/API error
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,  # Synchronous response for simplicity
        }

        if tools:
            payload["tools"] = tools

        response = await client.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        return response.json()

    def _truncate_to_token_limit(self, prompt: str) -> str:
        """
        Rough token truncation to enforce context limit (§6.3).

        Simple heuristic: ~4 chars per token.
        """
        max_chars = self.context_limit * 4
        if len(prompt) > max_chars:
            logger.warning(
                f"Prompt truncated from {len(prompt)} to {max_chars} chars "
                f"(context limit {self.context_limit} tokens)"
            )
            return prompt[:max_chars]
        return prompt

    def _validate_structured_output(
        self,
        response: str,
        schema: Dict[str, Any],
    ) -> str:
        """
        Validate structured output against schema (§6.3).

        Args:
            response: model response text
            schema: JSON schema for validation

        Returns:
            validated response (or raises on validation error)

        Raises:
            ValueError: if response doesn't match schema
        """
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            raise ValueError(f"Response is not valid JSON: {response[:100]}")

        # Basic schema validation (simplified; real implementation would use
        # jsonschema library)
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                raise ValueError(
                    f"Response missing required field: {field}"
                )

        return response

    def redact_secrets(self, log_line: str) -> str:
        """
        Redact secrets from logs (§6.3).

        Replaces known secret patterns with **REDACTED**.
        """
        # Pattern: "key": "value" where key matches secret names
        import re
        patterns = [
            r'"(api_key|token|password|secret|cloudflare_token)":\s*"[^"]*"',
            r'"(bearer|authorization)":\s*"Bearer [^"]*"',
        ]
        result = log_line
        for pattern in patterns:
            result = re.sub(pattern, r'"\1": "**REDACTED**"', result, flags=re.IGNORECASE)
        return result

    def get_metrics(self) -> List[InferenceMetrics]:
        """Get all recorded metrics."""
        return self.metrics


# ============================================================================
# Fake Model for Testing
# ============================================================================

class FakeModel:
    """
    Fake Ollama model for deterministic unit tests (no Ollama required).

    Simulates gateway behavior without network calls.
    """

    def __init__(self, deterministic_responses: Optional[Dict[str, str]] = None):
        """
        Initialize fake model.

        Args:
            deterministic_responses: dict mapping prompt hashes to responses
        """
        self.deterministic_responses = deterministic_responses or {}
        self.call_count = 0
        self.metrics: List[InferenceMetrics] = []

    async def infer(
        self,
        role: str,
        run_id: str,
        prompt: str,
        model: Optional[str] = None,
        structured_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Fake inference (deterministic, no network).

        Args:
            role: factory role
            run_id: run ID
            prompt: user prompt
            model: optional model override
            structured_schema: JSON schema (ignored in fake)
            tools: optional tools (ignored in fake)

        Returns:
            {"response": str, "tokens": {...}, "metrics": InferenceMetrics}
        """
        self.call_count += 1
        model = model or MODEL_ALIASES.get(role, "qwen2.5-coder:32b")

        # Deterministic response based on prompt hash
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        response_text = self.deterministic_responses.get(
            prompt_hash,
            f"Fake response for {role} (prompt hash: {prompt_hash})",
        )

        # Simulate token counts
        prompt_tokens = len(prompt.split())
        completion_tokens = len(response_text.split())
        total_tokens = prompt_tokens + completion_tokens

        metrics = InferenceMetrics(
            role=role,
            run_id=run_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=10.0,  # Fake: instant
            first_token_ms=2.0,  # Fake: instant
            success=True,
        )

        self.metrics.append(metrics)

        return {
            "response": response_text,
            "tokens": {
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": total_tokens,
            },
            "metrics": metrics,
        }

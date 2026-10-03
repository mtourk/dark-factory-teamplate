"""
Cloudflare Deployment Adapter (Wrangler integration).

Per master plan §15:
"GitHub Actions owns Cloudflare secrets. Models and local processes may not
read them. PR preview must pass before auto-merge. Push to `main` triggers
production.

After deployment, verify deployed version, health, critical browser/API
behavior, and project-specific invariants.

If deployment or smoke validation fails, pause new merges, record bad
SHA/deployment, follow only declared recovery, verify last-known-good state,
and resume only when production is known. Never invent destructive migration
rollback."

CRITICAL SECURITY INVARIANT: this module never holds, reads, logs, or
accepts a Cloudflare API token or account ID as a value. It only builds
command argument lists that *reference* environment variable names
(`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`) which Wrangler reads
directly from the process environment at execution time. That environment
is populated exclusively by GitHub Actions `secrets.*` injection -- never by
this codebase, never by a local `.env` file, and never by the factory
orchestrator. See `.factory/workflows/deploy.yml`.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# Environment variable names Wrangler itself reads. The adapter only ever
# refers to these *names*, never to a value.
CLOUDFLARE_TOKEN_ENV_VAR = "CLOUDFLARE_API_TOKEN"
CLOUDFLARE_ACCOUNT_ENV_VAR = "CLOUDFLARE_ACCOUNT_ID"

# A conservative token/secret-looking pattern used only to make sure nothing
# resembling a Cloudflare token has leaked into a value this adapter is
# about to log or record. This is a defensive guard, not the source of
# truth for secret handling.
_SUSPECTED_SECRET_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")


class DeploymentTarget(str, Enum):
    """Where a deployment is going (§15)."""
    PREVIEW = "preview"
    PRODUCTION = "production"


class DeploymentStatus(str, Enum):
    """Outcome of a deployment attempt."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    HEALTH_CHECK_FAILED = "health_check_failed"
    VERSION_MISMATCH = "version_mismatch"


class SecretLeakError(Exception):
    """Raised if a value that looks like a secret would be logged or recorded."""


def redact_for_logging(value: str) -> str:
    """
    Defensive redaction: replace anything resembling a long token/secret
    with a placeholder before it is ever logged or recorded in evidence.
    """
    return _SUSPECTED_SECRET_PATTERN.sub("[REDACTED]", value)


def assert_adapter_holds_no_secret(obj: Any) -> None:
    """
    Fail-closed guard: scan an object's attribute names for anything that
    looks like it is trying to hold a secret value directly. Used by tests
    to assert the adapter class never grows a `token`/`api_key` field.
    """
    forbidden_substrings = ("token", "secret", "api_key", "apikey", "password")
    for attr_name in vars(obj).keys() if hasattr(obj, "__dict__") else []:
        lowered = attr_name.lower()
        for forbidden in forbidden_substrings:
            if forbidden in lowered:
                raise SecretLeakError(
                    f"Adapter attribute '{attr_name}' suggests secret storage; "
                    "secrets must live only in the GitHub Actions environment."
                )


@dataclass
class DeploymentRequest:
    """A request to deploy to Cloudflare via Wrangler."""
    target: DeploymentTarget
    sha: str
    project_name: str
    branch: Optional[str] = None  # required for PREVIEW
    wrangler_env: Optional[str] = None  # e.g. "staging" / "production"

    def __post_init__(self):
        if self.target == DeploymentTarget.PREVIEW and not self.branch:
            raise ValueError("Preview deployments require a branch name")
        if len(self.sha) != 40 or not all(c in "0123456789abcdef" for c in self.sha.lower()):
            raise ValueError("sha must be a 40-character hex commit SHA")


@dataclass
class DeploymentResult:
    """Result of a Wrangler deployment attempt."""
    target: DeploymentTarget
    sha: str
    status: DeploymentStatus
    deployed_url: Optional[str] = None
    raw_output_redacted: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None


@dataclass
class HealthCheckResult:
    """Result of post-deployment health/invariant validation (§15)."""
    url: str
    healthy: bool
    status_code: Optional[int] = None
    version_matches: Optional[bool] = None
    invariants_checked: Dict[str, bool] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Regex over typical `wrangler deploy` / `wrangler pages deploy` stdout to
# find the deployed URL, e.g. "Published investisor (1.23 sec) ... https://abc123.investisor.pages.dev"
_WRANGLER_URL_PATTERN = re.compile(r"https://[a-zA-Z0-9.\-]+\.(pages|workers)\.dev\S*")


class CloudflareAdapter:
    """
    Wrangler integration for Cloudflare Pages/Workers deployment.

    This adapter never stores or transmits Cloudflare credentials. It only:
    1. Builds the Wrangler command line (which relies on Wrangler reading
       CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID from the environment).
    2. Parses command output for the deployed URL.
    3. Runs post-deployment health checks and version verification via an
       injectable HTTP client (never network calls baked into this class),
       so it stays unit-testable with a fake transport.
    """

    def __init__(self, http_get: Optional[Callable[[str], Any]] = None):
        """
        Args:
            http_get: injectable callable(url) -> response-like object with
                `.status_code` and `.text`/`.headers`. Defaults to None;
                callers running inside GitHub Actions inject `requests.get`
                (or similar) at the call site, never at construction time
                with any embedded credential.
        """
        self._http_get = http_get

    def build_wrangler_command(self, request: DeploymentRequest) -> List[str]:
        """
        Build the Wrangler CLI invocation for this deployment.

        The returned command never embeds a token or account ID value --
        Wrangler reads CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID directly
        from the process environment that GitHub Actions populates from
        `secrets.*` at workflow run time.
        """
        cmd = ["wrangler", "deploy"]

        if request.wrangler_env:
            cmd += ["--env", request.wrangler_env]

        if request.target == DeploymentTarget.PREVIEW:
            # Wrangler Pages preview deployments are branch-scoped.
            cmd += ["--branch", request.branch]

        return cmd

    def parse_deploy_output(self, raw_output: str) -> Optional[str]:
        """Extract the deployed URL from Wrangler stdout, if present."""
        match = _WRANGLER_URL_PATTERN.search(raw_output)
        return match.group(0) if match else None

    def record_deployment_attempt(
        self,
        request: DeploymentRequest,
        raw_output: str,
        succeeded: bool,
        error: Optional[str] = None,
    ) -> DeploymentResult:
        """
        Turn raw (potentially noisy) Wrangler output into a redacted,
        evidence-safe DeploymentResult. Nothing resembling a secret is
        retained.
        """
        redacted_output = redact_for_logging(raw_output)
        deployed_url = self.parse_deploy_output(raw_output) if succeeded else None

        status = DeploymentStatus.SUCCEEDED if succeeded else DeploymentStatus.FAILED

        return DeploymentResult(
            target=request.target,
            sha=request.sha,
            status=status,
            deployed_url=deployed_url,
            raw_output_redacted=redacted_output,
            error=redact_for_logging(error) if error else None,
        )

    def verify_deployed_version(
        self,
        deployed_url: str,
        expected_sha: str,
        version_header: str = "x-factory-sha",
    ) -> bool:
        """
        Verify the deployed site reports the expected commit SHA (§15:
        "verify deployed version").

        Expects the target app to expose its build SHA via a response
        header (set at build time); this is a project-specific invariant
        the target repo (investisor) must implement.
        """
        if self._http_get is None:
            raise RuntimeError("No HTTP client injected; cannot verify deployed version")

        response = self._http_get(deployed_url)
        headers = getattr(response, "headers", {}) or {}
        reported_sha = headers.get(version_header, "")
        return reported_sha.strip().lower() == expected_sha.strip().lower()

    def run_health_check(
        self,
        url: str,
        expected_sha: Optional[str] = None,
        invariants: Optional[Dict[str, Callable[[Any], bool]]] = None,
    ) -> HealthCheckResult:
        """
        Run post-deployment health and invariant validation (§15: "verify
        deployed version, health, critical browser/API behavior, and
        project-specific invariants").

        Args:
            url: the deployed preview or production URL.
            expected_sha: if provided, also verifies the version header.
            invariants: named predicate functions, each given the HTTP
                response and returning True/False, for project-specific
                checks (e.g. "homepage_loads", "api_responds").
        """
        if self._http_get is None:
            raise RuntimeError("No HTTP client injected; cannot run health check")

        try:
            response = self._http_get(url)
        except Exception as exc:  # noqa: BLE001 - deployment network errors are expected
            return HealthCheckResult(
                url=url,
                healthy=False,
                error=redact_for_logging(str(exc)),
            )

        status_code = getattr(response, "status_code", None)
        base_healthy = status_code is not None and 200 <= status_code < 400

        version_matches = None
        if expected_sha is not None:
            headers = getattr(response, "headers", {}) or {}
            reported_sha = headers.get("x-factory-sha", "")
            version_matches = reported_sha.strip().lower() == expected_sha.strip().lower()

        invariants_checked: Dict[str, bool] = {}
        if invariants:
            for name, predicate in invariants.items():
                try:
                    invariants_checked[name] = bool(predicate(response))
                except Exception:  # noqa: BLE001 - a failing invariant check is a failed invariant
                    invariants_checked[name] = False

        all_invariants_pass = all(invariants_checked.values()) if invariants_checked else True
        version_ok = version_matches if version_matches is not None else True

        healthy = base_healthy and version_ok and all_invariants_pass

        return HealthCheckResult(
            url=url,
            healthy=healthy,
            status_code=status_code,
            version_matches=version_matches,
            invariants_checked=invariants_checked,
        )

    def to_evidence_record(
        self,
        deployment: DeploymentResult,
        health: Optional[HealthCheckResult],
    ) -> Dict[str, Any]:
        """
        Build the evidence-manifest-safe record for this deployment (§16).
        Contains no secret material -- only SHAs, URLs, statuses, timestamps.
        """
        record: Dict[str, Any] = {
            "target": deployment.target.value,
            "sha": deployment.sha,
            "status": deployment.status.value,
            "deployed_url": deployment.deployed_url,
            "timestamp": deployment.timestamp,
        }
        if deployment.error:
            record["error"] = deployment.error
        if health is not None:
            record["health"] = {
                "healthy": health.healthy,
                "status_code": health.status_code,
                "version_matches": health.version_matches,
                "invariants_checked": health.invariants_checked,
                "error": health.error,
            }
        return record

"""
Phase 13: Cloudflare Preview and Production Deployment tests (§15).

Tests for:
1. Cloudflare adapter design (no secrets held locally)
2. Wrangler command construction
3. Deploy output parsing
4. Version verification
5. Health check and invariant validation
6. Evidence recording (SHA binding, no secrets)
7. Preview deployment + smoke test
8. Production deployment + health validation
9. Deployment status tracking
10. Error recording and redaction
"""

import pytest
from unittest.mock import Mock, MagicMock

from factory.deploy.cloudflare_adapter import (
    CloudflareAdapter,
    DeploymentRequest,
    DeploymentTarget,
    DeploymentStatus,
    HealthCheckResult,
    SecretLeakError,
    redact_for_logging,
    assert_adapter_holds_no_secret,
    CLOUDFLARE_TOKEN_ENV_VAR,
    CLOUDFLARE_ACCOUNT_ENV_VAR,
)


# ============================================================================
# Security: No Secrets Held Locally (§15)
# ============================================================================

class TestSecretHandling:
    """Test that adapter never stores secrets locally."""

    def test_adapter_instance_has_no_token_field(self):
        """Verify adapter does not have a token/secret-like field."""
        adapter = CloudflareAdapter()
        assert_adapter_holds_no_secret(adapter)

    def test_adapter_never_returns_secret_in_command(self):
        """Built command never embeds secret values -- only env var names."""
        adapter = CloudflareAdapter()
        request = DeploymentRequest(
            target=DeploymentTarget.PRODUCTION,
            sha="a" * 40,
            project_name="investisor",
        )
        cmd = adapter.build_wrangler_command(request)

        # Wrangler expects to read secrets from env, not command line.
        assert "wrangler" in cmd
        assert "deploy" in cmd

        # CRITICAL: secret values never appear as args; only env var names are known.
        assert CLOUDFLARE_TOKEN_ENV_VAR not in cmd
        assert CLOUDFLARE_ACCOUNT_ENV_VAR not in cmd

    def test_suspected_secret_redacted_in_logging(self):
        """Long token-like strings redacted before logging."""
        # Synthetic placeholder matching Cloudflare token shape -- never a
        # real credential. Real secrets must never appear in source or tests.
        fake_token = "cfat_" + "x" * 40
        noisy_output = f"Deployed with token {fake_token}!"
        redacted = redact_for_logging(noisy_output)

        assert "[REDACTED]" in redacted
        assert fake_token not in redacted


# ============================================================================
# Command Construction Tests (§15 via Wrangler)
# ============================================================================

class TestWranglerCommandConstruction:
    """Test Wrangler CLI building."""

    def test_preview_command_with_branch(self):
        """Preview deployment includes branch."""
        adapter = CloudflareAdapter()
        request = DeploymentRequest(
            target=DeploymentTarget.PREVIEW,
            sha="a" * 40,
            project_name="investisor",
            branch="pr-42",
        )
        cmd = adapter.build_wrangler_command(request)

        assert "wrangler" in cmd
        assert "deploy" in cmd
        assert "--branch" in cmd
        assert "pr-42" in cmd

    def test_production_command_no_branch(self):
        """Production deployment doesn't require branch."""
        adapter = CloudflareAdapter()
        request = DeploymentRequest(
            target=DeploymentTarget.PRODUCTION,
            sha="a" * 40,
            project_name="investisor",
        )
        cmd = adapter.build_wrangler_command(request)

        assert "wrangler" in cmd
        assert "deploy" in cmd
        assert "--branch" not in cmd

    def test_preview_without_branch_raises(self):
        """Preview deployment without branch is invalid."""
        with pytest.raises(ValueError, match="branch"):
            DeploymentRequest(
                target=DeploymentTarget.PREVIEW,
                sha="a" * 40,
                project_name="investisor",
            )

    def test_invalid_sha_raises(self):
        """Invalid SHA format rejected."""
        with pytest.raises(ValueError, match="sha"):
            DeploymentRequest(
                target=DeploymentTarget.PRODUCTION,
                sha="tooshort",
                project_name="investisor",
            )


# ============================================================================
# Deploy Output Parsing Tests
# ============================================================================

class TestDeployOutputParsing:
    """Test extraction of deployed URL from Wrangler output."""

    def test_parse_pages_deploy_output(self):
        """Extract Pages URL from deploy output."""
        output = """
        Building...
        Published investisor (1.23 sec)
        -> https://pr42.investisor.pages.dev
        """
        adapter = CloudflareAdapter()
        url = adapter.parse_deploy_output(output)

        assert url is not None
        assert "investisor.pages.dev" in url

    def test_parse_workers_deploy_output(self):
        """Extract Workers URL from deploy output."""
        output = "✓ Deployed investisor to https://factory.investisor.workers.dev"
        adapter = CloudflareAdapter()
        url = adapter.parse_deploy_output(output)

        assert url is not None
        assert "workers.dev" in url

    def test_parse_empty_output(self):
        """Handle output with no URL."""
        adapter = CloudflareAdapter()
        url = adapter.parse_deploy_output("Error: deployment failed")

        assert url is None


# ============================================================================
# Health Check and Invariant Validation Tests (§15)
# ============================================================================

class TestHealthChecks:
    """Test post-deployment validation."""

    def test_health_check_passes_on_200(self):
        """Deployment is healthy when status 200."""
        mock_http = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"x-factory-sha": "a" * 40}
        mock_http.return_value = mock_response

        adapter = CloudflareAdapter(http_get=mock_http)
        result = adapter.run_health_check(
            "https://example.pages.dev",
            expected_sha="a" * 40,
        )

        assert result.healthy is True
        assert result.status_code == 200
        assert result.version_matches is True

    def test_health_check_fails_on_500(self):
        """Deployment is unhealthy when status 500."""
        mock_http = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_http.return_value = mock_response

        adapter = CloudflareAdapter(http_get=mock_http)
        result = adapter.run_health_check("https://example.pages.dev")

        assert result.healthy is False
        assert result.status_code == 500

    def test_version_mismatch_blocks_health(self):
        """Deployed version not matching SHA blocks health check (§13)."""
        mock_http = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"x-factory-sha": "b" * 40}
        mock_http.return_value = mock_response

        adapter = CloudflareAdapter(http_get=mock_http)
        result = adapter.run_health_check(
            "https://example.pages.dev",
            expected_sha="a" * 40,
        )

        assert result.healthy is False
        assert result.version_matches is False

    def test_invariant_checks_run(self):
        """Custom invariants evaluated during health check."""
        mock_http = Mock()
        mock_response = Mock(status_code=200, headers={}, text="OK")
        mock_http.return_value = mock_response

        invariants = {
            "homepage_loads": lambda r: hasattr(r, "text") and "OK" in r.text,
            "api_responds": lambda r: False,  # This will fail
        }

        adapter = CloudflareAdapter(http_get=mock_http)
        result = adapter.run_health_check(
            "https://example.pages.dev",
            invariants=invariants,
        )

        assert result.invariants_checked["homepage_loads"] is True
        assert result.invariants_checked["api_responds"] is False
        assert result.healthy is False  # api_responds failed

    def test_health_check_network_error_caught(self):
        """Network errors during health check are recorded."""
        mock_http = Mock(side_effect=ConnectionError("Network unreachable"))

        adapter = CloudflareAdapter(http_get=mock_http)
        result = adapter.run_health_check("https://example.pages.dev")

        assert result.healthy is False
        assert result.error is not None
        assert "[REDACTED]" in result.error or "Network" in result.error


# ============================================================================
# Deployment Recording and Evidence Tests (§16)
# ============================================================================

class TestEvidenceRecording:
    """Test evidence-safe deployment recording."""

    def test_deployment_result_to_evidence(self):
        """Deployment result recorded for evidence manifest."""
        from factory.deploy.cloudflare_adapter import DeploymentResult

        deployment = DeploymentResult(
            target=DeploymentTarget.PREVIEW,
            sha="a" * 40,
            status=DeploymentStatus.SUCCEEDED,
            deployed_url="https://pr42.investisor.pages.dev",
        )

        health = HealthCheckResult(
            url="https://pr42.investisor.pages.dev",
            healthy=True,
            status_code=200,
            version_matches=True,
        )

        adapter = CloudflareAdapter()
        evidence = adapter.to_evidence_record(deployment, health)

        assert evidence["target"] == "preview"
        assert evidence["sha"] == "a" * 40
        assert evidence["status"] == "succeeded"
        assert evidence["health"]["healthy"] is True
        # No secret material in evidence
        assert "token" not in str(evidence).lower()
        assert "secret" not in str(evidence).lower()


# ============================================================================
# Deployment Result Recording
# ============================================================================

class TestDeploymentRecording:
    """Test deployment attempt recording."""

    def test_record_successful_deployment(self):
        """Successful deployment recorded with URL."""
        adapter = CloudflareAdapter()
        request = DeploymentRequest(
            target=DeploymentTarget.PREVIEW,
            sha="a" * 40,
            project_name="investisor",
            branch="pr-42",
        )
        output = "-> https://pr42.investisor.pages.dev"

        result = adapter.record_deployment_attempt(
            request,
            output,
            succeeded=True,
        )

        assert result.status == DeploymentStatus.SUCCEEDED
        assert result.deployed_url == "https://pr42.investisor.pages.dev"

    def test_record_failed_deployment(self):
        """Failed deployment recorded with error."""
        adapter = CloudflareAdapter()
        request = DeploymentRequest(
            target=DeploymentTarget.PRODUCTION,
            sha="a" * 40,
            project_name="investisor",
        )

        result = adapter.record_deployment_attempt(
            request,
            "Error: authentication failed",
            succeeded=False,
            error="Wrangler exited with code 1",
        )

        assert result.status == DeploymentStatus.FAILED
        assert result.deployed_url is None
        assert result.error is not None


# ============================================================================
# Phase 13 Gate Test
# ============================================================================

def test_phase13_gate_cloudflare_preview_and_production_operational():
    """
    Phase 13 Gate: Cloudflare preview and production deployment operational (§15).

    Verifies:
    - No secrets held locally (only env var names in commands)
    - Wrangler command construction for preview + production
    - Deploy output parsing (Pages and Workers URLs)
    - Health check + version verification
    - Invariant validation (project-specific checks)
    - Evidence recording (no secrets, SHAs, URLs, status, timestamps)
    - Deployment result recording and redaction
    """

    # 1. Adapter security invariant: no secrets stored
    adapter = CloudflareAdapter()
    assert_adapter_holds_no_secret(adapter)

    # 2. Preview deployment command
    preview_req = DeploymentRequest(
        target=DeploymentTarget.PREVIEW,
        sha="a" * 40,
        project_name="investisor",
        branch="pr-123",
    )
    preview_cmd = adapter.build_wrangler_command(preview_req)
    assert "wrangler" in preview_cmd
    assert "--branch" in preview_cmd
    assert "pr-123" in preview_cmd

    # 3. Production deployment command
    prod_req = DeploymentRequest(
        target=DeploymentTarget.PRODUCTION,
        sha="b" * 40,
        project_name="investisor",
    )
    prod_cmd = adapter.build_wrangler_command(prod_req)
    assert "wrangler" in prod_cmd
    assert "--branch" not in prod_cmd

    # 4. URL parsing
    wrangler_output = "-> https://pr123.investisor.pages.dev"
    url = adapter.parse_deploy_output(wrangler_output)
    assert url == "https://pr123.investisor.pages.dev"

    # 5. Health check with version verification (§15: verify deployed version)
    mock_http = Mock()
    mock_response = Mock(status_code=200, headers={"x-factory-sha": "b" * 40})
    mock_http.return_value = mock_response

    health = adapter.run_health_check(
        "https://prod.investisor.pages.dev",
        expected_sha="b" * 40,
    )
    assert health.healthy is True
    assert health.version_matches is True

    # 6. Invariants (project-specific checks per §15)
    invariants = {
        "critical_api": lambda r: r.status_code == 200,
    }
    health_with_invariants = adapter.run_health_check(
        "https://prod.investisor.pages.dev",
        expected_sha="b" * 40,
        invariants=invariants,
    )
    assert health_with_invariants.invariants_checked["critical_api"] is True

    # 7. Evidence recording (no secrets)
    from factory.deploy.cloudflare_adapter import DeploymentResult

    deployment = DeploymentResult(
        target=DeploymentTarget.PRODUCTION,
        sha="b" * 40,
        status=DeploymentStatus.SUCCEEDED,
        deployed_url="https://prod.investisor.pages.dev",
    )
    evidence = adapter.to_evidence_record(deployment, health)

    assert evidence["sha"] == "b" * 40
    assert evidence["health"]["healthy"] is True
    # No credential material in evidence
    assert "token" not in str(evidence).lower()
    assert "password" not in str(evidence).lower()

    # 8. Version mismatch blocks production (§15)
    mock_response_mismatch = Mock(
        status_code=200, headers={"x-factory-sha": "c" * 40}
    )
    mock_http.return_value = mock_response_mismatch
    health_mismatch = adapter.run_health_check(
        "https://prod.investisor.pages.dev",
        expected_sha="b" * 40,
    )
    assert health_mismatch.healthy is False
    assert health_mismatch.version_matches is False

    print("✓ Phase 13 Gate: Cloudflare preview/production deployment operational (no secrets held locally, health/version verified, evidence safe)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

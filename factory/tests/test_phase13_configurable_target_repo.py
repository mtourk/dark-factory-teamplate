"""
Phase 13 Extended: Configurable target-repo tests.

Tests for:
1. TargetRepository parsing and validation
2. FactoryConfig with target repo
3. TargetRepoSetup (workflow sync, secret configuration)
4. User-facing instructions generation
"""

import pytest

from factory.config import TargetRepository, FactoryConfig
from factory.deploy.target_repo_setup import TargetRepoSetup


# ============================================================================
# Target Repository Configuration Tests
# ============================================================================

class TestTargetRepository:
    """Test target repository configuration."""

    def test_target_repo_creation(self):
        """Create a target repository config."""
        repo = TargetRepository(
            owner="myorg",
            name="myrepo",
            url="https://github.com/myorg/myrepo",
        )
        assert repo.owner == "myorg"
        assert repo.name == "myrepo"
        assert repo.repo_string == "myorg/myrepo"

    def test_parse_github_url(self):
        """Parse GitHub HTTPS URL into target repo."""
        url = "https://github.com/user/project"
        repo = TargetRepository.from_url(url)

        assert repo.owner == "user"
        assert repo.name == "project"
        assert repo.url == url

    def test_invalid_url_raises(self):
        """Invalid GitHub URL rejected."""
        with pytest.raises(ValueError, match="GitHub HTTPS"):
            TargetRepository.from_url("https://example.com/user/repo")

    def test_missing_owner_or_name_raises(self):
        """Missing owner/name raises."""
        with pytest.raises(ValueError, match="owner and name"):
            TargetRepository(owner="", name="repo", url="https://github.com/u/repo")


# ============================================================================
# Factory Configuration Tests
# ============================================================================

class TestFactoryConfig:
    """Test factory configuration with target repo."""

    def test_config_with_target_repo(self):
        """Factory config accepts target repository."""
        repo = TargetRepository(
            owner="acme",
            name="widgets",
            url="https://github.com/acme/widgets",
        )
        config = FactoryConfig(
            target_repo=repo,
            cloudflare_account_id="abc123",
            cloudflare_api_token="token_xyz",
        )

        assert config.target_repo.name == "widgets"
        assert config.validate_cloudflare_credentials() is True

    def test_config_without_credentials(self):
        """Config without Cloudflare credentials returns False."""
        repo = TargetRepository(
            owner="acme",
            name="widgets",
            url="https://github.com/acme/widgets",
        )
        config = FactoryConfig(target_repo=repo)

        assert config.validate_cloudflare_credentials() is False


# ============================================================================
# Target Repo Setup Tests
# ============================================================================

class TestTargetRepoSetup:
    """Test target repository setup and configuration."""

    def test_setup_initialization(self):
        """TargetRepoSetup initializes with config."""
        repo = TargetRepository(
            owner="test",
            name="repo",
            url="https://github.com/test/repo",
        )
        config = FactoryConfig(target_repo=repo)
        setup = TargetRepoSetup(config)

        assert setup.config.target_repo.repo_string == "test/repo"

    def test_configure_github_secrets_instructions(self, capsys):
        """Secret configuration generates user instructions."""
        repo = TargetRepository(
            owner="user",
            name="target",
            url="https://github.com/user/target",
        )
        config = FactoryConfig(target_repo=repo)
        setup = TargetRepoSetup(config)

        result = setup.configure_github_secrets(
            account_id="account_123",
            api_token="token_456",
        )

        assert result is True
        captured = capsys.readouterr()
        assert "user/target" in captured.out
        assert "gh secret set" in captured.out
        assert "CLOUDFLARE_ACCOUNT_ID" in captured.out
        assert "CLOUDFLARE_API_TOKEN" in captured.out


# ============================================================================
# Phase 13 Gate Test (Extended)
# ============================================================================

def test_phase13_gate_configurable_cloudflare_deployment():
    """
    Phase 13 Gate Extended: Configurable Cloudflare deployment (§15, target-agnostic).

    Verifies:
    - TargetRepository accepts any GitHub URL
    - FactoryConfig combines target repo + Cloudflare credentials
    - TargetRepoSetup provides user instructions (never executes secrets directly)
    - Cloudflare adapter (from test_phase13_cloudflare_deploy.py) stays
      repo-agnostic and reusable
    """

    # 1. User provides a target repo (any GitHub project)
    user_target_url = "https://github.com/acme-corp/my-service"
    target_repo = TargetRepository.from_url(user_target_url)

    assert target_repo.owner == "acme-corp"
    assert target_repo.name == "my-service"
    assert target_repo.repo_string == "acme-corp/my-service"

    # 2. Factory is configured with that repo + Cloudflare credentials
    config = FactoryConfig(
        target_repo=target_repo,
        cloudflare_account_id="[REDACTED]",
        cloudflare_api_token="[REDACTED]",
    )

    assert config.validate_cloudflare_credentials() is True

    # 3. Setup layer generates user instructions (doesn't execute secrets)
    setup = TargetRepoSetup(config)
    result = setup.configure_github_secrets(
        account_id="[REDACTED]",
        api_token="[REDACTED]",
    )
    assert result is True

    # 4. The Cloudflare adapter is repo-agnostic (from Phase 13 test)
    from factory.deploy.cloudflare_adapter import CloudflareAdapter

    adapter = CloudflareAdapter()
    assert_adapter_holds_no_secret(adapter)

    print("✓ Phase 13 Extended: Configurable Cloudflare deployment (target-repo-agnostic)")


def assert_adapter_holds_no_secret(adapter):
    """Guard from cloudflare_adapter_tests."""
    from factory.deploy.cloudflare_adapter import assert_adapter_holds_no_secret as guard

    guard(adapter)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for the factory profiles system (factory/profiles.py, master plan §17).

Covers:
1. TargetRepository parsing and validation
2. CloudflareProjectRef (secret-free)
3. Profile serialization round-trip
4. list_profiles / load_profile / save_profile / create_profile
5. resolve_active_profile precedence (explicit > env var > implicit single > error)
6. TargetRepoSetup integration (never executes secrets directly)
7. Gate: the same factory code manages multiple distinct profiles unmodified
"""

import os

import pytest

from factory.profiles import (
    CloudflareProjectRef,
    NoActiveProfileError,
    Profile,
    ProfileNotFoundError,
    TargetRepository,
    create_profile,
    list_profiles,
    load_profile,
    resolve_active_profile,
    save_profile,
)
from factory.deploy.target_repo_setup import TargetRepoSetup


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    """Isolate profile storage to a temp directory for each test."""
    import factory.profiles as profiles_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(profiles_module, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.delenv("FACTORY_PROFILE", raising=False)
    return tmp_path / "profiles"


# ============================================================================
# TargetRepository
# ============================================================================

class TestTargetRepository:
    def test_target_repo_creation(self):
        repo = TargetRepository(owner="myorg", name="myrepo", url="https://github.com/myorg/myrepo")
        assert repo.repo_string == "myorg/myrepo"

    def test_parse_github_url(self):
        repo = TargetRepository.from_url("https://github.com/user/project")
        assert repo.owner == "user"
        assert repo.name == "project"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="GitHub HTTPS"):
            TargetRepository.from_url("https://example.com/user/repo")

    def test_missing_owner_or_name_raises(self):
        with pytest.raises(ValueError, match="owner and name"):
            TargetRepository(owner="", name="repo", url="https://github.com/u/repo")


# ============================================================================
# CloudflareProjectRef (secret-free)
# ============================================================================

class TestCloudflareProjectRef:
    def test_holds_no_secret_fields(self):
        ref = CloudflareProjectRef(project_name="my-service")
        field_names = ref.__dataclass_fields__.keys()
        for name in field_names:
            assert "token" not in name.lower()
            assert "secret" not in name.lower()
            assert "account_id" not in name.lower()


# ============================================================================
# Profile serialization round-trip
# ============================================================================

class TestProfileSerialization:
    def test_round_trip(self):
        profile = Profile(
            name="acme",
            target_repo=TargetRepository.from_url("https://github.com/acme/widgets"),
            cloudflare=CloudflareProjectRef(project_name="widgets-prod"),
            business_requirements_source="github_issues",
            protected_paths=["custom/protected.md"],
            notes="example",
        )
        restored = Profile.from_yaml_dict(profile.to_yaml_dict())
        assert restored.name == profile.name
        assert restored.target_repo.repo_string == profile.target_repo.repo_string
        assert restored.cloudflare.project_name == "widgets-prod"
        assert restored.protected_paths == ["custom/protected.md"]

    def test_target_branch_and_verification_commands_default(self):
        """A profile built without these fields gets safe, documented defaults."""
        profile = Profile(name="acme", target_repo=TargetRepository.from_url("https://github.com/acme/widgets"))
        assert profile.target_branch == "main"
        assert profile.verification_commands == {}

    def test_target_branch_and_verification_commands_round_trip(self):
        profile = Profile(
            name="acme",
            target_repo=TargetRepository.from_url("https://github.com/acme/widgets"),
            target_branch="develop",
            verification_commands={"unit": ["pytest"], "lint": ["npm", "run", "lint"]},
        )
        restored = Profile.from_yaml_dict(profile.to_yaml_dict())
        assert restored.target_branch == "develop"
        assert restored.verification_commands == {"unit": ["pytest"], "lint": ["npm", "run", "lint"]}

    def test_from_yaml_dict_defaults_when_keys_missing(self):
        """Loading an older profile file (written before these fields existed) still works."""
        minimal = Profile(name="acme", target_repo=TargetRepository.from_url("https://github.com/acme/widgets")).to_yaml_dict()
        del minimal["target_branch"]
        del minimal["verification_commands"]
        restored = Profile.from_yaml_dict(minimal)
        assert restored.target_branch == "main"
        assert restored.verification_commands == {}


# ============================================================================
# Profile storage: list / load / save / create
# ============================================================================

class TestProfileStorage:
    def test_create_and_load(self, profiles_dir):
        created = create_profile(name="my-project", target_repo_url="https://github.com/acme/my-project")
        loaded = load_profile("my-project")
        assert loaded.target_repo.repo_string == "acme/my-project"
        assert created.target_repo.repo_string == loaded.target_repo.repo_string

    def test_list_profiles_empty(self, profiles_dir):
        assert list_profiles() == []

    def test_list_profiles_multiple(self, profiles_dir):
        create_profile(name="alpha", target_repo_url="https://github.com/acme/alpha")
        create_profile(name="beta", target_repo_url="https://github.com/acme/beta")
        assert list_profiles() == ["alpha", "beta"]

    def test_load_missing_profile_raises_with_hint(self, profiles_dir):
        create_profile(name="alpha", target_repo_url="https://github.com/acme/alpha")
        with pytest.raises(ProfileNotFoundError, match="alpha"):
            load_profile("does-not-exist")

    def test_save_profile_never_writes_secret_fields(self, profiles_dir):
        """Profiles have no field capable of holding a secret, by construction."""
        profile = Profile(name="x", target_repo=TargetRepository.from_url("https://github.com/a/b"))
        path = save_profile(profile)
        content = path.read_text()
        assert "token" not in content.lower()
        assert "secret" not in content.lower()

    def test_create_profile_passes_through_target_branch_and_verification_commands(self, profiles_dir):
        created = create_profile(
            name="my-project",
            target_repo_url="https://github.com/acme/my-project",
            target_branch="develop",
            verification_commands={"unit": ["pytest", "-q"]},
        )
        assert created.target_branch == "develop"
        assert created.verification_commands == {"unit": ["pytest", "-q"]}

        loaded = load_profile("my-project")
        assert loaded.target_branch == "develop"
        assert loaded.verification_commands == {"unit": ["pytest", "-q"]}

    def test_create_profile_defaults_target_branch_to_main(self, profiles_dir):
        created = create_profile(name="my-project", target_repo_url="https://github.com/acme/my-project")
        assert created.target_branch == "main"
        assert created.verification_commands == {}


# ============================================================================
# resolve_active_profile precedence
# ============================================================================

class TestResolveActiveProfile:
    def test_explicit_wins(self, profiles_dir):
        create_profile(name="alpha", target_repo_url="https://github.com/acme/alpha")
        create_profile(name="beta", target_repo_url="https://github.com/acme/beta")
        os.environ["FACTORY_PROFILE"] = "alpha"
        try:
            resolved = resolve_active_profile(explicit="beta")
            assert resolved.name == "beta"
        finally:
            del os.environ["FACTORY_PROFILE"]

    def test_env_var_used_when_no_explicit(self, profiles_dir):
        create_profile(name="alpha", target_repo_url="https://github.com/acme/alpha")
        create_profile(name="beta", target_repo_url="https://github.com/acme/beta")
        os.environ["FACTORY_PROFILE"] = "beta"
        try:
            resolved = resolve_active_profile()
            assert resolved.name == "beta"
        finally:
            del os.environ["FACTORY_PROFILE"]

    def test_implicit_single_profile(self, profiles_dir):
        create_profile(name="only-one", target_repo_url="https://github.com/acme/only-one")
        resolved = resolve_active_profile()
        assert resolved.name == "only-one"

    def test_no_profiles_raises(self, profiles_dir):
        with pytest.raises(NoActiveProfileError, match="none exist"):
            resolve_active_profile()

    def test_multiple_profiles_without_selection_raises(self, profiles_dir):
        create_profile(name="alpha", target_repo_url="https://github.com/acme/alpha")
        create_profile(name="beta", target_repo_url="https://github.com/acme/beta")
        with pytest.raises(NoActiveProfileError, match="Multiple profiles"):
            resolve_active_profile()


# ============================================================================
# TargetRepoSetup integration
# ============================================================================

class TestTargetRepoSetup:
    def test_setup_initialization(self, profiles_dir):
        profile = create_profile(name="test-project", target_repo_url="https://github.com/test/repo")
        setup = TargetRepoSetup(profile)
        assert setup.profile.target_repo.repo_string == "test/repo"

    def test_configure_github_secrets_instructions(self, profiles_dir, capsys):
        profile = create_profile(name="target", target_repo_url="https://github.com/user/target")
        setup = TargetRepoSetup(profile)

        result = setup.configure_github_secrets(account_id="account_123", api_token="token_456")

        assert result is True
        captured = capsys.readouterr()
        assert "user/target" in captured.out
        assert "gh secret set" in captured.out
        assert "CLOUDFLARE_ACCOUNT_ID" in captured.out
        assert "CLOUDFLARE_API_TOKEN" in captured.out


# ============================================================================
# Gate: multi-project reuse
# ============================================================================

def test_profiles_gate_multi_project_reuse():
    """
    Gate: the same unmodified factory code manages N distinct profiles.

    Verifies:
    - Two unrelated projects can each have their own profile
    - Each profile's TargetRepoSetup is independent (no shared/leaked state)
    - The Cloudflare adapter remains repo-agnostic (Phase 13 invariant holds)
    - No secret-shaped field exists anywhere on Profile/TargetRepository/CloudflareProjectRef
    """
    import tempfile
    from pathlib import Path

    import factory.profiles as profiles_module

    original_dir = profiles_module.PROFILES_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            profiles_module.PROFILES_DIR = Path(tmp) / "profiles"

            project_a = create_profile(name="project-a", target_repo_url="https://github.com/acme-corp/service-a")
            project_b = create_profile(name="project-b", target_repo_url="https://github.com/other-org/service-b")

            assert project_a.target_repo.repo_string != project_b.target_repo.repo_string

            setup_a = TargetRepoSetup(project_a)
            setup_b = TargetRepoSetup(project_b)
            assert setup_a.profile.name != setup_b.profile.name

            from factory.deploy.cloudflare_adapter import CloudflareAdapter, assert_adapter_holds_no_secret

            adapter = CloudflareAdapter()
            assert_adapter_holds_no_secret(adapter)

            for dataclass_type in (Profile, TargetRepository, CloudflareProjectRef):
                for field_name in dataclass_type.__dataclass_fields__.keys():
                    assert "token" not in field_name.lower()
                    assert "api_key" not in field_name.lower()
    finally:
        profiles_module.PROFILES_DIR = original_dir

    print("✓ Profiles gate: factory reused unmodified across multiple distinct projects")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

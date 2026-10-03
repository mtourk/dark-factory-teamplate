"""
Factory profiles: per-managed-project configuration (master plan §17).

The Dark Factory is built ONCE as a reusable template/engine. Every concrete
piece of work — "take these business requirements, implement them against
this GitHub repo, deploy to this Cloudflare project" — is described by a
*profile*, not by anything hardcoded in factory orchestration code.

A profile is a small, secret-free YAML file under `profiles/<name>.yml`. It
is safe to commit: it names a target repository and (optionally) a Cloudflare
project reference, but it never holds credentials. Credentials for a given
profile's target repository live ONLY as GitHub Actions repository secrets on
that target repository (see factory/deploy/target_repo_setup.py) — never in
a profile file, never centrally in this factory repo, never read by local
factory processes.

Typical lifecycle:
    factory profile create my-project --repo https://github.com/acme/my-project
    factory --profile my-project feature "Add ROI calculator"
    factory --profile my-project run

Profile selection precedence (resolve_active_profile):
    1. Explicit `--profile <name>` CLI argument
    2. FACTORY_PROFILE environment variable
    3. If exactly one profile exists under profiles/, use it implicitly
    4. Otherwise, fail with a clear error listing available profiles
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

PROFILES_DIR = Path("profiles")

FACTORY_PROFILE_ENV_VAR = "FACTORY_PROFILE"


class ProfileNotFoundError(Exception):
    """Raised when a named profile does not exist on disk."""


class NoActiveProfileError(Exception):
    """Raised when no profile can be resolved unambiguously (see resolve_active_profile)."""


@dataclass
class TargetRepository:
    """The GitHub repository a profile's work is implemented and shipped against."""

    owner: str
    name: str
    url: str

    def __post_init__(self):
        if not self.owner or not self.name:
            raise ValueError("owner and name are required")
        if not self.url.startswith("https://github.com/"):
            raise ValueError("url must be a GitHub HTTPS URL")

    @property
    def repo_string(self) -> str:
        """GitHub CLI format: owner/name."""
        return f"{self.owner}/{self.name}"

    @classmethod
    def from_url(cls, url: str) -> "TargetRepository":
        """Parse a GitHub HTTPS URL (https://github.com/<owner>/<name>) into a TargetRepository."""
        if not url.startswith("https://github.com/"):
            raise ValueError("Must be a GitHub HTTPS URL")
        parts = url.rstrip("/").split("/")
        if len(parts) < 5:
            raise ValueError("Invalid GitHub URL format")
        owner, name = parts[-2], parts[-1]
        return cls(owner=owner, name=name, url=url)

    def to_dict(self) -> Dict[str, str]:
        return {"owner": self.owner, "name": self.name, "url": self.url}


@dataclass
class CloudflareProjectRef:
    """
    Non-secret Cloudflare project reference for a profile.

    Deliberately holds no credentials. Account ID and API Token are supplied
    at setup time (factory/deploy/target_repo_setup.py) and injected directly
    into the target repo's GitHub Actions secrets; they are never persisted
    into a profile file.
    """

    project_name: Optional[str] = None
    preview_url: Optional[str] = None
    production_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "project_name": self.project_name,
            "preview_url": self.preview_url,
            "production_url": self.production_url,
        }


@dataclass
class Profile:
    """
    One managed project: a target repository plus the project-specific
    configuration the factory needs to implement and deploy requirements
    against it.
    """

    name: str
    target_repo: TargetRepository
    cloudflare: CloudflareProjectRef = field(default_factory=CloudflareProjectRef)
    business_requirements_source: Optional[str] = None
    protected_paths: List[str] = field(default_factory=list)
    notes: str = ""

    def to_yaml_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "target_repo": self.target_repo.to_dict(),
            "cloudflare": self.cloudflare.to_dict(),
            "business_requirements_source": self.business_requirements_source,
            "protected_paths": self.protected_paths,
            "notes": self.notes,
        }

    @classmethod
    def from_yaml_dict(cls, data: Dict[str, Any]) -> "Profile":
        target_repo_data = data.get("target_repo") or {}
        cloudflare_data = data.get("cloudflare") or {}
        return cls(
            name=data["name"],
            target_repo=TargetRepository(
                owner=target_repo_data.get("owner", ""),
                name=target_repo_data.get("name", ""),
                url=target_repo_data.get("url", ""),
            ),
            cloudflare=CloudflareProjectRef(
                project_name=cloudflare_data.get("project_name"),
                preview_url=cloudflare_data.get("preview_url"),
                production_url=cloudflare_data.get("production_url"),
            ),
            business_requirements_source=data.get("business_requirements_source"),
            protected_paths=data.get("protected_paths") or [],
            notes=data.get("notes", ""),
        )


def _profile_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.yml"


def list_profiles() -> List[str]:
    """List names of all profiles under profiles/."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yml"))


def load_profile(name: str) -> Profile:
    """Load a profile by name from profiles/<name>.yml."""
    path = _profile_path(name)
    if not path.exists():
        available = list_profiles()
        hint = f" Available profiles: {', '.join(available)}" if available else " No profiles exist yet."
        raise ProfileNotFoundError(f"Profile '{name}' not found at {path}.{hint}")

    with open(path) as f:
        data = yaml.safe_load(f)
    return Profile.from_yaml_dict(data)


def save_profile(profile: Profile) -> Path:
    """Persist a profile to profiles/<name>.yml. Never writes secrets."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = _profile_path(profile.name)
    with open(path, "w") as f:
        yaml.dump(profile.to_yaml_dict(), f, default_flow_style=False, sort_keys=False)
    return path


def create_profile(
    name: str,
    target_repo_url: str,
    cloudflare_project_name: Optional[str] = None,
    business_requirements_source: Optional[str] = None,
    protected_paths: Optional[List[str]] = None,
    notes: str = "",
) -> Profile:
    """Convenience constructor: build a Profile from a GitHub URL and persist it."""
    profile = Profile(
        name=name,
        target_repo=TargetRepository.from_url(target_repo_url),
        cloudflare=CloudflareProjectRef(project_name=cloudflare_project_name),
        business_requirements_source=business_requirements_source,
        protected_paths=protected_paths or [],
        notes=notes,
    )
    save_profile(profile)
    return profile


def resolve_active_profile(explicit: Optional[str] = None) -> Profile:
    """
    Resolve which profile the current factory invocation should run against.

    Precedence:
      1. `explicit` (e.g. the --profile CLI flag)
      2. FACTORY_PROFILE environment variable
      3. Exactly one profile exists on disk -> use it
      4. Otherwise -> NoActiveProfileError
    """
    import os

    name = explicit or os.environ.get(FACTORY_PROFILE_ENV_VAR)
    if name:
        return load_profile(name)

    available = list_profiles()
    if len(available) == 1:
        return load_profile(available[0])
    if not available:
        raise NoActiveProfileError(
            "No profile specified and none exist yet. Create one with "
            "'factory profile create <name> --repo <github-url>'."
        )
    raise NoActiveProfileError(
        f"Multiple profiles exist ({', '.join(available)}); specify one with "
        f"--profile <name> or the {FACTORY_PROFILE_ENV_VAR} environment variable."
    )

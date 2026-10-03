"""Factory configuration and target repository management."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TargetRepository:
    """Configuration for the target repository the factory manages."""

    owner: str  # GitHub user/org
    name: str  # repo name
    url: str  # Full HTTPS URL, e.g. https://github.com/user/repo

    def __post_init__(self):
        # Basic validation
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
        """Parse a GitHub HTTPS URL into owner/name."""
        # https://github.com/user/repo -> owner=user, name=repo
        if not url.startswith("https://github.com/"):
            raise ValueError("Must be a GitHub HTTPS URL")
        parts = url.rstrip("/").split("/")
        if len(parts) < 5:
            raise ValueError("Invalid GitHub URL format")
        owner, name = parts[-2], parts[-1]
        return cls(owner=owner, name=name, url=url)


@dataclass
class FactoryConfig:
    """Dark Factory runtime configuration."""

    target_repo: TargetRepository
    cloudflare_account_id: Optional[str] = None
    cloudflare_api_token: Optional[str] = None

    def validate_cloudflare_credentials(self) -> bool:
        """Check that Cloudflare credentials are provided for production deploy."""
        return bool(self.cloudflare_account_id and self.cloudflare_api_token)

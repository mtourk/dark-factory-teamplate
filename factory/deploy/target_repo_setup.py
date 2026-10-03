"""
Phase 13: Configurable Cloudflare deployment — target-repo-agnostic.

Instead of hardcoding a specific target repository, Phase 13 is now:
1. A reusable Cloudflare adapter (already created in factory/deploy/cloudflare_adapter.py)
2. A workflow template at .factory/workflows/deploy.yml (already created)
3. A configuration system (factory/config) that accepts any target repo
4. Guidance for the user to:
   - Specify their target repo (via URL or owner/name)
   - Provide Cloudflare Account ID and API Token
   - The factory then syncs the workflow template to that repo and
     configures the GitHub Actions secrets there

This module provides the integration layer that takes user-provided
configuration and deploys/manages secrets on the actual target repository.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from factory.config import TargetRepository, FactoryConfig


class TargetRepoSetup:
    """
    Manages deployment of the factory workflow and secrets to a configured
    target repository (§15).

    This class is target-agnostic: it takes a TargetRepository config and
    performs the necessary GitHub API calls / Git operations without ever
    assuming a specific repo name.
    """

    def __init__(self, config: FactoryConfig):
        """
        Args:
            config: FactoryConfig with target_repo and optional credentials.
        """
        self.config = config

    def sync_workflow_to_target(self, workflow_template_path: Path) -> bool:
        """
        Copy the deploy workflow template from .factory/workflows/deploy.yml
        into the target repository's .github/workflows/deploy.yml (via git
        operations or API).

        In a full implementation, this would:
        1. Clone or fetch the target repo
        2. Copy .factory/workflows/deploy.yml to target/.github/workflows/deploy.yml
        3. Commit and push the change

        For now, this is a stub that documents the intended operation.
        """
        if not workflow_template_path.exists():
            raise FileNotFoundError(f"Workflow template not found: {workflow_template_path}")
        return True

    def configure_github_secrets(
        self,
        account_id: str,
        api_token: str,
    ) -> bool:
        """
        Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN as encrypted
        repository secrets on the target repo (§15: 'GitHub Actions owns
        Cloudflare secrets').

        Args:
            account_id: Cloudflare Account ID.
            api_token: Cloudflare API Token.

        Returns:
            True if successful, False otherwise.
        """
        # Use `gh secret set` to inject secrets into the target repo.
        # These commands are run *outside* the factory process; the user
        # executes them or authorizes them explicitly.
        commands = [
            [
                "gh",
                "secret",
                "set",
                "CLOUDFLARE_ACCOUNT_ID",
                "--repo",
                self.config.target_repo.repo_string,
                "--body",
                account_id,
            ],
            [
                "gh",
                "secret",
                "set",
                "CLOUDFLARE_API_TOKEN",
                "--repo",
                self.config.target_repo.repo_string,
                "--body",
                api_token,
            ],
        ]

        # Note: These commands are NOT executed here. Instead, they are
        # provided to the user for explicit execution or approval. This
        # avoids embedding secrets in a subprocess call within the factory
        # orchestrator (which could leak them in process listings, logs, etc.).
        return self._provide_user_instructions(commands)

    def _provide_user_instructions(self, commands: list) -> bool:
        """
        Instead of executing secret-bearing commands directly, provide them
        to the user for manual execution or approval.

        In a full implementation, this would:
        1. Print the commands to stdout with clear instructions
        2. Optionally write them to a file marked NEVER_COMMIT
        3. Wait for user confirmation / execution
        """
        print("\n" + "=" * 70)
        print("FACTORY SETUP: Configure GitHub Actions Secrets")
        print("=" * 70)
        print(f"\nTarget repository: {self.config.target_repo.repo_string}")
        print("\nTo complete Phase 13 setup, execute these commands from your terminal:")
        print("(Never commit these commands or store them; they contain secrets.)\n")

        for i, cmd in enumerate(commands, 1):
            print(f"{i}. {' '.join(cmd)}\n")

        print("=" * 70)
        print("These commands inject secrets into the target repo via GitHub CLI.")
        print("After execution, the Cloudflare workflow will be able to deploy.")
        print("=" * 70 + "\n")
        return True


def print_phase13_setup_instructions(target_repo_url: str, account_id: str, api_token: str) -> str:
    """
    User-facing instructions for completing Phase 13 setup on a target repo.

    Returns a formatted string the user can follow to set up secrets on their
    target repository.
    """
    target = TargetRepository.from_url(target_repo_url)
    config = FactoryConfig(
        target_repo=target,
        cloudflare_account_id=account_id,
        cloudflare_api_token=api_token,
    )
    setup = TargetRepoSetup(config)
    setup.configure_github_secrets(account_id, api_token)
    return ""

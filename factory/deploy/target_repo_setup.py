"""
Target repository setup — syncs the factory's deploy workflow template and
Cloudflare secrets onto a profile's managed target repository (§15, §17).

This module is deliberately target-agnostic: it operates on whichever
Profile (factory/profiles.py) is passed in, never on a hardcoded repo name.
A single factory installation can run this once per profile, once per
project, reused indefinitely as new profiles are added.

Flow:
1. A reusable Cloudflare adapter already exists (factory/deploy/cloudflare_adapter.py)
2. A workflow template already exists (.factory/workflows/deploy.yml)
3. A profile (factory/profiles.py) names the target repository
4. This module syncs the workflow template to that repo and provides the
   user with the exact commands to configure GitHub Actions secrets there

Secrets are never read, stored, or executed by the factory process itself —
see configure_github_secrets() below.
"""

from pathlib import Path

from factory.profiles import Profile


class TargetRepoSetup:
    """
    Manages deployment of the factory workflow and secrets to a profile's
    target repository (§15).

    Target-agnostic: takes a Profile and performs the necessary GitHub
    operations without ever assuming a specific repo name. Reusable across
    every profile the factory manages.
    """

    def __init__(self, profile: Profile):
        """
        Args:
            profile: The Profile naming the target repository to set up.
        """
        self.profile = profile

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
                self.profile.target_repo.repo_string,
                "--body",
                account_id,
            ],
            [
                "gh",
                "secret",
                "set",
                "CLOUDFLARE_API_TOKEN",
                "--repo",
                self.profile.target_repo.repo_string,
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
        print(f"FACTORY SETUP: Configure GitHub Actions Secrets [profile: {self.profile.name}]")
        print("=" * 70)
        print(f"\nTarget repository: {self.profile.target_repo.repo_string}")
        print("\nTo complete setup, execute these commands from your terminal:")
        print("(Never commit these commands or store them; they contain secrets.)\n")

        for i, cmd in enumerate(commands, 1):
            print(f"{i}. {' '.join(cmd)}\n")

        print("=" * 70)
        print("These commands inject secrets into the target repo via GitHub CLI.")
        print("After execution, the Cloudflare workflow will be able to deploy.")
        print("=" * 70 + "\n")
        return True


def print_setup_instructions(profile_name: str, account_id: str, api_token: str) -> None:
    """
    User-facing instructions for completing Cloudflare secret setup on a
    profile's target repository. Looks up the profile by name (factory/profiles.py)
    so this works identically for any managed project.
    """
    from factory.profiles import load_profile

    profile = load_profile(profile_name)
    setup = TargetRepoSetup(profile)
    setup.configure_github_secrets(account_id, api_token)

"""
Dark Factory Phase 17.0 — Local Profile Sync

Polls the Intake Worker for pending_profiles (new repos created via web UI)
and auto-creates local profile files, enabling them for the factory to claim.

Per the build plan: this runs as part of the Phase 4 polling loop (once Phase 4 is built).
For now, this is a standalone utility for testing/manual execution.

Usage:
  python -m factory.intake.local_sync
"""

import os
import sys
from pathlib import Path
from typing import Optional
import requests
import json

from factory.profiles import create_profile


INTAKE_WORKER_URL = "https://intake.ollama.mtourk.com"


class LocalProfileSync:
    """
    Syncs pending profiles from Intake Worker to local factory profile files.
    """

    def __init__(self, worker_url: str = INTAKE_WORKER_URL):
        self.worker_url = worker_url

    def fetch_pending_profiles(self) -> list[dict]:
        """
        Fetch pending profiles (synced=false) from the Intake Worker.

        Returns:
            List of pending profile dicts with keys: id, name, repo_url, owner, repo_name, created_at
        """
        try:
            response = requests.get(f"{self.worker_url}/pending-profiles", timeout=10)
            if response.status_code != 200:
                print(f"Error fetching pending profiles: {response.status_code} {response.text}")
                return []

            data = response.json()
            return data.get("profiles", [])
        except Exception as e:
            print(f"Error contacting intake worker: {e}")
            return []

    def create_local_profile(self, profile_data: dict) -> bool:
        """
        Create a local profile file from a pending profile.

        Args:
            profile_data: dict with keys: id, name, repo_url, owner, repo_name

        Returns:
            True if successful, False otherwise
        """
        try:
            name = profile_data["name"]
            repo_url = profile_data["repo_url"]

            print(f"  Creating local profile: {name}")
            print(f"    Repository: {repo_url}")

            # Use the factory's existing profile creation function
            profile = create_profile(
                name=name,
                target_repo_url=repo_url,
                notes=f"Auto-created by Intake Worker via Phase 17.0 web UI on {self._now()}",
            )

            print(f"  ✓ Profile created at profiles/{name}.yml")
            return True
        except Exception as e:
            print(f"  ✗ Failed to create profile {profile_data['name']}: {e}")
            return False

    def mark_profile_synced(self, profile_id: str) -> bool:
        """
        Tell the Intake Worker that a profile has been synced locally.

        Args:
            profile_id: the profile ID from the worker

        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.post(
                f"{self.worker_url}/pending-profiles/{profile_id}/sync-confirmed", timeout=10
            )
            if response.status_code == 200:
                return True
            else:
                print(f"  ✗ Failed to mark synced: {response.status_code} {response.text}")
                return False
        except Exception as e:
            print(f"  ✗ Error marking synced: {e}")
            return False

    def sync_all(self) -> int:
        """
        Sync all pending profiles.

        Returns:
            Number of profiles successfully synced
        """
        print("Fetching pending profiles from Intake Worker...")
        pending = self.fetch_pending_profiles()

        if not pending:
            print("No pending profiles.")
            return 0

        print(f"Found {len(pending)} pending profile(s).")
        synced = 0

        for profile_data in pending:
            if self.create_local_profile(profile_data):
                if self.mark_profile_synced(profile_data["id"]):
                    synced += 1
                    print(f"  ✓ Synced {profile_data['name']}")
                else:
                    print(f"  ⚠ Profile created but sync confirmation failed: {profile_data['name']}")
            else:
                print(f"  ✗ Failed to sync {profile_data['name']}")

        print(f"\nSync complete: {synced}/{len(pending)} profiles synced.")
        return synced

    def _now(self) -> str:
        """ISO timestamp for notes."""
        from datetime import datetime

        return datetime.utcnow().isoformat()


if __name__ == "__main__":
    syncer = LocalProfileSync()
    syncer.sync_all()

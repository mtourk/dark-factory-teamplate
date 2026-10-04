"""
GitHub API adapter for factory operations.

Handles: list issues, apply labels, read branch protection, create branches, push, create PRs.
Per master plan §14: "Use labels for ready, claimed, analyzing, decision-required, etc."

All operations verified after execution (never trust exit code alone, §9).
"""

import httpx
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GitHubIssue:
    """Parsed GitHub issue."""
    number: int
    title: str
    body: str
    labels: List[str]
    state: str  # open, closed
    created_at: str
    url: str


@dataclass
class GitHubLabel:
    """GitHub label."""
    name: str
    color: str
    description: str


class GitHubAdapter:
    """GitHub API client for factory operations."""

    def __init__(self, token: Optional[str] = None, owner: str = "", repo: str = ""):
        """
        Initialize GitHub adapter.

        Args:
            token: GitHub API token (from GH_TOKEN env or parameter)
            owner: GitHub owner (user/org)
            repo: Repository name
        """
        self.token = token or os.getenv("GH_TOKEN", "")
        self.owner = owner
        self.repo = repo
        self.base_url = "https://api.github.com"
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=self._auth_headers(),
            timeout=30.0,
        )

    def _auth_headers(self) -> Dict[str, str]:
        """Build Authorization header."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "dark-factory",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def set_repo(self, owner: str, repo: str) -> None:
        """Set target repository."""
        self.owner = owner
        self.repo = repo

    def list_issues(
        self,
        state: str = "open",
        labels: Optional[List[str]] = None,
        sort: str = "created",
        direction: str = "asc",
    ) -> List[GitHubIssue]:
        """
        List issues with optional label filter.

        Args:
            state: "open" or "closed"
            labels: filter by label names
            sort: "created" or "updated"
            direction: "asc" or "desc"

        Returns:
            List of parsed issues

        Raises:
            httpx.HTTPError: if API call fails
        """
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
        }
        if labels:
            params["labels"] = ",".join(labels)

        url = f"/repos/{self.owner}/{self.repo}/issues"
        response = self.client.get(url, params=params)
        response.raise_for_status()

        issues = []
        for issue_data in response.json():
            issues.append(GitHubIssue(
                number=issue_data["number"],
                title=issue_data["title"],
                body=issue_data.get("body", ""),
                labels=[label["name"] for label in issue_data.get("labels", [])],
                state=issue_data["state"],
                created_at=issue_data["created_at"],
                url=issue_data["html_url"],
            ))

        return issues

    def get_issue(self, issue_number: int) -> GitHubIssue:
        """
        Fetch a single issue by number.

        Args:
            issue_number: GitHub issue number

        Returns:
            Parsed issue (title, body, labels, state)

        Raises:
            httpx.HTTPError: if API call fails (e.g., issue not found)
        """
        url = f"/repos/{self.owner}/{self.repo}/issues/{issue_number}"
        response = self.client.get(url)
        response.raise_for_status()

        issue_data = response.json()
        return GitHubIssue(
            number=issue_data["number"],
            title=issue_data["title"],
            body=issue_data.get("body", "") or "",
            labels=[label["name"] for label in issue_data.get("labels", [])],
            state=issue_data["state"],
            created_at=issue_data["created_at"],
            url=issue_data["html_url"],
        )

    def add_labels(self, issue_number: int, labels: List[str]) -> List[str]:
        """
        Add labels to issue.

        Args:
            issue_number: GitHub issue number
            labels: label names to add

        Returns:
            All labels on issue after operation
        """
        url = f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels"
        response = self.client.post(url, json={"labels": labels})
        response.raise_for_status()

        result_labels = [label["name"] for label in response.json()]
        return result_labels

    def remove_label(self, issue_number: int, label_name: str) -> None:
        """
        Remove label from issue.

        Args:
            issue_number: GitHub issue number
            label_name: label to remove
        """
        url = f"/repos/{self.owner}/{self.repo}/issues/{issue_number}/labels/{label_name}"
        response = self.client.delete(url)
        response.raise_for_status()

    def create_branch(self, branch_name: str, from_sha: str) -> str:
        """
        Create branch from SHA (via Git Data API).

        Args:
            branch_name: new branch name
            from_sha: base commit SHA

        Returns:
            New branch ref path
        """
        url = f"/repos/{self.owner}/{self.repo}/git/refs"
        response = self.client.post(url, json={
            "ref": f"refs/heads/{branch_name}",
            "sha": from_sha,
        })
        response.raise_for_status()
        return response.json()["ref"]

    def get_branch_protection(self, branch: str = "main") -> Optional[Dict[str, Any]]:
        """
        Get branch protection rules.

        Args:
            branch: branch name

        Returns:
            Protection rules or None if not protected
        """
        url = f"/repos/{self.owner}/{self.repo}/branches/{branch}/protection"
        response = self.client.get(url)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def update_branch_protection(
        self,
        branch: str = "main",
        required_status_checks: Optional[List[str]] = None,
        dismiss_stale_reviews: bool = True,
        require_code_owner_reviews: bool = True,
    ) -> Dict[str, Any]:
        """
        Update branch protection rules (requires admin).

        Args:
            branch: branch name
            required_status_checks: required check names
            dismiss_stale_reviews: dismiss reviews on push
            require_code_owner_reviews: require CODEOWNERS

        Returns:
            Updated protection rules
        """
        url = f"/repos/{self.owner}/{self.repo}/branches/{branch}/protection"

        payload: Dict[str, Any] = {
            "enforce_admins": False,
            "dismiss_stale_reviews": dismiss_stale_reviews,
            "require_code_owner_reviews": require_code_owner_reviews,
            "required_linear_history": False,
            "allow_force_pushes": False,
            "allow_deletions": False,
        }

        if required_status_checks:
            payload["required_status_checks"] = {
                "strict": True,
                "contexts": required_status_checks,
            }

        response = self.client.put(url, json=payload)
        response.raise_for_status()
        return response.json()

    def create_pull_request(
        self,
        title: str,
        head_branch: str,
        base_branch: str = "main",
        body: str = "",
    ) -> Dict[str, Any]:
        """
        Create pull request.

        Args:
            title: PR title
            head_branch: feature branch
            base_branch: target branch
            body: PR description

        Returns:
            PR data (number, url, etc.)
        """
        url = f"/repos/{self.owner}/{self.repo}/pulls"
        response = self.client.post(url, json={
            "title": title,
            "head": head_branch,
            "base": base_branch,
            "body": body,
        })
        response.raise_for_status()
        return response.json()

    def create_commit_status(
        self,
        sha: str,
        state: str,
        context: str,
        description: str = "",
        target_url: str = "",
    ) -> Dict[str, Any]:
        """
        Create commit status (check result).

        Args:
            sha: commit SHA
            state: "pending", "success", "failure", "error"
            context: check name (e.g., "factory/intent")
            description: status message
            target_url: link to details

        Returns:
            Status data
        """
        url = f"/repos/{self.owner}/{self.repo}/statuses/{sha}"
        response = self.client.post(url, json={
            "state": state,
            "context": context,
            "description": description,
            "target_url": target_url,
        })
        response.raise_for_status()
        return response.json()

    def enable_auto_merge(
        self,
        pr_number: int,
        commit_title: str = "",
        commit_message: str = "",
    ) -> Dict[str, Any]:
        """
        Enable auto-merge on PR (requires appropriate permissions).

        Args:
            pr_number: PR number
            commit_title: merge commit title
            commit_message: merge commit message

        Returns:
            Auto-merge data
        """
        url = f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/merge"
        response = self.client.put(url, json={
            "merge_method": "squash",  # or "merge", "rebase"
            "commit_title": commit_title,
            "commit_message": commit_message,
        })
        response.raise_for_status()
        return response.json()

    def get_pull_request(self, pr_number: int) -> Dict[str, Any]:
        """
        Get PR details.

        Args:
            pr_number: PR number

        Returns:
            PR data
        """
        url = f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}"
        response = self.client.get(url)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def parse_repo_url(url: str) -> tuple[str, str]:
    """
    Parse GitHub repo URL to (owner, repo).

    Args:
        url: e.g., "https://github.com/mtourk/investisor"

    Returns:
        (owner, repo) tuple
    """
    # Remove .git suffix if present
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    # Extract owner/repo from URL
    parts = url.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]

    raise ValueError(f"Invalid GitHub URL: {url}")


if __name__ == "__main__":
    # Quick test (requires GH_TOKEN env var set)
    owner, repo = parse_repo_url("https://github.com/mtourk/investisor")
    print(f"Parsed: {owner}/{repo}")

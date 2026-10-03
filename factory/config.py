"""
Configuration management for FactoryFlow.

Loads YAML workflow definitions and project config.
Per master plan §3: "Use YAML workflow definition."
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from factory.models import Workflow


CONFIG_DIR = Path(".factory/config")


def load_workflow_yaml(workflow_name: str) -> Dict[str, Any]:
    """
    Load workflow YAML from .factory/config/workflows/

    Args:
        workflow_name: e.g., "issue-to-pr" loads "workflows/issue-to-pr.yml"

    Returns:
        Parsed YAML as dictionary

    Raises:
        FileNotFoundError: if workflow not found
        yaml.YAMLError: if YAML is invalid
    """
    workflow_path = CONFIG_DIR / "workflows" / f"{workflow_name}.yml"

    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow not found: {workflow_path}")

    with open(workflow_path) as f:
        workflow_dict = yaml.safe_load(f)

    return workflow_dict


def validate_workflow(workflow_dict: Dict[str, Any]) -> Workflow:
    """
    Validate workflow YAML against schema (Pydantic).

    Args:
        workflow_dict: parsed YAML

    Returns:
        Validated Workflow model

    Raises:
        pydantic.ValidationError: if schema violation
    """
    return Workflow(**workflow_dict)


def load_and_validate_workflow(workflow_name: str) -> Workflow:
    """Load and validate workflow in one call."""
    workflow_dict = load_workflow_yaml(workflow_name)
    return validate_workflow(workflow_dict)


def load_project_config() -> Dict[str, Any]:
    """
    Load project configuration from .factory/config/project.yml

    Contains:
    - GitHub repo URL
    - Target branch
    - Model selections
    - Context token limits
    - Backlog scheduling policy
    """
    config_path = CONFIG_DIR / "project.yml"

    if not config_path.exists():
        # Return defaults
        return {
            "project_id": "unknown",
            "github_repo": "",
            "target_branch": "main",
            "model_alias": "qwen2.5-coder:32b",
            "max_context_tokens": 8192,
        }

    with open(config_path) as f:
        return yaml.safe_load(f)


def save_project_config(config: Dict[str, Any]) -> None:
    """Save project configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = CONFIG_DIR / "project.yml"

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_workflow_names() -> list[str]:
    """List available workflows in .factory/config/workflows/"""
    workflows_dir = CONFIG_DIR / "workflows"
    if not workflows_dir.exists():
        return []

    return [f.stem for f in workflows_dir.glob("*.yml")]


def load_config() -> Dict[str, Any]:
    """
    Load factory-wide runtime configuration (project config).

    Back-compat alias for load_project_config(), used by the CLI (factory/cli.py)
    for generic diagnostics that are not tied to a specific managed project.
    See factory/profiles.py for the per-managed-project ("profile") configuration
    that this factory template reuses across multiple target repositories.
    """
    return load_project_config()


if __name__ == "__main__":
    # Test config loading
    try:
        config = load_project_config()
        print(f"Project config: {config}")
    except Exception as e:
        print(f"Config loading: {e}")

"""
Patch application: write BuilderOutput.changes to disk.

Per master plan §10/§12: the builder/repairer only ever *proposes* changes
(path -> full file content). Applying them to the working tree is a
separate, deliberately dumb step so the "did this touch a prohibited path"
check (already done by `BuilderCoordinator.validate_builder_output`) is the
single source of truth for what's allowed to land — this module does not
re-derive that policy, it just refuses to write anything that wasn't already
validated.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class ApplyResult:
    """Result of applying a set of changes to disk."""
    written_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def apply_changes(
    repo_root: Path,
    changes: Dict[str, str],
    allowed_files: List[str],
) -> ApplyResult:
    """
    Write each path -> content pair in `changes` to disk under `repo_root`.

    Args:
        repo_root: repository working tree root (absolute path)
        changes: path (relative to repo_root) -> full file content
        allowed_files: the subset of `changes` keys that already passed
            `BuilderCoordinator.validate_builder_output` (no prohibited/sealed
            paths). Any key not in this list is skipped, not written — this
            is a defense-in-depth check, not the primary enforcement point.

    Returns:
        ApplyResult with written/skipped files and any write errors.
    """
    result = ApplyResult()
    allowed = set(allowed_files)

    for rel_path, content in changes.items():
        if rel_path not in allowed:
            result.skipped_files.append(rel_path)
            continue

        try:
            target = (repo_root / rel_path).resolve()
            # Refuse to write outside repo_root (e.g. "../../etc/passwd").
            if repo_root.resolve() not in target.parents and target != repo_root.resolve():
                result.errors[rel_path] = "Resolved path escapes repo_root"
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            result.written_files.append(rel_path)
        except OSError as e:
            result.errors[rel_path] = str(e)

    return result

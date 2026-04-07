"""ADR0094 AI-assisted approval and promotion helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def resolve_approvals(
    *,
    candidates: list[dict[str, Any]],
    approve_all: bool,
    approve_paths: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    approved: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        logical_path = str(row.get("path", "")).strip()
        if not logical_path:
            rejected.append(row)
            continue
        allowed = approve_all or logical_path in approve_paths
        if allowed:
            approved.append(row)
        else:
            rejected.append(row)
    return approved, rejected


def promote_approved_candidates(
    *,
    repo_root: Path,
    approved: list[dict[str, Any]],
) -> list[dict[str, str]]:
    promoted: list[dict[str, str]] = []
    for row in approved:
        logical_path = str(row["path"])
        candidate_path = Path(str(row["candidate_path"])).resolve()
        metadata_path = Path(str(row["metadata_path"])).resolve()
        target_path = (repo_root.resolve() / logical_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate_path, target_path)

        promoted_metadata = target_path.with_suffix(target_path.suffix + ".ai-metadata.json")
        if metadata_path.exists():
            promoted_metadata.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(metadata_path, promoted_metadata)
        promoted.append(
            {
                "path": logical_path,
                "target_path": str(target_path),
                "metadata_path": str(promoted_metadata),
            }
        )
    return promoted


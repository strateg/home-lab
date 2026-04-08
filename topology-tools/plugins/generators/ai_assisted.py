"""ADR0094 AI-assisted candidate helpers."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any


def validate_candidate_path(*, project_id: str, artifact_path: str) -> tuple[bool, str]:
    token = artifact_path.strip()
    if not token:
        return False, "path is empty"
    if token.startswith("/"):
        return False, "absolute paths are not allowed"
    parts = Path(token).parts
    if any(part == ".." for part in parts):
        return False, "parent traversal is not allowed"
    prefix = f"generated/{project_id.strip()}/"
    normalized = Path(token).as_posix()
    if not normalized.startswith(prefix):
        return False, f"path must be under {prefix}"
    return True, ""


def materialize_candidate_artifacts(
    *,
    repo_root: Path,
    sandbox_session: Path,
    project_id: str,
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    candidates_root = (sandbox_session / "candidates").resolve()

    for row in candidates:
        path_raw = row.get("path")
        content = row.get("content")
        if not isinstance(path_raw, str):
            rejected.append({"path": "<unknown>", "reason": "missing path"})
            continue
        ok, reason = validate_candidate_path(project_id=project_id, artifact_path=path_raw)
        if not ok:
            rejected.append({"path": path_raw, "reason": reason})
            continue
        if not isinstance(content, str):
            rejected.append({"path": path_raw, "reason": "missing content"})
            continue
        logical_path = Path(path_raw).as_posix()
        target_path = (candidates_root / logical_path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        metadata_path = target_path.with_suffix(target_path.suffix + ".ai-metadata.json")
        metadata_path.write_text(
            json.dumps(
                {
                    "source": "ai-assisted",
                    "path": logical_path,
                    "confidence": row.get("confidence"),
                    "rationale": row.get("rationale", ""),
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        baseline_path = (repo_root / logical_path).resolve()
        accepted.append(
            {
                "path": logical_path,
                "candidate_path": str(target_path),
                "baseline_path": str(baseline_path),
                "metadata_path": str(metadata_path),
            }
        )
    return accepted, rejected


def build_candidate_diff(*, baseline_path: Path, candidate_path: Path, logical_path: str) -> dict[str, Any]:
    if baseline_path.exists() and baseline_path.is_file():
        old = baseline_path.read_text(encoding="utf-8").splitlines()
        change_type = "modified"
    else:
        old = []
        change_type = "added"
    new = candidate_path.read_text(encoding="utf-8").splitlines()
    diff_lines = list(
        difflib.unified_diff(
            old,
            new,
            fromfile=f"a/{logical_path}",
            tofile=f"b/{logical_path}",
            lineterm="",
        )
    )
    return {
        "path": logical_path,
        "change_type": change_type,
        "diff_text": "\n".join(diff_lines),
        "added_lines": max(0, len(new) - len(old)),
    }

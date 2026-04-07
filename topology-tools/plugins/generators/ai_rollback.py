"""ADR0094 AI-assisted rollback helpers."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any


def list_ai_promoted_artifacts(*, repo_root: Path, project_id: str) -> list[dict[str, str]]:
    generated_root = (repo_root.resolve() / "generated" / project_id.strip()).resolve()
    if not generated_root.exists() or not generated_root.is_dir():
        return []
    results: list[dict[str, str]] = []
    for metadata_path in sorted(generated_root.rglob("*.ai-metadata.json")):
        artifact_path = metadata_path.with_name(metadata_path.name.removesuffix(".ai-metadata.json"))
        logical_path = artifact_path.resolve().relative_to(repo_root.resolve()).as_posix()
        results.append(
            {
                "path": logical_path,
                "artifact_path": str(artifact_path.resolve()),
                "metadata_path": str(metadata_path.resolve()),
            }
        )
    return results


def rollback_ai_promoted_artifacts(
    *,
    repo_root: Path,
    artifacts: list[dict[str, Any]],
    ref: str = "HEAD",
) -> dict[str, Any]:
    start = time.monotonic()
    restored: list[str] = []
    deleted: list[str] = []
    failed: list[dict[str, str]] = []

    for row in artifacts:
        path = str(row.get("path", "")).strip()
        if not path:
            failed.append({"path": "<unknown>", "reason": "missing path"})
            continue
        target_path = (repo_root.resolve() / path).resolve()
        metadata_path = target_path.with_suffix(target_path.suffix + ".ai-metadata.json")

        exists_cmd = ["git", "-C", str(repo_root.resolve()), "cat-file", "-e", f"{ref}:{path}"]
        exists = subprocess.run(exists_cmd, capture_output=True).returncode == 0
        if exists:
            show_cmd = ["git", "-C", str(repo_root.resolve()), "show", f"{ref}:{path}"]
            result = subprocess.run(show_cmd, capture_output=True)
            if result.returncode != 0:
                failed.append({"path": path, "reason": result.stderr.decode("utf-8", errors="ignore").strip()})
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(result.stdout)
            restored.append(path)
        else:
            target_path.unlink(missing_ok=True)
            deleted.append(path)
        metadata_path.unlink(missing_ok=True)

    duration_seconds = time.monotonic() - start
    return {
        "restored": restored,
        "deleted": deleted,
        "failed": failed,
        "duration_seconds": duration_seconds,
    }


#!/usr/bin/env python3
"""Contract checks for ADR0094 AI rollback helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_rollback import (  # noqa: E402
    list_ai_promoted_artifacts,
    rollback_ai_promoted_artifacts,
)


def _git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(["git", "-C", str(cwd), *cmd], check=True, capture_output=True)


def test_list_ai_promoted_artifacts_finds_metadata_sidecars(tmp_path: Path) -> None:
    meta = tmp_path / "generated" / "home-lab" / "docs" / "a.md.ai-metadata.json"
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text('{"source":"ai-assisted"}', encoding="utf-8")
    (tmp_path / "generated" / "home-lab" / "docs" / "a.md").write_text("x\n", encoding="utf-8")
    rows = list_ai_promoted_artifacts(repo_root=tmp_path, project_id="home-lab")
    assert len(rows) == 1
    assert rows[0]["path"] == "generated/home-lab/docs/a.md"


def test_rollback_ai_promoted_artifacts_restores_or_deletes(tmp_path: Path) -> None:
    _git(["init"], tmp_path)
    _git(["config", "user.email", "ci@example.com"], tmp_path)
    _git(["config", "user.name", "CI"], tmp_path)

    tracked = tmp_path / "generated" / "home-lab" / "docs" / "tracked.md"
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text("baseline\n", encoding="utf-8")
    _git(["add", "."], tmp_path)
    _git(["commit", "-m", "baseline"], tmp_path)

    tracked.write_text("changed\n", encoding="utf-8")
    tracked.with_suffix(".md.ai-metadata.json").write_text("{}", encoding="utf-8")
    new_file = tmp_path / "generated" / "home-lab" / "docs" / "new.md"
    new_file.write_text("temp\n", encoding="utf-8")
    new_file.with_suffix(".md.ai-metadata.json").write_text("{}", encoding="utf-8")

    result = rollback_ai_promoted_artifacts(
        repo_root=tmp_path,
        artifacts=[
            {"path": "generated/home-lab/docs/tracked.md"},
            {"path": "generated/home-lab/docs/new.md"},
        ],
        ref="HEAD",
    )
    assert "generated/home-lab/docs/tracked.md" in result["restored"]
    assert "generated/home-lab/docs/new.md" in result["deleted"]
    assert result["duration_seconds"] < 300
    assert tracked.read_text(encoding="utf-8") == "baseline\n"
    assert new_file.exists() is False
    assert tracked.with_suffix(".md.ai-metadata.json").exists() is False

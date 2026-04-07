#!/usr/bin/env python3
"""Contract checks for ADR0094 AI-assisted candidate helpers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_assisted import (  # noqa: E402
    build_candidate_diff,
    materialize_candidate_artifacts,
    validate_candidate_path,
)


def test_validate_candidate_path_enforces_generated_project_scope() -> None:
    ok, _ = validate_candidate_path(project_id="home-lab", artifact_path="generated/home-lab/docs/a.md")
    assert ok is True
    bad_absolute, _ = validate_candidate_path(project_id="home-lab", artifact_path="/tmp/a.md")
    bad_traversal, _ = validate_candidate_path(project_id="home-lab", artifact_path="../generated/home-lab/a.md")
    bad_scope, _ = validate_candidate_path(project_id="home-lab", artifact_path="generated/other/a.md")
    assert bad_absolute is False
    assert bad_traversal is False
    assert bad_scope is False


def test_materialize_candidate_artifacts_writes_candidates_and_metadata(tmp_path: Path) -> None:
    session = tmp_path / ".work" / "ai-sandbox" / "home-lab" / "req-1"
    accepted, rejected = materialize_candidate_artifacts(
        repo_root=tmp_path,
        sandbox_session=session,
        project_id="home-lab",
        candidates=[
            {
                "path": "generated/home-lab/docs/overview.md",
                "content": "hello\n",
                "confidence": 0.8,
                "rationale": "update",
            },
            {"path": "generated/home-lab/docs/missing.md"},
        ],
    )
    assert len(accepted) == 1
    assert len(rejected) == 1
    candidate_path = Path(accepted[0]["candidate_path"])
    metadata_path = Path(accepted[0]["metadata_path"])
    assert candidate_path.exists()
    assert metadata_path.exists()


def test_build_candidate_diff_handles_added_and_modified(tmp_path: Path) -> None:
    baseline = tmp_path / "generated" / "home-lab" / "docs" / "overview.md"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text("old\n", encoding="utf-8")
    candidate = tmp_path / ".work" / "ai-sandbox" / "home-lab" / "req-2" / "candidates" / "generated" / "home-lab" / "docs" / "overview.md"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("new\n", encoding="utf-8")

    payload = build_candidate_diff(
        baseline_path=baseline,
        candidate_path=candidate,
        logical_path="generated/home-lab/docs/overview.md",
    )
    assert payload["change_type"] == "modified"
    assert "@@" in payload["diff_text"]


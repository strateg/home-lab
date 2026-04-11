#!/usr/bin/env python3
"""Contract checks for ADR0094 AI-assisted promotion helpers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from ai_runtime.ai_promotion import (  # noqa: E402
    promote_approved_candidates,
    resolve_approvals,
)


def test_resolve_approvals_supports_all_and_selective() -> None:
    candidates = [{"path": "generated/home-lab/docs/a.md"}, {"path": "generated/home-lab/docs/b.md"}]
    approved_all, rejected_all = resolve_approvals(candidates=candidates, approve_all=True, approve_paths=set())
    assert len(approved_all) == 2
    assert len(rejected_all) == 0

    approved_one, rejected_one = resolve_approvals(
        candidates=candidates,
        approve_all=False,
        approve_paths={"generated/home-lab/docs/b.md"},
    )
    assert [row["path"] for row in approved_one] == ["generated/home-lab/docs/b.md"]
    assert [row["path"] for row in rejected_one] == ["generated/home-lab/docs/a.md"]


def test_promote_approved_candidates_copies_artifact_and_metadata(tmp_path: Path) -> None:
    candidate = (
        tmp_path
        / ".work"
        / "ai-sandbox"
        / "home-lab"
        / "req-1"
        / "candidates"
        / "generated"
        / "home-lab"
        / "docs"
        / "a.md"
    )
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("hello\n", encoding="utf-8")
    meta = candidate.with_suffix(candidate.suffix + ".ai-metadata.json")
    meta.write_text('{"source":"ai-assisted"}', encoding="utf-8")

    promoted = promote_approved_candidates(
        repo_root=tmp_path,
        approved=[
            {
                "path": "generated/home-lab/docs/a.md",
                "candidate_path": str(candidate),
                "metadata_path": str(meta),
            }
        ],
    )
    target = tmp_path / "generated" / "home-lab" / "docs" / "a.md"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert Path(promoted[0]["metadata_path"]).exists()

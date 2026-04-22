"""
Tests for cleanup_obsolete_artifacts.py script.

Validates artifact plan parsing, obsolete detection, and cleanup logic.
"""

import json

# Add scripts to path
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "orchestration"
sys.path.insert(0, str(SCRIPTS))

from cleanup_obsolete_artifacts import (  # noqa: E402
    collect_obsolete_artifacts,
    load_artifact_plans,
)


@pytest.fixture
def mock_artifact_plans_dir(tmp_path: Path) -> Path:
    """Create mock artifact plans directory with test data."""
    plans_dir = tmp_path / ".state" / "artifact-plans"
    plans_dir.mkdir(parents=True)

    # Plan with obsolete candidates
    plan_with_obsolete = {
        "artifact_family": "test.family",
        "plugin_id": "test.plugin.obsolete",
        "schema_version": "1.0",
        "obsolete_candidates": [
            {
                "action": "warn",
                "reason": "obsolete-shadowed",
                "path": "generated/test/obsolete1.txt",
                "ownership_proven": True,
            },
            {
                "action": "warn",
                "reason": "obsolete-shadowed",
                "path": "generated/test/obsolete2.txt",
                "ownership_proven": True,
            },
            {
                "action": "keep",
                "reason": "still-active",
                "path": "generated/test/active.txt",
                "ownership_proven": True,
            },
        ],
        "planned_outputs": [],
    }

    # Plan without obsolete candidates
    plan_without_obsolete = {
        "artifact_family": "test.clean",
        "plugin_id": "test.plugin.clean",
        "schema_version": "1.0",
        "obsolete_candidates": [],
        "planned_outputs": [],
    }

    # Write plans
    (plans_dir / "test_obsolete.json").write_text(json.dumps(plan_with_obsolete, indent=2), encoding="utf-8")
    (plans_dir / "test_clean.json").write_text(json.dumps(plan_without_obsolete, indent=2), encoding="utf-8")

    return plans_dir


def test_load_artifact_plans(mock_artifact_plans_dir: Path) -> None:
    """Test loading artifact plans from directory."""
    with patch("cleanup_obsolete_artifacts.ARTIFACT_PLANS_DIR", mock_artifact_plans_dir):
        plans = load_artifact_plans()

    assert len(plans) == 2
    assert any(p["plugin_id"] == "test.plugin.obsolete" for p in plans)
    assert any(p["plugin_id"] == "test.plugin.clean" for p in plans)


def test_collect_obsolete_artifacts_filters_correctly(mock_artifact_plans_dir: Path) -> None:
    """Test that only warn + obsolete-shadowed artifacts are collected."""
    with patch("cleanup_obsolete_artifacts.ARTIFACT_PLANS_DIR", mock_artifact_plans_dir):
        plans = load_artifact_plans()
        obsolete = collect_obsolete_artifacts(plans)

    # Should find 2 obsolete artifacts (action=warn, reason=obsolete-shadowed)
    assert len(obsolete) == 2

    # Verify structure
    for artifact in obsolete:
        assert "path" in artifact
        assert "plugin_id" in artifact
        assert artifact["plugin_id"] == "test.plugin.obsolete"
        assert "generated/test/obsolete" in artifact["path"]


def test_collect_obsolete_artifacts_empty_when_none() -> None:
    """Test that empty list is returned when no obsolete artifacts exist."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        plans_dir = tmp_path / ".state" / "artifact-plans"
        plans_dir.mkdir(parents=True)

        # Create plan with no obsolete candidates
        plan = {
            "plugin_id": "test.empty",
            "schema_version": "1.0",
            "obsolete_candidates": [],
            "planned_outputs": [],
        }
        (plans_dir / "empty.json").write_text(json.dumps(plan), encoding="utf-8")

        with patch("cleanup_obsolete_artifacts.ARTIFACT_PLANS_DIR", plans_dir):
            plans = load_artifact_plans()
            obsolete = collect_obsolete_artifacts(plans)

        assert len(obsolete) == 0


def test_script_handles_missing_artifact_plans_dir(tmp_path: Path, capsys) -> None:
    """Test script exits gracefully when artifact plans directory missing."""
    non_existent = tmp_path / "does_not_exist"

    with patch("cleanup_obsolete_artifacts.ARTIFACT_PLANS_DIR", non_existent):
        with pytest.raises(SystemExit) as exc_info:
            load_artifact_plans()

        assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "Artifact plans directory not found" in captured.out


def test_collect_obsolete_artifacts_includes_metadata(mock_artifact_plans_dir: Path) -> None:
    """Test that collected artifacts include all required metadata."""
    with patch("cleanup_obsolete_artifacts.ARTIFACT_PLANS_DIR", mock_artifact_plans_dir):
        plans = load_artifact_plans()
        obsolete = collect_obsolete_artifacts(plans)

    for artifact in obsolete:
        assert "path" in artifact
        assert "plugin_id" in artifact
        assert "ownership_proven" in artifact
        assert "source_plan" in artifact
        assert artifact["source_plan"] == "test_obsolete.json"

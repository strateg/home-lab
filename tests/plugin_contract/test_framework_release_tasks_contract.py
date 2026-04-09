#!/usr/bin/env python3
"""Contract checks for framework release task wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TASKFILE_PATH = REPO_ROOT / "taskfiles" / "framework.yml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict), f"expected YAML mapping at {path}"
    return payload


def test_framework_verify_artifact_contents_task_exists() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("verify-artifact-contents")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "verify-framework-artifact-contents.py" in serialized


def test_release_candidate_depends_on_verify_artifact_contents() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    candidate = tasks.get("release-candidate")
    assert isinstance(candidate, dict)
    deps = candidate.get("deps", [])
    assert isinstance(deps, list)
    assert "verify-artifact-contents" in [str(item) for item in deps]


def test_framework_baseline_evidence_task_exists() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("baseline-evidence")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "generate-baseline-evidence.py" in serialized


def test_release_ci_depends_on_package_trust_gate() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    release_ci = tasks.get("release-ci")
    assert isinstance(release_ci, dict)
    deps = release_ci.get("deps", [])
    assert isinstance(deps, list)
    assert "package-trust-gate" in [str(item) for item in deps]

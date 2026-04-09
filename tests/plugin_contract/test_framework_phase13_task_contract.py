#!/usr/bin/env python3
"""Contract checks for ADR0076 Phase 13 evidence task wiring."""

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


def test_framework_phase13_evidence_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("phase13-evidence")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "topology-tools/utils/generate-phase13-evidence.py" in serialized


def test_framework_split_rehearsal_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("split-rehearsal")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "topology-tools/utils/run-split-rehearsal.py" in serialized


def test_framework_phase13_go_no_go_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("phase13-go-no-go")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "topology-tools/utils/validate-phase13-go-no-go.py" in serialized

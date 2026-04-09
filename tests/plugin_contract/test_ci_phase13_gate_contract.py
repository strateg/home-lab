#!/usr/bin/env python3
"""Contract checks for CI phase13 gate task wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TASKFILE_PATH = REPO_ROOT / "taskfiles" / "ci.yml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict), f"expected YAML mapping at {path}"
    return payload


def _serialized_cmds(task_payload: dict[str, Any]) -> str:
    cmds = task_payload.get("cmds", [])
    if not isinstance(cmds, list):
        return ""
    return "\n".join(str(item) for item in cmds)


def test_ci_phase13_gate_task_exists_and_runs_framework_gates() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    gate = tasks.get("phase13-gate")
    assert isinstance(gate, dict)
    serialized = _serialized_cmds(gate)
    assert "task framework:phase13-evidence" in serialized
    assert "task framework:phase13-go-no-go" in serialized


def test_strict_validate_core_tasks_include_phase13_gate() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    for name in ("_strict-validate-core", "_strict-validate-core-inject"):
        row = tasks.get(name)
        assert isinstance(row, dict), f"missing task: {name}"
        serialized = _serialized_cmds(row)
        assert "task ci:phase13-gate" in serialized


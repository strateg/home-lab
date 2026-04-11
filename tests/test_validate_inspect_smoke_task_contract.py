#!/usr/bin/env python3
"""Task contract checks for validate inspect-smoke wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
TASKFILE_PATH = REPO_ROOT / "taskfiles" / "validate.yml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict), f"expected YAML mapping at {path}"
    return payload


def _first_cmd(tasks: dict[str, Any], name: str) -> str:
    row = tasks.get(name)
    assert isinstance(row, dict), f"missing task: {name}"
    cmds = row.get("cmds", [])
    assert isinstance(cmds, list) and cmds, f"missing cmds for task: {name}"
    assert isinstance(cmds[0], str)
    return cmds[0]


def test_validate_taskfile_includes_inspect_smoke_task() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    assert "inspect-smoke" in tasks


def test_inspect_smoke_task_wires_runner_and_diagnostics_paths() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    cmd = _first_cmd(tasks, "inspect-smoke")

    assert "scripts/inspection/run_inspect_smoke_matrix.py" in cmd
    assert "--json-output build/diagnostics/inspect-smoke-matrix.json" in cmd
    assert "--text-output build/diagnostics/inspect-smoke-matrix.txt" in cmd
    assert "--allow-failures" not in cmd


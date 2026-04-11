#!/usr/bin/env python3
"""Task contract checks for inspect namespace wiring."""

from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
INSPECT_TASKFILE = REPO_ROOT / "taskfiles" / "inspect.yml"


def _load_tasks() -> dict[str, object]:
    payload = yaml.safe_load(INSPECT_TASKFILE.read_text(encoding="utf-8"))
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    return tasks


def _first_cmd(tasks: dict[str, object], task_name: str) -> str:
    task_row = tasks.get(task_name, {})
    assert isinstance(task_row, dict)
    cmds = task_row.get("cmds", [])
    assert isinstance(cmds, list) and cmds
    assert isinstance(cmds[0], str)
    return cmds[0]


def test_inspect_taskfile_contains_compact_and_detailed_object_instance_tasks() -> None:
    tasks = _load_tasks()
    for name in (
        "objects",
        "objects-detailed",
        "instances",
        "instances-detailed",
        "summary-json",
        "deps-json",
        "deps-typed-shadow",
        "deps-json-typed-shadow",
        "inheritance-json",
        "capabilities-json",
    ):
        assert name in tasks


def test_detailed_tasks_forward_detailed_flag_to_cli() -> None:
    tasks = _load_tasks()
    assert "objects --detailed" in _first_cmd(tasks, "objects-detailed")
    assert "instances --detailed" in _first_cmd(tasks, "instances-detailed")


def test_json_tasks_forward_json_flag_to_cli() -> None:
    tasks = _load_tasks()
    assert "summary --json" in _first_cmd(tasks, "summary-json")
    assert "deps --instance {{.INSTANCE}} --json" in _first_cmd(tasks, "deps-json")
    assert "deps --instance {{.INSTANCE}} --json --typed-shadow" in _first_cmd(tasks, "deps-json-typed-shadow")
    assert "inheritance --json" in _first_cmd(tasks, "inheritance-json")
    assert "capabilities --json" in _first_cmd(tasks, "capabilities-json")


def test_typed_shadow_task_forwards_flag_to_cli() -> None:
    tasks = _load_tasks()
    assert "deps --instance {{.INSTANCE}} --typed-shadow" in _first_cmd(tasks, "deps-typed-shadow")

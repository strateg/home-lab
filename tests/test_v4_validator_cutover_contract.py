#!/usr/bin/env python3
"""Guard Phase 9 cutover: active runtime must not depend on legacy v4 validator checks."""

from __future__ import annotations

from pathlib import Path

import yaml

FORBIDDEN_VALIDATOR_TOKENS = (
    "scripts/validators/checks",
    "v4/topology-tools/scripts/validators",
    "archive/v4/topology-tools/scripts/validators",
)

RUNTIME_PATHS = (
    "topology-tools/compile-topology.py",
    "scripts/orchestration/lane.py",
)


def test_active_runtime_has_no_legacy_v4_validator_check_references():
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[str] = []

    for rel_path in RUNTIME_PATHS:
        content = (repo_root / rel_path).read_text(encoding="utf-8")
        for token in FORBIDDEN_VALIDATOR_TOKENS:
            if token in content:
                violations.append(f"{rel_path}: contains forbidden token '{token}'")

    for path in (repo_root / "topology-tools" / "plugins").rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(repo_root).as_posix()
        for token in FORBIDDEN_VALIDATOR_TOKENS:
            if token in content:
                violations.append(f"{rel_path}: contains forbidden token '{token}'")

    assert not violations, "\n".join(violations)


def test_validate_default_task_remains_v5_only():
    repo_root = Path(__file__).resolve().parents[1]
    payload = yaml.safe_load((repo_root / "taskfiles" / "validate.yml").read_text(encoding="utf-8"))
    tasks = payload.get("tasks", {}) if isinstance(payload, dict) else {}
    default_task = tasks.get("default", {}) if isinstance(tasks, dict) else {}
    cmds = default_task.get("cmds", []) if isinstance(default_task, dict) else []

    serialized = "\n".join(str(cmd) for cmd in cmds)
    assert "lane.py validate-v5" in serialized
    assert "archive/v4" not in serialized
    assert "parity-v4-v5" not in serialized

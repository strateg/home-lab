#!/usr/bin/env python3
"""Contract checks for ADR0076 cutover evidence task wiring."""

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


def test_framework_cutover_evidence_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("cutover-evidence")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "topology-tools/utils/generate-cutover-evidence.py" in serialized


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


def test_framework_cutover_go_no_go_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("cutover-go-no-go")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "topology-tools/utils/validate-cutover-go-no-go.py" in serialized


def test_framework_package_trust_artifact_verification_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("verify-lock-package-trust-artifacts")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "--enforce-package-trust" in serialized
    assert "--verify-package-artifact-files" in serialized


def test_framework_package_trust_signature_verification_task_is_defined() -> None:
    payload = _load_yaml(TASKFILE_PATH)
    tasks = payload.get("tasks", {})
    assert isinstance(tasks, dict)
    task_payload = tasks.get("verify-lock-package-trust-signature")
    assert isinstance(task_payload, dict)
    cmds = task_payload.get("cmds", [])
    assert isinstance(cmds, list)
    serialized = "\n".join(str(item) for item in cmds)
    assert "--verify-package-signature" in serialized

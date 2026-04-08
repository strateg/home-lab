#!/usr/bin/env python3
"""Contract checks for ADR0090 product:* task surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKFILE_PATH = REPO_ROOT / "taskfiles" / "product.yml"
CONTRACT_PATH = REPO_ROOT / "topology-tools" / "data" / "product-task-contract.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict), f"expected YAML mapping at {path}"
    return payload


def _task_cmd_strings(task_payload: dict[str, Any]) -> list[str]:
    cmds = task_payload.get("cmds", [])
    if not isinstance(cmds, list):
        return []
    rendered: list[str] = []
    for item in cmds:
        if isinstance(item, str):
            rendered.append(item)
        elif isinstance(item, dict):
            # taskfile shorthand: {task: ..., vars: ...}
            task_name = item.get("task")
            if isinstance(task_name, str):
                rendered.append(f"task {task_name}")
    return rendered


def test_product_task_contract_covers_all_declared_product_tasks() -> None:
    taskfile = _load_yaml(TASKFILE_PATH)
    contract = _load_yaml(CONTRACT_PATH)

    tasks = taskfile.get("tasks", {})
    assert isinstance(tasks, dict)

    contract_tasks = contract.get("tasks", {})
    assert isinstance(contract_tasks, dict)

    declared_product_tasks = {f"product:{name}" for name in tasks.keys()}
    contract_task_set = set(contract_tasks.keys())

    assert declared_product_tasks == contract_task_set


def test_product_task_contract_declares_pre_and_postconditions() -> None:
    contract = _load_yaml(CONTRACT_PATH)
    tasks = contract.get("tasks", {})
    assert isinstance(tasks, dict)

    for task_name, payload in tasks.items():
        assert isinstance(payload, dict), f"contract task must be mapping: {task_name}"
        pre = payload.get("preconditions")
        post = payload.get("postconditions")
        assert isinstance(pre, list) and pre, f"preconditions missing for {task_name}"
        assert isinstance(post, list) and post, f"postconditions missing for {task_name}"


def test_read_only_product_tasks_do_not_invoke_apply_workflows() -> None:
    taskfile = _load_yaml(TASKFILE_PATH)
    tasks = taskfile.get("tasks", {})
    assert isinstance(tasks, dict)

    read_only_tasks = ("doctor", "plan", "audit")
    forbidden_tokens = (
        "workflow:deploy-apply",
        "deploy:service-chain-evidence-apply",
        "deploy:service-chain-evidence-apply-bundle",
        "ALLOW_APPLY",
    )

    for task_name in read_only_tasks:
        payload = tasks.get(task_name, {})
        assert isinstance(payload, dict), f"task '{task_name}' missing"
        cmds_serialized = "\n".join(_task_cmd_strings(payload))
        for token in forbidden_tokens:
            assert token not in cmds_serialized, f"read-only task '{task_name}' references '{token}'"


def test_product_doctor_uses_machine_readable_evidence_resolver() -> None:
    taskfile = _load_yaml(TASKFILE_PATH)
    tasks = taskfile.get("tasks", {})
    assert isinstance(tasks, dict)

    doctor = tasks.get("doctor", {})
    assert isinstance(doctor, dict)
    serialized = "\n".join(_task_cmd_strings(doctor))
    assert "scripts/orchestration/product/doctor.py" in serialized


def test_product_apply_task_has_explicit_safety_gate() -> None:
    taskfile = _load_yaml(TASKFILE_PATH)
    tasks = taskfile.get("tasks", {})
    assert isinstance(tasks, dict)

    apply_task = tasks.get("apply", {})
    assert isinstance(apply_task, dict)

    requires = apply_task.get("requires", {})
    assert isinstance(requires, dict)
    vars_required = requires.get("vars", [])
    assert isinstance(vars_required, list)
    assert "BUNDLE" in vars_required
    assert "ALLOW_APPLY" in vars_required

    preconditions = apply_task.get("preconditions", [])
    assert isinstance(preconditions, list)
    serialized = "\n".join(str(item) for item in preconditions)
    assert "ALLOW_APPLY" in serialized
    assert "YES" in serialized

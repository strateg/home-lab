"""ADR0094 Ansible-specific AI adapter helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable


def build_ansible_input_adapter(effective_json: dict[str, Any]) -> dict[str, Any]:
    instances = effective_json.get("instances")
    hosts: list[dict[str, Any]] = []
    if isinstance(instances, dict):
        for instance_id, row in instances.items():
            if not isinstance(instance_id, str) or not isinstance(row, dict):
                continue
            ip = row.get("management_ip")
            if isinstance(ip, str) and ip.strip():
                hosts.append({"instance_id": instance_id, "management_ip": ip.strip()})
    return {"hosts": hosts}


def parse_ansible_output_candidates(
    *,
    project_id: str,
    ai_output: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = ai_output.get("candidate_artifacts")
    if not isinstance(rows, list):
        return []
    prefix = f"generated/{project_id.strip()}/ansible/"
    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        if isinstance(path, str) and path.startswith(prefix):
            selected.append(dict(row))
    return selected


def validate_ansible_candidates_with_lint(
    *,
    candidates: list[dict[str, Any]],
    lint_cmd: str = "ansible-lint",
    runner: Callable[..., Any] = subprocess.run,
) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for row in candidates:
        candidate_path = row.get("candidate_path")
        logical_path = str(row.get("path", ""))
        if not isinstance(candidate_path, str):
            failures.append({"path": logical_path or "<unknown>", "reason": "missing candidate_path"})
            continue
        cmd = [lint_cmd, candidate_path]
        try:
            result = runner(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            failures.append({"path": logical_path or "<unknown>", "reason": f"{lint_cmd} not found"})
            continue
        if getattr(result, "returncode", 1) != 0:
            stderr = str(getattr(result, "stderr", "")).strip()
            failures.append({"path": logical_path or "<unknown>", "reason": stderr or "ansible-lint failed"})
    return failures


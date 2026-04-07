#!/usr/bin/env python3
"""Contract checks for ADR0094 Ansible AI adapters."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.ai_ansible import (  # noqa: E402
    build_ansible_input_adapter,
    parse_ansible_output_candidates,
    validate_ansible_candidates_with_lint,
)


def test_build_ansible_input_adapter_extracts_hosts() -> None:
    adapter = build_ansible_input_adapter(
        {
            "instances": {
                "srv-1": {"management_ip": "10.0.0.10"},
                "srv-2": {"management_ip": "10.0.0.11"},
                "srv-3": {"note": "no ip"},
            }
        }
    )
    assert len(adapter["hosts"]) == 2


def test_parse_ansible_output_candidates_filters_family_scope() -> None:
    rows = parse_ansible_output_candidates(
        project_id="home-lab",
        ai_output={
            "candidate_artifacts": [
                {"path": "generated/home-lab/ansible/inventory/production/hosts.yml"},
                {"path": "generated/home-lab/docs/overview.md"},
            ]
        },
    )
    assert [row["path"] for row in rows] == ["generated/home-lab/ansible/inventory/production/hosts.yml"]


def test_validate_ansible_candidates_with_lint_returns_failures() -> None:
    class _Result:
        def __init__(self, code: int, stderr: str = "") -> None:
            self.returncode = code
            self.stderr = stderr

    calls: list[list[str]] = []

    def _runner(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd[-1].endswith("bad.yml"):
            return _Result(1, "syntax error")
        return _Result(0)

    failures = validate_ansible_candidates_with_lint(
        candidates=[
            {"path": "generated/home-lab/ansible/inventory/good.yml", "candidate_path": "/tmp/good.yml"},
            {"path": "generated/home-lab/ansible/inventory/bad.yml", "candidate_path": "/tmp/bad.yml"},
        ],
        runner=_runner,
    )
    assert len(calls) == 2
    assert failures == [{"path": "generated/home-lab/ansible/inventory/bad.yml", "reason": "syntax error"}]


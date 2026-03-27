#!/usr/bin/env python3
"""Generate cutover readiness report for ADR0076 gates."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GateResult:
    name: str
    command: list[str]
    return_code: int
    ok: bool
    stdout: str
    stderr: str


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_output_json() -> Path:
    return _default_repo_root() / "build" / "diagnostics" / "cutover-readiness.json"


def _default_cutover_state_json(repo_root: Path) -> Path:
    return repo_root / "docs" / "framework" / "adr0076-cutover-state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ADR0076 cutover readiness report.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root where topology-tools are located.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=_default_output_json(),
        help="Output report path.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run core strict gates only (skip full test suite and lane validation).",
    )
    parser.add_argument(
        "--cutover-state-json",
        type=Path,
        default=None,
        help=(
            "Optional JSON file with manual production cutover completion state. "
            "Default: <repo-root>/docs/framework/adr0076-cutover-state.json."
        ),
    )
    return parser.parse_args()


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> GateResult:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return GateResult(
        name=command[2] if len(command) >= 3 and command[1].endswith(".py") else " ".join(command[:3]),
        command=command,
        return_code=completed.returncode,
        ok=completed.returncode == 0,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _gate_commands(repo_root: Path, *, quick: bool) -> list[tuple[str, list[str], dict[str, str] | None]]:
    python = sys.executable
    commands: list[tuple[str, list[str], dict[str, str] | None]] = [
        (
            "verify_framework_lock",
            [python, "topology-tools/verify-framework-lock.py", "--strict"],
            None,
        ),
        (
            "rehearse_rollback",
            [python, "topology-tools/rehearse-framework-rollback.py"],
            None,
        ),
        (
            "validate_compatibility_matrix",
            [python, "topology-tools/validate-framework-compatibility-matrix.py"],
            None,
        ),
        (
            "audit_strict_entrypoints",
            [python, "topology-tools/audit-strict-runtime-entrypoints.py"],
            None,
        ),
    ]
    if not quick:
        commands.extend(
            [
                (
                    "pytest_v4_v5_parity",
                    [
                        python,
                        "-m",
                        "pytest",
                        "-o",
                        "addopts=",
                        "tests/plugin_regression",
                        "tests/plugin_integration/test_parity_stage_order.py",
                        "tests/plugin_integration/test_parallel_profile_parity.py",
                        "-q",
                    ],
                    None,
                ),
                (
                    "pytest_v5",
                    [python, "-m", "pytest", "-o", "addopts=", "tests", "-q"],
                    None,
                ),
                (
                    "lane_validate_v5",
                    [python, "scripts/orchestration/lane.py", "validate-v5"],
                    {"V5_SECRETS_MODE": "passthrough"},
                ),
            ]
        )
    return commands


def _load_cutover_state(state_path: Path) -> dict[str, Any] | None:
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_json = args.output_json.resolve()
    quick = bool(args.quick)
    cutover_state_json = (
        args.cutover_state_json.resolve()
        if isinstance(args.cutover_state_json, Path)
        else _default_cutover_state_json(repo_root)
    )

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for gate_name, command, env_patch in _gate_commands(repo_root, quick=quick):
        env = None
        if env_patch:
            env = dict(os.environ)
            env.update(env_patch)
        result = _run(command, cwd=repo_root, env=env)
        payload = asdict(result)
        payload["gate"] = gate_name
        results.append(payload)
        status = "PASS" if result.ok else "FAIL"
        print(f"[cutover] {gate_name}: {status}")
        if not result.ok:
            failures.append(gate_name)
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())

    output_json.parent.mkdir(parents=True, exist_ok=True)
    cutover_state = _load_cutover_state(cutover_state_json)
    production_cutover_complete = bool(
        isinstance(cutover_state, dict) and cutover_state.get("production_cutover_complete") is True
    )
    pending_external_steps: list[str] = []
    if not production_cutover_complete:
        pending_external_steps.append("production cutover announcement and freeze switch")
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
        "quick": quick,
        "summary": {
            "total": len(results),
            "failed": len(failures),
            "passed": len(results) - len(failures),
        },
        "gates": results,
        "ready_for_cutover": len(failures) == 0,
        "production_cutover_complete": production_cutover_complete,
        "ready_for_operational_baseline": len(failures) == 0 and production_cutover_complete,
        "cutover_state_json": str(cutover_state_json),
        "pending_external_steps": pending_external_steps,
    }
    if cutover_state is not None:
        report["cutover_state"] = cutover_state
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"[cutover] report: {output_json}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

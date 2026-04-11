#!/usr/bin/env python3
"""Lane-specific command dispatcher."""

from __future__ import annotations

import argparse
from enum import IntEnum
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
PHASE1_REPORT_JSON = "build/diagnostics/phase1-gate-report.json"
LAYER_REPORT_JSON = "build/diagnostics/layer-contract-report.json"
ADR0088_GOVERNANCE_REPORT_JSON = "build/diagnostics/adr0088-governance-report.json"
SUPPORTED_SECRETS_MODES = {"inject", "passthrough", "strict"}
LEGACY_ROOT_DIRS = ("v4", "v5")


class LaneExitCode(IntEnum):
    OK = 0
    VALIDATION_ERROR = 1
    WARNING = 2
    INFRA_ERROR = 3


class LaneAggregateError(RuntimeError):
    """Raised when collect-all mode finishes with one or more failed steps."""

    def __init__(self, failures: list[str], *, has_timeout: bool = False) -> None:
        self.failures = tuple(failures)
        self.has_timeout = has_timeout
        super().__init__(f"{len(self.failures)} lane step(s) failed.")


def run(cmd: list[str], *, timeout: float | None = None) -> None:
    print(f"[lane] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, timeout=timeout)


def _resolve_secrets_mode() -> str:
    value = os.environ.get("V5_SECRETS_MODE", "inject").strip().lower()
    if value in SUPPORTED_SECRETS_MODES:
        return value
    return "inject"


def _format_timeout(timeout: float | None) -> str:
    if timeout is None:
        return "unknown"
    return f"{timeout:g}"


def _record_failure(cmd: list[str], exc: Exception, *, timeout: float | None) -> str:
    rendered = " ".join(cmd)
    if isinstance(exc, subprocess.CalledProcessError):
        return f"{rendered} exited with code {exc.returncode}"
    if isinstance(exc, subprocess.TimeoutExpired):
        timeout_value = exc.timeout if exc.timeout is not None else timeout
        return f"{rendered} timed out after {_format_timeout(timeout_value)}s"
    return f"{rendered} failed: {exc}"


def _run_steps(
    commands: list[list[str]], *, timeout: float | None = None, collect_all_errors: bool = False
) -> None:
    failures: list[str] = []
    saw_timeout = False
    for cmd in commands:
        try:
            run(cmd, timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            if not collect_all_errors:
                raise
            failures.append(_record_failure(cmd, exc, timeout=timeout))
            if isinstance(exc, subprocess.TimeoutExpired):
                saw_timeout = True
    if failures:
        raise LaneAggregateError(failures, has_timeout=saw_timeout)


def _validate_v5_commands(secrets_mode: str) -> list[list[str]]:
    if secrets_mode not in SUPPORTED_SECRETS_MODES:
        raise ValueError(f"Unsupported secrets mode: {secrets_mode}")
    # NOTE: canonical instance source is ADR0071 shards under project manifest instances_root.
    # export_v5_instance_bindings.py is legacy migration helper only.
    commands = [
        [PYTHON, "scripts/validation/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON],
        [PYTHON, "scripts/validation/validate_v5_scaffold.py"],
        [
            PYTHON,
            "topology-tools/check-capability-contract.py",
            "--topology",
            "topology/topology.yaml",
            "--classes-dir",
            "topology/class-modules",
            "--objects-dir",
            "topology/object-modules",
        ],
        [
            PYTHON,
            "topology-tools/compile-topology.py",
            "--topology",
            "topology/topology.yaml",
            "--strict-model-lock",
            "--secrets-mode",
            secrets_mode,
        ],
    ]
    governance_mode = os.environ.get("ADR0088_GOVERNANCE_MODE", "enforce").strip().lower()
    if governance_mode not in {"warn", "enforce"}:
        governance_mode = "enforce"
    commands.append(
        [
            PYTHON,
            "scripts/validation/validate_adr0088_governance.py",
            "--diagnostics-json",
            "build/diagnostics/report.json",
            "--output-json",
            ADR0088_GOVERNANCE_REPORT_JSON,
            "--mode",
            governance_mode,
        ]
    )
    return commands


def _run_validate_v5_with_mode(
    secrets_mode: str, *, step_timeout: float | None = None, collect_all_errors: bool = False
) -> None:
    _run_steps(
        _validate_v5_commands(secrets_mode),
        timeout=step_timeout,
        collect_all_errors=collect_all_errors,
    )


def _assert_workspace_layout() -> None:
    legacy_present = [name for name in LEGACY_ROOT_DIRS if (ROOT / name).exists()]
    if not legacy_present:
        return
    joined = ", ".join(legacy_present)
    raise RuntimeError(f"Legacy root directories detected: {joined}. Remove them before running lane commands.")


def validate_v5(*, step_timeout: float | None = None, collect_all_errors: bool = False) -> None:
    _run_validate_v5_with_mode(
        _resolve_secrets_mode(),
        step_timeout=step_timeout,
        collect_all_errors=collect_all_errors,
    )


def validate_v5_passthrough(*, step_timeout: float | None = None, collect_all_errors: bool = False) -> None:
    _run_validate_v5_with_mode(
        "passthrough",
        step_timeout=step_timeout,
        collect_all_errors=collect_all_errors,
    )


def build_v5(*, step_timeout: float | None = None, collect_all_errors: bool = False) -> None:
    for output_dir in ("generated", "build", "dist"):
        (ROOT / output_dir).mkdir(parents=True, exist_ok=True)
    validate_v5(step_timeout=step_timeout, collect_all_errors=collect_all_errors)
    print(
        "[lane] INFO: build emitted generator artifacts under generated/ (including docs + ansible + object generators)."
    )


def phase1_gate(*, step_timeout: float | None = None) -> None:
    # NOTE: phase1 gate validates archived legacy migration assets only.
    run([PYTHON, "scripts/validation/validate_phase1_gate.py", "--report-json", PHASE1_REPORT_JSON], timeout=step_timeout)


def validate_v5_layers(*, step_timeout: float | None = None) -> None:
    # NOTE: export helper remains legacy-only and is not part of ADR0071 runtime.
    run([PYTHON, "scripts/validation/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON], timeout=step_timeout)


def export_v5_bindings(*, step_timeout: float | None = None) -> None:
    """Export instance bindings from v4-to-v5-mapping.yaml (migration use only)."""
    run([PYTHON, "scripts/model/export_v5_instance_bindings.py"], timeout=step_timeout)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lane-specific commands.")
    parser.add_argument(
        "command",
        choices=(
            "validate-v5",
            "validate-v5-passthrough",
            "build-v5",
            "phase1-gate",
            "validate-v5-layers",
            "export-v5-bindings",
        ),
        help="Lane command to run.",
    )
    parser.add_argument(
        "--step-timeout",
        type=float,
        default=None,
        help="Per-step subprocess timeout in seconds.",
    )
    parser.add_argument(
        "--collect-all-errors",
        action="store_true",
        help="Continue validate/build lane steps after failures and report all failed commands at the end.",
    )
    return parser.parse_args(argv)


def _classify_lane_failure(exc: Exception) -> LaneExitCode:
    if isinstance(exc, LaneAggregateError):
        return LaneExitCode.INFRA_ERROR if exc.has_timeout else LaneExitCode.VALIDATION_ERROR
    if isinstance(exc, subprocess.TimeoutExpired):
        return LaneExitCode.INFRA_ERROR
    if isinstance(exc, subprocess.CalledProcessError):
        return LaneExitCode.VALIDATION_ERROR
    if isinstance(exc, RuntimeError) and "Legacy root directories detected:" in str(exc):
        return LaneExitCode.VALIDATION_ERROR
    return LaneExitCode.INFRA_ERROR


def _emit_failure(exc: Exception) -> LaneExitCode:
    exit_code = _classify_lane_failure(exc)
    if isinstance(exc, LaneAggregateError):
        print(f"[lane] FAIL: {exc}", file=sys.stderr, flush=True)
        for failure in exc.failures:
            print(f"[lane] FAIL: {failure}", file=sys.stderr, flush=True)
        print(f"[lane] EXIT: {exit_code.name} ({int(exit_code)})", file=sys.stderr, flush=True)
        return exit_code

    print(f"[lane] FAIL: {exc}", file=sys.stderr, flush=True)
    print(f"[lane] EXIT: {exit_code.name} ({int(exit_code)})", file=sys.stderr, flush=True)
    return exit_code


def main() -> int:
    args = parse_args()
    handlers = {
        "validate-v5": lambda: validate_v5(
            step_timeout=args.step_timeout,
            collect_all_errors=args.collect_all_errors,
        ),
        "validate-v5-passthrough": lambda: validate_v5_passthrough(
            step_timeout=args.step_timeout,
            collect_all_errors=args.collect_all_errors,
        ),
        "build-v5": lambda: build_v5(
            step_timeout=args.step_timeout,
            collect_all_errors=args.collect_all_errors,
        ),
        "phase1-gate": lambda: phase1_gate(step_timeout=args.step_timeout),
        "validate-v5-layers": lambda: validate_v5_layers(step_timeout=args.step_timeout),
        "export-v5-bindings": lambda: export_v5_bindings(step_timeout=args.step_timeout),
    }
    try:
        _assert_workspace_layout()
        handlers[args.command]()
    except (LaneAggregateError, subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as exc:
        return int(_emit_failure(exc))
    return int(LaneExitCode.OK)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Lane-specific command dispatcher."""

from __future__ import annotations

import argparse
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


def run(cmd: list[str]) -> None:
    print(f"[lane] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def _resolve_secrets_mode() -> str:
    value = os.environ.get("V5_SECRETS_MODE", "inject").strip().lower()
    if value in SUPPORTED_SECRETS_MODES:
        return value
    return "inject"


def _run_validate_v5_with_mode(secrets_mode: str) -> None:
    if secrets_mode not in SUPPORTED_SECRETS_MODES:
        raise ValueError(f"Unsupported secrets mode: {secrets_mode}")
    # NOTE: canonical instance source is ADR0071 shards under project manifest instances_root.
    # export_v5_instance_bindings.py is legacy migration helper only.
    run([PYTHON, "scripts/validation/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON])
    run([PYTHON, "scripts/validation/validate_v5_scaffold.py"])
    run(
        [
            PYTHON,
            "topology-tools/check-capability-contract.py",
            "--topology",
            "topology/topology.yaml",
            "--classes-dir",
            "topology/class-modules",
            "--objects-dir",
            "topology/object-modules",
        ]
    )
    run(
        [
            PYTHON,
            "topology-tools/compile-topology.py",
            "--topology",
            "topology/topology.yaml",
            "--strict-model-lock",
            "--secrets-mode",
            secrets_mode,
        ]
    )
    governance_mode = os.environ.get("ADR0088_GOVERNANCE_MODE", "enforce").strip().lower()
    if governance_mode not in {"warn", "enforce"}:
        governance_mode = "enforce"
    run(
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


def _assert_workspace_layout() -> None:
    legacy_present = [name for name in LEGACY_ROOT_DIRS if (ROOT / name).exists()]
    if not legacy_present:
        return
    joined = ", ".join(legacy_present)
    raise RuntimeError(f"Legacy root directories detected: {joined}. Remove them before running lane commands.")


def validate_v5() -> None:
    _run_validate_v5_with_mode(_resolve_secrets_mode())


def validate_v5_passthrough() -> None:
    _run_validate_v5_with_mode("passthrough")


def build_v5() -> None:
    for output_dir in ("generated", "build", "dist"):
        (ROOT / output_dir).mkdir(parents=True, exist_ok=True)
    validate_v5()
    print(
        "[lane] INFO: build emitted generator artifacts under generated/ (including docs + ansible + object generators)."
    )


def phase1_gate() -> None:
    # NOTE: phase1 gate validates archived legacy migration assets only.
    run([PYTHON, "scripts/validation/validate_phase1_gate.py", "--report-json", PHASE1_REPORT_JSON])


def validate_v5_layers() -> None:
    # NOTE: export helper remains legacy-only and is not part of ADR0071 runtime.
    run([PYTHON, "scripts/validation/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON])


def export_v5_bindings() -> None:
    """Export instance bindings from v4-to-v5-mapping.yaml (migration use only)."""
    run([PYTHON, "scripts/model/export_v5_instance_bindings.py"])


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _assert_workspace_layout()
    handlers = {
        "validate-v5": validate_v5,
        "validate-v5-passthrough": validate_v5_passthrough,
        "build-v5": build_v5,
        "phase1-gate": phase1_gate,
        "validate-v5-layers": validate_v5_layers,
        "export-v5-bindings": export_v5_bindings,
    }
    handlers[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

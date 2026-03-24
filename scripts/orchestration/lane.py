#!/usr/bin/env python3
"""Lane-specific command dispatcher."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable
PHASE1_REPORT_JSON = "build/diagnostics/phase1-gate-report.json"
LAYER_REPORT_JSON = "build/diagnostics/layer-contract-report.json"
SUPPORTED_SECRETS_MODES = {"inject", "passthrough", "strict"}


def run(cmd: list[str]) -> None:
    print(f"[lane] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def _resolve_secrets_mode() -> str:
    value = os.environ.get("V5_SECRETS_MODE", "inject").strip().lower()
    if value in SUPPORTED_SECRETS_MODES:
        return value
    return "inject"


def validate_v5() -> None:
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
    secrets_mode = _resolve_secrets_mode()
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
    handlers = {
        "validate-v5": validate_v5,
        "build-v5": build_v5,
        "phase1-gate": phase1_gate,
        "validate-v5-layers": validate_v5_layers,
        "export-v5-bindings": export_v5_bindings,
    }
    handlers[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

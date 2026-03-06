#!/usr/bin/env python3
"""Lane-specific command dispatcher for v4/v5 migration workflows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
PHASE1_REPORT_JSON = "v5-build/diagnostics/phase1-gate-report.json"
LAYER_REPORT_JSON = "v5-build/diagnostics/layer-contract-report.json"


def run(cmd: list[str]) -> None:
    print(f"[lane] RUN: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def validate_v4() -> None:
    run(
        [
            PYTHON,
            "v4/topology-tools/validate-topology.py",
            "--topology",
            "v4/topology.yaml",
            "--strict",
            "--no-topology-cache",
        ]
    )
    run(
        [
            PYTHON,
            "v4/topology-tools/compile-topology.py",
            "--topology",
            "v4/topology.yaml",
            "--strict-model-lock",
        ]
    )


def build_v4() -> None:
    run(
        [
            PYTHON,
            "v4/topology-tools/regenerate-all.py",
            "--topology",
            "v4/topology.yaml",
            "--strict",
            "--skip-mermaid-validate",
            "--no-topology-cache",
        ]
    )


def validate_v5() -> None:
    run([PYTHON, "v5/scripts/export_v5_instance_bindings.py"])
    run([PYTHON, "v5/scripts/validate_phase1_gate.py", "--report-json", PHASE1_REPORT_JSON])
    run([PYTHON, "v5/scripts/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON])
    run([PYTHON, "v5/scripts/validate_v5_scaffold.py"])
    run(
        [
            PYTHON,
            "v5/topology-tools/compile-topology.py",
            "--topology",
            "v5/topology/topology.yaml",
            "--strict-model-lock",
        ]
    )


def build_v5() -> None:
    for output_dir in ("v5-generated", "v5-build", "v5-dist"):
        (ROOT / output_dir).mkdir(parents=True, exist_ok=True)
    validate_v5()
    print("[lane] INFO: v5 build currently compiles canonical JSON; generators are introduced in later phases.")


def phase1_gate() -> None:
    run([PYTHON, "v5/scripts/export_v5_instance_bindings.py"])
    run([PYTHON, "v5/scripts/validate_phase1_gate.py", "--report-json", PHASE1_REPORT_JSON])


def validate_v5_layers() -> None:
    run([PYTHON, "v5/scripts/export_v5_instance_bindings.py"])
    run([PYTHON, "v5/scripts/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lane-specific migration commands.")
    parser.add_argument(
        "command",
        choices=("validate-v4", "validate-v5", "build-v4", "build-v5", "phase1-gate", "validate-v5-layers"),
        help="Lane command to run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    handlers = {
        "validate-v4": validate_v4,
        "validate-v5": validate_v5,
        "build-v4": build_v4,
        "build-v5": build_v5,
        "phase1-gate": phase1_gate,
        "validate-v5-layers": validate_v5_layers,
    }
    handlers[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

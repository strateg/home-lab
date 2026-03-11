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

# Global flag for plugin execution (ADR 0063)
ENABLE_PLUGINS = False


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
    # NOTE: canonical instance source is ADR0071 shards under paths.instances_root.
    # export_v5_instance_bindings.py is legacy migration helper only.
    run([PYTHON, "v5/scripts/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON])
    run([PYTHON, "v5/scripts/validate_v5_scaffold.py"])
    run(
        [
            PYTHON,
            "v5/topology-tools/check-capability-contract.py",
            "--topology",
            "v5/topology/topology.yaml",
            "--classes-dir",
            "v5/topology/class-modules/classes",
            "--objects-dir",
            "v5/topology/object-modules/objects",
        ]
    )
    compile_cmd = [
        PYTHON,
        "v5/topology-tools/compile-topology.py",
        "--topology",
        "v5/topology/topology.yaml",
        "--strict-model-lock",
    ]
    if ENABLE_PLUGINS:
        compile_cmd.append("--enable-plugins")
    run(compile_cmd)


def build_v5() -> None:
    for output_dir in ("v5-generated", "v5-build", "v5-dist"):
        (ROOT / output_dir).mkdir(parents=True, exist_ok=True)
    validate_v5()
    print("[lane] INFO: v5 build currently compiles canonical JSON; generators are introduced in later phases.")


def phase1_gate() -> None:
    # NOTE: phase1 gate validates archived legacy migration assets only.
    run([PYTHON, "v5/scripts/validate_phase1_gate.py", "--report-json", PHASE1_REPORT_JSON])


def validate_v5_layers() -> None:
    # NOTE: export helper remains legacy-only and is not part of ADR0071 runtime.
    run([PYTHON, "v5/scripts/validate_v5_layer_contract.py", "--report-json", LAYER_REPORT_JSON])


def export_v5_bindings() -> None:
    """Export instance bindings from v4-to-v5-mapping.yaml (migration use only)."""
    run([PYTHON, "v5/scripts/export_v5_instance_bindings.py"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lane-specific migration commands.")
    parser.add_argument(
        "command",
        choices=(
            "validate-v4",
            "validate-v5",
            "build-v4",
            "build-v5",
            "phase1-gate",
            "validate-v5-layers",
            "export-v5-bindings",
        ),
        help="Lane command to run.",
    )
    parser.add_argument(
        "--enable-plugins",
        action="store_true",
        help="Enable plugin execution in v5 compiler (ADR 0063).",
    )
    return parser.parse_args()


def main() -> int:
    global ENABLE_PLUGINS
    args = parse_args()
    ENABLE_PLUGINS = args.enable_plugins
    handlers = {
        "validate-v4": validate_v4,
        "validate-v5": validate_v5,
        "build-v4": build_v4,
        "build-v5": build_v5,
        "phase1-gate": phase1_gate,
        "validate-v5-layers": validate_v5_layers,
        "export-v5-bindings": export_v5_bindings,
    }
    handlers[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

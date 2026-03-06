#!/usr/bin/env python3
"""Lane-specific command dispatcher for v4/v5 migration workflows."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


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
    run([PYTHON, "scripts/export_v5_instance_bindings.py"])
    run([PYTHON, "scripts/validate_v5_scaffold.py"])
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run lane-specific migration commands.")
    parser.add_argument(
        "command",
        choices=("validate-v4", "validate-v5", "build-v4", "build-v5"),
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
    }
    handlers[args.command]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

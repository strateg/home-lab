#!/usr/bin/env python3
"""Run quality gates for acceptance TUC directories."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run acceptance TUC quality gates.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("acceptance-testing"),
        help="Acceptance testing root directory (default: acceptance-testing).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root
    gates = sorted(path for path in root.glob("TUC-*/quality-gate.py") if path.is_file())
    print(f"Found {len(gates)} quality gates")
    exit_code = 0
    for gate_path in gates:
        print(f"==> {gate_path.parent.name}")
        run = subprocess.run([sys.executable, str(gate_path)], text=True, capture_output=True, check=False)
        if run.stdout:
            print(run.stdout, end="")
        if run.stderr:
            print(run.stderr, end="", file=sys.stderr)
        if run.returncode != 0:
            exit_code = run.returncode
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Compatibility alias for assembling the native execution workspace."""

from __future__ import annotations

import argparse
import sys

from utils.native_workspace import NATIVE_WORK_ROOT, TARGET_CHOICES, assemble_native_workspace, print_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compatibility alias for assemble-native.py (ADR 0056 native workspace assembly)"
    )
    parser.add_argument(
        "--target",
        choices=TARGET_CHOICES,
        help="Assemble a single native target",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    report = assemble_native_workspace(target=args.target)
    if not args.quiet:
        title = "Native Workspace Assembler (compat alias: materialize-native-inputs)"
        if args.target:
            title = f"{title} - {args.target}"
        print_report(title, report, NATIVE_WORK_ROOT)

    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()

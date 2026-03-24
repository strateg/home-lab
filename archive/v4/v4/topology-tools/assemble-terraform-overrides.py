#!/usr/bin/env python3
"""Apply tracked Terraform overrides onto native workspace execution roots."""

from __future__ import annotations

import argparse
import sys

from utils.terraform_overrides import TARGETS, apply_overrides


def assemble(target: str | None, verbose: bool) -> int:
    """Apply overrides for one target or all targets."""
    targets = [target] if target else sorted(TARGETS)
    errors: list[str] = []

    if verbose:
        print("=" * 70)
        print("Terraform Override Assembler (ADR 0055)")
        print("=" * 70)

    for current in targets:
        destination_root = TARGETS[current]
        report = apply_overrides(current, destination_root)
        errors.extend(report.errors)

        if verbose:
            print(f"Target: {current}")
            print(f"  destination: {destination_root}")
            if report.copied:
                print("  copied:")
                for source, destination in report.copied:
                    print(f"    - {source} -> {destination}")
            if report.skipped:
                print("  skipped:")
                for item in report.skipped:
                    print(f"    - {item}")
            if report.errors:
                print("  errors:")
                for item in report.errors:
                    print(f"    - {item}")

    if verbose:
        print("=" * 70)

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply tracked Terraform overrides to native workspace roots")
    parser.add_argument("--target", choices=sorted(TARGETS), help="Single target to assemble")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress summary output")
    args = parser.parse_args()
    sys.exit(assemble(target=args.target, verbose=not args.quiet))


if __name__ == "__main__":
    main()

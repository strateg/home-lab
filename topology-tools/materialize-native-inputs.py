#!/usr/bin/env python3
"""Copy canonical local inputs into native execution roots."""

from __future__ import annotations

import argparse
import sys

from utils.local_inputs import REPO_ROOT, materialize_native_local_inputs, print_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize native local inputs from canonical local roots")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    report = materialize_native_local_inputs(REPO_ROOT)
    if not args.quiet:
        print_report("Native Input Materializer (ADR 0054)", report, REPO_ROOT / "generated")

    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()

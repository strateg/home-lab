#!/usr/bin/env python3
"""Copy package-local dist inputs from canonical local roots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from utils.local_inputs import CopyMapping, copy_mappings, materialize_dist_local_inputs, print_report

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIST = REPO_ROOT / "v4-dist"


def materialize_inputs(dist_root: Path, verbose: bool) -> int:
    """Copy known local inputs into dist package roots."""
    report = materialize_dist_local_inputs(dist_root)
    report.extend(
        copy_mappings(
            [
                CopyMapping(
                    source=REPO_ROOT / "ansible" / ".vault_pass",
                    target=dist_root / "control" / "ansible" / ".vault_pass",
                ),
                CopyMapping(
                    source=REPO_ROOT / "ansible" / "group_vars" / "all" / "vault.yml",
                    target=dist_root / "control" / "ansible" / "group_vars" / "all" / "vault.yml",
                ),
            ]
        )
    )

    if verbose:
        print_report("Dist Input Materializer (ADR 0053/0054)", report, dist_root)

    return 1 if report.errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize dist local inputs from canonical local roots")
    parser.add_argument(
        "--dist",
        type=Path,
        default=DEFAULT_DIST,
        help="Path to dist root",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress summary output",
    )
    args = parser.parse_args()

    sys.exit(materialize_inputs(dist_root=args.dist, verbose=not args.quiet))


if __name__ == "__main__":
    main()

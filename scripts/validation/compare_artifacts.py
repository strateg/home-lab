#!/usr/bin/env python3
"""Compare two generated artifact trees, excluding declared non-semantic fields.

A parity claim needs a procedure. The obvious one is invalid: generated output is
gitignored and untracked, so `git status` reports nothing about it whatever the
artifacts do. This compares content instead, and states what it excluded.

Two kinds of difference are not semantic and are excluded by name rather than by
judgement:

* `generated_at` in the artifact manifest, and the digests it records for
  `build/effective-topology.json` and `.yaml`, whose content embeds a timestamp.
* Nothing else. Every other difference is reported.

Files that vary for reasons the pipeline has not yet fixed are reported, not
excluded: see W13 in the implementation plan, where obsolete detection scans the
live output directory while sibling generators write into it, so the
`.state/artifact-plans` entries depend on execution order.

Usage:
    compare_artifacts.py BASELINE_DIR CANDIDATE_DIR [--json report.json]

Exit status is 0 when the trees match outside the exclusions, 1 when they differ,
and 2 on a usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Paths whose byte content legitimately varies between runs of identical sources.
# Each entry names why. Adding one is a decision, not a convenience.
NON_SEMANTIC_FILES: dict[str, str] = {
    "home-lab/artifact-manifest.json": (
        "carries generated_at and the digests of build/effective-topology.json and .yaml, "
        "which embed timestamps of their own"
    ),
}

# Within an otherwise compared JSON file, keys that carry run time rather than content.
NON_SEMANTIC_KEYS: tuple[str, ...] = ("generated_at", "compiled_at")


def _hash_tree(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def compare(baseline: Path, candidate: Path) -> dict[str, Any]:
    left, right = _hash_tree(baseline), _hash_tree(candidate)

    changed = sorted(k for k in set(left) & set(right) if left[k] != right[k])
    excluded = [k for k in changed if k in NON_SEMANTIC_FILES]
    reported = [k for k in changed if k not in NON_SEMANTIC_FILES]

    return {
        "baseline": str(baseline),
        "candidate": str(candidate),
        "files_compared": len(set(left) | set(right)),
        "removed": sorted(set(left) - set(right)),
        "added": sorted(set(right) - set(left)),
        "changed": reported,
        "excluded_as_non_semantic": {k: NON_SEMANTIC_FILES[k] for k in excluded},
    }


def _render(report: dict[str, Any]) -> str:
    lines = [
        f"compared {report['files_compared']} files",
        f"  {str(report['baseline'])} -> {str(report['candidate'])}",
    ]
    for label, key in (("removed", "removed"), ("added", "added"), ("changed", "changed")):
        for path in report[key]:
            lines.append(f"  {label:8} {path}")
    for path, reason in report["excluded_as_non_semantic"].items():
        lines.append(f"  excluded {path}  ({reason})")
    if not (report["removed"] or report["added"] or report["changed"]):
        lines.append("  PARITY: identical outside the declared exclusions")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--json", type=Path, help="write the report as JSON")
    args = parser.parse_args()

    for directory in (args.baseline, args.candidate):
        if not directory.is_dir():
            print(f"not a directory: {directory}", file=sys.stderr)
            return 2

    report = compare(args.baseline, args.candidate)
    print(_render(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    return 1 if (report["removed"] or report["added"] or report["changed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())

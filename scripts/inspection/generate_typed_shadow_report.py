#!/usr/bin/env python3
"""Generate ADR0095 typed-shadow coverage diagnostics artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_indexes import filter_instances as _filter_instances  # noqa: E402
from inspection_indexes import flatten_instances as _flatten_instances  # noqa: E402
from inspection_loader import load_effective as _load_effective  # noqa: E402
from inspection_typed_shadow_report import build_typed_shadow_report as _build_typed_shadow_report  # noqa: E402
from inspection_typed_shadow_report import typed_shadow_report_text as _typed_shadow_report_text  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ADR0095 typed-shadow diagnostics artifacts.")
    parser.add_argument(
        "--effective",
        default="build/effective-topology.json",
        help="Path to effective topology JSON (default: build/effective-topology.json)",
    )
    parser.add_argument("--layer", help="Optional layer filter.")
    parser.add_argument("--group", help="Optional instance group filter.")
    parser.add_argument(
        "--json-output",
        default="build/diagnostics/typed-shadow-report.json",
        help="JSON diagnostics artifact path (default: build/diagnostics/typed-shadow-report.json)",
    )
    parser.add_argument(
        "--text-output",
        default="build/diagnostics/typed-shadow-report.txt",
        help="Text diagnostics artifact path (default: build/diagnostics/typed-shadow-report.txt)",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=95.0,
        help="Minimum edge classification coverage percent gate threshold (default: 95.0)",
    )
    parser.add_argument(
        "--max-generic-share",
        type=float,
        default=40.0,
        help="Maximum generic_ref share percent gate threshold (default: 40.0)",
    )
    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Exit with code 2 when G2 gate thresholds fail.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    effective_path = Path(args.effective)
    json_output = Path(args.json_output)
    text_output = Path(args.text_output)

    payload = _load_effective(effective_path)
    instances = _filter_instances(
        _flatten_instances(payload),
        layer=args.layer,
        group=args.group,
    )

    report = _build_typed_shadow_report(
        instances,
        min_coverage_percent=args.min_coverage,
        max_generic_share_percent=args.max_generic_share,
    )
    report["command"] = "typed-shadow-report"
    report["inputs"] = {
        "effective": str(effective_path),
        "layer": args.layer,
        "group": args.group,
        "instance_count": len(instances),
    }

    text_body = _typed_shadow_report_text(report)

    json_output.parent.mkdir(parents=True, exist_ok=True)
    text_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text_output.write_text(text_body, encoding="utf-8")

    print(f"Wrote typed-shadow JSON report: {json_output}")
    print(f"Wrote typed-shadow text report: {text_output}")

    if args.fail_on_threshold and not bool(report.get("gates", {}).get("g2_pass")):
        print("Typed-shadow thresholds failed (see diagnostics artifacts for details).")
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"[inspect][error] {error}", file=sys.stderr)
        raise SystemExit(2) from error

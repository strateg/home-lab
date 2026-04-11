#!/usr/bin/env python3
"""Run ADR0095 inspection smoke matrix and emit diagnostics artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
INSPECT_SCRIPT = SCRIPT_DIR / "inspect_topology.py"


SMOKE_MATRIX_SCHEMA_VERSION = "adr0095.inspect.smoke-matrix.v1"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ADR0095 inspect smoke matrix.")
    parser.add_argument(
        "--effective",
        default="build/effective-topology.json",
        help="Path to effective topology JSON (default: build/effective-topology.json)",
    )
    parser.add_argument(
        "--query",
        default="mikrotik",
        help="Search query for the smoke `search` command (default: mikrotik)",
    )
    parser.add_argument(
        "--instance",
        default="rtr-mikrotik-chateau",
        help="Instance/source reference for the smoke `deps` command (default: rtr-mikrotik-chateau)",
    )
    parser.add_argument(
        "--json-output",
        default="build/diagnostics/inspect-smoke-matrix.json",
        help="JSON diagnostics output path (default: build/diagnostics/inspect-smoke-matrix.json)",
    )
    parser.add_argument(
        "--text-output",
        default="build/diagnostics/inspect-smoke-matrix.txt",
        help="Text diagnostics output path (default: build/diagnostics/inspect-smoke-matrix.txt)",
    )
    parser.add_argument(
        "--dot-output",
        default="build/diagnostics/topology-instance-deps-smoke.dot",
        help="DOT output path used by smoke deps-dot command (default: build/diagnostics/topology-instance-deps-smoke.dot)",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Return success even when one or more smoke commands fail.",
    )
    return parser.parse_args()


def _command_matrix(*, effective: Path, query: str, instance_ref: str, dot_output: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": "summary",
            "args": [str(INSPECT_SCRIPT), "summary", "--effective", str(effective)],
        },
        {
            "name": "classes",
            "args": [str(INSPECT_SCRIPT), "classes", "--effective", str(effective)],
        },
        {
            "name": "objects",
            "args": [str(INSPECT_SCRIPT), "objects", "--effective", str(effective)],
        },
        {
            "name": "instances",
            "args": [str(INSPECT_SCRIPT), "instances", "--effective", str(effective)],
        },
        {
            "name": "search",
            "args": [str(INSPECT_SCRIPT), "search", "--query", query, "--effective", str(effective)],
        },
        {
            "name": "deps",
            "args": [str(INSPECT_SCRIPT), "deps", "--instance", instance_ref, "--effective", str(effective)],
        },
        {
            "name": "deps-dot",
            "args": [
                str(INSPECT_SCRIPT),
                "deps-dot",
                "--effective",
                str(effective),
                "--output",
                str(dot_output),
            ],
        },
        {
            "name": "capability-packs",
            "args": [str(INSPECT_SCRIPT), "capability-packs", "--effective", str(effective)],
        },
    ]


def _preview(text: str, *, max_lines: int = 10, max_chars: int = 600) -> str:
    lines = text.splitlines()[:max_lines]
    compact = "\n".join(lines)
    if len(compact) > max_chars:
        return compact[: max_chars - 3] + "..."
    return compact


def _render_text_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "ADR0095 Inspect Smoke Matrix",
        "============================",
        f"schema_version: {report.get('schema_version', '-')}",
        f"timestamp_utc: {report.get('timestamp_utc', '-')}",
        f"effective: {report.get('effective', '-')}",
        f"query: {report.get('query', '-')}",
        f"instance: {report.get('instance', '-')}",
        "",
        "Summary",
        "-------",
        f"total: {summary.get('total', 0)}",
        f"passed: {summary.get('passed', 0)}",
        f"failed: {summary.get('failed', 0)}",
        f"status: {summary.get('status', 'UNKNOWN')}",
        "",
        "Commands",
        "--------",
    ]
    for row in report.get("commands", []):
        lines.extend(
            [
                f"- {row.get('name')}: {row.get('status')} (rc={row.get('return_code')}, duration_ms={row.get('duration_ms')})",
                f"  cmd: {' '.join(row.get('command', []))}",
            ]
        )
        out_preview = row.get("stdout_preview") or ""
        err_preview = row.get("stderr_preview") or ""
        if out_preview:
            lines.append("  stdout:")
            for ln in out_preview.splitlines():
                lines.append(f"    {ln}")
        if err_preview:
            lines.append("  stderr:")
            for ln in err_preview.splitlines():
                lines.append(f"    {ln}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()

    effective = Path(args.effective)
    json_output = Path(args.json_output)
    text_output = Path(args.text_output)
    dot_output = Path(args.dot_output)

    matrix = _command_matrix(
        effective=effective,
        query=args.query,
        instance_ref=args.instance,
        dot_output=dot_output,
    )

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    for row in matrix:
        started = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, *row["args"]],
            capture_output=True,
            text=True,
            check=False,
        )
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        status = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode == 0:
            passed += 1
        else:
            failed += 1
        results.append(
            {
                "name": row["name"],
                "status": status,
                "return_code": proc.returncode,
                "duration_ms": duration_ms,
                "command": [sys.executable, *row["args"]],
                "stdout_preview": _preview(proc.stdout),
                "stderr_preview": _preview(proc.stderr),
            }
        )

    report = {
        "schema_version": SMOKE_MATRIX_SCHEMA_VERSION,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "effective": str(effective),
        "query": args.query,
        "instance": args.instance,
        "dot_output": str(dot_output),
        "commands": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "status": "PASS" if failed == 0 else "FAIL",
        },
    }

    json_output.parent.mkdir(parents=True, exist_ok=True)
    text_output.parent.mkdir(parents=True, exist_ok=True)
    if dot_output.parent:
        dot_output.parent.mkdir(parents=True, exist_ok=True)

    json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text_output.write_text(_render_text_report(report), encoding="utf-8")

    print(f"Wrote inspect smoke matrix JSON report: {json_output}")
    print(f"Wrote inspect smoke matrix text report: {text_output}")
    print(f"Smoke summary: passed={passed} failed={failed} total={len(results)}")

    if failed > 0 and not args.allow_failures:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as error:
        print(f"[inspect][error] {error}", file=sys.stderr)
        raise SystemExit(2) from error


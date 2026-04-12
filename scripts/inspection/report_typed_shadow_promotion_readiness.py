#!/usr/bin/env python3
"""Report typed-shadow semantic promotion readiness for ADR0095."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_indexes import filter_instances as _filter_instances  # noqa: E402
from inspection_indexes import flatten_instances as _flatten_instances  # noqa: E402
from inspection_loader import load_effective as _load_effective  # noqa: E402
from inspection_typed_shadow_report import build_typed_shadow_report as _build_typed_shadow_report  # noqa: E402

READINESS_SCHEMA_VERSION = "adr0095.inspect.typed-shadow-promotion-readiness.v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _file_contains(path: Path, token: str) -> bool:
    if not path.exists():
        return False
    return token in path.read_text(encoding="utf-8")


def _gate_g1_contract_stability(repo_root: Path) -> dict[str, Any]:
    checks = [
        {
            "id": "g1-001",
            "desc": "relation typing contract tests exist",
            "ok": _file_contains(
                repo_root / "tests" / "test_inspection_relations.py",
                "test_infer_relation_type_classifies_common_domains",
            ),
        },
        {
            "id": "g1-002",
            "desc": "deps payload typed-shadow parity guard exists",
            "ok": _file_contains(
                repo_root / "tests" / "test_inspection_json.py",
                "test_deps_payload_typed_shadow_preserves_baseline_edge_contract",
            ),
        },
        {
            "id": "g1-003",
            "desc": "CLI typed-shadow parity guard exists",
            "ok": _file_contains(
                repo_root / "tests" / "test_inspect_topology.py",
                "test_deps_command_json_typed_shadow_preserves_baseline_edges",
            ),
        },
    ]
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _gate_g2_coverage(typed_shadow_report: dict[str, Any]) -> dict[str, Any]:
    gates = typed_shadow_report.get("gates", {}) if isinstance(typed_shadow_report, dict) else {}
    edge_counts = typed_shadow_report.get("edge_counts", {}) if isinstance(typed_shadow_report, dict) else {}
    return {
        "ok": bool(gates.get("g2_pass")),
        "checks": [
            {
                "id": "g2-001",
                "desc": "typed-shadow threshold gate passes",
                "ok": bool(gates.get("g2_pass")),
                "coverage_percent": edge_counts.get("coverage_percent"),
                "generic_ref_share_percent": typed_shadow_report.get("generic_ref_share_percent"),
            }
        ],
    }


def _gate_g3_error_drift_safety(repo_root: Path) -> dict[str, Any]:
    checks = [
        {
            "id": "g3-001",
            "desc": "JSON parity guard test exists",
            "ok": _file_contains(
                repo_root / "tests" / "test_inspection_json.py",
                "test_deps_payload_typed_shadow_preserves_baseline_edge_contract",
            ),
        },
        {
            "id": "g3-002",
            "desc": "CLI parity guard test exists",
            "ok": _file_contains(
                repo_root / "tests" / "test_inspect_topology.py",
                "test_deps_command_json_typed_shadow_preserves_baseline_edges",
            ),
        },
        {
            "id": "g3-003",
            "desc": "typed-shadow threshold gate task exists",
            "ok": _file_contains(repo_root / "taskfiles" / "validate.yml", "typed-shadow-gate"),
        },
    ]
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _gate_g4_operator_usability(repo_root: Path) -> dict[str, Any]:
    manual_path = repo_root / "manuals" / "dev-plane" / "DEV-COMMAND-REFERENCE.md"
    checks = [
        {
            "id": "g4-001",
            "desc": "manual documents non-authoritative shadow semantics",
            "ok": _file_contains(manual_path, "non-authoritative"),
        },
        {
            "id": "g4-002",
            "desc": "manual explains generic_ref interpretation",
            "ok": _file_contains(manual_path, "generic_ref"),
        },
    ]
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _gate_g5_adr_sync(repo_root: Path) -> dict[str, Any]:
    adr_path = repo_root / "adr" / "0095-topology-inspection-and-introspection-toolkit.md"
    plan_path = repo_root / "adr" / "0095-analysis" / "IMPLEMENTATION-PLAN.md"
    criteria_path = repo_root / "adr" / "0095-analysis" / "SEMANTIC-TYPING-PROMOTION-CRITERIA.md"
    checks = [
        {
            "id": "g5-001",
            "desc": "ADR0095 records non-authoritative shadow status",
            "ok": _file_contains(adr_path, "non-authoritative"),
        },
        {
            "id": "g5-002",
            "desc": "implementation plan tracks promotion decision outstanding",
            "ok": _file_contains(plan_path, "promotion decision"),
        },
        {
            "id": "g5-003",
            "desc": "promotion criteria contains explicit decision rule",
            "ok": _file_contains(criteria_path, "Promotion Decision Rule"),
        },
    ]
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _typed_shadow_report_from_artifact_or_effective(
    *,
    typed_shadow_report_path: Path,
    effective_path: Path,
    layer: str | None,
    group: str | None,
) -> tuple[dict[str, Any], str]:
    if typed_shadow_report_path.exists():
        return (
            json.loads(typed_shadow_report_path.read_text(encoding="utf-8")),
            str(typed_shadow_report_path),
        )
    payload = _load_effective(effective_path)
    instances = _filter_instances(_flatten_instances(payload), layer=layer, group=group)
    return (
        _build_typed_shadow_report(instances),
        f"computed-from-effective:{effective_path}",
    )


def build_report(
    *,
    repo_root: Path,
    typed_shadow_report: dict[str, Any],
    typed_shadow_report_source: str,
) -> dict[str, Any]:
    gate_g1 = _gate_g1_contract_stability(repo_root)
    gate_g2 = _gate_g2_coverage(typed_shadow_report)
    gate_g3 = _gate_g3_error_drift_safety(repo_root)
    gate_g4 = _gate_g4_operator_usability(repo_root)
    gate_g5 = _gate_g5_adr_sync(repo_root)

    gate_map = {
        "g1_contract_stability": gate_g1,
        "g2_coverage_of_meaningful_edges": gate_g2,
        "g3_error_drift_safety": gate_g3,
        "g4_operator_usability": gate_g4,
        "g5_adr_sync": gate_g5,
    }
    ready_for_promotion = all(row["ok"] for row in gate_map.values())
    blockers = [gate_name for gate_name, row in gate_map.items() if not row["ok"]]

    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "typed_shadow_report_source": typed_shadow_report_source,
        "typed_shadow_report_snapshot": {
            "coverage_percent": typed_shadow_report.get("edge_counts", {}).get("coverage_percent"),
            "generic_ref_share_percent": typed_shadow_report.get("generic_ref_share_percent"),
            "g2_pass": typed_shadow_report.get("gates", {}).get("g2_pass"),
        },
        "gates": gate_map,
        "ready_for_promotion": ready_for_promotion,
        "blocking_gates": blockers,
        "recommended_next_step": (
            "Record promotion decision in ADR0095 artifacts."
            if ready_for_promotion
            else "Keep typed shadow non-authoritative and resolve blocking gates."
        ),
    }


def _render_text_report(report: dict[str, Any]) -> str:
    lines = [
        "ADR0095 Typed Shadow Promotion Readiness",
        "=======================================",
        f"schema_version: {report.get('schema_version', '-')}",
        f"generated_at_utc: {report.get('generated_at_utc', '-')}",
        f"typed_shadow_report_source: {report.get('typed_shadow_report_source', '-')}",
        "",
        "Typed Shadow Snapshot",
        "---------------------",
        f"coverage_percent: {report.get('typed_shadow_report_snapshot', {}).get('coverage_percent')}",
        f"generic_ref_share_percent: {report.get('typed_shadow_report_snapshot', {}).get('generic_ref_share_percent')}",
        f"g2_pass: {report.get('typed_shadow_report_snapshot', {}).get('g2_pass')}",
        "",
        "Gate Status",
        "-----------",
    ]
    gates = report.get("gates", {})
    for gate_name in (
        "g1_contract_stability",
        "g2_coverage_of_meaningful_edges",
        "g3_error_drift_safety",
        "g4_operator_usability",
        "g5_adr_sync",
    ):
        gate_payload = gates.get(gate_name, {})
        status = "PASS" if bool(gate_payload.get("ok")) else "FAIL"
        lines.append(f"- {gate_name}: {status}")
    lines.extend(
        [
            "",
            f"ready_for_promotion: {report.get('ready_for_promotion')}",
            f"blocking_gates: {', '.join(report.get('blocking_gates', [])) or 'none'}",
            f"recommended_next_step: {report.get('recommended_next_step', '-')}",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report typed-shadow semantic promotion readiness for ADR0095.")
    parser.add_argument(
        "--typed-shadow-report",
        default="build/diagnostics/typed-shadow-report.json",
        help="Typed-shadow diagnostics report path (default: build/diagnostics/typed-shadow-report.json)",
    )
    parser.add_argument(
        "--effective",
        default="build/effective-topology.json",
        help="Fallback effective topology path when typed-shadow report artifact is missing.",
    )
    parser.add_argument(
        "--layer", help="Optional layer filter used only when computing fallback typed-shadow snapshot."
    )
    parser.add_argument(
        "--group", help="Optional group filter used only when computing fallback typed-shadow snapshot."
    )
    parser.add_argument(
        "--output-json",
        default="build/diagnostics/typed-shadow-promotion-readiness.json",
        help="Readiness JSON output path.",
    )
    parser.add_argument(
        "--output-text",
        default="build/diagnostics/typed-shadow-promotion-readiness.txt",
        help="Readiness text output path.",
    )
    parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="Exit with code 2 when one or more promotion gates are not ready.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = _repo_root()

    typed_shadow_report, source = _typed_shadow_report_from_artifact_or_effective(
        typed_shadow_report_path=repo_root / args.typed_shadow_report,
        effective_path=repo_root / args.effective,
        layer=args.layer,
        group=args.group,
    )
    report = build_report(
        repo_root=repo_root,
        typed_shadow_report=typed_shadow_report,
        typed_shadow_report_source=source,
    )

    output_json = repo_root / args.output_json
    output_text = repo_root / args.output_text
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_text.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_text.write_text(_render_text_report(report), encoding="utf-8")

    print(f"Wrote typed-shadow promotion readiness JSON report: {output_json}")
    print(f"Wrote typed-shadow promotion readiness text report: {output_text}")
    print(
        "Readiness summary: "
        f"ready_for_promotion={report['ready_for_promotion']} "
        f"blocking_gates={len(report['blocking_gates'])}"
    )

    if args.fail_on_not_ready and not report["ready_for_promotion"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"[inspect][error] {error}", file=sys.stderr)
        raise SystemExit(2) from error

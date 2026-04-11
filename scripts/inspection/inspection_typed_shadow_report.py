#!/usr/bin/env python3
"""Typed-shadow diagnostics helpers for ADR0095 inspection flows."""

from __future__ import annotations

from collections import defaultdict
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inspection_relations import build_dependency_graph, infer_relation_type, typed_relation_shadow


TYPED_SHADOW_REPORT_SCHEMA_VERSION = "adr0095.inspect.deps.typed-shadow-report.v1"


def build_typed_shadow_report(
    instances: list[dict[str, Any]],
    *,
    min_coverage_percent: float = 95.0,
    max_generic_share_percent: float = 40.0,
) -> dict[str, Any]:
    """Build semantic typing shadow diagnostics report for dependency edges."""
    edges, unresolved, edge_labels = build_dependency_graph(instances)

    edge_keys = sorted(f"{source}->{target}" for source, targets in edges.items() for target in sorted(targets))
    shadow = typed_relation_shadow(edge_labels)

    edge_type_counts: dict[str, int] = defaultdict(int)
    label_type_counts: dict[str, int] = defaultdict(int)

    edge_rows: list[dict[str, Any]] = []
    edges_with_labels = 0
    classified_edges = 0
    for edge_key in edge_keys:
        labels = sorted(set(edge_labels.get(edge_key, [])))
        if labels:
            edges_with_labels += 1
        types = shadow.get(edge_key, [])
        if types:
            classified_edges += 1
        for relation_type in types:
            edge_type_counts[relation_type] += 1
        for label in labels:
            label_type_counts[infer_relation_type(label)] += 1
        edge_rows.append(
            {
                "edge": edge_key,
                "labels": labels,
                "types": types,
            }
        )

    total_edges = len(edge_keys)
    unclassified_edges = total_edges - classified_edges
    coverage_percent = 100.0 if total_edges == 0 else round((classified_edges / total_edges) * 100.0, 2)

    total_label_classifications = sum(label_type_counts.values())
    generic_ref_count = label_type_counts.get("generic_ref", 0)
    generic_ref_share_percent = (
        0.0
        if total_label_classifications == 0
        else round((generic_ref_count / total_label_classifications) * 100.0, 2)
    )

    g2_coverage_pass = coverage_percent >= min_coverage_percent
    g2_generic_share_pass = generic_ref_share_percent <= max_generic_share_percent

    unresolved_distinct = sorted({ref for refs in unresolved.values() for ref in refs})

    return {
        "schema_version": TYPED_SHADOW_REPORT_SCHEMA_VERSION,
        "edge_counts": {
            "total": total_edges,
            "with_labels": edges_with_labels,
            "classified_non_empty": classified_edges,
            "unclassified": unclassified_edges,
            "coverage_percent": coverage_percent,
        },
        "label_type_counts": dict(sorted(label_type_counts.items())),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "label_classifications_total": total_label_classifications,
        "generic_ref_count": generic_ref_count,
        "generic_ref_share_percent": generic_ref_share_percent,
        "unresolved": {
            "sources_with_unresolved_refs": len(unresolved),
            "total_unresolved_refs": sum(len(refs) for refs in unresolved.values()),
            "distinct_unresolved_refs": len(unresolved_distinct),
            "distinct_unresolved_ref_values": unresolved_distinct,
        },
        "thresholds": {
            "min_coverage_percent": min_coverage_percent,
            "max_generic_share_percent": max_generic_share_percent,
        },
        "gates": {
            "g2_coverage_pass": g2_coverage_pass,
            "g2_generic_share_pass": g2_generic_share_pass,
            "g2_pass": g2_coverage_pass and g2_generic_share_pass,
        },
        "edges": edge_rows,
    }


def typed_shadow_report_text(report: dict[str, Any]) -> str:
    """Render a compact human-readable typed-shadow report summary."""
    edge_counts = report.get("edge_counts", {})
    gates = report.get("gates", {})
    thresholds = report.get("thresholds", {})
    label_type_counts = report.get("label_type_counts", {})
    edge_type_counts = report.get("edge_type_counts", {})
    unresolved = report.get("unresolved", {})

    status = "PASS" if bool(gates.get("g2_pass")) else "FAIL"
    lines = [
        "ADR0095 Typed Shadow Coverage Report",
        "====================================",
        f"status: {status}",
        "",
        "Edge Coverage",
        "-------------",
        f"total edges: {edge_counts.get('total', 0)}",
        f"classified edges: {edge_counts.get('classified_non_empty', 0)}",
        f"unclassified edges: {edge_counts.get('unclassified', 0)}",
        f"coverage percent: {edge_counts.get('coverage_percent', 0.0)}",
        "",
        "Generic Share",
        "-------------",
        f"label classifications total: {report.get('label_classifications_total', 0)}",
        f"generic_ref count: {report.get('generic_ref_count', 0)}",
        f"generic_ref share percent: {report.get('generic_ref_share_percent', 0.0)}",
        "",
        "Thresholds",
        "----------",
        f"min coverage percent: {thresholds.get('min_coverage_percent', 95.0)}",
        f"max generic share percent: {thresholds.get('max_generic_share_percent', 40.0)}",
        f"gate g2 coverage: {'PASS' if bool(gates.get('g2_coverage_pass')) else 'FAIL'}",
        f"gate g2 generic share: {'PASS' if bool(gates.get('g2_generic_share_pass')) else 'FAIL'}",
        "",
        "Label Type Counts",
        "-----------------",
    ]

    if isinstance(label_type_counts, dict) and label_type_counts:
        for relation_type in sorted(label_type_counts):
            lines.append(f"- {relation_type}: {label_type_counts[relation_type]}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Edge Type Counts",
            "----------------",
        ]
    )
    if isinstance(edge_type_counts, dict) and edge_type_counts:
        for relation_type in sorted(edge_type_counts):
            lines.append(f"- {relation_type}: {edge_type_counts[relation_type]}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Unresolved Refs",
            "---------------",
            f"sources with unresolved refs: {unresolved.get('sources_with_unresolved_refs', 0)}",
            f"total unresolved refs: {unresolved.get('total_unresolved_refs', 0)}",
            f"distinct unresolved refs: {unresolved.get('distinct_unresolved_refs', 0)}",
        ]
    )

    if not bool(gates.get("g2_pass")):
        lines.extend(
            [
                "",
                "Gate Failure Details",
                "--------------------",
            ]
        )
        if not bool(gates.get("g2_coverage_pass")):
            lines.append(
                f"- coverage percent {edge_counts.get('coverage_percent', 0.0)} is below "
                f"min {thresholds.get('min_coverage_percent', 95.0)}"
            )
        if not bool(gates.get("g2_generic_share_pass")):
            lines.append(
                f"- generic_ref share percent {report.get('generic_ref_share_percent', 0.0)} exceeds "
                f"max {thresholds.get('max_generic_share_percent', 40.0)}"
            )

    return "\n".join(lines) + "\n"

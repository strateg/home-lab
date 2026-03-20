"""Diagnostics reporting helpers for compile-topology orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def sort_diagnostics(diagnostics: list[Any]) -> None:
    diagnostics.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(getattr(item, "severity", ""), 9),
            getattr(item, "stage", ""),
            getattr(item, "code", ""),
            getattr(item, "path", ""),
        )
    )


def build_summary(diagnostics: list[Any]) -> tuple[dict[str, Any], int, int, int, int]:
    total = len(diagnostics)
    errors = sum(1 for item in diagnostics if getattr(item, "severity", "") == "error")
    warnings = sum(1 for item in diagnostics if getattr(item, "severity", "") == "warning")
    infos = sum(1 for item in diagnostics if getattr(item, "severity", "") == "info")
    by_stage: dict[str, int] = {}
    by_plugin: dict[str, int] = {}
    for item in diagnostics:
        stage = getattr(item, "stage", "")
        by_stage[stage] = by_stage.get(stage, 0) + 1
        plugin_id = getattr(item, "plugin_id", None)
        if isinstance(plugin_id, str) and plugin_id:
            by_plugin[plugin_id] = by_plugin.get(plugin_id, 0) + 1
    summary = {
        "total": total,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "by_stage": by_stage,
    }
    if by_plugin:
        summary["by_plugin"] = by_plugin
    return summary, total, errors, warnings, infos


def build_next_actions(diagnostics: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for diag in diagnostics:
        path = getattr(diag, "path", "")
        code = getattr(diag, "code", "")
        severity = getattr(diag, "severity", "")
        file_key = path.split(":")[0]
        entry = grouped.setdefault(file_key, {"file": file_key, "errors": 0, "warnings": 0, "codes": []})
        if severity == "error":
            entry["errors"] += 1
        elif severity == "warning":
            entry["warnings"] += 1
        entry["codes"].append(code)

    actions: list[dict[str, Any]] = []
    for _, entry in sorted(grouped.items(), key=lambda item: (-item[1]["errors"], -item[1]["warnings"], item[0])):
        primary_codes = sorted(set(entry["codes"]))[:3]
        actions.append(
            {
                "file": entry["file"],
                "errors": entry["errors"],
                "warnings": entry["warnings"],
                "primary_codes": primary_codes,
            }
        )
    return actions


def _report_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()).as_posix())
    except ValueError:
        return str(path.resolve().as_posix())


def write_diagnostics_report(
    *,
    diagnostics: list[Any],
    diagnostics_json: Path,
    diagnostics_txt: Path,
    topology_path: Path,
    error_catalog_path: Path,
    output_json: Path,
    repo_root: Path,
    now_iso: Callable[[], str],
    plugin_stats: dict[str, Any] | None = None,
    plugin_manifests: list[str] | None = None,
) -> tuple[int, int, int, int]:
    sort_diagnostics(diagnostics)
    summary, total, errors, warnings, infos = build_summary(diagnostics)

    diagnostics_json.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_txt.parent.mkdir(parents=True, exist_ok=True)

    inputs: dict[str, Any] = {
        "topology": _report_path(topology_path, repo_root),
        "schema": "v5/topology/topology.yaml",
        "error_catalog": _report_path(error_catalog_path, repo_root),
        "model_lock": "v5/topology/model.lock.yaml",
    }
    if plugin_manifests:
        inputs["plugin_manifests"] = plugin_manifests

    report: dict[str, Any] = {
        "report_version": "2.0.0",
        "tool": "topology-v5-compiler",
        "generated_at": now_iso(),
        "inputs": inputs,
        "outputs": {
            "effective_json": _report_path(output_json, repo_root),
            "diagnostics_json": _report_path(diagnostics_json, repo_root),
            "diagnostics_txt": _report_path(diagnostics_txt, repo_root),
        },
        "summary": summary,
        "next_actions": build_next_actions(diagnostics),
        "diagnostics": [item.as_dict() for item in diagnostics],
    }
    if isinstance(plugin_stats, dict):
        report["plugins"] = {
            "loaded": plugin_stats.get("loaded", 0),
            "executed": plugin_stats.get("executed", 0),
            "failed": plugin_stats.get("failed", 0),
            "by_kind": plugin_stats.get("by_kind", {}),
            "execution_order": plugin_stats.get("execution_order", []),
        }
    diagnostics_json.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, default=str),
        encoding="utf-8",
    )

    txt_lines = [
        "Topology v5 Compiler Diagnostics",
        "================================",
        "",
        f"generated_at: {report['generated_at']}",
        f"total={total} errors={errors} warnings={warnings} infos={infos}",
        "",
    ]
    for item in diagnostics:
        txt_lines.append(f"[{item.severity.upper()}] {item.code} ({item.stage}) {item.path}: {item.message}")
        hint = getattr(item, "hint", None)
        if hint:
            txt_lines.append(f"  hint: {hint}")
    diagnostics_txt.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

    return total, errors, warnings, infos

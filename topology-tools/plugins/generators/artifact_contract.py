"""Shared ArtifactPlan / ArtifactGenerationReport helpers (ADR 0093)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext

SCHEMA_VERSION = "1.0"


def _normalize_paths(paths: list[str]) -> list[str]:
    normalized = {str(path).strip() for path in paths if str(path).strip()}
    return sorted(normalized)


def build_planned_output(
    *,
    path: str,
    renderer: str = "jinja2",
    required: bool = True,
    reason: str = "base-family",
    template: str | None = None,
    capability_ref: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": path,
        "renderer": renderer,
        "required": required,
        "reason": reason,
    }
    if template:
        entry["template"] = template
    if capability_ref:
        entry["capability_ref"] = capability_ref
    return entry


def build_artifact_plan(
    *,
    plugin_id: str,
    artifact_family: str,
    planned_outputs: list[dict[str, Any]],
    projection_version: str = "1.0",
    ir_version: str = "1.0",
    obsolete_candidates: list[dict[str, Any]] | None = None,
    capabilities: list[str] | None = None,
    validation_profiles: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": plugin_id,
        "artifact_family": artifact_family,
        "projection_version": projection_version,
        "ir_version": ir_version,
        "planned_outputs": planned_outputs,
        "obsolete_candidates": obsolete_candidates or [],
        "capabilities": sorted({str(item) for item in capabilities or [] if str(item)}),
        "validation_profiles": sorted({str(item) for item in validation_profiles or [] if str(item)}),
    }


def build_generation_report(
    *,
    plugin_id: str,
    artifact_family: str,
    planned_outputs: list[dict[str, Any]],
    generated: list[str],
    skipped: list[str] | None = None,
    obsolete: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    generated_paths = _normalize_paths(generated)
    skipped_paths = _normalize_paths(skipped or [])
    obsolete_entries = obsolete or []
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": plugin_id,
        "artifact_family": artifact_family,
        "generated": generated_paths,
        "skipped": skipped_paths,
        "obsolete": obsolete_entries,
        "summary": {
            "planned_count": len(planned_outputs),
            "generated_count": len(generated_paths),
            "skipped_count": len(skipped_paths),
            "obsolete_count": len(obsolete_entries),
        },
    }


def _resolve_contracts_root(ctx: PluginContext) -> Path:
    raw_root = ctx.config.get("artifact_contracts_root")
    if isinstance(raw_root, str) and raw_root.strip():
        root = Path(raw_root.strip())
        if not root.is_absolute():
            repo_root_raw = ctx.config.get("repo_root")
            if isinstance(repo_root_raw, str) and repo_root_raw.strip():
                root = Path(repo_root_raw.strip()) / root
            elif ctx.output_dir:
                root = Path(ctx.output_dir) / root
            else:
                root = Path.cwd() / root
        return root.resolve()
    if ctx.output_dir:
        return (Path(ctx.output_dir).resolve() / "artifact-contracts").resolve()
    return (Path.cwd() / "build" / "artifact-contracts").resolve()


def write_contract_artifacts(
    *,
    ctx: PluginContext,
    plugin_id: str,
    artifact_plan: dict[str, Any],
    generation_report: dict[str, Any],
) -> dict[str, str]:
    contracts_root = _resolve_contracts_root(ctx)
    plugin_dir = contracts_root / plugin_id.replace(".", "__")
    plugin_dir.mkdir(parents=True, exist_ok=True)

    plan_path = plugin_dir / "artifact-plan.json"
    report_path = plugin_dir / "artifact-generation-report.json"
    summary_path = plugin_dir / "artifact-family-summary.json"

    plan_path.write_text(
        json.dumps(artifact_plan, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8"
    )
    report_path.write_text(
        json.dumps(generation_report, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": generation_report.get("plugin_id", plugin_id),
        "artifact_family": generation_report.get("artifact_family", ""),
        "summary": generation_report.get("summary", {}),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "artifact_plan_path": str(plan_path),
        "artifact_generation_report_path": str(report_path),
        "artifact_family_summary_path": str(summary_path),
    }

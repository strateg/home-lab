"""Shared ArtifactPlan / ArtifactGenerationReport helpers (ADR 0093)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext

SCHEMA_VERSION = "1.0"
SCHEMA_COMPATIBILITY_RANGE = ">=1.0,<2.0"
_SCHEMA_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")

try:
    import jsonschema
except ImportError:  # pragma: no cover - optional dependency in minimal runtime
    jsonschema = None  # type: ignore[assignment]


def _resolve_logical_root(ctx: PluginContext | None = None) -> Path:
    if ctx is not None:
        artifacts_root_raw = ctx.config.get("generator_artifacts_root")
        if isinstance(artifacts_root_raw, str) and artifacts_root_raw.strip():
            artifacts_root = Path(artifacts_root_raw.strip())
            if artifacts_root.is_absolute():
                return artifacts_root.resolve().parent
        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            return Path(repo_root_raw.strip()).resolve()
        if ctx.output_dir:
            return Path(ctx.output_dir).resolve().parent
    return Path.cwd().resolve()


def _resolve_artifact_root(ctx: PluginContext | None = None) -> Path | None:
    if ctx is None:
        return None
    artifacts_root_raw = ctx.config.get("generator_artifacts_root")
    if not isinstance(artifacts_root_raw, str) or not artifacts_root_raw.strip():
        return None
    artifact_root = Path(artifacts_root_raw.strip())
    if artifact_root.is_absolute():
        return artifact_root.resolve()
    repo_root_raw = ctx.config.get("repo_root")
    if isinstance(repo_root_raw, str) and repo_root_raw.strip():
        return (Path(repo_root_raw.strip()).resolve() / artifact_root).resolve()
    return artifact_root.resolve()


def _resolve_contract_artifact_prefix(ctx: PluginContext | None = None) -> str:
    if ctx is not None:
        raw = ctx.config.get("generator_contract_artifacts_prefix")
        if isinstance(raw, str) and raw.strip():
            return raw.strip().strip("/")
    return "generated"


def _to_absolute_path(path: str, *, ctx: PluginContext | None = None) -> Path:
    raw = str(path).strip()
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (_resolve_logical_root(ctx) / candidate).resolve()


def _to_contract_path(path: str, *, ctx: PluginContext | None = None) -> str:
    absolute_path = _to_absolute_path(path, ctx=ctx)
    artifact_root = _resolve_artifact_root(ctx)
    if artifact_root is not None:
        try:
            relative_to_artifacts = absolute_path.relative_to(artifact_root)
            prefix = _resolve_contract_artifact_prefix(ctx)
            if prefix:
                return f"{prefix}/{relative_to_artifacts.as_posix()}"
            return relative_to_artifacts.as_posix()
        except ValueError:
            pass
    logical_root = _resolve_logical_root(ctx)
    try:
        return absolute_path.relative_to(logical_root).as_posix()
    except ValueError:
        return absolute_path.as_posix()


def _normalize_paths(paths: list[str], *, ctx: PluginContext | None = None) -> list[str]:
    normalized = {_to_contract_path(str(path), ctx=ctx) for path in paths if str(path).strip()}
    return sorted(normalized)


def _is_supported_schema_version(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = _SCHEMA_VERSION_RE.fullmatch(value.strip())
    if match is None:
        return False
    return int(match.group("major")) == 1


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
    ctx: PluginContext | None = None,
) -> dict[str, Any]:
    normalized_planned_outputs: list[dict[str, Any]] = []
    for item in planned_outputs:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        path_value = normalized_item.get("path")
        if isinstance(path_value, str) and path_value.strip():
            normalized_item["path"] = _to_contract_path(path_value, ctx=ctx)
        normalized_planned_outputs.append(normalized_item)

    normalized_obsolete_candidates: list[dict[str, Any]] = []
    for item in obsolete_candidates or []:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        path_value = normalized_item.get("path")
        if isinstance(path_value, str) and path_value.strip():
            normalized_item["path"] = _to_contract_path(path_value, ctx=ctx)
        normalized_obsolete_candidates.append(normalized_item)

    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": plugin_id,
        "artifact_family": artifact_family,
        "projection_version": projection_version,
        "ir_version": ir_version,
        "planned_outputs": normalized_planned_outputs,
        "obsolete_candidates": normalized_obsolete_candidates,
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
    ctx: PluginContext | None = None,
) -> dict[str, Any]:
    generated_paths = _normalize_paths(generated, ctx=ctx)
    skipped_paths = _normalize_paths(skipped or [], ctx=ctx)
    obsolete_entries: list[dict[str, Any]] = []
    for item in obsolete or []:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        path_value = normalized_item.get("path")
        if isinstance(path_value, str) and path_value.strip():
            normalized_item["path"] = _to_contract_path(path_value, ctx=ctx)
        obsolete_entries.append(normalized_item)
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


def _resolve_state_root(ctx: PluginContext) -> Path:
    raw_state_root = ctx.config.get("artifact_plan_state_dir")
    if isinstance(raw_state_root, str) and raw_state_root.strip():
        state_root = Path(raw_state_root.strip())
        if state_root.is_absolute():
            return state_root.resolve()
        repo_root = _resolve_repo_root(ctx)
        return (repo_root / state_root).resolve()

    repo_root_raw = ctx.config.get("repo_root")
    if isinstance(repo_root_raw, str) and repo_root_raw.strip():
        return (Path(repo_root_raw.strip()).resolve() / ".state" / "artifact-plans").resolve()
    if ctx.output_dir:
        return (Path(ctx.output_dir).resolve() / ".state" / "artifact-plans").resolve()
    return (Path.cwd() / ".state" / "artifact-plans").resolve()


def _state_plan_path(*, ctx: PluginContext, plugin_id: str) -> Path:
    return _resolve_state_root(ctx) / f"{plugin_id}.json"


def load_previous_plan(*, ctx: PluginContext, plugin_id: str) -> dict[str, Any] | None:
    path = _state_plan_path(ctx=ctx, plugin_id=plugin_id)
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def save_current_plan(*, ctx: PluginContext, plugin_id: str, artifact_plan: dict[str, Any]) -> Path:
    path = _state_plan_path(ctx=ctx, plugin_id=plugin_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact_plan, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _collect_existing_files(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(str(path.resolve()) for path in root.rglob("*") if path.is_file())


def _extract_planned_paths(plan: dict[str, Any] | None, *, ctx: PluginContext | None = None) -> set[str]:
    if not isinstance(plan, dict):
        return set()
    payload = plan.get("planned_outputs")
    if not isinstance(payload, list):
        return set()
    out: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        out.add(str(_to_absolute_path(path, ctx=ctx)))
    return out


def _has_ownership_marker(*, path: Path, plugin_id: str) -> bool:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    marker = f"Generated by: {plugin_id}"
    return marker in content


def _resolve_obsolete_action(ctx: PluginContext) -> str:
    raw = ctx.config.get("artifact_obsolete_action")
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"retain", "delete", "warn"}:
            return token
    return "warn"


def compute_obsolete_entries(
    *,
    ctx: PluginContext,
    plugin_id: str,
    output_root: Path,
    planned_outputs: list[dict[str, Any]],
    ownership_prefix: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    planned_paths = _extract_planned_paths({"planned_outputs": planned_outputs}, ctx=ctx)
    existing_paths = set(_collect_existing_files(output_root.resolve()))
    stale_paths = sorted(existing_paths - planned_paths)
    previous_plan = load_previous_plan(ctx=ctx, plugin_id=plugin_id)
    previous_planned_paths = _extract_planned_paths(previous_plan, ctx=ctx)
    chosen_action = _resolve_obsolete_action(ctx)

    prefix_root = Path(ownership_prefix).resolve() if ownership_prefix else output_root.resolve()
    entries: list[dict[str, Any]] = []
    errors: list[str] = []

    for stale in stale_paths:
        stale_path = Path(stale).resolve()
        ownership_method = "none"
        ownership_proven = False

        if str(stale_path) in previous_planned_paths:
            ownership_proven = True
            ownership_method = "previous_plan_match"
        elif str(stale_path).startswith(str(prefix_root) + "/") or stale_path == prefix_root:
            ownership_proven = True
            ownership_method = "output_prefix_match"
        elif _has_ownership_marker(path=stale_path, plugin_id=plugin_id):
            ownership_proven = True
            ownership_method = "ownership_marker"

        action = chosen_action
        if action == "delete" and not ownership_proven:
            errors.append(
                f"Cannot mark obsolete file for delete without ownership proof: {stale_path} (plugin={plugin_id})."
            )
            action = "warn"

        entries.append(
            {
                "path": str(stale_path),
                "action": action,
                "reason": "obsolete-shadowed",
                "ownership_proven": ownership_proven,
                "ownership_method": ownership_method,
            }
        )

    return entries, errors


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
    state_plan_path = save_current_plan(ctx=ctx, plugin_id=plugin_id, artifact_plan=artifact_plan)

    return {
        "artifact_plan_path": str(plan_path),
        "artifact_generation_report_path": str(report_path),
        "artifact_family_summary_path": str(summary_path),
        "state_artifact_plan_path": str(state_plan_path),
    }


def _resolve_repo_root(ctx: PluginContext | None = None) -> Path:
    if ctx is not None:
        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            return Path(repo_root_raw.strip()).resolve()
    return Path(__file__).resolve().parents[3]


def _resolve_schema_paths(ctx: PluginContext | None = None) -> tuple[str, str]:
    candidates: list[Path] = []
    repo_root = _resolve_repo_root(ctx)
    candidates.append((repo_root / "schemas").resolve())

    if ctx is not None:
        class_modules_root_raw = ctx.config.get("class_modules_root")
        if isinstance(class_modules_root_raw, str) and class_modules_root_raw.strip():
            class_modules_root = Path(class_modules_root_raw.strip()).resolve()
            # class_modules_root points to <framework_root>/topology/class-modules
            framework_root = class_modules_root.parent.parent
            candidates.append((framework_root / "schemas").resolve())
        object_modules_root_raw = ctx.config.get("object_modules_root")
        if isinstance(object_modules_root_raw, str) and object_modules_root_raw.strip():
            object_modules_root = Path(object_modules_root_raw.strip()).resolve()
            # object_modules_root points to <framework_root>/topology/object-modules
            framework_root = object_modules_root.parent.parent
            candidates.append((framework_root / "schemas").resolve())

    candidates.append((Path(__file__).resolve().parents[3] / "schemas").resolve())

    seen: set[str] = set()
    for schema_root in candidates:
        key = str(schema_root)
        if key in seen:
            continue
        seen.add(key)
        plan_schema = schema_root / "artifact-plan.schema.json"
        report_schema = schema_root / "artifact-generation-report.schema.json"
        if plan_schema.is_file() and report_schema.is_file():
            return str(plan_schema), str(report_schema)

    fallback_root = candidates[0]
    return (
        str((fallback_root / "artifact-plan.schema.json").resolve()),
        str((fallback_root / "artifact-generation-report.schema.json").resolve()),
    )


@lru_cache(maxsize=16)
def _load_schema(schema_path: str) -> dict[str, Any]:
    path = Path(schema_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def validate_contract_payloads(
    *,
    artifact_plan: dict[str, Any],
    generation_report: dict[str, Any],
    ctx: PluginContext | None = None,
) -> list[str]:
    if jsonschema is None:
        return []

    plan_schema_path, report_schema_path = _resolve_schema_paths(ctx)
    if not Path(plan_schema_path).is_file() or not Path(report_schema_path).is_file():
        # Backward-compatible behavior for older framework distributions that do
        # not yet ship ADR0093 schema files.
        return []

    errors: list[str] = []
    for payload, schema_path, contract_name in (
        (artifact_plan, plan_schema_path, "artifact_plan"),
        (generation_report, report_schema_path, "artifact_generation_report"),
    ):
        try:
            schema_version = payload.get("schema_version")
            if not _is_supported_schema_version(schema_version):
                errors.append(
                    f"{contract_name} schema_version '{schema_version}' is unsupported; "
                    f"supported range: {SCHEMA_COMPATIBILITY_RANGE}"
                )
                continue
            schema = _load_schema(schema_path)
            jsonschema.validate(payload, schema)
        except Exception as exc:
            errors.append(f"{contract_name} validation failed: {exc}")
    return errors

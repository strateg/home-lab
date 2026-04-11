"""ADR0094 AI advisory input/output contract helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext

SCHEMA_VERSION = "1.0"
_SCHEMA_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")
_DEFAULT_SECRET_KEY_PATTERNS = (
    re.compile(r".*_password$", re.IGNORECASE),
    re.compile(r".*_token$", re.IGNORECASE),
    re.compile(r".*_key$", re.IGNORECASE),
    re.compile(r".*_secret$", re.IGNORECASE),
)

try:
    import jsonschema
except ImportError:  # pragma: no cover - optional dependency in minimal runtime
    jsonschema = None  # type: ignore[assignment]


def _is_supported_schema_version(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = _SCHEMA_VERSION_RE.fullmatch(value.strip())
    if match is None:
        return False
    return int(match.group("major")) == 1


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _compute_input_hash(payload_without_hash: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload_without_hash).encode("utf-8")).hexdigest()
    return f"sha256-{digest}"


def _normalize_secret_paths(paths: list[str] | None) -> set[str]:
    if not isinstance(paths, list):
        return set()
    return {str(path).strip() for path in paths if isinstance(path, str) and path.strip()}


def _looks_secret_key(path: str, key_name: str, key_patterns: tuple[re.Pattern[str], ...]) -> bool:
    token = key_name.strip()
    if not token:
        return False
    if any(pattern.fullmatch(token) for pattern in key_patterns):
        return True
    full_path = f"{path}.{token}" if path else token
    return any(pattern.fullmatch(full_path) for pattern in key_patterns)


def redact_sensitive_fields(
    payload: dict[str, Any],
    *,
    secret_paths: list[str] | None = None,
    annotation_secret_paths: list[str] | None = None,
    key_patterns: tuple[re.Pattern[str], ...] = _DEFAULT_SECRET_KEY_PATTERNS,
    placeholder_format: str = "<<REDACTED:{field_path}>>",
) -> tuple[dict[str, Any], dict[str, Any]]:
    redacted_paths: set[str] = set()
    explicit_paths = _normalize_secret_paths(secret_paths) | _normalize_secret_paths(annotation_secret_paths)
    cloned = json.loads(json.dumps(payload, ensure_ascii=True))

    def walk(node: Any, path: str, in_credentials_scope: bool = False) -> Any:
        if path in explicit_paths:
            redacted_paths.add(path)
            return placeholder_format.format(field_path=path)
        if in_credentials_scope and not isinstance(node, (dict, list)):
            redacted_paths.add(path)
            return placeholder_format.format(field_path=path)
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for key, value in node.items():
                key_name = str(key)
                child_path = f"{path}.{key_name}" if path else key_name
                child_in_credentials_scope = in_credentials_scope or (key_name.lower() == "credentials")
                if _looks_secret_key(path, key_name, key_patterns):
                    redacted_paths.add(child_path)
                    out[key_name] = placeholder_format.format(field_path=child_path)
                    continue
                out[key_name] = walk(value, child_path, child_in_credentials_scope)
            return out
        if isinstance(node, list):
            out_list: list[Any] = []
            for idx, value in enumerate(node):
                child_path = f"{path}[{idx}]"
                out_list.append(walk(value, child_path, in_credentials_scope))
            return out_list
        return node

    redacted = walk(cloned, "")
    summary = {
        "redacted_fields": len(redacted_paths),
        "placeholder_format": placeholder_format,
        "redacted_paths": sorted(redacted_paths),
    }
    if not isinstance(redacted, dict):
        redacted = {}
    return redacted, summary


def build_ai_input_payload(
    *,
    artifact_family: str,
    mode: str,
    plugin_id: str,
    effective_json: dict[str, Any],
    stable_projection: dict[str, Any],
    artifact_plan: dict[str, Any],
    generation_context_extra: dict[str, Any] | None = None,
    secret_paths: list[str] | None = None,
    annotation_secret_paths: list[str] | None = None,
    extra_key_patterns: tuple[re.Pattern[str], ...] = (),
    placeholder_format: str = "<<REDACTED:{field_path}>>",
) -> dict[str, Any]:
    generation_context = {
        "mode": str(mode),
        "plugin_id": str(plugin_id),
    }
    if isinstance(generation_context_extra, dict):
        for key, value in generation_context_extra.items():
            if isinstance(key, str) and key.strip():
                generation_context[key] = value
    payload = {
        "schema_version": SCHEMA_VERSION,
        "artifact_family": str(artifact_family),
        "generation_context": generation_context,
        "effective_json": effective_json,
        "stable_projection": stable_projection,
        "artifact_plan": artifact_plan,
    }
    redacted_payload, redaction_summary = redact_sensitive_fields(
        payload,
        secret_paths=secret_paths,
        annotation_secret_paths=annotation_secret_paths,
        key_patterns=_DEFAULT_SECRET_KEY_PATTERNS + tuple(extra_key_patterns),
        placeholder_format=placeholder_format,
    )
    payload = redacted_payload
    payload["redaction_summary"] = redaction_summary
    payload["input_hash"] = _compute_input_hash(payload)
    return payload


def parse_ai_output_payload(ai_output: dict[str, Any]) -> dict[str, Any]:
    recommendations: list[dict[str, Any]] = []
    rows = ai_output.get("advisory_recommendations")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                recommendations.append(dict(row))

    confidence_scores: dict[str, float] = {}
    raw_scores = ai_output.get("confidence_scores")
    if isinstance(raw_scores, dict):
        for key, value in raw_scores.items():
            if isinstance(key, str) and isinstance(value, (int, float)):
                confidence_scores[key] = max(0.0, min(1.0, float(value)))

    metadata = ai_output.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "metadata": metadata,
        "recommendations": recommendations,
        "confidence_scores": confidence_scores,
    }


def _resolve_schema_paths(ctx: PluginContext | None = None) -> tuple[str, str]:
    candidates: list[Path] = []
    repo_root = Path(__file__).resolve().parents[3]
    candidates.append((repo_root / "schemas").resolve())

    if ctx is not None:
        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            candidates.append((Path(repo_root_raw.strip()).resolve() / "schemas").resolve())

    seen: set[str] = set()
    for schema_root in candidates:
        key = str(schema_root)
        if key in seen:
            continue
        seen.add(key)
        input_schema = schema_root / "ai-input-contract.schema.json"
        output_schema = schema_root / "ai-output-contract.schema.json"
        if input_schema.is_file() and output_schema.is_file():
            return str(input_schema), str(output_schema)

    fallback = repo_root / "schemas"
    return str((fallback / "ai-input-contract.schema.json").resolve()), str(
        (fallback / "ai-output-contract.schema.json").resolve()
    )


def _load_schema(schema_path: str) -> dict[str, Any]:
    payload = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def validate_ai_contract_payloads(
    *,
    ai_input: dict[str, Any] | None,
    ai_output: dict[str, Any] | None,
    ctx: PluginContext | None = None,
) -> list[str]:
    errors: list[str] = []
    payload_specs = (
        (ai_input, "ai_input"),
        (ai_output, "ai_output"),
    )

    for payload, contract_name in payload_specs:
        if payload is None:
            continue
        schema_version = payload.get("schema_version")
        if not _is_supported_schema_version(schema_version):
            errors.append(f"{contract_name} schema_version '{schema_version}' is unsupported; expected major 1.x.")

    if jsonschema is None:
        return errors

    input_schema_path, output_schema_path = _resolve_schema_paths(ctx)
    if not Path(input_schema_path).is_file() or not Path(output_schema_path).is_file():
        return errors

    for payload, schema_path, contract_name in (
        (ai_input, input_schema_path, "ai_input"),
        (ai_output, output_schema_path, "ai_output"),
    ):
        if payload is None:
            continue
        try:
            if not _is_supported_schema_version(payload.get("schema_version")):
                continue
            schema = _load_schema(schema_path)
            jsonschema.validate(payload, schema)
        except Exception as exc:  # pragma: no cover
            errors.append(f"{contract_name} contract validation failed: {exc}")
    return errors

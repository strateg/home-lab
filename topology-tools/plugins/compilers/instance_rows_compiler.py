"""Instance rows normalization compiler plugin (ADR 0069 WS2/WS3, ADR 0072 side-car secrets)."""

from __future__ import annotations

import copy
import datetime as dt
import ipaddress
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from field_annotations import parse_field_annotation
from identifier_policy import contains_unsafe_identifier_chars
from kernel.plugin_base import (
    CompilerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)
from semantic_keywords import SemanticKeywordRegistry, load_semantic_keyword_registry, resolve_semantic_value
from yaml_loader import load_yaml_text


class InstanceRowsCompiler(CompilerPlugin):
    """Normalize instance_bindings rows and emit row-shape diagnostics."""

    _ANNOTATION_PLUGIN_ID = "base.compiler.annotation_resolver"
    _SECRET_RESOLVED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_secret_resolve"
    _RESOLVED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_resolve"
    _PREPARED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_prepare"
    _VALIDATED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_validate"
    _RESERVED_ROW_KEYS = {
        "instance",
        "group",
        "layer",
        "source_id",
        "class_ref",
        "object_ref",
        "status",
        "notes",
        "runtime",
        "firmware_ref",
        "os_refs",
        "embedded_in",
        "sops",
        "_source_file",
        "hardware_identity_secret_ref",
    }

    _TODO_MARKER_RE = re.compile(r"^<TODO_[A-Z0-9_]+>$")
    _SEMANTIC_ROW_TOKEN_MAP: tuple[tuple[str, str], ...] = (
        ("schema_version", "version"),
        ("instance_id", "instance"),
        ("entity_layer", "layer"),
        ("parent_ref", "object_ref"),
        ("entity_title", "title"),
        ("entity_summary", "summary"),
        ("entity_description", "description"),
    )

    @classmethod
    def _extract_extensions(cls, row: dict[str, Any]) -> dict[str, Any]:
        extensions: dict[str, Any] = {}
        for key in sorted(row.keys()):
            if key in cls._RESERVED_ROW_KEYS:
                continue
            extensions[key] = row[key]
        return extensions

    def _normalize_semantic_row(
        self,
        *,
        row: dict[str, Any],
        semantic_registry: SemanticKeywordRegistry,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
    ) -> dict[str, Any] | None:
        normalized = dict(row)
        for token, legacy_key in self._SEMANTIC_ROW_TOKEN_MAP:
            resolution = resolve_semantic_value(
                normalized,
                registry=semantic_registry,
                context="entity_manifest",
                token=token,
            )
            if resolution.has_collision:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8803",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Instance row contains semantic-key collision for {token}: "
                            f"{', '.join(resolution.present_keys)}."
                        ),
                        path=row_path,
                    )
                )
                return None
            if token == "parent_ref" and resolution.found and "object_ref" in normalized:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8803",
                        severity="error",
                        stage=stage,
                        message="Instance row must not define both '@extends' and legacy 'object_ref'.",
                        path=row_path,
                    )
                )
                return None
            if resolution.found:
                normalized[legacy_key] = resolution.value
        normalized.pop("@version", None)
        normalized.pop("@instance", None)
        normalized.pop("@layer", None)
        normalized.pop("@extends", None)
        normalized.pop("extends", None)
        normalized.pop("@title", None)
        normalized.pop("@summary", None)
        normalized.pop("@description", None)
        return normalized

    @staticmethod
    def _resolve_secrets_mode(ctx: PluginContext) -> str:
        mode = ctx.config.get("secrets_mode", "passthrough")
        if not isinstance(mode, str):
            return "passthrough"
        normalized = mode.strip().lower()
        if normalized in {"inject", "passthrough", "strict"}:
            return normalized
        return "passthrough"

    @staticmethod
    def _resolve_require_unlock(ctx: PluginContext) -> bool:
        value = ctx.config.get("require_unlock", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
        return True

    @staticmethod
    def _format_path(path: tuple[Any, ...]) -> str:
        if not path:
            return "<root>"
        parts: list[str] = []
        for token in path:
            if isinstance(token, int):
                parts.append(f"[{token}]")
            else:
                if parts:
                    parts.append(".")
                parts.append(str(token))
        return "".join(parts)

    @staticmethod
    def _annotation_payload(annotation: Any) -> dict[str, Any]:
        return {
            "name": annotation.name,
            "value_type": annotation.value_type,
            "required": annotation.required,
            "optional": annotation.optional,
            "secret": annotation.secret,
        }

    def _collect_row_annotations(self, row: dict[str, Any]) -> dict[str, dict[str, Any]]:
        annotations: dict[str, dict[str, Any]] = {}

        def walk(node: Any, path: tuple[Any, ...]) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, path + (key,))
                return
            if isinstance(node, list):
                for idx, value in enumerate(node):
                    walk(value, path + (idx,))
                return
            if not isinstance(node, str) or not node.startswith("@") or node.startswith("@@"):
                return
            annotation, annotation_error = parse_field_annotation(node)
            if annotation_error is not None or annotation is None:
                return
            annotations[self._format_path(path)] = self._annotation_payload(annotation)

        walk(row, ())
        return annotations

    @staticmethod
    def _extract_annotation_spec(
        *,
        path: str,
        row_annotations: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(row_annotations, dict):
            return None
        spec = row_annotations.get(path)
        if isinstance(spec, dict):
            return spec
        return None

    @staticmethod
    def _is_scalar(value: Any) -> bool:
        return not isinstance(value, dict) and not isinstance(value, list)

    def _collect_all_placeholder_paths(
        self,
        row: dict[str, Any],
        *,
        row_annotations: dict[str, dict[str, Any]] | None = None,
    ) -> list[str]:
        """Walk row and collect unresolved secret marker paths."""
        unresolved: list[str] = []
        secret_paths = {
            path
            for path, spec in (row_annotations or {}).items()
            if isinstance(spec, dict) and bool(spec.get("secret"))
        }

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    # Skip reserved/metadata keys
                    if key in ("sops", "_source_file"):
                        continue
                    child_path = f"{path}.{key}" if path else str(key)
                    walk(value, child_path)
                return
            if isinstance(node, list):
                for idx, value in enumerate(node):
                    child_path = f"{path}[{idx}]"
                    walk(value, child_path)
                return
            if not isinstance(node, str):
                return
            if self._TODO_MARKER_RE.fullmatch(node):
                # Strict secrets mode must enforce unresolved placeholders only for
                # secret-annotated paths. When annotation index is unavailable
                # (direct single-plugin execution), keep legacy strict behavior.
                if path in secret_paths or row_annotations is None:
                    unresolved.append(path)
                return
            if path in secret_paths and node.startswith("@"):
                unresolved.append(path)
                return
            if row_annotations is None:
                annotation, annotation_error = parse_field_annotation(node)
                if annotation_error is None and annotation is not None and annotation.secret:
                    unresolved.append(path)

        walk(row, "")
        return unresolved

    def _validate_format(self, value: Any, spec: dict[str, Any]) -> tuple[bool, str]:
        expected_type = spec.get("type")
        if expected_type == "string":
            if not isinstance(value, str):
                return False, f"expected string, got {type(value).__name__}"
        elif expected_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                return False, f"expected integer, got {type(value).__name__}"
        elif expected_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"expected number, got {type(value).__name__}"
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                return False, f"expected boolean, got {type(value).__name__}"

        if value is None:
            return False, "null is not allowed; omit optional field instead"

        pattern = spec.get("pattern")
        if isinstance(pattern, str):
            try:
                regex = re.compile(pattern)
            except re.error as exc:  # pragma: no cover - registry error path
                return False, f"invalid registry regex: {exc}"
            if not isinstance(value, str) or regex.fullmatch(value) is None:
                return False, "regex mismatch"

        validator = spec.get("validator")
        if validator == "ipv4":
            try:
                ipaddress.IPv4Address(str(value))
            except Exception:
                return False, "not a valid IPv4 address"
        elif validator == "ipv6":
            try:
                ipaddress.IPv6Address(str(value))
            except Exception:
                return False, "not a valid IPv6 address"
        elif validator == "cidr":
            try:
                ipaddress.ip_network(str(value), strict=False)
            except Exception:
                return False, "not a valid CIDR"
        elif validator == "uri":
            parsed = urlparse(str(value))
            if not parsed.scheme or (not parsed.netloc and not parsed.path):
                return False, "not a valid URI"
        elif validator == "iso8601":
            text = str(value)
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                dt.datetime.fromisoformat(text)
            except ValueError:
                return False, "not a valid ISO8601 value"
        elif isinstance(validator, str) and validator:
            return False, f"unsupported validator '{validator}' in registry"

        return True, "ok"

    def _validate_secret_typed_value(
        self,
        *,
        instance_id: str,
        path: str,
        value: Any,
        annotation_spec: dict[str, Any] | None,
        annotation_formats: dict[str, dict[str, Any]] | None,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
    ) -> bool:
        if not isinstance(annotation_spec, dict):
            return True
        value_type = annotation_spec.get("value_type")
        if not isinstance(value_type, str) or not value_type:
            return True
        if not isinstance(annotation_formats, dict) or not annotation_formats:
            return True
        format_spec = annotation_formats.get(value_type)
        if not isinstance(format_spec, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7213",
                    severity="error",
                    stage=stage,
                    message=(f"Secret value format '{value_type}' is not defined for " f"'{instance_id}' at '{path}'."),
                    path=row_path,
                )
            )
            return False
        ok, reason = self._validate_format(value, format_spec)
        if not ok:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7213",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Secret value for '{instance_id}' at '{path}' does not match "
                        f"annotation format '{value_type}': {reason}."
                    ),
                    path=row_path,
                )
            )
            return False
        return True

    def _decrypt_sidecar_file(
        self,
        *,
        sidecar_path: Path,
        instance_id: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
        require_unlock: bool,
    ) -> dict[str, Any] | None:
        """Decrypt side-car secrets file using sops."""
        command = ["sops", "-d", str(sidecar_path)]
        fail_hard = mode == "strict" or require_unlock
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            severity = "error" if fail_hard else "warning"
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7200",
                    severity=severity,
                    stage=stage,
                    message=f"Failed to execute sops for side-car secrets '{instance_id}': {exc}",
                    path=row_path,
                )
            )
            return None

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            severity = "error" if fail_hard else "warning"
            code = "E7201" if fail_hard else "W7210"
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity=severity,
                    stage=stage,
                    message=(
                        f"Failed to decrypt side-car secrets for '{instance_id}'. "
                        f"sops exit={result.returncode}. {stderr}"
                    ),
                    path=row_path,
                )
            )
            return None

        try:
            payload = load_yaml_text(result.stdout) or {}
        except yaml.YAMLError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7203",
                    severity="error",
                    stage=stage,
                    message=f"Side-car YAML parse failed for '{instance_id}': {exc}",
                    path=row_path,
                )
            )
            return None

        if not isinstance(payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7203",
                    severity="error",
                    stage=stage,
                    message=f"Side-car payload must be object/mapping for '{instance_id}'.",
                    path=row_path,
                )
            )
            return None

        return payload

    def _merge_placeholders(
        self,
        row: dict[str, Any],
        secrets: dict[str, Any],
        instance_id: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
        row_annotations: dict[str, dict[str, Any]] | None,
        annotation_formats: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Deep merge: replace <TODO_*> placeholders with values from decrypted secrets."""
        result = copy.deepcopy(row)

        def walk_and_replace(target: Any, source: Any, path: str) -> Any:
            annotation_spec = self._extract_annotation_spec(path=path, row_annotations=row_annotations)
            secret_by_index = bool(annotation_spec and annotation_spec.get("secret"))

            if isinstance(target, dict) and isinstance(source, dict):
                for key, source_value in source.items():
                    child_path = f"{path}.{key}" if path else str(key)
                    if key in target:
                        target[key] = walk_and_replace(target[key], source_value, child_path)
                    else:
                        if self._is_scalar(source_value):
                            child_spec = self._extract_annotation_spec(path=child_path, row_annotations=row_annotations)
                            if self._validate_secret_typed_value(
                                instance_id=instance_id,
                                path=child_path,
                                value=source_value,
                                annotation_spec=child_spec,
                                annotation_formats=annotation_formats,
                                stage=stage,
                                diagnostics=diagnostics,
                                row_path=row_path,
                            ):
                                target[key] = copy.deepcopy(source_value)
                        else:
                            if isinstance(source_value, dict):
                                target[key] = walk_and_replace({}, source_value, child_path)
                            else:
                                target[key] = copy.deepcopy(source_value)
                return target

            if isinstance(target, list) and isinstance(source, list):
                for idx in range(min(len(target), len(source))):
                    target[idx] = walk_and_replace(target[idx], source[idx], f"{path}[{idx}]")
                return target

            if isinstance(target, str) and self._TODO_MARKER_RE.fullmatch(target):
                # Target is placeholder - replace with secret value if available.
                if self._is_scalar(source):
                    if self._validate_secret_typed_value(
                        instance_id=instance_id,
                        path=path,
                        value=source,
                        annotation_spec=annotation_spec,
                        annotation_formats=annotation_formats,
                        stage=stage,
                        diagnostics=diagnostics,
                        row_path=row_path,
                    ):
                        return source
                    return target
                if mode == "strict":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7211",
                            severity="error",
                            stage=stage,
                            message=f"Placeholder '{target}' at '{path}' has no matching secret value.",
                            path=row_path,
                        )
                    )
                return target

            if secret_by_index and isinstance(target, str) and target.startswith("@"):
                if self._is_scalar(source):
                    if self._validate_secret_typed_value(
                        instance_id=instance_id,
                        path=path,
                        value=source,
                        annotation_spec=annotation_spec,
                        annotation_formats=annotation_formats,
                        stage=stage,
                        diagnostics=diagnostics,
                        row_path=row_path,
                    ):
                        return source
                    return target
                if mode == "strict":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7211",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Secret annotation at '{path}' has no matching secret value "
                                f"for instance '{instance_id}'."
                            ),
                            path=row_path,
                        )
                    )
                return target

            if isinstance(target, str) and target.startswith("@"):
                # Fallback path for direct plugin execution without annotation_resolver dependency.
                annotation, annotation_error = parse_field_annotation(target)
                if annotation_error is not None:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"Invalid annotation '{target}' at '{path}': {annotation_error}.",
                            path=row_path,
                        )
                    )
                    return target
                if annotation is not None and annotation.secret:
                    temp_spec = self._annotation_payload(annotation)
                    if self._is_scalar(source):
                        if self._validate_secret_typed_value(
                            instance_id=instance_id,
                            path=path,
                            value=source,
                            annotation_spec=temp_spec,
                            annotation_formats=annotation_formats,
                            stage=stage,
                            diagnostics=diagnostics,
                            row_path=row_path,
                        ):
                            return source
                        return target
                    if mode == "strict":
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7211",
                                severity="error",
                                stage=stage,
                                message=f"Secret annotation '{target}' at '{path}' has no matching secret value.",
                                path=row_path,
                            )
                        )
                    return target

            if self._is_scalar(source):
                if target is not None and target != source:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7212",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Secret conflict at '{path}' in instance '{instance_id}': "
                                "plaintext value differs from decrypted side-car value. "
                                "Use @secret/@*_secret marker or remove plaintext value."
                            ),
                            path=row_path,
                        )
                    )

            # Non-placeholder values are preserved unchanged.
            return target

        for key in secrets:
            if key in ("instance", "sops"):
                continue
            if key in result:
                result[key] = walk_and_replace(result[key], secrets[key], key)
            else:
                source_value = secrets[key]
                if self._is_scalar(source_value):
                    key_spec = self._extract_annotation_spec(path=key, row_annotations=row_annotations)
                    if self._validate_secret_typed_value(
                        instance_id=instance_id,
                        path=key,
                        value=source_value,
                        annotation_spec=key_spec,
                        annotation_formats=annotation_formats,
                        stage=stage,
                        diagnostics=diagnostics,
                        row_path=row_path,
                    ):
                        result[key] = copy.deepcopy(source_value)
                else:
                    if isinstance(source_value, dict):
                        result[key] = walk_and_replace({}, source_value, key)
                    else:
                        result[key] = copy.deepcopy(source_value)

        return result

    def _resolve_sidecar_secrets(
        self,
        *,
        row: dict[str, Any],
        instance_id: str,
        secrets_root: Path,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
        require_unlock: bool,
        row_annotations: dict[str, dict[str, Any]] | None,
        annotation_formats: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Merge decrypted side-car secrets into instance row, replacing placeholders only."""
        if mode == "passthrough":
            return row

        # Look for side-car file
        sidecar_path = secrets_root / "instances" / f"{instance_id}.yaml"
        if not sidecar_path.exists():
            # No side-car file - check if strict mode needs to fail on placeholders
            if mode == "strict":
                unresolved = self._collect_all_placeholder_paths(row, row_annotations=row_annotations)
                if unresolved:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7210",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Strict mode: instance '{instance_id}' has unresolved placeholders "
                                f"but no side-car secrets file at {sidecar_path.name}. "
                                f"Placeholders: {', '.join(unresolved[:5])}"
                                + (f" (+{len(unresolved) - 5} more)" if len(unresolved) > 5 else "")
                            ),
                            path=row_path,
                        )
                    )
            return row

        # Decrypt side-car file
        decrypted = self._decrypt_sidecar_file(
            sidecar_path=sidecar_path,
            instance_id=instance_id,
            stage=stage,
            diagnostics=diagnostics,
            row_path=row_path,
            mode=mode,
            require_unlock=require_unlock,
        )
        if decrypted is None:
            return row

        # Validate instance ID match
        sidecar_instance = decrypted.get("instance")
        if isinstance(sidecar_instance, str) and sidecar_instance and sidecar_instance != instance_id:
            mismatch_is_error = mode == "strict" or require_unlock
            severity = "error" if mismatch_is_error else "warning"
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7205",
                    severity=severity,
                    stage=stage,
                    message=(
                        f"Side-car instance mismatch: row instance '{instance_id}' "
                        f"!= side-car instance '{sidecar_instance}'."
                    ),
                    path=row_path,
                )
            )
            # Mismatch means side-car cannot be trusted for this row in any mode.
            return row

        # Merge placeholders
        merged_row = self._merge_placeholders(
            row=row,
            secrets=decrypted,
            instance_id=instance_id,
            stage=stage,
            diagnostics=diagnostics,
            row_path=row_path,
            mode=mode,
            row_annotations=row_annotations,
            annotation_formats=annotation_formats,
        )

        return merged_row

    def _load_annotation_inputs(
        self,
        ctx: PluginContext,
    ) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
        row_annotations_by_instance: dict[str, dict[str, dict[str, Any]]] = {}
        object_secret_annotations_by_object: dict[str, dict[str, dict[str, Any]]] = {}
        annotation_formats: dict[str, dict[str, Any]] = {}

        legacy_annotation_payloads = (
            ctx.get_published_data().get(self._ANNOTATION_PLUGIN_ID, {})
            if not ctx.is_snapshot_backed
            else {}
        )

        try:
            subscribed_rows = ctx.subscribe(self._ANNOTATION_PLUGIN_ID, "row_annotations_by_instance")
            if isinstance(subscribed_rows, dict):
                row_annotations_by_instance = subscribed_rows
        except PluginDataExchangeError:
            legacy_rows = legacy_annotation_payloads.get("row_annotations_by_instance")
            if isinstance(legacy_rows, dict):
                row_annotations_by_instance = legacy_rows

        try:
            subscribed_objects = ctx.subscribe(self._ANNOTATION_PLUGIN_ID, "object_secret_annotations")
            if isinstance(subscribed_objects, dict):
                object_secret_annotations_by_object = subscribed_objects
        except PluginDataExchangeError:
            legacy_objects = legacy_annotation_payloads.get("object_secret_annotations")
            if isinstance(legacy_objects, dict):
                object_secret_annotations_by_object = legacy_objects

        try:
            subscribed_formats = ctx.subscribe(self._ANNOTATION_PLUGIN_ID, "annotation_formats")
            if isinstance(subscribed_formats, dict):
                annotation_formats = subscribed_formats
        except PluginDataExchangeError:
            legacy_formats = legacy_annotation_payloads.get("annotation_formats")
            if isinstance(legacy_formats, dict):
                annotation_formats = legacy_formats

        return row_annotations_by_instance, object_secret_annotations_by_object, annotation_formats

    @staticmethod
    def _resolve_secrets_root_path(ctx: PluginContext) -> Path:
        secrets_root_str = ctx.config.get("secrets_root", "projects/home-lab/secrets")
        repo_root = ctx.config.get("repo_root")
        if isinstance(repo_root, str) and repo_root:
            return Path(repo_root) / secrets_root_str
        return Path(__file__).resolve().parents[4] / secrets_root_str

    @staticmethod
    def _merge_secret_annotations(
        *,
        row_annotations: dict[str, dict[str, Any]],
        object_secret_annotations: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        merged_secret_annotations: dict[str, dict[str, Any]] = {}
        for path, spec in object_secret_annotations.items():
            if isinstance(path, str) and isinstance(spec, dict):
                merged_secret_annotations[path] = spec
        for path, spec in row_annotations.items():
            if isinstance(path, str) and isinstance(spec, dict):
                merged_secret_annotations[path] = spec
        return merged_secret_annotations

    def _normalize_os_refs(
        self,
        *,
        os_refs: Any,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        path_prefix: str,
    ) -> list[str]:
        if os_refs is not None and not isinstance(os_refs, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="os_refs must be a list when set.",
                    path=path_prefix,
                )
            )
            return []

        normalized_os_refs: list[str] = []
        if not isinstance(os_refs, list):
            return normalized_os_refs

        for os_idx, os_ref in enumerate(os_refs):
            if not isinstance(os_ref, str) or not os_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message="os_refs entries must be non-empty strings.",
                        path=f"{path_prefix}[{os_idx}]",
                    )
                )
                continue
            normalized_os_refs.append(os_ref)
        return normalized_os_refs

    def _resolve_class_and_object_refs(
        self,
        *,
        row: dict[str, Any],
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
    ) -> tuple[Any, Any]:
        class_ref = row.get("class_ref")
        object_ref = row.get("object_ref")
        derived_class_ref: str | None = None

        if isinstance(class_ref, str) and class_ref and contains_unsafe_identifier_chars(class_ref):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=(
                        f"class_ref '{class_ref}' contains filename-unsafe characters; "
                        "use only cross-platform filename-safe symbols."
                    ),
                    path=f"{row_path}.class_ref",
                )
            )
            class_ref = None

        if not isinstance(object_ref, str) or not object_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Instance row must define non-empty 'object_ref'.",
                    path=f"{row_path}.object_ref",
                )
            )
        else:
            if contains_unsafe_identifier_chars(object_ref):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=(
                            f"object_ref '{object_ref}' contains filename-unsafe characters; "
                            "use only cross-platform filename-safe symbols."
                        ),
                        path=f"{row_path}.object_ref",
                    )
                )
            else:
                if object_ref in ctx.classes and object_ref not in ctx.objects:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E8804",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Instance row '@extends/object_ref' target '{object_ref}' is class id; "
                                "instance inheritance requires object id."
                            ),
                            path=f"{row_path}.object_ref",
                        )
                    )
                object_payload = ctx.objects.get(object_ref)
                if isinstance(object_payload, dict):
                    candidate_class_ref = object_payload.get("class_ref")
                    if isinstance(candidate_class_ref, str) and candidate_class_ref:
                        derived_class_ref = candidate_class_ref

        if not isinstance(class_ref, str) or not class_ref:
            class_ref = derived_class_ref
        elif isinstance(derived_class_ref, str) and derived_class_ref and class_ref != derived_class_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E2403",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Instance class_ref '{class_ref}' does not match object_ref '{object_ref}' "
                        f"class_ref '{derived_class_ref}'."
                    ),
                    path=f"{row_path}.class_ref",
                )
            )

        if not isinstance(class_ref, str) or not class_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=(
                        "Instance row must define non-empty 'class_ref' or provide "
                        "object_ref with resolvable class_ref."
                    ),
                    path=f"{row_path}.class_ref",
                )
            )

        return class_ref, object_ref

    def _secret_resolve_binding_row(
        self,
        *,
        row: dict[str, Any],
        group_name: str,
        row_index: int,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        semantic_registry: SemanticKeywordRegistry,
        row_annotations_by_instance: dict[str, dict[str, dict[str, Any]]],
        object_secret_annotations_by_object: dict[str, dict[str, dict[str, Any]]],
        annotation_formats: dict[str, dict[str, Any]],
        secrets_root: Path,
        mode: str,
        require_unlock: bool,
    ) -> dict[str, Any] | None:
        row_path = f"instance_bindings.{group_name}[{row_index}]"
        normalized_row = self._normalize_semantic_row(
            row=row,
            semantic_registry=semantic_registry,
            stage=stage,
            diagnostics=diagnostics,
            row_path=row_path,
        )
        if normalized_row is None:
            return None
        row = normalized_row
        instance_id = row.get("instance")

        if not isinstance(instance_id, str) or not instance_id:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Instance row must define non-empty 'instance'.",
                    path=f"{row_path}.instance",
                )
            )
            return None
        if "hardware_identity_secret_ref" in row:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=(
                        "Field 'hardware_identity_secret_ref' is deprecated and forbidden. "
                        "Store encrypted secret data adjacent to target fields."
                    ),
                    path=f"{row_path}.hardware_identity_secret_ref",
                )
            )

        row_annotations = row_annotations_by_instance.get(instance_id)
        if not isinstance(row_annotations, dict):
            row_annotations = self._collect_row_annotations(row)

        object_secret_annotations: dict[str, dict[str, Any]] = {}
        object_ref_for_annotations = row.get("object_ref")
        if isinstance(object_ref_for_annotations, str):
            candidate_object_annotations = object_secret_annotations_by_object.get(object_ref_for_annotations)
            if isinstance(candidate_object_annotations, dict):
                object_secret_annotations = candidate_object_annotations

        merged_secret_annotations = self._merge_secret_annotations(
            row_annotations=row_annotations,
            object_secret_annotations=object_secret_annotations,
        )

        row = self._resolve_sidecar_secrets(
            row=row,
            instance_id=instance_id,
            secrets_root=secrets_root,
            stage=stage,
            diagnostics=diagnostics,
            row_path=row_path,
            mode=mode,
            require_unlock=require_unlock,
            row_annotations=merged_secret_annotations,
            annotation_formats=annotation_formats,
        )

        if mode == "strict":
            unresolved_paths = self._collect_all_placeholder_paths(row, row_annotations=merged_secret_annotations)
            for unresolved_path in unresolved_paths:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7208",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Strict secrets mode requires resolved placeholder: "
                            f"'{unresolved_path}' in instance '{instance_id}'."
                        ),
                        path=row_path,
                    )
                )

        return {
            "group": group_name,
            "row_index": row_index,
            "instance": instance_id,
            "row": row,
        }

    def _resolve_binding_row(
        self,
        *,
        secret_resolved_row: dict[str, Any],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        seen_instances: set[str],
    ) -> dict[str, Any] | None:
        row = secret_resolved_row.get("row")
        group_name = secret_resolved_row.get("group")
        instance_id = secret_resolved_row.get("instance")
        row_index = secret_resolved_row.get("row_index")

        if (
            not isinstance(row, dict)
            or not isinstance(group_name, str)
            or not isinstance(instance_id, str)
            or not isinstance(row_index, int)
        ):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Secret-resolved row payload is malformed.",
                    path="pipeline:instance_rows_secret_resolve",
                )
            )
            return None

        row_path = f"instance_bindings.{group_name}[{row_index}]"
        if contains_unsafe_identifier_chars(instance_id):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=(
                        f"instance id '{instance_id}' contains filename-unsafe characters; "
                        "use only cross-platform filename-safe symbols."
                    ),
                    path=f"{row_path}.instance",
                )
            )
            return None
        if instance_id in seen_instances:
            diagnostics.append(
                PluginDiagnostic(
                    code="E2102",
                    severity="error",
                    stage="resolve",
                    message=f"Duplicate instance '{instance_id}'.",
                    path=row_path,
                    plugin_id=self.plugin_id,
                )
            )
            return None
        seen_instances.add(instance_id)

        return {
            "group": group_name,
            "instance": instance_id,
            "row": row,
        }

    def _build_secret_resolved_rows(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> list[dict[str, Any]]:
        bindings_root = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(bindings_root, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="instance-bindings root must contain mapping 'instance_bindings'.",
                    path="instance_bindings",
                )
            )
            return []

        rows: list[dict[str, Any]] = []
        mode = self._resolve_secrets_mode(ctx)
        require_unlock = self._resolve_require_unlock(ctx)
        semantic_keywords_raw = ctx.config.get("semantic_keywords_path")
        semantic_keywords_path = (
            Path(semantic_keywords_raw) if isinstance(semantic_keywords_raw, str) and semantic_keywords_raw else None
        )
        semantic_registry = load_semantic_keyword_registry(semantic_keywords_path)
        row_annotations_by_instance, object_secret_annotations_by_object, annotation_formats = (
            self._load_annotation_inputs(ctx)
        )
        secrets_root = self._resolve_secrets_root_path(ctx)

        for group_name, group_rows in bindings_root.items():
            if not isinstance(group_rows, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance_bindings.{group_name} must be a list.",
                        path=f"instance_bindings.{group_name}",
                    )
                )
                continue

            for idx, row in enumerate(group_rows):
                if not isinstance(row, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must be an object.",
                            path=f"instance_bindings.{group_name}[{idx}]",
                        )
                    )
                    continue

                secret_resolved_row = self._secret_resolve_binding_row(
                    row=row,
                    group_name=group_name,
                    row_index=idx,
                    ctx=ctx,
                    stage=stage,
                    diagnostics=diagnostics,
                    semantic_registry=semantic_registry,
                    row_annotations_by_instance=row_annotations_by_instance,
                    object_secret_annotations_by_object=object_secret_annotations_by_object,
                    annotation_formats=annotation_formats,
                    secrets_root=secrets_root,
                    mode=mode,
                    require_unlock=require_unlock,
                )
                if secret_resolved_row is None:
                    continue
                rows.append(secret_resolved_row)

        return rows

    def _prepare_resolved_row(
        self,
        *,
        resolved_row: dict[str, Any],
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        row = resolved_row.get("row")
        group_name = resolved_row.get("group")
        instance_id = resolved_row.get("instance")
        if not isinstance(row, dict) or not isinstance(group_name, str) or not isinstance(instance_id, str):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Resolved row payload is malformed.",
                    path="pipeline:instance_rows_resolve",
                )
            )
            return None

        class_ref, object_ref = self._resolve_class_and_object_refs(
            row=row,
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
            row_path=f"instance_bindings.{group_name}[{instance_id}]",
        )
        source_id = row.get("source_id", instance_id)
        if not isinstance(source_id, str) or not source_id:
            source_id = instance_id

        return {
            "group": group_name,
            "instance": instance_id,
            "row_path": f"instance_bindings.{group_name}[{instance_id}]",
            "row": row,
            "source_id": source_id,
            "class_ref": class_ref,
            "object_ref": object_ref,
        }

    def _validate_prepared_row_shape(
        self,
        *,
        prepared_row: dict[str, Any],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        row = prepared_row.get("row")
        group_name = prepared_row.get("group")
        instance_id = prepared_row.get("instance")
        row_path = prepared_row.get("row_path")
        class_ref = prepared_row.get("class_ref")
        object_ref = prepared_row.get("object_ref")
        source_id = prepared_row.get("source_id")

        if (
            not isinstance(row, dict)
            or not isinstance(group_name, str)
            or not isinstance(instance_id, str)
            or not isinstance(row_path, str)
        ):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Prepared row payload is malformed.",
                    path="pipeline:instance_rows_prepare",
                )
            )
            return None

        layer = row.get("layer")
        if not isinstance(layer, str) or not layer:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Instance row must define non-empty 'layer'.",
                    path=f"{row_path}.layer",
                )
            )

        firmware_ref = row.get("firmware_ref")
        if firmware_ref is not None and (not isinstance(firmware_ref, str) or not firmware_ref):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="firmware_ref must be non-empty string when set.",
                    path=f"{row_path}.firmware_ref",
                )
            )

        embedded_in = row.get("embedded_in")
        if embedded_in is not None and (not isinstance(embedded_in, str) or not embedded_in):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="embedded_in must be non-empty string when set.",
                    path=f"{row_path}.embedded_in",
                )
            )
            embedded_in = None

        normalized_os_refs = self._normalize_os_refs(
            os_refs=row.get("os_refs"),
            stage=stage,
            diagnostics=diagnostics,
            path_prefix=f"{row_path}.os_refs",
        )

        return {
            "group": group_name,
            "instance": instance_id,
            "layer": layer,
            "source_id": source_id if isinstance(source_id, str) and source_id else instance_id,
            "class_ref": class_ref,
            "object_ref": object_ref,
            "status": row.get("status", "pending"),
            "notes": row.get("notes", ""),
            "runtime": row.get("runtime"),
            "firmware_ref": firmware_ref if isinstance(firmware_ref, str) and firmware_ref else None,
            "os_refs": normalized_os_refs,
            "embedded_in": embedded_in if isinstance(embedded_in, str) and embedded_in else None,
            "extensions": self._extract_extensions(row),
        }

    def _build_resolved_rows(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        secret_resolved_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_instances: set[str] = set()

        source_rows = secret_resolved_rows if secret_resolved_rows is not None else self._build_secret_resolved_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
        )
        for secret_resolved_row in source_rows:
            if not isinstance(secret_resolved_row, dict):
                continue
            normalized_row = self._resolve_binding_row(
                secret_resolved_row=secret_resolved_row,
                stage=stage,
                diagnostics=diagnostics,
                seen_instances=seen_instances,
            )
            if normalized_row is None:
                continue
            rows.append(normalized_row)

        return rows

    def _build_prepared_rows(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        resolved_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        source_rows = resolved_rows if resolved_rows is not None else self._build_resolved_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
        )

        prepared_rows: list[dict[str, Any]] = []
        for resolved_row in source_rows:
            if not isinstance(resolved_row, dict):
                continue
            prepared_row = self._prepare_resolved_row(
                resolved_row=resolved_row,
                ctx=ctx,
                stage=stage,
                diagnostics=diagnostics,
            )
            if prepared_row is None:
                continue
            prepared_rows.append(prepared_row)
        return prepared_rows

    def _build_validated_rows(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        prepared_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        source_rows = prepared_rows if prepared_rows is not None else self._build_prepared_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
        )

        validated_rows: list[dict[str, Any]] = []
        for prepared_row in source_rows:
            if not isinstance(prepared_row, dict):
                continue
            validated_row = self._validate_prepared_row_shape(
                prepared_row=prepared_row,
                stage=stage,
                diagnostics=diagnostics,
            )
            if validated_row is None:
                continue
            validated_rows.append(validated_row)
        return validated_rows

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"normalized_rows": []})

        validated_rows: list[dict[str, Any]] | None = None
        if ctx.is_snapshot_backed:
            subscribed_validated_rows = ctx.subscribe(self._VALIDATED_ROWS_PLUGIN_ID, "validated_rows")
            if isinstance(subscribed_validated_rows, list):
                validated_rows = [row for row in subscribed_validated_rows if isinstance(row, dict)]
        else:
            try:
                subscribed_validated_rows = ctx.subscribe(self._VALIDATED_ROWS_PLUGIN_ID, "validated_rows")
                if isinstance(subscribed_validated_rows, list):
                    validated_rows = [row for row in subscribed_validated_rows if isinstance(row, dict)]
            except PluginDataExchangeError:
                validated_rows = None

        rows = validated_rows if validated_rows is not None else self._build_validated_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
        )

        ctx.publish("normalized_rows", rows)
        return self.make_result(diagnostics, output_data={"normalized_rows": rows})

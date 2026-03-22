"""ADR 0068 validator plugin: typed instance placeholders in object templates.

Validates object placeholder markers:
- @required:<format>
- @optional:<format>

And enforces instance-level override policy:
- only placeholder-marked paths may be overridden
- required placeholders must be overridden per instance
- override values must match declared format
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from field_annotations import parse_field_annotation
from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin

DEFAULT_FORMAT_REGISTRY = Path(__file__).resolve().parents[2] / "data" / "instance-field-formats.yaml"
DEFAULT_ENFORCEMENT_MODE = "enforce"
SUPPORTED_ENFORCEMENT_MODES = {"warn", "warn+gate-new", "enforce"}
DEFAULT_GATE_STATUSES = {"modeled", "mapped"}

class InstancePlaceholderValidator(ValidatorJsonPlugin):
    """Validate ADR0068 placeholder/override contract."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        bindings = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(bindings, dict):
            return self.make_result(diagnostics)

        enforcement_mode, gate_statuses = self._load_enforcement_policy(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
        )
        formats = self._load_format_registry(ctx, stage, diagnostics)
        object_placeholders: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}

        for object_id, object_payload in ctx.objects.items():
            if not isinstance(object_payload, dict):
                continue
            object_placeholders[object_id] = self._collect_object_placeholders(
                object_id=object_id,
                payload=object_payload,
                formats=formats,
                stage=stage,
                diagnostics=diagnostics,
            )

        for group_name, group_rows in bindings.items():
            if not isinstance(group_rows, list):
                continue
            for row in group_rows:
                if not isinstance(row, dict):
                    continue
                self._validate_instance_row(
                    ctx=ctx,
                    stage=stage,
                    diagnostics=diagnostics,
                    group_name=group_name,
                    row=row,
                    object_placeholders=object_placeholders,
                    formats=formats,
                    enforcement_mode=enforcement_mode,
                    gate_statuses=gate_statuses,
                )

        return self.make_result(diagnostics)

    def _load_format_registry(
        self,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, dict[str, Any]]:
        configured = ctx.config.get("format_registry_path")
        registry_path = Path(configured) if isinstance(configured, str) and configured else DEFAULT_FORMAT_REGISTRY
        if not registry_path.is_absolute():
            registry_path = (Path(__file__).resolve().parents[2] / registry_path).resolve()

        try:
            payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # pragma: no cover - defensive path
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=f"Cannot load ADR0068 format registry '{registry_path}': {exc}",
                    path="plugin:base.validator.instance_placeholders",
                )
            )
            return {}

        formats = payload.get("formats")
        if not isinstance(formats, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=f"ADR0068 format registry '{registry_path}' must contain mapping 'formats'.",
                    path="plugin:base.validator.instance_placeholders",
                )
            )
            return {}

        result: dict[str, dict[str, Any]] = {}
        for name, spec in formats.items():
            if isinstance(name, str) and isinstance(spec, dict):
                result[name] = spec
        return result

    def _load_enforcement_policy(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> tuple[str, set[str]]:
        mode = ctx.config.get("enforcement_mode", DEFAULT_ENFORCEMENT_MODE)
        if not isinstance(mode, str) or mode not in SUPPORTED_ENFORCEMENT_MODES:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=(
                        "Invalid ADR0068 enforcement_mode. " f"Expected one of: {sorted(SUPPORTED_ENFORCEMENT_MODES)}."
                    ),
                    path="plugin:base.validator.instance_placeholders.enforcement_mode",
                )
            )
            mode = DEFAULT_ENFORCEMENT_MODE

        gate_statuses_cfg = ctx.config.get("gate_statuses")
        if gate_statuses_cfg is None:
            return mode, set(DEFAULT_GATE_STATUSES)
        if not isinstance(gate_statuses_cfg, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="ADR0068 gate_statuses must be an array of strings when provided.",
                    path="plugin:base.validator.instance_placeholders.gate_statuses",
                )
            )
            return mode, set(DEFAULT_GATE_STATUSES)

        gate_statuses: set[str] = set()
        for idx, token in enumerate(gate_statuses_cfg):
            if not isinstance(token, str) or not token.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message="ADR0068 gate_statuses entries must be non-empty strings.",
                        path=f"plugin:base.validator.instance_placeholders.gate_statuses[{idx}]",
                    )
                )
                continue
            gate_statuses.add(token.strip().lower())

        return mode, (gate_statuses if gate_statuses else set(DEFAULT_GATE_STATUSES))

    def _collect_object_placeholders(
        self,
        *,
        object_id: str,
        payload: dict[str, Any],
        formats: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[tuple[Any, ...], dict[str, Any]]:
        placeholders: dict[tuple[Any, ...], dict[str, Any]] = {}

        def walk(node: Any, path: tuple[Any, ...]) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, path + (key,))
                return
            if isinstance(node, list):
                for idx, item in enumerate(node):
                    walk(item, path + (idx,))
                return
            if not isinstance(node, str):
                return
            if node.startswith("@@"):
                return
            if not node.startswith("@"):
                return

            annotation, annotation_error = parse_field_annotation(node)
            if annotation_error:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6801",
                        severity="error",
                        stage=stage,
                        message=f"Invalid annotation '{node}': {annotation_error}.",
                        path=f"object:{object_id}:{self._format_path(path)}",
                    )
                )
                return
            if annotation is None:
                return
            if not annotation.required and not annotation.optional:
                # Marker without required/optional semantics (e.g. @secret)
                # is valid, but not part of ADR0068 override contract.
                return
            fmt = annotation.value_type
            if not isinstance(fmt, str) or not fmt:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6801",
                        severity="error",
                        stage=stage,
                        message=f"Annotation '{node}' must declare value type suffix ':<format>'.",
                        path=f"object:{object_id}:{self._format_path(path)}",
                    )
                )
                return

            if fmt not in formats:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6801",
                        severity="error",
                        stage=stage,
                        message=f"Placeholder format '{fmt}' is not defined in format registry.",
                        path=f"object:{object_id}:{self._format_path(path)}",
                    )
                )
                return
            placeholders[path] = {"required": annotation.required, "format": fmt, "secret": annotation.secret}

        walk(payload, ())
        return placeholders

    def _validate_instance_row(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        group_name: str,
        row: dict[str, Any],
        object_placeholders: dict[str, dict[tuple[Any, ...], dict[str, Any]]],
        formats: dict[str, dict[str, Any]],
        enforcement_mode: str,
        gate_statuses: set[str],
    ) -> None:
        object_ref = row.get("object_ref")
        if not isinstance(object_ref, str) or object_ref not in ctx.objects:
            return

        instance_id = row.get("instance", "<unknown>")
        path_prefix = f"instance:{group_name}:{instance_id}"
        strict = self._is_strict_row(
            row=row,
            enforcement_mode=enforcement_mode,
            gate_statuses=gate_statuses,
        )
        placeholders = object_placeholders.get(object_ref, {})
        object_payload = ctx.objects.get(object_ref)
        if not isinstance(object_payload, dict):
            return

        overrides_payload = row.get("instance_overrides")
        if overrides_payload is None:
            override_values: dict[tuple[Any, ...], Any] = {}
        elif not isinstance(overrides_payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="instance_overrides must be an object when provided.",
                    path=f"{path_prefix}.instance_overrides",
                )
            )
            return
        else:
            override_values = {}
            self._flatten_override_values(overrides_payload, (), override_values)

        unresolved_markers = self._collect_unresolved_markers(
            row=row,
            path_prefix=path_prefix,
        )
        for marker_path, marker_value in unresolved_markers:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6806",
                    severity=self._policy_severity(strict),
                    stage=stage,
                    message=(
                        f"Unresolved placeholder marker '{marker_value}' found in instance payload; "
                        "replace it with a concrete value."
                    ),
                    path=marker_path,
                )
            )

        # Compatibility bridge: allow instance identity map to provide values
        # for object ethernet[*].mac placeholders without explicit instance_overrides.
        derived_identity_overrides, derived_identity_sources = self._derive_hardware_identity_overrides(
            row=row,
            object_payload=object_payload,
            placeholders=placeholders,
        )
        for path_key, derived_value in derived_identity_overrides.items():
            override_values.setdefault(path_key, derived_value)

        for override_path, value in override_values.items():
            placeholder_spec = placeholders.get(override_path)
            if placeholder_spec is None:
                code = "E6803" if self._path_exists(object_payload, override_path) else "E6804"
                message = (
                    f"Override path '{self._format_path(override_path)}' is not marked as placeholder."
                    if code == "E6803"
                    else f"Override path '{self._format_path(override_path)}' does not exist in object template."
                )
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity=self._policy_severity(strict),
                        stage=stage,
                        message=message,
                        path=self._resolve_override_diagnostic_path(
                            path_prefix=path_prefix,
                            override_path=override_path,
                            derived_sources=derived_identity_sources,
                        ),
                    )
                )
                continue

            fmt = placeholder_spec.get("format")
            if not isinstance(fmt, str) or fmt not in formats:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6805",
                        severity=self._policy_severity(strict),
                        stage=stage,
                        message=f"Unknown declared format '{fmt}' for override path '{self._format_path(override_path)}'.",
                        path=self._resolve_override_diagnostic_path(
                            path_prefix=path_prefix,
                            override_path=override_path,
                            derived_sources=derived_identity_sources,
                        ),
                    )
                )
                continue

            ok, reason = self._validate_format(value, formats[fmt])
            if not ok:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6805",
                        severity=self._policy_severity(strict),
                        stage=stage,
                        message=(
                            f"Override value for '{self._format_path(override_path)}' does not satisfy "
                            f"format '{fmt}': {reason}"
                        ),
                        path=self._resolve_override_diagnostic_path(
                            path_prefix=path_prefix,
                            override_path=override_path,
                            derived_sources=derived_identity_sources,
                        ),
                    )
                )

        for placeholder_path, placeholder_spec in placeholders.items():
            if placeholder_spec.get("required") and placeholder_path not in override_values:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E6802",
                        severity=self._policy_severity(strict),
                        stage=stage,
                        message=(
                            f"Required placeholder '{self._format_path(placeholder_path)}' is missing "
                            "in instance payload."
                        ),
                        path=path_prefix,
                    )
                )

    @staticmethod
    def _policy_severity(strict: bool) -> str:
        return "error" if strict else "warning"

    def _is_strict_row(
        self,
        *,
        row: dict[str, Any],
        enforcement_mode: str,
        gate_statuses: set[str],
    ) -> bool:
        if enforcement_mode == "enforce":
            return True
        if enforcement_mode == "warn":
            return False
        row_status = row.get("status")
        if not isinstance(row_status, str):
            return False
        return row_status.strip().lower() in gate_statuses

    def _collect_unresolved_markers(
        self,
        *,
        row: dict[str, Any],
        path_prefix: str,
    ) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        seen: set[str] = set()

        def walk(node: Any, path: tuple[Any, ...]) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, path + (key,))
                return
            if isinstance(node, list):
                for idx, item in enumerate(node):
                    walk(item, path + (idx,))
                return
            if not isinstance(node, str):
                return
            annotation, annotation_error = parse_field_annotation(node)
            if annotation_error is not None or annotation is None:
                return
            if annotation.secret:
                # Secret markers are resolved by side-car secrets flow.
                return
            formatted = self._format_path(path)
            if formatted in seen:
                return
            seen.add(formatted)
            found.append((f"{path_prefix}.{formatted}", node))

        overrides_payload = row.get("instance_overrides")
        if isinstance(overrides_payload, dict):
            walk(overrides_payload, ("instance_overrides",))
        hardware_identity = row.get("hardware_identity")
        if isinstance(hardware_identity, dict):
            walk(hardware_identity, ("hardware_identity",))
        return found

    def _derive_hardware_identity_overrides(
        self,
        *,
        row: dict[str, Any],
        object_payload: dict[str, Any],
        placeholders: dict[tuple[Any, ...], dict[str, Any]],
    ) -> tuple[dict[tuple[Any, ...], Any], dict[tuple[Any, ...], str]]:
        hardware_identity = row.get("hardware_identity")
        if not isinstance(hardware_identity, dict):
            return {}, {}
        mac_addresses = hardware_identity.get("mac_addresses")
        if not isinstance(mac_addresses, dict):
            return {}, {}

        derived: dict[tuple[Any, ...], Any] = {}
        source_paths: dict[tuple[Any, ...], str] = {}
        for path in placeholders:
            if not path:
                continue
            if path[-1] != "mac":
                continue
            candidate_keys = self._interface_identity_candidate_keys(object_payload, path[:-1])
            if not candidate_keys:
                continue
            for key in candidate_keys:
                if key in mac_addresses:
                    value = mac_addresses[key]
                    if isinstance(value, str):
                        annotation, annotation_error = parse_field_annotation(value)
                        if annotation_error is None and annotation is not None:
                            # Annotation marker is not a concrete override value.
                            continue
                    derived[path] = value
                    source_paths[path] = f"hardware_identity.mac_addresses.{key}"
                    break
        return derived, source_paths

    def _interface_identity_candidate_keys(
        self,
        object_payload: dict[str, Any],
        interface_path: tuple[Any, ...],
    ) -> list[str]:
        iface_name = self._get_path_value(object_payload, interface_path + ("name",))
        if not isinstance(iface_name, str) or not iface_name:
            return []
        keys = [iface_name]
        # Backward-compatible alias for existing instance naming style:
        # wlan0 + band 5ghz => wlan0_5ghz ; wlan1 + 2.4ghz => wlan1_2_4ghz.
        band = self._get_path_value(object_payload, interface_path + ("band",))
        if isinstance(band, str) and band:
            normalized_band = band.replace(".", "_").replace("-", "_")
            keys.append(f"{iface_name}_{normalized_band}")
        return keys

    def _resolve_override_diagnostic_path(
        self,
        *,
        path_prefix: str,
        override_path: tuple[Any, ...],
        derived_sources: dict[tuple[Any, ...], str],
    ) -> str:
        source_path = derived_sources.get(override_path)
        if source_path:
            return f"{path_prefix}.{source_path}"
        return f"{path_prefix}.instance_overrides.{self._format_path(override_path)}"

    def _get_path_value(self, payload: Any, path: tuple[Any, ...]) -> Any:
        node = payload
        for token in path:
            if isinstance(node, dict):
                if token not in node:
                    return None
                node = node[token]
                continue
            if isinstance(node, list):
                if not isinstance(token, int) or token < 0 or token >= len(node):
                    return None
                node = node[token]
                continue
            return None
        return node

    def _flatten_override_values(
        self,
        node: Any,
        path: tuple[Any, ...],
        out: dict[tuple[Any, ...], Any],
    ) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                self._flatten_override_values(value, path + (key,), out)
            return
        out[path] = node

    def _path_exists(self, payload: Any, path: tuple[Any, ...]) -> bool:
        node = payload
        for token in path:
            if isinstance(node, dict):
                if token not in node:
                    return False
                node = node[token]
                continue
            if isinstance(node, list) and isinstance(token, int):
                if token < 0 or token >= len(node):
                    return False
                node = node[token]
                continue
            return False
        return True

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

        fmt_kind = spec.get("kind")
        if fmt_kind == "regex" and spec.get("pattern") is None:
            return False, "registry regex format requires pattern"
        if spec.get("validator") is None and spec.get("pattern") is None and fmt_kind == "network":
            return False, "network format requires validator"

        return True, "ok"

    def _format_path(self, path: tuple[Any, ...]) -> str:
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

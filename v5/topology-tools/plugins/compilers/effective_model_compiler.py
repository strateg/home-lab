"""Effective model candidate compiler plugin (ADR 0069 WS2).

Builds a parity-focused candidate compiled model from loaded class/object
modules and instance bindings. During migration, this mirrors legacy effective
assembly so parity gate can compare equivalent payloads.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capability_derivation import default_firmware_policy as shared_default_firmware_policy
from capability_derivation import derive_firmware_capabilities as shared_derive_firmware_capabilities
from capability_derivation import derive_os_capabilities as shared_derive_os_capabilities
from capability_derivation import extract_firmware_properties as shared_extract_firmware_properties
from capability_derivation import extract_os_properties as shared_extract_os_properties
from capability_derivation import normalize_release_token as shared_normalize_release_token
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _manifest_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EffectiveModelCompiler(CompilerPlugin):
    """Assemble candidate effective model in compile stage."""

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
        "extensions",
    }

    @staticmethod
    def _normalize_release_token(value: str) -> str:
        return shared_normalize_release_token(value)

    @staticmethod
    def _default_firmware_policy(class_id: str) -> str:
        return shared_default_firmware_policy(class_id)

    @staticmethod
    def _extract_firmware_properties(object_payload: dict[str, Any]) -> dict[str, Any]:
        return shared_extract_firmware_properties(object_payload)

    def _extract_os_properties(self, object_payload: dict[str, Any]) -> dict[str, Any] | None:
        _ = self
        return shared_extract_os_properties(object_payload)

    def _derive_firmware_capabilities(
        self, *, object_payload: dict[str, Any]
    ) -> tuple[set[str], dict[str, Any] | None]:
        return shared_derive_firmware_capabilities(
            object_id="plugin-effective-model",
            object_payload=object_payload,
            catalog_ids=set(),
            path="plugin:effective_model",
            add_diag=lambda **_: None,
            emit_diagnostics=False,
        )

    def _derive_os_capabilities(self, *, object_payload: dict[str, Any]) -> tuple[set[str], dict[str, Any] | None]:
        return shared_derive_os_capabilities(
            object_id="plugin-effective-model",
            object_payload=object_payload,
            catalog_ids=set(),
            path="plugin:effective_model",
            add_diag=lambda **_: None,
            emit_diagnostics=False,
        )

    @staticmethod
    def _extract_extensions(row: dict[str, Any]) -> dict[str, Any]:
        extensions: dict[str, Any] = {}
        for key in sorted(row.keys()):
            if key in EffectiveModelCompiler._RESERVED_ROW_KEYS:
                continue
            extensions[key] = row[key]
        return extensions

    @staticmethod
    def _normalize_instance_rows(raw_bindings: dict[str, Any], *, objects: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_instances: set[str] = set()
        for group_name, group_rows in raw_bindings.items():
            if not isinstance(group_rows, list):
                continue

            for row in group_rows:
                if not isinstance(row, dict):
                    continue

                instance_id = row.get("instance")
                if not isinstance(instance_id, str) or not instance_id:
                    continue
                if instance_id in seen_instances:
                    continue
                seen_instances.add(instance_id)

                os_refs = row.get("os_refs")
                if not isinstance(os_refs, list):
                    os_refs = []
                normalized_os_refs: list[str] = []
                for os_ref in os_refs:
                    if isinstance(os_ref, str) and os_ref:
                        normalized_os_refs.append(os_ref)

                embedded_in = row.get("embedded_in")
                if not isinstance(embedded_in, str) or not embedded_in:
                    embedded_in = None

                firmware_ref = row.get("firmware_ref")
                if not isinstance(firmware_ref, str) or not firmware_ref:
                    firmware_ref = None

                object_ref = row.get("object_ref")
                class_ref = row.get("class_ref")
                if (not isinstance(class_ref, str) or not class_ref) and isinstance(object_ref, str) and object_ref:
                    object_payload = objects.get(object_ref)
                    if isinstance(object_payload, dict):
                        candidate = object_payload.get("class_ref")
                        if isinstance(candidate, str) and candidate:
                            class_ref = candidate
                if not isinstance(class_ref, str) or not class_ref:
                    class_ref = None
                source_id = row.get("source_id", instance_id)
                if not isinstance(source_id, str) or not source_id:
                    source_id = instance_id
                extensions = row.get("extensions")
                if not isinstance(extensions, dict):
                    extensions = EffectiveModelCompiler._extract_extensions(row)

                rows.append(
                    {
                        "group": group_name,
                        "instance": instance_id,
                        "layer": row.get("layer"),
                        "source_id": source_id,
                        "class_ref": class_ref,
                        "object_ref": object_ref,
                        "status": row.get("status", "pending"),
                        "notes": row.get("notes", ""),
                        "runtime": row.get("runtime"),
                        "firmware_ref": firmware_ref,
                        "os_refs": normalized_os_refs,
                        "embedded_in": embedded_in,
                        "extensions": extensions,
                    }
                )
        return rows

    @staticmethod
    def _collect_output_matches(
        plugin_outputs: Any,
        *,
        key: str,
    ) -> list[tuple[str, Any]]:
        if not isinstance(plugin_outputs, dict):
            return []
        matches: list[tuple[str, Any]] = []
        for plugin_id, payload in plugin_outputs.items():
            if not isinstance(plugin_id, str):
                continue
            if not isinstance(payload, dict):
                continue
            if key in payload:
                matches.append((plugin_id, payload[key]))
        return matches

    def _derive_object_effective(
        self, *, objects: dict[str, Any]
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
        object_derived_caps: dict[str, list[str]] = {}
        object_effective_os: dict[str, dict[str, Any]] = {}
        for object_id, payload in objects.items():
            object_payload = payload if isinstance(payload, dict) else {}
            os_caps, effective_os = self._derive_os_capabilities(object_payload=object_payload)
            object_derived_caps[object_id] = sorted(os_caps)
            if effective_os:
                object_effective_os[object_id] = effective_os
        return object_derived_caps, object_effective_os

    def _derive_instance_effective(
        self, *, rows: list[dict[str, Any]], objects: dict[str, Any]
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, Any]]]:
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        instance_derived_caps: dict[str, list[str]] = {}
        instance_software_refs: dict[str, dict[str, Any]] = {}

        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue

            firmware_ref = row.get("firmware_ref")
            os_refs = row.get("os_refs", []) or []
            if not isinstance(os_refs, list):
                os_refs = []

            derived_caps: set[str] = set()
            firmware_effective: dict[str, Any] | None = None

            firmware_row: dict[str, Any] | None = None
            if isinstance(firmware_ref, str):
                candidate = row_by_id.get(firmware_ref)
                if isinstance(candidate, dict):
                    firmware_row = candidate

            if isinstance(firmware_row, dict):
                firmware_object_ref = firmware_row.get("object_ref")
                if isinstance(firmware_object_ref, str):
                    firmware_object_payload = objects.get(firmware_object_ref, {})
                    if not isinstance(firmware_object_payload, dict):
                        firmware_object_payload = {}
                    fw_caps, fw_effective = self._derive_firmware_capabilities(object_payload=firmware_object_payload)
                    derived_caps.update(fw_caps)
                    firmware_effective = fw_effective

            resolved_os_refs: list[str] = []
            resolved_os_effective: list[dict[str, Any]] = []
            for os_ref in os_refs:
                os_row = row_by_id.get(os_ref)
                if not isinstance(os_row, dict):
                    continue
                if os_row.get("class_ref") != "class.os":
                    continue
                os_object_ref = os_row.get("object_ref")
                if not isinstance(os_object_ref, str):
                    continue
                os_object_payload = objects.get(os_object_ref, {})
                if not isinstance(os_object_payload, dict):
                    os_object_payload = {}
                os_caps, os_effective = self._derive_os_capabilities(object_payload=os_object_payload)
                derived_caps.update(os_caps)
                if isinstance(os_effective, dict):
                    resolved_os_effective.append(os_effective)
                os_instance_id = os_row.get("instance")
                if isinstance(os_instance_id, str):
                    resolved_os_refs.append(os_instance_id)

            instance_derived_caps[row_id] = sorted(derived_caps)
            instance_software_refs[row_id] = {
                "firmware_ref": firmware_ref if isinstance(firmware_ref, str) else None,
                "os_refs": resolved_os_refs,
                "effective": {
                    "firmware": firmware_effective,
                    "os": resolved_os_effective,
                },
            }

        return instance_derived_caps, instance_software_refs

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        raw_bindings = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(raw_bindings, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="instance_bindings must contain mapping 'instance_bindings'.",
                    path="instance_bindings",
                )
            )
            return self.make_result(diagnostics)

        plugin_rows = None
        normalized_row_matches = self._collect_output_matches(ctx.plugin_outputs, key="normalized_rows")
        if len(normalized_row_matches) == 1:
            plugin_rows = normalized_row_matches[0][1]
        elif len(normalized_row_matches) > 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6901",
                    severity="error",
                    stage=stage,
                    message=(
                        "Ambiguous compiler output 'normalized_rows' published by "
                        f"{[plugin_id for plugin_id, _ in normalized_row_matches]}."
                    ),
                    path="pipeline:mode",
                )
            )
        config_rows = ctx.config.get("normalized_rows")
        if isinstance(plugin_rows, list):
            rows = [row for row in plugin_rows if isinstance(row, dict)]
        elif isinstance(config_rows, list) and config_rows:
            rows = [row for row in config_rows if isinstance(row, dict)]
        else:
            rows = self._normalize_instance_rows(raw_bindings, objects=ctx.objects)
        object_derived_caps, object_effective_os = self._derive_object_effective(objects=ctx.objects)
        instance_derived_caps, instance_software_refs = self._derive_instance_effective(rows=rows, objects=ctx.objects)

        classes_index: dict[str, Any] = {
            class_id: payload for class_id, payload in sorted(ctx.classes.items(), key=lambda item: item[0])
        }
        objects_index: dict[str, Any] = {
            object_id: payload for object_id, payload in sorted(ctx.objects.items(), key=lambda item: item[0])
        }

        by_group: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            group_name = row.get("group")
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            instance_id = row.get("instance")

            class_payload = ctx.classes.get(class_ref, {}) if isinstance(class_ref, str) else {}
            if not isinstance(class_payload, dict):
                class_payload = {}
            object_payload = ctx.objects.get(object_ref, {}) if isinstance(object_ref, str) else {}
            if not isinstance(object_payload, dict):
                object_payload = {}

            effective_item: dict[str, Any] = {
                "instance_id": instance_id,
                "instance": instance_id,
                "source_id": row.get("source_id", instance_id),
                "layer": row.get("layer"),
                "class_ref": class_ref,
                "object_ref": object_ref,
                "status": row.get("status"),
                "notes": row.get("notes"),
                "runtime": row.get("runtime"),
                "class": {
                    "version": class_payload.get("version"),
                    "os_policy": class_payload.get("os_policy", "allowed"),
                    "firmware_policy": class_payload.get(
                        "firmware_policy",
                        self._default_firmware_policy(class_ref if isinstance(class_ref, str) else ""),
                    ),
                    "os_cardinality": class_payload.get("os_cardinality"),
                    "multi_boot": class_payload.get("multi_boot", False),
                    "required_capabilities": class_payload.get("required_capabilities", []),
                    "optional_capabilities": class_payload.get("optional_capabilities", []),
                    "capability_packs": class_payload.get("capability_packs", []),
                },
                "object": {
                    "version": object_payload.get("version"),
                    "enabled_capabilities": object_payload.get("enabled_capabilities", []),
                    "enabled_packs": object_payload.get("enabled_packs", []),
                    "derived_capabilities": object_derived_caps.get(object_ref, []),
                    "vendor_capabilities": object_payload.get("vendor_capabilities", []),
                    "vendor": object_payload.get("vendor"),
                    "model": object_payload.get("model"),
                },
            }
            row_extensions = row.get("extensions")
            if isinstance(row_extensions, dict) and row_extensions:
                effective_item["instance_data"] = row_extensions

            software_refs = instance_software_refs.get(instance_id) if isinstance(instance_id, str) else None
            if isinstance(software_refs, dict):
                effective_item["instance"] = {
                    "firmware_ref": software_refs.get("firmware_ref"),
                    "os_refs": software_refs.get("os_refs", []),
                    "derived_capabilities": instance_derived_caps.get(instance_id, []),
                    "effective_software": software_refs.get("effective", {}),
                }

            effective_os = object_effective_os.get(object_ref) if isinstance(object_ref, str) else None
            if isinstance(effective_os, dict):
                effective_item["object"]["software"] = {"os": effective_os}

            prerequisites = object_payload.get("prerequisites")
            if isinstance(prerequisites, dict):
                os_ref = prerequisites.get("os_ref")
                if isinstance(os_ref, str) and os_ref:
                    effective_item["object"]["prerequisites"] = {"os_ref": os_ref}

            by_group.setdefault(group_name, []).append(effective_item)

        for group_rows in by_group.values():
            group_rows.sort(key=lambda item: str(item.get("instance", "")))

        raw_manifest = ctx.raw_yaml if isinstance(ctx.raw_yaml, dict) else {}
        generated_at = ctx.config.get("compile_generated_at")
        if not isinstance(generated_at, str) or not generated_at:
            generated_at = _utc_now()
        compiled_model_version = ctx.config.get("compiled_model_version", "1.0")
        if not isinstance(compiled_model_version, str) or not compiled_model_version:
            compiled_model_version = "1.0"
        compiler_pipeline_version = ctx.config.get("compiler_pipeline_version", "adr0069-ws2")
        if not isinstance(compiler_pipeline_version, str) or not compiler_pipeline_version:
            compiler_pipeline_version = "adr0069-ws2"
        source_manifest_digest = ctx.config.get("source_manifest_digest")
        if not isinstance(source_manifest_digest, str) or not source_manifest_digest:
            source_manifest_digest = _manifest_digest(raw_manifest)
        candidate = {
            "version": raw_manifest.get("version", "5.0.0"),
            "model": raw_manifest.get("model", "class-object-instance"),
            "generated_at": generated_at,
            "compiled_model_version": compiled_model_version,
            "compiled_at": generated_at,
            "compiler_pipeline_version": compiler_pipeline_version,
            "source_manifest_digest": source_manifest_digest,
            "topology_manifest": ctx.topology_path,
            "classes": classes_index,
            "objects": objects_index,
            "instances": by_group,
        }

        # Publish for dependent plugins and place into compiled_json candidate.
        ctx.publish("effective_model_candidate", candidate)
        ctx.compiled_json = candidate

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"effective_model_candidate": candidate},
        )

"""Effective model candidate compiler plugin (ADR 0069 WS2).

Builds a parity-focused candidate compiled model from loaded class/object
modules and instance bindings. During migration, this mirrors legacy effective
assembly so parity gate can compare equivalent payloads.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from capability_derivation import default_firmware_policy as shared_default_firmware_policy
from capability_derivation import derive_firmware_capabilities as shared_derive_firmware_capabilities
from capability_derivation import derive_os_capabilities as shared_derive_os_capabilities
from capability_derivation import extract_firmware_properties as shared_extract_firmware_properties
from capability_derivation import extract_os_properties as shared_extract_os_properties
from capability_derivation import normalize_release_token as shared_normalize_release_token
from kernel.plugin_base import (
    CompilerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _manifest_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EffectiveModelCompiler(CompilerPlugin):
    """Assemble candidate effective model in compile stage."""

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
    def _subscribe_required(ctx: PluginContext, *, plugin_id: str, key: str) -> Any:
        try:
            return ctx.subscribe(plugin_id, key)
        except PluginDataExchangeError as exc:
            raise PluginDataExchangeError(f"Missing required published key '{key}' from '{plugin_id}': {exc}") from exc

    @staticmethod
    def _build_class_lineage_map(*, classes: dict[str, Any]) -> dict[str, list[str]]:
        class_lineage: dict[str, list[str]] = {}
        class_ids = {class_id for class_id in classes if isinstance(class_id, str)}

        for class_id in sorted(class_ids):
            chain: list[str] = []
            visited: set[str] = set()
            cursor = class_id
            while cursor in class_ids and cursor not in visited:
                visited.add(cursor)
                chain.append(cursor)
                payload = classes.get(cursor, {})
                parent_ref = payload.get("extends") if isinstance(payload, dict) else None
                if not isinstance(parent_ref, str) or not parent_ref:
                    break
                cursor = parent_ref
            class_lineage[class_id] = list(reversed(chain))
        return class_lineage

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

        plugin_rows: Any = None
        try:
            plugin_rows = self._subscribe_required(
                ctx,
                plugin_id="base.compiler.instance_rows",
                key="normalized_rows",
            )
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6901",
                    severity="error",
                    stage=stage,
                    message=str(exc),
                    path="pipeline:mode",
                )
            )
        if isinstance(plugin_rows, list):
            rows = [row for row in plugin_rows if isinstance(row, dict)]
        else:
            rows = []
        object_derived_caps, object_effective_os = self._derive_object_effective(objects=ctx.objects)
        instance_derived_caps, instance_software_refs = self._derive_instance_effective(rows=rows, objects=ctx.objects)
        class_lineage_map = self._build_class_lineage_map(classes=ctx.classes)

        classes_index: dict[str, Any] = {}
        for class_id, payload in sorted(ctx.classes.items(), key=lambda item: item[0]):
            class_payload = payload if isinstance(payload, dict) else {}
            parent_class = class_payload.get("extends") if isinstance(class_payload.get("extends"), str) else None
            normalized_class = dict(class_payload)
            normalized_class["parent_class"] = parent_class
            normalized_class["lineage"] = class_lineage_map.get(class_id, [class_id])
            classes_index[class_id] = normalized_class

        objects_index: dict[str, Any] = {}
        for object_id, payload in sorted(ctx.objects.items(), key=lambda item: item[0]):
            object_payload = payload if isinstance(payload, dict) else {}
            class_ref = object_payload.get("class_ref") if isinstance(object_payload.get("class_ref"), str) else None
            normalized_object = dict(object_payload)
            normalized_object["extends_class"] = class_ref
            normalized_object["materializes_class"] = class_ref
            if isinstance(class_ref, str) and class_ref:
                normalized_object["class_lineage"] = class_lineage_map.get(class_ref, [class_ref])
            else:
                normalized_object["class_lineage"] = []
            objects_index[object_id] = normalized_object

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
            class_parent = class_payload.get("extends") if isinstance(class_payload.get("extends"), str) else None
            object_class_ref = object_payload.get("class_ref") if isinstance(object_payload.get("class_ref"), str) else None
            if isinstance(class_ref, str) and class_ref:
                resolved_lineage = class_lineage_map.get(class_ref, [class_ref])
            else:
                resolved_lineage = []

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
                    "parent_class": class_parent,
                    "lineage": resolved_lineage,
                },
                "object": {
                    "version": object_payload.get("version"),
                    "enabled_capabilities": object_payload.get("enabled_capabilities", []),
                    "enabled_packs": object_payload.get("enabled_packs", []),
                    "derived_capabilities": object_derived_caps.get(object_ref, []),
                    "vendor_capabilities": object_payload.get("vendor_capabilities", []),
                    "vendor": object_payload.get("vendor"),
                    "model": object_payload.get("model"),
                    "extends_class": object_class_ref,
                    "materializes_class": object_class_ref,
                    "class_lineage": class_lineage_map.get(object_class_ref, [object_class_ref])
                    if isinstance(object_class_ref, str) and object_class_ref
                    else [],
                },
            }
            row_extensions = row.get("extensions")
            if isinstance(row_extensions, dict) and row_extensions:
                effective_item["instance_data"] = row_extensions

            instance_block: dict[str, Any] = {
                "extends_object": object_ref if isinstance(object_ref, str) else None,
                "materializes_object": object_ref if isinstance(object_ref, str) else None,
                "materializes_class": class_ref if isinstance(class_ref, str) else None,
                "resolved_lineage": resolved_lineage,
                "firmware_ref": None,
                "os_refs": [],
                "derived_capabilities": instance_derived_caps.get(instance_id, []),
                "effective_software": {},
            }
            software_refs = instance_software_refs.get(instance_id) if isinstance(instance_id, str) else None
            if isinstance(software_refs, dict):
                instance_block["firmware_ref"] = software_refs.get("firmware_ref")
                instance_block["os_refs"] = software_refs.get("os_refs", [])
                instance_block["effective_software"] = software_refs.get("effective", {})
            effective_item["instance"] = instance_block

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

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

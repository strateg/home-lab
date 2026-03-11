"""Instance rows normalization compiler plugin (ADR 0069 WS2/WS3)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class InstanceRowsCompiler(CompilerPlugin):
    """Normalize instance_bindings rows and emit row-shape diagnostics."""

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
    }

    @classmethod
    def _extract_extensions(cls, row: dict[str, Any]) -> dict[str, Any]:
        extensions: dict[str, Any] = {}
        for key in sorted(row.keys()):
            if key in cls._RESERVED_ROW_KEYS:
                continue
            extensions[key] = row[key]
        return extensions

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"normalized_rows": ctx.config.get("normalized_rows", [])})

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
            rows: list[dict[str, Any]] = []
            ctx.publish("normalized_rows", rows)
            ctx.config["normalized_rows"] = rows
            return self.make_result(diagnostics, output_data={"normalized_rows": rows})

        rows = []
        seen_instances: set[str] = set()
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

                instance_id = row.get("instance")
                layer = row.get("layer")
                class_ref = row.get("class_ref")
                object_ref = row.get("object_ref")
                firmware_ref = row.get("firmware_ref")
                os_refs = row.get("os_refs")
                derived_class_ref: str | None = None

                if not isinstance(instance_id, str) or not instance_id:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must define non-empty 'instance'.",
                            path=f"instance_bindings.{group_name}[{idx}].instance",
                        )
                    )
                    continue
                if instance_id in seen_instances:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E2102",
                            severity="error",
                            stage="resolve",
                            message=f"Duplicate instance '{instance_id}'.",
                            path=f"instance_bindings.{group_name}[{idx}]",
                            plugin_id=self.plugin_id,
                        )
                    )
                    continue
                seen_instances.add(instance_id)

                if not isinstance(object_ref, str) or not object_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must define non-empty 'object_ref'.",
                            path=f"instance_bindings.{group_name}[{idx}].object_ref",
                        )
                    )
                else:
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
                            path=f"instance_bindings.{group_name}[{idx}].class_ref",
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
                            path=f"instance_bindings.{group_name}[{idx}].class_ref",
                        )
                    )
                if not isinstance(layer, str) or not layer:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must define non-empty 'layer'.",
                            path=f"instance_bindings.{group_name}[{idx}].layer",
                        )
                    )
                if firmware_ref is not None and (not isinstance(firmware_ref, str) or not firmware_ref):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="firmware_ref must be non-empty string when set.",
                            path=f"instance_bindings.{group_name}[{idx}].firmware_ref",
                        )
                    )
                if os_refs is not None and not isinstance(os_refs, list):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="os_refs must be a list when set.",
                            path=f"instance_bindings.{group_name}[{idx}].os_refs",
                        )
                    )
                    os_refs = []

                embedded_in = row.get("embedded_in")
                if embedded_in is not None and (not isinstance(embedded_in, str) or not embedded_in):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="embedded_in must be non-empty string when set.",
                            path=f"instance_bindings.{group_name}[{idx}].embedded_in",
                        )
                    )
                    embedded_in = None

                normalized_os_refs: list[str] = []
                if isinstance(os_refs, list):
                    for os_idx, os_ref in enumerate(os_refs):
                        if not isinstance(os_ref, str) or not os_ref:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E3201",
                                    severity="error",
                                    stage=stage,
                                    message="os_refs entries must be non-empty strings.",
                                    path=f"instance_bindings.{group_name}[{idx}].os_refs[{os_idx}]",
                                )
                            )
                            continue
                        normalized_os_refs.append(os_ref)

                source_id = row.get("source_id", instance_id)
                if not isinstance(source_id, str) or not source_id:
                    source_id = instance_id
                extensions = self._extract_extensions(row)

                rows.append(
                    {
                        "group": group_name,
                        "instance": instance_id,
                        "layer": layer,
                        "source_id": source_id,
                        "class_ref": class_ref,
                        "object_ref": object_ref,
                        "status": row.get("status", "pending"),
                        "notes": row.get("notes", ""),
                        "runtime": row.get("runtime"),
                        "firmware_ref": firmware_ref if isinstance(firmware_ref, str) and firmware_ref else None,
                        "os_refs": normalized_os_refs,
                        "embedded_in": embedded_in if isinstance(embedded_in, str) and embedded_in else None,
                        "extensions": extensions,
                    }
                )

        ctx.publish("normalized_rows", rows)
        ctx.config["normalized_rows"] = rows
        return self.make_result(diagnostics, output_data={"normalized_rows": rows})

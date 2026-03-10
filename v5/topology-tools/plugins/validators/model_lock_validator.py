"""Model lock validation plugin for v5 topology compiler (ADR 0069 WS3).

Mirrors legacy `_validate_model_lock` semantics and can take ownership from
core validation in plugin-first mode.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


class ModelLockValidator(ValidatorJsonPlugin):
    """Validate model.lock pinning and version consistency."""

    @staticmethod
    def _normalize_rows(bindings: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_instances: set[str] = set()
        for group_name, group_rows in bindings.items():
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
                rows.append(
                    {
                        "group": group_name,
                        "instance": instance_id,
                        "class_ref": row.get("class_ref"),
                        "object_ref": row.get("object_ref"),
                    }
                )
        return rows

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Keep legacy core as owner when runtime explicitly marks ownership.
        # If ownership key is absent, execute plugin for standalone tests/usages.
        owner = ctx.config.get("validation_owner_model_lock")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        strict_mode = bool(ctx.config.get("strict_mode", False))
        model_lock_loaded = bool(ctx.config.get("model_lock_loaded", False))

        if not model_lock_loaded:
            if strict_mode:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=Stage.VALIDATE,
                        message="model.lock is required in strict mode.",
                        path="model.lock",
                    )
                )
            else:
                diagnostics.append(
                    PluginDiagnostic(
                        code="W2401",
                        severity="warning",
                        stage="load",
                        message="model.lock is missing; pinning checks skipped.",
                        path="model.lock",
                        plugin_id=self.plugin_id,
                    )
                )
            return self.make_result(diagnostics)

        diagnostics.append(
            PluginDiagnostic(
                code="I2401",
                severity="info",
                stage="load",
                message="model.lock loaded.",
                path="model.lock",
                plugin_id=self.plugin_id,
                confidence=1.0,
            )
        )

        lock_payload = ctx.model_lock if isinstance(ctx.model_lock, dict) else {}
        lock_classes = lock_payload.get("classes")
        lock_objects = lock_payload.get("objects")
        if not isinstance(lock_classes, dict) or not isinstance(lock_objects, dict):
            diagnostics.append(
                PluginDiagnostic(
                    code="E2402",
                    severity="error",
                    stage="load",
                    message="model.lock must define mapping keys: classes and objects.",
                    path="model.lock",
                    plugin_id=self.plugin_id,
                )
            )
            return self.make_result(diagnostics)

        bindings = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(bindings, dict):
            return self.make_result(diagnostics)
        rows = self._normalize_rows(bindings)

        for row in rows:
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            path = f"instance:{row.get('group')}:{row.get('instance')}"

            if not isinstance(class_ref, str) or not class_ref:
                continue
            if not isinstance(object_ref, str) or not object_ref:
                continue

            class_pin = lock_classes.get(class_ref)
            object_pin = lock_objects.get(object_ref)

            if class_pin is None:
                if strict_mode:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                            path=path,
                        )
                    )
                else:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W2402",
                            severity="warning",
                            stage=stage,
                            message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                            path=path,
                        )
                    )

            if object_pin is None:
                if strict_mode:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                            path=path,
                        )
                    )
                else:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W2403",
                            severity="warning",
                            stage=stage,
                            message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                            path=path,
                        )
                    )

            if isinstance(object_pin, dict):
                pinned_class_ref = object_pin.get("class_ref")
                if isinstance(pinned_class_ref, str) and pinned_class_ref and pinned_class_ref != class_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2403",
                            severity="error",
                            stage=stage,
                            message=(
                                f"object_ref '{object_ref}' requires class_ref '{pinned_class_ref}' "
                                f"per model.lock, got '{class_ref}'."
                            ),
                            path=path,
                        )
                    )

            class_module = ctx.classes.get(class_ref)
            class_module_version = class_module.get("version") if isinstance(class_module, dict) else None
            if isinstance(class_pin, dict):
                class_pin_version = class_pin.get("version")
                if (
                    isinstance(class_module_version, str)
                    and isinstance(class_pin_version, str)
                    and class_module_version != class_pin_version
                ):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W3201",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"class_ref '{class_ref}' version mismatch: "
                                f"module='{class_module_version}' lock='{class_pin_version}'."
                            ),
                            path=path,
                        )
                    )

            object_module = ctx.objects.get(object_ref)
            object_module_version = object_module.get("version") if isinstance(object_module, dict) else None
            if isinstance(object_pin, dict):
                object_pin_version = object_pin.get("version")
                if (
                    isinstance(object_module_version, str)
                    and isinstance(object_pin_version, str)
                    and object_module_version != object_pin_version
                ):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W3201",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"object_ref '{object_ref}' version mismatch: "
                                f"module='{object_module_version}' lock='{object_pin_version}'."
                            ),
                            path=path,
                        )
                    )

        return self.make_result(diagnostics)

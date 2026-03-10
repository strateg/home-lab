"""Model lock validation plugin for v5 topology compiler (ADR 0063).

This plugin validates that all class_ref and object_ref values are pinned
in model.lock.yaml when --strict-model-lock is enabled.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import (
    PluginContext,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class ModelLockValidator(ValidatorJsonPlugin):
    """Validates model.lock pinning for all class_ref and object_ref values."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Validate model.lock pins."""
        diagnostics: list[PluginDiagnostic] = []

        # Skip if not in strict mode
        if not ctx.config.get("strict_mode", False):
            return self.make_result(diagnostics)

        lock = ctx.model_lock
        if not lock:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W2401",
                    severity="warning",
                    stage=stage,
                    message="model.lock is missing or empty",
                    path="model.lock",
                    hint="Create model.lock.yaml to pin class and object versions",
                )
            )
            return self.make_result(diagnostics)

        # Build lookup sets from model.lock
        lock_classes = lock.get("classes", {})
        lock_objects = lock.get("objects", {})

        pinned_class_ids = set(lock_classes.keys()) if isinstance(lock_classes, dict) else set()
        pinned_object_ids = set(lock_objects.keys()) if isinstance(lock_objects, dict) else set()

        # Check each instance
        bindings = ctx.instance_bindings.get("instance_bindings", {})

        for group_name, rows in bindings.items():
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue

                instance_id = row.get("id", "<unknown>")
                path = f"instance:{group_name}:{instance_id}"

                # Validate class_ref is pinned
                class_ref = row.get("class_ref")
                if class_ref and class_ref not in pinned_class_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                            path=path,
                            hint="Add class to model.lock.yaml classes section",
                        )
                    )

                # Validate object_ref is pinned
                object_ref = row.get("object_ref")
                if object_ref and object_ref not in pinned_object_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                            path=path,
                            hint="Add object to model.lock.yaml objects section",
                        )
                    )

        return self.make_result(diagnostics)

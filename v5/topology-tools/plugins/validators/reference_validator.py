"""Reference validation plugin for v5 topology compiler (ADR 0063).

This plugin validates that all instance references point to valid targets:
- class_ref -> class exists
- object_ref -> object exists
- firmware_ref -> firmware instance exists
- os_refs -> OS instances exist
- embedded_in -> firmware instance exists
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent to path for kernel imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import (
    PluginContext,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class ReferenceValidator(ValidatorJsonPlugin):
    """Validates all cross-entity references in compiled topology."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Validate references in instance bindings."""
        diagnostics: list[PluginDiagnostic] = []

        # Build lookup sets
        class_ids = set(ctx.classes.keys())
        object_ids = set(ctx.objects.keys())
        firmware_ids: set[str] = set()
        os_ids: set[str] = set()
        device_ids: set[str] = set()

        # Collect instance IDs by type
        bindings = ctx.instance_bindings.get("instance_bindings", {})

        for row in bindings.get("l1_software_firmware", []):
            if isinstance(row, dict) and row.get("id"):
                firmware_ids.add(row["id"])

        for row in bindings.get("l1_software_os", []):
            if isinstance(row, dict) and row.get("id"):
                os_ids.add(row["id"])

        for row in bindings.get("l1_devices", []):
            if isinstance(row, dict) and row.get("id"):
                device_ids.add(row["id"])

        for row in bindings.get("l4_lxc", []):
            if isinstance(row, dict) and row.get("id"):
                device_ids.add(row["id"])

        # Validate each group
        for group_name, rows in bindings.items():
            if not isinstance(rows, list):
                continue

            for row in rows:
                if not isinstance(row, dict):
                    continue

                instance_id = row.get("id", "<unknown>")
                path = f"instance:{group_name}:{instance_id}"

                # Validate class_ref
                class_ref = row.get("class_ref")
                if class_ref and class_ref not in class_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2101",
                            severity="error",
                            stage=stage,
                            message=f"class_ref '{class_ref}' not found in loaded classes",
                            path=path,
                            hint=f"Available classes: {', '.join(sorted(class_ids)[:5])}...",
                        )
                    )

                # Validate object_ref
                object_ref = row.get("object_ref")
                if object_ref and object_ref not in object_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2101",
                            severity="error",
                            stage=stage,
                            message=f"object_ref '{object_ref}' not found in loaded objects",
                            path=path,
                            hint="Check object exists in object-modules directory",
                        )
                    )

                # Validate firmware_ref
                firmware_ref = row.get("firmware_ref")
                if firmware_ref and firmware_ref not in firmware_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2101",
                            severity="error",
                            stage=stage,
                            message=f"firmware_ref '{firmware_ref}' not found",
                            path=path,
                            hint="Add firmware instance to l1_software_firmware group",
                        )
                    )

                # Validate os_refs
                os_refs = row.get("os_refs", [])
                if isinstance(os_refs, list):
                    for os_ref in os_refs:
                        if os_ref and os_ref not in os_ids:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E2101",
                                    severity="error",
                                    stage=stage,
                                    message=f"os_ref '{os_ref}' not found",
                                    path=path,
                                    hint="Add OS instance to l1_software_os group",
                                )
                            )

                # Validate embedded_in (for OS instances)
                embedded_in = row.get("embedded_in")
                if embedded_in and embedded_in not in firmware_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2101",
                            severity="error",
                            stage=stage,
                            message=f"embedded_in '{embedded_in}' not found",
                            path=path,
                            hint="embedded_in must reference a firmware instance",
                        )
                    )

                # Validate runtime.target_ref (for services)
                runtime = row.get("runtime")
                if isinstance(runtime, dict):
                    target_ref = runtime.get("target_ref")
                    if target_ref and target_ref not in device_ids:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E2101",
                                severity="error",
                                stage=stage,
                                message=f"runtime.target_ref '{target_ref}' not found",
                                path=path,
                                hint="Target must be an L1 device or L4 workload",
                            )
                        )

        return self.make_result(diagnostics)

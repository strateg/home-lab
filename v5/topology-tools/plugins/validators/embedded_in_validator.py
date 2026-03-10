"""Embedded_in validation plugin for v5 topology compiler (ADR 0063/0064).

This plugin validates the embedded_in relationship between OS and firmware:
- embedded_in must reference a valid firmware instance
- Circular references are not allowed
- Firmware instance must exist in l1_software_firmware group
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


class EmbeddedInValidator(ValidatorJsonPlugin):
    """Validates embedded_in references for OS instances (ADR 0064)."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Validate embedded_in references."""
        diagnostics: list[PluginDiagnostic] = []

        bindings = ctx.instance_bindings.get("instance_bindings", {})

        # Collect firmware instance IDs
        firmware_ids: set[str] = set()
        for row in bindings.get("l1_software_firmware", []):
            if isinstance(row, dict) and row.get("instance"):
                firmware_ids.add(row["instance"])

        # Validate OS instances
        for row in bindings.get("l1_software_os", []):
            if not isinstance(row, dict):
                continue

            instance_id = row.get("instance", "<unknown>")
            path = f"instance:l1_software_os:{instance_id}"

            embedded_in = row.get("embedded_in")
            if not embedded_in:
                # embedded_in is optional - OS can be standalone
                continue

            # Validate embedded_in references a firmware instance
            if embedded_in not in firmware_ids:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E2102",
                        severity="error",
                        stage=stage,
                        message=f"embedded_in '{embedded_in}' is not a valid firmware instance",
                        path=path,
                        hint=f"Available firmware: {', '.join(sorted(firmware_ids)[:5])}..."
                        if firmware_ids
                        else "No firmware instances defined in l1_software_firmware",
                    )
                )

            # Check for self-reference (shouldn't happen but guard against it)
            if embedded_in == instance_id:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E2103",
                        severity="error",
                        stage=stage,
                        message="OS instance cannot be embedded_in itself",
                        path=path,
                        hint="Remove circular embedded_in reference",
                    )
                )

        return self.make_result(diagnostics)

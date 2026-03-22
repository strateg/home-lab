"""Module-level validator for MikroTik router ethernet port inventory."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorJsonPlugin


class MikrotikRouterPortsValidator(ValidatorJsonPlugin):
    """Validate ethernet list shape for router-class MikroTik objects."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        for object_id, payload in ctx.objects.items():
            if not (isinstance(object_id, str) and object_id.startswith("obj.mikrotik.")):
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("class_ref") != "class.router":
                continue

            hardware_specs = payload.get("hardware_specs")
            if not isinstance(hardware_specs, dict):
                # Virtual router objects (for example CHR) may not expose hardware sections.
                continue
            interfaces = hardware_specs.get("interfaces")
            if not isinstance(interfaces, dict):
                continue
            ethernet = interfaces.get("ethernet")
            if ethernet is None:
                continue
            if not isinstance(ethernet, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7302",
                        severity="error",
                        stage=stage,
                        message="hardware_specs.interfaces.ethernet must be a list when provided.",
                        path=f"object:{object_id}:hardware_specs.interfaces.ethernet",
                    )
                )
                continue

            seen: set[str] = set()
            for index, port in enumerate(ethernet):
                if not isinstance(port, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7302",
                            severity="error",
                            stage=stage,
                            message="Ethernet port entries must be objects.",
                            path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}]",
                        )
                    )
                    continue
                name = port.get("name")
                if not isinstance(name, str) or not name:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7302",
                            severity="error",
                            stage=stage,
                            message="Ethernet port entry must define non-empty 'name'.",
                            path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}].name",
                        )
                    )
                    continue
                if name in seen:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7302",
                            severity="error",
                            stage=stage,
                            message=f"Duplicate ethernet port name '{name}'.",
                            path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}].name",
                        )
                    )
                seen.add(name)

        return self.make_result(diagnostics)

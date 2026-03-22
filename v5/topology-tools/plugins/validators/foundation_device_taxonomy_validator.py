"""Foundation device taxonomy validator for L1 instance groups."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class FoundationDeviceTaxonomyValidator(ValidatorJsonPlugin):
    """Validate L1 group/class taxonomy conventions."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7851",
                    severity="error",
                    stage=stage,
                    message=f"foundation_device_taxonomy validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        for row in rows:
            if row.get("layer") != "L1":
                continue
            group = row.get("group")
            class_ref = row.get("class_ref")
            row_id = row.get("instance")
            path = f"instance:{group}:{row_id}.class_ref"

            if not isinstance(group, str) or not isinstance(class_ref, str):
                continue

            if group == "devices":
                if not (class_ref == "class.router" or class_ref.startswith("class.compute.")):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7851",
                            severity="error",
                            stage=stage,
                            message=(
                                f"L1 group 'devices' expects compute/router classes, got '{class_ref}' "
                                f"for instance '{row_id}'."
                            ),
                            path=path,
                        )
                    )
            elif group == "firmware":
                if class_ref != "class.firmware":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7851",
                            severity="error",
                            stage=stage,
                            message=f"L1 group 'firmware' expects class.firmware, got '{class_ref}'.",
                            path=path,
                        )
                    )
            elif group == "os":
                if class_ref != "class.os":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7851",
                            severity="error",
                            stage=stage,
                            message=f"L1 group 'os' expects class.os, got '{class_ref}'.",
                            path=path,
                        )
                    )
            elif group == "physical-links":
                if class_ref != "class.network.physical_link":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7851",
                            severity="error",
                            stage=stage,
                            message=(
                                "L1 group 'physical-links' expects class.network.physical_link, "
                                f"got '{class_ref}'."
                            ),
                            path=path,
                        )
                    )
            elif group == "power":
                if not class_ref.startswith("class.power."):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7851",
                            severity="error",
                            stage=stage,
                            message=f"L1 group 'power' expects class.power.* classes, got '{class_ref}'.",
                            path=path,
                        )
                    )

        return self.make_result(diagnostics)

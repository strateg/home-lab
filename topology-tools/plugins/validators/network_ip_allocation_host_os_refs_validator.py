"""Mode H network ip_allocation ownership validator."""

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


class NetworkIpAllocationHostOsRefsValidator(ValidatorJsonPlugin):
    """Validate Mode H network ip_allocations ownership fields."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _NETWORK_CLASS_EXCLUSIONS = {
        "class.network.bridge",
        "class.network.trust_zone",
        "class.network.firewall_policy",
        "class.network.firewall_rule",
        "class.network.data_link",
        "class.network.physical_link",
        "class.network.qos",
    }

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7827",
                    severity="error",
                    stage=stage,
                    message=f"ip_allocation_host_os_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        for row in rows:
            if not self._is_network_row(row):
                continue
            row_id = row.get("instance")
            ip_allocations, allocations_path = self._resolve_allocations(ctx=ctx, row=row)
            if not isinstance(ip_allocations, list):
                continue
            for idx, alloc in enumerate(ip_allocations):
                if not isinstance(alloc, dict):
                    continue
                device_ref = alloc.get("device_ref")
                ip_value = alloc.get("ip", "unknown")
                path = f"{allocations_path}[{idx}]"

                if "host_os_ref" in alloc:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7827",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Network '{row_id}' ip_allocation '{ip_value}': "
                                "host_os_ref is forbidden in Mode H; use device_ref ownership only."
                            ),
                            path=f"{path}.host_os_ref",
                        )
                    )
                    continue

                if isinstance(device_ref, str) and device_ref:
                    continue

                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7827",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Network '{row_id}' ip_allocation '{ip_value}': "
                            "device_ref is required in Mode H."
                        ),
                        path=f"{path}.device_ref",
                    )
                )

        return self.make_result(diagnostics)

    @staticmethod
    def _resolve_allocations(*, ctx: PluginContext, row: dict[str, Any]) -> tuple[Any, str]:
        extensions = row.get("extensions")
        row_prefix = f"instance:{row.get('group')}:{row.get('instance')}"
        if isinstance(extensions, dict) and "ip_allocations" in extensions:
            return extensions.get("ip_allocations"), f"{row_prefix}.extensions.ip_allocations"
        if "ip_allocations" in row:
            return row.get("ip_allocations"), f"{row_prefix}.ip_allocations"
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        if isinstance(properties, dict):
            return properties.get("ip_allocations"), f"{row_prefix}.ip_allocations"
        return None, f"{row_prefix}.ip_allocations"

    def _is_network_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if not isinstance(class_ref, str):
            return False
        if not class_ref.startswith("class.network."):
            return False
        if class_ref in self._NETWORK_CLASS_EXCLUSIONS:
            return False
        return row.get("layer") in {None, "L2"}

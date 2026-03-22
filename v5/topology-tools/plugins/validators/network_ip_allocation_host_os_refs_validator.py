"""IP allocation host_os_ref validator for network rows."""

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
    """Validate host_os_ref usage inside network ip_allocations lists."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

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
        row_by_id: dict[str, dict[str, Any]] = {}
        host_os_ids: set[str] = set()
        for row in rows:
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            row_by_id[row_id] = row
            if row.get("class_ref") == "class.os":
                host_os_ids.add(row_id)
        has_host_os_inventory = bool(host_os_ids)

        for row in rows:
            if row.get("class_ref") != "class.network.vlan":
                continue
            row_id = row.get("instance")
            group = row.get("group")
            ip_allocations = self._resolve_field(ctx=ctx, row=row, key="ip_allocations")
            if not isinstance(ip_allocations, list):
                continue
            for idx, alloc in enumerate(ip_allocations):
                if not isinstance(alloc, dict):
                    continue
                host_os_ref = alloc.get("host_os_ref")
                device_ref = alloc.get("device_ref")
                ip_value = alloc.get("ip", "unknown")
                path = f"instance:{group}:{row_id}.ip_allocations[{idx}]"

                if isinstance(host_os_ref, str) and host_os_ref:
                    target = row_by_id.get(host_os_ref)
                    if host_os_ref not in host_os_ids or not isinstance(target, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7827",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Network '{row_id}' ip_allocation '{ip_value}': host_os_ref "
                                    f"'{host_os_ref}' does not reference a known class.os instance."
                                ),
                                path=f"{path}.host_os_ref",
                            )
                        )
                        continue

                    if isinstance(device_ref, str) and device_ref:
                        device_row = row_by_id.get(device_ref)
                        if isinstance(device_row, dict):
                            os_refs = device_row.get("os_refs")
                            if isinstance(os_refs, list) and os_refs and host_os_ref not in os_refs:
                                diagnostics.append(
                                    self.emit_diagnostic(
                                        code="W7828",
                                        severity="warning",
                                        stage=stage,
                                        message=(
                                            f"Network '{row_id}' ip_allocation '{ip_value}': host_os_ref "
                                            f"'{host_os_ref}' is not listed in device '{device_ref}' os_refs."
                                        ),
                                        path=f"{path}.host_os_ref",
                                    )
                                )

                elif has_host_os_inventory and isinstance(device_ref, str) and device_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7828",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Network '{row_id}' ip_allocation '{ip_value}': device_ref '{device_ref}' is set "
                                "without host_os_ref while host OS inventory exists."
                            ),
                            path=f"{path}.device_ref",
                        )
                    )

        return self.make_result(diagnostics)

    @staticmethod
    def _resolve_field(*, ctx: PluginContext, row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict) and key in extensions:
            return extensions.get(key)
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        if isinstance(properties, dict):
            return properties.get(key)
        return None

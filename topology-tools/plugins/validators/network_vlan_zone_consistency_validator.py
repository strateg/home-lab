"""VLAN/trust-zone consistency validator."""

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


class NetworkVlanZoneConsistencyValidator(ValidatorJsonPlugin):
    """Warn when VLAN id is outside trust-zone vlan_ids contract."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7829",
                    severity="error",
                    stage=stage,
                    message=f"vlan_zone_consistency validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        for row in rows:
            if row.get("class_ref") != "class.network.vlan":
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"

            vlan_id = self._resolve_field(ctx=ctx, row=row, key="vlan_id")
            trust_zone_ref = self._resolve_field(ctx=ctx, row=row, key="trust_zone_ref")
            if not isinstance(vlan_id, int) or not isinstance(trust_zone_ref, str) or not trust_zone_ref:
                continue

            zone_row = row_by_id.get(trust_zone_ref)
            if not isinstance(zone_row, dict):
                continue
            zone_object_ref = zone_row.get("object_ref")
            zone_object = ctx.objects.get(zone_object_ref) if isinstance(zone_object_ref, str) else None
            zone_properties = zone_object.get("properties") if isinstance(zone_object, dict) else None
            if not isinstance(zone_properties, dict):
                continue

            vlan_ids = zone_properties.get("vlan_ids")
            if vlan_ids is None:
                continue
            if not isinstance(vlan_ids, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7830",
                        severity="warning",
                        stage=stage,
                        message=f"Trust-zone '{trust_zone_ref}' property 'vlan_ids' should be a list when set.",
                        path=f"{row_prefix}.trust_zone_ref",
                    )
                )
                continue
            normalized_vlan_ids = [item for item in vlan_ids if isinstance(item, int)]
            if vlan_id not in normalized_vlan_ids:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7830",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"VLAN '{row_id}' id {vlan_id} is not present in trust-zone '{trust_zone_ref}' "
                            f"vlan_ids {normalized_vlan_ids}."
                        ),
                        path=f"{row_prefix}.trust_zone_ref",
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

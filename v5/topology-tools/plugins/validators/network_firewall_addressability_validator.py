"""Firewall addressability validator for network policy refs."""

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


class NetworkFirewallAddressabilityValidator(ValidatorJsonPlugin):
    """Warn when firewall policy refs cannot resolve to static address sets."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7823",
                    severity="error",
                    stage=stage,
                    message=f"network_firewall_addressability validator requires normalized rows: {exc}",
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

        network_cidr_by_id: dict[str, str] = {}
        zone_has_static_cidr: dict[str, bool] = {}
        for row in rows:
            if row.get("class_ref") != "class.network.vlan":
                continue
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            cidr = self._resolve_field(ctx=ctx, row=row, key="cidr")
            if isinstance(cidr, str) and cidr:
                network_cidr_by_id[row_id] = cidr

            trust_zone_ref = self._resolve_field(ctx=ctx, row=row, key="trust_zone_ref")
            if isinstance(trust_zone_ref, str) and trust_zone_ref:
                has_static = isinstance(cidr, str) and cidr and cidr != "dhcp"
                zone_has_static_cidr[trust_zone_ref] = zone_has_static_cidr.get(trust_zone_ref, False) or has_static

        for row in rows:
            if row.get("class_ref") != "class.network.firewall_policy":
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"

            for key in ("source_network_ref", "destination_network_ref"):
                network_ref = self._resolve_field(ctx=ctx, row=row, key=key)
                if not isinstance(network_ref, str) or not network_ref:
                    continue
                cidr = network_cidr_by_id.get(network_ref)
                if cidr == "dhcp":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7824",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Firewall policy '{row_id}': {key} '{network_ref}' resolves to dynamic "
                                "CIDR ('dhcp'); address-list matching may be incomplete."
                            ),
                            path=f"{row_prefix}.{key}",
                        )
                    )

            zone_refs: list[str] = []
            for key in ("source_zone_ref", "destination_zone_ref"):
                zone_ref = self._resolve_field(ctx=ctx, row=row, key=key)
                if isinstance(zone_ref, str) and zone_ref:
                    zone_refs.append(zone_ref)
            destination_zones_ref = self._resolve_field(ctx=ctx, row=row, key="destination_zones_ref")
            if isinstance(destination_zones_ref, list):
                for item in destination_zones_ref:
                    if isinstance(item, str) and item:
                        zone_refs.append(item)

            for zone_ref in zone_refs:
                if zone_ref == "untrusted":
                    continue
                if not zone_has_static_cidr.get(zone_ref, False):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7824",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Firewall policy '{row_id}': zone ref '{zone_ref}' has no static-CIDR "
                                "network instances; address-list derivation may be empty."
                            ),
                            path=f"{row_prefix}.zones",
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

"""VLAN tag consistency validator for workload network attachments."""

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


class NetworkVlanTagsValidator(ValidatorJsonPlugin):
    """Validate workload vlan_tag values against VLAN network contracts."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7838",
                    severity="error",
                    stage=stage,
                    message=f"vlan_tags validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        bridge_vlan_aware: dict[str, bool] = {}
        network_vlan_meta: dict[str, dict[str, Any]] = {}

        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        for row in rows:
            class_ref = row.get("class_ref")
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            if class_ref == "class.network.bridge":
                vlan_aware = self._resolve_field(ctx=ctx, row=row, key="vlan_aware")
                bridge_vlan_aware[row_id] = bool(vlan_aware)
            elif class_ref == "class.network.vlan":
                network_vlan_meta[row_id] = {
                    "vlan_id": self._resolve_field(ctx=ctx, row=row, key="vlan_id"),
                    "bridge_ref": self._resolve_field(ctx=ctx, row=row, key="bridge_ref"),
                }

        for row in rows:
            class_ref = row.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref.startswith("class.compute.workload"):
                continue
            row_id = row.get("instance")
            group = row.get("group")
            networks = self._resolve_field(ctx=ctx, row=row, key="networks")
            if not isinstance(networks, list):
                continue
            for idx, nic in enumerate(networks):
                if not isinstance(nic, dict):
                    continue
                network_ref = nic.get("network_ref")
                vlan_tag = nic.get("vlan_tag")
                nic_bridge_ref = nic.get("bridge_ref")
                path = f"instance:{group}:{row_id}.networks[{idx}]"

                if not isinstance(network_ref, str) or not network_ref:
                    continue
                network_meta = network_vlan_meta.get(network_ref)
                if network_meta is None:
                    continue

                network_vlan = network_meta.get("vlan_id")
                if isinstance(network_vlan, int):
                    if vlan_tag is None:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="W7839",
                                severity="warning",
                                stage=stage,
                                message=(
                                    f"Workload '{row_id}': network '{network_ref}' uses VLAN {network_vlan} "
                                    "but vlan_tag is not set."
                                ),
                                path=f"{path}.vlan_tag",
                            )
                        )
                    elif vlan_tag != network_vlan:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7838",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Workload '{row_id}': vlan_tag {vlan_tag} does not match "
                                    f"network '{network_ref}' VLAN {network_vlan}."
                                ),
                                path=f"{path}.vlan_tag",
                            )
                        )
                elif vlan_tag is not None:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7839",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"Workload '{row_id}': vlan_tag {vlan_tag} set but network '{network_ref}' "
                                "does not define vlan_id."
                            ),
                            path=f"{path}.vlan_tag",
                        )
                    )

                effective_bridge_ref = nic_bridge_ref if isinstance(nic_bridge_ref, str) and nic_bridge_ref else network_meta.get(
                    "bridge_ref"
                )
                if vlan_tag is not None and isinstance(effective_bridge_ref, str) and effective_bridge_ref:
                    if bridge_vlan_aware.get(effective_bridge_ref) is False:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="W7839",
                                severity="warning",
                                stage=stage,
                                message=(
                                    f"Workload '{row_id}': vlan_tag {vlan_tag} used on non-vlan-aware bridge "
                                    f"'{effective_bridge_ref}'."
                                ),
                                path=f"{path}.bridge_ref",
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

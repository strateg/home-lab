#!/usr/bin/env python3
"""MikroTik bridge-VLAN compiler plugin (W07 migration order item 4f).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md. Bridge
VLAN membership shape (WiFi interface VLAN-filtering entries) used to run
inside the MikroTik projection at generate stage; relocated here verbatim,
with no behavior change, so the fact exists at compile stage instead of
being invisible until render time.

Depends on `wifi_config` (W07 migration order item 4c), the same forward
dependency the W07 decision document recorded when 4c moved: the projection
already threads that channel into this function locally, so this plugin
subscribes to the compiler's channel instead of re-deriving it.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDataExchangeError, PluginDiagnostic, PluginResult, Stage


def _resolved_object_ref(row: dict[str, Any]) -> str:
    """Same resolution projection_core._resolved_object_ref uses."""
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_object", "materializes_object"):
            value = instance_block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


def _extract_bridge_vlans(
    routers: list[dict[str, Any]],
    wifi_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract bridge VLAN entries for WiFi interface VLAN membership.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _extract_bridge_vlans (W07 migration order item 4f).

    When bridge_vlan_filtering is enabled, WiFi interfaces must be explicitly
    added to bridge VLANs. Interfaces with datapaths that have no vlan_id go
    to VLAN 1 (untagged), interfaces with vlan_id go to that VLAN (tagged on bridge).

    Returns:
        List of bridge VLAN entries:
        [
            {"bridge": "bridge", "vlan_id": 1, "untagged": ["bridge", "wifi1", "wifi2"], "tagged": []},
            {"bridge": "bridge", "vlan_id": 55, "untagged": [], "tagged": ["bridge"]},
        ]
    """
    bridge_vlans: dict[int, dict[str, Any]] = {}  # vlan_id -> entry

    for router in routers:
        instance_data = router.get("instance_data", {})
        if not isinstance(instance_data, dict):
            continue

        observed = instance_data.get("observed_runtime", {})
        if not isinstance(observed, dict):
            continue

        lan = observed.get("lan", {})
        if not isinstance(lan, dict):
            continue

        # Check if VLAN filtering is enabled
        vlan_filtering = lan.get("bridge_vlan_filtering", False)
        if not vlan_filtering:
            continue

        bridge_name = str(lan.get("bridge_interface", "bridge")).strip() or "bridge"
        bridge_ports = lan.get("bridge_ports", [])
        if not isinstance(bridge_ports, list):
            bridge_ports = []

        # Build datapath -> vlan_id mapping from wifi_data
        datapath_vlan: dict[str, int] = {}  # datapath name -> vlan_id (0 means native/VLAN 1)
        for dp in wifi_data.get("datapaths", []):
            dp_name = str(dp.get("name", "")).strip()
            vlan_id = dp.get("vlan_id", 0)
            if dp_name:
                datapath_vlan[dp_name] = int(vlan_id) if vlan_id else 0

        # Build interface -> datapath mapping from wifi_data
        iface_datapath: dict[str, str] = {}  # interface name -> datapath name
        for cfg in wifi_data.get("configurations", []):
            cfg_name = str(cfg.get("name", "")).strip()
            dp_name = str(cfg.get("datapath", "")).strip()
            if cfg_name and dp_name:
                # Find interface using this configuration
                for iface in wifi_data.get("interfaces", []):
                    if str(iface.get("configuration", "")).strip() == cfg_name:
                        iface_name = str(iface.get("name", "")).strip()
                        if iface_name:
                            iface_datapath[iface_name] = dp_name

        # Initialize VLAN 1 with bridge itself as untagged
        if 1 not in bridge_vlans:
            bridge_vlans[1] = {
                "bridge": bridge_name,
                "vlan_id": 1,
                "untagged": [bridge_name],
                "tagged": [],
            }

        # Process each bridge port
        for port in bridge_ports:
            port_name = str(port).strip()
            if not port_name:
                continue

            # Check if this is a WiFi interface with a datapath
            dp_name = iface_datapath.get(port_name, "")
            vlan_id = datapath_vlan.get(dp_name, 0) if dp_name else 0

            if vlan_id == 0:
                # Native VLAN 1 - add as untagged
                if port_name not in bridge_vlans[1]["untagged"]:
                    bridge_vlans[1]["untagged"].append(port_name)
            else:
                # Tagged VLAN - create entry if needed
                if vlan_id not in bridge_vlans:
                    bridge_vlans[vlan_id] = {
                        "bridge": bridge_name,
                        "vlan_id": vlan_id,
                        "untagged": [],
                        "tagged": [bridge_name],  # Bridge itself is tagged for VLAN trunking
                    }
                # Add WiFi interface as untagged (it sends/receives untagged frames for this VLAN)
                if port_name not in bridge_vlans[vlan_id]["untagged"]:
                    bridge_vlans[vlan_id]["untagged"].append(port_name)

    return sorted(bridge_vlans.values(), key=lambda x: x.get("vlan_id", 0))


class MikrotikBridgeVlansCompiler(CompilerPlugin):
    """Derives MikroTik bridge-VLAN membership shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        if not isinstance(devices, list):
            devices = []

        routers = [
            row
            for row in devices
            if isinstance(row, dict) and _resolved_object_ref(row).startswith("obj.mikrotik.")
        ]

        try:
            wifi_data = ctx.subscribe("object.mikrotik.compiler.wifi_config", "wifi_config")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9204",
                    severity="error",
                    stage=stage,
                    message=f"failed to obtain wifi_config: {exc}",
                    path="plugin:object.mikrotik.compiler.bridge_vlans",
                )
            )
            return self.make_result(diagnostics)
        if not isinstance(wifi_data, dict):
            wifi_data = {}

        bridge_vlans = _extract_bridge_vlans(routers, wifi_data)

        diagnostics.append(
            self.emit_diagnostic(
                code="I4216",
                severity="info",
                stage=stage,
                message=f"Derived {len(bridge_vlans)} MikroTik bridge VLAN entr(y/ies)",
                path="plugin:object.mikrotik.compiler.bridge_vlans",
            )
        )

        ctx.publish("bridge_vlans", bridge_vlans)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bridge_vlans": bridge_vlans},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model and object.mikrotik.compiler.wifi_config, also
        # finalize). The kernel dispatches phase-specific hooks, not
        # execute() directly.
        return self.execute(ctx, stage)

#!/usr/bin/env python3
"""MikroTik WiFi configuration compiler plugin (W07 migration order item 4c).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md. WiFi
interface/VLAN membership shape (datapaths, configurations, security
profiles, interface bindings) used to run inside the MikroTik projection at
generate stage; relocated here verbatim, with no behavior change, so the
fact exists at compile stage instead of being invisible until render time.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


def _resolved_object_ref(row: dict[str, Any]) -> str:
    """Same resolution projection_core._resolved_object_ref uses."""
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_object", "materializes_object"):
            value = instance_block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


_MIKROTIK_ADAPTER = "cap.firewall.security_matrix.routeros"


def _is_mikrotik_enforcer(instance_id: Any, enforcer_resolution: dict[str, Any]) -> bool:
    """ADR 0118/0119 D-TYPE-1..3: is this instance a resolved RouterOS enforcer?

    Selection by declared capability (enforcer_resolution's adapter), not by
    object_ref name convention (ENFORCER-AXIS-CONFORMANCE.md V-14). A device
    with no device-kind capability, or whose OS family resolves a different
    (or no) adapter - rtr-slate, GL.iNet/OpenWrt, resolves enforcer type
    "network" but no adapter - no longer qualifies just because its object_ref
    happens to start with "obj.mikrotik.".
    """
    if not isinstance(instance_id, str) or not instance_id:
        return False
    resolution = enforcer_resolution.get(instance_id) if isinstance(enforcer_resolution, dict) else None
    return isinstance(resolution, dict) and resolution.get("adapter") == _MIKROTIK_ADAPTER


def _extract_wifi_config(routers: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract WiFi configuration from router instances.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _extract_wifi_config (W07 migration order item 4c).

    Returns:
        {
            "datapaths": [...],      # Unique datapath configurations
            "configurations": [...], # WiFi configurations (SSIDs)
            "securities": [...],     # Security profiles
            "interfaces": [...],     # Interface -> configuration bindings
                                     # (entries with master_interface are
                                     # virtual/slave APs that must be created)
        }
    """
    datapaths: dict[str, dict[str, Any]] = {}  # keyed by name to dedupe
    configurations: list[dict[str, Any]] = []
    securities: dict[str, dict[str, Any]] = {}  # keyed by name to dedupe
    interfaces: list[dict[str, Any]] = []

    for router in routers:
        instance_data = router.get("instance_data", {})
        if not isinstance(instance_data, dict):
            continue

        observed = instance_data.get("observed_runtime", {})
        if not isinstance(observed, dict):
            continue

        wifi_config = observed.get("wifi", {})
        if not isinstance(wifi_config, dict):
            continue

        for iface_name, iface_data in wifi_config.items():
            if not isinstance(iface_data, dict):
                continue

            ssid = iface_data.get("ssid")
            if not ssid:
                continue

            # Extract datapath
            datapath = iface_data.get("datapath")
            if isinstance(datapath, dict):
                dp_name = datapath.get("name", "")
                if dp_name and dp_name not in datapaths:
                    dp_entry: dict[str, Any] = {
                        "name": dp_name,
                        "bridge": datapath.get("bridge", "bridge"),
                        "comment": f"{ssid} datapath - managed by topology",
                    }
                    # Only include vlan_id if present and non-zero
                    vlan_id = datapath.get("vlan_id")
                    if vlan_id:
                        dp_entry["vlan_id"] = int(vlan_id)
                    datapaths[dp_name] = dp_entry

            # Extract security profile
            # Supports both string format ("wpa2-psk") and object format:
            # security:
            #   authentication_types: [wpa2-psk, wpa3-psk]
            #   fast_transition: true
            #   fast_transition_over_ds: true
            security = iface_data.get("security")
            sec_name = None
            if security:
                sec_name = f"sec-{iface_name}"
                if sec_name not in securities:
                    sec_entry: dict[str, Any] = {
                        "name": sec_name,
                        "passphrase": True,  # indicates variable needed
                        "comment": f"{ssid} security - managed by topology",
                    }
                    if isinstance(security, str):
                        # Simple string format: "wpa2-psk"
                        sec_entry["authentication_types"] = [security]
                    elif isinstance(security, dict):
                        # Object format with WPA3/FT support
                        auth_types = security.get("authentication_types", [])
                        if isinstance(auth_types, list):
                            sec_entry["authentication_types"] = auth_types
                        elif isinstance(auth_types, str):
                            sec_entry["authentication_types"] = [auth_types]
                        # Fast Transition (802.11r) support
                        if security.get("fast_transition"):
                            sec_entry["ft"] = True
                        if security.get("fast_transition_over_ds"):
                            sec_entry["ft_over_ds"] = True
                    securities[sec_name] = sec_entry

            # Build configuration entry
            cfg_name = f"cfg-{iface_name}"
            cfg_entry: dict[str, Any] = {
                "name": cfg_name,
                "ssid": ssid,
                "mode": iface_data.get("mode", "ap"),
                "comment": f"{ssid} - managed by topology",
            }
            if sec_name:
                cfg_entry["security"] = sec_name
            if isinstance(datapath, dict) and datapath.get("name"):
                cfg_entry["datapath"] = datapath.get("name")

            configurations.append(cfg_entry)

            # Interface -> configuration binding. Staged SSIDs are not bound
            # (their configuration exists but no AP broadcasts it yet).
            # Entries with master_interface describe virtual (slave) APs
            # (e.g. VPN-Germany on wifi1) which do NOT exist out of the box
            # on a fresh RouterOS and must be created by the deploy tooling.
            status = str(iface_data.get("status", "")).strip().lower()
            if status != "staged":
                iface_entry: dict[str, Any] = {
                    # Physical slots use the mapping key (wifi1/wifi2);
                    # virtual APs carry an explicit interface name.
                    "name": str(iface_data.get("name") or iface_name),
                    "configuration": cfg_name,
                }
                master = str(iface_data.get("master_interface") or "").strip()
                if master:
                    iface_entry["master_interface"] = master

                # Channel configuration (frequency in MHz, band, width)
                frequency = iface_data.get("frequency")
                if frequency:
                    iface_entry["frequency"] = int(frequency)
                band = iface_data.get("band")
                if band:
                    iface_entry["band"] = str(band)
                channel_width = iface_data.get("channel_width")
                if channel_width:
                    iface_entry["channel_width"] = str(channel_width)

                interfaces.append(iface_entry)

    return {
        "datapaths": list(datapaths.values()),
        "configurations": configurations,
        "securities": list(securities.values()),
        "interfaces": interfaces,
    }


class MikrotikWifiConfigCompiler(CompilerPlugin):
    """Derives MikroTik WiFi interface/VLAN membership shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        if not isinstance(devices, list):
            devices = []
        if not isinstance(enforcer_resolution, dict):
            enforcer_resolution = {}

        routers = [
            row
            for row in devices
            if isinstance(row, dict) and _is_mikrotik_enforcer(row.get("instance_id"), enforcer_resolution)
        ]

        wifi_config = _extract_wifi_config(routers)

        diagnostics.append(
            self.emit_diagnostic(
                code="I4213",
                severity="info",
                stage=stage,
                message=f"Derived {len(wifi_config['interfaces'])} MikroTik WiFi interface binding(s)",
                path="plugin:object.mikrotik.compiler.wifi_config",
            )
        )

        ctx.publish("wifi_config", wifi_config)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"wifi_config": wifi_config},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize, order 60). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)

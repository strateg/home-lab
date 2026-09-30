#!/usr/bin/env python3
"""MikroTik VLAN-entry compiler plugin (W07 migration order item 4g).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md. VLAN
row -> rendered shape (row-selection, `managed_by_ref` resolution and
per-row field extraction) used to run inside the MikroTik projection at
generate stage, as one branch of a larger shared loop over `network` rows
that also builds bridges; relocated here verbatim, with no behavior change,
so the fact exists at compile stage instead of being invisible until render
time. The same "per-row builder fed by a shared loop" shape items 4d/4e
named: this plugin replicates only the VLAN branch's row-selection and
`managed_by_ref`-resolution logic, checked against the full network-row
loop in `build_mikrotik_projection`, leaving the bridge branch of that same
loop untouched in the projection.
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


def _get_object_properties(object_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Same lookup projections.py's _get_object_properties uses."""
    if not object_ref or not isinstance(objects_map, dict):
        return {}
    obj_data = objects_map.get(object_ref)
    if not isinstance(obj_data, dict):
        return {}
    props = obj_data.get("properties")
    if isinstance(props, dict):
        return props
    return {}


def _build_vlan_entry(row: dict[str, Any], *, managed_by_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Extract VLAN configuration from network row.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _build_vlan_entry (W07 migration order item 4g).
    """
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}

    # Get properties from compiled object map (effective topology)
    props = _get_object_properties(object_ref, objects_map)

    # Instance data overrides object properties
    vlan_id = inst_data.get("vlan_id") or props.get("vlan_id")
    cidr = inst_data.get("cidr") or props.get("cidr")
    gateway = inst_data.get("gateway") or props.get("gateway")
    mtu = inst_data.get("mtu") or props.get("mtu", 1500)
    dhcp_enabled = inst_data.get("dhcp_enabled") if "dhcp_enabled" in inst_data else props.get("dhcp_enabled", False)
    dns_servers = inst_data.get("dns_servers") or props.get("dns_servers", [])

    is_native_lan = int(vlan_id or 0) == 1
    interface_name = "bridge" if is_native_lan else f"vlan{vlan_id}"

    # Extract MAC assignments for bridge host entries
    mac_assignments = inst_data.get("mac_assignments") or props.get("mac_assignments", [])
    if not isinstance(mac_assignments, list):
        mac_assignments = []

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.vlan.", "").replace(".", "_"),
        "vlan_id": vlan_id,
        "cidr": cidr,
        "gateway": gateway,
        "mtu": mtu,
        "dhcp_enabled": dhcp_enabled,
        "dhcp_range": inst_data.get("dhcp_range"),
        "dns_servers": dns_servers,
        "managed_by_ref": managed_by_ref,
        "trust_zone_ref": inst_data.get("trust_zone_ref"),
        "staged": str(row.get("status", "")).strip().lower() == "modeled"
        or "currently not configured" in str(row.get("notes", "")).strip().lower(),
        "is_native_lan": is_native_lan,
        "interface_name": interface_name,
        "interface_is_resource": not is_native_lan,
        "mac_assignments": mac_assignments,
    }


class MikrotikVlanEntriesCompiler(CompilerPlugin):
    """Derives MikroTik VLAN row -> rendered shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        network_rows = instances.get("network", []) if isinstance(instances, dict) else []
        objects_map = effective_model.get("objects", {}) if isinstance(effective_model, dict) else {}
        if not isinstance(devices, list):
            devices = []
        if not isinstance(network_rows, list):
            network_rows = []
        if not isinstance(objects_map, dict):
            objects_map = {}

        if not isinstance(enforcer_resolution, dict):
            enforcer_resolution = {}

        router_ids: set[str] = set()
        for row in devices:
            if not isinstance(row, dict):
                continue
            instance_id = row.get("instance_id")
            if _is_mikrotik_enforcer(instance_id, enforcer_resolution):
                router_ids.add(instance_id)
        default_router_id = next(iter(sorted(router_ids)), "")

        vlans: list[dict[str, Any]] = []
        for row in network_rows:
            if not isinstance(row, dict):
                continue
            object_ref = _resolved_object_ref(row)
            # routing_policy objects (e.g. obj.network.routing_policy.vpn_vlan)
            # also contain "vlan" in their ref and must not be treated as VLANs.
            if "vlan" not in object_ref or "routing_policy" in object_ref:
                continue
            inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
            managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
            if not managed_by_ref and len(router_ids) == 1:
                # VLAN instances are treated as router-owned in single-router topology.
                managed_by_ref = default_router_id
            if not managed_by_ref:
                allocations = inst_data.get("ip_allocations")
                if isinstance(allocations, list):
                    for item in allocations:
                        if not isinstance(item, dict):
                            continue
                        device_ref = str(item.get("device_ref") or "").strip()
                        if device_ref in router_ids:
                            managed_by_ref = device_ref
                            break
            if managed_by_ref in router_ids:
                vlans.append(_build_vlan_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map))

        diagnostics.append(
            self.emit_diagnostic(
                code="I4217",
                severity="info",
                stage=stage,
                message=f"Derived {len(vlans)} MikroTik VLAN entr(y/ies)",
                path="plugin:object.mikrotik.compiler.vlan_entries",
            )
        )

        ctx.publish("vlans", vlans)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"vlans": vlans},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)

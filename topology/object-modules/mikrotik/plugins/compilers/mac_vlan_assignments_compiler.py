#!/usr/bin/env python3
"""MikroTik MAC-to-VLAN assignment compiler plugin (W07 migration order item 4e).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md.
MAC-based VLAN assignment shape (bridge host entries, ADR 0117 L1/L2
separation) used to run inside the MikroTik projection at generate stage;
relocated here verbatim, with no behavior change, so the fact exists at
compile stage instead of being invisible until render time.

Unlike items 4a-4c, `_extract_mac_vlan_assignments` needs a VLAN
instance_id -> vlan_id index that the projection used to build from its own
already-filtered `vlans` list - itself a slice of the same shared per-network-
row loop item 4d's routing-policy migration also drew from. This plugin
replicates that slice's row-selection, managed_by_ref-resolution and
vlan_id-fallback logic directly (the same lesson item 4d recorded: a per-row
builder or index fed by a shared loop needs the loop's own logic replicated
for the rows it cares about, checked against the surrounding loop in full).
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


def _resolved_class_ref(row: dict[str, Any]) -> str:
    """Declared class, mirroring _resolved_object_ref's own resolution order.

    V-14 (ENFORCER-AXIS-CONFORMANCE.md): row-kind selection by declared
    class, not by matching a substring against the object_ref name.
    """
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_class", "materializes_class"):
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


def _build_vlan_id_index(
    network_rows: list[dict[str, Any]],
    *,
    router_ids: set[str],
    default_router_id: str,
    objects_map: dict[str, Any],
) -> tuple[dict[str, int], list[str]]:
    """Replicates the VLAN branch of build_mikrotik_projection's network-row loop.

    Only the instance_id -> vlan_id mapping is needed here, not the full
    `_build_vlan_entry` shape (still generate-stage, W07 migration order item
    4g) - but the row-selection and managed_by_ref-resolution must match it
    exactly, or a VLAN this plugin skips (or wrongly includes) silently drops
    (or fabricates) MAC assignments for that VLAN.

    Returns the index plus the sorted instance ids of VLAN rows whose
    managed_by_ref could not be resolved at all (V-10: an ambiguous target
    among 0 or several candidate routers, not merely "not this compiler's
    router") - the caller emits a diagnostic for each rather than the row
    being silently absent from the index.
    """
    vlan_id_index: dict[str, int] = {}
    ambiguous_instance_ids: list[str] = []
    for row in network_rows:
        if not isinstance(row, dict):
            continue
        if _resolved_class_ref(row) != "class.network.vlan":
            continue
        object_ref = _resolved_object_ref(row)
        inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
        managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
        if not managed_by_ref and len(router_ids) == 1:
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
        if not managed_by_ref:
            instance_id = str(row.get("instance_id", "")).strip()
            if instance_id:
                ambiguous_instance_ids.append(instance_id)
            continue
        if managed_by_ref not in router_ids:
            continue
        props = _get_object_properties(object_ref, objects_map)
        vlan_id = inst_data.get("vlan_id") or props.get("vlan_id")
        instance_id = str(row.get("instance_id", "")).strip()
        if instance_id and vlan_id:
            vlan_id_index[instance_id] = int(vlan_id)
    return vlan_id_index, sorted(ambiguous_instance_ids)


def _extract_mac_vlan_assignments(
    all_groups: dict[str, list[dict[str, Any]]],
    vlan_id_index: dict[str, int],
) -> list[dict[str, Any]]:
    """Extract MAC-based VLAN assignments from device instances.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _extract_mac_vlan_assignments (W07 migration order
    item 4e).

    Finds devices with both vlan_ref and secrets_ref, then builds
    assignment entries for bridge host generation.

    Supports ADR 0117 L1/L2 separation:
    - Direct: device has vlan_ref and secrets_ref
    - Indirect: device has provides_ref -> L2 iot_interface has vlan_ref/secrets_ref

    Args:
        all_groups: All instance groups from compiled JSON.
        vlan_id_index: Mapping of vlan instance_id to vlan_id.

    Returns:
        List of assignment entries:
        [
            {
                "device_id": "inst.device.tv-sony-bravia",
                "device_name": "Sony Bravia AJ9",
                "secrets_ref": "secrets.instances.tv-sony-bravia",
                "secrets_path": "instances/tv-sony-bravia.yaml",
                "vlan_ref": "inst.vlan.vpn_germany",
                "vlan_id": 55,
                "comment": "Sony Bravia AJ9 -> VLAN 55",
            }
        ]
    """
    assignments: list[dict[str, Any]] = []

    # Build L2 interface index: interface_id -> {vlan_ref, secrets_ref, device_ref}
    # ADR 0117: IoT interfaces are in network group with iot_interface in instance_id
    l2_interface_index: dict[str, dict[str, str]] = {}
    network_rows = all_groups.get("network", [])
    for net_row in network_rows:
        net_instance_id = str(net_row.get("instance_id", "")).strip()
        if "iot_interface" not in net_instance_id:
            continue
        net_inst_data = net_row.get("instance_data", {})
        if not isinstance(net_inst_data, dict):
            continue
        l2_interface_index[net_instance_id] = {
            "vlan_ref": str(net_inst_data.get("vlan_ref", "")).strip(),
            "secrets_ref": str(net_inst_data.get("secrets_ref", "")).strip(),
            "device_ref": str(net_inst_data.get("device_ref", "")).strip(),
        }

    # Check devices group for device instances with vlan_ref
    devices = all_groups.get("devices", [])

    for row in devices:
        instance_id = str(row.get("instance_id", "")).strip()
        if not instance_id.startswith("inst.device."):
            continue

        inst_data = row.get("instance_data", {})
        if not isinstance(inst_data, dict):
            continue

        # Try direct vlan_ref/secrets_ref on device first
        vlan_ref = str(inst_data.get("vlan_ref", "")).strip()
        secrets_ref = str(inst_data.get("secrets_ref", "")).strip()

        # ADR 0117: If not found, check provides_ref for L2 interface
        if not vlan_ref or not secrets_ref:
            provides_ref = str(inst_data.get("provides_ref", "")).strip()
            if provides_ref and provides_ref in l2_interface_index:
                l2_data = l2_interface_index[provides_ref]
                if not vlan_ref:
                    vlan_ref = l2_data.get("vlan_ref", "")
                if not secrets_ref:
                    secrets_ref = l2_data.get("secrets_ref", "")

        if not vlan_ref or not secrets_ref:
            continue

        vlan_id = vlan_id_index.get(vlan_ref)
        if not vlan_id:
            continue

        # Convert secrets_ref to path: secrets.instances.foo -> instances/foo.yaml
        secrets_path = ""
        if secrets_ref.startswith("secrets."):
            secrets_path = secrets_ref[8:].replace(".", "/") + ".yaml"

        device_name = str(inst_data.get("device_name", "")).strip()
        if not device_name:
            device_name = instance_id.replace("inst.device.", "")

        assignments.append(
            {
                "device_id": instance_id,
                "device_name": device_name,
                "secrets_ref": secrets_ref,
                "secrets_path": secrets_path,
                "vlan_ref": vlan_ref,
                "vlan_id": vlan_id,
                "comment": f"{device_name} -> VLAN {vlan_id}",
            }
        )

    return sorted(assignments, key=lambda x: (x.get("vlan_id", 0), x.get("device_id", "")))


class MikrotikMacVlanAssignmentsCompiler(CompilerPlugin):
    """Derives MikroTik MAC-to-VLAN assignment shape at compile stage."""

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

        vlan_id_index, ambiguous_vlan_ids = _build_vlan_id_index(
            network_rows,
            router_ids=router_ids,
            default_router_id=default_router_id,
            objects_map=objects_map,
        )
        for ambiguous_instance_id in ambiguous_vlan_ids:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7027",
                    severity="error",
                    stage=stage,
                    message=(
                        f"'{ambiguous_instance_id}' has no managed_by_ref and no matching "
                        f"ip_allocations entry, with {len(router_ids)} candidate router(s) "
                        "present; refusing an ambiguous target rather than silently "
                        "dropping the row's MAC-to-VLAN assignments (ADR 0119 D1: "
                        "multiplicity a channel cannot represent must be refused with a "
                        "diagnostic)."
                    ),
                    path=f"instance:network:{ambiguous_instance_id}.managed_by_ref",
                )
            )

        mac_vlan_assignments = _extract_mac_vlan_assignments(
            {"network": network_rows, "devices": devices},
            vlan_id_index,
        )

        diagnostics.append(
            self.emit_diagnostic(
                code="I4215",
                severity="info",
                stage=stage,
                message=f"Derived {len(mac_vlan_assignments)} MikroTik MAC-to-VLAN assignment(s)",
                path="plugin:object.mikrotik.compiler.mac_vlan_assignments",
            )
        )

        ctx.publish("mac_vlan_assignments", mac_vlan_assignments)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"mac_vlan_assignments": mac_vlan_assignments},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize, order 60). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)

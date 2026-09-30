#!/usr/bin/env python3
"""MikroTik firewall-entry compiler plugin (W07 migration order item 4i).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md.
Firewall-policy row -> rendered shape (row-selection, `managed_by_ref`
resolution and per-row field extraction) used to run inside the MikroTik
projection at generate stage, as its own dedicated loop over the `firewall`
instance group - not a shared loop with any other row kind, unlike items
4d/4e/4g/4h; relocated here verbatim, with no behavior change, so the fact
exists at compile stage instead of being invisible until render time.

The zone/CIDR resolution `build_mikrotik_projection` still does on this
channel's output (trust-zone-to-CIDR matching, `src_zone_ref`/`dst_zone_ref`
normalization) is not part of `_build_firewall_entry` and stays in the
projection - it depends on `vlans` (itself already a compile-stage channel,
item 4g) in the same way policy-based routing's `src_vlan_ref` resolution
stays local to the routing_policies plugin's own scope.
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


def _build_firewall_entry(row: dict[str, Any], *, managed_by_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Extract firewall policy from network row.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _build_firewall_entry (W07 migration order item 4i).
    """
    object_ref = _resolved_object_ref(row)
    props = _get_object_properties(object_ref, objects_map)
    inst_data = row.get("instance_data", {}) or {}

    return {
        "instance_id": row.get("instance_id", ""),
        "name": row.get("instance_id", "").replace("inst.fw.", "").replace(".", "_"),
        "chain": str(inst_data.get("chain") or "forward"),
        "managed_by_ref": managed_by_ref,
        "priority": int(props.get("priority", 1000)),
        "default_action": str(props.get("default_action", "drop")),
        "rules": props.get("rules", []) if isinstance(props.get("rules"), list) else [],
        "comment": str(row.get("notes", "")),
        "staged": str(row.get("status", "")).strip().lower() == "modeled"
        or "currently not configured" in str(row.get("notes", "")).strip().lower(),
    }


class MikrotikFirewallEntriesCompiler(CompilerPlugin):
    """Derives MikroTik firewall-policy row -> rendered shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        firewall_rows = instances.get("firewall", []) if isinstance(instances, dict) else []
        objects_map = effective_model.get("objects", {}) if isinstance(effective_model, dict) else {}
        if not isinstance(devices, list):
            devices = []
        if not isinstance(firewall_rows, list):
            firewall_rows = []
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

        firewall_policies: list[dict[str, Any]] = []
        for row in firewall_rows:
            if not isinstance(row, dict):
                continue
            object_ref = _resolved_object_ref(row)
            if "firewall_policy" not in object_ref:
                continue
            inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
            managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
            if not managed_by_ref and len(router_ids) == 1:
                managed_by_ref = default_router_id
            if managed_by_ref in router_ids:
                firewall_policies.append(
                    _build_firewall_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map)
                )

        diagnostics.append(
            self.emit_diagnostic(
                code="I4219",
                severity="info",
                stage=stage,
                message=f"Derived {len(firewall_policies)} MikroTik firewall-policy entr(y/ies)",
                path="plugin:object.mikrotik.compiler.firewall_entries",
            )
        )

        ctx.publish("firewall_policies", firewall_policies)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"firewall_policies": firewall_policies},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)

#!/usr/bin/env python3
"""MikroTik bridge-entry compiler plugin (W07 migration order item 4h).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md. Bridge
row -> rendered shape (row-selection, `managed_by_ref` resolution and
per-row field extraction) used to run inside the MikroTik projection at
generate stage, as one branch of a larger shared loop over `network` rows
that also built VLANs (item 4g, already migrated); relocated here
verbatim, with no behavior change, so the fact exists at compile stage
instead of being invisible until render time. Same "per-row builder fed by
a shared loop" shape items 4d/4e/4g named: this plugin replicates only the
bridge branch's row-selection and `managed_by_ref`-resolution logic,
checked against the full network-row loop in `build_mikrotik_projection`.
"""

from __future__ import annotations

from ipaddress import ip_interface
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


def _build_bridge_entry(row: dict[str, Any], *, managed_by_ref: str, objects_map: dict[str, Any]) -> dict[str, Any]:
    """Extract bridge configuration from network row.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _build_bridge_entry (W07 migration order item 4h).
    """
    object_ref = _resolved_object_ref(row)
    inst_data = row.get("instance_data", {}) or {}
    props = _get_object_properties(object_ref, objects_map)
    ip_addr = str(inst_data.get("ip") or "").strip()
    cidr = str(inst_data.get("cidr") or "").strip()
    if not cidr and ip_addr:
        try:
            cidr = str(ip_interface(ip_addr).network)
        except ValueError:
            cidr = ""
    name = str(props.get("name") or row.get("instance_id", "").replace("inst.bridge.", "")).strip() or "bridge"
    return {
        "instance_id": row.get("instance_id", ""),
        "name": name.replace(".", "_"),
        "bridge_name": name,
        "ip": ip_addr,
        "cidr": cidr,
        "managed_by_ref": managed_by_ref,
        "staged": str(row.get("status", "")).strip().lower() == "modeled"
        or "currently not configured" in str(row.get("notes", "")).strip().lower(),
    }


class MikrotikBridgeEntriesCompiler(CompilerPlugin):
    """Derives MikroTik bridge row -> rendered shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
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

        router_ids: set[str] = set()
        for row in devices:
            if not isinstance(row, dict):
                continue
            if not _resolved_object_ref(row).startswith("obj.mikrotik."):
                continue
            instance_id = row.get("instance_id")
            if isinstance(instance_id, str) and instance_id:
                router_ids.add(instance_id)

        bridges: list[dict[str, Any]] = []
        for row in network_rows:
            if not isinstance(row, dict):
                continue
            object_ref = _resolved_object_ref(row)
            if "bridge" not in object_ref:
                continue
            inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
            managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
            host_ref = str(inst_data.get("host_ref") or "").strip()
            if not managed_by_ref and host_ref in router_ids:
                managed_by_ref = host_ref
            if managed_by_ref in router_ids:
                bridges.append(_build_bridge_entry(row, managed_by_ref=managed_by_ref, objects_map=objects_map))

        diagnostics.append(
            self.emit_diagnostic(
                code="I4218",
                severity="info",
                stage=stage,
                message=f"Derived {len(bridges)} MikroTik bridge entr(y/ies)",
                path="plugin:object.mikrotik.compiler.bridge_entries",
            )
        )

        ctx.publish("bridges", bridges)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"bridges": bridges},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)

#!/usr/bin/env python3
"""MikroTik capability-flag compiler plugin (W07 migration order item 1).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md: "It
cannot occur only in a generator after the relevant validator ran." Boolean
capability-flag derivation for conditional Terraform generation
(has_wireguard, has_containers, ...) used to run inside the MikroTik
projection at generate stage - relocated here verbatim, with no behavior
change, so the fact exists at compile stage where a validator could check it,
instead of being invisible until render time.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Extract capability IDs from an effective-model instance row.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _extract_capabilities: same three sources (instance,
    object, root-level legacy), same field names, same row shape
    (compiled_json's "instances"."devices" entries).
    """
    caps: set[str] = set()

    instance_data = row.get("instance", {}) or {}
    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = instance_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    obj_data = row.get("object", {}) or {}
    for field_name in ("enabled_capabilities", "derived_capabilities", "vendor_capabilities"):
        raw_caps = obj_data.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    for field_name in ("capabilities", "derived_capabilities", "enabled_capabilities"):
        raw_caps = row.get(field_name)
        if isinstance(raw_caps, list):
            for cap in raw_caps:
                if isinstance(cap, str) and cap:
                    caps.add(cap)

    return caps


def _derive_capability_flags(routers: list[dict[str, Any]]) -> dict[str, bool]:
    """Derive boolean capability flags for conditional Terraform generation.

    Moved verbatim from projections.py's _derive_mikrotik_capability_flags.
    ADR0078: capabilities must come from object definitions, not hardcoded
    model checks.
    """
    all_caps: set[str] = set()
    for router in routers:
        all_caps.update(_extract_capabilities(router))

    return {
        "has_wireguard": any(cap.startswith("cap.net.overlay.vpn.wireguard") for cap in all_caps),
        "has_openvpn": any(cap.startswith("cap.net.overlay.vpn.openvpn") for cap in all_caps),
        "has_ipsec": "cap.net.overlay.vpn.ipsec" in all_caps,
        "has_containers": "cap.net.platform.containers" in all_caps,
        "has_qos_basic": "cap.net.l3.qos.basic" in all_caps,
        "has_qos_advanced": "cap.net.l3.qos.advanced" in all_caps,
        "has_lte": "cap.net.interface.lte" in all_caps,
        "has_wifi": "cap.net.interface.wifi" in all_caps,
        "has_vlan": "cap.net.l2.segmentation.vlan.8021q" in all_caps,
        "has_multi_wan": "cap.net.l3.uplink.multi_uplink" in all_caps,
        "has_failover": "cap.net.l3.uplink.failover" in all_caps,
    }


def _resolved_object_ref(row: dict[str, Any]) -> str:
    """Same resolution projection_core._resolved_object_ref uses."""
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_object", "materializes_object"):
            value = instance_block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


class MikrotikCapabilityFlagsCompiler(CompilerPlugin):
    """Derives MikroTik conditional-generation capability flags at compile stage."""

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

        capability_flags = _derive_capability_flags(routers)

        diagnostics.append(
            self.emit_diagnostic(
                code="I4210",
                severity="info",
                stage=stage,
                message=f"Derived MikroTik capability flags from {len(routers)} router instance(s)",
                path="plugin:object.mikrotik.compiler.capability_flags",
            )
        )

        ctx.publish("capability_flags", capability_flags)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"capability_flags": capability_flags},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # This plugin is registered at phase: finalize (it must run after
        # base.compiler.effective_model, also finalize, order 60). The
        # kernel dispatches phase-specific hooks, not execute() directly;
        # effective_model_compiler.py uses the same one-line delegation.
        return self.execute(ctx, stage)

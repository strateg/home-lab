#!/usr/bin/env python3
"""MikroTik routing-policy compiler plugin (W07 migration order item 4d).

Backend specialization must happen in compile stage, before any validator
runs, per adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md.
Policy-based routing shape (mangle/NAT/firewall rules with `*_vlan_ref`
resolved against the compiler's CIDR map) used to run inside the MikroTik
projection at generate stage; relocated here verbatim, with no behavior
change, so the fact exists at compile stage instead of being invisible
until render time.
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


def _build_routing_policy_entry(
    row: dict[str, Any],
    *,
    managed_by_ref: str,
    vlan_cidr_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Extract policy-based routing configuration from network row.

    Moved verbatim from topology/object-modules/mikrotik/plugins/
    projections.py's _build_routing_policy_entry (W07 migration order
    item 4d).

    Args:
        row: Network instance row from compiled JSON.
        managed_by_ref: Device instance ID managing this policy.
        vlan_cidr_index: VLAN instance_id -> CIDR mapping for resolving refs.

    Supports VLAN reference resolution (ADR-0111 extension):
        - source_match.vlan_ref -> source_subnet (if value not provided)
        - firewall_rules[].src_vlan_ref -> src_address
        - firewall_rules[].dst_vlan_ref -> dst_address
        - mangle_rules[].src_vlan_ref -> src_address
        - mangle_rules[].dst_vlan_ref -> dst_address
        - nat_rules[].src_vlan_ref -> src_address
    """
    if vlan_cidr_index is None:
        vlan_cidr_index = {}

    inst_data = row.get("instance_data", {}) or {}
    mikrotik_config = inst_data.get("mikrotik_config", {}) or {}
    if not isinstance(mikrotik_config, dict):
        mikrotik_config = {}
    source_match = inst_data.get("source_match", {}) or {}
    if not isinstance(source_match, dict):
        source_match = {}
    target_gateway = inst_data.get("target_gateway", {}) or {}
    if not isinstance(target_gateway, dict):
        target_gateway = {}

    instance_id = str(row.get("instance_id", "")).strip()
    name = instance_id.replace("inst.routing_policy.", "").replace(".", "_").replace("-", "_")

    # Resolve source_subnet from vlan_ref if value not provided
    source_subnet = str(source_match.get("value", "")).strip()
    if not source_subnet:
        source_vlan_ref = str(source_match.get("vlan_ref", "")).strip()
        if source_vlan_ref:
            source_subnet = vlan_cidr_index.get(source_vlan_ref, "")

    # Helper to resolve vlan refs in rule dicts
    def resolve_rule_refs(rule: dict[str, Any]) -> dict[str, Any]:
        """Resolve vlan_ref fields to actual CIDRs in a rule dict."""
        resolved = dict(rule)
        # src_vlan_ref -> src_address
        src_ref = str(rule.get("src_vlan_ref", "")).strip()
        if src_ref and not rule.get("src_address"):
            cidr = vlan_cidr_index.get(src_ref)
            if cidr:
                resolved["src_address"] = cidr
        # dst_vlan_ref -> dst_address
        dst_ref = str(rule.get("dst_vlan_ref", "")).strip()
        if dst_ref and not rule.get("dst_address"):
            cidr = vlan_cidr_index.get(dst_ref)
            if cidr:
                resolved["dst_address"] = cidr
        return resolved

    mangle_rules = mikrotik_config.get("mangle_rules", [])
    if not isinstance(mangle_rules, list):
        mangle_rules = []
    routing_table = mikrotik_config.get("routing_table", {})
    if not isinstance(routing_table, dict):
        routing_table = {}
    routes = mikrotik_config.get("routes", [])
    if not isinstance(routes, list):
        routes = []
    nat_rules = mikrotik_config.get("nat_rules", [])
    if not isinstance(nat_rules, list):
        nat_rules = []
    mss_clamp = mikrotik_config.get("mss_clamp", {})
    if not isinstance(mss_clamp, dict):
        mss_clamp = {}
    fasttrack = mikrotik_config.get("fasttrack", {})
    if not isinstance(fasttrack, dict):
        fasttrack = {}
    notrack = mikrotik_config.get("notrack", [])
    if not isinstance(notrack, list):
        notrack = []
    firewall_rules = mikrotik_config.get("firewall_rules", [])
    if not isinstance(firewall_rules, list):
        firewall_rules = []

    # Resolve vlan refs in all rule types
    resolved_mangle = [resolve_rule_refs(r) for r in mangle_rules if isinstance(r, dict)]
    resolved_nat = [resolve_rule_refs(r) for r in nat_rules if isinstance(r, dict)]
    resolved_firewall = [resolve_rule_refs(r) for r in firewall_rules if isinstance(r, dict)]

    return {
        "instance_id": instance_id,
        "name": name,
        "policy_name": str(inst_data.get("policy_name", "")).strip() or name,
        "enabled": bool(inst_data.get("enabled", True)),
        "source_subnet": source_subnet,
        "tunnel_interface": str(target_gateway.get("value", "")).strip(),
        "mangle_rules": resolved_mangle,
        "routing_table": routing_table,
        "routes": [route for route in routes if isinstance(route, dict)],
        "nat_rules": resolved_nat,
        "mss_clamp": mss_clamp if mss_clamp.get("new_mss") else None,
        "fasttrack": fasttrack if fasttrack.get("enabled") else None,
        "notrack": [rule for rule in notrack if isinstance(rule, dict)],
        "firewall_rules": resolved_firewall,
        "managed_by_ref": managed_by_ref,
        "staged": str(row.get("status", "")).strip().lower() == "modeled"
        or "currently not configured" in str(row.get("notes", "")).strip().lower(),
    }


class MikrotikRoutingPoliciesCompiler(CompilerPlugin):
    """Derives MikroTik policy-based routing shape at compile stage."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        devices = instances.get("devices", []) if isinstance(instances, dict) else []
        network_rows = instances.get("network", []) if isinstance(instances, dict) else []
        if not isinstance(devices, list):
            devices = []
        if not isinstance(network_rows, list):
            network_rows = []

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

        try:
            vlan_cidr_index = ctx.subscribe("base.compiler.security_matrix", "vlan_cidr_map")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9203",
                    severity="error",
                    stage=stage,
                    message=f"failed to obtain vlan_cidr_map: {exc}",
                    path="plugin:object.mikrotik.compiler.routing_policies",
                )
            )
            return self.make_result(diagnostics)
        if not isinstance(vlan_cidr_index, dict):
            vlan_cidr_index = {}

        routing_policies: list[dict[str, Any]] = []
        for row in network_rows:
            if not isinstance(row, dict):
                continue
            if _resolved_class_ref(row) != "class.network.routing_policy":
                continue
            inst_data = row.get("instance_data", {}) if isinstance(row.get("instance_data"), dict) else {}
            managed_by_ref = str(inst_data.get("managed_by_ref") or "").strip()
            if not managed_by_ref and len(router_ids) == 1:
                managed_by_ref = default_router_id
            if managed_by_ref in router_ids:
                routing_policies.append(
                    _build_routing_policy_entry(row, managed_by_ref=managed_by_ref, vlan_cidr_index=vlan_cidr_index)
                )

        diagnostics.append(
            self.emit_diagnostic(
                code="I4214",
                severity="info",
                stage=stage,
                message=f"Derived {len(routing_policies)} MikroTik routing polic(y/ies)",
                path="plugin:object.mikrotik.compiler.routing_policies",
            )
        )

        ctx.publish("routing_policies", routing_policies)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"routing_policies": routing_policies},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize (must run after base.compiler.
        # effective_model, also finalize, order 60). The kernel dispatches
        # phase-specific hooks, not execute() directly.
        return self.execute(ctx, stage)

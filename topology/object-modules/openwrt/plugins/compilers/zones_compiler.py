#!/usr/bin/env python3
"""OpenWrt zone compiler: lowers the ADR 0110 matrix into firewall4 zone intent.

Backend specialization belongs in the compile stage, before any validator runs
(adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md). This plugin derives
the facts an OpenWrt renderer needs and publishes them where a validator can
still check them, rather than discovering them at render time.

Two properties of firewall4 shape everything here, both read from
package/network/config/firewall templates rather than assumed:

* Zone chains are **terminal** - `forward_<zone>` ends in a jump to the zone's
  own policy - and the nftables base chains carry `policy drop`. Default-deny is
  therefore structural, in two independent layers. A terminal "drop-all" rule of
  the kind ADR 0110 section 4.4 mandates for RouterOS must NOT be ported: it
  would be appended inside a zone chain, ahead of the forwardings it is meant to
  follow.
* There is **no ordering control** anywhere in the uapi surface. Consequently a
  matrix cell that denies traffic is lowered as the *absence* of a
  `firewall_forwarding` object, not as a deny rule. Denied pairs are still
  published, so the fact stays auditable and `E9906` has something to check, but
  they are explicitly not emissions.

Zone input policy is not in the ADR 0110 model, which covers inter-zone forward
only. Stock OpenWrt ships `zone lan` with `input ACCEPT`, which exposes every
router service to that zone, so this compiler defaults every zone to `REJECT`
and derives the narrow set of router services each client segment actually needs
(DHCP, DNS). `E9907` is the check that no zone reaches a renderer with an
implicit input policy.
"""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage

# Selection is by declared capability, never by object_ref name convention
# (ENFORCER-AXIS-CONFORMANCE.md V-14).
_OPENWRT_OS_CAP = "cap.os.openwrt"

# Matrix cell actions. The compiler treats anything not explicitly permissive as
# denied: an unknown action must not become a grant.
_PERMIT_ACTIONS = frozenset({"allow", "accept"})


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    """Collect capability ids from an effective-model instance row.

    Same three sources the other object modules read: instance block, object
    block, and root-level legacy fields.
    """
    caps: set[str] = set()
    blocks = (row.get("instance") or {}, row.get("object") or {}, row)
    fields = ("capabilities", "derived_capabilities", "enabled_capabilities", "vendor_capabilities")
    for block in blocks:
        if not isinstance(block, dict):
            continue
        for field in fields:
            values = block.get(field)
            if isinstance(values, list):
                caps.update(value for value in values if isinstance(value, str) and value)
    return caps


def _is_openwrt_network_enforcer(
    instance_id: Any,
    row: dict[str, Any],
    enforcer_resolution: dict[str, Any],
) -> bool:
    """Is this instance an OpenWrt device resolved as a network enforcer?

    Deliberately *not* gated on the adapter capability the way the MikroTik
    compilers gate on `cap.firewall.security_matrix.routeros`. The
    `cap.os.openwrt -> cap.firewall.security_matrix.openwrt` mapping is not
    registered in `_ENFORCER_ADAPTER_BY_TYPE` yet, by design: an adapter
    identifier that resolves with no generator behind it would be a false claim
    of coverage under ADR 0119 D1.1, which is why `W7016` is allowlisted instead.

    Until that mapping lands, the honest selector is the pair the mapping will
    connect: the OS family that identifies the platform, and the enforcer type
    the capability engine already resolved. Both are declared capabilities, so
    this stays capability-driven rather than name-driven.
    """
    if not isinstance(instance_id, str) or not instance_id:
        return False
    if _OPENWRT_OS_CAP not in _extract_capabilities(row):
        return False
    resolution = enforcer_resolution.get(instance_id) if isinstance(enforcer_resolution, dict) else None
    return isinstance(resolution, dict) and resolution.get("type") == "network"


def _local_segments(network_rows: list[Any], enforcer_id: str) -> dict[str, list[dict[str, Any]]]:
    """Address domains this enforcer owns, grouped by trust zone.

    A zone's membership on *this* device is the set of segments whose
    `managed_by_ref` names it. Zones that appear in the matrix without a local
    segment are destinations reached through a tunnel, not local zones, and are
    reported rather than rendered as empty.
    """
    by_zone: dict[str, list[dict[str, Any]]] = {}
    for row in network_rows:
        if not isinstance(row, dict):
            continue
        # Segment fields live in `instance_data`; the sibling `instance` block
        # carries lineage and capability metadata, not the authored values.
        data = row.get("instance_data")
        if not isinstance(data, dict):
            continue

        if data.get("managed_by_ref") != enforcer_id:
            continue
        zone_ref = data.get("trust_zone_ref")
        cidr = data.get("cidr")
        if not isinstance(zone_ref, str) or not isinstance(cidr, str):
            continue

        # The uci interface name for this segment. uapi_firewall_zone's
        # `network` list names config interface sections, not topology
        # instances, so an instance id there would reference a section that
        # does not exist. Authored explicitly when it must differ; otherwise
        # derived from the instance id's tail, which keeps the name stable as
        # long as the instance is not renamed - and a rename is a section
        # rename, which uapi treats as delete plus create.
        declared_name = data.get("interface")
        interface_name = (
            declared_name
            if isinstance(declared_name, str) and declared_name
            else str(row.get("instance_id", "")).rsplit(".", 1)[-1]
        )

        by_zone.setdefault(zone_ref, []).append(
            {
                "instance_id": row.get("instance_id"),
                "interface": interface_name,
                "cidr": cidr,
                "gateway": data.get("gateway"),
                "mtu": data.get("mtu"),
                "vlan_id": data.get("vlan_id"),
                "dhcp_range": data.get("dhcp_range"),
                "dns_servers": data.get("dns_servers"),
            }
        )
    return by_zone


def _local_interfaces(row: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Non-segment interfaces this device places in a zone, grouped by zone.

    Zone membership is not only address domains. The venue uplink and every
    WireGuard interface are `config interface` sections with no VLAN and no
    client prefix, and `uapi_firewall_zone` has no `device` or `subnet` field -
    only `network` - so each must be a named interface inside some zone or it
    belongs to none and is silently unreachable.
    """
    data = row.get("instance_data")
    if not isinstance(data, dict):
        return {}
    intent = data.get("runtime_intent")
    if not isinstance(intent, dict):
        return {}

    by_zone: dict[str, list[dict[str, Any]]] = {}

    def add(zone_ref: Any, entry: dict[str, Any]) -> None:
        if isinstance(zone_ref, str) and zone_ref:
            by_zone.setdefault(zone_ref, []).append(entry)

    uplink = intent.get("uplink")
    if isinstance(uplink, dict):
        for role in ("primary", "wired"):
            spec = uplink.get(role)
            if not isinstance(spec, dict) or spec.get("enabled") is False:
                continue
            name = spec.get("interface")
            if not isinstance(name, str) or not name:
                continue
            add(
                spec.get("trust_zone_ref"),
                {
                    "name": name,
                    "kind": "uplink",
                    "role": role,
                    "proto": spec.get("proto"),
                    "immutable": False,
                },
            )

    # The management path is neither a client segment nor an uplink: it is the
    # interface the uapi request itself arrives on. A write that reconfigures it
    # never returns a response, so Terraform records nothing (E9904).
    management = intent.get("management")
    if isinstance(management, dict):
        name = management.get("interface")
        if isinstance(name, str) and name:
            add(
                management.get("trust_zone_ref"),
                {
                    "name": name,
                    "kind": "management",
                    "device": management.get("device"),
                    "proto": management.get("proto"),
                    "address": management.get("address"),
                    "immutable": bool(management.get("immutable", False)),
                    "endpoint_arrives_here": bool(management.get("endpoint_arrives_here", False)),
                    "input_services": management.get("input_services") or [],
                },
            )

    wireguard = intent.get("wireguard")
    if isinstance(wireguard, dict):
        for entry in wireguard.get("interfaces") or []:
            if not isinstance(entry, dict) or entry.get("enabled") is False:
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue
            add(
                entry.get("trust_zone_ref"),
                {
                    "name": name,
                    "kind": "wireguard",
                    "mtu": entry.get("mtu"),
                    "advertises": entry.get("advertises") or [],
                    "exit_mode": entry.get("exit_mode"),
                    "immutable": False,
                },
            )

    return by_zone


def _input_services(
    segments: list[dict[str, Any]],
    interfaces: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Router services a zone genuinely needs on the input path.

    Derived rather than assumed, because the alternative to a narrow list is
    stock OpenWrt's `input ACCEPT`, which publishes SSH and the uapi endpoint to
    every client in the zone.

    Segments contribute what their own configuration implies: DHCP when the
    segment hands out leases, DNS only when its declared resolver is the router
    itself rather than a public one reached through a tunnel.

    Interfaces may also declare services explicitly, which is how the
    management path keeps SSH and uapi reachable. Nothing else is inferred for
    them: an interface that declares none gets none, so the first apply cannot
    quietly publish a service nobody asked for.
    """
    services: set[str] = set()
    for segment in segments:
        if segment.get("dhcp_range"):
            services.add("dhcp")
        gateway = segment.get("gateway")
        dns_servers = segment.get("dns_servers")
        if isinstance(dns_servers, list) and gateway in dns_servers:
            services.add("dns")
    for interface in interfaces or []:
        declared = interface.get("input_services")
        if isinstance(declared, list):
            services.update(item for item in declared if isinstance(item, str) and item)
    return sorted(services)


def _lower_matrix(
    matrix: dict[str, Any],
    local_zone_refs: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Split matrix cells into forwardings to emit and denials to record.

    Only pairs whose source is a local zone produce anything: this enforcer
    filters traffic entering from its own segments, not traffic between two
    remote zones it merely knows about.
    """
    forwardings: list[dict[str, str]] = []
    denied: list[dict[str, Any]] = []

    for from_zone in sorted(matrix):
        if from_zone not in local_zone_refs:
            continue
        to_zones = matrix.get(from_zone) or {}
        if not isinstance(to_zones, dict):
            continue
        for to_zone in sorted(to_zones):
            cell = to_zones.get(to_zone) or {}
            if not isinstance(cell, dict) or from_zone == to_zone:
                continue
            action = str(cell.get("action", "")).lower()
            if action in _PERMIT_ACTIONS:
                forwardings.append({"src": from_zone, "dest": to_zone})
            else:
                denied.append(
                    {
                        "src": from_zone,
                        "dest": to_zone,
                        "rule": cell.get("rule"),
                        "reason": cell.get("reason"),
                        "log": bool(cell.get("log", False)),
                    }
                )
    return forwardings, denied


class OpenwrtZonesCompiler(CompilerPlugin):
    """Lowers composed security matrices into OpenWrt zone/forwarding intent."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        effective_model = ctx.subscribe("base.compiler.effective_model", "effective_model_candidate")
        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
        composed = ctx.subscribe("base.compiler.security_matrix", "composed_matrices_by_enforcer")

        if not isinstance(enforcer_resolution, dict):
            enforcer_resolution = {}
        if not isinstance(composed, dict):
            composed = {}
        instances = effective_model.get("instances", {}) if isinstance(effective_model, dict) else {}
        device_rows = instances.get("devices", []) if isinstance(instances, dict) else []
        network_rows = instances.get("network", []) if isinstance(instances, dict) else []
        if not isinstance(device_rows, list):
            device_rows = []
        if not isinstance(network_rows, list):
            network_rows = []

        rows_by_id = {
            row.get("instance_id"): row for row in device_rows if isinstance(row, dict) and row.get("instance_id")
        }

        openwrt_zones: dict[str, Any] = {}

        for enforcer_id in sorted(composed):
            row = rows_by_id.get(enforcer_id)
            if not isinstance(row, dict):
                continue
            if not _is_openwrt_network_enforcer(enforcer_id, row, enforcer_resolution):
                continue

            plan = composed.get(enforcer_id) or {}
            zone_data = plan.get("zones") or {}
            matrix = plan.get("matrix") or {}
            if not isinstance(zone_data, dict) or not isinstance(matrix, dict):
                continue

            segments_by_zone = _local_segments(network_rows, enforcer_id)
            interfaces_by_zone = _local_interfaces(row)
            # A zone is local if this device puts anything in it - an address
            # domain or a bare interface. The uplink zone has no client prefix
            # at all, so membership by segment alone would report it as remote.
            local_zone_refs = set(segments_by_zone) | set(interfaces_by_zone)

            zones: dict[str, Any] = {}
            for zone_ref in sorted(zone_data):
                segments = segments_by_zone.get(zone_ref, [])
                interfaces = interfaces_by_zone.get(zone_ref, [])
                zones[zone_ref] = {
                    "local": bool(segments) or bool(interfaces),
                    "segments": segments,
                    "interfaces": interfaces,
                    # firewall4 zone chains are terminal and the base chains
                    # carry policy drop, so a zone's own policy is the whole
                    # default-deny story. Permits are the explicit forwardings
                    # below; nothing here needs a trailing drop rule.
                    "input": "REJECT",
                    "forward": "REJECT",
                    "output": "ACCEPT",
                    "input_services": _input_services(segments, interfaces),
                }

            forwardings, denied = _lower_matrix(matrix, local_zone_refs)

            openwrt_zones[enforcer_id] = {
                "scope_ids": plan.get("scope_ids") or [],
                "zones": zones,
                "forwardings": forwardings,
                # Recorded, deliberately not emitted: on firewall4 a denial is
                # the absence of a forwarding object. Published so the fact is
                # auditable and E9906 can assert no tunnel-only zone acquired a
                # forwarding to an uplink zone.
                "denied_pairs": denied,
            }

            remote = sorted(ref for ref, data in zones.items() if not data["local"])
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9901",
                    severity="info",
                    stage=stage,
                    message=(
                        f"Lowered {len(zones)} zone(s) for OpenWrt enforcer '{enforcer_id}': "
                        f"{len(forwardings)} forwarding(s) to emit, {len(denied)} denied pair(s) "
                        "left as absent forwardings"
                    ),
                    path=f"instance:{enforcer_id}.openwrt_zones",
                )
            )
            if remote:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="I9902",
                        severity="info",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}' has no local segment for zone(s): {', '.join(remote)}. "
                            "Expected for zones reached through a tunnel; an uplink zone appearing here means "
                            "its interface intent is not authored yet."
                        ),
                        path=f"instance:{enforcer_id}.openwrt_zones.remote",
                    )
                )

        ctx.publish("openwrt_zones", openwrt_zones)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={"openwrt_zones": openwrt_zones},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize, after base.compiler.effective_model
        # (also finalize, order 60). The kernel dispatches phase hooks rather
        # than execute() directly; same one-line delegation the other
        # finalize-phase compilers use.
        return self.execute(ctx, stage)

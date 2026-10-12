#!/usr/bin/env python3
"""Lowers `runtime_intent` onto the uapi resource surface, before rendering.

The firewall plan says which interfaces exist and which zone each sits in. This
plugin says what each one *is*: proto, addresses, bridge membership, radio,
SSID, DHCP pool. Backend specialization belongs in the compile stage, where a
validator can still see it (W07-BACKEND-SPECIALIZATION-DECISION.md), so the
arithmetic and the shape juggling happen here rather than inside a template.

Interface **names** are not re-derived here. `object.openwrt.compiler.zones`
already derives the uci section name for every segment, and `firewall_zone.
network` references those names; deriving them a second time would let the two
plans disagree about what a section is called while both looked correct. This
compiler consumes the zone plan and reads the names out of it, so there is one
producer of that fact.

Four things the provider's schema forces, each of which would be a silent defect
if it were left to a template:

* **`ipaddrs` is a list, `netmask` a scalar, and `ipaddr` is read-only.** A
  topology CIDR has to be split into exactly that shape. Writing to `ipaddr`
  would be writing to a computed attribute.
* **`uapi_wireless_device.channel` is typed Number**, so the string `auto` is
  not renderable. netifd settles what to use instead: `_wdev_prepare_channel`
  matches `""|0|auto` and sets `channel=0; auto_channel=1`, so `0` is an exact
  synonym and the only spelling the attribute can carry.
* **`uapi_dhcp_server` has `start` and `limit` but no `end`.** An authored
  `dhcp_range: "a-b"` must become a host offset and a count. Getting the count
  wrong by one is invisible: the pool is simply one address short.
* **`uapi_wireless_interface.network` is a single string**, not a list, so one
  SSID maps to one network - and the string must name a section that exists
  (E9912), or clients associate onto nothing.

Parked sections are rendered `disabled`, never omitted. Four of the six APs are
deliberately off as the ath11k memory-leak budget (report D7); omitting them
would leave them unmanaged, so turning one on would be a hand-edit on the device
instead of a topology change.

WireGuard peers are deliberately **not** lowered here. A peer needs its public
key and endpoint, which live in the tunnel instances and in SOPS, and an
interface needs its private key; half-rendering a tunnel that cannot come up is
worse than recording that it is deferred. The interfaces are published with
`private_key_ref` naming where the secret lives, and the deferral is published
as data so the generator reports it rather than discovering it.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage

_OPENWRT_OS_CAP = "cap.os.openwrt"

# mac80211 is the only driver family this device has; `type` is required on
# uapi_wireless_device and has no sensible default.
_WIRELESS_TYPE = "mac80211"

# Routing tables the kernel owns: 255 local, 254 main, 253 default.
_RESERVED_TABLES = frozenset({253, 254, 255})

# The main-table lookup sits at priority 32766. A source rule must be evaluated
# BEFORE it or it never matches - everything would already have been resolved
# against the main table. Derived from the table number rather than authored, so
# the mapping is 1:1 and stable, and well clear of the 1000-2000 band netifd
# uses for its own per-interface rules.
_RULE_PRIORITY_BASE = 30000
_MAIN_TABLE_PRIORITY = 32766


def _rule_priority(table: int) -> int:
    return _RULE_PRIORITY_BASE + table


def _extract_capabilities(row: dict[str, Any]) -> set[str]:
    caps: set[str] = set()
    for block in (row.get("instance") or {}, row.get("object") or {}, row):
        if not isinstance(block, dict):
            continue
        for field in ("capabilities", "derived_capabilities", "enabled_capabilities", "vendor_capabilities"):
            values = block.get(field)
            if isinstance(values, list):
                caps.update(value for value in values if isinstance(value, str) and value)
    return caps


def _is_enabled(entry: dict[str, Any]) -> bool:
    """Absent `enabled` means enabled; only an explicit false parks a section."""
    return entry.get("enabled") is not False


def _split_address(address: Any) -> tuple[str, str] | None:
    """`"192.168.1.1/24"` -> `("192.168.1.1", "255.255.255.0")`.

    `ipaddrs` takes the host address and `netmask` the mask, separately; a
    prefix-length string in either would be rejected by netifd.
    """
    if not isinstance(address, str) or "/" not in address:
        return None
    try:
        iface = ipaddress.ip_interface(address)
    except ValueError:
        return None
    return str(iface.ip), str(iface.network.netmask)


def _router_address(cidr: Any, gateway: Any) -> tuple[str, str] | None:
    """The router's own address on a segment: its gateway, with the segment mask."""
    if not isinstance(cidr, str) or not isinstance(gateway, str):
        return None
    try:
        network = ipaddress.ip_network(cidr, strict=False)
        host = ipaddress.ip_address(gateway)
    except ValueError:
        return None
    if host not in network:
        return None
    return str(host), str(network.netmask)


def _dhcp_pool(cidr: Any, dhcp_range: Any) -> tuple[int, int] | str:
    """`("10.77.1.0/24", "10.77.1.100-10.77.1.200")` -> `(100, 101)`.

    Returns a reason string instead when the range cannot be expressed, because
    `uapi_dhcp_server` has no `end`: `start` is an offset from the network
    address and `limit` is a count, so a range that leaves the prefix or runs
    backwards has no faithful lowering. 100 through 200 inclusive is 101
    addresses - the off-by-one here is the whole reason this is not a template
    expression.
    """
    if not isinstance(dhcp_range, str) or "-" not in dhcp_range:
        return f"not a 'first-last' range: {dhcp_range!r}"
    first_text, _, last_text = dhcp_range.partition("-")
    try:
        network = ipaddress.ip_network(str(cidr), strict=False)
        first = ipaddress.ip_address(first_text.strip())
        last = ipaddress.ip_address(last_text.strip())
    except ValueError as exc:
        return f"unparseable: {exc}"
    if first not in network or last not in network:
        return f"{first}-{last} is not inside {network}"
    if int(last) < int(first):
        return f"{first}-{last} runs backwards"
    return int(first) - int(network.network_address), int(last) - int(first) + 1


def _auto_channel(channel: Any) -> int | None:
    """Normalize to what the Number-typed attribute can carry.

    netifd's `_wdev_prepare_channel` matches `""|0|auto` and sets
    `channel=0; auto_channel=1`, so every auto spelling becomes 0 and a pinned
    channel passes through. `None` means the radio declared nothing, which
    netifd also reads as auto - emitted as 0 so the rendered state is explicit
    rather than inherited from whatever the device already had.
    """
    if channel is None:
        return 0
    if isinstance(channel, bool):
        return None
    if isinstance(channel, int):
        return channel
    if isinstance(channel, str):
        text = channel.strip().lower()
        if text in {"", "0", "auto"}:
            return 0
        try:
            return int(text)
        except ValueError:
            return None
    return None


class OpenwrtInterfacesCompiler(CompilerPlugin):
    """Lowers device runtime intent into uapi network, wireless and DHCP intent."""

    _ZONES_PLUGIN_ID = "object.openwrt.compiler.zones"
    _ZONES_KEY = "openwrt_zones"
    _MODEL_PLUGIN_ID = "base.compiler.effective_model"
    _MODEL_KEY = "effective_model_candidate"

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Registered at phase: finalize, order 81, right after the zone compiler
        # whose plan this consumes. The kernel dispatches phase hooks, and the
        # base `on_finalize` returns SKIPPED - so without this delegation the
        # plugin loads, traces a plugin_start, and does nothing.
        return self.execute(ctx, stage)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        plans = ctx.subscribe(self._ZONES_PLUGIN_ID, self._ZONES_KEY)
        model = ctx.subscribe(self._MODEL_PLUGIN_ID, self._MODEL_KEY)
        if not isinstance(plans, dict):
            plans = {}

        instances = model.get("instances", {}) if isinstance(model, dict) else {}
        device_rows = instances.get("devices", []) if isinstance(instances, dict) else []
        if not isinstance(device_rows, list):
            device_rows = []
        rows_by_id = {
            row.get("instance_id"): row
            for row in device_rows
            if isinstance(row, dict) and row.get("instance_id")
        }

        network_rows = instances.get("network", []) if isinstance(instances, dict) else []
        if not isinstance(network_rows, list):
            network_rows = []
        # Tunnel instances, which carry the far side of every WireGuard
        # interface: its listen port, the prefixes this device routes through
        # it, and where its keys live.
        tunnels = {
            str(row.get("instance_id")): row.get("instance_data") or {}
            for row in network_rows
            if isinstance(row, dict) and str(row.get("instance_id", "")).startswith("inst.tunnel.")
        }

        lowered: dict[str, Any] = {}

        for enforcer_id in sorted(plans):
            plan = plans.get(enforcer_id)
            row = rows_by_id.get(enforcer_id)
            if not isinstance(plan, dict) or not isinstance(row, dict):
                continue
            if _OPENWRT_OS_CAP not in _extract_capabilities(row):
                continue

            intent = (row.get("instance_data") or {}).get("runtime_intent")
            if not isinstance(intent, dict):
                continue

            entry, entry_diagnostics = self._lower_device(
                enforcer_id, plan, intent, tunnels, stage
            )
            diagnostics.extend(entry_diagnostics)
            lowered[enforcer_id] = entry

        for enforcer_id in sorted(lowered):
            entry = lowered[enforcer_id]
            diagnostics.append(
                self.emit_diagnostic(
                    code="I9904",
                    severity="info",
                    stage=stage,
                    message=(
                        f"Enforcer '{enforcer_id}': lowered {len(entry['interfaces'])} interfaces, "
                        f"{len(entry['devices'])} devices, {len(entry['wireless_devices'])} radios, "
                        f"{len(entry['wireless_interfaces'])} wifi-ifaces "
                        f"({entry['parked_wireless']} parked), {len(entry['dhcp_servers'])} DHCP pools, "
                        f"{len(entry['peers'])} peer(s), {len(entry['routes'])} policy route(s), "
                        f"{len(entry['rules'])} ip-rule(s), "
                        f"{len(entry['adoption'])} section(s) to adopt, "
                        f"{len(entry['unmanaged'])} left unmanaged"
                        f"{'' if entry['adoption_reconciled'] else ' (ledger NOT reconciled against the device)'}. "
                        f"Deferred: {', '.join(entry['deferred']) or 'nothing'}."
                    ),
                    path=f"instance:{enforcer_id}.runtime_intent",
                )
            )

        ctx.publish("openwrt_interfaces", lowered)
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"openwrt_interfaces": lowered, "device_count": len(lowered)},
        )

    # ------------------------------------------------------------------

    def _lower_device(
        self,
        enforcer_id: str,
        plan: dict[str, Any],
        intent: dict[str, Any],
        tunnels: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> tuple[dict[str, Any], list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []

        segments = self._segments_from_plan(plan)
        interfaces, devices, unmanaged = self._lower_interfaces(segments, intent)

        dhcp_servers, dhcp_diagnostics = self._lower_dhcp(enforcer_id, segments, stage)
        diagnostics.extend(dhcp_diagnostics)

        radios, wifi_ifaces, wireless_diagnostics = self._lower_wireless(
            enforcer_id, intent, segments, interfaces, stage
        )
        diagnostics.extend(wireless_diagnostics)

        diagnostics.extend(self._check_mtu_budget(enforcer_id, intent, segments, stage))

        peers, peer_diagnostics = self._lower_peers(enforcer_id, intent, tunnels, stage)
        diagnostics.extend(peer_diagnostics)

        routes, rules, routing_diagnostics = self._lower_policy_routing(
            enforcer_id, intent, segments, peers, stage
        )
        diagnostics.extend(routing_diagnostics)

        adoption, adoption_diagnostics = self._lower_adoption(
            enforcer_id,
            intent,
            rendered={
                "uapi_network_interface": {str(item["id"]) for item in interfaces},
                "uapi_network_device": {str(item["id"]) for item in devices},
                "uapi_wireless_device": {str(item["id"]) for item in radios},
                "uapi_wireless_interface": {str(item["id"]) for item in wifi_ifaces},
                "uapi_dhcp_server": {str(item["id"]) for item in dhcp_servers},
            },
            stage=stage,
        )
        diagnostics.extend(adoption_diagnostics)

        packages = []
        services = intent.get("services")
        if isinstance(services, dict) and isinstance(services.get("packages"), list):
            packages = [item for item in services["packages"] if isinstance(item, str) and item]

        entry = {
            "peers": peers,
            "routes": routes,
            "rules": rules,
            "adoption": adoption,
            "adoption_reconciled": bool(
                (intent.get("adoption") or {}).get("reconciled_against_device", False)
            )
            if isinstance(intent.get("adoption"), dict)
            else False,
            "devices": devices,
            # Sections this device has that are deliberately left alone, with
            # the reason. Named, not omitted: an unmanaged section is a real
            # gap in coverage and a reader deserves to know it was a decision.
            "unmanaged": unmanaged,
            "interfaces": interfaces,
            "wireless_devices": radios,
            "wireless_interfaces": wifi_ifaces,
            "parked_wireless": sum(1 for item in wifi_ifaces if item.get("disabled")),
            "dhcp_servers": dhcp_servers,
            "packages": sorted(packages),
            # Named rather than silently absent, so the generator reports what it
            # is not rendering instead of a reader inferring it from a gap.
            # Nothing is deferred any more: peers are lowered, with their
            # public key and endpoint host as variables rather than values.
            "deferred": [],
        }
        return entry, diagnostics

    @staticmethod
    def _segments_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
        """Every local segment the zone plan derived, with its uci name attached.

        Read from the zone plan rather than from the model, so the section names
        here and the names in `firewall_zone.network` are the same strings by
        construction.
        """
        found: list[dict[str, Any]] = []
        zones = plan.get("zones")
        if not isinstance(zones, dict):
            return found
        for zone_ref in sorted(zones):
            zone = zones.get(zone_ref)
            if not isinstance(zone, dict):
                continue
            for segment in zone.get("segments") or []:
                if isinstance(segment, dict) and segment.get("interface"):
                    found.append({**segment, "trust_zone_ref": zone_ref})
        return found

    def _lower_interfaces(
        self,
        segments: list[dict[str, Any]],
        intent: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        interfaces: list[dict[str, Any]] = []
        devices: list[dict[str, Any]] = []
        unmanaged: list[str] = []

        management = intent.get("management")
        if isinstance(management, dict) and management.get("interface"):
            address = _split_address(management.get("address"))
            interfaces.append(
                {
                    "id": management["interface"],
                    "kind": "management",
                    "proto": management.get("proto") or "static",
                    "device": management.get("device"),
                    "ipaddrs": [address[0]] if address else [],
                    "netmask": address[1] if address else None,
                    "disabled": False,
                    # The interface the uapi request arrives on. E9904 holds the
                    # invariant; carried here so the generator can refuse to
                    # render proto/ipaddrs for it rather than trusting the flag.
                    "immutable": bool(management.get("immutable", False)),
                    "endpoint_arrives_here": bool(management.get("endpoint_arrives_here", False)),
                }
            )
            # The management bridge is deliberately NOT emitted as a
            # uapi_network_device, even though bridge membership lives there
            # and `bridge_ports` is authored.
            #
            # Measured on the device 2026-10-12: the stock bridge is
            # `network.cfg030f15` - an ANONYMOUS section whose `name` option is
            # 'br-lan'. The kernel device name and the uci section name are
            # different things, and only the latter can be imported. So this
            # section cannot be adopted (uapi would rename it to a ULID), which
            # leaves only two options, and one of them is unsafe:
            #
            #   * Create a second, named `config device` for the same kernel
            #     device -> two bridge definitions for br-lan.
            #   * Delete the stock section by hand first, as the wifi-iface
            #     path does -> between the delete and the create, br-lan has no
            #     definition, the LAN goes down, and the apply cannot arrive.
            #     That is the stranding case E9904 exists to prevent, one level
            #     below the interface it protects.
            #
            # So the bridge carrying the management path stays unmanaged. It is
            # stock, it already matches what topology declares (ports lan1 and
            # lan2), and `ignore_changes` on the interface above is the same
            # reasoning one level up. Reported in I9904 rather than silently
            # skipped.
            if isinstance(management.get("device"), str) and isinstance(
                management.get("bridge_ports"), list
            ):
                unmanaged.append(
                    f"{management['device']} (management bridge: the stock section is anonymous, "
                    "and both ways of managing it interrupt the path the apply arrives over)"
                )

        uplink = intent.get("uplink")
        if isinstance(uplink, dict):
            for role in ("primary", "wired"):
                spec = uplink.get(role)
                if not isinstance(spec, dict) or not spec.get("interface"):
                    continue
                interfaces.append(
                    {
                        "id": spec["interface"],
                        "kind": "uplink",
                        "role": role,
                        "proto": spec.get("proto") or "dhcp",
                        "device": spec.get("device"),
                        "ipaddrs": [],
                        "netmask": None,
                        "disabled": not _is_enabled(spec),
                        "immutable": False,
                        # A radio-backed uplink has no `device`: netifd attaches
                        # the station interface to it by name from the
                        # wifi-iface's `network`, so naming a device here would
                        # claim a netdev that does not exist until association.
                        "wireless_iface": spec.get("wireless_iface"),
                    }
                )

        wireguard = intent.get("wireguard")
        if isinstance(wireguard, dict):
            for spec in wireguard.get("interfaces") or []:
                if not isinstance(spec, dict) or not spec.get("name"):
                    continue
                address = _split_address(spec.get("tunnel_ip"))
                interfaces.append(
                    {
                        "id": spec["name"],
                        "kind": "wireguard",
                        "proto": "wireguard",
                        "device": None,
                        # A /32 tunnel address is normal on WireGuard, and
                        # ip_interface keeps the mask the author wrote rather
                        # than widening it to the peer's view.
                        "ipaddrs": [address[0]] if address else [],
                        "netmask": address[1] if address else None,
                        "mtu": spec.get("mtu"),
                        "disabled": not _is_enabled(spec),
                        "immutable": False,
                        "tunnel_ref": spec.get("tunnel_ref"),
                        "advertises": list(spec.get("advertises") or []),
                        "exit_mode": spec.get("exit_mode"),
                        # Where the secret lives, not the secret. The generator
                        # decides how to surface it; nothing here reads SOPS.
                        "private_key_ref": f"instances/{spec['name']}.private_key",
                    }
                )

        for segment in segments:
            address = _router_address(segment.get("cidr"), segment.get("gateway"))
            interfaces.append(
                {
                    "id": segment["interface"],
                    "kind": "segment",
                    "proto": "static",
                    "device": None,
                    "ipaddrs": [address[0]] if address else [],
                    "netmask": address[1] if address else None,
                    "mtu": segment.get("mtu"),
                    "disabled": False,
                    "immutable": False,
                    "instance_id": segment.get("instance_id"),
                }
            )

        interfaces.sort(key=lambda item: str(item["id"]))
        devices.sort(key=lambda item: str(item["id"]))
        return interfaces, devices, sorted(unmanaged)

    def _lower_dhcp(
        self,
        enforcer_id: str,
        segments: list[dict[str, Any]],
        stage: Stage,
    ) -> tuple[list[dict[str, Any]], list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []
        servers: list[dict[str, Any]] = []

        for segment in segments:
            authored_range = segment.get("dhcp_range")
            if authored_range is None:
                # No pool authored: dnsmasq must not serve the segment at all.
                servers.append(
                    {
                        "id": f"dhcp_{segment['interface']}",
                        "interface": segment["interface"],
                        "ignore": True,
                    }
                )
                continue

            pool = _dhcp_pool(segment.get("cidr"), authored_range)
            if isinstance(pool, str):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9911",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': segment '{segment['interface']}' declares "
                            f"dhcp_range {authored_range!r}, which cannot be lowered onto uapi_dhcp_server - "
                            f"{pool}. The resource exposes start and limit but no end, so an unfaithful "
                            "lowering would serve addresses outside the segment or an empty pool, and "
                            "dnsmasq reports neither."
                        ),
                        path=f"instance:{segment.get('instance_id')}.dhcp_range",
                    )
                )
                continue

            start, limit = pool
            servers.append(
                {
                    "id": f"dhcp_{segment['interface']}",
                    "interface": segment["interface"],
                    "start": start,
                    "limit": limit,
                    "ignore": False,
                }
            )

        servers.sort(key=lambda item: str(item["id"]))
        return servers, diagnostics

    def _lower_wireless(
        self,
        enforcer_id: str,
        intent: dict[str, Any],
        segments: list[dict[str, Any]],
        interfaces: list[dict[str, Any]],
        stage: Stage,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []
        radios: list[dict[str, Any]] = []
        wifi_ifaces: list[dict[str, Any]] = []

        wireless = intent.get("wireless")
        if not isinstance(wireless, dict):
            return radios, wifi_ifaces, diagnostics

        declared = wireless.get("radios")
        for radio_name in sorted(declared if isinstance(declared, dict) else {}):
            radio = declared.get(radio_name)
            if not isinstance(radio, dict):
                continue
            radios.append(
                {
                    # The section name is the radio's only identity: the schema
                    # has no `path`, so `id` must match the stock section for
                    # adoption to bind to the intended phy.
                    "id": radio_name,
                    "type": _WIRELESS_TYPE,
                    "band": radio.get("band"),
                    "channel": _auto_channel(radio.get("channel")),
                    "htmode": radio.get("htmode"),
                    "country": radio.get("country"),
                    "disabled": not _is_enabled(radio),
                }
            )

        # Everything a wifi-iface's `network` may legally name: a segment's uci
        # section or a non-segment interface such as the uplink.
        known_networks = {str(item["id"]) for item in interfaces}
        by_instance = {
            str(segment.get("instance_id")): str(segment["interface"]) for segment in segments
        }

        for spec in wireless.get("interfaces") or []:
            if not isinstance(spec, dict) or not spec.get("name"):
                continue

            network_ref = spec.get("network_ref")
            if isinstance(network_ref, str) and network_ref:
                network = by_instance.get(network_ref)
                source = f"network_ref {network_ref}"
            else:
                network = spec.get("network")
                source = f"network {network!r}"

            if not isinstance(network, str) or network not in known_networks:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9912",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': wifi-iface '{spec['name']}' resolves to no "
                            f"rendered network ({source}). uapi_wireless_interface.network names one "
                            "config interface section, so a name that does not exist leaves the SSID "
                            "bridged nowhere - clients associate, get no address, and hostapd reports "
                            "success."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.wireless.interfaces.{spec['name']}",
                    )
                )
                continue

            wifi_ifaces.append(
                {
                    "id": spec["name"],
                    "device": spec.get("device"),
                    "mode": spec.get("mode"),
                    "ssid": spec.get("ssid"),
                    "encryption": spec.get("encryption"),
                    # Scalar, per the schema: one SSID, one network.
                    "network": network,
                    # Rendered, not omitted: a parked AP that Terraform does not
                    # manage can be switched on by hand and never show as drift.
                    "disabled": not _is_enabled(spec),
                }
            )

        wifi_ifaces.sort(key=lambda item: str(item["id"]))
        return radios, wifi_ifaces, diagnostics

    # Anonymous uci sections are named `cfg` plus six hex digits. uapi adopts a
    # named section in place but adopts an anonymous one by RENAMING it to a
    # ULID, which mutates the router (W9903), so the two must be told apart
    # before an import block is emitted rather than after.
    _ANONYMOUS_SECTION = re.compile(r"^cfg[0-9a-f]{6,}$")

    def _lower_peers(
        self,
        enforcer_id: str,
        intent: dict[str, Any],
        tunnels: dict[str, dict[str, Any]],
        stage: Stage,
    ) -> tuple[list[dict[str, Any]], list[PluginDiagnostic]]:
        """One peer per WireGuard interface, derived from its tunnel instance.

        What comes from topology and what does not is the whole design here.

        From topology: which peer exists, its `listen_port`, the keepalive, and
        its `allowed_ips`. The last is the interesting one - `allowed_ips` on a
        WireGuard peer is simultaneously the crypto-routing ACL and, with
        `route_allowed_ips`, a route installer. A tunnel carrying a default
        route needs `0.0.0.0/0` so the peer may carry internet traffic at all,
        but `route_allowed_ips` must stay FALSE for it: letting netifd install
        that as a main-table default route would capture every segment,
        including the split-mode one, and silently collapse the two-mode design
        into one. The default route is installed deliberately instead, in the
        tunnel's own table, by the policy-routing resources.

        Not from topology: the public key and the endpoint host. A public key is
        not secret, but in this repo it lives in SOPS beside the private one, and
        a VPS's public address is an operational value rather than topology.
        Both become `sensitive` variables, which is also what the MikroTik
        generator does for the same reason.
        """
        diagnostics: list[PluginDiagnostic] = []
        peers: list[dict[str, Any]] = []

        wireguard = intent.get("wireguard")
        if not isinstance(wireguard, dict):
            return peers, diagnostics

        for spec in wireguard.get("interfaces") or []:
            if not isinstance(spec, dict) or not spec.get("name"):
                continue
            name = str(spec["name"])
            tunnel_ref = spec.get("tunnel_ref")
            tunnel = tunnels.get(str(tunnel_ref)) if isinstance(tunnel_ref, str) else None
            if not isinstance(tunnel, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9915",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': WireGuard interface '{name}' names tunnel "
                            f"'{tunnel_ref}', which is not a tunnel instance in this model. Without it "
                            "there is no peer to derive, and an interface with no peer comes up and "
                            "carries nothing."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.wireguard.{name}.tunnel_ref",
                    )
                )
                continue

            # The far side is the tunnel's server endpoint: this device is a
            # road-warrior client, so it dials out and the server listens.
            server = None
            for role_key in ("endpoint_a", "endpoint_b"):
                candidate = tunnel.get(role_key)
                if isinstance(candidate, dict) and candidate.get("role") == "server":
                    server = candidate
                    break
            if server is None:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9915",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': tunnel '{tunnel_ref}' declares no endpoint with "
                            f"role 'server', so '{name}' has no address to dial. A road-warrior client "
                            "cannot be the listening side."
                        ),
                        path=f"instance:{tunnel_ref}.endpoint_a",
                    )
                )
                continue

            # Everything this interface routes through the tunnel. The far side
            # must be permitted to source those prefixes, or WireGuard drops the
            # reply before the firewall ever sees it.
            allowed: list[str] = []
            for peer_entry in tunnel.get("road_warrior_peers") or []:
                if isinstance(peer_entry, dict) and peer_entry.get("device_ref") == enforcer_id:
                    allowed.extend(
                        item for item in peer_entry.get("routes") or [] if isinstance(item, str)
                    )
            network = tunnel.get("tunnel_network")
            if isinstance(network, str) and network and network not in allowed:
                allowed.append(network)

            carries_default = bool(spec.get("default_route_for"))
            prefixes = sorted(set(allowed))
            if carries_default:
                # The ACL must be wide for a full tunnel: return traffic from
                # the internet arrives with arbitrary source addresses, so the
                # peer has to be permitted to source anything or WireGuard
                # drops the replies before the firewall sees them. 0.0.0.0/0
                # subsumes the specific prefixes for ACL purposes - but they
                # are kept in `prefixes` below, because with
                # route_allowed_ips=false netifd installs NO routes at all and
                # the specific ones still have to exist in the main table.
                allowed = ["0.0.0.0/0"]
            else:
                allowed = prefixes

            peers.append(
                {
                    "id": f"peer_{name}",
                    "interface": name,
                    "allowed_ips": allowed,
                    # Destination prefixes reached through this tunnel, kept
                    # separately from the ACL: these become main-table routes so
                    # every permitted zone can use them, not only the segments
                    # whose default route this tunnel carries.
                    "prefixes": prefixes,
                    "endpoint_port": server.get("listen_port"),
                    "persistent_keepalive": spec.get("persistent_keepalive"),
                    # FALSE whenever this tunnel carries a default route: netifd
                    # would otherwise install 0.0.0.0/0 in the MAIN table and
                    # capture every segment, collapsing the two modes into one.
                    "route_allowed_ips": not carries_default,
                    "disabled": not _is_enabled(spec),
                    "peer_device_ref": server.get("device_ref"),
                    "secrets_ref": tunnel.get("secrets_ref"),
                }
            )

        peers.sort(key=lambda item: str(item["id"]))
        return peers, diagnostics

    def _lower_policy_routing(
        self,
        enforcer_id: str,
        intent: dict[str, Any],
        segments: list[dict[str, Any]],
        peers: list[dict[str, Any]],
        stage: Stage,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[PluginDiagnostic]]:
        """Routes and ip-rules that make D2's two modes take two different paths.

        Policy routing is required here, not stylistic. Both modes have
        destination 0.0.0.0/0, so a destination-based default route cannot
        separate them - whichever route won would capture both. Only a
        source-based rule can, which is what `routing.selector: source_subnet`
        has been declaring all along while nothing read it.

        The shape per full-tunnel tunnel is two resources: a default route in
        the tunnel's own table, and an ip-rule sending that segment's source
        prefix to that table. A segment named by no `default_route_for` gets no
        rule, falls through to the main table and egresses via the venue uplink
        - which is exactly what split and guest mode want.
        """
        diagnostics: list[PluginDiagnostic] = []
        routes: list[dict[str, Any]] = []
        rules: list[dict[str, Any]] = []

        by_instance = {
            str(segment.get("instance_id")): segment for segment in segments if segment.get("instance_id")
        }
        tables_seen: dict[int, str] = {}
        routed_segments: set[str] = set()

        wireguard = intent.get("wireguard")
        if not isinstance(wireguard, dict):
            return routes, rules, diagnostics

        for spec in wireguard.get("interfaces") or []:
            if not isinstance(spec, dict) or not spec.get("name"):
                continue
            targets = [item for item in spec.get("default_route_for") or [] if isinstance(item, str)]
            if not targets:
                continue

            name = str(spec["name"])
            table = spec.get("route_table")
            if not isinstance(table, int) or isinstance(table, bool):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9914",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': tunnel '{name}' carries a default route for "
                            f"{len(targets)} segment(s) but declares no numeric route_table. The rule has "
                            "nowhere to point, so the segment would fall through to the main table and "
                            "egress via the venue - the opposite of full-tunnel, and silently."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.wireguard.{name}.route_table",
                    )
                )
                continue

            if table in _RESERVED_TABLES:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9914",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': tunnel '{name}' declares route_table {table}, which "
                            "the kernel reserves (253 default, 254 main, 255 local). Writing a default "
                            "route there would hijack the host's own routing rather than add a policy path."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.wireguard.{name}.route_table",
                    )
                )
                continue

            previous = tables_seen.get(table)
            if previous is not None:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9914",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': tunnels '{previous}' and '{name}' both declare "
                            f"route_table {table}. The second default route would replace or race the "
                            "first, so one tunnel's traffic silently leaves through the other."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.wireguard.{name}.route_table",
                    )
                )
                continue

            priority = _rule_priority(table)
            if priority >= _MAIN_TABLE_PRIORITY:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9914",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': tunnel '{name}' with route_table {table} derives "
                            f"ip-rule priority {priority}, at or after the main-table lookup at "
                            f"{_MAIN_TABLE_PRIORITY}. The rule would never match, because the destination "
                            "is already resolved against the main table by then."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.wireguard.{name}.route_table",
                    )
                )
                continue

            tables_seen[table] = name

            routes.append(
                {
                    "id": f"route_default_{name}",
                    "target": "0.0.0.0/0",
                    "interface": name,
                    "table": table,
                    # A parked tunnel's route is rendered disabled for the same
                    # reason its interface is: so enabling it is one topology
                    # change and not a hand-edit that never shows as drift.
                    "disabled": not _is_enabled(spec),
                    "tunnel": name,
                    "kind": "default",
                }
            )

            for target in targets:
                segment = by_instance.get(target)
                if not isinstance(segment, dict) or not segment.get("cidr"):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E9914",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Enforcer '{enforcer_id}': tunnel '{name}' claims the default route for "
                                f"'{target}', which is not a segment this device owns. The ip-rule would "
                                "have no source prefix to match."
                            ),
                            path=f"instance:{enforcer_id}.runtime_intent.wireguard.{name}.default_route_for",
                        )
                    )
                    continue
                routed_segments.add(target)
                rules.append(
                    {
                        "id": f"rule_{segment['interface']}_via_{name}",
                        "src": segment["cidr"],
                        "lookup": table,
                        # Explicit, because routing rules DO have ordering -
                        # unlike the firewall, where uapi exposes none.
                        "priority": priority,
                        "disabled": not _is_enabled(spec),
                        "segment": segment["interface"],
                        "tunnel": name,
                    }
                )

        # Specific prefixes reached through each tunnel go in the MAIN table,
        # not in the tunnel's policy table.
        #
        # This is the half that `route_allowed_ips = false` removes and that has
        # to be put back deliberately. Slate-Split is the case that proves it
        # necessary: it reaches home over wg-home while its internet stays on
        # the venue, so it has no ip-rule and resolves against the main table -
        # where, without these, there is no route to the home prefixes at all
        # and its home access silently fails. The router's own traffic to those
        # prefixes resolves the same way.
        for peer in peers:
            tunnel_name = str(peer.get("interface"))
            for prefix in peer.get("prefixes") or []:
                routes.append(
                    {
                        "id": f"route_{tunnel_name}_{str(prefix).replace('/', '_').replace('.', '_')}",
                        "target": prefix,
                        "interface": tunnel_name,
                        # No `table`: the main table, so every permitted zone
                        # can use it rather than only the full-tunnel segments.
                        "table": None,
                        "disabled": bool(peer.get("disabled")),
                        "tunnel": tunnel_name,
                        "kind": "prefix",
                    }
                )

        diagnostics.extend(
            self._check_internet_path(enforcer_id, segments, routed_segments, stage)
        )

        routes.sort(key=lambda item: str(item["id"]))
        rules.sort(key=lambda item: str(item["id"]))
        return routes, rules, diagnostics

    def _check_internet_path(
        self,
        enforcer_id: str,
        segments: list[dict[str, Any]],
        routed_segments: set[str],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        """W9905: a segment cut off from the uplink and from every tunnel.

        A warning rather than an error because the compiler cannot know whether
        a segment is *meant* to reach the internet - an isolated IoT segment
        legitimately has no path. What it can say is that the firewall half of
        full-tunnel mode was built and the routing half was not, which presents
        on the device as "home works, internet does not".
        """
        diagnostics: list[PluginDiagnostic] = []

        for segment in segments:
            instance_id = str(segment.get("instance_id") or "")
            if instance_id in routed_segments:
                continue
            # `forward_to_uplink` is published by the zone compiler per segment:
            # whether the matrix lets this segment's zone reach the uplink zone.
            # Absent means the question was not answered, not that it is false.
            if segment.get("forward_to_uplink") is not False:
                continue
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9905",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Enforcer '{enforcer_id}': segment '{segment.get('interface')}' is denied "
                        "forwarding to the uplink zone and takes no default route through any tunnel, so "
                        "it has no path off this device. Intended for an isolated segment; on one meant "
                        "to be full-tunnel it means the firewall half of the mode exists and the routing "
                        "half does not."
                    ),
                    path=f"instance:{instance_id}.trust_zone_ref",
                )
            )

        return diagnostics

    def _lower_adoption(
        self,
        enforcer_id: str,
        intent: dict[str, Any],
        *,
        rendered: dict[str, set[str]],
        stage: Stage,
    ) -> tuple[list[dict[str, Any]], list[PluginDiagnostic]]:
        """Pair each ledger entry with the resource it adopts.

        The ledger is authored rather than inferred because both ways of being
        wrong are loud: the provider refuses duplicate-name creation with 422
        conflict, so a section missing from the ledger fails the first apply,
        and a section listed that does not exist fails the import. Neither is
        drift - which is the argument for authoring it.

        What is checked here is the half that can be checked without the device:
        that every entry names a resource this generator actually renders
        (E9913). Terraform refuses an import block whose target does not exist,
        and refuses it for the whole root, so one stale entry costs every plan.
        """
        diagnostics: list[PluginDiagnostic] = []
        adoption: list[dict[str, Any]] = []

        ledger = intent.get("adoption")
        if not isinstance(ledger, dict):
            return adoption, diagnostics

        for item in ledger.get("sections") or []:
            if not isinstance(item, dict):
                continue
            resource = item.get("resource")
            section_id = item.get("id")
            if not isinstance(resource, str) or not isinstance(section_id, str):
                continue

            anonymous = bool(self._ANONYMOUS_SECTION.match(section_id))
            known = rendered.get(resource)

            # An anonymous section's ledger id is the name the DEVICE gave it
            # (`cfg030f15`), while the resource's id is what this topology wants
            # it called. Those differ by construction, so an anonymous entry
            # cannot be paired with a rendered resource by id - and it must not
            # be, because uapi would rename it to a ULID rather than to our
            # name. It is passed through flagged, for W9903 to report at render
            # time; E9913 is about a *named* target that is not rendered.
            if anonymous and known is not None:
                adoption.append({"resource": resource, "id": section_id, "anonymous": True})
                continue

            if known is None or section_id not in known:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9913",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': the adoption ledger names "
                            f"{resource}.'{section_id}', which this generator does not render. "
                            "Terraform refuses an import block whose target does not exist, and refuses "
                            "it for the whole root, so one stale entry costs every plan. Either the "
                            "section should not be adopted, or the resource it adopts is missing from "
                            "the topology."
                        ),
                        path=f"instance:{enforcer_id}.runtime_intent.adoption.sections",
                    )
                )
                continue

            # `anonymous` is derived, never authored: an author asserting "this
            # one is named" is an assertion that can be wrong, while the uci
            # naming convention is a fact about the string.
            adoption.append({"resource": resource, "id": section_id, "anonymous": False})

        adoption.sort(key=lambda item: (item["resource"], item["id"]))
        return adoption, diagnostics

    def _check_mtu_budget(
        self,
        enforcer_id: str,
        intent: dict[str, Any],
        segments: list[dict[str, Any]],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        """W9902: a client segment must not advertise more MTU than its tunnel.

        A WireGuard interface's MTU *is* the inner payload capacity, so the
        condition is `segment_mtu <= tunnel_mtu`. The link between the two is the
        tunnel's `advertises` list, which is the authored statement of which
        prefixes leave through it.

        Reported rather than corrected, and a warning rather than an error,
        because zone `mtu_fix` clamps TCP MSS and keeps TCP working: what breaks
        is UDP and QUIC, which blackhole instead of degrading. That is a
        measurement to take on the venue, not a number to derive here.
        """
        diagnostics: list[PluginDiagnostic] = []

        by_cidr = {
            str(segment.get("cidr")): segment for segment in segments if segment.get("cidr")
        }

        wireguard = intent.get("wireguard")
        if not isinstance(wireguard, dict):
            return diagnostics

        for spec in wireguard.get("interfaces") or []:
            if not isinstance(spec, dict):
                continue
            tunnel_mtu = spec.get("mtu")
            if not isinstance(tunnel_mtu, int):
                continue
            for prefix in spec.get("advertises") or []:
                segment = by_cidr.get(str(prefix))
                if not isinstance(segment, dict):
                    continue
                segment_mtu = segment.get("mtu")
                if not isinstance(segment_mtu, int) or segment_mtu <= tunnel_mtu:
                    continue
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9902",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Enforcer '{enforcer_id}': segment '{segment['interface']}' advertises "
                            f"MTU {segment_mtu} but egresses through '{spec.get('name')}', whose MTU is "
                            f"{tunnel_mtu}. A full-size packet from a client cannot be carried. Zone "
                            "mtu_fix clamps TCP MSS only, so TCP degrades and UDP/QUIC blackhole."
                        ),
                        path=f"instance:{segment.get('instance_id')}.mtu",
                    )
                )

        return diagnostics

#!/usr/bin/env python3
# ADR: 0110, 0118, 0119
"""Integration tests for the OpenWrt zones compiler.

The assertions here are the contract, not illustrations of it. Three of them
encode facts read out of firewall4/netifd source rather than out of ADR 0110,
because on this backend the ADR's RouterOS-shaped guidance would be wrong:
denials are the absence of a forwarding, no terminal drop-all may be produced,
and a zone's input policy must never be left implicit.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test  # noqa: E402

PLUGIN_ID = "object.openwrt.compiler.zones"
_PRODUCERS = {"base.compiler.effective_model", "base.compiler.security_matrix"}

_UNTRUSTED = "inst.trust_zone.untrusted"
_USER = "inst.trust_zone.user"
_VPN = "inst.trust_zone.vpn_tunnel"
_SERVERS = "inst.trust_zone.servers"


def _load_module():
    path = V5_ROOT / "topology" / "object-modules" / "openwrt" / "plugins" / "compilers" / "zones_compiler.py"
    spec = importlib.util.spec_from_file_location("test_openwrt_zones_compiler_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _device_row(instance_id: str, *, os_cap: str) -> dict:
    return {
        "instance_id": instance_id,
        "instance": {"derived_capabilities": [os_cap, "cap.net.l3.security.firewall.zone_policy"]},
        "object": {},
    }


def _segment_row(instance_id: str, *, zone: str, cidr: str, enforcer: str, **extra) -> dict:
    data = {
        "managed_by_ref": enforcer,
        "trust_zone_ref": zone,
        "cidr": cidr,
        "gateway": cidr.replace("0/24", "1"),
    }
    data.update(extra)
    return {"instance_id": instance_id, "instance_data": data}


def _cell(action: str, *, rule: str = "R3", log: bool = False) -> dict:
    return {"action": action, "rule": rule, "reason": f"{rule} test cell", "log": log}


def _fixture_model(enforcer: str = "rtr-slate", os_cap: str = "cap.os.openwrt") -> dict:
    return {
        "instances": {
            "devices": [_device_row(enforcer, os_cap=os_cap)],
            "network": [
                _segment_row(
                    "inst.vlan.slate_home",
                    zone=_USER,
                    cidr="10.77.1.0/24",
                    enforcer=enforcer,
                    dhcp_range="10.77.1.100-10.77.1.200",
                    dns_servers=["10.77.1.1"],
                    mtu=1420,
                ),
                _segment_row(
                    "inst.vlan.slate_ru",
                    zone=_VPN,
                    cidr="10.77.57.0/24",
                    enforcer=enforcer,
                    dhcp_range="10.77.57.100-10.77.57.200",
                    dns_servers=["1.1.1.1"],
                    mtu=1340,
                ),
                # Owned by a different enforcer: must not become a local
                # segment here.
                _segment_row(
                    "inst.vlan.lan",
                    zone=_USER,
                    cidr="192.168.88.0/24",
                    enforcer="rtr-mikrotik-chateau",
                ),
            ],
        }
    }


def _fixture_matrix() -> dict:
    return {
        "rtr-slate": {
            "scope_ids": ["inst.security_matrix.rtr_slate"],
            "zones": {
                _UNTRUSTED: {"security_level": 0, "isolated": False},
                _USER: {"security_level": 3, "isolated": False},
                _VPN: {"security_level": 2, "isolated": False},
                _SERVERS: {"security_level": 4, "isolated": False},
            },
            "matrix": {
                # The two kill-switch cells, as the real matrix produces them
                # once the R6 overrides are applied.
                _USER: {
                    _UNTRUSTED: _cell("drop", rule="R6", log=True),
                    _SERVERS: _cell("accept", rule="R6"),
                    _VPN: _cell("deny", rule="R4"),
                },
                _VPN: {
                    _UNTRUSTED: _cell("drop", rule="R6", log=True),
                    _USER: _cell("deny", rule="R4"),
                },
                # A remote zone's own row: this enforcer filters traffic from
                # its own segments, not between two zones it merely knows of.
                _SERVERS: {_USER: _cell("accept", rule="R3")},
            },
        }
    }


def _run(model: dict, matrix: dict, resolution: dict):
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.effective_model", "effective_model_candidate", model)
    publish_for_test(ctx, "base.compiler.effective_model", "enforcer_resolution", resolution)
    publish_for_test(ctx, "base.compiler.security_matrix", "composed_matrices_by_enforcer", matrix)

    plugin = MODULE.OpenwrtZonesCompiler(PLUGIN_ID)
    result = run_plugin_for_test(plugin, ctx, Stage.COMPILE, consumes_keys=_PRODUCERS)
    assert result.status == PluginStatus.SUCCESS
    return result.output_data["openwrt_zones"]


def _run_with_diagnostics(model: dict, matrix: dict, resolution: dict) -> dict:
    """Run the compiler and return {code: message} instead of the plan."""
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.effective_model", "effective_model_candidate", model)
    publish_for_test(ctx, "base.compiler.effective_model", "enforcer_resolution", resolution)
    publish_for_test(ctx, "base.compiler.security_matrix", "composed_matrices_by_enforcer", matrix)
    plugin = MODULE.OpenwrtZonesCompiler(PLUGIN_ID)
    result = run_plugin_for_test(
        plugin,
        ctx,
        Stage.COMPILE,
        consumes_keys=_PRODUCERS,
    )
    return {d.code: d.message for d in result.diagnostics}


def _resolution(enforcer: str = "rtr-slate", **kwargs) -> dict:
    entry = {"type": "network", "adapter": "cap.firewall.security_matrix.openwrt"}
    entry.update(kwargs)
    return {enforcer: entry}


def test_enforcer_is_selected_by_its_resolved_adapter():
    """Selection is by the adapter the capability engine resolved, as the
    MikroTik compilers do - never by an object_ref name convention (V-14)."""
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())

    assert "rtr-slate" in plan


def test_an_unresolved_adapter_is_not_claimed():
    """Before the D-TYPE-2 mapping existed this resolved to None, and claiming
    it anyway would have meant rendering for a device nothing could render."""
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution(adapter=None))

    assert plan == {}


def test_non_openwrt_enforcer_is_ignored_even_with_an_adapter():
    plan = _run(
        _fixture_model(os_cap="cap.os.routeros"),
        _fixture_matrix(),
        _resolution(adapter="cap.firewall.security_matrix.routeros"),
    )

    assert plan == {}


def test_another_backends_adapter_is_not_claimed():
    plan = _run(
        _fixture_model(),
        _fixture_matrix(),
        _resolution(adapter="cap.firewall.security_matrix.pve"),
    )

    assert plan == {}


def test_denied_pairs_are_recorded_and_absent_from_forwardings():
    """The kill switch: on firewall4 a denial is an omission, not a rule."""
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    forwardings = {(f["src"], f["dest"]) for f in plan["forwardings"]}
    denied = {(p["src"], p["dest"]) for p in plan["denied_pairs"]}

    assert (_USER, _UNTRUSTED) in denied
    assert (_VPN, _UNTRUSTED) in denied
    assert (_USER, _UNTRUSTED) not in forwardings
    assert (_VPN, _UNTRUSTED) not in forwardings
    # The permit in the same row is not a forwarding either, but for an
    # unrelated reason: servers is hosted elsewhere, and this fixture declares
    # no interface that reaches it, so it is reported as unroutable rather than
    # guessed at.
    assert (_USER, _SERVERS) not in forwardings
    assert (_USER, _SERVERS) in {(p["src"], p["dest"]) for p in plan["unroutable_permits"]}


def test_an_unknown_action_is_not_a_grant():
    matrix = _fixture_matrix()
    matrix["rtr-slate"]["matrix"][_USER][_UNTRUSTED] = _cell("probably-fine", rule="R?")

    plan = _run(_fixture_model(), matrix, _resolution())["rtr-slate"]

    forwardings = {(f["src"], f["dest"]) for f in plan["forwardings"]}
    denied = {(p["src"], p["dest"]) for p in plan["denied_pairs"]}
    assert (_USER, _UNTRUSTED) not in forwardings
    assert (_USER, _UNTRUSTED) in denied


def test_a_remote_zones_own_row_produces_no_forwarding():
    """servers -> user is in the matrix, but servers is not local here."""
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    assert all(f["src"] != _SERVERS for f in plan["forwardings"])


def test_zone_input_policy_is_never_implicit():
    """Stock OpenWrt ships zone lan with input ACCEPT, exposing router services."""
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    for zone_ref, zone in plan["zones"].items():
        assert zone["input"] == "REJECT", zone_ref
        assert zone["forward"] == "REJECT", zone_ref


def test_input_services_are_derived_not_assumed():
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    # Resolver is the segment's own gateway, so the router answers DNS for it.
    assert plan["zones"][_USER]["input_services"] == ["dhcp", "dns"]
    # Country segment resolves through the tunnel against a public resolver,
    # so the router owes it DHCP only.
    assert plan["zones"][_VPN]["input_services"] == ["dhcp"]


def test_segments_of_another_enforcer_are_not_adopted():
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    cidrs = {segment["cidr"] for segment in plan["zones"][_USER]["segments"]}
    assert cidrs == {"10.77.1.0/24"}


def test_zone_without_a_local_segment_is_marked_remote():
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    assert plan["zones"][_SERVERS]["local"] is False
    assert plan["zones"][_SERVERS]["segments"] == []
    assert plan["zones"][_USER]["local"] is True


def test_interfaces_make_a_zone_local_without_any_segment():
    """The uplink zone owns no client prefix, only interfaces.

    uapi_firewall_zone has no device or subnet field - only `network` - so a
    bare interface is how the venue uplink joins a zone at all. Counting
    membership by address domain alone reported untrusted as remote.
    """
    model = _fixture_model()
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "uplink": {
                "management_path_immutable": True,
                "primary": {
                    "interface": "wwan",
                    "proto": "dhcp",
                    "trust_zone_ref": _UNTRUSTED,
                },
            }
        }
    }
    # A zone holding an uplink must now state whether it masquerades (E9918),
    # so the fixture answers. Added when that check landed - the fixture was
    # silent, which is exactly what the check refuses.
    model["instances"]["network"].append(
        _matrix_row([_egress(_UNTRUSTED)])
    )
    matrix = _fixture_matrix()
    matrix["rtr-slate"]["matrix"][_UNTRUSTED] = {_USER: _cell("deny", rule="R4")}

    plan = _run(model, matrix, _resolution())["rtr-slate"]

    zone = plan["zones"][_UNTRUSTED]
    assert zone["local"] is True
    assert zone["segments"] == []
    assert [iface["name"] for iface in zone["interfaces"]] == ["wwan"]
    # The uplink is not the management path - rtr-slate's uapi endpoint arrives
    # on the LAN bridge - so it carries no immutability claim of its own.
    assert zone["interfaces"][0]["immutable"] is False


def test_management_interface_carries_immutability_and_its_services():
    """E9904 and the lockout it prevents both depend on these two fields.

    The uapi request arrives on this interface, so a plan that rewrites it never
    returns a response. And because every zone defaults to input REJECT, the
    services that must survive an apply have to travel with the interface or
    the first apply locks the operator out of the device it was applied to.
    """
    model = _fixture_model()
    # No segments: the assertion is about what the interface alone contributes.
    model["instances"]["network"] = []
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "management": {
                "interface": "lan",
                "device": "br-lan",
                "address": "192.168.1.1/24",
                "proto": "static",
                "trust_zone_ref": _USER,
                "immutable": True,
                "endpoint_arrives_here": True,
                "input_services": ["ssh", "uapi"],
            }
        }
    }

    # A zone holding a live tunnel must state its egress treatment (E9920),
    # so the fixture answers for the zone the tunnel sits in.
    model["instances"]["network"].append(_matrix_row([_egress(_USER)]))

    plan = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]

    zone = plan["zones"][_USER]
    interface = next(item for item in zone["interfaces"] if item["name"] == "lan")
    assert interface["immutable"] is True
    assert interface["endpoint_arrives_here"] is True
    assert zone["input_services"] == ["ssh", "uapi"]


def test_an_interface_declaring_no_services_gets_none():
    """Nothing is inferred for interfaces, so an apply cannot publish a service
    nobody asked for."""
    model = _fixture_model()
    model["instances"]["network"] = []
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "wireguard": {"interfaces": [{"name": "wg-ru", "trust_zone_ref": _USER, "enabled": True}]}
        }
    }

    # A zone holding a live tunnel must state its egress treatment (E9920),
    # so the fixture answers for the zone the tunnel sits in.
    model["instances"]["network"].append(_matrix_row([_egress(_USER)]))

    plan = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]

    assert plan["zones"][_USER]["input_services"] == []


def test_parked_tunnel_interface_is_still_placed_in_its_zone():
    """The opposite of the wireless rule, and the asymmetry is in netifd.

    A `wifi-iface` with `disabled '1'` is dropped at parse time, so a parked
    SSID cannot affect anything and is skipped. A `config interface` with
    `disabled '1'` stays in uci and is merely left down - and it is rendered, so
    it is subject to the same zone-coverage rule as any other interface.

    Skipping it here produced exactly one silent failure: enabling a parked
    country tunnel brought it up into no zone at all, where the nftables base
    chain's policy drop swallows its traffic with nothing reporting why.
    """
    model = _fixture_model()
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "wireguard": {
                "interfaces": [
                    {"name": "wg-home", "trust_zone_ref": _USER, "enabled": True},
                    {"name": "wg-ru", "trust_zone_ref": _USER, "enabled": False},
                ]
            }
        }
    }

    # A zone holding a live tunnel must state its egress treatment (E9920),
    # so the fixture answers for the zone the tunnel sits in.
    model["instances"]["network"].append(_matrix_row([_egress(_USER)]))

    plan = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]

    interfaces = plan["zones"][_USER]["interfaces"]
    assert [iface["name"] for iface in interfaces] == ["wg-home", "wg-ru"]
    # Carried so a consumer can tell the two apart; naming a down interface in
    # a zone costs nothing, because fw4 resolves each network's devices and a
    # down one contributes none.
    assert {iface["name"]: iface["enabled"] for iface in interfaces} == {
        "wg-home": True,
        "wg-ru": False,
    }


def test_a_parked_tunnel_does_not_make_a_remote_zone_routable():
    """Zone membership and egress capability are separate questions.

    A parked tunnel belongs to its zone, but a permit must not lower to a rule
    pointing through an interface that is down - that would render a grant whose
    path does not exist.
    """
    model = _fixture_model()
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "wireguard": {
                "interfaces": [
                    {
                        "name": "wg-ru",
                        "trust_zone_ref": _USER,
                        "reaches_zone_refs": ["inst.trust_zone.servers"],
                        "enabled": False,
                    }
                ]
            }
        }
    }

    # A zone holding a live tunnel must state its egress treatment (E9920),
    # so the fixture answers for the zone the tunnel sits in.
    model["instances"]["network"].append(_matrix_row([_egress(_USER)]))

    plan = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]

    parked = next(
        iface for iface in plan["zones"][_USER]["interfaces"] if iface["name"] == "wg-ru"
    )
    assert parked["reaches_zone_refs"] == []


def test_no_terminal_drop_all_is_produced():
    """ADR 0110 section 4.4's mandatory final drop-all must not be ported.

    firewall4 zone chains are terminal and the nftables base chains carry
    policy drop, so an appended drop-all would land inside a zone chain ahead
    of the forwardings it is supposed to follow.
    """
    plan = _run(_fixture_model(), _fixture_matrix(), _resolution())["rtr-slate"]

    serialized = repr(plan).lower()
    for token in ("drop_all", "drop-all", "final_drop", "place_before"):
        assert token not in serialized


def _model_with_tunnel(reaches: list[str] | None = None) -> dict:
    """A device whose tunnel interface optionally declares what it reaches."""
    model = _fixture_model()
    iface = {"name": "wg-home", "trust_zone_ref": _EXIT_ZONE, "enabled": True}
    if reaches is not None:
        iface["reaches_zone_refs"] = reaches
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {"wireguard": {"interfaces": [iface]}}
    }
    # The tunnel's zone is an egress path, so it must state its treatment
    # (E9920): a tunnel is narrower than the client segments behind it, which
    # is exactly where clamping decides whether TCP works.
    model["instances"]["network"].append(_matrix_row([_egress(_EXIT_ZONE, masquerade=False)]))
    return model


_EXIT_ZONE = "inst.trust_zone.vpn_exit"


def _matrix_with_remote_permit(ports: dict | None = None) -> dict:
    matrix = _fixture_matrix()
    matrix["rtr-slate"]["zones"][_EXIT_ZONE] = {"security_level": 1, "isolated": True}
    matrix["rtr-slate"]["zones"][_SERVERS] = {
        "security_level": 4,
        "isolated": False,
        "cidrs": ["10.0.100.0/24"],
    }
    cell = _cell("accept", rule="R6")
    if ports:
        cell["ports"] = ports
    matrix["rtr-slate"]["matrix"][_USER] = {_SERVERS: cell}
    return matrix


def test_a_port_scoped_permit_becomes_a_rule_not_a_forwarding():
    """A forwarding is all-or-nothing between zones, so emitting one for a
    port-scoped permit would grant every port."""
    plan = _run(
        _model_with_tunnel([_SERVERS]),
        _matrix_with_remote_permit({"tcp": [80, 443]}),
        _resolution(),
    )["rtr-slate"]

    assert plan["forwardings"] == []
    assert len(plan["rules"]) == 1
    rule = plan["rules"][0]
    assert rule["ports"] == {"tcp": [80, 443]}


def test_a_remote_permit_leaves_through_the_declared_egress_zone():
    plan = _run(
        _model_with_tunnel([_SERVERS]),
        _matrix_with_remote_permit(),
        _resolution(),
    )["rtr-slate"]

    rule = plan["rules"][0]
    assert rule["src"] == _USER
    # The destination is the local zone the traffic leaves through, restricted
    # to the remote zone's prefixes - there is no servers zone on this device.
    assert rule["dest"] == _EXIT_ZONE
    assert rule["remote_zone"] == _SERVERS
    assert rule["dest_cidrs"] == ["10.0.100.0/24"]


def test_a_remote_permit_without_a_declared_egress_is_reported_not_guessed():
    """Guessing an interface here would invent a route the compiler cannot see."""
    plan = _run(
        _model_with_tunnel(None),
        _matrix_with_remote_permit({"tcp": [80]}),
        _resolution(),
    )["rtr-slate"]

    assert plan["rules"] == []
    assert plan["forwardings"] == []
    assert len(plan["unroutable_permits"]) == 1
    assert plan["unroutable_permits"][0]["missing"] == "egress interface"


# --------------------------------------------------------------------------
# E9918 / egress NAT
#
# Masquerading is a property of the pair (device, zone), not of the trust
# level, so it is authored on the matrix instance. The check requires the
# question to be ANSWERED for any zone holding an uplink - stating false is a
# legitimate answer for a routed uplink with a public prefix. What is refused
# is silence, because neither default is safe.
#
# The second failure is not hypothetical: before this existed, NAT on
# rtr-slate worked only because the STOCK wan zone was still present with
# masq=1, so the planned removal of the stock zones would have killed internet
# for the split and guest segments with nothing saying why.
# --------------------------------------------------------------------------


def _matrix_row(entries, instance="inst.security_matrix.rtr_slate"):
    return {"instance_id": instance, "instance_data": {"egress": entries}}


def _egress(zone, *, masquerade=True, mss_clamp=True):
    """One zone's egress block. Both facts are stated by default, because a
    zone holding an uplink or a tunnel must answer both (E9918, E9920); a test
    passes None for the fact it wants to leave unstated."""
    entry = {"zone_ref": zone}
    if masquerade is not None:
        entry["masquerade"] = masquerade
    if mss_clamp is not None:
        entry["mss_clamp"] = mss_clamp
    return entry


def _model_with_nat(entries, *, uplink_zone=_UNTRUSTED):
    model = _fixture_model()
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "uplink": {
                "primary": {
                    "interface": "wwan",
                    "proto": "dhcp",
                    "trust_zone_ref": uplink_zone,
                }
            }
        }
    }
    if entries is not None:
        model["instances"]["network"].append(_matrix_row(entries))
    return model


def test_masquerade_statements_reach_the_zone_plan():
    model = _model_with_nat(
        [
            _egress(_UNTRUSTED),
            _egress(_USER, masquerade=False),
        ]
    )

    result = _run(model, _fixture_matrix(), _resolution())
    zones = result["rtr-slate"]["zones"]

    assert zones[_UNTRUSTED]["masq"] is True
    assert zones[_USER]["masq"] is False


def test_an_unstated_zone_carries_none_not_a_default():
    """Tri-state on purpose: absent is a third thing, not false."""
    model = _model_with_nat([_egress(_UNTRUSTED)])

    zones = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]["zones"]

    assert zones[_USER]["masq"] is None


def test_an_uplink_zone_that_says_nothing_is_refused():
    model = _model_with_nat([_egress(_USER, masquerade=False)])

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9918" in result
    assert _UNTRUSTED in next(m for c, m in result.items() if c == "E9918")


def test_no_statement_at_all_is_refused_for_the_uplink_zone():
    assert "E9918" in _run_with_diagnostics(
        _model_with_nat(None), _fixture_matrix(), _resolution()
    )


def test_stating_false_is_a_valid_answer():
    """A routed uplink with a public prefix legitimately does not translate."""
    model = _model_with_nat([_egress(_UNTRUSTED, masquerade=False)])

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9918" not in result


def test_a_zone_without_an_uplink_needs_no_statement():
    """Only the zones where it decides reachability are required to answer."""
    model = _model_with_nat([_egress(_UNTRUSTED)])

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9918" not in result


def test_a_non_boolean_masquerade_does_not_count_as_an_answer():
    """`masquerade: "yes"` is not a statement; only a boolean is."""
    model = _model_with_nat([{"zone_ref": _UNTRUSTED, "masquerade": "yes", "mss_clamp": True}])

    assert "E9918" in _run_with_diagnostics(model, _fixture_matrix(), _resolution())


# --------------------------------------------------------------------------
# E9920 / MSS clamping
#
# The criterion differs from masquerade's on purpose. Masquerade is about
# leaving the device for someone else's network, so the uplink is what matters.
# Clamping is about the onward link being narrower than the client's segment,
# which is true of a tunnel too - and on the tunnel zone it never existed,
# while W9902's own text named it as the mitigation.
# --------------------------------------------------------------------------


def _model_with_live_tunnel(zone=_USER):
    model = _fixture_model()
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "wireguard": {"interfaces": [{"name": "wg_home", "trust_zone_ref": zone, "enabled": True}]}
        }
    }
    return model


def test_clamping_statements_reach_the_zone_plan():
    model = _model_with_live_tunnel()
    model["instances"]["network"].append(
        _matrix_row([_egress(_USER, masquerade=False, mss_clamp=True)])
    )

    zones = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]["zones"]

    assert zones[_USER]["mtu_fix"] is True


def test_a_tunnel_zone_that_says_nothing_about_clamping_is_refused():
    """The case that existed on the real device: a tunnel zone, no clamping."""
    model = _model_with_live_tunnel()
    model["instances"]["network"].append(
        _matrix_row([_egress(_USER, masquerade=False, mss_clamp=None)])
    )

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9920" in result
    assert "narrower than the client" in result["E9920"]


def test_a_tunnel_zone_needs_no_masquerade_statement():
    """The two criteria are independent: a tunnel is not an uplink."""
    model = _model_with_live_tunnel()
    model["instances"]["network"].append(
        _matrix_row([_egress(_USER, masquerade=None, mss_clamp=True)])
    )

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9918" not in result
    assert "E9920" not in result


def test_stating_no_clamping_is_a_valid_answer():
    model = _model_with_live_tunnel()
    model["instances"]["network"].append(
        _matrix_row([_egress(_USER, masquerade=False, mss_clamp=False)])
    )

    assert "E9920" not in _run_with_diagnostics(model, _fixture_matrix(), _resolution())


def test_a_parked_tunnel_does_not_make_its_zone_an_egress_path():
    """A disabled interface forwards nothing, so there is no treatment to
    decide - the same reasoning that excludes parked uplinks from E9919."""
    model = _fixture_model()
    model["instances"]["devices"][0]["instance_data"] = {
        "runtime_intent": {
            "wireguard": {
                "interfaces": [{"name": "wg_ru", "trust_zone_ref": _USER, "enabled": False}]
            }
        }
    }

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9920" not in result
    assert "E9918" not in result


def test_a_client_zone_needs_neither_statement():
    """Clamping and NAT are decided where the link narrows or leaves, not on
    every zone that happens to exist."""
    model = _model_with_live_tunnel(zone="inst.trust_zone.vpn_exit")
    model["instances"]["network"].append(
        _matrix_row([_egress("inst.trust_zone.vpn_exit", masquerade=False)])
    )

    result = _run_with_diagnostics(model, _fixture_matrix(), _resolution())

    assert "E9920" not in result

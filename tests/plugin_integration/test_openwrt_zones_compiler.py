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
    # The permit in the same row still comes through.
    assert (_USER, _SERVERS) in forwardings


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

    plan = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]

    assert plan["zones"][_USER]["input_services"] == []


def test_parked_tunnel_interface_is_not_placed_in_a_zone():
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

    plan = _run(model, _fixture_matrix(), _resolution())["rtr-slate"]

    names = [iface["name"] for iface in plan["zones"][_USER]["interfaces"]]
    assert names == ["wg-home"]


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

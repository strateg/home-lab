#!/usr/bin/env python3
# ADR: 0106, 0110, 0118, 0119
"""Tests for the OpenWrt interfaces compiler.

The arithmetic here is the point. Every lowering this plugin performs exists
because the provider's schema will not take the authored shape, and each one
fails quietly if it is wrong: a DHCP pool one address short, a netmask written
where a prefix length belongs, a channel the Number-typed attribute cannot
carry. So the pure functions are tested directly against their boundaries, and
the plugin is then driven end to end over a model shaped like the real one.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test  # noqa: E402

COMPILER_ID = "object.openwrt.compiler.interfaces"
ZONES_ID = "object.openwrt.compiler.zones"
MODEL_ID = "base.compiler.effective_model"

_USER = "inst.trust_zone.user"
_MGMT = "inst.trust_zone.management"
_VPN_EXIT = "inst.trust_zone.vpn_exit"


def _load(module_name: str, relative: str):
    path = V5_ROOT / "topology" / "object-modules" / "openwrt" / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load(
    "test_openwrt_interfaces_compiler_module",
    "plugins/compilers/interfaces_compiler.py",
)


# ---------------------------------------------------------------------------
# DHCP pool: uapi_dhcp_server has start and limit, no end
# ---------------------------------------------------------------------------


def test_pool_lowers_to_offset_and_inclusive_count():
    """100 through 200 inclusive is 101 addresses, not 100.

    `start` is an offset from the network address and `limit` is a count. The
    off-by-one is invisible on the device - the pool is simply one address
    short - which is why this is arithmetic in a compiler and not an expression
    in a template.
    """
    assert MODULE._dhcp_pool("10.77.1.0/24", "10.77.1.100-10.77.1.200") == (100, 101)


def test_single_address_pool_is_a_limit_of_one():
    assert MODULE._dhcp_pool("10.77.1.0/24", "10.77.1.50-10.77.1.50") == (50, 1)


def test_pool_offset_is_measured_from_the_network_address():
    """A /25 starting at .128 must not produce the offset of a /24."""
    assert MODULE._dhcp_pool("10.77.1.128/25", "10.77.1.140-10.77.1.150") == (12, 11)


def test_pool_outside_the_prefix_is_refused():
    result = MODULE._dhcp_pool("10.77.1.0/24", "10.77.2.100-10.77.2.200")

    assert isinstance(result, str)
    assert "not inside" in result


def test_pool_with_one_endpoint_outside_the_prefix_is_refused():
    result = MODULE._dhcp_pool("10.77.1.0/24", "10.77.1.200-10.77.2.10")

    assert isinstance(result, str)


def test_backwards_pool_is_refused():
    result = MODULE._dhcp_pool("10.77.1.0/24", "10.77.1.200-10.77.1.100")

    assert isinstance(result, str)
    assert "backwards" in result


def test_unparseable_pool_is_refused():
    assert isinstance(MODULE._dhcp_pool("10.77.1.0/24", "not-an-address"), str)
    assert isinstance(MODULE._dhcp_pool("10.77.1.0/24", "10.77.1.100"), str)
    assert isinstance(MODULE._dhcp_pool("nonsense", "10.77.1.100-10.77.1.200"), str)


# ---------------------------------------------------------------------------
# Address split: ipaddrs is a list, netmask a scalar, ipaddr read-only
# ---------------------------------------------------------------------------


def test_address_splits_into_host_and_mask():
    assert MODULE._split_address("192.168.1.1/24") == ("192.168.1.1", "255.255.255.0")


def test_host_route_tunnel_address_keeps_its_own_mask():
    """A /32 is normal on WireGuard and must not be widened to the peer's view."""
    assert MODULE._split_address("10.100.1.10/32") == ("10.100.1.10", "255.255.255.255")


def test_address_without_a_prefix_is_not_split():
    assert MODULE._split_address("192.168.1.1") is None
    assert MODULE._split_address(None) is None


def test_router_address_takes_the_gateway_with_the_segment_mask():
    assert MODULE._router_address("10.77.1.0/24", "10.77.1.1") == ("10.77.1.1", "255.255.255.0")


def test_gateway_outside_its_segment_is_refused():
    """Otherwise the router would be given an address off its own segment."""
    assert MODULE._router_address("10.77.1.0/24", "10.77.9.1") is None


# ---------------------------------------------------------------------------
# Channel: the attribute is typed Number, so `auto` is not renderable
# ---------------------------------------------------------------------------


def test_every_auto_spelling_lowers_to_zero():
    """netifd's `_wdev_prepare_channel` matches `""|0|auto` identically."""
    for spelling in ("auto", "AUTO", "", "0", 0, None):
        assert MODULE._auto_channel(spelling) == 0, spelling


def test_pinned_channel_passes_through():
    assert MODULE._auto_channel(36) == 36
    assert MODULE._auto_channel("36") == 36


def test_nonsense_channel_is_not_silently_zero():
    """Lowering junk to 0 would turn a typo into a working auto-channel radio."""
    assert MODULE._auto_channel("thirty-six") is None
    assert MODULE._auto_channel(True) is None


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


def _zone_plan(*, dhcp_range="10.77.1.100-10.77.1.200", mtu=1420):
    return {
        "rtr-slate": {
            "scope_ids": ["inst.security_matrix.rtr_slate"],
            "zones": {
                _USER: {
                    "local": True,
                    "segments": [
                        {
                            "instance_id": "inst.vlan.slate_home",
                            "interface": "slate_home",
                            "cidr": "10.77.1.0/24",
                            "gateway": "10.77.1.1",
                            "mtu": mtu,
                            "vlan_id": 101,
                            "dhcp_range": dhcp_range,
                            "dns_servers": ["10.77.1.1"],
                        }
                    ],
                    "interfaces": [],
                },
                _MGMT: {"local": True, "segments": [], "interfaces": [{"name": "lan"}]},
                _VPN_EXIT: {"local": True, "segments": [], "interfaces": [{"name": "wg-home"}]},
            },
        }
    }


def _model(*, wireless=None, wireguard_mtu=1420):
    intent = {
        "management": {
            "interface": "lan",
            "device": "br-lan",
            "bridge_ports": ["lan1", "lan2"],
            "address": "192.168.1.1/24",
            "proto": "static",
            "trust_zone_ref": _MGMT,
            "immutable": True,
            "endpoint_arrives_here": True,
            "input_services": ["ssh", "uapi"],
        },
        "uplink": {
            "primary": {
                "interface": "wwan",
                "proto": "dhcp",
                "wireless_iface": "uplink",
                "trust_zone_ref": "inst.trust_zone.untrusted",
            },
            "wired": {
                "interface": "wan",
                "device": "wan",
                "proto": "dhcp",
                "trust_zone_ref": "inst.trust_zone.untrusted",
                "enabled": True,
            },
        },
        "wireguard": {
            "interfaces": [
                {
                    "name": "wg-home",
                    "tunnel_ref": "inst.tunnel.wg-home-to-oci",
                    "tunnel_ip": "10.100.0.4/24",
                    "mtu": wireguard_mtu,
                    "advertises": ["10.77.1.0/24"],
                    "trust_zone_ref": _VPN_EXIT,
                    "enabled": True,
                }
            ]
        },
        "services": {"packages": ["iwinfo", "kmod-wireguard"]},
    }
    if wireless is not None:
        intent["wireless"] = wireless
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-slate",
                    "instance": {"derived_capabilities": ["cap.os.openwrt"]},
                    "object": {},
                    "instance_data": {"runtime_intent": intent},
                }
            ],
            "network": [],
        }
    }


def _wireless(*, channel="auto", network_ref="inst.vlan.slate_home", parked=False):
    return {
        "radios": {
            "radio0": {"band": "5g", "channel": 36, "htmode": "HE80", "country": "EE"},
            "radio1": {"band": "2g", "channel": channel, "htmode": "HT20", "country": "EE"},
        },
        "interfaces": [
            {
                "name": "ap_home",
                "device": "radio0",
                "mode": "ap",
                "ssid": "Slate-Home",
                "encryption": "sae-mixed",
                "network_ref": network_ref,
                "enabled": not parked,
            },
            {
                "name": "uplink",
                "device": "radio1",
                "mode": "sta",
                "network": "wwan",
                "enabled": True,
            },
        ],
    }


def _run(plan, model):
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, ZONES_ID, "openwrt_zones", plan)
    publish_for_test(ctx, MODEL_ID, "effective_model_candidate", model)
    plugin = MODULE.OpenwrtInterfacesCompiler(COMPILER_ID)
    return run_plugin_for_test(
        plugin, ctx, Stage.COMPILE, consumes_keys={ZONES_ID, MODEL_ID}
    )


def _codes(result) -> list[str]:
    return [d.code for d in result.diagnostics]


def _plan_of(result):
    return result.output_data["openwrt_interfaces"]["rtr-slate"]


def test_management_lowers_to_an_interface_and_a_bridge_device():
    """Bridge membership is uapi_network_device.ports, not an interface field."""
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    lan = next(item for item in entry["interfaces"] if item["id"] == "lan")
    assert lan["proto"] == "static"
    assert lan["ipaddrs"] == ["192.168.1.1"]
    assert lan["netmask"] == "255.255.255.0"
    # Carried so the generator can refuse to write proto/ipaddrs here rather
    # than trusting a flag it cannot see (E9904).
    assert lan["immutable"] is True
    assert lan["endpoint_arrives_here"] is True

    device = next(item for item in entry["devices"] if item["id"] == "br-lan")
    assert device["type"] == "bridge"
    assert device["ports"] == ["lan1", "lan2"]


def test_segment_interface_takes_the_name_the_zone_plan_derived():
    """One producer of the section name, so firewall_zone.network cannot diverge."""
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    segment = next(item for item in entry["interfaces"] if item["kind"] == "segment")
    assert segment["id"] == "slate_home"
    assert segment["ipaddrs"] == ["10.77.1.1"]
    assert segment["netmask"] == "255.255.255.0"
    assert segment["mtu"] == 1420


def test_radio_uplink_gets_no_device():
    """netifd attaches the station by the wifi-iface's network, not by netdev.

    Naming a device would claim an interface that does not exist until the
    station associates.
    """
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    wwan = next(item for item in entry["interfaces"] if item["id"] == "wwan")
    assert wwan["device"] is None
    assert wwan["wireless_iface"] == "uplink"


def test_wireguard_interface_carries_a_key_reference_not_a_key():
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    tunnel = next(item for item in entry["interfaces"] if item["id"] == "wg-home")
    assert tunnel["proto"] == "wireguard"
    assert tunnel["ipaddrs"] == ["10.100.0.4"]
    assert "private_key_ref" in tunnel
    assert "private_key" not in tunnel


def test_wireguard_peers_are_named_as_deferred_not_silently_absent():
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    assert any("wireguard_peers" in item for item in entry["deferred"])


def test_auto_channel_is_rendered_as_zero():
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless(channel="auto"))))

    radio1 = next(item for item in entry["wireless_devices"] if item["id"] == "radio1")
    assert radio1["channel"] == 0
    assert radio1["type"] == "mac80211"
    assert radio1["country"] == "EE"


def test_wifi_iface_network_ref_resolves_to_the_uci_section_name():
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    ap = next(item for item in entry["wireless_interfaces"] if item["id"] == "ap_home")
    # Scalar, per the schema: one SSID, one network.
    assert ap["network"] == "slate_home"
    assert isinstance(ap["network"], str)


def test_parked_wifi_iface_is_rendered_disabled_not_omitted():
    """An unmanaged parked AP can be switched on by hand and never show as drift."""
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless(parked=True))))

    ap = next(item for item in entry["wireless_interfaces"] if item["id"] == "ap_home")
    assert ap["disabled"] is True
    assert entry["parked_wireless"] == 1


def test_dhcp_pool_is_lowered_for_each_segment():
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    pool = next(item for item in entry["dhcp_servers"] if item["interface"] == "slate_home")
    assert (pool["start"], pool["limit"]) == (100, 101)
    assert pool["ignore"] is False


def test_segment_without_a_pool_is_explicitly_ignored():
    """Absent is not the same as unserved; dnsmasq must be told."""
    entry = _plan_of(_run(_zone_plan(dhcp_range=None), _model(wireless=_wireless())))

    pool = next(item for item in entry["dhcp_servers"] if item["interface"] == "slate_home")
    assert pool["ignore"] is True
    assert "start" not in pool


def test_unexpressable_pool_raises_e9911():
    result = _run(_zone_plan(dhcp_range="10.77.9.10-10.77.9.20"), _model(wireless=_wireless()))

    assert "E9911" in _codes(result)
    message = next(d.message for d in result.diagnostics if d.code == "E9911")
    assert "no end" in message


def test_wifi_iface_naming_an_unknown_network_raises_e9912():
    result = _run(_zone_plan(), _model(wireless=_wireless(network_ref="inst.vlan.nonexistent")))

    assert "E9912" in _codes(result)


def test_segment_mtu_above_its_tunnel_raises_w9902():
    """The link is the tunnel's `advertises` list, which names the prefix."""
    result = _run(_zone_plan(mtu=1500), _model(wireless=_wireless(), wireguard_mtu=1420))

    assert "W9902" in _codes(result)
    message = next(d.message for d in result.diagnostics if d.code == "W9902")
    assert "mtu_fix clamps TCP MSS only" in message


def test_segment_mtu_equal_to_its_tunnel_is_fine():
    """A WireGuard interface's MTU *is* the inner payload capacity."""
    result = _run(_zone_plan(mtu=1420), _model(wireless=_wireless(), wireguard_mtu=1420))

    assert "W9902" not in _codes(result)


def test_a_device_without_the_openwrt_capability_is_not_lowered():
    """Selection is by declared capability, never by name (ENFORCER-AXIS V-14)."""
    model = _model(wireless=_wireless())
    model["instances"]["devices"][0]["instance"]["derived_capabilities"] = ["cap.os.debian"]

    result = _run(_zone_plan(), model)

    assert result.output_data["openwrt_interfaces"] == {}


def test_the_summary_reports_what_was_lowered():
    result = _run(_zone_plan(), _model(wireless=_wireless()))

    assert "I9904" in _codes(result)
    message = next(d.message for d in result.diagnostics if d.code == "I9904")
    assert "wireguard_peers" in message


def test_no_wireless_intent_lowers_the_rest_without_failing():
    """A device may legitimately have no radios."""
    result = _run(_zone_plan(), _model(wireless=None))

    entry = _plan_of(result)
    assert entry["wireless_devices"] == []
    assert entry["wireless_interfaces"] == []
    assert entry["interfaces"]
    assert not [code for code in _codes(result) if code.startswith("E")]


# ---------------------------------------------------------------------------
# Adoption ledger
#
# Authored rather than inferred because both ways of being wrong are loud: the
# provider refuses duplicate-name creation with 422 conflict, so a section
# missing from the ledger fails the first apply, and a section listed that does
# not exist fails the import. Neither is drift.
# ---------------------------------------------------------------------------


def _with_adoption(sections, *, reconciled=False):
    model = _model(wireless=_wireless())
    model["instances"]["devices"][0]["instance_data"]["runtime_intent"]["adoption"] = {
        "reconciled_against_device": reconciled,
        "sections": sections,
    }
    return model


def test_ledger_entries_pair_with_the_resources_they_adopt():
    result = _run(
        _zone_plan(),
        _with_adoption(
            [
                {"resource": "uapi_network_interface", "id": "lan"},
                {"resource": "uapi_network_device", "id": "br-lan"},
                {"resource": "uapi_wireless_device", "id": "radio0"},
            ]
        ),
    )

    assert "E9913" not in _codes(result)
    adoption = _plan_of(result)["adoption"]
    assert [(item["resource"], item["id"]) for item in adoption] == [
        ("uapi_network_device", "br-lan"),
        ("uapi_network_interface", "lan"),
        ("uapi_wireless_device", "radio0"),
    ]


def test_anonymous_sections_are_identified_from_their_name():
    """Derived, never authored: an author asserting "this one is named" is an
    assertion that can be wrong, while the uci convention is a fact about the
    string. uci names anonymous sections `cfg` plus hex digits.
    """
    plan = _zone_plan()
    model = _with_adoption([{"resource": "uapi_wireless_interface", "id": "ap_home"}])
    entry = _plan_of(_run(plan, model))

    assert entry["adoption"][0]["anonymous"] is False

    compiler = MODULE.OpenwrtInterfacesCompiler(COMPILER_ID)
    assert compiler._ANONYMOUS_SECTION.match("cfg030f15")
    assert compiler._ANONYMOUS_SECTION.match("cfg0f1532ab")
    assert not compiler._ANONYMOUS_SECTION.match("lan")
    assert not compiler._ANONYMOUS_SECTION.match("cfg")
    # A real section may legitimately start with cfg without being anonymous.
    assert not compiler._ANONYMOUS_SECTION.match("cfgzzzzzz")


def test_a_ledger_entry_for_an_unrendered_resource_is_refused():
    """Terraform refuses an import block whose target does not exist, and
    refuses it for the whole root, so one stale entry costs every plan."""
    result = _run(
        _zone_plan(),
        _with_adoption([{"resource": "uapi_network_interface", "id": "does-not-exist"}]),
    )

    assert "E9913" in _codes(result)
    assert _plan_of(result)["adoption"] == []


def test_a_ledger_entry_naming_the_wrong_resource_kind_is_refused():
    """`lan` exists as an interface, not as a wireless device."""
    result = _run(
        _zone_plan(),
        _with_adoption([{"resource": "uapi_wireless_device", "id": "lan"}]),
    )

    assert "E9913" in _codes(result)


def test_an_unreconciled_ledger_is_reported_as_such():
    """The ledger was authored from board support files, not read off a router
    that has been configured by hand."""
    result = _run(_zone_plan(), _with_adoption([], reconciled=False))

    assert _plan_of(result)["adoption_reconciled"] is False
    assert "ledger NOT reconciled" in next(d.message for d in result.diagnostics if d.code == "I9904")


def test_a_reconciled_ledger_is_not_flagged():
    result = _run(_zone_plan(), _with_adoption([], reconciled=True))

    assert _plan_of(result)["adoption_reconciled"] is True
    assert "ledger NOT reconciled" not in next(
        d.message for d in result.diagnostics if d.code == "I9904"
    )


def test_no_ledger_means_nothing_to_adopt():
    """A fresh device creates every section; adoption is not mandatory."""
    entry = _plan_of(_run(_zone_plan(), _model(wireless=_wireless())))

    assert entry["adoption"] == []
    assert entry["adoption_reconciled"] is False


def test_an_anonymous_ledger_entry_is_passed_through_not_refused():
    """E9913 is about a *named* target that is not rendered.

    An anonymous section's ledger id is the name the DEVICE gave it
    (`cfg030f15`), while the resource's id is what this topology wants it
    called. Those differ by construction, so an anonymous entry cannot be
    paired with a rendered resource by id - and must not be, because uapi would
    rename it to a ULID rather than to our name. It is passed through flagged,
    for W9903 to report at render time.
    """
    result = _run(
        _zone_plan(),
        _with_adoption([{"resource": "uapi_wireless_interface", "id": "cfg030f15"}]),
    )

    assert "E9913" not in _codes(result)
    adoption = _plan_of(result)["adoption"]
    assert adoption == [
        {"resource": "uapi_wireless_interface", "id": "cfg030f15", "anonymous": True}
    ]


def test_an_anonymous_entry_for_an_unknown_resource_kind_is_still_refused():
    """Being anonymous excuses the id, not a misspelled resource type."""
    result = _run(
        _zone_plan(),
        _with_adoption([{"resource": "uapi_not_a_resource", "id": "cfg030f15"}]),
    )

    assert "E9913" in _codes(result)

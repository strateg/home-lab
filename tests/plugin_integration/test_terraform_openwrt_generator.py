#!/usr/bin/env python3
# ADR: 0110, 0119
"""Tests for the OpenWrt Terraform generator's render decisions.

Exercises `_build_render_context`, which is where every decision about what
reaches Terraform lives. Rendering itself is Jinja over that context, so the
decisions are what is worth pinning: a denial that became a resource, or a
port-scoped permit widened into a forwarding, would both be security changes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

GENERATOR_ID = "object.openwrt.generator.terraform"

_UNTRUSTED = "inst.trust_zone.untrusted"
_USER = "inst.trust_zone.user"
_EXIT = "inst.trust_zone.vpn_exit"
_SERVERS = "inst.trust_zone.servers"


def _load():
    path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "openwrt"
        / "plugins"
        / "generators"
        / "terraform_openwrt_generator.py"
    )
    spec = importlib.util.spec_from_file_location("test_terraform_openwrt_generator_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _plan(**overrides) -> dict:
    plan = {
        "scope_ids": ["inst.security_matrix.rtr_slate"],
        "zones": {
            _USER: {
                "local": True,
                "segments": [{"instance_id": "inst.vlan.slate_home", "interface": "slate_home"}],
                "interfaces": [],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": ["dhcp", "dns"],
            },
            _EXIT: {
                "local": True,
                "segments": [],
                "interfaces": [{"name": "wg-home", "kind": "wireguard"}],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": [],
            },
            _UNTRUSTED: {
                "local": True,
                "segments": [],
                "interfaces": [{"name": "wwan", "kind": "uplink"}],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": [],
            },
            # Known about, hosted elsewhere: reached through a tunnel.
            _SERVERS: {
                "local": False,
                "segments": [],
                "interfaces": [],
                "input": "REJECT",
                "forward": "REJECT",
                "output": "ACCEPT",
                "input_services": [],
            },
        },
        "forwardings": [
            {"src": _USER, "dest": _EXIT},
        ],
        "denied_pairs": [
            {"src": _USER, "dest": _UNTRUSTED, "rule": "R6", "reason": "kill switch", "log": True}
        ],
    }
    plan.update(overrides)
    return plan


def _context(plan: dict):
    generator = MODULE.TerraformOpenwrtGenerator(GENERATOR_ID)
    return generator._build_render_context("rtr-slate", plan)


def test_only_local_zones_become_resources():
    """uapi_firewall_zone takes a network list, and a remote zone has nothing
    local to put in it."""
    context, _ = _context(_plan())

    rendered = {zone["zone_ref"] for zone in context["zones"]}
    assert _SERVERS not in rendered
    assert {_USER, _EXIT, _UNTRUSTED} <= rendered


def test_zone_networks_use_interface_names_not_instance_ids():
    """The network list names config interface sections; an instance id there
    would reference a section that does not exist on the device."""
    context, _ = _context(_plan())

    user = next(zone for zone in context["zones"] if zone["zone_ref"] == _USER)
    assert user["networks"] == ["slate_home"]
    exit_zone = next(zone for zone in context["zones"] if zone["zone_ref"] == _EXIT)
    assert exit_zone["networks"] == ["wg-home"]


def test_denials_never_become_resources():
    """The kill switch is an omission on this backend."""
    context, _ = _context(_plan())

    emitted = {(fwd["src"], fwd["dest"]) for fwd in context["forwardings"]}
    assert ("user", "untrusted") not in emitted
    # The denial still travels into the render context so the template can list
    # it as a reviewable comment.
    assert context["denied_pairs"]


def test_remote_destination_permit_is_deferred_not_dropped():
    plan = _plan(forwardings=[{"src": _USER, "dest": _SERVERS}])

    context, deferred = _context(plan)

    assert context["forwardings"] == []
    assert deferred["remote_dest"] == 1


def test_port_scoped_permit_is_deferred_not_widened():
    """A forwarding is all-or-nothing between zones, so emitting one for a
    port-scoped permit would grant every port."""
    plan = _plan(forwardings=[{"src": _USER, "dest": _EXIT, "ports": {"tcp": [80, 443]}}])

    context, deferred = _context(plan)

    assert context["forwardings"] == []
    assert deferred["port_scoped"] == 1


def test_a_permit_from_a_remote_source_is_ignored():
    """This enforcer filters traffic leaving its own segments, not traffic
    between two zones it merely knows about."""
    plan = _plan(forwardings=[{"src": _SERVERS, "dest": _USER}])

    context, deferred = _context(plan)

    assert context["forwardings"] == []
    assert deferred == {"remote_dest": 0, "port_scoped": 0}


def test_forwardings_carry_resource_labels_for_ordering():
    """Referencing the zone resources rather than literal names is what makes
    Terraform create the zones before the forwardings."""
    context, _ = _context(_plan())

    fwd = context["forwardings"][0]
    assert fwd["src_label"] == "user"
    assert fwd["dest_label"] == "vpn_exit"


def test_zone_policies_are_carried_verbatim():
    context, _ = _context(_plan())

    for zone in context["zones"]:
        assert zone["input"] == "REJECT"
        assert zone["forward"] == "REJECT"
        assert zone["output"] == "ACCEPT"

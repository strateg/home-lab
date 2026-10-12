#!/usr/bin/env python3
# ADR: 0110, 0119
"""Tests for the OpenWrt interface/management-path validator.

Both codes guard failures that present as something other than a firewall
problem: an unzoned interface looks like dead hardware, and an unprotected
management path looks fine right up to the apply that ends the session.
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

VALIDATOR_ID = "object.openwrt.validator_json.interfaces"
MODEL_ID = "base.compiler.effective_model"
ZONES_ID = "object.openwrt.compiler.zones"

_MGMT = "inst.trust_zone.management"
_UNTRUSTED = "inst.trust_zone.untrusted"
_EXIT = "inst.trust_zone.vpn_exit"


def _load():
    path = (
        V5_ROOT / "topology" / "object-modules" / "openwrt" / "plugins" / "validators" / "interfaces_validator.py"
    )
    spec = importlib.util.spec_from_file_location("test_openwrt_interfaces_validator_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _intent(**overrides) -> dict:
    """A well-formed intent: one uplink, one management path, one tunnel."""
    intent = {
        "uplink": {
            "primary": {"interface": "wwan", "proto": "dhcp", "trust_zone_ref": _UNTRUSTED},
        },
        "management": {
            "interface": "lan",
            "device": "br-lan",
            "trust_zone_ref": _MGMT,
            "immutable": True,
            "endpoint_arrives_here": True,
            "input_services": ["ssh", "uapi"],
        },
        "wireguard": {
            "interfaces": [{"name": "wg-home", "trust_zone_ref": _EXIT, "enabled": True}],
        },
    }
    intent.update(overrides)
    return intent


def _zones(**overrides) -> dict:
    zones = {
        _UNTRUSTED: {"input": "REJECT", "input_services": []},
        _MGMT: {"input": "REJECT", "input_services": ["ssh", "uapi"]},
        _EXIT: {"input": "REJECT", "input_services": []},
    }
    zones.update(overrides)
    return zones


def _run(intent: dict | None, zones: dict | None, *, os_cap: str = "cap.os.openwrt"):
    model = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-slate",
                    "instance": {"derived_capabilities": [os_cap]},
                    "object": {},
                    "instance_data": {} if intent is None else {"runtime_intent": intent},
                }
            ]
        }
    }
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, MODEL_ID, "effective_model_candidate", model)
    if zones is not None:
        publish_for_test(ctx, ZONES_ID, "openwrt_zones", {"rtr-slate": {"zones": zones}})

    plugin = MODULE.OpenwrtInterfacesValidator(VALIDATOR_ID)
    result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE, consumes_keys={MODEL_ID, ZONES_ID})

    severities = {d.severity for d in result.diagnostics}
    expected = PluginStatus.FAILED if "error" in severities else PluginStatus.SUCCESS
    assert result.status == expected

    return [d.code for d in result.diagnostics]


def test_well_formed_intent_raises_nothing():
    assert _run(_intent(), _zones()) == []


# --------------------------------------------------------------------------
# E9905 - interface-to-zone coverage
# --------------------------------------------------------------------------


def test_interface_without_a_zone_is_refused():
    intent = _intent()
    del intent["wireguard"]["interfaces"][0]["trust_zone_ref"]

    assert "E9905" in _run(intent, _zones())


def test_interface_naming_an_unrendered_zone_is_refused():
    intent = _intent()
    intent["wireguard"]["interfaces"][0]["trust_zone_ref"] = "inst.trust_zone.nowhere"

    assert "E9905" in _run(intent, _zones())


def test_the_same_interface_in_two_zones_is_refused():
    intent = _intent()
    intent["wireguard"]["interfaces"].append(
        {"name": "wwan", "trust_zone_ref": _EXIT, "enabled": True}
    )

    assert "E9905" in _run(intent, _zones())


def test_a_parked_interface_still_needs_a_zone():
    """Parked is not exempt: a `config interface` with `disabled '1'` stays in
    uci and is rendered, unlike a parked `wifi-iface`, which netifd drops at
    parse time. Exempting it let a parked tunnel be enabled later and come up
    into no zone, where the base chain's policy drop swallows its traffic.
    """
    intent = _intent()
    intent["wireguard"]["interfaces"].append({"name": "wg-ru", "enabled": False})

    assert "E9905" in _run(intent, _zones())


def test_a_parked_interface_with_a_rendered_zone_is_accepted():
    intent = _intent()
    intent["wireguard"]["interfaces"].append(
        {"name": "wg-ru", "trust_zone_ref": _EXIT, "enabled": False}
    )

    assert _run(intent, _zones()) == []


def test_coverage_is_not_claimed_when_no_plan_exists():
    """Without a lowered plan there is no zone set to check membership against,
    so only the missing-ref case is decidable."""
    intent = _intent()
    intent["wireguard"]["interfaces"][0]["trust_zone_ref"] = "inst.trust_zone.nowhere"

    assert _run(intent, None) == []


# --------------------------------------------------------------------------
# E9904 - management path protection
# --------------------------------------------------------------------------


def test_no_endpoint_declaration_is_refused():
    intent = _intent()
    intent["management"]["endpoint_arrives_here"] = False

    assert "E9904" in _run(intent, _zones())


def test_two_endpoint_declarations_are_refused():
    intent = _intent()
    intent["uplink"]["primary"]["endpoint_arrives_here"] = True
    intent["uplink"]["primary"]["immutable"] = True

    assert "E9904" in _run(intent, _zones())


def test_endpoint_not_marked_immutable_is_refused():
    intent = _intent()
    intent["management"]["immutable"] = False

    assert "E9904" in _run(intent, _zones())


def test_management_zone_without_input_services_is_refused():
    """The lockout this code exists for: every zone defaults to input REJECT."""
    assert "E9904" in _run(_intent(), _zones(**{_MGMT: {"input": "REJECT", "input_services": []}}))


def test_management_zone_services_are_read_from_the_plan_not_the_intent():
    """The plan is what gets rendered, so the plan is what must keep the path open."""
    intent = _intent()
    intent["management"]["input_services"] = ["ssh", "uapi"]

    codes = _run(intent, _zones(**{_MGMT: {"input": "REJECT", "input_services": []}}))

    assert "E9904" in codes


# --------------------------------------------------------------------------
# Scope and robustness
# --------------------------------------------------------------------------


def test_non_openwrt_device_is_ignored():
    assert _run(_intent(), _zones(), os_cap="cap.os.routeros") == []


def test_device_without_intent_is_ignored():
    assert _run(None, _zones()) == []


def test_malformed_intent_does_not_crash():
    assert _run({"uplink": "nonsense", "wireguard": "nonsense"}, _zones()) == ["E9904"]

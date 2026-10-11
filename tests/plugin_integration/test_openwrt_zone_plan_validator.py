#!/usr/bin/env python3
# ADR: 0110, 0118, 0119
"""Tests for the OpenWrt zone-plan validator.

A validator that only ever sees good data is a claim nobody checks, so every
test here feeds it a violation and asserts the specific code fires. The last
test closes the loop by piping the real compiler's output through it.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test  # noqa: E402

VALIDATOR_ID = "object.openwrt.validator_json.zone_plan"
COMPILER_ID = "object.openwrt.compiler.zones"

_UNTRUSTED = "inst.trust_zone.untrusted"
_USER = "inst.trust_zone.user"


def _load(module_name: str, relative: str):
    path = V5_ROOT / "topology" / "object-modules" / "openwrt" / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR_MODULE = _load("test_openwrt_zone_plan_validator_module", "plugins/validators/zone_plan_validator.py")
COMPILER_MODULE = _load("test_openwrt_zones_compiler_for_validator", "plugins/compilers/zones_compiler.py")


def _faithful_plan() -> dict:
    return {
        "rtr-slate": {
            "scope_ids": ["inst.security_matrix.rtr_slate"],
            "zones": {
                _USER: {
                    "local": True,
                    "segments": [{"cidr": "10.77.1.0/24"}],
                    "input": "REJECT",
                    "forward": "REJECT",
                    "output": "ACCEPT",
                    "input_services": ["dhcp", "dns"],
                },
                _UNTRUSTED: {
                    "local": False,
                    "segments": [],
                    "input": "REJECT",
                    "forward": "REJECT",
                    "output": "ACCEPT",
                    "input_services": [],
                },
            },
            "forwardings": [{"src": _USER, "dest": "inst.trust_zone.servers"}],
            "denied_pairs": [
                {"src": _USER, "dest": _UNTRUSTED, "rule": "R6", "reason": "kill switch", "log": True}
            ],
        }
    }


def _run_validator(plans):
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    if plans is not None:
        publish_for_test(ctx, COMPILER_ID, "openwrt_zones", plans)
    plugin = VALIDATOR_MODULE.OpenwrtZonePlanValidator(VALIDATOR_ID)
    result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE, consumes_keys={COMPILER_ID})
    return result


def _codes(result) -> list[str]:
    return [d.code for d in result.diagnostics]


def test_faithful_plan_raises_nothing():
    result = _run_validator(_faithful_plan())

    assert _codes(result) == []


def test_denied_pair_emitted_as_forwarding_is_refused():
    """The kill switch failing silently is the whole reason this code exists."""
    plans = _faithful_plan()
    plans["rtr-slate"]["forwardings"].append({"src": _USER, "dest": _UNTRUSTED})

    result = _run_validator(plans)

    assert "E9906" in _codes(result)
    message = next(d.message for d in result.diagnostics if d.code == "E9906")
    assert _USER in message and _UNTRUSTED in message
    # The matrix's own reason travels with the diagnostic, so the operator sees
    # which rule was overridden rather than just a pair of zone names.
    assert "kill switch" in message


def test_missing_input_policy_is_refused():
    plans = _faithful_plan()
    del plans["rtr-slate"]["zones"][_USER]["input"]

    result = _run_validator(plans)

    assert "E9907" in _codes(result)


def test_input_accept_is_refused():
    plans = _faithful_plan()
    plans["rtr-slate"]["zones"][_USER]["input"] = "ACCEPT"

    result = _run_validator(plans)

    assert "E9907" in _codes(result)


def test_input_accept_is_refused_regardless_of_spelling():
    plans = _faithful_plan()
    plans["rtr-slate"]["zones"][_USER]["input"] = "  accept "

    result = _run_validator(plans)

    assert "E9907" in _codes(result)


def test_absent_channel_is_not_a_defect():
    """A project with no OpenWrt enforcer never produces the channel."""
    result = _run_validator(None)

    assert result.status == PluginStatus.SUCCESS
    assert _codes(result) == []


def test_malformed_plan_does_not_crash():
    result = _run_validator({"rtr-slate": "not a plan"})

    assert result.status == PluginStatus.SUCCESS
    assert _codes(result) == []


def test_every_enforcer_is_checked_not_just_the_first():
    plans = _faithful_plan()
    second = copy.deepcopy(plans["rtr-slate"])
    second["forwardings"].append({"src": _USER, "dest": _UNTRUSTED})
    plans["rtr-other"] = second

    result = _run_validator(plans)

    assert _codes(result).count("E9906") == 1
    assert "rtr-other" in next(d.message for d in result.diagnostics if d.code == "E9906")


def test_compiler_output_passes_its_own_validator():
    """Closes the loop: the producer's real output satisfies the consumer."""
    model = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-slate",
                    "instance": {
                        "derived_capabilities": [
                            "cap.os.openwrt",
                            "cap.net.l3.security.firewall.zone_policy",
                        ]
                    },
                    "object": {},
                }
            ],
            "network": [
                {
                    "instance_id": "inst.vlan.slate_home",
                    "instance_data": {
                        "managed_by_ref": "rtr-slate",
                        "trust_zone_ref": _USER,
                        "cidr": "10.77.1.0/24",
                        "gateway": "10.77.1.1",
                        "dhcp_range": "10.77.1.100-10.77.1.200",
                        "dns_servers": ["10.77.1.1"],
                    },
                }
            ],
        }
    }
    matrix = {
        "rtr-slate": {
            "scope_ids": ["inst.security_matrix.rtr_slate"],
            "zones": {_USER: {}, _UNTRUSTED: {}},
            "matrix": {_USER: {_UNTRUSTED: {"action": "drop", "rule": "R6", "reason": "kill switch"}}},
        }
    }

    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    publish_for_test(ctx, "base.compiler.effective_model", "effective_model_candidate", model)
    publish_for_test(
        ctx,
        "base.compiler.effective_model",
        "enforcer_resolution",
        {"rtr-slate": {"type": "network", "adapter": "cap.firewall.security_matrix.openwrt"}},
    )
    publish_for_test(ctx, "base.compiler.security_matrix", "composed_matrices_by_enforcer", matrix)

    compiler = COMPILER_MODULE.OpenwrtZonesCompiler(COMPILER_ID)
    compiled = run_plugin_for_test(
        compiler,
        ctx,
        Stage.COMPILE,
        consumes_keys={"base.compiler.effective_model", "base.compiler.security_matrix"},
    )
    plan = compiled.output_data["openwrt_zones"]

    # The denial must have been lowered as an omission, which is what makes the
    # validator pass rather than a coincidence of empty data.
    assert plan["rtr-slate"]["denied_pairs"]
    assert plan["rtr-slate"]["forwardings"] == []

    result = _run_validator(plan)
    assert _codes(result) == []

#!/usr/bin/env python3
# ADR: 0110, 0118, 0119
"""Tests for the OpenWrt rule-plan validator.

Both codes here guard failure modes that are silent on the live device: fw4
drops a wrong-arity section without logging it, and an overlapping pair of
sections resolves by an order uapi gives no way to specify. Neither shows up as
a Terraform error, so every test feeds the validator a violation and asserts the
specific code fires rather than asserting a clean plan passes.

The last two tests close the loop against the real compiler: the plan this repo
actually produces must be clean, and it must be clean because the tuples are
disjoint rather than because the rule list is empty.
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

VALIDATOR_ID = "object.openwrt.validator_json.rule_plan"
COMPILER_ID = "object.openwrt.compiler.zones"

_USER = "inst.trust_zone.user"
_SERVERS = "inst.trust_zone.servers"
_VPN_EXIT = "inst.trust_zone.vpn_exit"


def _load(module_name: str, relative: str):
    path = V5_ROOT / "topology" / "object-modules" / "openwrt" / relative
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR_MODULE = _load(
    "test_openwrt_rule_plan_validator_module",
    "plugins/validators/rule_plan_validator.py",
)
COMPILER_MODULE = _load(
    "test_openwrt_zones_compiler_for_rule_validator",
    "plugins/compilers/zones_compiler.py",
)


def _rule(**overrides):
    rule = {
        "src": _USER,
        "dest": _VPN_EXIT,
        "remote_zone": _SERVERS,
        "dest_cidrs": ["10.77.1.0/24"],
        "ports": {"tcp": [80, 443]},
        "rule": "R6",
        "reason": "policy_override: slate-home-to-servers",
    }
    rule.update(overrides)
    return rule


def _plan(rules):
    return {"rtr-slate": {"scope_ids": ["inst.security_matrix.rtr_slate"], "rules": rules}}


def _run(plans):
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        instance_bindings={"instance_bindings": {}},
    )
    if plans is not None:
        publish_for_test(ctx, COMPILER_ID, "openwrt_zones", plans)
    plugin = VALIDATOR_MODULE.OpenwrtRulePlanValidator(VALIDATOR_ID)
    return run_plugin_for_test(plugin, ctx, Stage.VALIDATE, consumes_keys={COMPILER_ID})


def _codes(result) -> list[str]:
    return [d.code for d in result.diagnostics]


def _message(result, code: str) -> str:
    return next(d.message for d in result.diagnostics if d.code == code)


# ---------------------------------------------------------------------------
# Absence and well-formed input
# ---------------------------------------------------------------------------


def test_absent_channel_is_not_a_defect():
    """A project with no OpenWrt enforcer never produces the channel."""
    assert _codes(_run(None)) == []


def test_disjoint_rules_raise_nothing():
    plans = _plan(
        [
            _rule(ports={"tcp": [80, 443]}),
            _rule(ports={"udp": [53]}),
        ]
    )

    assert _codes(_run(plans)) == []


def test_different_chains_never_interact():
    """Disjointness is per chain; the same tuple in two chains is two chains."""
    plans = _plan(
        [
            _rule(src=_USER),
            _rule(src="inst.trust_zone.travel_split"),
        ]
    )

    assert _codes(_run(plans)) == []


# ---------------------------------------------------------------------------
# E9902 - overlapping match tuples
# ---------------------------------------------------------------------------


def test_identical_tuples_are_refused():
    """Two resources claiming one uci section, and no statement of which wins."""
    plans = _plan([_rule(), _rule()])

    result = _run(plans)

    assert "E9902" in _codes(result)
    assert "identical match tuples" in _message(result, "E9902")


def test_opposing_targets_on_one_tuple_are_refused():
    plans = _plan([_rule(target="ACCEPT"), _rule(target="DROP")])

    result = _run(plans)

    assert "E9902" in _codes(result)
    message = _message(result, "E9902")
    assert "opposing targets" in message
    assert "ACCEPT" in message and "DROP" in message


def test_overlapping_ports_with_opposing_targets_are_refused():
    """Partial port overlap is still overlap: 443 is matched by both."""
    plans = _plan(
        [
            _rule(target="ACCEPT", ports={"tcp": [80, 443]}),
            _rule(target="REJECT", ports={"tcp": [443, 8443]}),
        ]
    )

    assert "E9902" in _codes(_run(plans))


def test_disjoint_ports_with_opposing_targets_are_allowed():
    """Opposing targets are fine when the tuples cannot both match a packet."""
    plans = _plan(
        [
            _rule(target="ACCEPT", ports={"tcp": [80]}),
            _rule(target="DROP", ports={"tcp": [22]}),
        ]
    )

    assert _codes(_run(plans)) == []


def test_protocol_separates_otherwise_identical_tuples():
    """The generator emits one entry per protocol precisely so this holds."""
    plans = _plan([_rule(ports={"tcp": [53], "udp": [53]})])

    assert _codes(_run(plans)) == []


def test_port_unrestricted_rule_overlaps_a_port_scoped_one():
    """An absent port set means every port, so it cannot be disjoint."""
    plans = _plan(
        [
            _rule(target="ACCEPT", ports=None),
            _rule(target="DROP", ports={"tcp": [22]}),
        ]
    )

    assert "E9902" in _codes(_run(plans))


def test_prefixes_are_compared_as_networks_not_strings():
    """10.0.0.0/8 contains 10.77.1.0/24; string equality would miss it.

    This is the case that makes the check worth computing rather than comparing:
    two tuples with opposing targets and different-looking prefixes that match
    the same packets.
    """
    plans = _plan(
        [
            _rule(target="ACCEPT", dest_cidrs=["10.0.0.0/8"]),
            _rule(target="DROP", dest_cidrs=["10.77.1.0/24"]),
        ]
    )

    result = _run(plans)

    assert "E9902" in _codes(result)
    assert "opposing targets" in _message(result, "E9902")


def test_non_overlapping_prefixes_are_allowed():
    plans = _plan(
        [
            _rule(target="ACCEPT", dest_cidrs=["10.77.1.0/24"]),
            _rule(target="DROP", dest_cidrs=["10.77.2.0/24"]),
        ]
    )

    assert _codes(_run(plans)) == []


def test_unrestricted_prefix_overlaps_every_prefix():
    plans = _plan(
        [
            _rule(target="ACCEPT", dest_cidrs=[]),
            _rule(target="DROP", dest_cidrs=["10.77.2.0/24"]),
        ]
    )

    assert "E9902" in _codes(_run(plans))


def test_narrower_tuple_with_the_same_target_is_allowed():
    """Redundant but unambiguous: both match, both accept, order cannot matter.

    Erroring here would refuse a plan that enforces exactly what it says, which
    is how a disjointness check turns into a source of false positives.
    """
    plans = _plan(
        [
            _rule(target="ACCEPT", ports={"tcp": [80, 443]}),
            _rule(target="ACCEPT", ports={"tcp": [443]}),
        ]
    )

    assert _codes(_run(plans)) == []


def test_the_finding_names_both_rule_indices():
    """An operator needs to know which two of n rules to reconcile."""
    plans = _plan([_rule(ports={"udp": [53]}), _rule(), _rule()])

    result = _run(plans)

    message = _message(result, "E9902")
    assert "#1" in message and "#2" in message


# ---------------------------------------------------------------------------
# E9903 - match field arity
# ---------------------------------------------------------------------------


def test_bare_string_port_set_is_refused():
    """The renderer iterates it, so "80" becomes ["8", "0"] - valid and absurd."""
    plans = _plan([_rule(ports={"tcp": "80"})])

    result = _run(plans)

    assert "E9903" in _codes(result)
    assert "ports.tcp" in next(d.path for d in result.diagnostics if d.code == "E9903")


def test_bare_string_dest_cidrs_is_refused():
    plans = _plan([_rule(dest_cidrs="10.77.1.0/24")])

    assert "E9903" in _codes(_run(plans))


def test_list_zone_endpoint_is_refused():
    """src_zone is a string in the provider schema, not a list."""
    plans = _plan([_rule(src=[_USER])])

    assert "E9903" in _codes(_run(plans))


def test_missing_zone_endpoint_is_refused():
    plans = _plan([_rule(dest=None)])

    assert "E9903" in _codes(_run(plans))


def test_ports_as_a_list_instead_of_a_protocol_mapping_is_refused():
    plans = _plan([_rule(ports=[80, 443])])

    assert "E9903" in _codes(_run(plans))


def test_non_mapping_rule_entry_is_refused():
    assert "E9903" in _codes(_run(_plan(["not-a-rule"])))


def test_absent_ports_are_not_an_arity_defect():
    """A permit with no port scope is the normal unrestricted case."""
    plans = _plan([_rule(ports=None)])

    assert _codes(_run(plans)) == []


def test_arity_defect_suppresses_the_disjointness_report():
    """Flattening a wrong-arity rule would compare a shape nothing renders.

    Both rules here would be identical tuples if flattened, so without the
    short-circuit this plan would also carry an E9902 derived from a port set
    the generator would never produce.
    """
    plans = _plan([_rule(ports={"tcp": "80"}), _rule(ports={"tcp": "80"})])

    codes = _codes(_run(plans))

    assert "E9903" in codes
    assert "E9902" not in codes


# ---------------------------------------------------------------------------
# Against the real compiler
# ---------------------------------------------------------------------------


def _compile_real_plan():
    """Drive the real compiler over a matrix that produces port-scoped rules."""
    model = {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-slate",
                    # Capability metadata lives in the sibling `instance` block;
                    # authored values live in `instance_data`.
                    "instance": {
                        "derived_capabilities": [
                            "cap.os.openwrt",
                            "cap.net.l3.security.firewall.zone_policy",
                        ]
                    },
                    "object": {},
                    # Shaped as the real instance authors it: management is one
                    # interface spec, wireguard a list under `interfaces`, and
                    # `reaches_zone_refs` is what makes the remote servers zone
                    # routable through the tunnel zone.
                    "instance_data": {
                        "runtime_intent": {
                            "management": {
                                "interface": "lan",
                                "device": "br-lan",
                                "address": "192.168.1.1/24",
                                "proto": "static",
                                "trust_zone_ref": "inst.trust_zone.management",
                                "immutable": True,
                                "endpoint_arrives_here": True,
                                "input_services": ["ssh", "uapi"],
                            },
                            "wireguard": {
                                "interfaces": [
                                    {
                                        "name": "wg-home",
                                        "tunnel_ip": "10.100.0.4/24",
                                        "mtu": 1420,
                                        "advertises": ["10.77.1.0/24"],
                                        "reaches_zone_refs": [_SERVERS],
                                        "trust_zone_ref": _VPN_EXIT,
                                        "enabled": True,
                                    }
                                ]
                            },
                        }
                    },
                },
            ],
            "network": [
                {
                    "instance_id": "inst.vlan.slate_home",
                    "instance_data": {
                        "cidr": "10.77.1.0/24",
                        "trust_zone_ref": _USER,
                        "managed_by_ref": "rtr-slate",
                    },
                },
                {
                    "instance_id": "inst.vlan.servers",
                    "instance_data": {
                        "cidr": "10.0.30.0/24",
                        "trust_zone_ref": _SERVERS,
                        "managed_by_ref": "rtr-mikrotik-chateau",
                    },
                },
            ],
        }
    }
    # Two port-scoped permits from one source zone to one remote zone: the exact
    # shape that would collide if the generator did not split per protocol.
    matrix = {
        "rtr-slate": {
            "scope_ids": ["inst.security_matrix.rtr_slate"],
            # Zone prefixes reach the lowering through the composed matrix's
            # zone data, which is where the security_matrix compiler puts each
            # zone's address space. A remote zone has no local segment, so this
            # is the only place its prefixes can come from.
            "zones": {_USER: {}, _SERVERS: {"cidrs": ["10.0.30.0/24"]}, _VPN_EXIT: {}},
            "matrix": {
                _USER: {
                    _SERVERS: {
                        "action": "accept",
                        "rule": "R6",
                        "reason": "policy_override: slate-home-to-servers",
                        # Two protocols on one pair: the lowering keeps them in
                        # one rule and the renderer splits them, which is the
                        # mechanism that keeps the chain's tuples disjoint.
                        "ports": {"tcp": [80, 443, 5432, 6379], "udp": [53]},
                    },
                    _VPN_EXIT: {"action": "accept", "rule": "R3", "reason": "downhill"},
                },
            },
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
    return compiled.output_data["openwrt_zones"]


def test_the_real_compilers_plan_is_clean():
    plan = _compile_real_plan()

    # Clean because the tuples are disjoint, not because there is nothing to
    # check: assert the rules exist before asserting they pass.
    assert plan["rtr-slate"]["rules"], "the fixture must produce port-scoped rules"

    assert _codes(_run(plan)) == []


def test_the_real_compiler_emits_list_arity_throughout():
    """The arity contract holds on produced data, not only on hand-built plans."""
    plan = _compile_real_plan()

    for rule in plan["rtr-slate"]["rules"]:
        assert isinstance(rule["src"], str)
        assert isinstance(rule["dest"], str)
        assert isinstance(rule["dest_cidrs"], list)
        for values in (rule.get("ports") or {}).values():
            assert isinstance(values, list)

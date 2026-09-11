#!/usr/bin/env python3
"""The consumer that makes the v2 declarations binding.

Gate G1 of ADR 0118 needs a schema that constrains an instance, not one that
sits in a class file unread. These tests execute the plugin through the registry,
which is also the only proof that it loads at all: a validator that emits nothing
because it never ran looks exactly like one that emits nothing because the
sources are clean.

The schemas come from the real class files rather than from a fixture copy. A
fixture would let the validator and the declaration drift apart while every test
kept passing, which is the failure this whole gate is about.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402
from yaml_loader import load_yaml_file  # noqa: E402

from tests.helpers.plugin_execution import publish_for_test  # noqa: E402

PLUGIN_ID = "base.validator.network_intent_schema"

WORKLOAD_CLASS = REPO_ROOT / "topology/class-modules/L4-platform/compute/workload/class.compute.workload.yaml"
SERVICE_CLASS = REPO_ROOT / "topology/class-modules/L5-application/service/class.service.yaml"
POLICY_CLASS = REPO_ROOT / "topology/class-modules/L2-network/network/class.network.firewall_policy.yaml"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _classes() -> dict:
    """Real declarations, with the lineage the compiler actually produces."""
    workload = load_yaml_file(WORKLOAD_CLASS) or {}
    service = load_yaml_file(SERVICE_CLASS) or {}
    policy = load_yaml_file(POLICY_CLASS) or {}
    return {
        "class.compute.workload": {
            "lineage": ["class.compute.workload"],
            "network_intent_schema": workload["network_intent_schema"],
        },
        # The base's payload is deliberately absent here, as it is in the
        # compiled model: inheritance records lineage and merges nothing.
        "class.compute.workload.lxc": {"lineage": ["class.compute.workload", "class.compute.workload.lxc"]},
        "class.service": {
            "lineage": ["class.service"],
            "service_publication_schema": service["service_publication_schema"],
        },
        "class.service.proxy": {"lineage": ["class.service", "class.service.proxy"]},
        "class.network.firewall_policy": {
            "lineage": ["class.network.firewall_policy"],
            "policy_intent_schema": policy["policy_intent_schema"],
        },
    }


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes=copy.deepcopy(_classes()),
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _run(rows: list[dict]):
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    return registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)


def _workload(network: dict, class_ref: str = "class.compute.workload.lxc") -> list[dict]:
    return [
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": class_ref,
            "layer": "L4",
            "object_ref": "obj.workload.a",
            "extensions": {"network": network},
        }
    ]


def _codes(result) -> list[str]:
    return [diag.code for diag in result.diagnostics]


# --- the plugin exists and runs ---------------------------------------------


def test_the_plugin_is_registered_and_executes() -> None:
    """Proof of loading. Without it, silence is not evidence of anything."""
    registry = _registry()

    assert PLUGIN_ID in registry.specs
    assert registry.specs[PLUGIN_ID].consumes[0]["required"] is True

    result = _run([])
    assert result.status == PluginStatus.SUCCESS


def test_a_v1_source_is_left_alone() -> None:
    """Today's entire tree is v1. The validator must be inert on it."""
    result = _run(_workload({"vlan_ref": "inst.vlan.lan", "host": 20}))

    assert result.diagnostics == []


def test_a_row_with_no_network_block_is_not_an_error() -> None:
    rows = [{"group": "lxc", "instance": "lxc-b", "class_ref": "class.compute.workload.lxc", "layer": "L4"}]

    assert _run(rows).diagnostics == []


# --- resolution along lineage ------------------------------------------------


def test_the_schema_is_found_through_lineage_not_on_the_named_class() -> None:
    """The measured fact this plugin is built around.

    `class.compute.workload.lxc` carries no schema of its own. A consumer reading
    only the class an instance names would find nothing and pass everything, so
    this test asserts a rejection that is only possible if lineage was walked.
    """
    result = _run(_workload({"schema_version": 2, "attachments": {"bad-key": {"network_ref": "inst.vlan.lan"}}}))

    assert "E7002" in _codes(result)


def test_an_unknown_class_cannot_silently_pass_a_v2_block() -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {}}, class_ref="class.nonexistent"))

    assert "E7001" in _codes(result)
    assert any("no class in its lineage declares" in diag.message for diag in result.diagnostics)


# --- E7001 unknown key -------------------------------------------------------


def test_an_undeclared_key_in_the_block_is_refused() -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {}, "nonsense": 1}))

    assert "E7001" in _codes(result)


def test_an_undeclared_property_in_a_record_is_refused() -> None:
    result = _run(
        _workload({"schema_version": 2, "attachments": {"primary": {"network_ref": "inst.vlan.lan", "colour": "red"}}})
    )

    assert "E7001" in _codes(result)
    assert any("colour" in diag.message for diag in result.diagnostics)


# --- E7002 local key grammar -------------------------------------------------


@pytest.mark.parametrize("key", ["wan-uplink", "net.primary", "@primary", "1st"])
def test_a_record_key_outside_the_grammar_is_refused(key: str) -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {key: {"network_ref": "inst.vlan.lan"}}}))

    assert "E7002" in _codes(result)


@pytest.mark.parametrize("key", ["primary", "_internal", "wan0", "backend"])
def test_a_valid_record_key_is_accepted(key: str) -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {key: {"network_ref": "inst.vlan.lan"}}}))

    assert result.diagnostics == []


def test_the_validator_grammar_equals_the_declared_key_pattern() -> None:
    """Three copies of one rule, tied together so they cannot drift."""
    sys.path.insert(0, str(REPO_ROOT))
    from netmodel.identity import LOCAL_KEY_RE as model_pattern

    from plugins.validators.network_intent_schema_validator import LOCAL_KEY_RE as plugin_pattern

    declared = (load_yaml_file(WORKLOAD_CLASS) or {})["network_intent_schema"]["attachments"]["key_pattern"]

    assert plugin_pattern.pattern == model_pattern.pattern == declared


# --- E7003 derived field authored --------------------------------------------


@pytest.mark.parametrize("field", ["ip", "gateway", "zone", "routing_domain", "address_family"])
def test_a_derived_field_authored_on_an_attachment_is_refused(field: str) -> None:
    record = {"network_ref": "inst.vlan.lan", field: "whatever"}
    result = _run(_workload({"schema_version": 2, "attachments": {"primary": record}}))

    assert "E7003" in _codes(result)
    assert any(field in diag.message for diag in result.diagnostics)


def test_a_derived_field_is_reported_as_derived_not_as_unknown() -> None:
    """Two different mistakes deserve two different codes.

    'ip is not declared here' sends an author looking for a typo; 'ip is derived'
    tells them the value already exists and must not be restated.
    """
    result = _run(_workload({"schema_version": 2, "attachments": {"primary": {"network_ref": "n", "ip": "10.0.0.5"}}}))

    assert _codes(result) == ["E7003"]


# --- E7004 mixed versions ----------------------------------------------------


def test_a_block_mixing_v1_keys_with_v2_is_refused() -> None:
    result = _run(
        _workload({"schema_version": 2, "vlan_ref": "inst.vlan.lan", "host": 20, "attachments": {}})
    )

    assert "E7004" in _codes(result)
    assert any("vlan_ref" in diag.message and "host" in diag.message for diag in result.diagnostics)


# --- E7005 required field ----------------------------------------------------


def test_an_attachment_without_network_ref_is_refused() -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {"primary": {"interface": "eth0"}}}))

    assert "E7005" in _codes(result)
    assert any("network_ref" in diag.message for diag in result.diagnostics)


def test_a_record_that_is_not_an_object_is_refused() -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {"primary": "inst.vlan.lan"}}))

    assert "E7005" in _codes(result)


# --- E7006 version -----------------------------------------------------------


def test_a_v2_collection_without_a_version_is_refused() -> None:
    result = _run(_workload({"attachments": {"primary": {"network_ref": "inst.vlan.lan"}}}))

    assert _codes(result) == ["E7006"]


@pytest.mark.parametrize("version", [1, 3, "2", None])
def test_an_unsupported_version_is_refused(version) -> None:
    block = {"schema_version": version, "attachments": {}}
    result = _run(_workload(block))

    assert "E7006" in _codes(result)


# --- publications (L5) -------------------------------------------------------


def _service(publication: dict) -> list[dict]:
    return [
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.proxy",
            "layer": "L5",
            "extensions": {"publication": publication},
        }
    ]


def test_a_publication_missing_its_required_fields_is_refused() -> None:
    result = _run(_service({"schema_version": 2, "publications": {"web": {"protocol": "tcp"}}}))

    messages = " ".join(diag.message for diag in result.diagnostics)
    assert "E7005" in _codes(result)
    assert "endpoint_ref" in messages and "port" in messages


def test_a_publication_cannot_author_a_source_selector() -> None:
    """The structural claim, now enforced rather than only declared."""
    record = {"endpoint_ref": "primary", "protocol": "tcp", "port": 443, "allowed_from": ["inst.vlan.lan"]}
    result = _run(_service({"schema_version": 2, "publications": {"web": record}}))

    assert "E7003" in _codes(result)
    assert any("allowed_from" in diag.message for diag in result.diagnostics)


def test_a_valid_publication_passes() -> None:
    record = {"endpoint_ref": "primary", "protocol": "tcp", "port": 443, "mechanism": "direct"}

    assert _run(_service({"schema_version": 2, "publications": {"web": record}})).diagnostics == []


# --- policies and bindings (L2) ----------------------------------------------


def _policy(policy: dict) -> list[dict]:
    return [
        {
            "group": "network",
            "instance": "inst.firewall_policy.main",
            "class_ref": "class.network.firewall_policy",
            "layer": "L2",
            "extensions": {"policy": policy},
        }
    ]


def _template(**overrides) -> dict:
    record = {
        "effect": "permit",
        "activation": "binding_only",
        "direction": "ingress",
        "source": "{binding: source}",
        "destination": "{binding: destination}",
        "protocol": "tcp",
        "ports": [443],
        "owner": "infra-admin",
        "rationale": "why",
    }
    record.update(overrides)
    return record


def test_a_policy_template_missing_owner_or_rationale_is_refused() -> None:
    record = _template()
    del record["owner"]
    del record["rationale"]
    result = _run(_policy({"schema_version": 2, "policies": {"dns": record}}))

    messages = " ".join(diag.message for diag in result.diagnostics)
    assert "E7005" in _codes(result)
    assert "owner" in messages and "rationale" in messages


def test_an_authored_rule_position_is_refused() -> None:
    """Positions come from execution precedence, never from an author's number."""
    result = _run(_policy({"schema_version": 2, "policies": {"dns": _template(position=3, priority=10)}}))

    codes = _codes(result)
    messages = " ".join(diag.message for diag in result.diagnostics)
    assert codes.count("E7003") == 2
    assert "position" in messages and "priority" in messages


def test_a_binding_cannot_restate_the_effect_it_binds() -> None:
    binding = {"policy_ref": "dns", "sources": ["a"], "destinations": ["b"], "effect": "permit"}
    result = _run(_policy({"schema_version": 2, "policies": {"dns": _template()}, "bindings": {"b1": binding}}))

    assert "E7003" in _codes(result)
    assert any("effect" in diag.message for diag in result.diagnostics)


def test_a_v1_policy_with_rules_beside_v2_is_refused() -> None:
    block = {"schema_version": 2, "rules": [{"action": "accept"}], "policies": {"dns": _template()}}
    result = _run(_policy(block))

    assert "E7004" in _codes(result)


def test_a_complete_policy_and_binding_pass() -> None:
    binding = {"policy_ref": "dns", "sources": ["inst.vlan.lan"], "destinations": ["inst.vlan.mgmt"], "approved": True}
    result = _run(_policy({"schema_version": 2, "policies": {"dns": _template()}, "bindings": {"b1": binding}}))

    assert result.diagnostics == []

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


def _domain(instance: str = "inst.vlan.lan", cidr: str = "10.0.20.0/24") -> dict:
    """A modeled address domain, so an attachment has something real to name."""
    return {
        "group": "network",
        "instance": instance,
        "class_ref": "class.network.vlan",
        "layer": "L2",
        "extensions": {"cidr": cidr},
    }


def _workload(network: dict, class_ref: str = "class.compute.workload.lxc") -> list[dict]:
    return [
        _domain(),
        {
            "group": "lxc",
            "instance": "lxc-a",
            "class_ref": class_ref,
            "layer": "L4",
            "object_ref": "obj.workload.a",
            "extensions": {"network": network},
        },
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


def _service(publication: dict, *, host_attachments: dict | None = None) -> list[dict]:
    attachments = {"primary": {"network_ref": "inst.vlan.lan"}} if host_attachments is None else host_attachments
    return [
        _domain(),
        {
            "group": "lxc",
            "instance": "lxc-host",
            "class_ref": "class.compute.workload.lxc",
            "layer": "L4",
            "extensions": {"network": {"schema_version": 2, "attachments": attachments}},
        },
        {
            "group": "services",
            "instance": "svc-a",
            "class_ref": "class.service.proxy",
            "layer": "L5",
            "extensions": {
                "publication": publication,
                "runtime": {"type": "lxc", "target_ref": "lxc-host"},
            },
        },
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


# --- pass two: meaning across records ----------------------------------------


def test_an_attachment_to_an_unmodeled_network_is_refused() -> None:
    result = _run(_workload({"schema_version": 2, "attachments": {"p": {"network_ref": "inst.vlan.ghost"}}}))

    assert "E7020" in _codes(result)
    assert any("not a modeled address domain" in diag.message for diag in result.diagnostics)


def test_two_attachments_claiming_one_host_offset_are_refused() -> None:
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 20}},
                "b": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 20}},
            },
        }
    )

    result = _run(rows)

    assert "E7022" in _codes(result)
    assert any("already claimed by" in diag.message for diag in result.diagnostics)


def test_the_same_offset_in_different_domains_is_fine() -> None:
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 20}},
                "b": {"network_ref": "inst.vlan.dmz", "address": {"allocation": "static", "host": 20}},
            },
        }
    )
    rows.append(_domain("inst.vlan.dmz", "10.0.30.0/24"))

    assert _run(rows).diagnostics == []


def test_a_disabled_attachment_claims_nothing() -> None:
    """Explicit false disables a record; it must not keep holding an address."""
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 20}},
                "b": {
                    "enabled": False,
                    "network_ref": "inst.vlan.lan",
                    "address": {"allocation": "static", "host": 20},
                },
            },
        }
    )

    assert _run(rows).diagnostics == []


def test_a_static_address_in_a_domain_with_no_prefix_is_refused() -> None:
    rows = _workload(
        {"schema_version": 2, "attachments": {"a": {"network_ref": "inst.vlan.lan", "address": {"host": 20}}}}
    )
    rows[0]["extensions"] = {}  # the domain declares no cidr

    result = _run(rows)

    assert "E7023" in _codes(result)


def test_pass_two_does_not_run_while_a_shape_error_stands() -> None:
    """One mistake, one message. Follow-on errors bury the first."""
    rows = _workload({"schema_version": 2, "attachments": {"bad-key": {"network_ref": "inst.vlan.ghost"}}})

    codes = _codes(_run(rows))

    assert codes == ["E7002"], "the unresolvable network_ref must wait until the key is fixed"


# --- publications ------------------------------------------------------------


def test_a_publication_naming_an_endpoint_the_host_lacks_is_refused() -> None:
    publication = {"schema_version": 2, "publications": {"web": {"endpoint_ref": "ghost", "protocol": "tcp", "port": 443}}}

    result = _run(_service(publication))

    assert "E7040" in _codes(result)
    assert any("Declared there: ['primary']" in diag.message for diag in result.diagnostics)


def test_two_publications_on_one_endpoint_and_port_are_refused() -> None:
    publication = {
        "schema_version": 2,
        "publications": {
            "a": {"endpoint_ref": "primary", "protocol": "tcp", "port": 443},
            "b": {"endpoint_ref": "primary", "protocol": "tcp", "port": 443},
        },
    }

    result = _run(_service(publication))

    assert "E7041" in _codes(result)


def test_the_same_port_on_different_protocols_is_fine() -> None:
    publication = {
        "schema_version": 2,
        "publications": {
            "a": {"endpoint_ref": "primary", "protocol": "tcp", "port": 53},
            "b": {"endpoint_ref": "primary", "protocol": "udp", "port": 53},
        },
    }

    assert _run(_service(publication)).diagnostics == []


# --- policy algebra ----------------------------------------------------------


def _guard(**overrides) -> dict:
    record = {
        "effect": "deny",
        "activation": "scope_guard",
        "direction": "transit",
        "source": ["inst.vlan.guest"],
        "destination": ["inst.vlan.mgmt"],
        "protocol": "tcp",
        "ports": [22, 443],
        "owner": "security",
        "rationale": "guest must not reach management",
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    ("effect", "activation"), [("permit", "scope_guard"), ("deny", "binding_only")]
)
def test_a_mode_outside_the_baseline_is_refused(effect: str, activation: str) -> None:
    result = _run(_policy({"schema_version": 2, "policies": {"x": _template(effect=effect, activation=activation)}}))

    assert "E7060" in _codes(result)


def test_a_scope_guard_cannot_carry_an_unbound_parameter() -> None:
    result = _run(_policy({"schema_version": 2, "policies": {"g": _guard(source="{binding: source}")}}))

    assert "E7064" in _codes(result)


def test_a_binding_to_an_unknown_policy_is_refused() -> None:
    binding = {"policy_ref": "nope", "sources": ["a"], "destinations": ["b"]}
    result = _run(_policy({"schema_version": 2, "policies": {"dns": _template()}, "bindings": {"b1": binding}}))

    assert "E7061" in _codes(result)


def test_a_binding_to_a_guard_is_refused() -> None:
    binding = {"policy_ref": "g", "sources": ["inst.vlan.guest"], "destinations": ["inst.vlan.mgmt"]}
    result = _run(_policy({"schema_version": 2, "policies": {"g": _guard()}, "bindings": {"b1": binding}}))

    assert "E7061" in _codes(result)
    assert any("Only a permit can be bound" in diag.message for diag in result.diagnostics)


def test_a_binding_that_does_not_intersect_its_template_is_refused() -> None:
    scoped = _template(source=["inst.vlan.lan"])
    binding = {"policy_ref": "p", "sources": ["inst.vlan.guest"], "destinations": ["inst.vlan.mgmt"]}
    result = _run(_policy({"schema_version": 2, "policies": {"p": scoped}, "bindings": {"b1": binding}}))

    assert "E7064" in _codes(result)
    assert any("not 'any'" in diag.message for diag in result.diagnostics)


def test_a_permit_overlapping_a_guard_is_refused_with_a_concrete_witness() -> None:
    binding = {"policy_ref": "p", "sources": ["inst.vlan.guest"], "destinations": ["inst.vlan.mgmt"]}
    block = {
        "schema_version": 2,
        "policies": {"p": _template(ports=[443]), "g": _guard()},
        "bindings": {"b1": binding},
    }

    result = _run(_policy(block))

    assert "E7063" in _codes(result)
    assert any(
        "inst.vlan.guest -> inst.vlan.mgmt tcp/443 matches both" in diag.message for diag in result.diagnostics
    )


def test_a_narrower_permit_does_not_defeat_a_guard() -> None:
    """Specificity is not authorization."""
    binding = {"policy_ref": "p", "sources": ["inst.vlan.guest"], "destinations": ["inst.vlan.mgmt"]}
    block = {
        "schema_version": 2,
        "policies": {"p": _template(ports=[22]), "g": _guard(ports=[22, 80, 443])},
        "bindings": {"b1": binding},
    }

    assert "E7063" in _codes(_run(_policy(block)))


def test_a_permit_beside_a_guard_that_it_misses_is_fine() -> None:
    binding = {"policy_ref": "p", "sources": ["inst.vlan.lan"], "destinations": ["inst.vlan.mgmt"], "approved": True}
    block = {"schema_version": 2, "policies": {"p": _template(), "g": _guard()}, "bindings": {"b1": binding}}

    assert _run(_policy(block)).diagnostics == []


def test_different_protocols_do_not_overlap() -> None:
    binding = {"policy_ref": "p", "sources": ["inst.vlan.guest"], "destinations": ["inst.vlan.mgmt"]}
    block = {
        "schema_version": 2,
        "policies": {"p": _template(protocol="udp"), "g": _guard(protocol="tcp")},
        "bindings": {"b1": binding},
    }

    assert _run(_policy(block)).diagnostics == []


# --- the forcing function ----------------------------------------------------


def test_the_plugin_algebra_agrees_with_the_reference_model() -> None:
    """Two implementations of one rule need something holding them together.

    The plugin cannot import netmodel: that package sits outside framework
    distribution deliberately, so an external project would not have it. The
    algebra is therefore written twice, and this test is the only thing that
    stops the copies from diverging - it runs both over the same cases and
    requires the same verdict.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from netmodel.policy import (
        BINDING_DESTINATION,
        BINDING_SOURCE,
        Activation,
        Binding,
        Effect,
        PolicyError,
        PolicyTemplate,
        authorize,
        resolve_grant,
    )

    cases = [
        (["inst.vlan.guest"], ["inst.vlan.mgmt"], [443], [22, 443], True),
        (["inst.vlan.lan"], ["inst.vlan.mgmt"], [443], [22, 443], False),
        (["inst.vlan.guest"], ["inst.vlan.mgmt"], [80], [22, 443], False),
        (["inst.vlan.guest"], ["inst.vlan.mgmt"], [22], [22, 80, 443], True),
        (["inst.vlan.guest", "inst.vlan.lan"], ["inst.vlan.mgmt"], [443], [443], True),
    ]

    for sources, destinations, permit_ports, guard_ports, expected_conflict in cases:
        binding = {"policy_ref": "p", "sources": sources, "destinations": destinations}
        block = {
            "schema_version": 2,
            "policies": {"p": _template(ports=permit_ports), "g": _guard(ports=guard_ports)},
            "bindings": {"b1": binding},
        }
        plugin_conflict = "E7063" in _codes(_run(_policy(block)))

        template = PolicyTemplate(
            policy_id="p",
            effect=Effect.PERMIT,
            activation=Activation.BINDING_ONLY,
            direction="ingress",
            source=BINDING_SOURCE,
            destination=BINDING_DESTINATION,
            protocol="tcp",
            ports=frozenset(permit_ports),
            owner="o",
            rationale="r",
        )
        guard = PolicyTemplate(
            policy_id="g",
            effect=Effect.DENY,
            activation=Activation.SCOPE_GUARD,
            direction="transit",
            source=frozenset({"inst.vlan.guest"}),
            destination=frozenset({"inst.vlan.mgmt"}),
            protocol="tcp",
            ports=frozenset(guard_ports),
            owner="o",
            rationale="r",
        )
        grant = resolve_grant(
            template,
            Binding(
                binding_id="b1",
                policy_id="p",
                sources=frozenset(sources),
                destinations=frozenset(destinations),
                approved=True,
            ),
        )
        try:
            authorize([grant], {"g": guard})
            model_conflict = False
        except PolicyError:
            model_conflict = True

        assert plugin_conflict == model_conflict == expected_conflict, (
            f"plugin and reference model disagree for {sources} -> {destinations} "
            f"permit {permit_ports} guard {guard_ports}"
        )


# --- address domain resolution -----------------------------------------------


def test_an_offset_outside_the_prefix_is_refused() -> None:
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {"a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 300}}},
        }
    )

    result = _run(rows)

    assert "E7024" in _codes(result)
    assert any("usable offsets are 1..254" in diag.message for diag in result.diagnostics)


def test_the_same_offset_is_valid_in_a_larger_prefix() -> None:
    """host is an offset, not a last octet, and the difference is visible here.

    300 does not exist in a /24 and is an ordinary address in a /16. A validator
    that read host as a last octet would reject both or accept both.
    """
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {"a": {"network_ref": "inst.vlan.big", "address": {"allocation": "static", "host": 300}}},
        }
    )
    rows[0] = _domain("inst.vlan.big", "10.4.0.0/16")

    assert _run(rows).diagnostics == []


@pytest.mark.parametrize("host", [0, 255])
def test_the_network_and_broadcast_offsets_are_refused(host: int) -> None:
    """Neither is assignable, and an address that fails on the device is expensive."""
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {"a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": host}}},
        }
    )

    assert "E7024" in _codes(_run(rows))


def test_a_point_to_point_prefix_admits_both_addresses() -> None:
    """RFC 3021: a /31 has no network or broadcast address to set aside."""
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.p2p", "address": {"allocation": "static", "host": 0}},
            },
        }
    )
    rows[0] = _domain("inst.vlan.p2p", "10.9.9.0/31")

    assert _run(rows).diagnostics == []


def test_a_dynamic_address_is_not_range_checked() -> None:
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {"a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "dynamic"}}},
        }
    )

    assert _run(rows).diagnostics == []


# --- default routes ----------------------------------------------------------


def test_two_default_routes_in_one_family_are_refused() -> None:
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.lan", "default_route": True},
                "b": {"network_ref": "inst.vlan.dmz", "default_route": True},
            },
        }
    )
    rows.append(_domain("inst.vlan.dmz", "10.0.30.0/24"))

    result = _run(rows)

    assert "E7021" in _codes(result)
    assert any("default_route for ipv4" in diag.message for diag in result.diagnostics)


def test_one_default_route_per_family_is_correct_for_dual_stack() -> None:
    """The case a per-workload count would wrongly reject.

    The rule is one default per address family, not one per workload. Family is
    derived from the referenced domain's prefix, so this passes and the v4-only
    pair above does not.
    """
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "v4": {"network_ref": "inst.vlan.lan", "default_route": True},
                "v6": {"network_ref": "inst.vlan.lan6", "default_route": True},
            },
        }
    )
    rows.append(_domain("inst.vlan.lan6", "2001:db8:20::/64"))

    assert _run(rows).diagnostics == []


def test_a_disabled_attachment_does_not_hold_a_default_route() -> None:
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.lan", "default_route": True},
                "b": {"enabled": False, "network_ref": "inst.vlan.dmz", "default_route": True},
            },
        }
    )
    rows.append(_domain("inst.vlan.dmz", "10.0.30.0/24"))

    assert _run(rows).diagnostics == []


def test_a_domain_with_an_unreadable_prefix_is_not_a_family_match() -> None:
    """Two unknown families are not thereby the same family."""
    rows = _workload(
        {
            "schema_version": 2,
            "attachments": {
                "a": {"network_ref": "inst.vlan.junk1", "default_route": True},
                "b": {"network_ref": "inst.vlan.junk2", "default_route": True},
            },
        }
    )
    rows[0] = _domain("inst.vlan.junk1", "not-a-prefix")
    rows.append(_domain("inst.vlan.junk2", "also-not-a-prefix"))

    assert "E7021" not in _codes(_run(rows))


# --- the second forcing function ---------------------------------------------


def test_the_plugin_resolver_agrees_with_the_reference_model() -> None:
    """The address algebra also exists twice, for the same distribution reason.

    Compared by arithmetic over chosen offsets, never by enumeration: asking an
    IPv6 /64 for its host list allocates 2**64 addresses and takes the machine
    down with it.
    """
    sys.path.insert(0, str(REPO_ROOT))
    import ipaddress

    from netmodel.domains import AddressDomain, DomainError
    from netmodel.domains import offset_range as model_offset_range

    from plugins.validators.address_domain_helper import AddressDomainError, parse_prefix, resolve_offset

    prefixes = [
        "10.0.20.0/24",
        "10.4.0.0/16",
        "10.0.20.0/30",
        "10.0.20.0/31",
        "10.0.20.5/32",
        "2001:db8::/64",
        "2001:db8::/127",
        "2001:db8::1/128",
    ]

    for cidr in prefixes:
        network = ipaddress.ip_network(cidr, strict=False)
        assert parse_prefix(cidr).offset_range == model_offset_range(network), cidr

        low, high = model_offset_range(network)
        domain = AddressDomain(domain_id="inst.probe", kind="vlan", prefix=network)
        for offset in {low, high, low - 1, high + 1, 0, 1, 300}:
            try:
                plugin_result = resolve_offset(cidr, offset)
            except AddressDomainError:
                plugin_result = None
            try:
                model_result = str(domain.resolve_host(offset))
            except DomainError:
                model_result = None

            assert plugin_result == model_result, f"{cidr} offset {offset}: {plugin_result} vs {model_result}"

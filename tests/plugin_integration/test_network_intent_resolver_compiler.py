#!/usr/bin/env python3
"""The compiler that publishes resolved v2 attachments and their provenance.

Executed through the registry, which is the only proof it loads: a compiler that
publishes an empty channel because it never ran is indistinguishable, in a
compile summary, from one that ran over v1-only sources and correctly found
nothing.

The resolution rules themselves are the reference model's, and a differential in
`tests/netmodel/test_resolve.py` holds the two in agreement. What is checked here
is the part only the plugin has: what it reads, what it publishes, and what it
refuses to guess.
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

from tests.helpers.plugin_execution import publish_for_test  # noqa: E402

PLUGIN_ID = "base.compiler.network_intent_resolver"
CHANNEL = "resolved_network_intent"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _domain(instance: str, cidr: str | None, gateway: str | None = None) -> dict:
    extensions: dict = {}
    if cidr is not None:
        extensions["cidr"] = cidr
    if gateway is not None:
        extensions["gateway"] = gateway
    return {
        "group": "network",
        "instance": instance,
        "class_ref": "class.network.vlan",
        "layer": "L2",
        "extensions": extensions,
    }


def _workload(attachments: dict, *, schema_version: int | None = 2) -> dict:
    block: dict = {"attachments": attachments}
    if schema_version is not None:
        block["schema_version"] = schema_version
    return {
        "group": "lxc",
        "instance": "lxc-a",
        "class_ref": "class.compute.workload.lxc",
        "layer": "L4",
        "extensions": {"network": block},
    }


def _run(rows: list[dict]):
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", copy.deepcopy(rows))
    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)
    assert result.status == PluginStatus.SUCCESS

    # Read the plugin's own result. `subscribe` needs an active execution scope
    # that is gone by assertion time, and reaching into the publish registry is
    # banned by contract - it couples a test to a private structure the envelope
    # contract exists to replace.
    return result.output_data[CHANNEL]


LAN = _domain("inst.vlan.lan", "192.168.88.0/24", "192.168.88.1")
SHIFTED = _domain("inst.vlan.shifted", "10.0.30.128/25")
BARE = _domain("inst.vlan.bare", None)


# --- it exists and runs --------------------------------------------------------


def test_the_plugin_is_registered_and_publishes_its_channel() -> None:
    registry = _registry()

    assert PLUGIN_ID in registry.specs
    assert registry.specs[PLUGIN_ID].produces[0]["key"] == CHANNEL

    published = _run([])
    assert published == {"schema_version": 2, "attachments": [], "unresolved": []}


def test_a_v1_source_publishes_nothing() -> None:
    """Every source in the tree is v1; the channel must stay empty for them."""
    row = {
        "group": "lxc",
        "instance": "lxc-legacy",
        "class_ref": "class.compute.workload.lxc",
        "layer": "L4",
        "extensions": {"network": {"vlan_ref": "inst.vlan.lan", "host": 20}},
    }

    published = _run([LAN, row])

    assert published["attachments"] == []
    assert published["unresolved"] == []


def test_a_block_without_a_version_is_not_treated_as_v2() -> None:
    rows = [LAN, _workload({"a": {"network_ref": "inst.vlan.lan"}}, schema_version=None)]

    assert _run(rows)["attachments"] == []


# --- what it resolves ----------------------------------------------------------


def test_an_address_is_the_offset_from_the_network_address() -> None:
    rows = [LAN, _workload({"a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 20}}})]

    entry = _run(rows)["attachments"][0]

    assert entry["address"] == "192.168.88.20"
    assert entry["gateway"] == "192.168.88.1"
    assert entry["address_family"] == "ipv4"


def test_a_shifted_subnet_resolves_inside_itself() -> None:
    """The case the legacy path gets wrong, silently."""
    rows = [
        SHIFTED,
        _workload({"a": {"network_ref": "inst.vlan.shifted", "address": {"allocation": "static", "host": 10}}}),
    ]

    entry = _run(rows)["attachments"][0]

    assert entry["address"] == "10.0.30.138"


def test_the_source_map_names_what_produced_each_value() -> None:
    rows = [LAN, _workload({"a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 20}}})]

    source_map = _run(rows)["attachments"][0]["source_map"]

    assert source_map["address"] == (
        "derived from inst.vlan.lan (offset 20 from the network address of 192.168.88.0/24)"
    )
    assert source_map["gateway"] == "derived from inst.vlan.lan (declared on the address domain)"
    assert source_map["address_family"] == "derived from inst.vlan.lan (the version of the domain's prefix)"
    assert "authored at lxc-a" in source_map["network_ref"]


# --- what it refuses to guess --------------------------------------------------


def test_a_dynamic_allocation_yields_no_address() -> None:
    rows = [LAN, _workload({"a": {"network_ref": "inst.vlan.lan", "address": {"allocation": "dynamic"}}})]

    entry = _run(rows)["attachments"][0]

    assert entry["address"] is None
    assert entry["allocation"] == "dynamic"
    assert entry["address_family"] == "ipv4"


def test_a_domain_without_a_gateway_yields_none_not_the_first_address() -> None:
    """The legacy path defaulted to .1 and put gateways outside their network."""
    rows = [
        SHIFTED,
        _workload({"a": {"network_ref": "inst.vlan.shifted", "address": {"allocation": "static", "host": 10}}}),
    ]

    assert _run(rows)["attachments"][0]["gateway"] is None


@pytest.mark.parametrize(
    ("attachment", "domain", "reason"),
    [
        ({"network_ref": "inst.vlan.ghost"}, None, "not a modeled address domain"),
        ({"interface": "eth0"}, None, "no network_ref"),
        (
            {"network_ref": "inst.vlan.bare", "address": {"allocation": "static", "host": 5}},
            BARE,
            "declares no prefix",
        ),
        (
            {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": 300}},
            None,
            "outside",
        ),
        (
            {"network_ref": "inst.vlan.lan", "address": {"allocation": "static", "host": "20"}},
            None,
            "integer host offset",
        ),
    ],
)
def test_an_unresolvable_attachment_is_recorded_with_its_reason(attachment, domain, reason: str) -> None:
    """Published as unresolved, never as a partial record.

    This runs before the validate stage, so the fault is reported by
    base.validator.network_intent_schema with the right diagnostic code. Failing
    here as well would report one fault twice.
    """
    rows = [LAN, _workload({"a": attachment})]
    if domain is not None:
        rows.append(domain)

    published = _run(rows)

    assert published["attachments"] == []
    assert len(published["unresolved"]) == 1
    assert reason in published["unresolved"][0]["reason"]
    assert published["unresolved"][0]["path"] == "lxc-a.network.attachments.a"


def test_a_disabled_attachment_is_neither_resolved_nor_reported() -> None:
    rows = [LAN, _workload({"a": {"enabled": False, "network_ref": "inst.vlan.ghost"}})]

    published = _run(rows)

    assert published["attachments"] == []
    assert published["unresolved"] == []


def test_the_compiler_never_fails_the_stage_on_a_bad_attachment() -> None:
    """Its job is to publish, not to diagnose; the validator owns the codes."""
    registry = _registry()
    ctx = _context()
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [_workload({"a": {"network_ref": "inst.vlan.ghost"}})],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_the_plugin_and_the_validator_share_one_resolver() -> None:
    """Two copies of this arithmetic is how the legacy split happened."""
    import plugins.compilers.network_intent_resolver_compiler as compiler
    import plugins.validators.network_intent_schema_validator as validator

    assert compiler.resolve_offset is validator.resolve_offset

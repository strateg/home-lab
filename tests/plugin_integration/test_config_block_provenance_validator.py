#!/usr/bin/env python3
"""Integration tests for the config-block provenance validator (ADR 0120 D6).

The rule under test: a block that speaks device configuration must name the
plugin that consumes it, or declare itself documentation. The regression it
guards is measured - `inst.tunnel.wg-exit.chateau_routing` declared rules for
four road-warrior addresses that no plugin read, and two of those paths were
enforced by nothing at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.config_block_provenance"
REAL_CONSUMER = "object.mikrotik.generator.terraform"


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


def _row(extensions: dict) -> dict:
    return {
        "group": "network",
        "instance": "inst.routing_policy.example",
        "class_ref": "class.network.routing_policy",
        "layer": "L3",
        "object_ref": "obj.network.routing_policy.vpn_vlan",
        "extensions": extensions,
    }


def _run(rows: list[dict]):
    registry = _registry()
    ctx = _context()
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)
    return registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)


def test_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    consumes = registry.specs[PLUGIN_ID].consumes[0]
    assert consumes["key"] == "normalized_rows"
    assert consumes["required"] is True


def test_nested_config_block_without_a_declared_consumer_is_refused() -> None:
    result = _run([_row({"mikrotik_config": {"mangle_rules": [{"chain": "prerouting"}]}})])

    assert result.status == PluginStatus.FAILED
    assert [diag.code for diag in result.diagnostics] == ["E8420"]
    assert "mikrotik_config.mangle_rules" in result.diagnostics[0].path


def test_top_level_config_block_without_a_declared_consumer_is_refused() -> None:
    result = _run([_row({"nat_rules": [{"chain": "dstnat"}]})])

    assert result.status == PluginStatus.FAILED
    assert [diag.code for diag in result.diagnostics] == ["E8420"]
    # The path names the block once, not twice: a top-level block is its own container.
    assert result.diagnostics[0].path.endswith(".nat_rules")


def test_a_named_existing_consumer_satisfies_the_rule() -> None:
    result = _run(
        [
            _row(
                {
                    "mikrotik_config": {"firewall_rules": [{"chain": "forward"}]},
                    "config_block_provenance": {"mikrotik_config": REAL_CONSUMER},
                }
            )
        ]
    )

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_documentation_satisfies_the_rule() -> None:
    result = _run(
        [
            _row(
                {
                    "chateau_routing": {"mangle_rules": [{"chain": "prerouting"}]},
                    "config_block_provenance": {"chateau_routing": "documentation"},
                }
            )
        ]
    )

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_a_consumer_that_no_manifest_declares_is_refused() -> None:
    result = _run(
        [
            _row(
                {
                    "mikrotik_config": {"firewall_rules": [{"chain": "forward"}]},
                    "config_block_provenance": {"mikrotik_config": "object.nowhere.generator.imaginary"},
                }
            )
        ]
    )

    assert result.status == PluginStatus.FAILED
    assert [diag.code for diag in result.diagnostics] == ["E8421"]


def test_a_non_string_declaration_is_refused() -> None:
    result = _run(
        [
            _row(
                {
                    "mikrotik_config": {"firewall_rules": [{"chain": "forward"}]},
                    "config_block_provenance": {"mikrotik_config": True},
                }
            )
        ]
    )

    assert result.status == PluginStatus.FAILED
    assert [diag.code for diag in result.diagnostics] == ["E8421"]


def test_the_provenance_map_is_not_itself_treated_as_configuration() -> None:
    """Its keys are container names, and some container names are block names.

    Walking into it reported `config_block_provenance.nat_rules` as an
    unattributed config block - a self-inflicted finding that would make the
    rule impossible to satisfy for a top-level block.
    """
    result = _run([_row({"nat_rules": [{"chain": "dstnat"}], "config_block_provenance": {"nat_rules": REAL_CONSUMER}})])

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_instance_data_rows_are_checked_too() -> None:
    """Both row shapes carry authored data, so both are subject to the rule."""
    row = {
        "group": "routeros_container",
        "instance": "docker-example",
        "instance_data": {"nat_rules": [{"chain": "dstnat"}]},
    }

    result = _run([row])

    assert result.status == PluginStatus.FAILED
    assert [diag.code for diag in result.diagnostics] == ["E8420"]


def test_an_instance_without_config_blocks_is_untouched() -> None:
    result = _run([_row({"vlan_id": 30, "cidr": "10.0.30.0/24"})])

    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []

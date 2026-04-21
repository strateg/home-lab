#!/usr/bin/env python3
"""Integration tests for network IP overlap validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.network_ip_overlap"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_network_ip_overlap_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def test_network_ip_overlap_validator_accepts_unique_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"instance": "inst.router.a", "ip_address": "192.168.10.1/24"},
            {"instance": "inst.router.b", "ip_address": "192.168.10.2/24"},
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_network_ip_overlap_validator_reports_duplicate_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {"instance": "inst.router.a", "ip_address": "10.0.0.1/24"},
            {"instance": "inst.router.b", "management_ip": "10.0.0.1"},
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7816" for diag in result.diagnostics)


def test_network_ip_overlap_validator_ignores_reference_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "instance": "lxc-postgresql",
                "extensions": {"network": {"ip": "10.0.30.10/24", "gateway": "10.0.30.1"}},
            },
            {
                "instance": "svc-postgresql",
                "extensions": {"config": {"postgresql_listen_addresses": "10.0.30.10"}},
            },
            {
                "instance": "lxc-redis",
                "extensions": {"network": {"ip": "10.0.30.11/24", "gateway": "10.0.30.1"}},
            },
            {
                "instance": "docker-nginx",
                "extensions": {
                    "network": {"ip": "172.18.0.2/24", "gateway": "172.18.0.1"},
                    "nat_rules": [{"to_address": "172.18.0.2"}],
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(diag.code == "W7816" for diag in result.diagnostics)


def test_network_ip_overlap_validator_reports_duplicate_network_ip_allocations_as_error():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "vlan-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "extensions": {
                    "ip_allocations": [
                        {"ip": "10.20.30.10/24", "device_ref": "srv-a"},
                        {"ip": "10.20.30.10/24", "vm_ref": "vm-a"},
                    ]
                },
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_network_ip_overlap_validator_reports_duplicate_network_ip_allocations_from_top_level_payload():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "network",
                "instance": "vlan-a",
                "class_ref": "class.network.vlan",
                "layer": "L2",
                "ip_allocations": [
                    {"ip": "10.20.30.11/24", "device_ref": "srv-a"},
                    {"ip": "10.20.30.11/24", "lxc_ref": "lxc-a"},
                ],
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7817" for diag in result.diagnostics)


def test_network_ip_overlap_validator_requires_compiler_rows():
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_network_ip_overlap_validator_ignores_observed_runtime_ips():
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "instance": "rtr-mikrotik-chateau",
                "extensions": {
                    "observed_runtime": {
                        "containers": {"bridge_ip": "172.18.0.1"},
                    }
                },
            },
            {
                "instance": "docker-nginx",
                "extensions": {
                    "network": {"gateway": "172.18.0.1"},
                },
            },
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert not any(diag.code == "W7816" for diag in result.diagnostics)


def test_network_ip_overlap_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/instance_rows_compiler.py').as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": f"{(V5_TOOLS / 'plugins/validators/network_ip_overlap_validator.py').as_posix()}:NetworkIpOverlapValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 116,
                "depends_on": ["base.compiler.instance_rows"],
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)

#!/usr/bin/env python3
"""Integration checks for docs generator plugin."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.generator.docs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _context(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "srv-a",
                    "object_ref": "obj.proxmox.ve",
                    "class_ref": "class.compute.hypervisor",
                    "layer": "L1",
                    "status": "mapped",
                }
            ],
            "services": [
                {
                    "instance_id": "svc-a",
                    "object_ref": "obj.service.web",
                    "class_ref": "class.service.web_ui",
                    "status": "mapped",
                    "runtime": {"type": "docker", "target_ref": "srv-a", "network_binding_ref": "inst.vlan.servers"},
                }
            ],
            "lxc": [],
            "vm": [],
            "vms": [],
            "network": [],
        }
    }


def _semanticize(compiled_json: dict) -> dict:
    payload = copy.deepcopy(compiled_json)
    instances = payload.get("instances")
    if not isinstance(instances, dict):
        return payload
    for rows in instances.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            object_ref = row.pop("object_ref", None)
            class_ref = row.pop("class_ref", None)
            if not isinstance(object_ref, str) and not isinstance(class_ref, str):
                continue
            instance_block = row.get("instance")
            if not isinstance(instance_block, dict):
                instance_block = {}
                row["instance"] = instance_block
            if isinstance(object_ref, str) and object_ref:
                instance_block.setdefault("materializes_object", object_ref)
            if isinstance(class_ref, str) and class_ref:
                instance_block.setdefault("materializes_class", class_ref)
    return payload


def test_docs_generator_writes_expected_files(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(tmp_path, _compiled_fixture())

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    docs_root = tmp_path / "generated" / "docs"
    assert (docs_root / "overview.md").exists()
    assert (docs_root / "devices.md").exists()
    assert (docs_root / "services.md").exists()
    assert (docs_root / "network-diagram.md").exists()
    assert (docs_root / "ip-allocation.md").exists()
    assert (docs_root / "dns-dhcp-overview.md").exists()
    assert (docs_root / "rack-layout.md").exists()
    assert (docs_root / "vlan-topology.md").exists()
    assert (docs_root / "trust-zones.md").exists()
    assert (docs_root / "trust-zone-firewall-policy.md").exists()
    assert (docs_root / "security-posture-matrix.md").exists()
    assert (docs_root / "service-dependencies.md").exists()
    assert (docs_root / "storage-topology.md").exists()
    assert (docs_root / "data-flow-topology.md").exists()
    assert (docs_root / "monitoring-topology.md").exists()
    assert (docs_root / "vpn-topology.md").exists()
    assert (docs_root / "qos-topology.md").exists()
    assert (docs_root / "ups-topology.md").exists()
    assert (docs_root / "backup-schedule.md").exists()
    assert (docs_root / "_generated_files.txt").exists()

    overview = (docs_root / "overview.md").read_text(encoding="utf-8")
    assert "| Devices | 1 |" in overview
    assert "| Services | 1 |" in overview
    services = (docs_root / "services.md").read_text(encoding="utf-8")
    assert "svc-a" in services
    assert "docker" in services
    network = (docs_root / "network-diagram.md").read_text(encoding="utf-8")
    assert "Network Inventory" in network


def test_docs_generator_reports_projection_error(tmp_path: Path) -> None:
    registry = _registry()
    ctx = _context(tmp_path, {"instances": {"devices": [{}]}})

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9701" for diag in result.diagnostics)


def test_docs_manifest_depends_on_effective_model() -> None:
    registry = _registry()

    assert registry.specs[PLUGIN_ID].depends_on == ["base.compiler.effective_model"]


def test_docs_execute_stage_commits_generated_payloads(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.effective_model",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
            },
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(V5_TOOLS / 'plugins/generators/docs_generator.py').as_posix()}:DocsGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "post",
                "order": 220,
                "depends_on": ["base.compiler.effective_model"],
                "subinterpreter_compatible": True,
                "produces": [
                    {"key": "generated_dir", "scope": "pipeline_shared"},
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "docs_files", "scope": "pipeline_shared"},
                    {"key": "docs_projection", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context(tmp_path, _compiled_fixture())

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    payload = results[0].output_data
    assert payload["docs_dir"].endswith("generated/docs")
    assert any(path.endswith("overview.md") for path in payload["docs_files"])
    assert any(path.endswith("services.md") for path in payload["docs_files"])


def test_docs_execute_stage_requires_compiled_json(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.effective_model",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
            },
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(V5_TOOLS / 'plugins/generators/docs_generator.py').as_posix()}:DocsGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "post",
                "order": 220,
                "depends_on": ["base.compiler.effective_model"],
                "subinterpreter_compatible": True,
                "produces": [
                    {"key": "generated_dir", "scope": "pipeline_shared"},
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "docs_files", "scope": "pipeline_shared"},
                    {"key": "docs_projection", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context(tmp_path, {})

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E3001" for diag in results[0].diagnostics)
    assert not ctx.get_published_keys(PLUGIN_ID)

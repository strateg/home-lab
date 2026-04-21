#!/usr/bin/env python3
"""Integration checks for Mermaid diagram generator plugin."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(TOOLS_ROOT))

from kernel import PluginRegistry
from kernel.plugin_base import PluginContext, PluginStatus, Stage


def _load_generator_class():
    module_path = TOOLS_ROOT / "plugins" / "generators" / "diagram_generator.py"
    spec = importlib.util.spec_from_file_location("test_diagram_generator_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DiagramGenerator


DiagramGenerator = _load_generator_class()
PLUGIN_ID = "base.generator.diagrams"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(TOOLS_ROOT)
    registry.load_manifest(TOOLS_ROOT / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "mermaid_icon_mode": "none",
        },
    )


def _run_generator(generator: DiagramGenerator, ctx: PluginContext):
    from tests.helpers.plugin_execution import run_plugin_for_test

    return run_plugin_for_test(generator, ctx, Stage.GENERATE)


def _compiled_fixture() -> dict:
    return _semanticize(
        {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-slate",
                        "class_ref": "class.network.router",
                        "object_ref": "obj.glinet.slate_ax1800",
                        "layer": "L1",
                        "status": "mapped",
                    },
                    {
                        "instance_id": "srv-gamayun",
                        "class_ref": "class.compute.hypervisor",
                        "object_ref": "obj.proxmox.ve",
                        "layer": "L1",
                        "status": "mapped",
                    },
                ],
                "network": [
                    {
                        "instance_id": "inst.trust_zone.servers",
                        "class_ref": "class.network.trust_zone",
                        "object_ref": "obj.network.trust_zone.servers",
                        "status": "mapped",
                    },
                    {
                        "instance_id": "inst.vlan.servers",
                        "class_ref": "class.network.vlan",
                        "object_ref": "obj.network.vlan.servers",
                        "status": "mapped",
                        "instance_data": {
                            "vlan_id": 30,
                            "cidr": "10.0.30.0/24",
                            "gateway": "10.0.30.1",
                            "trust_zone_ref": "inst.trust_zone.servers",
                        },
                    },
                    {
                        "instance_id": "inst.data_link.rtr_to_hv",
                        "class_ref": "class.network.data_link",
                        "object_ref": "obj.network.ethernet_link",
                        "status": "mapped",
                        "instance_data": {
                            "endpoint_a": {"device_ref": "rtr-slate"},
                            "endpoint_b": {"device_ref": "srv-gamayun"},
                            "medium": "ethernet",
                            "speed_mbps": 1000,
                        },
                    },
                ],
                "services": [
                    {
                        "instance_id": "svc-prometheus",
                        "class_ref": "class.service.monitoring",
                        "object_ref": "obj.service.prometheus",
                        "status": "mapped",
                        "runtime": {"type": "container", "target_ref": "lxc-prometheus"},
                    }
                ],
                "lxc": [
                    {
                        "instance_id": "lxc-prometheus",
                        "class_ref": "class.compute.workload.lxc",
                        "object_ref": "obj.proxmox.lxc.debian12.prometheus",
                        "status": "mapped",
                        "instance_data": {
                            "hostname": "prometheus",
                            "host_ref": "srv-gamayun",
                            "trust_zone_ref": "inst.trust_zone.servers",
                        },
                    }
                ],
                "vm": [],
                "vms": [],
            }
        }
    )


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


def test_diagram_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = DiagramGenerator("base.generator.diagrams")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = _run_generator(generator, ctx)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "docs" / "diagrams"
    expected_files = {
        "physical-topology.md",
        "network-topology.md",
        "icon-legend.md",
        "index.md",
        "_generated_files.txt",
    }
    assert expected_files.issubset({path.name for path in target_dir.iterdir()})

    physical = (target_dir / "physical-topology.md").read_text(encoding="utf-8")
    assert "rtr-slate" in physical
    assert "srv-gamayun" in physical


def test_diagram_generator_supports_icon_mode_override_via_env(tmp_path: Path) -> None:
    generator = DiagramGenerator("base.generator.diagrams")
    ctx = _ctx(tmp_path, _compiled_fixture())

    prev = os.environ.get("V5_DIAGRAM_ICON_MODE")
    os.environ["V5_DIAGRAM_ICON_MODE"] = "icon-nodes"
    try:
        result = _run_generator(generator, ctx)
    finally:
        if prev is None:
            os.environ.pop("V5_DIAGRAM_ICON_MODE", None)
        else:
            os.environ["V5_DIAGRAM_ICON_MODE"] = prev

    assert result.status == PluginStatus.SUCCESS
    network = (tmp_path / "generated" / "docs" / "diagrams" / "network-topology.md").read_text(encoding="utf-8")
    assert "@{ icon:" in network


def test_diagram_generator_emits_icon_cache_manifest_in_icon_node_mode(tmp_path: Path) -> None:
    icon_pack = {
        "prefix": "mdi",
        "width": 24,
        "height": 24,
        "icons": {
            "router-network": {"body": "<path d='M1 1h22v22H1z'/>"},
            "shield-half-full": {"body": "<path d='M2 2h20v20H2z'/>"},
            "lan": {"body": "<path d='M3 3h18v18H3z'/>"},
            "bridge": {"body": "<path d='M4 4h16v16H4z'/>"},
            "cube-outline": {"body": "<path d='M5 5h14v14H5z'/>"},
            "chart-line": {"body": "<path d='M6 6h12v12H6z'/>"},
        },
    }
    pack_dir = tmp_path / "workspace" / "node_modules" / "@iconify-json" / "mdi"
    pack_dir.mkdir(parents=True)
    (pack_dir / "icons.json").write_text(json.dumps(icon_pack), encoding="utf-8")

    generator = DiagramGenerator("base.generator.diagrams")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_compiled_fixture(),
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "mermaid_icon_mode": "icon-nodes",
            "icon_pack_search_roots": [str(tmp_path / "workspace")],
        },
    )

    result = _run_generator(generator, ctx)

    assert result.status == PluginStatus.SUCCESS
    cache_root = tmp_path / "generated" / "docs" / "diagrams" / "icons"
    manifest_path = cache_root / "icon-cache.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["icons_total"] > 0
    assert manifest["icons_resolved"] > 0
    assert "mdi" in manifest["packs_loaded"]


def test_diagram_generator_uses_embedded_fallback_icons_when_packs_missing(tmp_path: Path) -> None:
    generator = DiagramGenerator("base.generator.diagrams")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_compiled_fixture(),
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "mermaid_icon_mode": "icon-nodes",
            "icon_pack_search_roots": [str(tmp_path / "workspace-without-packs")],
        },
    )

    result = _run_generator(generator, ctx)

    assert result.status == PluginStatus.SUCCESS
    cache_root = tmp_path / "generated" / "docs" / "diagrams" / "icons"
    manifest = json.loads((cache_root / "icon-cache.json").read_text(encoding="utf-8"))
    assert manifest["icons_total"] > 0
    assert manifest["icons_resolved_via_fallback"] > 0
    assert manifest["icons_unresolved"] == 0


def test_diagram_manifest_depends_on_effective_model() -> None:
    registry = _registry()

    assert registry.specs[PLUGIN_ID].depends_on == ["base.compiler.effective_model"]


def test_diagram_execute_stage_commits_generated_payloads(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.effective_model",
                "kind": "compiler",
                "entry": f"{(TOOLS_ROOT / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
            },
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(TOOLS_ROOT / 'plugins/generators/diagram_generator.py').as_posix()}:DiagramGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "post",
                "order": 225,
                "depends_on": ["base.compiler.effective_model"],
                "subinterpreter_compatible": True,
                "config": {"mermaid_icon_mode": "none"},
                "produces": [
                    {"key": "diagram_dir", "scope": "pipeline_shared"},
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "diagram_files", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(TOOLS_ROOT)
    registry.load_manifest(manifest)
    ctx = _ctx(tmp_path, _compiled_fixture())

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    payload = results[0].output_data
    assert payload["diagram_dir"].endswith("generated/docs/diagrams")
    assert any(path.endswith("physical-topology.md") for path in payload["diagram_files"])
    assert any(path.endswith("index.md") for path in payload["diagram_files"])


def test_diagram_execute_stage_requires_compiled_json(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.effective_model",
                "kind": "compiler",
                "entry": f"{(TOOLS_ROOT / 'plugins/compilers/effective_model_compiler.py').as_posix()}:EffectiveModelCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 60,
            },
            {
                "id": PLUGIN_ID,
                "kind": "generator",
                "entry": f"{(TOOLS_ROOT / 'plugins/generators/diagram_generator.py').as_posix()}:DiagramGenerator",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "post",
                "order": 225,
                "depends_on": ["base.compiler.effective_model"],
                "subinterpreter_compatible": True,
                "config": {"mermaid_icon_mode": "none"},
                "produces": [
                    {"key": "diagram_dir", "scope": "pipeline_shared"},
                    {"key": "generated_files", "scope": "pipeline_shared"},
                    {"key": "diagram_files", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(TOOLS_ROOT)
    registry.load_manifest(manifest)
    ctx = _ctx(tmp_path, {})

    results = registry.execute_stage(Stage.GENERATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E3001" for diag in results[0].diagnostics)
    assert not ctx.get_published_keys(PLUGIN_ID)

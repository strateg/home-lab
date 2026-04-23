#!/usr/bin/env python3
"""Integration tests for foundation file placement validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.foundation_file_placement"

REQUIRED_INSTANCE_DIRS = (
    "L0-meta/meta",
    "L1-foundation/devices",
    "L1-foundation/firmware",
    "L1-foundation/physical-links",
    "L1-foundation/power",
    "L2-network/data-channels",
    "L2-network/network",
    "L3-data/pools",
    "L3-data/data-assets",
    "L4-platform/os",
    "L4-platform/lxc",
    "L4-platform/vm",
    "L5-application/services",
    "L6-observability/observability",
    "L7-operations/operations",
)


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(project_root: str | None) -> PluginContext:
    config = {"project_root": project_root} if project_root is not None else {}
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config=config,
    )


def _build_tree(root: Path) -> Path:
    instances_root = root / "topology" / "instances"
    for rel in REQUIRED_INSTANCE_DIRS:
        (instances_root / rel).mkdir(parents=True, exist_ok=True)
    return instances_root


def _write_instance(file_path: Path, *, instance: str, group: str, layer: str | None) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"@instance: {instance}",
        "@extends: obj.test.sample",
        f"group: {group}",
    ]
    if layer is not None:
        lines.append(f"@layer: {layer}")
    lines.append("@version: 1.0.0")
    file_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_object(file_path: Path, *, object_id: str, layer: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    class_file = file_path.parents[1] / "class-modules" / "class.test.sample.yaml"
    class_file.parent.mkdir(parents=True, exist_ok=True)
    class_file.write_text(
        "\n".join(
            (
                "@class: class.test.sample",
                f"@layer: {layer}",
                "@version: 1.0.0",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    file_path.write_text(
        "\n".join(
            (
                f"@object: {object_id}",
                "@extends: class.test.sample",
                f"@layer: {layer}",
                "@version: 1.0.0",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def test_foundation_file_placement_validator_accepts_valid_layout(tmp_path: Path):
    instances_root = _build_tree(tmp_path)
    _write_instance(
        instances_root / "L1-foundation" / "devices" / "rtr-core.yaml",
        instance="rtr-core",
        group="devices",
        layer="L1",
    )

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_file_placement_validator_warns_on_layer_dir_mismatch(tmp_path: Path):
    instances_root = _build_tree(tmp_path)
    _write_instance(
        instances_root / "L2-network" / "devices" / "rtr-core.yaml",
        instance="rtr-core",
        group="devices",
        layer="L1",
    )

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7901" for diag in result.diagnostics)


def test_foundation_file_placement_validator_warns_on_group_dir_mismatch(tmp_path: Path):
    instances_root = _build_tree(tmp_path)
    _write_instance(
        instances_root / "L1-foundation" / "firmware" / "rtr-core.yaml",
        instance="rtr-core",
        group="devices",
        layer="L1",
    )

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7901" for diag in result.diagnostics)


def test_foundation_file_placement_validator_warns_on_filename_instance_mismatch(tmp_path: Path):
    instances_root = _build_tree(tmp_path)
    _write_instance(
        instances_root / "L1-foundation" / "devices" / "wrong-name.yaml",
        instance="rtr-core",
        group="devices",
        layer="L1",
    )

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7901" for diag in result.diagnostics)


def test_foundation_file_placement_validator_warns_on_missing_placement_fields(tmp_path: Path):
    instances_root = _build_tree(tmp_path)
    file_path = instances_root / "L1-foundation" / "devices" / "rtr-core.yaml"
    file_path.write_text(
        "\n".join(
            (
                "@instance: rtr-core",
                "@extends: obj.test.sample",
                "@version: 1.0.0",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.PARTIAL
    assert any(diag.code == "W7901" for diag in result.diagnostics)


def test_foundation_file_placement_validator_derives_layer_from_object_when_missing(tmp_path: Path):
    instances_root = _build_tree(tmp_path)
    _write_object(
        tmp_path / "topology" / "object-modules" / "obj.test.sample.yaml",
        object_id="obj.test.sample",
        layer="L1",
    )
    _write_instance(
        instances_root / "L1-foundation" / "devices" / "rtr-core.yaml",
        instance="rtr-core",
        group="devices",
        layer=None,
    )

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_file_placement_validator_requires_project_root():
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(None), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7900" for diag in result.diagnostics)

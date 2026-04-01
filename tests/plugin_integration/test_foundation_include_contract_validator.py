#!/usr/bin/env python3
"""Integration tests for foundation include contract validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.foundation_include_contract"

REQUIRED_INSTANCE_DIRS = (
    "L0-meta/meta",
    "L1-foundation/devices",
    "L1-foundation/firmware",
    "L1-foundation/os",
    "L1-foundation/physical-links",
    "L1-foundation/power",
    "L2-network/data-channels",
    "L2-network/network",
    "L3-data/pools",
    "L3-data/data-assets",
    "L4-platform/lxc",
    "L4-platform/vms",
    "L5-application/services",
    "L6-observability/observability",
    "L7-operations/operations",
)


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(
    project_root: str | None,
    *,
    repo_root: str | None = None,
    project_manifest_path: str | None = None,
    topology_path: str = "topology/topology.yaml",
) -> PluginContext:
    config = {}
    if project_root is not None:
        config["project_root"] = project_root
    if repo_root is not None:
        config["repo_root"] = repo_root
    if project_manifest_path is not None:
        config["project_manifest_path"] = project_manifest_path
    return PluginContext(
        topology_path=topology_path,
        profile="test",
        model_lock={},
        raw_yaml={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config=config,
    )


def _build_tree(root: Path, *, direct_instances_root: bool = False) -> None:
    base = root if direct_instances_root else (root / "topology" / "instances")
    for rel in REQUIRED_INSTANCE_DIRS:
        (base / rel).mkdir(parents=True, exist_ok=True)


def test_foundation_include_contract_validator_accepts_valid_tree(tmp_path: Path):
    _build_tree(tmp_path)
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_include_contract_validator_rejects_missing_required_dir(tmp_path: Path):
    _build_tree(tmp_path)
    missing_dir = tmp_path / "topology" / "instances" / "L3-data" / "pools"
    missing_dir.rmdir()

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7846" for diag in result.diagnostics)


def test_foundation_include_contract_validator_rejects_manual_index_file(tmp_path: Path):
    _build_tree(tmp_path)
    index_file = tmp_path / "topology" / "instances" / "L1-foundation" / "devices" / "_index.yaml"
    index_file.write_text("{}", encoding="utf-8")

    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(str(tmp_path)), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7847" for diag in result.diagnostics)


def test_foundation_include_contract_validator_requires_project_root():
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(None), Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7845" for diag in result.diagnostics)


def test_foundation_include_contract_validator_resolves_relative_project_root_from_repo_root(tmp_path: Path):
    repo_root = tmp_path / "external-repo"
    project_root = repo_root / "home-lab"
    _build_tree(project_root)

    registry = _registry()
    result = registry.execute_plugin(
        PLUGIN_ID,
        _context("home-lab", repo_root=str(repo_root)),
        Stage.VALIDATE,
    )
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_include_contract_validator_resolves_relative_project_root_from_topology_parent(tmp_path: Path):
    repo_root = tmp_path / "external-repo"
    project_root = repo_root / "home-lab"
    _build_tree(project_root)
    topology_path = repo_root / "topology.yaml"
    topology_path.write_text("version: 5.0.0\n", encoding="utf-8")

    registry = _registry()
    result = registry.execute_plugin(
        PLUGIN_ID,
        _context("home-lab", topology_path=str(topology_path)),
        Stage.VALIDATE,
    )
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_include_contract_validator_uses_instances_root_from_project_manifest(tmp_path: Path):
    repo_root = tmp_path / "external-repo"
    project_root = repo_root / "home-lab"
    instances_root = tmp_path / "shared-instances"
    _build_tree(instances_root, direct_instances_root=True)

    project_root.mkdir(parents=True, exist_ok=True)
    project_manifest = project_root / "project.yaml"
    project_manifest.write_text(f"instances_root: {instances_root.as_posix()}\n", encoding="utf-8")

    registry = _registry()
    result = registry.execute_plugin(
        PLUGIN_ID,
        _context(
            "home-lab",
            repo_root=str(repo_root),
            project_manifest_path=str(project_manifest),
        ),
        Stage.VALIDATE,
    )
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_foundation_include_contract_validator_resolves_relative_instances_root_from_manifest(tmp_path: Path):
    repo_root = tmp_path / "external-repo"
    project_root = repo_root / "home-lab"
    instances_root = project_root / "custom-instances"
    _build_tree(instances_root, direct_instances_root=True)

    project_root.mkdir(parents=True, exist_ok=True)
    project_manifest = project_root / "project.yaml"
    project_manifest.write_text("instances_root: custom-instances\n", encoding="utf-8")

    registry = _registry()
    result = registry.execute_plugin(
        PLUGIN_ID,
        _context(
            "home-lab",
            repo_root=str(repo_root),
            project_manifest_path=str(project_manifest),
        ),
        Stage.VALIDATE,
    )
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []

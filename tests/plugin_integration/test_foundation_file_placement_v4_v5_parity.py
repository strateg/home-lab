#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 file placement warning semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

V4_FOUNDATION_CHECKS = (
    Path(__file__).resolve().parents[3]
    / "v4"
    / "topology-tools"
    / "scripts"
    / "validators"
    / "checks"
    / "foundation.py"
)
V5_PLUGIN_ID = "base.validator.foundation_file_placement"

REQUIRED_INSTANCE_DIRS = (
    "L0-meta/meta",
    "L1-foundation/devices",
    "L1-foundation/firmware",
    "L1-foundation/os",
    "L1-foundation/physical-links",
    "L1-foundation/power",
    "L2-network/data-channels",
    "L2-network/network",
    "L3-data/storage",
    "L4-platform/lxc",
    "L4-platform/vms",
    "L5-application/services",
    "L6-observability/observability",
    "L7-operations/operations",
)


def _load_v4_foundation_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_foundation_checks", V4_FOUNDATION_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 foundation checks module from {V4_FOUNDATION_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(project_root: Path) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"project_root": str(project_root)},
    )


def _build_v5_instances_tree(project_root: Path) -> None:
    instances_root = project_root / "topology" / "instances"
    for rel in REQUIRED_INSTANCE_DIRS:
        (instances_root / rel).mkdir(parents=True, exist_ok=True)


def test_file_name_id_mismatch_warning_is_emitted_in_v4_and_v5(tmp_path: Path):
    v4_module = _load_v4_foundation_checks_module()
    v4_warnings: list[str] = []
    v4_messages: list[str] = []

    legacy_topology_root = tmp_path / "legacy"
    legacy_topology_root.mkdir(parents=True, exist_ok=True)
    (legacy_topology_root / "topology").mkdir(parents=True, exist_ok=True)
    topology_path = legacy_topology_root / "topology.yaml"
    topology_path.write_text("version: 4.0.0\n", encoding="utf-8")
    legacy_device_file = legacy_topology_root / "topology" / "L1-foundation" / "devices" / "wrong-name.yaml"
    legacy_device_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_device_file.write_text(
        "\n".join(
            (
                "id: rtr-core",
                "type: router",
                "role: edge",
                "class: network",
                "substrate: baremetal-owned",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    def _policy_get(_path: list[str], default: Any) -> Any:
        return default

    def _emit_by_severity(_severity: str, message: str) -> None:
        v4_messages.append(message)

    v4_module.check_file_placement(
        topology_path=topology_path,
        policy_get=_policy_get,
        emit_by_severity=_emit_by_severity,
        warnings=v4_warnings,
    )
    assert any("filename 'wrong-name' differs from id 'rtr-core'" in message for message in v4_messages)

    project_root = tmp_path / "v5-project"
    _build_v5_instances_tree(project_root)
    v5_instance_file = project_root / "topology" / "instances" / "L1-foundation" / "devices" / "wrong-name.yaml"
    v5_instance_file.write_text(
        "\n".join(
            (
                "instance: rtr-core",
                "object_ref: obj.test.sample",
                "group: devices",
                "layer: L1",
                "version: 1.0.0",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    registry = _registry()
    result = registry.execute_plugin(V5_PLUGIN_ID, _context(project_root), Stage.VALIDATE)
    assert any("should be named 'rtr-core.yaml'" in diag.message for diag in result.diagnostics)

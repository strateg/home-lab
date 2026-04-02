#!/usr/bin/env python3
"""Contract checks for projection ownership boundaries (ADR0078 WP10)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.object_projection_loader import discover_object_projection_paths  # noqa: E402

CORE_PROJECTIONS = V5_ROOT / "topology-tools" / "plugins" / "generators" / "projections.py"
MIKROTIK_PROJECTIONS = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "projections.py"
PROXMOX_PROJECTIONS = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "projections.py"
SHARED_BOOTSTRAP_PROJECTIONS = V5_ROOT / "topology-tools" / "plugins" / "generators" / "bootstrap_projections.py"

CORE_BUILDERS = {"build_ansible_projection", "build_docs_projection"}
OBJECT_BUILDERS = {"build_mikrotik_projection", "build_proxmox_projection"}
SHARED_BUILDERS = {"build_bootstrap_projection"}


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def test_core_projections_module_does_not_own_object_specific_builders() -> None:
    names = _function_names(CORE_PROJECTIONS)
    for name in CORE_BUILDERS:
        assert name in names, f"Core projection builder '{name}' missing in {CORE_PROJECTIONS}"
    leaked = sorted(name for name in (OBJECT_BUILDERS | SHARED_BUILDERS) if name in names)
    assert leaked == [], f"Core projections module must not define object/shared builders: {leaked}"


def test_object_projection_modules_do_not_define_core_builders() -> None:
    mikrotik_names = _function_names(MIKROTIK_PROJECTIONS)
    proxmox_names = _function_names(PROXMOX_PROJECTIONS)

    assert "build_mikrotik_projection" in mikrotik_names
    assert "build_proxmox_projection" in proxmox_names

    for core_builder in CORE_BUILDERS:
        assert (
            core_builder not in mikrotik_names
        ), f"MikroTik projection module must not define core builder '{core_builder}'"
        assert (
            core_builder not in proxmox_names
        ), f"Proxmox projection module must not define core builder '{core_builder}'"


def test_shared_bootstrap_projection_module_owns_bootstrap_builder_only() -> None:
    names = _function_names(SHARED_BOOTSTRAP_PROJECTIONS)
    assert "build_bootstrap_projection" in names
    leaked = sorted(name for name in (CORE_BUILDERS | OBJECT_BUILDERS) if name in names)
    assert leaked == [], f"Shared bootstrap module must not define core/object builders: {leaked}"


def test_object_projection_discovery_is_limited_to_object_modules_with_projections_file() -> None:
    discovered = discover_object_projection_paths()
    assert "mikrotik" in discovered
    assert "proxmox" in discovered
    assert "_shared" not in discovered, "Shared helper module must not be loaded as object projection module"

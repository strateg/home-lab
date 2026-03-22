#!/usr/bin/env python3
"""Side-by-side parity checks for v4/v5 governance warning semantics."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry
from kernel.plugin_base import Stage

V4_GOVERNANCE_CHECKS = (
    Path(__file__).resolve().parents[3] / "v4" / "topology-tools" / "scripts" / "validators" / "checks" / "governance.py"
)
V5_GOVERNANCE_PLUGIN_ID = "base.validator.governance_contract"


def _load_v4_governance_checks_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_governance_checks", V4_GOVERNANCE_CHECKS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v4 governance checks module from {V4_GOVERNANCE_CHECKS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(raw_yaml: dict[str, Any]) -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        raw_yaml=raw_yaml,
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def test_metadata_date_format_warning_is_emitted_in_v4_and_v5():
    v4_module = _load_v4_governance_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_l0_contracts(
        topology={
            "L0_meta": {
                "version": "4.0.0",
                "metadata": {"created": "2026/01/01", "last_updated": "2026-02-01"},
            }
        },
        ids={"security_policies": set(), "devices": set()},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("created/last_updated should use YYYY-MM-DD format" in message for message in v4_warnings)

    registry = _registry()
    result = registry.execute_plugin(
        V5_GOVERNANCE_PLUGIN_ID,
        _context(
            {
                "version": "5.0.0",
                "model": "class-object-instance",
                "framework": {
                    "class_modules_root": "v5/topology/class-modules",
                    "object_modules_root": "v5/topology/object-modules",
                    "model_lock": "v5/topology/model.lock.yaml",
                    "layer_contract": "v5/topology/layer-contract.yaml",
                    "capability_catalog": "v5/topology/class-modules/router/capability-catalog.yaml",
                    "capability_packs": "v5/topology/class-modules/router/capability-packs.yaml",
                },
                "project": {"active": "home-lab", "projects_root": "v5/projects"},
                "meta": {
                    "instance": "home-lab",
                    "status": "active",
                    "metadata": {"created": "2026/01/01", "last_updated": "2026-02-01"},
                },
            }
        ),
        Stage.VALIDATE,
    )
    assert any(diag.code == "W7809" for diag in result.diagnostics)


def test_changelog_missing_current_version_warning_is_emitted_in_v4_and_v5():
    v4_module = _load_v4_governance_checks_module()
    v4_errors: list[str] = []
    v4_warnings: list[str] = []
    v4_module.check_l0_contracts(
        topology={
            "L0_meta": {
                "version": "4.2.0",
                "metadata": {"created": "2026-01-01", "last_updated": "2026-02-01", "changelog": [{"version": "4.1.0"}]},
            }
        },
        ids={"security_policies": set(), "devices": set()},
        errors=v4_errors,
        warnings=v4_warnings,
    )
    assert any("changelog does not contain current version '4.2.0'" in message for message in v4_warnings)

    registry = _registry()
    result = registry.execute_plugin(
        V5_GOVERNANCE_PLUGIN_ID,
        _context(
            {
                "version": "5.2.0",
                "model": "class-object-instance",
                "framework": {
                    "class_modules_root": "v5/topology/class-modules",
                    "object_modules_root": "v5/topology/object-modules",
                    "model_lock": "v5/topology/model.lock.yaml",
                    "layer_contract": "v5/topology/layer-contract.yaml",
                    "capability_catalog": "v5/topology/class-modules/router/capability-catalog.yaml",
                    "capability_packs": "v5/topology/class-modules/router/capability-packs.yaml",
                },
                "project": {"active": "home-lab", "projects_root": "v5/projects"},
                "meta": {
                    "instance": "home-lab",
                    "status": "active",
                    "metadata": {"created": "2026-01-01", "last_updated": "2026-02-01", "changelog": [{"version": "5.1.0"}]},
                },
            }
        ),
        Stage.VALIDATE,
    )
    assert any(diag.code == "W7810" for diag in result.diagnostics)

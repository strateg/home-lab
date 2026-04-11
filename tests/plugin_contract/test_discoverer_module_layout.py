#!/usr/bin/env python3
"""Contract checks for discoverer module split layout."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
DISCOVERERS = V5_TOOLS / "plugins" / "discoverers"


def _load_module(module_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_base_manifest_points_discover_plugins_to_dedicated_modules() -> None:
    manifest = yaml.safe_load((V5_TOOLS / "plugins" / "plugins.yaml").read_text(encoding="utf-8"))
    plugins = {plugin["id"]: plugin for plugin in manifest["plugins"]}

    assert plugins["base.discover.manifest_loader"]["entry"] == (
        "discoverers/discover_manifest_loader.py:DiscoverManifestLoaderCompiler"
    )
    assert plugins["base.discover.inventory"]["entry"] == "discoverers/discover_inventory.py:DiscoverInventoryCompiler"
    assert plugins["base.discover.boundary"]["entry"] == "discoverers/discover_boundary.py:DiscoverBoundaryCompiler"
    assert plugins["base.discover.capability_preflight"]["entry"] == (
        "discoverers/discover_capability_preflight.py:DiscoverCapabilityPreflightCompiler"
    )


def test_discover_compiler_shim_reexports_split_classes() -> None:
    shim = _load_module(DISCOVERERS / "discover_compiler.py", "discover_compiler_shim_test")
    assert shim.DiscoverManifestLoaderCompiler.__name__ == "DiscoverManifestLoaderCompiler"
    assert shim.DiscoverInventoryCompiler.__name__ == "DiscoverInventoryCompiler"
    assert shim.DiscoverBoundaryCompiler.__name__ == "DiscoverBoundaryCompiler"
    assert shim.DiscoverCapabilityPreflightCompiler.__name__ == "DiscoverCapabilityPreflightCompiler"

    assert shim.DiscoverManifestLoaderCompiler.__module__ == "discover_manifest_loader"
    assert shim.DiscoverInventoryCompiler.__module__ == "discover_inventory"
    assert shim.DiscoverBoundaryCompiler.__module__ == "discover_boundary"
    assert shim.DiscoverCapabilityPreflightCompiler.__module__ == "discover_capability_preflight"

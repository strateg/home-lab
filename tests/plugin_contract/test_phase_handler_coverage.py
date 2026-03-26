#!/usr/bin/env python3
"""Contract checks for non-run phase handler coverage."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import Phase, PluginRegistry
from plugin_manifest_discovery import discover_plugin_manifest_paths


def _manifest_paths() -> list[Path]:
    repo_root = V5_TOOLS.parent
    return discover_plugin_manifest_paths(
        base_manifest_path=V5_TOOLS / "plugins" / "plugins.yaml",
        class_modules_root=repo_root / "topology" / "class-modules",
        object_modules_root=repo_root / "topology" / "object-modules",
    )


def test_non_run_phase_plugins_override_phase_handlers() -> None:
    registry = PluginRegistry(V5_TOOLS)
    for manifest_path in _manifest_paths():
        registry.load_manifest(manifest_path)

    missing: list[str] = []
    for plugin_id, spec in sorted(registry.specs.items()):
        if spec.phase == Phase.RUN:
            continue
        plugin = registry.load_plugin(plugin_id)
        handler_name = f"on_{spec.phase.value}"
        if handler_name in plugin.__class__.__dict__:
            continue
        missing.append(f"{plugin_id} ({spec.phase.value}) -> {spec.entry}")

    assert not missing, "Plugins with non-run phase must override on_<phase>:\n" + "\n".join(missing)

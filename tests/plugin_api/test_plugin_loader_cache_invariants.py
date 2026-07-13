#!/usr/bin/env python3
"""Pre-fix invariant tests for load_plugin instance caching (S8 gate).

PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07 S8 risk control: before
`load_plugin` delegates to `PluginLoader.load` with a single instance
cache, pin the observable cache behavior of the facade:

- repeated load_plugin calls return the identical instance object and
  populate `registry.instances`
- a pre-seeded object in `registry.instances` short-circuits loading
  (cache-hit precedes the spec lookup, even for unknown ids)
- unknown plugin id raises PluginLoadError("Plugin not found in registry")
- config validation failure raises PluginConfigError and does not cache
- kind mismatch raises PluginLoadError and does not cache
- get_stats()["executed"] mirrors len(registry.instances)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginRegistry  # noqa: E402
from kernel.plugin_registry import PluginConfigError, PluginLoadError  # noqa: E402

PLUGINS_MODULE = "\n".join(
    [
        "from kernel import PluginResult, ValidatorJsonPlugin",
        "",
        "class NoopPlugin(ValidatorJsonPlugin):",
        "    def execute(self, ctx, stage):",
        "        return PluginResult.success(self.plugin_id, self.api_version)",
    ]
)


def _registry_with_manifest(tmp_path: Path, plugins: list[dict]) -> PluginRegistry:
    (tmp_path / "cache_plugins.py").write_text(PLUGINS_MODULE, encoding="utf-8")
    manifest = tmp_path / "plugins.yaml"
    manifest.write_text(
        yaml.safe_dump({"schema_version": 1, "plugins": plugins}, sort_keys=False),
        encoding="utf-8",
    )
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    return registry


def _noop_plugin_row(**overrides) -> dict:
    row = {
        "id": "invariant.validator_json.cached",
        "kind": "validator_json",
        "entry": "cache_plugins.py:NoopPlugin",
        "api_version": "1.x",
        "stages": ["validate"],
        "phase": "run",
        "order": 100,
    }
    row.update(overrides)
    return row


def test_load_plugin_caches_instance_and_updates_instances(tmp_path: Path) -> None:
    """Repeated loads return the identical object; instances/stats reflect it."""
    registry = _registry_with_manifest(tmp_path, [_noop_plugin_row()])

    first = registry.load_plugin("invariant.validator_json.cached")
    second = registry.load_plugin("invariant.validator_json.cached")

    assert first is second
    assert registry.instances["invariant.validator_json.cached"] is first
    assert registry.get_stats()["executed"] == len(registry.instances) == 1


def test_preseeded_instance_short_circuits_loading(tmp_path: Path) -> None:
    """Cache-hit precedes the spec lookup - even for ids without a spec."""
    registry = _registry_with_manifest(tmp_path, [_noop_plugin_row()])

    sentinel = object()
    registry.instances["invariant.validator_json.preseeded"] = sentinel  # type: ignore[assignment]

    assert registry.load_plugin("invariant.validator_json.preseeded") is sentinel


def test_load_plugin_unknown_id_raises_not_found(tmp_path: Path) -> None:
    registry = _registry_with_manifest(tmp_path, [_noop_plugin_row()])

    with pytest.raises(PluginLoadError, match="Plugin not found in registry"):
        registry.load_plugin("invariant.validator_json.missing")

    assert "invariant.validator_json.missing" not in registry.instances


def test_config_validation_error_is_raised_and_not_cached(tmp_path: Path) -> None:
    row = _noop_plugin_row(
        id="invariant.validator_json.badconfig",
        config_schema={
            "type": "object",
            "properties": {"needed": {"type": "string"}},
            "required": ["needed"],
        },
    )
    registry = _registry_with_manifest(tmp_path, [row])

    with pytest.raises(PluginConfigError, match="config error"):
        registry.load_plugin("invariant.validator_json.badconfig")

    assert "invariant.validator_json.badconfig" not in registry.instances


def test_kind_mismatch_raises_and_not_cached(tmp_path: Path) -> None:
    """Spec kind vs class kind mismatch is detected at load time."""
    row = _noop_plugin_row(
        id="invariant.compiler.mismatch",
        kind="compiler",
        stages=["compile"],
        order=50,
    )
    registry = _registry_with_manifest(tmp_path, [row])

    with pytest.raises(PluginLoadError, match="Plugin kind mismatch"):
        registry.load_plugin("invariant.compiler.mismatch")

    assert "invariant.compiler.mismatch" not in registry.instances

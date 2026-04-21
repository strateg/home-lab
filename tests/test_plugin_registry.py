#!/usr/bin/env python3
"""Tests for v5 plugin registry (ADR 0063).

Tests cover:
- Manifest loading
- Plugin instantiation
- Execution order resolution
- Plugin execution with timeout
- Config validation
- Error handling with traceback
- Kernel info
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import MethodType

import yaml

# Add topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[1] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (
    KERNEL_API_VERSION,
    KERNEL_VERSION,
    PluginContext,
    PluginDataExchangeError,
    PluginKind,
    PluginManifest,
    PluginRegistry,
    PluginResult,
    PluginSpec,
    PluginStatus,
    ValidatorJsonPlugin,
)
from kernel.plugin_base import Phase, PluginDiagnostic, Stage

from tests.helpers.plugin_execution import publish_for_test

REFERENCE_VALIDATOR_ENTRY = "plugins/validators/reference_validator.py:ReferenceValidator"


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_manifest_loading():
    """Test loading plugin manifest from YAML."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    manifest = PluginManifest.from_file(manifest_path)

    assert manifest.schema_version == 1
    assert len(manifest.plugins) >= 1

    discover_plugin = next(p for p in manifest.plugins if p.id == "base.discover.inventory")
    assert discover_plugin.kind == PluginKind.DISCOVERER
    assert Stage.DISCOVER in discover_plugin.stages
    assert discover_plugin.timeout == 30

    # Find the reference validator plugin
    ref_plugin = next(p for p in manifest.plugins if p.id == "base.validator.references")
    assert ref_plugin.kind == PluginKind.VALIDATOR_JSON
    assert Stage.VALIDATE in ref_plugin.stages
    assert ref_plugin.config == {"strict_mode": False}
    print("PASS: Manifest loading works")


def test_registry_load():
    """Test registry loading plugins."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    assert len(registry.specs) >= 1
    assert "base.validator.references" in registry.specs
    assert len(registry.get_load_errors()) == 0
    print("PASS: Registry loading works")


def test_execution_order():
    """Test plugin execution order resolution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    order = registry.get_execution_order(Stage.VALIDATE)
    assert "base.validator.references" in order
    print("PASS: Execution order works")


def test_stage_order_prefers_order_over_manifest_insertion(tmp_path: Path):
    """Independent plugins should be ordered by numeric order, not load order."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "zmod.validator_json.second",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 188,
                "depends_on": [],
            },
            {
                "id": "amod.validator_json.first",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "depends_on": [],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    order = registry.get_execution_order(Stage.VALIDATE)
    assert order == ["amod.validator_json.first", "zmod.validator_json.second"]


def test_stage_order_uses_id_as_tiebreaker(tmp_path: Path):
    """Plugins with same order should be sorted lexically by plugin ID."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "zmod.validator_json.b",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "depends_on": [],
            },
            {
                "id": "amod.validator_json.a",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "depends_on": [],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    order = registry.get_execution_order(Stage.VALIDATE)
    assert order == ["amod.validator_json.a", "zmod.validator_json.b"]


def test_stage_order_respects_depends_on_over_numeric_order(tmp_path: Path):
    """Dependency relation must dominate numeric order."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "amod.validator_json.base",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 188,
                "depends_on": [],
            },
            {
                "id": "zmod.validator_json.dep",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 91,
                "depends_on": ["amod.validator_json.base"],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    order = registry.get_execution_order(Stage.VALIDATE)
    assert order == ["amod.validator_json.base", "zmod.validator_json.dep"]


def test_execution_order_filters_by_phase(tmp_path: Path):
    """Execution order must be resolved independently for each phase."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "phase.validator_json.init",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "init",
                "order": 91,
            },
            {
                "id": "phase.validator_json.run",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 91,
                "depends_on": ["phase.validator_json.init"],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)

    init_order = registry.get_execution_order(Stage.VALIDATE, phase=Phase.INIT)
    run_order = registry.get_execution_order(Stage.VALIDATE, phase=Phase.RUN)

    assert init_order == ["phase.validator_json.init"]
    assert run_order == ["phase.validator_json.run"]


def test_base_manifest_run_phase_dispatch_uses_execute():
    """Run-phase dispatch must remain execute()-compatible for all base plugins."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", []) if isinstance(payload, dict) else []
    base_plugin_ids = [item.get("id") for item in plugins if isinstance(item, dict) and isinstance(item.get("id"), str)]

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest_path)
    ctx = PluginContext(topology_path="test", profile="test-real", model_lock={})

    dispatched = 0
    for plugin_id in base_plugin_ids:
        spec = registry.specs[plugin_id]
        plugin = registry.load_plugin(plugin_id)
        stage = spec.stages[0]

        def _sentinel_execute(self, _ctx, _stage):
            return PluginResult.success(
                plugin_id=self.plugin_id,
                api_version=self.api_version,
                output_data={"dispatch": "execute", "plugin_id": self.plugin_id},
            )

        original_execute = plugin.execute
        plugin.execute = MethodType(_sentinel_execute, plugin)  # type: ignore[assignment]
        try:
            result = plugin.execute_phase(ctx, stage, Phase.RUN)
        finally:
            plugin.execute = original_execute  # type: ignore[assignment]

        assert result.status == PluginStatus.SUCCESS
        assert result.output_data == {"dispatch": "execute", "plugin_id": plugin_id}
        dispatched += 1

    assert dispatched >= 47


def test_plugin_instantiation():
    """Test loading and instantiating a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    plugin = registry.load_plugin("base.validator.references")
    assert plugin.plugin_id == "base.validator.references"
    assert plugin.kind == PluginKind.VALIDATOR_JSON
    assert plugin.api_version == "1.x"
    print("PASS: Plugin instantiation works")


def test_plugin_execution():
    """Test executing a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Create minimal context
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router", "firmware_policy": "allowed", "os_policy": "allowed"}},
        objects={"obj.test": {"object": "obj.test", "class_ref": "class.router"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ],
                "firmware": [],
                "os": [],
                "lxc": [],
            }
        },
    )
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "test-device",
                "class_ref": "class.router",
                "object_ref": "obj.test",
                "firmware_ref": None,
                "os_refs": [],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert isinstance(result, PluginResult)
    assert result.status == PluginStatus.SUCCESS
    assert result.plugin_id == "base.validator.references"
    assert result.duration_ms > 0
    print("PASS: Plugin execution works")


def test_plugin_detects_invalid_ref():
    """Test that plugin detects invalid references."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Create context with invalid class_ref
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},  # Empty - class.router doesn't exist
        objects={},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.nonexistent",
                        "object_ref": "obj.nonexistent",
                    }
                ],
                "firmware": [],
                "os": [],
                "lxc": [],
            }
        },
    )

    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "test-device",
                "class_ref": "class.nonexistent",
                "object_ref": "obj.nonexistent",
                "firmware_ref": None,
                "os_refs": [],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert len(result.diagnostics) >= 1
    assert result.has_errors
    print("PASS: Plugin detects invalid references")


def test_plugin_result_statuses():
    """Test PluginResult factory methods."""
    # Test success
    result = PluginResult.success("test.plugin", duration_ms=100.0)
    assert result.status == PluginStatus.SUCCESS
    assert result.duration_ms == 100.0

    # Test partial (warnings)
    result = PluginResult.partial("test.plugin")
    assert result.status == PluginStatus.PARTIAL

    # Test failed
    result = PluginResult.failed("test.plugin", error_traceback="traceback here")
    assert result.status == PluginStatus.FAILED
    assert result.error_traceback == "traceback here"

    # Test timeout
    result = PluginResult.timeout("test.plugin", duration_ms=30000.0)
    assert result.status == PluginStatus.TIMEOUT

    # Test skipped
    result = PluginResult.skipped("test.plugin", reason="dependency failed")
    assert result.status == PluginStatus.SKIPPED
    assert result.output_data == {"skip_reason": "dependency failed"}

    print("PASS: PluginResult statuses work")


def test_plugin_result_to_dict():
    """Test PluginResult serialization."""
    diag = PluginDiagnostic(
        code="E2101",
        severity="error",
        stage="validate",
        message="Test error",
        path="test:path",
        plugin_id="test.plugin",
    )
    result = PluginResult(
        plugin_id="test.plugin",
        api_version="1.x",
        status=PluginStatus.FAILED,
        duration_ms=50.0,
        diagnostics=[diag],
        error_traceback="test traceback",
    )

    d = result.to_dict()
    assert d["plugin_id"] == "test.plugin"
    assert d["api_version"] == "1.x"
    assert d["status"] == "FAILED"
    assert d["duration_ms"] == 50.0
    assert len(d["diagnostics"]) == 1
    assert d["error_traceback"] == "test traceback"
    print("PASS: PluginResult serialization works")


def test_registry_stats():
    """Test registry statistics."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    stats = registry.get_stats()
    assert stats["loaded"] >= 1
    assert "validator_json" in stats["by_kind"]
    print("PASS: Registry stats work")


def test_kernel_info():
    """Test kernel info retrieval."""
    info = PluginRegistry.get_kernel_info()
    assert info["version"] == KERNEL_VERSION
    assert info["plugin_api_version"] == KERNEL_API_VERSION
    assert "1.x" in info["supported_api_versions"]
    assert info["default_timeout"] == 30.0
    print("PASS: Kernel info works")


def test_config_injection():
    """Test runtime config is restored after plugin execution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"runtime_flag": True},
    )

    registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert ctx.config == {"runtime_flag": True}
    print("PASS: Runtime config restore works")


def test_execute_stage():
    """Test executing all plugins for a stage."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) >= 1
    assert all(isinstance(r, PluginResult) for r in results)
    print("PASS: Stage execution works")


def test_execute_stage_fails_on_capability_mismatch(tmp_path: Path):
    """Stage execution must fail fast when requires_capabilities is unsatisfied."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "captest.validator_json.consumer",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "requires_capabilities": ["cap.kernel.missing"],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "kernel.capability_guard"
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E4010" for diag in results[0].diagnostics)


def test_execute_stage_allows_when_capability_is_provided(tmp_path: Path):
    """Requires-capabilities check should pass when provider plugin declares capability."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "captest.validator_json.provider",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 91,
                "capabilities": ["cap.kernel.available"],
            },
            {
                "id": "captest.validator_json.consumer",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "requires_capabilities": ["cap.kernel.available"],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 2
    assert all(result.plugin_id != "kernel.capability_guard" for result in results)


def test_execute_stage_fails_on_unsupported_model_version(tmp_path: Path):
    """Stage execution must fail before plugins when model version is incompatible."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "modeltest.validator_json.simple",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={"core_model_version": "9.9.0"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"model_lock_loaded": True},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "kernel.model_version_guard"
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E4011" for diag in results[0].diagnostics)


def test_execute_stage_accepts_compatible_model_version(tmp_path: Path):
    """Model version guard accepts compatible model.lock core_model_version."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "modeltest.validator_json.simple",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={"core_model_version": "1.0.0"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"model_lock_loaded": True},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert all(result.plugin_id != "kernel.model_version_guard" for result in results)


def test_execute_stage_fails_when_plugin_model_versions_incompatible(tmp_path: Path):
    """Plugin-level model_versions restriction must be enforced."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "modeltest.validator_json.restricted",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "model_versions": ["2.0"],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={"core_model_version": "1.0.0"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"model_lock_loaded": True},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "kernel.model_version_guard"
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E4011" for diag in results[0].diagnostics)


def test_execute_stage_fails_when_plugin_model_versions_require_missing_context(tmp_path: Path):
    """Plugin-level model_versions should fail if core_model_version context is missing."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "modeltest.validator_json.restricted",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "model_versions": ["1.0"],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"model_lock_loaded": False},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "kernel.model_version_guard"
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E4012" for diag in results[0].diagnostics)


def test_execute_stage_allows_when_plugin_model_versions_match(tmp_path: Path):
    """Plugin-level model_versions runs when restriction matches core model version."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "modeltest.validator_json.restricted",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "model_versions": ["1.0"],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={"core_model_version": "1.0.0"},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"model_lock_loaded": True},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert all(result.plugin_id != "kernel.model_version_guard" for result in results)


def test_execute_stage_runs_finalize_on_fail_fast(tmp_path: Path):
    """Finalize phase must still execute when fail_fast is triggered earlier."""
    plugin_module = tmp_path / "phase_plugins.py"
    plugin_module.write_text(
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "from kernel.plugin_base import PluginDiagnostic",
                "",
                "class FailingRunPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        diag = PluginDiagnostic(",
                "            code='E9999',",
                "            severity='error',",
                "            stage=stage.value,",
                "            message='forced run failure',",
                "            path='plugin:test',",
                "            plugin_id=self.plugin_id,",
                "        )",
                "        return PluginResult.failed(self.plugin_id, self.api_version, diagnostics=[diag])",
                "",
                "class FinalizeProbePlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "",
                "    def on_finalize(self, ctx, stage):",
                "        ctx.publish('finalized', True)",
                "        failures = ctx.config.get('stage_failure_context', [])",
                "        ctx.publish('failure_count', len(failures) if isinstance(failures, list) else 0)",
                "        return PluginResult.success(",
                "            self.plugin_id,",
                "            self.api_version,",
                "            output_data={'finalized': True},",
                "        )",
            ]
        ),
        encoding="utf-8",
    )

    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "phase.validator_json.failing_run",
                "kind": "validator_json",
                "entry": "phase_plugins.py:FailingRunPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
            },
            {
                "id": "phase.validator_json.finalize_probe",
                "kind": "validator_json",
                "entry": "phase_plugins.py:FinalizeProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "finalize",
                "order": 188,
                "produces": [
                    {"key": "finalized", "scope": "pipeline_shared"},
                    {"key": "failure_count", "scope": "pipeline_shared"},
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, fail_fast=True)
    statuses = {result.plugin_id: result.status for result in results}

    assert statuses["phase.validator_json.failing_run"] == PluginStatus.FAILED
    assert statuses["phase.validator_json.finalize_probe"] == PluginStatus.SUCCESS
    failure_context = ctx.config.get("stage_failure_context")
    assert isinstance(failure_context, list)
    assert failure_context and failure_context[0]["plugin_id"] == "phase.validator_json.failing_run"
    assert "diagnostics" in failure_context[0]
    assert isinstance(failure_context[0]["diagnostics"], list)
    assert failure_context[0]["diagnostics"][0]["code"] == "E9999"
    published = ctx.get_published_data().get("phase.validator_json.finalize_probe", {})
    assert published.get("failure_count") == 1


def test_partial_stage_selection_runs_finalize_for_started_stages_only(tmp_path: Path):
    """Finalize should run for started stages only when later stages are skipped."""
    plugin_module = tmp_path / "partial_stage_plugins.py"
    plugin_module.write_text(
        "\n".join(
            [
                "from kernel import CompilerPlugin, GeneratorPlugin, PluginResult, ValidatorJsonPlugin",
                "",
                "class CompileFinalize(CompilerPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "    def on_finalize(self, ctx, stage):",
                "        ctx.publish('finalized', True)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "",
                "class ValidateFinalize(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "    def on_finalize(self, ctx, stage):",
                "        ctx.publish('finalized', True)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "",
                "class GenerateFinalize(GeneratorPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "    def on_finalize(self, ctx, stage):",
                "        ctx.publish('finalized', True)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
        encoding="utf-8",
    )

    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "partial.compile.finalize",
                "kind": "compiler",
                "entry": "partial_stage_plugins.py:CompileFinalize",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 88,
                "produces": [{"key": "finalized", "scope": "pipeline_shared"}],
            },
            {
                "id": "partial.validate.finalize",
                "kind": "validator_json",
                "entry": "partial_stage_plugins.py:ValidateFinalize",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "finalize",
                "order": 188,
                "produces": [{"key": "finalized", "scope": "pipeline_shared"}],
            },
            {
                "id": "partial.generate.finalize",
                "kind": "generator",
                "entry": "partial_stage_plugins.py:GenerateFinalize",
                "api_version": "1.x",
                "stages": ["generate"],
                "phase": "finalize",
                "order": 390,
                "produces": [{"key": "finalized", "scope": "pipeline_shared"}],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    compile_results = registry.execute_stage(Stage.COMPILE, ctx)
    validate_results = registry.execute_stage(Stage.VALIDATE, ctx)

    assert [result.plugin_id for result in compile_results] == ["partial.compile.finalize"]
    assert [result.plugin_id for result in validate_results] == ["partial.validate.finalize"]
    published = ctx.get_published_data()
    assert published.get("partial.compile.finalize", {}).get("finalized") is True
    assert published.get("partial.validate.finalize", {}).get("finalized") is True
    assert "partial.generate.finalize" not in published


def test_execute_stage_skips_when_before_capability_preflight(tmp_path: Path):
    """Plugins skipped by when-predicate must not fail capability preflight."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "when.validator_json.consumer",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "requires_capabilities": ["cap.kernel.missing"],
                "when": {"profiles": ["production"]},
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "when.validator_json.consumer"
    assert results[0].status == PluginStatus.SKIPPED


def test_execute_stage_skips_when_changed_input_scopes_do_not_intersect(tmp_path: Path):
    """when.changed_input_scopes should skip plugin when runtime scopes are known and disjoint."""
    _write_module(
        tmp_path / "when_scope_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class NoopValidator(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )

    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "when.validator_json.scope_guard",
                "kind": "validator_json",
                "entry": "when_scope_plugins.py:NoopValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "when": {"changed_input_scopes": ["docs"]},
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        changed_input_scopes=["terraform"],
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "when.validator_json.scope_guard"
    assert results[0].status == PluginStatus.SKIPPED


def test_execute_stage_allows_when_changed_input_scopes_unknown(tmp_path: Path):
    """when.changed_input_scopes stays non-blocking until runtime computes scopes."""
    _write_module(
        tmp_path / "when_scope_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class NoopValidator(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )

    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "when.validator_json.scope_guard",
                "kind": "validator_json",
                "entry": "when_scope_plugins.py:NoopValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "when": {"changed_input_scopes": ["docs"]},
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx)
    assert len(results) == 1
    assert results[0].plugin_id == "when.validator_json.scope_guard"
    assert results[0].status == PluginStatus.SUCCESS


def test_execute_stage_parallel_keeps_deterministic_order(tmp_path: Path):
    """Parallel phase execution should return results in deterministic plugin order."""
    _write_module(
        tmp_path / "parallel_plugins.py",
        "\n".join(
            [
                "import time",
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class SleepPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        sleep_ms = int(ctx.active_config.get('sleep_ms', 0))",
                "        if sleep_ms > 0:",
                "            time.sleep(sleep_ms / 1000.0)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "parallel.validator_json.first",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "config": {"sleep_ms": 80},
            },
            {
                "id": "parallel.validator_json.second",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 150,
                "config": {"sleep_ms": 5},
            },
            {
                "id": "parallel.validator_json.third",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 188,
                "config": {"sleep_ms": 30},
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    sequential = registry.execute_stage(Stage.VALIDATE, ctx)
    parallel = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
    expected_order = [
        "parallel.validator_json.first",
        "parallel.validator_json.second",
        "parallel.validator_json.third",
    ]

    assert [result.plugin_id for result in sequential] == expected_order
    assert [result.plugin_id for result in parallel] == expected_order
    assert all(result.status == PluginStatus.SUCCESS for result in parallel)


def test_execute_stage_parallel_is_deterministic_across_repeated_runs(tmp_path: Path):
    """Repeated parallel executions should preserve identical result ordering."""
    _write_module(
        tmp_path / "parallel_plugins.py",
        "\n".join(
            [
                "import time",
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class SleepPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        sleep_ms = int(ctx.active_config.get('sleep_ms', 0))",
                "        if sleep_ms > 0:",
                "            time.sleep(sleep_ms / 1000.0)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "repeat.validator_json.first",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "config": {"sleep_ms": 35},
            },
            {
                "id": "repeat.validator_json.second",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 120,
                "config": {"sleep_ms": 5},
            },
            {
                "id": "repeat.validator_json.third",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 150,
                "config": {"sleep_ms": 20},
            },
        ],
    }
    _write_manifest(manifest, payload)

    expected_order = [
        "repeat.validator_json.first",
        "repeat.validator_json.second",
        "repeat.validator_json.third",
    ]
    observed_orders: list[list[str]] = []
    for _ in range(12):
        registry = PluginRegistry(V5_TOOLS)
        registry.load_manifest(manifest)
        ctx = PluginContext(
            topology_path="test",
            profile="test",
            model_lock={},
            classes={},
            objects={},
            instance_bindings={"instance_bindings": {}},
        )
        results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
        observed_orders.append([result.plugin_id for result in results])
        assert all(result.status == PluginStatus.SUCCESS for result in results)

    assert all(order == expected_order for order in observed_orders)


def test_execute_stage_parallel_respects_depends_on(tmp_path: Path):
    """Parallel wavefront execution must honor intra-phase dependency edges."""
    _write_module(
        tmp_path / "parallel_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class DependencyProbePlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        required = ctx.active_config.get('required', [])",
                "        for dep_id in required:",
                "            ctx.subscribe(dep_id, 'ready')",
                "        ctx.publish('ready', self.plugin_id)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "parallel.validator_json.base_a",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:DependencyProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "parallel.validator_json.base_b",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:DependencyProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 110,
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "parallel.validator_json.consumer",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:DependencyProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 188,
                "depends_on": ["parallel.validator_json.base_a", "parallel.validator_json.base_b"],
                "config": {
                    "required": [
                        "parallel.validator_json.base_a",
                        "parallel.validator_json.base_b",
                    ]
                },
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
                "consumes": [
                    {
                        "from_plugin": "parallel.validator_json.base_a",
                        "key": "ready",
                        "required": True,
                    },
                    {
                        "from_plugin": "parallel.validator_json.base_b",
                        "key": "ready",
                        "required": True,
                    },
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
    assert [result.plugin_id for result in results] == [
        "parallel.validator_json.base_a",
        "parallel.validator_json.base_b",
        "parallel.validator_json.consumer",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in results)


def test_execute_stage_serial_compatible_plugins_commit_via_pipeline_state(tmp_path: Path):
    """Compatible plugins should execute via snapshot/envelope path even without parallel mode."""
    _write_module(
        tmp_path / "envelope_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ProducerPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('ready', {'value': 'ok'})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "",
                "class ConsumerPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        payload = ctx.subscribe('envelope.validator_json.producer', 'ready')",
                "        assert payload['value'] == 'ok'",
                "        ctx.publish('seen', {'source': payload['value']})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "envelope.validator_json.producer",
                "kind": "validator_json",
                "entry": "envelope_plugins.py:ProducerPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "subinterpreter_compatible": True,
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "envelope.validator_json.consumer",
                "kind": "validator_json",
                "entry": "envelope_plugins.py:ConsumerPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 120,
                "depends_on": ["envelope.validator_json.producer"],
                "subinterpreter_compatible": True,
                "consumes": [{"from_plugin": "envelope.validator_json.producer", "key": "ready"}],
                "produces": [{"key": "seen", "scope": "pipeline_shared"}],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert [result.plugin_id for result in results] == [
        "envelope.validator_json.producer",
        "envelope.validator_json.consumer",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in results)
    published = ctx.get_published_data()
    assert published["envelope.validator_json.producer"]["ready"] == {"value": "ok"}
    assert published["envelope.validator_json.consumer"]["seen"] == {"source": "ok"}


def test_execute_stage_parallel_compatible_plugin_crash_does_not_commit_partial_publish(tmp_path: Path):
    """Failed compatible worker must not leak local outbox content into committed state."""
    _write_module(
        tmp_path / "envelope_crash_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class CrashAfterPublishPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('ready', {'value': 'leak'})",
                "        raise RuntimeError('boom')",
                "",
                "class ConsumerPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('envelope.validator_json.crash', 'ready')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "envelope.validator_json.crash",
                "kind": "validator_json",
                "entry": "envelope_crash_plugins.py:CrashAfterPublishPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "subinterpreter_compatible": True,
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "envelope.validator_json.consumer",
                "kind": "validator_json",
                "entry": "envelope_crash_plugins.py:ConsumerPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 120,
                "depends_on": ["envelope.validator_json.crash"],
                "subinterpreter_compatible": True,
                "consumes": [{"from_plugin": "envelope.validator_json.crash", "key": "ready"}],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)

    assert [result.plugin_id for result in results] == [
        "envelope.validator_json.crash",
        "envelope.validator_json.consumer",
    ]
    by_plugin = {result.plugin_id: result for result in results}
    assert by_plugin["envelope.validator_json.crash"].status == PluginStatus.FAILED
    assert by_plugin["envelope.validator_json.consumer"].status == PluginStatus.FAILED
    assert ctx.get_published_keys("envelope.validator_json.crash") == []


def test_execute_stage_invalidates_stage_local_outputs(tmp_path: Path):
    """stage_local published keys must be dropped after stage completion."""
    _write_module(
        tmp_path / "stage_local_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, CompilerPlugin",
                "",
                "class StageLocalPublisher(CompilerPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('tmp_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "stage_local.compiler.publisher",
                "kind": "compiler",
                "entry": "stage_local_plugins.py:StageLocalPublisher",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 88,
                "produces": [{"key": "tmp_key", "scope": "stage_local"}],
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.COMPILE, ctx)
    assert len(results) == 1
    assert results[0].status == PluginStatus.SUCCESS
    assert ctx.get_published_keys("stage_local.compiler.publisher") == []

    ctx._set_execution_context(  # noqa: SLF001 - testing stage_local cleanup
        "stage_local.validator.consumer", {"stage_local.compiler.publisher"}, stage=Stage.VALIDATE
    )
    try:
        try:
            ctx.subscribe("stage_local.compiler.publisher", "tmp_key")
            assert False, "Expected missing stage_local key after stage cleanup"
        except PluginDataExchangeError as exc:
            assert "has not published any data" in str(exc)
    finally:
        ctx._clear_execution_context()  # noqa: SLF001


def test_execute_stage_trace_records_execution_events(tmp_path: Path):
    """Trace mode should record stage/phase/plugin execution lifecycle."""
    _write_module(
        tmp_path / "trace_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class TraceProbePlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "trace.validator_json.probe",
                "kind": "validator_json",
                "entry": "trace_plugins.py:TraceProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
            }
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )

    results = registry.execute_stage(Stage.VALIDATE, ctx, trace_execution=True)
    assert len(results) == 1
    trace = registry.get_execution_trace()
    events = [entry["event"] for entry in trace]

    assert events[0] == "stage_start"
    assert "phase_start" in events
    assert "plugin_start" in events
    assert "plugin_result" in events
    assert events[-1] == "stage_end"

    registry.reset_execution_trace()
    assert registry.get_execution_trace() == []


def test_execute_plugin_warns_on_undeclared_publish(tmp_path: Path):
    """Runtime must emit W8001 when plugin publishes without produces declaration."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class PublisherNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "contract.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:PublisherNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin(
        "contract.validator_json.publisher",
        ctx,
        Stage.VALIDATE,
        contract_warnings=True,
    )
    assert any(diag.code == "W8001" for diag in result.diagnostics)
    assert result.status == PluginStatus.PARTIAL


def test_execute_plugin_warns_on_undeclared_subscribe(tmp_path: Path):
    """Runtime must emit W8003 when plugin subscribes without consumes declaration."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ConsumerNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('contract.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "contract.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:ConsumerNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["contract.compiler.producer"],
                },
                {
                    "id": "contract.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "contract.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin(
        "contract.validator_json.consumer",
        ctx,
        Stage.VALIDATE,
        contract_warnings=True,
    )
    assert any(diag.code == "W8003" for diag in result.diagnostics)
    assert result.status == PluginStatus.PARTIAL


def test_execute_plugin_errors_on_undeclared_publish_in_strict_mode(tmp_path: Path):
    """Strict contract mode must fail undeclared publish with E8004/E8005."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class PublisherNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:PublisherNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin(
        "strict.validator_json.publisher",
        ctx,
        Stage.VALIDATE,
        contract_errors=True,
    )
    assert any(diag.code == "E8004" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_errors_on_undeclared_subscribe_in_strict_mode(tmp_path: Path):
    """Strict contract mode must fail undeclared consume with E8006/E8007."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ConsumerNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('strict.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:ConsumerNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["strict.compiler.producer"],
                },
                {
                    "id": "strict.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "strict.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin(
        "strict.validator_json.consumer",
        ctx,
        Stage.VALIDATE,
        contract_errors=True,
    )
    assert any(diag.code == "E8006" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_requires_explicit_consumes_even_with_declared_producer(tmp_path: Path):
    """Strict contract mode does not infer consumes from depends_on + producer contract."""
    _write_module(
        tmp_path / "contract_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ConsumerNoContract(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('strict.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "contract_plugins.py:ConsumerNoContract",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["strict.compiler.producer"],
                },
                {
                    "id": "strict.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                    "produces": [
                        {
                            "key": "runtime_key",
                            "scope": "pipeline_shared",
                        }
                    ],
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "strict.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin(
        "strict.validator_json.consumer",
        ctx,
        Stage.VALIDATE,
        contract_errors=True,
    )
    assert any(diag.code == "E8006" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_stage_applies_contract_errors_mode(tmp_path: Path):
    """execute_stage(contract_errors=True) must fail undeclared publish/consume."""
    _write_module(
        tmp_path / "strict_stage_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class StageStrictPublisher(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "strict_stage.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "strict_stage_plugins.py:StageStrictPublisher",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    results = registry.execute_stage(Stage.VALIDATE, ctx, contract_errors=True)
    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8004" for diag in results[0].diagnostics)


def test_execute_plugin_fails_on_invalid_produced_schema_ref_payload(tmp_path: Path):
    """Declared produces.schema_ref must validate published payload."""
    _write_module(
        tmp_path / "schema_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class InvalidSchemaPublisher(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', 'not-an-object')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "payload.schema.json").write_text(
        json.dumps(
            {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}, ensure_ascii=True
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "schema.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "schema_plugins.py:InvalidSchemaPublisher",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "produces": [{"key": "runtime_key", "schema_ref": "schemas/payload.schema.json"}],
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("schema.validator_json.publisher", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8002" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_fails_on_invalid_consumed_schema_ref_payload(tmp_path: Path):
    """Declared consumes.schema_ref must validate subscribed payload."""
    _write_module(
        tmp_path / "schema_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class SchemaConsumer(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('schema.compiler.producer', 'runtime_key')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "payload.schema.json").write_text(
        json.dumps({"type": "integer"}, ensure_ascii=True),
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "schema.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "schema_plugins.py:SchemaConsumer",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["schema.compiler.producer"],
                    "consumes": [
                        {
                            "from_plugin": "schema.compiler.producer",
                            "key": "runtime_key",
                            "schema_ref": "schemas/payload.schema.json",
                        }
                    ],
                },
                {
                    "id": "schema.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})
    publish_for_test(ctx, "schema.compiler.producer", "runtime_key", {"ok": True}, stage=Stage.COMPILE)

    result = registry.execute_plugin("schema.validator_json.consumer", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8002" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_fails_on_missing_schema_ref(tmp_path: Path):
    """Missing schema_ref target must fail with E8001."""
    _write_module(
        tmp_path / "schema_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class MissingSchemaPublisher(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('runtime_key', {'ok': True})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "schema.validator_json.missing",
                    "kind": "validator_json",
                    "entry": "schema_plugins.py:MissingSchemaPublisher",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "produces": [{"key": "runtime_key", "schema_ref": "schemas/missing.json"}],
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("schema.validator_json.missing", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8001" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_fails_when_required_consume_payload_missing(tmp_path: Path):
    """consumes.required=true must fail before plugin execution when payload is absent."""
    _write_module(
        tmp_path / "required_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class RequiredConsumer(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        # If pre-check works, runtime should never reach this call.",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "required.validator_json.consumer",
                    "kind": "validator_json",
                    "entry": "required_plugins.py:RequiredConsumer",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["required.compiler.producer"],
                    "consumes": [
                        {
                            "from_plugin": "required.compiler.producer",
                            "key": "required_key",
                            "required": True,
                        }
                    ],
                },
                {
                    "id": "required.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("required.validator_json.consumer", ctx, Stage.VALIDATE)
    assert any(diag.code == "E8003" for diag in result.diagnostics)
    assert result.status == PluginStatus.FAILED


def test_execute_plugin_allows_when_consume_required_false_and_payload_missing(tmp_path: Path):
    """consumes.required=false must not fail pre-run when payload is absent."""
    _write_module(
        tmp_path / "required_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class OptionalConsumer(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "required.validator_json.optional_consumer",
                    "kind": "validator_json",
                    "entry": "required_plugins.py:OptionalConsumer",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "order": 100,
                    "depends_on": ["required.compiler.producer"],
                    "consumes": [
                        {
                            "from_plugin": "required.compiler.producer",
                            "key": "optional_key",
                            "required": False,
                        }
                    ],
                },
                {
                    "id": "required.compiler.producer",
                    "kind": "compiler",
                    "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                    "api_version": "1.x",
                    "stages": ["compile"],
                    "order": 31,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = PluginContext(topology_path="test", profile="test", model_lock={})

    result = registry.execute_plugin("required.validator_json.optional_consumer", ctx, Stage.VALIDATE)
    assert not any(diag.code == "E8003" for diag in result.diagnostics)
    assert result.status == PluginStatus.SUCCESS


def test_timeout_does_not_block_pipeline():
    """Timeout should return promptly instead of waiting for plugin completion."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={"obj.test": {"object": "obj.test"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [{"instance": "test-device", "class_ref": "class.router", "object_ref": "obj.test"}]
            }
        },
    )
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "test-device",
                "class_ref": "class.router",
                "object_ref": "obj.test",
                "firmware_ref": None,
                "os_refs": [],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    plugin = registry.load_plugin("base.validator.references")
    original_execute = plugin.execute

    def slow_execute(ctx: PluginContext, stage: Stage) -> PluginResult:
        time.sleep(2.0)
        return original_execute(ctx, stage)

    plugin.execute = slow_execute  # type: ignore[assignment]
    try:
        start = time.perf_counter()
        result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE, timeout=0.1)
        elapsed = time.perf_counter() - start
    finally:
        plugin.execute = original_execute  # type: ignore[assignment]

    assert result.status == PluginStatus.TIMEOUT
    assert elapsed < 1.0
    print("PASS: Timeout returns promptly")


def test_runtime_config_takes_precedence():
    """Runtime ctx.config values should override plugin defaults."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={"obj.test": {"object": "obj.test"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ]
            }
        },
        config={"strict_mode": True},
    )
    publish_for_test(ctx, "base.compiler.model_lock_loader", "lock_payload", {})
    publish_for_test(ctx, "base.compiler.model_lock_loader", "model_lock_loaded", False)
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])

    result = registry.execute_plugin("base.validator.model_lock", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E3201" for d in result.diagnostics)
    assert ctx.config == {"strict_mode": True}
    print("PASS: Runtime config precedence works")


def test_publish_subscribe_basic():
    """Test basic publish/subscribe functionality."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Set execution context (simulating registry behavior)
    publish_for_test(ctx, "plugin.producer", "key1", {"data": "value1"})
    publish_for_test(ctx, "plugin.producer", "key2", [1, 2, 3])

    # Set up consumer plugin with dependency
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})  # noqa: SLF001 - testing context subscribe

    # Subscribe to data
    data1 = ctx.subscribe("plugin.producer", "key1")
    assert data1 == {"data": "value1"}

    data2 = ctx.subscribe("plugin.producer", "key2")
    assert data2 == [1, 2, 3]

    # Get published keys
    keys = ctx.get_published_keys("plugin.producer")
    assert set(keys) == {"key1", "key2"}

    ctx._clear_execution_context()  # noqa: SLF001
    print("PASS: Basic publish/subscribe works")


def test_publish_subscribe_dependency_check():
    """Test that subscribe enforces dependency declaration."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Producer publishes data
    publish_for_test(ctx, "plugin.producer", "data", {"value": 42})

    # Consumer WITHOUT dependency should fail
    ctx._set_execution_context("plugin.consumer", set())  # noqa: SLF001 - testing dependency enforcement

    try:
        ctx.subscribe("plugin.producer", "data")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "not in depends_on list" in str(e)

    ctx._clear_execution_context()  # noqa: SLF001
    print("PASS: Subscribe dependency check works")


def test_publish_subscribe_missing_data():
    """Test subscribe error handling for missing data."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Consumer with valid dependency but producer hasn't published
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})  # noqa: SLF001 - testing missing data handling

    try:
        ctx.subscribe("plugin.producer", "nonexistent")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "has not published any data" in str(e)

    ctx._clear_execution_context()  # noqa: SLF001

    # Producer publishes some data
    publish_for_test(ctx, "plugin.producer", "existing_key", "value")

    # Consumer tries to get missing key
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})  # noqa: SLF001 - testing missing key handling

    try:
        ctx.subscribe("plugin.producer", "nonexistent_key")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "has not published key" in str(e)

    ctx._clear_execution_context()  # noqa: SLF001
    print("PASS: Subscribe missing data error handling works")


def test_publish_without_context():
    """Test that publish fails without execution context."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # No execution context set
    try:
        ctx.publish("key", "value")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "no current plugin context" in str(e)

    print("PASS: Publish without context error works")


if __name__ == "__main__":
    print("=" * 60)
    print("ADR 0063 Plugin Registry Tests")
    print("=" * 60)
    print()

    tests = [
        test_manifest_loading,
        test_registry_load,
        test_execution_order,
        test_stage_order_prefers_order_over_manifest_insertion,
        test_stage_order_uses_id_as_tiebreaker,
        test_stage_order_respects_depends_on_over_numeric_order,
        test_execution_order_filters_by_phase,
        test_plugin_instantiation,
        test_plugin_execution,
        test_plugin_detects_invalid_ref,
        test_plugin_result_statuses,
        test_plugin_result_to_dict,
        test_registry_stats,
        test_kernel_info,
        test_config_injection,
        test_execute_stage,
        test_execute_stage_fails_on_capability_mismatch,
        test_execute_stage_allows_when_capability_is_provided,
        test_execute_stage_fails_on_unsupported_model_version,
        test_execute_stage_accepts_compatible_model_version,
        test_execute_stage_fails_when_plugin_model_versions_incompatible,
        test_execute_stage_fails_when_plugin_model_versions_require_missing_context,
        test_execute_stage_allows_when_plugin_model_versions_match,
        test_execute_stage_runs_finalize_on_fail_fast,
        test_partial_stage_selection_runs_finalize_for_started_stages_only,
        test_execute_stage_skips_when_before_capability_preflight,
        test_execute_stage_skips_when_changed_input_scopes_do_not_intersect,
        test_execute_stage_allows_when_changed_input_scopes_unknown,
        test_execute_stage_parallel_keeps_deterministic_order,
        test_execute_stage_parallel_is_deterministic_across_repeated_runs,
        test_execute_stage_parallel_respects_depends_on,
        test_execute_stage_invalidates_stage_local_outputs,
        test_execute_stage_trace_records_execution_events,
        test_execute_plugin_warns_on_undeclared_publish,
        test_execute_plugin_warns_on_undeclared_subscribe,
        test_execute_plugin_errors_on_undeclared_publish_in_strict_mode,
        test_execute_plugin_errors_on_undeclared_subscribe_in_strict_mode,
        test_execute_stage_applies_contract_errors_mode,
        test_execute_plugin_fails_on_invalid_produced_schema_ref_payload,
        test_execute_plugin_fails_on_invalid_consumed_schema_ref_payload,
        test_execute_plugin_fails_on_missing_schema_ref,
        test_execute_plugin_fails_when_required_consume_payload_missing,
        test_execute_plugin_allows_when_consume_required_false_and_payload_missing,
        test_timeout_does_not_block_pipeline,
        test_runtime_config_takes_precedence,
        # ADR 0065 inter-plugin data exchange tests
        test_publish_subscribe_basic,
        test_publish_subscribe_dependency_check,
        test_publish_subscribe_missing_data,
        test_publish_without_context,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            import traceback

            print(f"FAIL: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)

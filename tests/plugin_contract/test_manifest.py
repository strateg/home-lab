#!/usr/bin/env python3
"""Tests for plugin manifest loading and validation (ADR 0066 - Contract Tests).

Tests cover:
- Manifest YAML parsing
- Plugin spec extraction
- API version compatibility
- Config schema validation
- Entry point validation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Add topology-tools to path
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (
    KERNEL_API_VERSION,
    KERNEL_VERSION,
    SUPPORTED_API_VERSIONS,
    Phase,
    PluginContext,
    PluginDataExchangeError,
    PluginExecutionScope,
    PluginKind,
    PluginLoadError,
    PluginManifest,
    PluginRegistry,
    PluginSpec,
)
from kernel.plugin_base import Stage


def test_manifest_loading():
    """Test loading plugin manifest from YAML."""
    manifest_path = V5_TOOLS / "plugins" / "plugins.yaml"
    manifest = PluginManifest.from_file(manifest_path)

    assert manifest.schema_version == 1
    assert len(manifest.plugins) >= 1

    # First plugin is now the compiler plugin
    compiler_plugin = manifest.plugins[0]
    assert compiler_plugin.id == "base.compiler.capabilities"
    assert compiler_plugin.kind == PluginKind.COMPILER
    assert Stage.COMPILE in compiler_plugin.stages

    # Find the reference validator plugin
    ref_plugin = next(p for p in manifest.plugins if p.id == "base.validator.references")
    assert ref_plugin.kind == PluginKind.VALIDATOR_JSON
    assert Stage.VALIDATE in ref_plugin.stages
    print("PASS: Manifest loading works")


def test_registry_load():
    """Test registry loading plugins."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    assert len(registry.specs) >= 1
    assert "base.validator.references" in registry.specs
    assert len(registry.get_load_errors()) == 0
    print("PASS: Registry loading works")


def test_api_version_compatibility():
    """Test API version compatibility checking."""
    registry = PluginRegistry(V5_TOOLS)

    # Compatible versions
    assert registry._is_api_compatible("1.x")
    assert registry._is_api_compatible("1.0")

    # Incompatible versions
    assert not registry._is_api_compatible("2.x")
    assert not registry._is_api_compatible("0.x")
    print("PASS: API version compatibility works")


def test_config_validation():
    """Test plugin config validation against schema."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Valid config should pass
    errors = registry.validate_plugin_config("base.validator.references")
    assert len(errors) == 0
    print("PASS: Config validation works")


def test_kernel_info():
    """Test kernel info retrieval."""
    info = PluginRegistry.get_kernel_info()
    assert info["version"] == KERNEL_VERSION
    assert info["plugin_api_version"] == KERNEL_API_VERSION
    assert "1.x" in info["supported_api_versions"]
    assert info["default_timeout"] == 30.0
    print("PASS: Kernel info works")


def test_plugin_instantiation():
    """Test loading and instantiating a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    plugin = registry.load_plugin("base.validator.references")
    assert plugin.plugin_id == "base.validator.references"
    assert plugin.kind == PluginKind.VALIDATOR_JSON
    assert plugin.api_version == "1.x"
    print("PASS: Plugin instantiation works")


def test_duplicate_plugin_id():
    """Test that duplicate plugin IDs are detected."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Loading same manifest again should detect duplicates
    initial_count = len(registry.specs)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Specs count should not increase (duplicates rejected)
    assert len(registry.specs) == initial_count

    # Should have load errors for duplicates
    errors = registry.get_load_errors()
    assert any("Duplicate" in err for err in errors)
    print("PASS: Duplicate plugin ID detection works")


def test_manifest_schema_rejects_unknown_fields(tmp_path: Path):
    """Runtime loader must reject manifest entries violating schema."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.validator_json.extra",
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "unexpected_field": "not_allowed",
            }
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)
    try:
        registry.load_manifest(manifest)
        assert False, "Expected PluginLoadError for schema violation"
    except PluginLoadError as exc:
        assert "schema validation failed" in str(exc).lower()


def test_manifest_schema_accepts_model_versions(tmp_path: Path):
    """model_versions is a valid optional plugin manifest field."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.validator_json.model_versions",
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "model_versions": ["1.0", "2.0"],
            }
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    assert "test.validator_json.model_versions" in registry.specs


def test_manifest_schema_accepts_phase_field(tmp_path: Path):
    """phase is a valid optional plugin manifest field (ADR 0080 draft)."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.validator_json.phase",
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
            }
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    assert "test.validator_json.phase" in registry.specs


def test_manifest_schema_declares_build_stage_and_phase_enum():
    """Schema declares the ADR0080 stage and phase enums."""
    schema_path = V5_TOOLS / "schemas" / "plugin-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    plugin_props = schema["$defs"]["plugin"]["properties"]

    assert plugin_props["stages"]["items"]["enum"] == [
        "discover",
        "compile",
        "validate",
        "generate",
        "assemble",
        "build",
    ]
    assert plugin_props["kind"]["enum"] == [
        "compiler",
        "validator_yaml",
        "validator_json",
        "generator",
        "assembler",
        "builder",
    ]
    assert plugin_props["phase"]["enum"] == ["init", "pre", "run", "post", "verify", "finalize"]


def test_schema_and_runtime_stage_phase_enums_stay_in_sync():
    """Stage and Phase enums must match between runtime and manifest schema."""
    schema_path = V5_TOOLS / "schemas" / "plugin-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    plugin_props = schema["$defs"]["plugin"]["properties"]

    assert [stage.value for stage in Stage] == plugin_props["stages"]["items"]["enum"]
    assert [phase.value for phase in Phase] == plugin_props["phase"]["enum"]


def test_manifest_schema_accepts_build_stage_and_new_fields(tmp_path: Path):
    """A build-stage manifest with Wave B fields must load in runtime."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.builder.bundle",
                "kind": "builder",
                "entry": "plugins/generators/effective_json_generator.py:EffectiveJsonGenerator",
                "api_version": "1.x",
                "stages": ["build"],
                "phase": "finalize",
                "order": 500,
                "compiled_json_owner": False,
                "when": {"pipeline_modes": ["plugin-first"]},
                "produces": [{"key": "bundle_path", "scope": "pipeline_shared"}],
                "consumes": [{"from_plugin": "test.compiler.input", "key": "artifact_manifest_path"}],
            }
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)

    spec = registry.specs["test.builder.bundle"]
    assert spec.kind == PluginKind.BUILDER
    assert spec.stages == [Stage.BUILD]
    assert spec.phase == Phase.FINALIZE
    assert spec.when == {"pipeline_modes": ["plugin-first"]}


def test_plugin_context_scope_backed_publish_subscribe_and_active_config():
    """Execution scope should drive pub/sub identity and per-plugin config view."""
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="production",
        model_lock={},
        config={"global_flag": "base"},
    )

    producer_scope = PluginExecutionScope(
        plugin_id="test.compiler.producer",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        config={"global_flag": "producer", "scoped_only": "yes"},
    )
    token = ctx._set_execution_scope(producer_scope)
    try:
        assert ctx.config.get("global_flag") == "producer"
        assert ctx.active_config["scoped_only"] == "yes"
        ctx.publish("payload", {"ok": True})
    finally:
        ctx._clear_execution_scope(token)

    consumer_scope = PluginExecutionScope(
        plugin_id="test.validator.consumer",
        allowed_dependencies=frozenset({"test.compiler.producer"}),
        phase=Phase.RUN,
        config={"global_flag": "consumer"},
    )
    token = ctx._set_execution_scope(consumer_scope)
    try:
        assert ctx.subscribe("test.compiler.producer", "payload") == {"ok": True}
        assert ctx.config.get("global_flag") == "consumer"
    finally:
        ctx._clear_execution_scope(token)

    assert ctx.config.get("global_flag") == "base"


def test_plugin_context_blocks_cross_stage_subscribe_for_stage_local_keys():
    """stage_local keys must not be consumable from a different stage."""
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="production",
        model_lock={},
    )
    producer_scope = PluginExecutionScope(
        plugin_id="test.compiler.producer",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        stage=Stage.COMPILE,
        config={},
        produced_key_scopes={"tmp_key": "stage_local"},
    )
    token = ctx._set_execution_scope(producer_scope)
    try:
        ctx.publish("tmp_key", {"value": 1})
    finally:
        ctx._clear_execution_scope(token)

    consumer_scope = PluginExecutionScope(
        plugin_id="test.validator.consumer",
        allowed_dependencies=frozenset({"test.compiler.producer"}),
        phase=Phase.RUN,
        stage=Stage.VALIDATE,
        config={},
    )
    token = ctx._set_execution_scope(consumer_scope)
    try:
        try:
            ctx.subscribe("test.compiler.producer", "tmp_key")
            assert False, "Expected stage_local cross-stage subscription error"
        except PluginDataExchangeError as exc:
            assert "stage_local key" in str(exc)
    finally:
        ctx._clear_execution_scope(token)


def test_plugin_context_invalidates_stage_local_keys_on_stage_boundary():
    """stage_local keys should be removed when the publishing stage completes."""
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="production",
        model_lock={},
    )
    producer_scope = PluginExecutionScope(
        plugin_id="test.compiler.producer",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        stage=Stage.COMPILE,
        config={},
        produced_key_scopes={"tmp_key": "stage_local"},
    )
    token = ctx._set_execution_scope(producer_scope)
    try:
        ctx.publish("tmp_key", {"value": 1})
    finally:
        ctx._clear_execution_scope(token)

    removed = ctx.invalidate_stage_local_data(Stage.COMPILE)
    assert removed == ["test.compiler.producer.tmp_key"]
    assert ctx.get_published_keys("test.compiler.producer") == []


def test_compiled_json_owner_must_be_unique_per_stage_phase(tmp_path: Path):
    """Only one compiled_json owner is allowed per stage+phase."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.compiler.owner_a",
                "kind": "compiler",
                "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 300,
                "compiled_json_owner": True,
            },
            {
                "id": "test.compiler.owner_b",
                "kind": "compiler",
                "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "finalize",
                "order": 301,
                "compiled_json_owner": True,
            },
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)

    try:
        registry.load_manifest(manifest)
        assert False, "Expected PluginLoadError for compiled_json_owner conflict"
    except PluginLoadError as exc:
        assert "compiled_json_owner conflicts" in str(exc)


def test_consumes_requires_depends_on_declaration(tmp_path: Path):
    """Declared consumes must reference producer in depends_on."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.compiler.producer",
                "kind": "compiler",
                "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 10,
                "produces": [{"key": "k1", "scope": "pipeline_shared"}],
            },
            {
                "id": "test.validator.consumer",
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "consumes": [{"from_plugin": "test.compiler.producer", "key": "k1"}],
            },
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    try:
        registry.resolve_dependencies()
        assert False, "Expected consumes/depends_on contract error"
    except PluginLoadError as exc:
        assert "requires 'test.compiler.producer' in depends_on" in str(exc)


def test_stage_local_consumes_across_stages_is_rejected(tmp_path: Path):
    """stage_local produced key cannot be consumed from a different stage."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "test.compiler.producer",
                "kind": "compiler",
                "entry": "plugins/compilers/capability_compiler.py:CapabilityCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 10,
                "produces": [{"key": "k1", "scope": "stage_local"}],
            },
            {
                "id": "test.validator.consumer",
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "depends_on": ["test.compiler.producer"],
                "consumes": [{"from_plugin": "test.compiler.producer", "key": "k1"}],
            },
        ],
    }
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    try:
        registry.resolve_dependencies()
        assert False, "Expected stage_local cross-stage contract error"
    except PluginLoadError as exc:
        assert "stage_local key cannot cross stage boundary" in str(exc)


def test_registry_loads_build_stage_manifest():
    """Runtime Stage enum must allow build-stage manifests to load."""
    manifest = V5_TOOLS / "plugins" / "plugins.yaml"
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    assert registry.get_load_errors() == []


def test_base_manifest_declares_high_value_data_bus_contracts():
    """Base manifest should declare core produces/consumes contracts for key plugins."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    module_loader = registry.specs["base.compiler.module_loader"]
    instance_rows = registry.specs["base.compiler.instance_rows"]
    capability_loader = registry.specs["base.compiler.capability_contract_loader"]
    references = registry.specs["base.validator.references"]

    assert {item["key"] for item in module_loader.produces} >= {
        "class_map",
        "object_map",
        "class_module_paths",
        "object_module_paths",
    }
    assert {item["key"] for item in instance_rows.produces} >= {"normalized_rows"}
    assert {item["key"] for item in capability_loader.produces} >= {"catalog_ids", "packs_map"}
    assert {(item["from_plugin"], item["key"]) for item in references.consumes} >= {
        ("base.compiler.instance_rows", "normalized_rows"),
        ("base.compiler.capability_contract_loader", "catalog_ids"),
    }
    # Ensure declared contracts pass strict dependency validation path.
    registry.resolve_dependencies()


if __name__ == "__main__":
    print("=" * 60)
    print("ADR 0066 Plugin Contract Tests")
    print("=" * 60)
    print()

    tests = [
        test_manifest_loading,
        test_registry_load,
        test_api_version_compatibility,
        test_config_validation,
        test_kernel_info,
        test_plugin_instantiation,
        test_duplicate_plugin_id,
        test_manifest_schema_rejects_unknown_fields,
        test_manifest_schema_accepts_model_versions,
        test_manifest_schema_accepts_phase_field,
        test_manifest_schema_declares_build_stage_and_phase_enum,
        test_schema_and_runtime_stage_phase_enums_stay_in_sync,
        test_manifest_schema_accepts_build_stage_and_new_fields,
        test_plugin_context_scope_backed_publish_subscribe_and_active_config,
        test_plugin_context_blocks_cross_stage_subscribe_for_stage_local_keys,
        test_plugin_context_invalidates_stage_local_keys_on_stage_boundary,
        test_compiled_json_owner_must_be_unique_per_stage_phase,
        test_consumes_requires_depends_on_declaration,
        test_stage_local_consumes_across_stages_is_rejected,
        test_registry_loads_build_stage_manifest,
        test_base_manifest_declares_high_value_data_bus_contracts,
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

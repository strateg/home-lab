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
    """Schema draft includes stage=build and phase enum declarations."""
    schema_path = V5_TOOLS / "schemas" / "plugin-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    plugin_props = schema["$defs"]["plugin"]["properties"]

    assert "build" in plugin_props["stages"]["items"]["enum"]
    assert plugin_props["phase"]["enum"] == ["init", "pre", "run", "post", "verify", "finished"]


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

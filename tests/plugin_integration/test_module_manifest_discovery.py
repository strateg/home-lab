#!/usr/bin/env python3
"""Integration checks for module-level plugin manifest loading (ADR 0063)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module_discovery", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest(path: Path, *, plugin_id: str, description: str = "") -> None:
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": plugin_id,
                "kind": "validator_json",
                "entry": "validators/reference_validator.py:ReferenceValidator",
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 200,
                "description": description,
            }
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _create_compiler(mod, tmp_path: Path):
    out_dir = mod.REPO_ROOT / "build" / "test-module-manifest-discovery" / tmp_path.name
    return mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=out_dir / "effective.json",
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )


def test_module_level_manifests_are_loaded(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(class_root / "alpha" / "plugins.yaml", plugin_id="class.validator.alpha")
    _write_manifest(object_root / "beta" / "plugins.yaml", plugin_id="object.validator.beta")

    compiler._load_plugin_manifests(class_modules_root=class_root, object_modules_root=object_root)

    assert "class.validator.alpha" in compiler._plugin_registry.specs
    assert "object.validator.beta" in compiler._plugin_registry.specs
    assert any(d.code == "I4001" for d in compiler._diagnostics)


def test_duplicate_plugin_id_between_manifests_is_reported(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    _write_manifest(
        class_root / "first" / "plugins.yaml",
        plugin_id="shared.validator.duplicate",
        description="class-version",
    )
    _write_manifest(
        object_root / "second" / "plugins.yaml",
        plugin_id="shared.validator.duplicate",
        description="object-version",
    )

    compiler._load_plugin_manifests(class_modules_root=class_root, object_modules_root=object_root)

    spec = compiler._plugin_registry.specs["shared.validator.duplicate"]
    assert spec.description == "class-version"
    assert any(d.code == "E4001" for d in compiler._diagnostics)


def test_invalid_module_manifest_is_reported_without_crash(tmp_path: Path) -> None:
    mod = _load_compiler_module()
    compiler = _create_compiler(mod, tmp_path)
    assert compiler._plugin_registry is not None

    class_root = tmp_path / "class-modules"
    object_root = tmp_path / "object-modules"
    bad_manifest = class_root / "bad" / "plugins.yaml"
    bad_manifest.parent.mkdir(parents=True, exist_ok=True)
    bad_manifest.write_text("schema_version: 1\nplugins: [\n", encoding="utf-8")

    compiler._load_plugin_manifests(class_modules_root=class_root, object_modules_root=object_root)

    assert any(d.code == "E4001" for d in compiler._diagnostics)

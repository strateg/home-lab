#!/usr/bin/env python3
"""Integration checks for compile-topology + framework lock verification."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_lock_integration", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _create_minimal_repo(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo_root = tmp_path / "repo"
    topology_path = repo_root / "topology" / "topology.yaml"
    framework_manifest = repo_root / "topology" / "framework.yaml"
    project_manifest = repo_root / "projects" / "home-lab" / "project.yaml"
    error_catalog = repo_root / "topology-tools" / "data" / "error-catalog.yaml"

    _write_yaml(
        topology_path,
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "class_modules_root": "topology/class-modules",
                "object_modules_root": "topology/object-modules",
                "model_lock": "topology/model.lock.yaml",
                "profile_map": "topology/profile-map.yaml",
                "layer_contract": "topology/layer-contract.yaml",
                "capability_catalog": "topology/class-modules/L1-foundation/router/capability-catalog.yaml",
                "capability_packs": "topology/class-modules/L1-foundation/router/capability-packs.yaml",
            },
            "project": {
                "active": "home-lab",
                "projects_root": "projects",
            },
        },
    )
    _write_yaml(
        framework_manifest,
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "topology/framework.yaml",
                    "topology/topology.yaml",
                ],
            },
        },
    )
    _write_yaml(
        project_manifest,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",  # pragma: allowlist secret
        },
    )
    _write_yaml(error_catalog, {"version": 1, "tool": "topology-compiler", "codes": {}})
    return repo_root, topology_path, project_manifest, error_catalog


def _create_compiler(mod, *, topology_path: Path, error_catalog_path: Path):
    source_repo_root = Path(__file__).resolve().parents[2]
    output_root = topology_path.parent.parent.parent / "build" / "compile-lock-tests"
    return mod.V5Compiler(
        manifest_path=topology_path,
        output_json=output_root / "effective-topology.json",
        diagnostics_json=output_root / "diagnostics.json",
        diagnostics_txt=output_root / "diagnostics.txt",
        error_catalog_path=error_catalog_path,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
        plugins_manifest_path=source_repo_root / "topology-tools" / "plugins" / "plugins.yaml",
    )


def test_compile_fails_when_framework_lock_missing(monkeypatch, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    repo_root, topology_path, _, error_catalog_path = _create_minimal_repo(tmp_path)
    monkeypatch.setattr(mod, "REPO_ROOT", repo_root)

    compiler = _create_compiler(mod, topology_path=topology_path, error_catalog_path=error_catalog_path)
    exit_code = compiler.run()

    assert exit_code == 1
    assert any(diag.code == "E7822" for diag in compiler._diagnostics)


def test_compile_fails_when_framework_integrity_mismatch(monkeypatch, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    repo_root, topology_path, _, error_catalog_path = _create_minimal_repo(tmp_path)
    monkeypatch.setattr(mod, "REPO_ROOT", repo_root)

    lock_path = repo_root / "projects" / "home-lab" / "framework.lock.yaml"
    _write_yaml(
        lock_path,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project_contract_revision": 1,
            "framework": {
                "id": "home-lab-v5-framework",
                "version": "5.0.0",
                "source": "git",
                "repository": "https://example.invalid/infra-topology-framework.git",
                "revision": "0123456789abcdef",
                "integrity": "sha256-deadbeef",
            },
            "locked_at": "2026-03-20T12:00:00+00:00",
        },
    )

    compiler = _create_compiler(mod, topology_path=topology_path, error_catalog_path=error_catalog_path)
    exit_code = compiler.run()

    assert exit_code == 1
    assert any(diag.code == "E7824" for diag in compiler._diagnostics)


def test_compile_lock_check_uses_extracted_framework_manifest_when_present(monkeypatch, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    repo_root, topology_path, project_manifest_path, error_catalog_path = _create_minimal_repo(tmp_path)
    monkeypatch.setattr(mod, "REPO_ROOT", repo_root)

    _write_yaml(
        repo_root / "framework-extracted" / "framework.yaml",
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "framework.yaml",
                ],
            },
        },
    )

    compiler = _create_compiler(mod, topology_path=topology_path, error_catalog_path=error_catalog_path)
    ok = compiler._verify_framework_lock(
        project_id="home-lab",
        project_root=repo_root / "projects" / "home-lab",
        project_manifest_path=project_manifest_path,
        framework_paths={"root": "framework-extracted"},
    )
    assert ok is False
    assert any(diag.code == "E7822" for diag in compiler._diagnostics)
    assert not any(diag.code == "E7821" for diag in compiler._diagnostics)


def test_compile_parser_defaults_catalog_and_plugins_to_script_paths() -> None:
    mod = _load_compiler_module()
    parser = mod.build_parser()
    args = parser.parse_args([])
    assert Path(args.error_catalog) == mod.DEFAULT_ERROR_CATALOG
    assert Path(args.plugins_manifest) == mod.DEFAULT_PLUGINS_MANIFEST


def test_resolve_topology_path_falls_back_to_standalone_topology_yaml(monkeypatch, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    repo_root = tmp_path / "external-project"
    repo_root.mkdir(parents=True, exist_ok=True)
    standalone_topology = repo_root / "topology.yaml"
    standalone_topology.write_text("version: 5.0.0\n", encoding="utf-8")

    monkeypatch.setattr(mod, "REPO_ROOT", repo_root)

    resolved = mod.resolve_topology_path(mod.DEFAULT_TOPOLOGY_RELATIVE)

    assert resolved == standalone_topology


def test_resolve_topology_path_keeps_default_monorepo_target_when_no_fallback(monkeypatch, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    repo_root = tmp_path / "empty-project"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mod, "REPO_ROOT", repo_root)

    resolved = mod.resolve_topology_path(mod.DEFAULT_TOPOLOGY_RELATIVE)

    assert resolved == repo_root / mod.DEFAULT_TOPOLOGY_RELATIVE


def test_compile_supports_project_manifest_at_projects_root(monkeypatch, tmp_path: Path) -> None:
    mod = _load_compiler_module()
    repo_root = tmp_path / "project-repo"
    topology_path = repo_root / "topology.yaml"
    project_manifest_path = repo_root / "project.yaml"
    framework_manifest_path = repo_root / "framework" / "framework.yaml"
    error_catalog_path = repo_root / "error-catalog.yaml"

    _write_yaml(
        topology_path,
        {
            "version": "5.0.0",
            "model": "class-object-instance",
            "framework": {
                "root": "framework",
                "class_modules_root": "framework/class-modules",
                "object_modules_root": "framework/object-modules",
                "model_lock": "framework/model.lock.yaml",
                "profile_map": "framework/profile-map.yaml",
                "layer_contract": "framework/layer-contract.yaml",
                "capability_catalog": "framework/class-modules/L1-foundation/router/capability-catalog.yaml",
                "capability_packs": "framework/class-modules/L1-foundation/router/capability-packs.yaml",
            },
            "project": {
                "active": "home-lab",
                "projects_root": ".",
            },
        },
    )
    _write_yaml(
        project_manifest_path,
        {
            "schema_version": 1,
            "project_schema_version": "1.0.0",
            "project": "home-lab",
            "project_min_framework_version": "5.0.0",
            "project_contract_revision": 1,
            "instances_root": "instances",
            "secrets_root": "secrets",  # pragma: allowlist secret
        },
    )
    _write_yaml(
        framework_manifest_path,
        {
            "schema_version": 1,
            "framework_id": "home-lab-v5-framework",
            "framework_api_version": "5.0.0",
            "supported_project_schema_range": ">=1.0.0 <2.0.0",
            "distribution": {
                "layout_version": 1,
                "include": [
                    "framework.yaml",
                ],
            },
        },
    )
    _write_yaml(error_catalog_path, {"version": 1, "tool": "topology-compiler", "codes": {}})
    monkeypatch.setattr(mod, "REPO_ROOT", repo_root)

    compiler = _create_compiler(mod, topology_path=topology_path, error_catalog_path=error_catalog_path)
    exit_code = compiler.run()

    assert exit_code == 1
    assert any(diag.code == "E7822" for diag in compiler._diagnostics)
    assert not any("home-lab/project.yaml" in diag.path for diag in compiler._diagnostics if diag.code == "E1001")

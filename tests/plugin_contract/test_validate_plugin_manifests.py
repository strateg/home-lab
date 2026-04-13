#!/usr/bin/env python3
"""Targeted tests for plugin manifest validation warnings."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import yaml


def _load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "validation" / "validate_plugin_manifests.py"
    spec = importlib.util.spec_from_file_location("validate_plugin_manifests_test_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_repo_fixture(
    tmp_path: Path,
    *,
    entry: str,
    source: str,
    config_schema: dict | None = None,
) -> tuple[Path, dict]:
    repo_root = tmp_path / "repo"
    manifest_dir = repo_root / "topology-tools" / "plugins"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "topology" / "class-modules").mkdir(parents=True, exist_ok=True)
    (repo_root / "topology" / "object-modules").mkdir(parents=True, exist_ok=True)
    schema_src = Path(__file__).resolve().parents[2] / "topology-tools" / "schemas" / "plugin-manifest.schema.json"
    schema_dst = repo_root / "topology-tools" / "schemas" / "plugin-manifest.schema.json"
    schema_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(schema_src, schema_dst)

    module_rel, _sep, _symbol = entry.partition(":")
    module_path = manifest_dir / module_rel
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(source, encoding="utf-8")

    plugin = {
        "id": "test.assembler.fixture",
        "kind": "assembler",
        "entry": entry,
        "api_version": "1.x",
        "stages": ["assemble"],
        "phase": "run",
        "order": 100,
        "timeout": 30,
        "config": {},
        "config_schema": config_schema
        or {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "description": "Fixture plugin manifest.",
    }
    manifest = {"schema_version": 1, "plugins": [plugin]}
    (manifest_dir / "plugins.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return repo_root, plugin


def test_config_schema_warning_ignores_runtime_context_keys(tmp_path: Path) -> None:
    mod = _load_module()
    repo_root, plugin = _write_repo_fixture(
        tmp_path,
        entry="assemblers/runtime_only.py:RuntimeOnlyAssembler",
        source="""
class RuntimeOnlyAssembler:
    def run(self, ctx):
        return (
            ctx.config.get("repo_root"),
            ctx.config.get("validation_owner_runtime_only"),
        )
""".strip() + "\n",
    )

    warning = mod._config_schema_warning(plugin, repo_root / "topology-tools" / "plugins")

    assert warning is None


def test_config_schema_warning_reports_missing_plugin_specific_key(tmp_path: Path) -> None:
    mod = _load_module()
    repo_root, plugin = _write_repo_fixture(
        tmp_path,
        entry="assemblers/deploy_bundle.py:DeployBundleAssembler",
        source="""
class DeployBundleAssembler:
    def run(self, ctx):
        return ctx.config.get("deploy_bundles_root")
""".strip() + "\n",
    )

    warning = mod._config_schema_warning(plugin, repo_root / "topology-tools" / "plugins")

    assert warning == (
        "test.assembler.fixture: entry consumes ctx.config keys without config_schema coverage: deploy_bundles_root"
    )


def test_main_can_fail_on_warnings(tmp_path: Path, monkeypatch, capsys) -> None:
    mod = _load_module()
    repo_root, _plugin = _write_repo_fixture(
        tmp_path,
        entry="assemblers/deploy_bundle.py:DeployBundleAssembler",
        source="""
class DeployBundleAssembler:
    def run(self, ctx):
        return ctx.config.get("deploy_bundles_root")
""".strip() + "\n",
    )

    monkeypatch.setattr(mod, "_repo_root", lambda: repo_root)

    assert mod.main([]) == 0
    default_out = capsys.readouterr().out
    assert "WARN config_schema:" in default_out
    assert "All plugin manifests validated" in default_out

    assert mod.main(["--fail-on-warnings"]) == 1
    strict_out = capsys.readouterr().out
    assert "WARN config_schema:" in strict_out
    assert "ERROR: plugin manifest warnings detected: 1" in strict_out

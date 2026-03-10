#!/usr/bin/env python3
"""Integration checks for ADR0069 WS1 stage wiring."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "v5" / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pipeline_stage_order_and_compiled_context(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "v5-build" / "test-stage-order"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=test_output_dir / "effective-topology.json",
        diagnostics_json=test_output_dir / "diagnostics.json",
        diagnostics_txt=test_output_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    seen_stages: list[str] = []

    def _record_execute_plugins(*, stage, ctx):
        seen_stages.append(stage.value)
        if stage.value in {"validate", "generate"}:
            assert isinstance(ctx.compiled_json, dict)
            assert "instances" in ctx.compiled_json

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)

    exit_code = compiler.run()

    assert exit_code == 0
    assert seen_stages == ["compile", "validate", "generate"]


def test_pipeline_mode_plugin_first_requires_plugins():
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "v5-build" / "test-pipeline-mode-no-plugins"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=test_output_dir / "effective-topology.json",
        diagnostics_json=test_output_dir / "diagnostics.json",
        diagnostics_txt=test_output_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        pipeline_mode="plugin-first",
        enable_plugins=False,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 1
    assert any(d.code == "E6901" for d in compiler._diagnostics)


def test_pipeline_mode_plugin_first_uses_plugin_compiled_json(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "v5-build" / "test-pipeline-mode-plugin-first"
    output_path = test_output_dir / "effective-topology.json"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=output_path,
        diagnostics_json=test_output_dir / "diagnostics.json",
        diagnostics_txt=test_output_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        pipeline_mode="plugin-first",
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    plugin_payload = {
        "version": "plugin-first",
        "model": "plugin-candidate",
        "generated_at": "2026-03-11T00:00:00+00:00",
        "topology_manifest": "test",
        "classes": {},
        "objects": {},
        "instances": {},
    }

    def _record_execute_plugins(*, stage, ctx):
        if stage.value == "compile":
            ctx.compiled_json = plugin_payload
            ctx.plugin_outputs["base.compiler.module_loader"] = {
                "class_map": {},
                "object_map": {},
            }
            ctx.plugin_outputs["base.compiler.instance_rows"] = {"normalized_rows": []}
            ctx.plugin_outputs["base.compiler.capability_contract_loader"] = {
                "catalog_ids": [],
                "packs_map": {},
            }
        if stage.value == "generate":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(ctx.compiled_json), encoding="utf-8")

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)

    exit_code = compiler.run()

    assert exit_code == 0
    assert output_path.exists()
    emitted = json.loads(output_path.read_text(encoding="utf-8"))
    assert emitted == plugin_payload
    assert any(d.code == "I6901" for d in compiler._diagnostics)


def test_parity_gate_fails_on_drift(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "v5-build" / "test-parity-gate-drift"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=test_output_dir / "effective-topology.json",
        diagnostics_json=test_output_dir / "diagnostics.json",
        diagnostics_txt=test_output_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        pipeline_mode="legacy",
        parity_gate=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    plugin_payload = {
        "version": "plugin-first",
        "model": "drift",
        "generated_at": "2026-03-11T00:00:00+00:00",
        "topology_manifest": "test",
        "classes": {},
        "objects": {},
        "instances": {},
    }

    def _record_execute_plugins(*, stage, ctx):
        if stage.value == "compile":
            ctx.compiled_json = plugin_payload

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)

    exit_code = compiler.run()
    assert exit_code == 1
    assert any(d.code == "E6902" for d in compiler._diagnostics)

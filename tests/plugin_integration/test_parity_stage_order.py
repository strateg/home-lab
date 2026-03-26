#!/usr/bin/env python3
"""Integration checks for ADR0069 WS1 stage wiring."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_compiler_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _publish_minimal_compile_outputs(ctx) -> None:
    ctx._set_execution_context("base.compiler.module_loader", set())
    ctx.publish("class_map", {})
    ctx.publish("object_map", {})
    ctx._clear_execution_context()

    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", [])
    ctx._clear_execution_context()

    ctx._set_execution_context("base.compiler.capability_contract_loader", set())
    ctx.publish("catalog_ids", [])
    ctx.publish("packs_map", {})
    ctx._clear_execution_context()


def test_pipeline_stage_order_and_compiled_context(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-stage-order"

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
        if stage.value == "compile":
            ctx.compiled_json = {
                "version": "plugin-first",
                "model": "test-stage-order",
                "generated_at": "2026-03-11T00:00:00+00:00",
                "compiled_model_version": "1.0",
                "compiled_at": "2026-03-11T00:00:00+00:00",
                "compiler_pipeline_version": "adr0069-ws2",
                "source_manifest_digest": "test-manifest-digest",
                "topology_manifest": "test",
                "classes": {},
                "objects": {},
                "instances": {},
            }
            _publish_minimal_compile_outputs(ctx)
        if stage.value == "generate":
            compiler.output_json.parent.mkdir(parents=True, exist_ok=True)
            compiler.output_json.write_text(json.dumps(ctx.compiled_json), encoding="utf-8")
        seen_stages.append(stage.value)
        if stage.value in {"validate", "generate"}:
            assert isinstance(ctx.compiled_json, dict)
            assert "instances" in ctx.compiled_json

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)

    exit_code = compiler.run()

    assert exit_code == 0
    assert seen_stages == ["discover", "compile", "validate", "generate", "assemble", "build"]


def test_pipeline_mode_plugin_first_rejects_disabled_plugins_flag():
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-pipeline-mode-no-plugins"

    try:
        mod.V5Compiler(
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
    except ValueError as exc:
        assert "--disable-plugins is retired" in str(exc)
    else:
        raise AssertionError("Expected ValueError for enable_plugins=False in plugin-first runtime")


def test_pipeline_mode_plugin_first_uses_plugin_compiled_json(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-pipeline-mode-plugin-first"
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
        "compiled_model_version": "1.0",
        "compiled_at": "2026-03-11T00:00:00+00:00",
        "compiler_pipeline_version": "adr0069-ws2",
        "source_manifest_digest": "test-manifest-digest",
        "topology_manifest": "test",
        "classes": {},
        "objects": {},
        "instances": {},
    }

    def _record_execute_plugins(*, stage, ctx):
        if stage.value == "compile":
            ctx.compiled_json = plugin_payload
            _publish_minimal_compile_outputs(ctx)
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


def test_pipeline_mode_legacy_is_rejected():
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-legacy-mode-rejected"

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
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 1
    assert any(d.code == "E6904" for d in compiler._diagnostics)


def test_parity_gate_is_rejected_after_cutover():
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-parity-gate-retired"

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
        parity_gate=True,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 1
    assert any(d.code == "E6905" for d in compiler._diagnostics)


def test_compiled_model_contract_rejects_incompatible_version(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-compiled-contract-version"

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
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    plugin_payload = {
        "version": "plugin-first",
        "model": "plugin-candidate",
        "generated_at": "2026-03-11T00:00:00+00:00",
        "compiled_model_version": "2.0",
        "compiled_at": "2026-03-11T00:00:00+00:00",
        "compiler_pipeline_version": "adr0069-ws2",
        "source_manifest_digest": "test-manifest-digest",
        "topology_manifest": "test",
        "classes": {},
        "objects": {},
        "instances": {},
    }

    def _record_execute_plugins(*, stage, ctx):
        if stage.value == "compile":
            ctx.compiled_json = plugin_payload
            _publish_minimal_compile_outputs(ctx)

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)

    exit_code = compiler.run()
    assert exit_code == 1
    assert any(d.code == "E6903" for d in compiler._diagnostics)


def test_runtime_profile_is_propagated_to_plugin_context(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-runtime-profile"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=test_output_dir / "effective-topology.json",
        diagnostics_json=test_output_dir / "diagnostics.json",
        diagnostics_txt=test_output_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=False,
        fail_on_warning=False,
        require_new_model=True,
        runtime_profile="modeled",
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    seen_profiles: list[str] = []

    def _record_execute_plugins(*, stage, ctx):
        if stage.value == "compile":
            ctx.compiled_json = {
                "version": "plugin-first",
                "model": "test-runtime-profile",
                "generated_at": "2026-03-11T00:00:00+00:00",
                "compiled_model_version": "1.0",
                "compiled_at": "2026-03-11T00:00:00+00:00",
                "compiler_pipeline_version": "adr0069-ws2",
                "source_manifest_digest": "test-manifest-digest",
                "topology_manifest": "test",
                "classes": {},
                "objects": {},
                "instances": {},
            }
            _publish_minimal_compile_outputs(ctx)
        if stage.value == "generate":
            compiler.output_json.parent.mkdir(parents=True, exist_ok=True)
            compiler.output_json.write_text(json.dumps(ctx.compiled_json), encoding="utf-8")
        seen_profiles.append(ctx.profile)

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)

    exit_code = compiler.run()
    assert exit_code == 0
    assert seen_profiles == ["modeled", "modeled", "modeled", "modeled", "modeled", "modeled"]


def test_compile_stage_uses_fail_fast_in_registry(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-compile-fail-fast-flag"

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
    assert compiler._plugin_registry is not None

    calls: list[tuple[str, bool]] = []

    def _fake_execute_stage(stage, ctx, profile=None, fail_fast=False):
        _ = (ctx, profile)
        calls.append((stage.value, fail_fast))
        return []

    monkeypatch.setattr(compiler._plugin_registry, "execute_stage", _fake_execute_stage)

    ctx = mod.PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
    )

    compiler._execute_plugins(stage=mod.Stage.COMPILE, ctx=ctx)
    compiler._execute_plugins(stage=mod.Stage.VALIDATE, ctx=ctx)

    assert calls == [("compile", True), ("validate", False)]


def test_execute_plugins_propagates_contract_modes_to_registry(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-plugin-contract-flags"

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
        plugin_contract_warnings=True,
        plugin_contract_errors=True,
    )
    assert compiler._plugin_registry is not None

    calls: list[dict[str, object]] = []

    def _fake_execute_stage(stage, ctx, profile=None, fail_fast=False, **kwargs):
        _ = (ctx, profile)
        calls.append(
            {
                "stage": stage.value,
                "fail_fast": fail_fast,
                "contract_warnings": kwargs.get("contract_warnings", False),
                "contract_errors": kwargs.get("contract_errors", False),
            }
        )
        return []

    monkeypatch.setattr(compiler._plugin_registry, "execute_stage", _fake_execute_stage)

    ctx = mod.PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
    )

    compiler._execute_plugins(stage=mod.Stage.COMPILE, ctx=ctx)
    compiler._execute_plugins(stage=mod.Stage.VALIDATE, ctx=ctx)

    assert calls == [
        {
            "stage": "compile",
            "fail_fast": True,
            "contract_warnings": True,
            "contract_errors": True,
        },
        {
            "stage": "validate",
            "fail_fast": False,
            "contract_warnings": True,
            "contract_errors": True,
        },
    ]


def test_strict_only_rejects_legacy_instance_bindings_path():
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-strict-only-legacy-paths"
    topology_path = test_output_dir / "topology.yaml"
    topology_path.parent.mkdir(parents=True, exist_ok=True)
    topology_path.write_text(
        json.dumps(
            {
                "version": "5.0.0",
                "model": "class-object-instance",
                "paths": {
                    "class_modules_root": "topology/class-modules",
                    "object_modules_root": "topology/object-modules",
                    "capability_catalog": "topology/class-modules/router/capability-catalog.yaml",
                    "capability_packs": "topology/class-modules/router/capability-packs.yaml",
                    "layer_contract": "topology/layer-contract.yaml",
                    "model_lock": "topology/model.lock.yaml",
                    "instances_root": "topology/instances",
                    "instance_bindings": "topology/instances/_legacy-home-lab/instance-bindings.yaml",
                },
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
    )

    compiler = mod.V5Compiler(
        manifest_path=topology_path,
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

    exit_code = compiler.run()

    assert exit_code == 1
    assert any(d.code == "E7808" for d in compiler._diagnostics)

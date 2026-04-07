#!/usr/bin/env python3
"""Integration checks for ADR0069 WS1 stage wiring."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
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

    calls: list[tuple[str, bool, bool]] = []

    def _fake_execute_stage(stage, ctx, profile=None, fail_fast=False, **kwargs):
        _ = (ctx, profile)
        calls.append((stage.value, fail_fast, bool(kwargs.get("parallel_plugins", False))))
        return []

    monkeypatch.setattr(compiler._plugin_registry, "execute_stage", _fake_execute_stage)

    ctx = mod.PluginContext(
        topology_path="test",
        profile="test-real",
        model_lock={},
    )

    compiler._execute_plugins(stage=mod.Stage.COMPILE, ctx=ctx)
    compiler._execute_plugins(stage=mod.Stage.VALIDATE, ctx=ctx)

    assert calls == [("compile", True, True), ("validate", False, True)]


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


def test_plugin_contract_errors_enabled_by_default():
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-plugin-contract-defaults"

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

    assert compiler.plugin_contract_warnings is False
    assert compiler.plugin_contract_errors is True


def test_parser_allows_disabling_default_plugin_contract_errors():
    mod = _load_compiler_module()
    parser = mod.build_parser()
    defaults = parser.parse_args([])
    disabled = parser.parse_args(["--no-plugin-contract-errors"])

    assert defaults.plugin_contract_errors is True
    assert disabled.plugin_contract_errors is False


def test_parser_accepts_ai_advisory_flags():
    mod = _load_compiler_module()
    parser = mod.build_parser()
    args = parser.parse_args(
        [
            "--ai-advisory",
            "--ai-assisted",
            "--ai-output-json",
            "build/ai-output.json",
            "--ai-audit-retention-days",
            "14",
            "--ai-sandbox-retention-days",
            "3",
            "--ai-sandbox-max-files",
            "16",
            "--ai-sandbox-max-bytes",
            "4096",
            "--ai-promote-approved",
            "--ai-approve-all",
            "--ai-approve-paths",
            "generated/home-lab/docs/a.md,generated/home-lab/docs/b.md",
        ]
    )

    assert args.ai_advisory is True
    assert args.ai_assisted is True
    assert args.ai_output_json == "build/ai-output.json"
    assert args.ai_audit_retention_days == 14
    assert args.ai_sandbox_retention_days == 3
    assert args.ai_sandbox_max_files == 16
    assert args.ai_sandbox_max_bytes == 4096
    assert args.ai_promote_approved is True
    assert args.ai_approve_all is True
    assert args.ai_approve_paths == "generated/home-lab/docs/a.md,generated/home-lab/docs/b.md"


def test_main_ai_advisory_forces_read_only_stage_set(monkeypatch, tmp_path):
    mod = _load_compiler_module()
    ai_output_path = tmp_path / "ai-output.json"
    ai_output_path.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    class _FakeCompiler:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self) -> int:
            return 0

    monkeypatch.setattr(mod, "V5Compiler", _FakeCompiler)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile-topology.py",
            "--ai-advisory",
            "--stages",
            "discover,compile,validate,generate,assemble,build",
            "--ai-output-json",
            str(ai_output_path),
        ],
    )

    exit_code = mod.main()

    assert exit_code == 0
    assert captured["ai_advisory"] is True
    assert captured["ai_assisted"] is False
    assert captured["stages"] == [mod.Stage.DISCOVER, mod.Stage.COMPILE, mod.Stage.VALIDATE]
    assert captured["ai_output_json"] == ai_output_path
    assert captured["ai_audit_retention_days"] == 30
    assert captured["ai_sandbox_retention_days"] == 7
    assert captured["ai_sandbox_max_files"] == 128
    assert captured["ai_sandbox_max_bytes"] == 10 * 1024 * 1024
    assert captured["ai_promote_approved"] is False
    assert captured["ai_approve_all"] is False
    assert captured["ai_approve_paths"] == ()


def test_main_ai_assisted_forces_read_only_stage_set(monkeypatch, tmp_path):
    mod = _load_compiler_module()
    ai_output_path = tmp_path / "ai-output.json"
    ai_output_path.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    class _FakeCompiler:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self) -> int:
            return 0

    monkeypatch.setattr(mod, "V5Compiler", _FakeCompiler)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile-topology.py",
            "--ai-assisted",
            "--stages",
            "discover,compile,validate,generate,assemble,build",
            "--ai-output-json",
            str(ai_output_path),
        ],
    )

    exit_code = mod.main()

    assert exit_code == 0
    assert captured["ai_advisory"] is False
    assert captured["ai_assisted"] is True
    assert captured["stages"] == [mod.Stage.DISCOVER, mod.Stage.COMPILE, mod.Stage.VALIDATE]


def test_main_rejects_simultaneous_ai_modes(monkeypatch):
    mod = _load_compiler_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile-topology.py",
            "--ai-advisory",
            "--ai-assisted",
        ],
    )
    assert mod.main() == 1


def test_main_rejects_promotion_without_assisted(monkeypatch):
    mod = _load_compiler_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compile-topology.py",
            "--ai-promote-approved",
        ],
    )
    assert mod.main() == 1


def test_ai_advisory_payload_normalizer_handles_non_json_scalars():
    mod = _load_compiler_module()
    normalized = mod.V5Compiler._json_safe_payload({"today": date(2026, 4, 7), "ok": True})

    assert normalized["today"] == "2026-04-07"
    assert normalized["ok"] is True


def test_ai_advisory_redaction_patterns_collect_from_annotations_and_registry(tmp_path):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-ai-advisory-redaction-patterns"
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
    ctx = mod.PluginContext(topology_path="test", profile="test-real", model_lock={})
    secrets_root = tmp_path / "secrets"
    (secrets_root / "instances").mkdir(parents=True, exist_ok=True)
    (secrets_root / "instances" / "r1.yaml").write_text(
        "instance: r1\nserial_number: SN-001\nnested:\n  interface_mac: aa:bb:cc:dd:ee:ff\n",
        encoding="utf-8",
    )
    ctx.config["secrets_root"] = str(secrets_root)

    ctx._set_execution_context("base.compiler.annotation_resolver", set())
    ctx.publish(
        "row_annotations_by_instance",
        {"r1": {"hardware.serial_number": {"secret": True}, "nested.plain": {"secret": False}}},
    )
    ctx.publish(
        "object_secret_annotations",
        {"obj": {"credentials.api_token": {"secret": True}}},
    )
    ctx._clear_execution_context()

    annotation_patterns = compiler._collect_annotation_redaction_patterns(ctx)
    registry_patterns = compiler._collect_registry_redaction_patterns(ctx)

    assert any(pattern.fullmatch("serial_number") for pattern in annotation_patterns)
    assert any(pattern.fullmatch("api_token") for pattern in annotation_patterns)
    assert any(pattern.fullmatch("serial_number") for pattern in registry_patterns)
    assert any(pattern.fullmatch("interface_mac") for pattern in registry_patterns)


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


def test_stage_selection_runs_compile_and_validate_only(monkeypatch):
    mod = _load_compiler_module()
    test_output_dir = mod.REPO_ROOT / "build" / "test-stage-selection-compile-validate"

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
        stages=[mod.Stage.COMPILE, mod.Stage.VALIDATE],
    )

    seen_stages: list[str] = []

    def _record_execute_plugins(*, stage, ctx):
        if stage.value == "compile":
            ctx.compiled_json = {
                "version": "plugin-first",
                "model": "test-stage-selection",
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
        seen_stages.append(stage.value)

    monkeypatch.setattr(compiler, "_execute_plugins", _record_execute_plugins)
    exit_code = compiler.run()
    assert exit_code == 0
    assert seen_stages == ["compile", "validate"]

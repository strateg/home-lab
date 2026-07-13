#!/usr/bin/env python3
"""execute_stage gates: capability preflight, model-version guards,
finalize-phase guarantees and skip predicates.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level; gate implementations live in
kernel/scheduler/preflight.py and stage_executor.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (  # noqa: E402
    PluginContext,
    PluginRegistry,
    PluginResult,
    PluginStatus,
    ValidatorJsonPlugin,
)
from kernel.plugin_base import PluginDiagnostic, Stage  # noqa: E402

REFERENCE_VALIDATOR_ENTRY = "plugins/validators/reference_validator.py:ReferenceValidator"


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


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

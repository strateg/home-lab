#!/usr/bin/env python3
"""execute_stage stage-local output invalidation and execution
trace events.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (  # noqa: E402
    PluginContext,
    PluginDataExchangeError,
    PluginRegistry,
    PluginResult,
    PluginStatus,
    ValidatorJsonPlugin,
)
from kernel.plugin_base import Stage  # noqa: E402


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


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

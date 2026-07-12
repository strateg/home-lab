#!/usr/bin/env python3
"""Pre-fix invariant tests for execute_stage hidden behavior (S6 gate).

PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07 S6 risk control: before
moving `execute_stage` to `scheduler/stage_executor.py` and the
model-version/capability gates to `scheduler/preflight.py`, pin down the
invariants that are easy to lose during extraction:

- I4013 when-predicate skip results (with "when=false" trace message)
- `finally` block guarantees: stage-local invalidation, pipeline-state
  sync back to context, and the stage_end trace event - even when an
  internal (non-plugin) error propagates out of the stage
- gate early returns (E4011 model guard, E4010 capability guard) still
  pass through the `finally` block (stage_end emitted)

Complements test_execute_stage_runs_finalize_on_fail_fast and
test_execute_stage_invalidates_stage_local_outputs in the frozen
tests/test_plugin_registry.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _context(**overrides) -> PluginContext:
    kwargs = dict(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )
    kwargs.update(overrides)
    return PluginContext(**kwargs)


PUBLISHER_MODULE = "\n".join(
    [
        "from kernel import PluginResult, ValidatorJsonPlugin",
        "",
        "class PublisherPlugin(ValidatorJsonPlugin):",
        "    def execute(self, ctx, stage):",
        "        ctx.publish('tmp_key', 'stage-local-value')",
        "        ctx.publish('shared_key', 'shared-value')",
        "        return PluginResult.success(self.plugin_id, self.api_version)",
        "",
        "class NoopPlugin(ValidatorJsonPlugin):",
        "    def execute(self, ctx, stage):",
        "        return PluginResult.success(self.plugin_id, self.api_version)",
    ]
)


def test_when_skip_emits_i4013_result_and_trace(tmp_path: Path) -> None:
    """when=false plugins produce SKIPPED results with I4013 and a trace entry."""
    _write_module(tmp_path / "invariant_plugins.py", PUBLISHER_MODULE)
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "invariant.validator_json.gated",
                    "kind": "validator_json",
                    "entry": "invariant_plugins.py:NoopPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                    "when": {"profiles": ["production"]},
                },
                {
                    "id": "invariant.validator_json.active",
                    "kind": "validator_json",
                    "entry": "invariant_plugins.py:NoopPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 150,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()  # profile="test" != "production"

    results = registry.execute_stage(Stage.VALIDATE, ctx, trace_execution=True)

    by_id = {result.plugin_id: result for result in results}
    skipped = by_id["invariant.validator_json.gated"]
    assert skipped.status == PluginStatus.SKIPPED
    assert [diag.code for diag in skipped.diagnostics] == ["I4013"]
    assert "skipped by when predicates" in skipped.diagnostics[0].message
    assert by_id["invariant.validator_json.active"].status == PluginStatus.SUCCESS

    trace = registry.get_execution_trace()
    skip_events = [
        entry
        for entry in trace
        if entry["event"] == "plugin_result" and entry.get("plugin_id") == "invariant.validator_json.gated"
    ]
    assert len(skip_events) == 1
    assert skip_events[0].get("message") == "when=false"
    assert skip_events[0].get("status") == PluginStatus.SKIPPED.value


def test_finally_invalidates_and_syncs_on_internal_error(tmp_path: Path) -> None:
    """Internal (non-plugin) errors still invalidate stage-local data and sync state.

    A RuntimeError from snapshot building is NOT a PluginDataExchangeError,
    so it propagates out of execute_stage. The finally block must still:
    - invalidate stage_local published keys
    - sync pipeline state back to the context (shared key stays visible)
    - emit the stage_end trace event
    """
    _write_module(tmp_path / "invariant_plugins.py", PUBLISHER_MODULE)
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "invariant.validator_json.publisher",
                    "kind": "validator_json",
                    "entry": "invariant_plugins.py:PublisherPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                    "produces": [
                        {"key": "tmp_key", "scope": "stage_local"},
                        {"key": "shared_key", "scope": "pipeline_shared"},
                    ],
                },
                {
                    "id": "invariant.validator_json.second",
                    "kind": "validator_json",
                    "entry": "invariant_plugins.py:NoopPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 150,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    original = registry._build_input_snapshot

    def flaky_build(*, plugin_id, stage, phase, ctx, pipeline_state=None):
        if plugin_id == "invariant.validator_json.second":
            raise RuntimeError("forced snapshot infrastructure error")
        return original(plugin_id=plugin_id, stage=stage, phase=phase, ctx=ctx, pipeline_state=pipeline_state)

    with patch.object(registry, "_build_input_snapshot", side_effect=flaky_build):
        with pytest.raises(RuntimeError, match="forced snapshot infrastructure error"):
            registry.execute_stage(Stage.VALIDATE, ctx, trace_execution=True)

    published_keys = ctx.get_published_keys("invariant.validator_json.publisher")
    assert "tmp_key" not in published_keys, "stage_local key must be invalidated in finally"
    assert "shared_key" in published_keys, "pipeline state must be synced to context in finally"

    trace = registry.get_execution_trace()
    stage_end_events = [entry for entry in trace if entry["event"] == "stage_end"]
    assert len(stage_end_events) == 1
    assert "invalidated_stage_local=" in stage_end_events[0].get("message", "")


def test_model_version_guard_early_return_passes_finally(tmp_path: Path) -> None:
    """E4011 model-version gate returns a single guard result and still emits stage_end."""
    _write_module(tmp_path / "invariant_plugins.py", PUBLISHER_MODULE)
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "invariant.validator_json.active",
                    "kind": "validator_json",
                    "entry": "invariant_plugins.py:NoopPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context(model_lock={"core_model_version": "99.0"})

    results = registry.execute_stage(Stage.VALIDATE, ctx, trace_execution=True)

    assert [result.plugin_id for result in results] == ["kernel.model_version_guard"]
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E4011" for diag in results[0].diagnostics)

    trace = registry.get_execution_trace()
    events = [entry["event"] for entry in trace]
    assert "stage_start" in events
    assert "stage_end" in events


def test_capability_guard_early_return_passes_finally(tmp_path: Path) -> None:
    """E4010 capability gate returns a single guard result and still emits stage_end."""
    _write_module(tmp_path / "invariant_plugins.py", PUBLISHER_MODULE)
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "invariant.validator_json.needy",
                    "kind": "validator_json",
                    "entry": "invariant_plugins.py:NoopPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                    "requires_capabilities": ["missing.capability.token"],
                }
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, trace_execution=True)

    assert [result.plugin_id for result in results] == ["kernel.capability_guard"]
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E4010" for diag in results[0].diagnostics)

    trace = registry.get_execution_trace()
    events = [entry["event"] for entry in trace]
    assert "stage_start" in events
    assert "stage_end" in events

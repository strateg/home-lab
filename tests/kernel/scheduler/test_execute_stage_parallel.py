#!/usr/bin/env python3
"""execute_stage parallel-mode determinism and pipeline-state
commit semantics for parallel-compatible plugins.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level; the implementation lives in
kernel/scheduler/parallel_executor.py and execution_planner.py.
"""

from __future__ import annotations

import sys
import time
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
from kernel.plugin_base import Stage  # noqa: E402


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_module(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_execute_stage_parallel_keeps_deterministic_order(tmp_path: Path):
    """Parallel phase execution should return results in deterministic plugin order."""
    _write_module(
        tmp_path / "parallel_plugins.py",
        "\n".join(
            [
                "import time",
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class SleepPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        sleep_ms = int(ctx.active_config.get('sleep_ms', 0))",
                "        if sleep_ms > 0:",
                "            time.sleep(sleep_ms / 1000.0)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "parallel.validator_json.first",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "config": {"sleep_ms": 80},
            },
            {
                "id": "parallel.validator_json.second",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 150,
                "config": {"sleep_ms": 5},
            },
            {
                "id": "parallel.validator_json.third",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 188,
                "config": {"sleep_ms": 30},
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

    sequential = registry.execute_stage(Stage.VALIDATE, ctx)
    parallel = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
    expected_order = [
        "parallel.validator_json.first",
        "parallel.validator_json.second",
        "parallel.validator_json.third",
    ]

    assert [result.plugin_id for result in sequential] == expected_order
    assert [result.plugin_id for result in parallel] == expected_order
    assert all(result.status == PluginStatus.SUCCESS for result in parallel)


def test_execute_stage_parallel_is_deterministic_across_repeated_runs(tmp_path: Path):
    """Repeated parallel executions should preserve identical result ordering."""
    _write_module(
        tmp_path / "parallel_plugins.py",
        "\n".join(
            [
                "import time",
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class SleepPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        sleep_ms = int(ctx.active_config.get('sleep_ms', 0))",
                "        if sleep_ms > 0:",
                "            time.sleep(sleep_ms / 1000.0)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "repeat.validator_json.first",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "config": {"sleep_ms": 35},
            },
            {
                "id": "repeat.validator_json.second",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 120,
                "config": {"sleep_ms": 5},
            },
            {
                "id": "repeat.validator_json.third",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:SleepPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 150,
                "config": {"sleep_ms": 20},
            },
        ],
    }
    _write_manifest(manifest, payload)

    expected_order = [
        "repeat.validator_json.first",
        "repeat.validator_json.second",
        "repeat.validator_json.third",
    ]
    observed_orders: list[list[str]] = []
    for _ in range(12):
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
        results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
        observed_orders.append([result.plugin_id for result in results])
        assert all(result.status == PluginStatus.SUCCESS for result in results)

    assert all(order == expected_order for order in observed_orders)


def test_execute_stage_parallel_respects_depends_on(tmp_path: Path):
    """Parallel wavefront execution must honor intra-phase dependency edges."""
    _write_module(
        tmp_path / "parallel_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class DependencyProbePlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        required = ctx.active_config.get('required', [])",
                "        for dep_id in required:",
                "            ctx.subscribe(dep_id, 'ready')",
                "        ctx.publish('ready', self.plugin_id)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "parallel.validator_json.base_a",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:DependencyProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "parallel.validator_json.base_b",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:DependencyProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 110,
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "parallel.validator_json.consumer",
                "kind": "validator_json",
                "entry": "parallel_plugins.py:DependencyProbePlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 188,
                "depends_on": ["parallel.validator_json.base_a", "parallel.validator_json.base_b"],
                "config": {
                    "required": [
                        "parallel.validator_json.base_a",
                        "parallel.validator_json.base_b",
                    ]
                },
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
                "consumes": [
                    {
                        "from_plugin": "parallel.validator_json.base_a",
                        "key": "ready",
                        "required": True,
                    },
                    {
                        "from_plugin": "parallel.validator_json.base_b",
                        "key": "ready",
                        "required": True,
                    },
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

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
    assert [result.plugin_id for result in results] == [
        "parallel.validator_json.base_a",
        "parallel.validator_json.base_b",
        "parallel.validator_json.consumer",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in results)


def test_execute_stage_serial_compatible_plugins_commit_via_pipeline_state(tmp_path: Path):
    """Compatible plugins should execute via snapshot/envelope path even without parallel mode."""
    _write_module(
        tmp_path / "envelope_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class ProducerPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('ready', {'value': 'ok'})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "",
                "class ConsumerPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        payload = ctx.subscribe('envelope.validator_json.producer', 'ready')",
                "        assert payload['value'] == 'ok'",
                "        ctx.publish('seen', {'source': payload['value']})",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "envelope.validator_json.producer",
                "kind": "validator_json",
                "entry": "envelope_plugins.py:ProducerPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "execution_mode": "subinterpreter",
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "envelope.validator_json.consumer",
                "kind": "validator_json",
                "entry": "envelope_plugins.py:ConsumerPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 120,
                "depends_on": ["envelope.validator_json.producer"],
                "execution_mode": "subinterpreter",
                "consumes": [{"from_plugin": "envelope.validator_json.producer", "key": "ready"}],
                "produces": [{"key": "seen", "scope": "pipeline_shared"}],
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

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert [result.plugin_id for result in results] == [
        "envelope.validator_json.producer",
        "envelope.validator_json.consumer",
    ]
    assert all(result.status == PluginStatus.SUCCESS for result in results)
    published = ctx.get_published_data()
    assert published["envelope.validator_json.producer"]["ready"] == {"value": "ok"}
    assert published["envelope.validator_json.consumer"]["seen"] == {"source": "ok"}


def test_execute_stage_parallel_compatible_plugin_crash_does_not_commit_partial_publish(tmp_path: Path):
    """Failed compatible worker must not leak local outbox content into committed state."""
    _write_module(
        tmp_path / "envelope_crash_plugins.py",
        "\n".join(
            [
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class CrashAfterPublishPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.publish('ready', {'value': 'leak'})",
                "        raise RuntimeError('boom')",
                "",
                "class ConsumerPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        ctx.subscribe('envelope.validator_json.crash', 'ready')",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "envelope.validator_json.crash",
                "kind": "validator_json",
                "entry": "envelope_crash_plugins.py:CrashAfterPublishPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 100,
                "execution_mode": "subinterpreter",
                "produces": [{"key": "ready", "scope": "pipeline_shared"}],
            },
            {
                "id": "envelope.validator_json.consumer",
                "kind": "validator_json",
                "entry": "envelope_crash_plugins.py:ConsumerPlugin",
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 120,
                "depends_on": ["envelope.validator_json.crash"],
                "execution_mode": "subinterpreter",
                "consumes": [{"from_plugin": "envelope.validator_json.crash", "key": "ready"}],
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

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)

    assert [result.plugin_id for result in results] == [
        "envelope.validator_json.crash",
        "envelope.validator_json.consumer",
    ]
    by_plugin = {result.plugin_id: result for result in results}
    assert by_plugin["envelope.validator_json.crash"].status == PluginStatus.FAILED
    assert by_plugin["envelope.validator_json.consumer"].status == PluginStatus.FAILED
    assert ctx.get_published_keys("envelope.validator_json.crash") == []

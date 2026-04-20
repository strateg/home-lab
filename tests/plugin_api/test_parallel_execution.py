#!/usr/bin/env python3
"""Focused parallel plugin execution tests."""

from __future__ import annotations

import sys
from pathlib import Path

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


def _context() -> PluginContext:
    return PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def test_parallel_execution_preserves_result_order_and_published_data(tmp_path: Path) -> None:
    _write_module(
        tmp_path / "parallel_api_plugins.py",
        "\n".join(
            [
                "import time",
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class PublisherPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        time.sleep(float(ctx.active_config.get('sleep_seconds', 0)))",
                "        ctx.publish('ready', self.plugin_id)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "parallel.api.first",
                    "kind": "validator_json",
                    "entry": "parallel_api_plugins.py:PublisherPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                    "config": {"sleep_seconds": 0.04},
                    "produces": [{"key": "ready", "scope": "pipeline_shared"}],
                },
                {
                    "id": "parallel.api.second",
                    "kind": "validator_json",
                    "entry": "parallel_api_plugins.py:PublisherPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 120,
                    "config": {"sleep_seconds": 0.0},
                    "produces": [{"key": "ready", "scope": "pipeline_shared"}],
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)

    assert [result.plugin_id for result in results] == ["parallel.api.first", "parallel.api.second"]
    assert all(result.status == PluginStatus.SUCCESS for result in results)
    assert ctx.get_published_data() == {
        "parallel.api.first": {"ready": "parallel.api.first"},
        "parallel.api.second": {"ready": "parallel.api.second"},
    }


def test_parallel_execution_reports_failure_and_timeout_without_blocking_stage(tmp_path: Path) -> None:
    _write_module(
        tmp_path / "parallel_api_plugins.py",
        "\n".join(
            [
                "import time",
                "from kernel import PluginResult, ValidatorJsonPlugin",
                "",
                "class FastPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
                "",
                "class FailingPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        raise RuntimeError('forced failure')",
                "",
                "class SlowPlugin(ValidatorJsonPlugin):",
                "    def execute(self, ctx, stage):",
                "        time.sleep(0.2)",
                "        return PluginResult.success(self.plugin_id, self.api_version)",
            ]
        ),
    )
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        {
            "schema_version": 1,
            "plugins": [
                {
                    "id": "parallel.api.fast",
                    "kind": "validator_json",
                    "entry": "parallel_api_plugins.py:FastPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 100,
                },
                {
                    "id": "parallel.api.failing",
                    "kind": "validator_json",
                    "entry": "parallel_api_plugins.py:FailingPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 120,
                },
                {
                    "id": "parallel.api.slow",
                    "kind": "validator_json",
                    "entry": "parallel_api_plugins.py:SlowPlugin",
                    "api_version": "1.x",
                    "stages": ["validate"],
                    "phase": "run",
                    "order": 140,
                    "timeout": 1,
                },
            ],
        },
    )

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    registry.specs["parallel.api.slow"].timeout = 0.01
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=True)
    statuses = {result.plugin_id: result.status for result in results}

    assert statuses == {
        "parallel.api.fast": PluginStatus.SUCCESS,
        "parallel.api.failing": PluginStatus.FAILED,
        "parallel.api.slow": PluginStatus.TIMEOUT,
    }
    failure_context = ctx.config.get("stage_failure_context")
    assert isinstance(failure_context, list)
    assert {row["plugin_id"] for row in failure_context} == {
        "parallel.api.failing",
        "parallel.api.slow",
    }

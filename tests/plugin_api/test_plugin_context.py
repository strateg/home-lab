#!/usr/bin/env python3
"""Focused PluginContext data exchange tests."""

from __future__ import annotations

import concurrent.futures
import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginDataExchangeError  # noqa: E402
from kernel.plugin_base import Phase, PluginExecutionScope, Stage  # noqa: E402


def _context() -> PluginContext:
    return PluginContext(topology_path="test", profile="test", model_lock={})


def test_publish_requires_active_execution_scope() -> None:
    ctx = _context()

    with pytest.raises(PluginDataExchangeError, match="execution scope is not active"):
        ctx.publish("data", {"value": 1})


def test_stage_local_data_is_blocked_across_stages() -> None:
    ctx = _context()
    producer_scope = PluginExecutionScope(
        plugin_id="test.producer",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        stage=Stage.COMPILE,
        config={},
        produced_key_scopes={"local": "stage_local", "shared": "pipeline_shared"},
    )
    producer_token = ctx._set_execution_scope(producer_scope)
    try:
        ctx.publish("local", {"compile_only": True})
        ctx.publish("shared", {"pipeline": True})
    finally:
        ctx._clear_execution_scope(producer_token)

    consumer_scope = PluginExecutionScope(
        plugin_id="test.consumer",
        allowed_dependencies=frozenset({"test.producer"}),
        phase=Phase.RUN,
        stage=Stage.VALIDATE,
        config={},
    )
    consumer_token = ctx._set_execution_scope(consumer_scope)
    try:
        with pytest.raises(PluginDataExchangeError, match="stage_local key"):
            ctx.subscribe("test.producer", "local")
        assert ctx.subscribe("test.producer", "shared") == {"pipeline": True}
    finally:
        ctx._clear_execution_scope(consumer_token)


def test_subscribe_reports_missing_producer_and_missing_key() -> None:
    ctx = _context()
    consumer_scope = PluginExecutionScope(
        plugin_id="test.consumer",
        allowed_dependencies=frozenset({"test.producer"}),
        phase=Phase.RUN,
        stage=Stage.VALIDATE,
        config={},
    )
    consumer_token = ctx._set_execution_scope(consumer_scope)
    try:
        with pytest.raises(PluginDataExchangeError, match="has not published any data"):
            ctx.subscribe("test.producer", "ready")
    finally:
        ctx._clear_execution_scope(consumer_token)

    producer_scope = PluginExecutionScope(
        plugin_id="test.producer",
        allowed_dependencies=frozenset(),
        phase=Phase.RUN,
        stage=Stage.VALIDATE,
        config={},
    )
    producer_token = ctx._set_execution_scope(producer_scope)
    try:
        ctx.publish("ready", {"ok": True})
    finally:
        ctx._clear_execution_scope(producer_token)

    consumer_token = ctx._set_execution_scope(consumer_scope)
    try:
        with pytest.raises(PluginDataExchangeError, match="has not published key 'missing'"):
            ctx.subscribe("test.producer", "missing")
        assert ctx.subscribe("test.producer", "ready") == {"ok": True}
    finally:
        ctx._clear_execution_scope(consumer_token)


def test_context_scopes_are_thread_local_for_concurrent_publish() -> None:
    ctx = _context()

    def publish_from_worker(index: int) -> None:
        scope = PluginExecutionScope(
            plugin_id=f"test.producer.{index}",
            allowed_dependencies=frozenset(),
            phase=Phase.RUN,
            stage=Stage.VALIDATE,
            config={},
        )
        token = ctx._set_execution_scope(scope)
        try:
            ctx.publish("value", index)
        finally:
            ctx._clear_execution_scope(token)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(publish_from_worker, range(32)))

    published = ctx.get_published_data()
    assert len(published) == 32
    for index in range(32):
        assert published[f"test.producer.{index}"] == {"value": index}

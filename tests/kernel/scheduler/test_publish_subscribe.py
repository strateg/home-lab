#!/usr/bin/env python3
"""Publish/subscribe data-bus behavior during plugin execution.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level.
"""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginDataExchangeError  # noqa: E402
from tests.helpers.plugin_execution import publish_for_test  # noqa: E402


def test_publish_subscribe_basic():
    """Test basic publish/subscribe functionality."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Set execution context (simulating registry behavior)
    publish_for_test(ctx, "plugin.producer", "key1", {"data": "value1"})
    publish_for_test(ctx, "plugin.producer", "key2", [1, 2, 3])

    # Set up consumer plugin with dependency
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})  # noqa: SLF001 - testing context subscribe

    # Subscribe to data
    data1 = ctx.subscribe("plugin.producer", "key1")
    assert data1 == {"data": "value1"}

    data2 = ctx.subscribe("plugin.producer", "key2")
    assert data2 == [1, 2, 3]

    # Get published keys
    keys = ctx.get_published_keys("plugin.producer")
    assert set(keys) == {"key1", "key2"}

    ctx._clear_execution_context()  # noqa: SLF001
    print("PASS: Basic publish/subscribe works")


def test_publish_subscribe_dependency_check():
    """Test that subscribe enforces dependency declaration."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Producer publishes data
    publish_for_test(ctx, "plugin.producer", "data", {"value": 42})

    # Consumer WITHOUT dependency should fail
    ctx._set_execution_context("plugin.consumer", set())  # noqa: SLF001 - testing dependency enforcement

    try:
        ctx.subscribe("plugin.producer", "data")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "not in declared dependency contract" in str(e)

    ctx._clear_execution_context()  # noqa: SLF001
    print("PASS: Subscribe dependency check works")


def test_publish_subscribe_missing_data():
    """Test subscribe error handling for missing data."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # Consumer with valid dependency but producer hasn't published
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})  # noqa: SLF001 - testing missing data handling

    try:
        ctx.subscribe("plugin.producer", "nonexistent")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "has not published any data" in str(e)

    ctx._clear_execution_context()  # noqa: SLF001

    # Producer publishes some data
    publish_for_test(ctx, "plugin.producer", "existing_key", "value")

    # Consumer tries to get missing key
    ctx._set_execution_context("plugin.consumer", {"plugin.producer"})  # noqa: SLF001 - testing missing key handling

    try:
        ctx.subscribe("plugin.producer", "nonexistent_key")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "has not published key" in str(e)

    ctx._clear_execution_context()  # noqa: SLF001
    print("PASS: Subscribe missing data error handling works")


def test_publish_without_context():
    """Test that publish fails without execution context."""
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
    )

    # No execution context set
    try:
        ctx.publish("key", "value")
        assert False, "Should have raised PluginDataExchangeError"
    except PluginDataExchangeError as e:
        assert "no current plugin context" in str(e)

    print("PASS: Publish without context error works")


if __name__ == "__main__":
    print("=" * 60)
    print("ADR 0063 Plugin Registry Tests")
    print("=" * 60)
    print()

    tests = [
        test_manifest_loading,
        test_registry_load,
        test_execution_order,
        test_stage_order_prefers_order_over_manifest_insertion,
        test_stage_order_uses_id_as_tiebreaker,
        test_stage_order_respects_depends_on_over_numeric_order,
        test_execution_order_filters_by_phase,
        test_plugin_instantiation,
        test_plugin_execution,
        test_plugin_detects_invalid_ref,
        test_plugin_result_statuses,
        test_plugin_result_to_dict,
        test_registry_stats,
        test_kernel_info,
        test_config_injection,
        test_execute_stage,
        test_execute_stage_fails_on_capability_mismatch,
        test_execute_stage_allows_when_capability_is_provided,
        test_execute_stage_fails_on_unsupported_model_version,
        test_execute_stage_accepts_compatible_model_version,
        test_execute_stage_fails_when_plugin_model_versions_incompatible,
        test_execute_stage_fails_when_plugin_model_versions_require_missing_context,
        test_execute_stage_allows_when_plugin_model_versions_match,
        test_execute_stage_runs_finalize_on_fail_fast,
        test_partial_stage_selection_runs_finalize_for_started_stages_only,
        test_execute_stage_skips_when_before_capability_preflight,
        test_execute_stage_skips_when_changed_input_scopes_do_not_intersect,
        test_execute_stage_allows_when_changed_input_scopes_unknown,
        test_execute_stage_parallel_keeps_deterministic_order,
        test_execute_stage_parallel_is_deterministic_across_repeated_runs,
        test_execute_stage_parallel_respects_depends_on,
        test_execute_stage_invalidates_stage_local_outputs,
        test_execute_stage_trace_records_execution_events,
        test_execute_plugin_warns_on_undeclared_publish,
        test_execute_plugin_warns_on_undeclared_subscribe,
        test_execute_plugin_errors_on_undeclared_publish_in_strict_mode,
        test_execute_plugin_errors_on_undeclared_subscribe_in_strict_mode,
        test_execute_stage_applies_contract_errors_mode,
        test_execute_plugin_fails_on_invalid_produced_schema_ref_payload,
        test_execute_plugin_fails_on_invalid_consumed_schema_ref_payload,
        test_execute_plugin_fails_on_missing_schema_ref,
        test_execute_plugin_fails_when_required_consume_payload_missing,
        test_execute_plugin_allows_when_consume_required_false_and_payload_missing,
        test_timeout_does_not_block_pipeline,
        test_runtime_config_takes_precedence,
        # ADR 0065 inter-plugin data exchange tests
        test_publish_subscribe_basic,
        test_publish_subscribe_dependency_check,
        test_publish_subscribe_missing_data,
        test_publish_without_context,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            import traceback

            print(f"FAIL: {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)

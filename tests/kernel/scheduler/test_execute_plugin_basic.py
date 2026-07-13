#!/usr/bin/env python3
"""execute_plugin basic behavior: success, failure diagnostics,
runtime-config injection/restore and timeout isolation.

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level; the legacy thread-path implementation
lives in kernel/scheduler/legacy_executor.py (D13 quarantine).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import (  # noqa: E402
    PluginContext,
    PluginRegistry,
    PluginResult,
    PluginStatus,
)
from kernel.plugin_base import Stage  # noqa: E402
from tests.helpers.plugin_execution import publish_for_test  # noqa: E402


def test_plugin_execution():
    """Test executing a plugin."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Create minimal context
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router", "firmware_policy": "allowed", "os_policy": "allowed"}},
        objects={"obj.test": {"object": "obj.test", "class_ref": "class.router"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ],
                "firmware": [],
                "os": [],
                "lxc": [],
            }
        },
    )
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "test-device",
                "class_ref": "class.router",
                "object_ref": "obj.test",
                "firmware_ref": None,
                "os_refs": [],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert isinstance(result, PluginResult)
    assert result.status == PluginStatus.SUCCESS
    assert result.plugin_id == "base.validator.references"
    assert result.duration_ms > 0
    print("PASS: Plugin execution works")


def test_plugin_detects_invalid_ref():
    """Test that plugin detects invalid references."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    # Create context with invalid class_ref
    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},  # Empty - class.router doesn't exist
        objects={},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.nonexistent",
                        "object_ref": "obj.nonexistent",
                    }
                ],
                "firmware": [],
                "os": [],
                "lxc": [],
            }
        },
    )

    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "test-device",
                "class_ref": "class.nonexistent",
                "object_ref": "obj.nonexistent",
                "firmware_ref": None,
                "os_refs": [],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert len(result.diagnostics) >= 1
    assert result.has_errors
    print("PASS: Plugin detects invalid references")


def test_config_injection():
    """Test runtime config is restored after plugin execution."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
        config={"runtime_flag": True},
    )

    registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE)
    assert ctx.config == {"runtime_flag": True}
    print("PASS: Runtime config restore works")


def test_timeout_does_not_block_pipeline():
    """Timeout should return promptly instead of waiting for plugin completion."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={"obj.test": {"object": "obj.test"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [{"instance": "test-device", "class_ref": "class.router", "object_ref": "obj.test"}]
            }
        },
    )
    publish_for_test(
        ctx,
        "base.compiler.instance_rows",
        "normalized_rows",
        [
            {
                "group": "devices",
                "instance": "test-device",
                "class_ref": "class.router",
                "object_ref": "obj.test",
                "firmware_ref": None,
                "os_refs": [],
            }
        ],
    )
    publish_for_test(ctx, "base.compiler.capability_contract_loader", "catalog_ids", [])

    plugin = registry.load_plugin("base.validator.references")
    original_execute = plugin.execute

    def slow_execute(ctx: PluginContext, stage: Stage) -> PluginResult:
        time.sleep(2.0)
        return original_execute(ctx, stage)

    plugin.execute = slow_execute  # type: ignore[assignment]
    try:
        start = time.perf_counter()
        result = registry.execute_plugin("base.validator.references", ctx, Stage.VALIDATE, timeout=0.1)
        elapsed = time.perf_counter() - start
    finally:
        plugin.execute = original_execute  # type: ignore[assignment]

    assert result.status == PluginStatus.TIMEOUT
    assert elapsed < 1.0
    print("PASS: Timeout returns promptly")


def test_runtime_config_takes_precedence():
    """Runtime ctx.config values should override plugin defaults."""
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")

    ctx = PluginContext(
        topology_path="test",
        profile="test",
        model_lock={},
        classes={"class.router": {"class": "class.router"}},
        objects={"obj.test": {"object": "obj.test"}},
        instance_bindings={
            "instance_bindings": {
                "devices": [
                    {
                        "instance": "test-device",
                        "class_ref": "class.router",
                        "object_ref": "obj.test",
                    }
                ]
            }
        },
        config={"strict_mode": True},
    )
    publish_for_test(ctx, "base.compiler.model_lock_loader", "lock_payload", {})
    publish_for_test(ctx, "base.compiler.model_lock_loader", "model_lock_loaded", False)
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", [])

    result = registry.execute_plugin("base.validator.model_lock", ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E3201" for d in result.diagnostics)
    assert ctx.config == {"strict_mode": True}
    print("PASS: Runtime config precedence works")

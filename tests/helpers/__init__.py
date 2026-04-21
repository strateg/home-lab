"""Test helpers for ADR 0097/0099 compliant plugin testing.

This module provides utilities for executing plugins in tests without
directly calling legacy internal methods like `_set_execution_context`.

Usage:
    from tests.helpers.plugin_execution import run_plugin_for_test

    result = run_plugin_for_test(plugin, ctx, Stage.VALIDATE)
"""

from tests.helpers.plugin_execution import (
    run_plugin_for_test,
    run_plugin_isolated,
)

__all__ = [
    "run_plugin_for_test",
    "run_plugin_isolated",
]

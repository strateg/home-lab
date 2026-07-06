"""Workload defaults redundancy compiler (ADR 0107 Phase 1).

Detects instance fields that duplicate values from host workload_defaults.
These fields can be removed since they will be inherited via @on directives.
"""

from __future__ import annotations

import re
from typing import Any

from kernel.plugin_base import (
    CompilerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)


class WorkloadDefaultsRedundancyCompiler(CompilerPlugin):
    """Warn on redundant instance fields that match workload_defaults.

    ADR 0107 Phase 1: Help identify instance fields that can be removed
    because they duplicate values from host workload_defaults.

    Example:
        Host workload_defaults: { network: { gateway: "10.0.30.1" } }
        Object defaults: { network: { gateway: "@on:host.network.gateway?" } }
        Instance: { network: { gateway: "10.0.30.1" } }  # REDUNDANT - can be removed
    """

    _PREPARED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_prepare"
    _PREPARED_ROWS_KEY = "prepared_rows"
    _HOST_INDEX_PLUGIN_ID = "base.compiler.instance_host_index"
    _HOST_INDEX_KEY = "host_workload_defaults_index"

    # Regex to match @on directives: @on:host.path.to.field[?][:default]
    _ON_DIRECTIVE_PATTERN = re.compile(r"^@on:(\w+)\.(.+?)(\?)?(?::(.*))?$")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Get prepared rows (before @on resolution)
        try:
            prepared_rows = ctx.subscribe(self._PREPARED_ROWS_PLUGIN_ID, self._PREPARED_ROWS_KEY)
        except PluginDataExchangeError:
            # Plugin not available, skip validation
            return self.make_result(diagnostics)

        if not isinstance(prepared_rows, list):
            return self.make_result(diagnostics)

        # Get host workload defaults index
        try:
            host_index = ctx.subscribe(self._HOST_INDEX_PLUGIN_ID, self._HOST_INDEX_KEY)
        except PluginDataExchangeError:
            return self.make_result(diagnostics)

        if not isinstance(host_index, dict):
            return self.make_result(diagnostics)

        # Process each prepared row
        for prepared_row in prepared_rows:
            if not isinstance(prepared_row, dict):
                continue

            instance_id = prepared_row.get("instance")
            object_ref = prepared_row.get("object_ref")
            row_data = prepared_row.get("row", {})
            row_path = prepared_row.get("row_path", f"instance:{instance_id}")

            if not isinstance(instance_id, str) or not isinstance(row_data, dict):
                continue

            # Get host_ref to find workload_defaults
            host_ref = row_data.get("host_ref")
            if not isinstance(host_ref, str) or host_ref not in host_index:
                continue

            host_defaults = host_index.get(host_ref, {})
            if not host_defaults:
                continue

            # Get object template defaults
            if not isinstance(object_ref, str):
                continue

            obj_payload = ctx.objects.get(object_ref)
            if not isinstance(obj_payload, dict):
                continue

            obj_defaults = obj_payload.get("defaults", {})
            if not isinstance(obj_defaults, dict):
                continue

            # Find redundant fields
            self._check_redundancy(
                instance_id=instance_id,
                row_path=row_path,
                instance_data=row_data,
                obj_defaults=obj_defaults,
                host_defaults=host_defaults,
                path_prefix="",
                stage=stage,
                diagnostics=diagnostics,
            )

        return self.make_result(diagnostics)

    def _check_redundancy(
        self,
        instance_id: str,
        row_path: str,
        instance_data: dict[str, Any],
        obj_defaults: dict[str, Any],
        host_defaults: dict[str, Any],
        path_prefix: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        """Recursively check for redundant fields."""
        for key, obj_value in obj_defaults.items():
            current_path = f"{path_prefix}.{key}" if path_prefix else key

            # Skip if instance doesn't have this field
            if key not in instance_data:
                continue

            instance_value = instance_data[key]

            if isinstance(obj_value, str):
                # Check if it's an @on directive
                match = self._ON_DIRECTIVE_PATTERN.match(obj_value)
                if match:
                    source, field_path, optional, default = match.groups()
                    if source == "host":
                        # Get value from host defaults
                        host_value = self._get_nested_value(host_defaults, field_path)

                        # Compare instance value with host default
                        if host_value is not None and instance_value == host_value:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="W0107",
                                    severity="warning",
                                    stage=stage,
                                    message=(
                                        f"Instance '{instance_id}' field '{current_path}' "
                                        f"duplicates workload_defaults value '{instance_value}'. "
                                        f"Consider removing - will be inherited via @on directive."
                                    ),
                                    path=f"{row_path}.{current_path}",
                                )
                            )

            elif isinstance(obj_value, dict) and isinstance(instance_value, dict):
                # Recurse into nested dicts
                nested_host_defaults = self._get_nested_value(host_defaults, key)
                if isinstance(nested_host_defaults, dict):
                    self._check_redundancy(
                        instance_id=instance_id,
                        row_path=row_path,
                        instance_data=instance_value,
                        obj_defaults=obj_value,
                        host_defaults=nested_host_defaults,
                        path_prefix=current_path,
                        stage=stage,
                        diagnostics=diagnostics,
                    )

    @staticmethod
    def _get_nested_value(data: dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot-separated path."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

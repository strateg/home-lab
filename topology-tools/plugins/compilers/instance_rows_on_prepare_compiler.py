"""Instance rows @on directive resolver (ADR 0107 D12).

Resolves @on:host.X and @on:root.X markers in prepared instance rows
using host_workload_defaults_index built by instance_host_index_compiler.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from host_chain_utils import (
    extract_host_ref,
    get_host_at_level,
    get_root_host,
)
from kernel.plugin_base import (
    CompilerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)

# Pattern for @on directive: @on:<source>.<path>[?][:<default>]
_ON_DIRECTIVE_RE = re.compile(
    r"^@on:(?P<source>host|root|host\[\d+\])\.(?P<path>[a-zA-Z0-9_.]+)"
    r"(?P<optional>\?)?(?::(?P<default>.+))?$"
)


class InstanceRowsOnPrepareCompiler(CompilerPlugin):
    """Resolve @on directives in prepared instance rows.

    This run-phase compiler processes prepared_rows and resolves
    @on:host.X, @on:root.X, and @on:host[N].X markers by looking up
    values from host_workload_defaults_index.

    The resolved rows are published as on_prepared_rows for consumption
    by instance_rows_validate.
    """

    _PREPARED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_prepare"
    _HOST_INDEX_PLUGIN_ID = "base.compiler.instance_host_index"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        # Subscribe to prepared_rows
        prepared_rows = self._get_prepared_rows(ctx, stage, diagnostics)
        if prepared_rows is None:
            return self.make_result(diagnostics, output_data={"on_prepared_rows": []})

        # Subscribe to host_workload_defaults_index
        host_index = self._get_host_index(ctx, stage, diagnostics)

        # Build instance lookup for host chain traversal
        instance_lookup = self._build_instance_lookup_from_rows(prepared_rows)

        # Process each row, resolving @on markers
        on_prepared_rows: list[dict[str, Any]] = []

        for prepared_row in prepared_rows:
            if not isinstance(prepared_row, dict):
                continue

            resolved_row = self._resolve_on_markers_in_row(
                prepared_row=prepared_row,
                host_index=host_index,
                instance_lookup=instance_lookup,
                ctx=ctx,
                stage=stage,
                diagnostics=diagnostics,
            )

            on_prepared_rows.append(resolved_row)

        ctx.publish("on_prepared_rows", on_prepared_rows)
        return self.make_result(
            diagnostics,
            output_data={"on_prepared_rows": on_prepared_rows},
        )

    def _get_prepared_rows(
        self,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> list[dict[str, Any]] | None:
        """Subscribe to prepared_rows from instance_rows_prepare."""
        try:
            subscribed = ctx.subscribe(self._PREPARED_ROWS_PLUGIN_ID, "prepared_rows")
            if isinstance(subscribed, list):
                return [row for row in subscribed if isinstance(row, dict)]
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6800",
                    severity="error",
                    stage=stage,
                    message=f"@on resolver requires prepared_rows: {exc}",
                    path="pipeline:instance_rows_on_prepare",
                )
            )
        return None

    def _get_host_index(
        self,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, dict[str, Any]]:
        """Subscribe to host_workload_defaults_index."""
        try:
            subscribed = ctx.subscribe(
                self._HOST_INDEX_PLUGIN_ID,
                "host_workload_defaults_index",
            )
            if isinstance(subscribed, dict):
                return subscribed
        except PluginDataExchangeError:
            # Index not available - @on markers won't resolve but that's OK
            # for backward compatibility
            pass
        return {}

    def _build_instance_lookup_from_rows(
        self,
        prepared_rows: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Build instance_id -> row lookup from prepared rows."""
        lookup: dict[str, dict[str, Any]] = {}

        for prepared_row in prepared_rows:
            if not isinstance(prepared_row, dict):
                continue

            instance_id = prepared_row.get("instance")
            row_data = prepared_row.get("row")

            if isinstance(instance_id, str) and isinstance(row_data, dict):
                lookup[instance_id] = row_data

        return lookup

    def _resolve_on_markers_in_row(
        self,
        prepared_row: dict[str, Any],
        host_index: dict[str, dict[str, Any]],
        instance_lookup: dict[str, dict[str, Any]],
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any]:
        """Resolve @on markers in a prepared row.

        Processes both object template defaults and instance row data,
        resolving any @on directives found. Object defaults are resolved
        first (lower priority), then instance data (higher priority),
        and results are deep merged.
        """
        resolved_row = copy.deepcopy(prepared_row)
        instance_id = prepared_row.get("instance")
        row_path = prepared_row.get("row_path", f"instance:{instance_id}")
        row_data = resolved_row.get("row")

        if not isinstance(instance_id, str) or not isinstance(row_data, dict):
            return resolved_row

        # Step 1: Resolve @on in object template defaults (lower priority base)
        object_ref = prepared_row.get("object_ref")
        resolved_obj_defaults: dict[str, Any] = {}

        if isinstance(object_ref, str) and object_ref:
            obj_payload = ctx.objects.get(object_ref)
            if isinstance(obj_payload, dict):
                obj_defaults = obj_payload.get("defaults", {})
                if isinstance(obj_defaults, dict) and obj_defaults:
                    resolved_obj_defaults = self._resolve_values_recursive(
                        data=obj_defaults,
                        instance_id=instance_id,
                        host_index=host_index,
                        instance_lookup=instance_lookup,
                        path="",
                        row_path=f"{row_path}[object:{object_ref}]",
                        stage=stage,
                        diagnostics=diagnostics,
                    )

        # Step 2: Resolve @on in instance row data (higher priority)
        resolved_instance_data = self._resolve_values_recursive(
            data=row_data,
            instance_id=instance_id,
            host_index=host_index,
            instance_lookup=instance_lookup,
            path="",
            row_path=row_path,
            stage=stage,
            diagnostics=diagnostics,
        )

        # Step 3: Strip None values from object defaults (unresolved optional @on paths)
        # These should not be merged into the final result
        stripped_obj_defaults = self._strip_none_values(resolved_obj_defaults)

        # Step 4: Deep merge (instance data wins over object defaults)
        final_data = self._deep_merge(stripped_obj_defaults, resolved_instance_data)

        resolved_row["row"] = final_data
        return resolved_row

    @staticmethod
    def _strip_none_values(data: dict[str, Any]) -> dict[str, Any]:
        """Recursively remove keys with None values from a dict.

        This ensures that unresolved optional @on paths (which return None)
        are not merged into the final result, preventing validator errors
        for fields like network.bridge_ref that may not apply to all hosts.
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, dict):
                stripped = InstanceRowsOnPrepareCompiler._strip_none_values(value)
                if stripped:  # Only include non-empty dicts
                    result[key] = stripped
            else:
                result[key] = value
        return result

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dicts, override wins for conflicts."""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = InstanceRowsOnPrepareCompiler._deep_merge(
                    result[key], value
                )
            else:
                result[key] = copy.deepcopy(value)
        return result

    def _resolve_values_recursive(
        self,
        data: Any,
        instance_id: str,
        host_index: dict[str, dict[str, Any]],
        instance_lookup: dict[str, dict[str, Any]],
        path: str,
        row_path: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> Any:
        """Recursively resolve @on markers in data structure."""
        if isinstance(data, dict):
            return {
                k: self._resolve_values_recursive(
                    data=v,
                    instance_id=instance_id,
                    host_index=host_index,
                    instance_lookup=instance_lookup,
                    path=f"{path}.{k}" if path else k,
                    row_path=row_path,
                    stage=stage,
                    diagnostics=diagnostics,
                )
                for k, v in data.items()
            }

        if isinstance(data, list):
            return [
                self._resolve_values_recursive(
                    data=item,
                    instance_id=instance_id,
                    host_index=host_index,
                    instance_lookup=instance_lookup,
                    path=f"{path}[{idx}]",
                    row_path=row_path,
                    stage=stage,
                    diagnostics=diagnostics,
                )
                for idx, item in enumerate(data)
            ]

        if not isinstance(data, str):
            return data

        # Check if it's an @on directive
        match = _ON_DIRECTIVE_RE.fullmatch(data)
        if not match:
            return data

        source = match.group("source")
        field_path = match.group("path")
        optional = bool(match.group("optional"))
        default_value = match.group("default")

        # Resolve the host to lookup from
        target_host_id = self._resolve_source_host(
            instance_id=instance_id,
            source=source,
            instance_lookup=instance_lookup,
        )

        if not target_host_id:
            if optional:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W6814",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Optional @on source '{source}' could not be resolved "
                            f"for instance '{instance_id}' at '{path}'"
                        ),
                        path=f"{row_path}.{path}",
                    )
                )
                return default_value if default_value is not None else None

            diagnostics.append(
                self.emit_diagnostic(
                    code="E6811",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Cannot resolve @on source '{source}' for instance "
                        f"'{instance_id}' at '{path}': no valid host_ref"
                    ),
                    path=f"{row_path}.{path}",
                )
            )
            return data

        # Lookup from host_workload_defaults_index
        target_defaults = host_index.get(target_host_id, {})
        resolved_value = self._get_nested_value(target_defaults, field_path)

        if resolved_value is None:
            if optional:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W6814",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Optional path '{field_path}' not found in "
                            f"workload_defaults of host '{target_host_id}'"
                        ),
                        path=f"{row_path}.{path}",
                    )
                )
                return default_value if default_value is not None else None

            diagnostics.append(
                self.emit_diagnostic(
                    code="E6810",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Path '{field_path}' not found in workload_defaults of "
                        f"host '{target_host_id}' for @on directive at '{path}'"
                    ),
                    path=f"{row_path}.{path}",
                )
            )
            return data

        return resolved_value

    def _resolve_source_host(
        self,
        instance_id: str,
        source: str,
        instance_lookup: dict[str, dict[str, Any]],
    ) -> str | None:
        """Resolve @on source directive to target host instance ID."""
        instance_data = instance_lookup.get(instance_id)
        if not isinstance(instance_data, dict):
            return None

        if source == "host":
            return extract_host_ref(instance_data)

        if source == "root":
            return get_root_host(instance_id, instance_lookup)

        # host[N] syntax
        bracket_match = re.match(r"host\[(\d+)\]", source)
        if bracket_match:
            level = int(bracket_match.group(1))
            return get_host_at_level(instance_id, instance_lookup, level)

        return None

    def _get_nested_value(
        self,
        data: dict[str, Any],
        path: str,
    ) -> Any:
        """Get nested value from dict using dotted path."""
        current = data
        for key in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

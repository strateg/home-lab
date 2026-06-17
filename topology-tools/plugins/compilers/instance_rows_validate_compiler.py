"""Validates prepared instance rows before final publish (ADR 0097 Wave 3B).

Updated for ADR 0107: Consumes on_prepared_rows (from @on resolver) with
fallback to prepared_rows for backward compatibility.
"""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDataExchangeError, PluginResult, Stage
from plugins.compilers.instance_rows_compiler import InstanceRowsCompiler


class InstanceRowsValidateCompiler(InstanceRowsCompiler):
    """Validate prepared instance rows into normalized stage-local payloads."""

    _ON_PREPARED_ROWS_PLUGIN_ID = "base.compiler.instance_rows_on_prepare"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"validated_rows": []})

        # ADR 0107: Try on_prepared_rows first, then fallback to prepared_rows
        prepared_rows = self._get_source_rows(ctx)

        rows = self._build_validated_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
            prepared_rows=prepared_rows,
        )
        ctx.publish("validated_rows", rows)
        return self.make_result(diagnostics, output_data={"validated_rows": rows})

    def _get_source_rows(self, ctx: PluginContext) -> list | None:
        """Get source rows with ADR 0107 fallback chain.

        Tries on_prepared_rows first (@on resolved), then prepared_rows.
        """
        # Try on_prepared_rows first (ADR 0107)
        if ctx.is_snapshot_backed:
            try:
                on_prepared = ctx.subscribe(self._ON_PREPARED_ROWS_PLUGIN_ID, "on_prepared_rows")
                if isinstance(on_prepared, list) and on_prepared:
                    return [row for row in on_prepared if isinstance(row, dict)]
            except (PluginDataExchangeError, KeyError):
                pass

            # Fallback to prepared_rows
            subscribed = ctx.subscribe(self._PREPARED_ROWS_PLUGIN_ID, "prepared_rows")
            if isinstance(subscribed, list):
                return [row for row in subscribed if isinstance(row, dict)]
        else:
            # Non-snapshot mode: try both with exception handling
            try:
                on_prepared = ctx.subscribe(self._ON_PREPARED_ROWS_PLUGIN_ID, "on_prepared_rows")
                if isinstance(on_prepared, list) and on_prepared:
                    return [row for row in on_prepared if isinstance(row, dict)]
            except PluginDataExchangeError:
                pass

            try:
                subscribed = ctx.subscribe(self._PREPARED_ROWS_PLUGIN_ID, "prepared_rows")
                if isinstance(subscribed, list):
                    return [row for row in subscribed if isinstance(row, dict)]
            except PluginDataExchangeError:
                pass

        return None

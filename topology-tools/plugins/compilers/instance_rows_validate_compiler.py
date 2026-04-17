"""Validates prepared instance rows before final publish (ADR 0097 Wave 3B)."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDataExchangeError, PluginResult, Stage
from plugins.compilers.instance_rows_compiler import InstanceRowsCompiler


class InstanceRowsValidateCompiler(InstanceRowsCompiler):
    """Validate prepared instance rows into normalized stage-local payloads."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"validated_rows": []})

        prepared_rows = None
        if ctx.is_snapshot_backed:
            subscribed_prepared_rows = ctx.subscribe(self._PREPARED_ROWS_PLUGIN_ID, "prepared_rows")
            if isinstance(subscribed_prepared_rows, list):
                prepared_rows = [row for row in subscribed_prepared_rows if isinstance(row, dict)]
        else:
            try:
                subscribed_prepared_rows = ctx.subscribe(self._PREPARED_ROWS_PLUGIN_ID, "prepared_rows")
                if isinstance(subscribed_prepared_rows, list):
                    prepared_rows = [row for row in subscribed_prepared_rows if isinstance(row, dict)]
            except PluginDataExchangeError:
                prepared_rows = None

        rows = self._build_validated_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
            prepared_rows=prepared_rows,
        )
        ctx.publish("validated_rows", rows)
        return self.make_result(diagnostics, output_data={"validated_rows": rows})

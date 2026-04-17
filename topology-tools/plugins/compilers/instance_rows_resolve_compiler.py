"""Resolves raw instance rows before shape normalization (ADR 0097 Wave 3B)."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDataExchangeError, PluginResult, Stage
from plugins.compilers.instance_rows_compiler import InstanceRowsCompiler


class InstanceRowsResolveCompiler(InstanceRowsCompiler):
    """Resolve semantic keys and sidecar secrets into stage-local rows."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"resolved_rows": []})

        secret_resolved_rows = None
        if ctx.is_snapshot_backed:
            subscribed_secret_resolved_rows = ctx.subscribe(
                self._SECRET_RESOLVED_ROWS_PLUGIN_ID, "secret_resolved_rows"
            )
            if isinstance(subscribed_secret_resolved_rows, list):
                secret_resolved_rows = [row for row in subscribed_secret_resolved_rows if isinstance(row, dict)]
        else:
            try:
                subscribed_secret_resolved_rows = ctx.subscribe(
                    self._SECRET_RESOLVED_ROWS_PLUGIN_ID, "secret_resolved_rows"
                )
                if isinstance(subscribed_secret_resolved_rows, list):
                    secret_resolved_rows = [row for row in subscribed_secret_resolved_rows if isinstance(row, dict)]
            except PluginDataExchangeError:
                secret_resolved_rows = None

        rows = self._build_resolved_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
            secret_resolved_rows=secret_resolved_rows,
        )
        ctx.publish("resolved_rows", rows)
        return self.make_result(diagnostics, output_data={"resolved_rows": rows})

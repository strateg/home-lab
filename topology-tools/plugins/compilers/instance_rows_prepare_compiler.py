"""Prepares normalized instance rows before final commit (ADR 0097 Wave 3B)."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDataExchangeError, PluginResult, Stage
from plugins.compilers.instance_rows_compiler import InstanceRowsCompiler


class InstanceRowsPrepareCompiler(InstanceRowsCompiler):
    """Build prepared instance rows as a stage-local intermediate."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"prepared_rows": []})

        resolved_rows = None
        fallback_triggered = False
        fallback_reason = ""
        if ctx.is_snapshot_backed:
            subscribed_resolved_rows = ctx.subscribe(self._RESOLVED_ROWS_PLUGIN_ID, "resolved_rows")
            if isinstance(subscribed_resolved_rows, list):
                resolved_rows = [row for row in subscribed_resolved_rows if isinstance(row, dict)]
            else:
                fallback_triggered = True
                fallback_reason = "wrong type (expected list)"
        else:
            try:
                subscribed_resolved_rows = ctx.subscribe(self._RESOLVED_ROWS_PLUGIN_ID, "resolved_rows")
                if isinstance(subscribed_resolved_rows, list):
                    resolved_rows = [row for row in subscribed_resolved_rows if isinstance(row, dict)]
                else:
                    fallback_triggered = True
                    fallback_reason = "wrong type (expected list)"
            except PluginDataExchangeError:
                resolved_rows = None
                fallback_triggered = True
                fallback_reason = "publication unavailable"

        if fallback_triggered:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I7951",
                    severity="info",
                    stage=stage,
                    message=f"resolved_rows {fallback_reason}; using legacy fallback path.",
                    path="pipeline:compile",
                )
            )

        rows = self._build_prepared_rows(
            ctx=ctx,
            stage=stage,
            diagnostics=diagnostics,
            resolved_rows=resolved_rows,
        )
        ctx.publish("prepared_rows", rows)
        return self.make_result(diagnostics, output_data={"prepared_rows": rows})

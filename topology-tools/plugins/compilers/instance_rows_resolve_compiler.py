"""Resolves raw instance rows before shape normalization (ADR 0097 Wave 3B)."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginResult, Stage
from plugins.compilers.instance_rows_compiler import InstanceRowsCompiler


class InstanceRowsResolveCompiler(InstanceRowsCompiler):
    """Resolve semantic keys and sidecar secrets into stage-local rows."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"resolved_rows": []})

        rows = self._build_resolved_rows(ctx=ctx, stage=stage, diagnostics=diagnostics)
        ctx.publish("resolved_rows", rows)
        return self.make_result(diagnostics, output_data={"resolved_rows": rows})

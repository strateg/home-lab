"""Resolves instance-row semantic keys and secrets before duplicate/reference checks."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginResult, Stage
from plugins.compilers.instance_rows_compiler import InstanceRowsCompiler


class InstanceRowsSecretResolveCompiler(InstanceRowsCompiler):
    """Resolve row-level semantic keys, annotations, and side-car secrets."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"secret_resolved_rows": []})

        rows = self._build_secret_resolved_rows(ctx=ctx, stage=stage, diagnostics=diagnostics)
        ctx.publish("secret_resolved_rows", rows)
        return self.make_result(diagnostics, output_data={"secret_resolved_rows": rows})

"""Generator plugin that emits effective topology JSON (ADR 0069 WS4)."""

from __future__ import annotations

import json
from pathlib import Path

from kernel.plugin_base import (
    GeneratorPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)


class EffectiveJsonGenerator(GeneratorPlugin):
    """Emit canonical effective JSON artifact from compiled_json."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("generation_owner_effective_json")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics)

        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot emit effective JSON.",
                    path="generator:effective_json",
                )
            )
            return self.make_result(diagnostics)

        if isinstance(ctx.compiled_file, str) and ctx.compiled_file:
            output_path = Path(ctx.compiled_file)
        else:
            output_dir = Path(ctx.output_dir) if isinstance(ctx.output_dir, str) and ctx.output_dir else Path.cwd()
            output_path = output_dir / "effective-topology.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, default=str),
            encoding="utf-8",
        )
        try:
            ctx.publish("generated_files", [str(output_path)])
            ctx.publish("effective_json_path", str(output_path))
        except PluginDataExchangeError:
            pass

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "effective_json": str(output_path),
                "generated_files": [str(output_path)],
            },
        )

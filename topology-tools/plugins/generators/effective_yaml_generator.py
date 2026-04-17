"""Generator plugin that emits effective topology YAML (ADR 0069 WS4 seed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import GeneratorPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class EffectiveYamlGenerator(GeneratorPlugin):
    """Emit YAML artifact from compiled_json model."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        payload = ctx.compiled_json
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3001",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot emit effective YAML.",
                    path="generator:effective_yaml",
                )
            )
            return self.make_result(diagnostics)

        output_dir = Path(ctx.output_dir) if isinstance(ctx.output_dir, str) and ctx.output_dir else Path.cwd()
        filename = ctx.config.get("output_filename", "effective-topology.yaml")
        if not isinstance(filename, str) or not filename.strip():
            filename = "effective-topology.yaml"

        output_path = output_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
        output_path.write_text(text, encoding="utf-8")

        diagnostics.append(
            self.emit_diagnostic(
                code="I9001",
                severity="info",
                stage=stage,
                message=f"Generated effective YAML artifact: {output_path}",
                path="generator:effective_yaml",
                confidence=1.0,
            )
        )
        ctx.publish("generated_files", [str(output_path)])
        ctx.publish("effective_yaml_path", str(output_path))
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "effective_yaml": str(output_path),
                "generated_files": [str(output_path)],
            },
        )

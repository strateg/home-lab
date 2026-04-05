"""Model lock loader compiler plugin (ADR 0069 WS2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage
from yaml_loader import load_yaml_file

REPO_ROOT = Path(__file__).resolve().parents[4]


class ModelLockLoaderCompiler(CompilerPlugin):
    """Load and parse model.lock data for plugin-first pipeline."""

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT).as_posix())
        except ValueError:
            return str(path)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("compilation_owner_model_lock_data")
        if owner is not None and owner != "plugin":
            current_payload = ctx.model_lock if isinstance(ctx.model_lock, dict) else {}
            return self.make_result(
                diagnostics,
                output_data={
                    "lock_payload": current_payload,
                    "model_lock_loaded": bool(current_payload),
                },
            )

        lock_path_raw = ctx.config.get("model_lock_path")
        if not isinstance(lock_path_raw, str) or not lock_path_raw:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Missing model_lock_path in plugin context config.",
                    path="pipeline:model_lock_loader",
                )
            )
            ctx.model_lock = {}
            return self.make_result(
                diagnostics,
                output_data={"lock_payload": {}, "model_lock_loaded": False},
            )

        lock_path = Path(lock_path_raw)
        if not lock_path.exists() or not lock_path.is_file():
            ctx.model_lock = {}
            ctx.publish("lock_payload", {})
            ctx.publish("model_lock_loaded", False)
            return self.make_result(
                diagnostics,
                output_data={"lock_payload": {}, "model_lock_loaded": False},
            )

        try:
            payload = load_yaml_file(lock_path) or {}
        except (OSError, yaml.YAMLError) as exc:
            diagnostics.append(
                PluginDiagnostic(
                    code="E2401",
                    severity="error",
                    stage="load",
                    message=f"YAML parse error: {exc}",
                    path=self._rel(lock_path),
                    plugin_id=self.plugin_id,
                )
            )
            ctx.model_lock = {}
            ctx.publish("lock_payload", {})
            ctx.publish("model_lock_loaded", False)
            return self.make_result(
                diagnostics,
                output_data={"lock_payload": {}, "model_lock_loaded": False},
            )

        if not isinstance(payload, dict):
            diagnostics.append(
                PluginDiagnostic(
                    code="E1004",
                    severity="error",
                    stage="load",
                    message="Expected mapping/object at YAML root.",
                    path=self._rel(lock_path),
                    plugin_id=self.plugin_id,
                )
            )
            ctx.model_lock = {}
            ctx.publish("lock_payload", {})
            ctx.publish("model_lock_loaded", False)
            return self.make_result(
                diagnostics,
                output_data={"lock_payload": {}, "model_lock_loaded": False},
            )

        ctx.model_lock = payload
        ctx.publish("lock_payload", payload)
        ctx.publish("model_lock_loaded", True)
        return self.make_result(
            diagnostics,
            output_data={"lock_payload": payload, "model_lock_loaded": True},
        )

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

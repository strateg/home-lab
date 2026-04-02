"""Foundation layout validator for v5 class/object module roots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorYamlPlugin


class FoundationLayoutValidator(ValidatorYamlPlugin):
    """Validate framework module-root declarations and repository layout basics."""

    _ROOT_KEYS = ("class_modules_root", "object_modules_root")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        raw = ctx.raw_yaml if isinstance(ctx.raw_yaml, dict) else {}
        framework = raw.get("framework")
        if not isinstance(framework, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7811",
                    severity="error",
                    stage=stage,
                    message="framework section must be an object.",
                    path="topology:framework",
                )
            )
            return self.make_result(diagnostics)

        repo_root = self._resolve_repo_root(ctx.config.get("repo_root"))
        plugins_manifest_count = 0

        for key in self._ROOT_KEYS:
            value = framework.get(key)
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7811",
                        severity="error",
                        stage=stage,
                        message=f"framework.{key} must be a non-empty string path.",
                        path=f"topology:framework.{key}",
                    )
                )
                continue

            root = self._resolve_path(value=value, repo_root=repo_root)
            if not root.exists() or not root.is_dir():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7812",
                        severity="error",
                        stage=stage,
                        message=f"framework.{key} path does not exist or is not a directory: '{value}'.",
                        path=f"topology:framework.{key}",
                    )
                )
                continue

            yaml_files = [path for path in root.rglob("*.yaml") if path.is_file()]
            if not yaml_files:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7813",
                        severity="error",
                        stage=stage,
                        message=f"framework.{key} directory '{value}' has no YAML module files.",
                        path=f"topology:framework.{key}",
                    )
                )

            plugins_manifest_count += sum(1 for path in root.rglob("plugins.yaml") if path.is_file())

        if plugins_manifest_count == 0:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7814",
                    severity="warning",
                    stage=stage,
                    message="Framework module roots contain no plugins.yaml manifests.",
                    path="topology:framework",
                )
            )

        return self.make_result(diagnostics)

    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    @staticmethod
    def _resolve_repo_root(value: Any) -> Path:
        if isinstance(value, str) and value.strip():
            return Path(value).resolve()
        return Path.cwd().resolve()

    @staticmethod
    def _resolve_path(*, value: str, repo_root: Path) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = repo_root / candidate
        return candidate.resolve()

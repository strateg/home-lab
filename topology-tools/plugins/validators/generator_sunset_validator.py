"""Strict sunset enforcement validator for ADR0093 target generator families."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginKind,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)
from yaml_loader import load_yaml_file

_SUPPORTED_MODES = {"legacy", "migrating", "migrated", "rollback"}


class GeneratorSunsetValidator(ValidatorJsonPlugin):
    """Fail validation when any scheduled ADR0093 target remains in legacy mode."""

    @staticmethod
    def _resolve_repo_root(ctx: PluginContext) -> Path:
        raw = ctx.config.get("repo_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).resolve()
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def _resolve_framework_root(ctx: PluginContext) -> Path | None:
        class_modules_root_raw = ctx.config.get("class_modules_root")
        if isinstance(class_modules_root_raw, str) and class_modules_root_raw.strip():
            class_modules_root = Path(class_modules_root_raw.strip()).resolve()
            return class_modules_root.parent.parent
        object_modules_root_raw = ctx.config.get("object_modules_root")
        if isinstance(object_modules_root_raw, str) and object_modules_root_raw.strip():
            object_modules_root = Path(object_modules_root_raw.strip()).resolve()
            return object_modules_root.parent.parent
        return None

    def _resolve_policy_path(self, *, ctx: PluginContext, value: str) -> Path:
        candidate = Path(value.strip())
        if candidate.is_absolute():
            return candidate.resolve()
        repo_path = (self._resolve_repo_root(ctx) / candidate).resolve()
        if repo_path.exists():
            return repo_path
        framework_root = self._resolve_framework_root(ctx)
        if framework_root is not None:
            framework_path = (framework_root / candidate).resolve()
            if framework_path.exists():
                return framework_path
        return repo_path

    def _load_policy_schedule(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
    ) -> tuple[dict[str, Any], list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []
        policy_path_raw = ctx.config.get("sunset_policy_path")
        if not isinstance(policy_path_raw, str) or not policy_path_raw.strip():
            return {}, diagnostics

        policy_path = self._resolve_policy_path(ctx=ctx, value=policy_path_raw)
        if not policy_path.exists() or not policy_path.is_file():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9396",
                    severity="error",
                    stage=stage,
                    message=f"sunset policy file does not exist: {policy_path}",
                    path=f"pipeline:config.sunset_policy_path={policy_path}",
                )
            )
            return {}, diagnostics
        try:
            payload = load_yaml_file(policy_path)
        except (OSError, yaml.YAMLError) as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9396",
                    severity="error",
                    stage=stage,
                    message=f"failed to load sunset policy file '{policy_path}': {exc}",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        if not isinstance(payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9396",
                    severity="error",
                    stage=stage,
                    message=f"sunset policy '{policy_path}' must be a YAML object.",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        schema_version = payload.get("schema_version")
        if schema_version != 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9396",
                    severity="error",
                    stage=stage,
                    message=f"sunset policy '{policy_path}' schema_version must be 1.",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        raw_schedule = payload.get("sunset_schedule")
        if not isinstance(raw_schedule, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9396",
                    severity="error",
                    stage=stage,
                    message=f"sunset policy '{policy_path}' must define object key 'sunset_schedule'.",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        return dict(raw_schedule), diagnostics

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        registry = ctx.config.get("plugin_registry")
        specs = getattr(registry, "specs", None)
        if not isinstance(specs, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9396",
                    severity="warning",
                    stage=stage,
                    message="plugin_registry specs are unavailable; generator sunset enforcement skipped.",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        config_today = self._parse_date(ctx.config.get("sunset_today"))
        today = config_today or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        schedule, policy_diags = self._load_policy_schedule(ctx=ctx, stage=stage)
        diagnostics.extend(policy_diags)
        if any(diag.severity == "error" for diag in policy_diags):
            return self.make_result(diagnostics=diagnostics)

        raw_schedule_override = ctx.config.get("sunset_schedule")
        if isinstance(raw_schedule_override, dict):
            schedule.update(raw_schedule_override)

        summary = {
            "scheduled_targets": 0,
            "legacy_targets": 0,
            "warnings": 0,
            "errors": 0,
            "today": today.date().isoformat(),
        }

        for plugin_id in sorted(schedule.keys()):
            item = schedule.get(plugin_id)
            if not isinstance(item, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9396",
                        severity="warning",
                        stage=stage,
                        message=f"sunset_schedule entry for '{plugin_id}' must be an object; skipping.",
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["warnings"] += 1
                continue
            spec = specs.get(plugin_id)
            if spec is None or spec.kind != PluginKind.GENERATOR:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9396",
                        severity="warning",
                        stage=stage,
                        message=f"sunset_schedule target '{plugin_id}' is not a known generator plugin; skipping.",
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["warnings"] += 1
                continue

            sunset_date = self._parse_date(item.get("compatibility_sunset"))
            hard_error_date = self._parse_date(item.get("hard_error_date"))
            if sunset_date is None or hard_error_date is None or hard_error_date < sunset_date:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9396",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"sunset_schedule '{plugin_id}' has invalid dates; "
                            "expected compatibility_sunset <= hard_error_date (YYYY-MM-DD)."
                        ),
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["warnings"] += 1
                continue

            summary["scheduled_targets"] += 1
            mode = str(getattr(spec, "migration_mode", "legacy")).strip().lower() or "legacy"
            if mode not in _SUPPORTED_MODES:
                mode = "legacy"
            if mode != "legacy":
                continue

            summary["legacy_targets"] += 1
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9399",
                    severity="error",
                    stage=stage,
                    message=(
                        f"generator '{plugin_id}' remains in legacy mode; ADR0093 compatibility mode is closed "
                        f"(sunset={sunset_date.date().isoformat()}, hard_error_date={hard_error_date.date().isoformat()})."
                    ),
                    path=f"plugin:{plugin_id}",
                )
            )
            summary["errors"] += 1

        diagnostics.append(
            self.emit_diagnostic(
                code="I9399",
                severity="info",
                stage=stage,
                message=(
                    "generator sunset summary: "
                    f"scheduled={summary['scheduled_targets']} legacy={summary['legacy_targets']} "
                    f"warnings={summary['warnings']} errors={summary['errors']}"
                ),
                path="pipeline:validate",
            )
        )

        try:
            ctx.publish("generator_sunset_summary", summary)
        except PluginDataExchangeError:
            pass
        return self.make_result(diagnostics=diagnostics, output_data={"generator_sunset_summary": summary})

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

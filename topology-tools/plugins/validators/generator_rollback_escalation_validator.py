"""Rollback escalation validator for ADR0093 generator migration mode."""

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


class GeneratorRollbackEscalationValidator(ValidatorJsonPlugin):
    """Warn when generators remain in rollback mode beyond policy threshold."""

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None

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

    def _load_policy(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
    ) -> tuple[dict[str, Any], list[PluginDiagnostic]]:
        diagnostics: list[PluginDiagnostic] = []
        policy_path_raw = ctx.config.get("rollback_policy_path")
        if not isinstance(policy_path_raw, str) or not policy_path_raw.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9400",
                    severity="error",
                    stage=stage,
                    message="rollback_policy_path is required for rollback escalation validator.",
                    path="pipeline:config.rollback_policy_path",
                )
            )
            return {}, diagnostics
        policy_path = self._resolve_policy_path(ctx=ctx, value=policy_path_raw)
        if not policy_path.exists() or not policy_path.is_file():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9400",
                    severity="error",
                    stage=stage,
                    message=f"rollback policy file does not exist: {policy_path}",
                    path=f"pipeline:config.rollback_policy_path={policy_path}",
                )
            )
            return {}, diagnostics
        try:
            payload = load_yaml_file(policy_path)
        except (OSError, yaml.YAMLError) as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9400",
                    severity="error",
                    stage=stage,
                    message=f"failed to load rollback policy file '{policy_path}': {exc}",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        if not isinstance(payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9400",
                    severity="error",
                    stage=stage,
                    message=f"rollback policy '{policy_path}' must be a YAML object.",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        schema_version = payload.get("schema_version")
        if schema_version != 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9400",
                    severity="error",
                    stage=stage,
                    message=f"rollback policy '{policy_path}' schema_version must be 1.",
                    path=str(policy_path),
                )
            )
            return {}, diagnostics
        return payload, diagnostics

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        registry = ctx.config.get("plugin_registry")
        specs = getattr(registry, "specs", None)
        if not isinstance(specs, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9401",
                    severity="warning",
                    stage=stage,
                    message="plugin_registry specs are unavailable; rollback escalation checks skipped.",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        policy, policy_diags = self._load_policy(ctx=ctx, stage=stage)
        diagnostics.extend(policy_diags)
        if any(diag.severity == "error" for diag in policy_diags):
            return self.make_result(diagnostics=diagnostics)

        max_days_raw = policy.get("max_rollback_days", 7)
        max_days = max_days_raw if isinstance(max_days_raw, int) and max_days_raw >= 1 else 7
        policy_generators = policy.get("generators")
        generator_policy = policy_generators if isinstance(policy_generators, dict) else {}
        overrides_raw = ctx.config.get("rollback_overrides")
        overrides = overrides_raw if isinstance(overrides_raw, dict) else {}
        policy_map = dict(generator_policy)
        policy_map.update(overrides)

        config_today = self._parse_date(ctx.config.get("rollback_today"))
        today = config_today or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        summary: dict[str, Any] = {
            "rollback_generators": 0,
            "escalated": 0,
            "missing_started_at": 0,
            "warnings": 0,
            "max_rollback_days": max_days,
            "today": today.date().isoformat(),
            "events": [],
        }

        for plugin_id, spec in sorted(specs.items()):
            if spec.kind != PluginKind.GENERATOR:
                continue
            mode = str(getattr(spec, "migration_mode", "legacy")).strip().lower() or "legacy"
            if mode != "rollback":
                continue

            summary["rollback_generators"] += 1
            item = policy_map.get(plugin_id)
            started_at_raw = item.get("rollback_started_at") if isinstance(item, dict) else None
            started_at = self._parse_date(started_at_raw)
            if started_at is None:
                summary["events"].append(
                    {
                        "event_type": "rollback_missing_started_at",
                        "plugin_id": plugin_id,
                        "recorded_at": today.date().isoformat(),
                        "severity": "warning",
                    }
                )
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9402",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"generator '{plugin_id}' is in rollback mode without rollback_started_at metadata "
                            "(policy contract)."
                        ),
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["missing_started_at"] += 1
                summary["warnings"] += 1
                continue

            rollback_days = (today.date() - started_at.date()).days
            if rollback_days > max_days:
                summary["events"].append(
                    {
                        "event_type": "rollback_escalated",
                        "plugin_id": plugin_id,
                        "recorded_at": today.date().isoformat(),
                        "severity": "warning",
                        "rollback_days": rollback_days,
                        "max_rollback_days": max_days,
                        "rollback_started_at": started_at.date().isoformat(),
                    }
                )
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9403",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"generator '{plugin_id}' has been in rollback mode for {rollback_days} days "
                            f"(policy max {max_days}); escalation required."
                        ),
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["escalated"] += 1
                summary["warnings"] += 1
            else:
                summary["events"].append(
                    {
                        "event_type": "rollback_within_threshold",
                        "plugin_id": plugin_id,
                        "recorded_at": today.date().isoformat(),
                        "severity": "info",
                        "rollback_days": rollback_days,
                        "max_rollback_days": max_days,
                        "rollback_started_at": started_at.date().isoformat(),
                    }
                )

        diagnostics.append(
            self.emit_diagnostic(
                code="I9400",
                severity="info",
                stage=stage,
                message=(
                    "generator rollback summary: "
                    f"rollback_generators={summary['rollback_generators']} escalated={summary['escalated']} "
                    f"missing_started_at={summary['missing_started_at']} warnings={summary['warnings']}"
                ),
                path="pipeline:validate",
            )
        )
        try:
            ctx.publish("generator_rollback_summary", summary)
        except PluginDataExchangeError:
            pass
        return self.make_result(diagnostics=diagnostics, output_data={"generator_rollback_summary": summary})

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

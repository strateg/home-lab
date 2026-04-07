"""Sunset enforcement validator for ADR0093 migrated generator families."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginKind,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)

_SUPPORTED_MODES = {"legacy", "migrating", "migrated", "rollback"}


class GeneratorSunsetValidator(ValidatorJsonPlugin):
    """Apply sunset/grace/hard-error policy for scheduled legacy generators."""

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

        raw_schedule = ctx.config.get("sunset_schedule")
        schedule = raw_schedule if isinstance(raw_schedule, dict) else {}

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
            if today < sunset_date:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9397",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"generator '{plugin_id}' is legacy and scheduled for ADR0093 sunset on "
                            f"{sunset_date.date().isoformat()} (hard error after {hard_error_date.date().isoformat()})."
                        ),
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["warnings"] += 1
            elif today <= hard_error_date:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W9398",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"generator '{plugin_id}' is still legacy during ADR0093 grace period; "
                            f"hard error date is {hard_error_date.date().isoformat()}."
                        ),
                        path=f"plugin:{plugin_id}",
                    )
                )
                summary["warnings"] += 1
            else:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9399",
                        severity="error",
                        stage=stage,
                        message=(
                            f"generator '{plugin_id}' remains legacy after ADR0093 hard error date "
                            f"{hard_error_date.date().isoformat()}."
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

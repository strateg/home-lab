"""Generator migration status validator for ADR0093 rollout visibility."""

from __future__ import annotations

from collections import Counter
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

_SUPPORTED_MODES = ("legacy", "migrating", "migrated", "rollback")


class GeneratorMigrationStatusValidator(ValidatorJsonPlugin):
    """Emit migration status summary for generator plugins."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        registry = ctx.config.get("plugin_registry")
        specs = getattr(registry, "specs", None)
        if not isinstance(specs, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9391",
                    severity="warning",
                    stage=stage,
                    message="plugin_registry specs are unavailable; generator migration status summary skipped.",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        migration_counter: Counter[str] = Counter()
        unknown_mode_specs: list[str] = []

        for plugin_id, spec in specs.items():
            try:
                if spec.kind != PluginKind.GENERATOR:
                    continue
            except Exception:
                continue
            mode_raw = getattr(spec, "migration_mode", "legacy")
            mode = str(mode_raw).strip().lower() or "legacy"
            if mode not in _SUPPORTED_MODES:
                unknown_mode_specs.append(plugin_id)
                mode = "legacy"
            migration_counter[mode] += 1

        if unknown_mode_specs:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9392",
                    severity="warning",
                    stage=stage,
                    message=(
                        "Unknown generator migration_mode values found; treated as legacy for summary: "
                        + ", ".join(sorted(unknown_mode_specs))
                    ),
                    path="pipeline:validate",
                )
            )

        parts = [f"{mode}={migration_counter.get(mode, 0)}" for mode in _SUPPORTED_MODES]
        diagnostics.append(
            self.emit_diagnostic(
                code="I9390",
                severity="info",
                stage=stage,
                message=f"generator migration status: {', '.join(parts)}",
                path="pipeline:validate",
            )
        )

        summary: dict[str, Any] = {
            "legacy": migration_counter.get("legacy", 0),
            "migrating": migration_counter.get("migrating", 0),
            "migrated": migration_counter.get("migrated", 0),
            "rollback": migration_counter.get("rollback", 0),
            "total_generators": sum(migration_counter.values()),
        }
        try:
            ctx.publish("generator_migration_summary", summary)
        except PluginDataExchangeError:
            # Standalone tests can execute without registry execution scope.
            pass
        return self.make_result(diagnostics=diagnostics, output_data={"generator_migration_summary": summary})

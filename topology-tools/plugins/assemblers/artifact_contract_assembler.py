"""Assembler-stage contract guard for ADR0093 migrated generators."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    AssemblerPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginKind,
    PluginResult,
    Stage,
)


class ArtifactContractAssembler(AssemblerPlugin):
    """Validate migrated generator contract publications before assemble finalize."""

    _REQUIRED_KEYS = ("artifact_plan", "artifact_generation_report", "artifact_contract_files")

    @staticmethod
    def _resolve_registry(ctx: PluginContext) -> Any:
        return ctx.config.get("plugin_registry")

    @staticmethod
    def _resolve_enforce_migrating(ctx: PluginContext) -> bool:
        raw = ctx.config.get("enforce_migrating")
        if isinstance(raw, bool):
            return raw
        return False

    @staticmethod
    def _is_valid_contract_files(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        return all(isinstance(item, str) and item.strip() for item in value)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        registry = self._resolve_registry(ctx)
        specs = getattr(registry, "specs", None)
        if not isinstance(specs, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W9395",
                    severity="warning",
                    stage=stage,
                    message="plugin_registry specs are unavailable; artifact contract assemble guard skipped.",
                    path="pipeline:assemble",
                )
            )
            return self.make_result(diagnostics=diagnostics, output_data={"artifact_contract_guard": None})

        published_data = ctx.get_published_data()
        enforce_migrating = self._resolve_enforce_migrating(ctx)

        summary = {
            "legacy": 0,
            "migrating": 0,
            "migrated": 0,
            "rollback": 0,
            "checked": 0,
            "missing_contracts": [],
        }

        for plugin_id, spec in sorted(specs.items()):
            if spec.kind != PluginKind.GENERATOR:
                continue
            mode = str(getattr(spec, "migration_mode", "legacy")).strip().lower() or "legacy"
            if mode not in summary:
                mode = "legacy"
            summary[mode] += 1
            if mode in {"legacy", "rollback"}:
                continue

            summary["checked"] += 1
            payload = published_data.get(plugin_id, {})
            missing = [key for key in self._REQUIRED_KEYS if key not in payload]
            if "artifact_contract_files" not in missing and not self._is_valid_contract_files(
                payload["artifact_contract_files"]
            ):
                missing.append("artifact_contract_files(non-empty-list)")

            if not missing:
                continue

            summary["missing_contracts"].append({"plugin_id": plugin_id, "mode": mode, "missing": sorted(missing)})
            if mode == "migrated" or (mode == "migrating" and enforce_migrating):
                severity = "error"
                code = "E9394"
            else:
                severity = "warning"
                code = "W9393"
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity=severity,
                    stage=stage,
                    message=(
                        f"generator '{plugin_id}' migration_mode={mode} is missing required contract keys: "
                        + ", ".join(sorted(missing))
                    ),
                    path=f"plugin:{plugin_id}",
                )
            )

        diagnostics.append(
            self.emit_diagnostic(
                code="I9396",
                severity="info",
                stage=stage,
                message=(
                    "artifact contract guard summary: "
                    f"legacy={summary['legacy']} migrating={summary['migrating']} "
                    f"migrated={summary['migrated']} rollback={summary['rollback']} "
                    f"checked={summary['checked']} missing={len(summary['missing_contracts'])}"
                ),
                path="pipeline:assemble",
            )
        )
        try:
            ctx.publish("artifact_contract_guard", summary)
        except PluginDataExchangeError:
            pass
        return self.make_result(diagnostics=diagnostics, output_data={"artifact_contract_guard": summary})

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

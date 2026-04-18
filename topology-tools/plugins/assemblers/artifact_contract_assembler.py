"""Assembler-stage contract guard for ADR0093 migrated generators."""

from __future__ import annotations

from pathlib import Path
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
    def _is_valid_contract_files(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        return all(isinstance(item, str) and item.strip() for item in value)

    @staticmethod
    def _normalize_generated_dir(value: Any) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            return None
        return Path(value.strip()).resolve()

    @staticmethod
    def _paths_overlap(left: Path, right: Path) -> bool:
        if left == right:
            return True
        left_parts = left.parts
        right_parts = right.parts
        shared_len = min(len(left_parts), len(right_parts))
        if shared_len == 0:
            return False
        if left_parts[:shared_len] != right_parts[:shared_len]:
            return False
        return left == right or left in right.parents or right in left.parents

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
        summary: dict[str, Any] = {
            "legacy": 0,
            "migrating": 0,
            "migrated": 0,
            "rollback": 0,
            "checked": 0,
            "missing_contracts": [],
            "prefix_conflicts": [],
        }
        generator_output_roots: list[tuple[str, str, Path]] = []

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
                generated_dir = self._normalize_generated_dir(payload.get("generated_dir"))
                if generated_dir is not None:
                    generator_output_roots.append((plugin_id, mode, generated_dir))
            else:
                summary["missing_contracts"].append({"plugin_id": plugin_id, "mode": mode, "missing": sorted(missing)})
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9394",
                        severity="error",
                        stage=stage,
                        message=(
                            f"generator '{plugin_id}' migration_mode={mode} is missing required contract keys: "
                            + ", ".join(sorted(missing))
                        ),
                        path=f"plugin:{plugin_id}",
                    )
                )

        for idx, left in enumerate(generator_output_roots):
            left_id, left_mode, left_root = left
            for right_id, right_mode, right_root in generator_output_roots[idx + 1 :]:
                if not self._paths_overlap(left_root, right_root):
                    continue
                summary["prefix_conflicts"].append(
                    {
                        "plugin_a": left_id,
                        "mode_a": left_mode,
                        "generated_dir_a": str(left_root),
                        "plugin_b": right_id,
                        "mode_b": right_mode,
                        "generated_dir_b": str(right_root),
                    }
                )
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E9391",
                        severity="error",
                        stage=stage,
                        message=(
                            "overlapping generator output prefixes detected for ADR0093 ownership contract: "
                            f"'{left_id}' ({left_root}) and '{right_id}' ({right_root})"
                        ),
                        path=f"plugin:{left_id}|{right_id}",
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
                    f"checked={summary['checked']} missing={len(summary['missing_contracts'])} "
                    f"prefix_conflicts={len(summary['prefix_conflicts'])}"
                ),
                path="pipeline:assemble",
            )
        )
        ctx.publish("artifact_contract_guard", summary)
        return self.make_result(diagnostics=diagnostics, output_data={"artifact_contract_guard": summary})

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

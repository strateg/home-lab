"""Build-stage plugins for release packaging (ADR 0080 Wave G)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kernel.plugin_base import (
    BuilderPlugin,
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ReleaseBundleBuilder(BuilderPlugin):
    """Create zip bundle from assembled workspace artifacts."""

    @staticmethod
    def _repo_root(ctx: PluginContext) -> Path:
        repo_root = ctx.config.get("repo_root")
        if isinstance(repo_root, str) and repo_root.strip():
            return Path(repo_root).resolve()
        return Path.cwd()

    @staticmethod
    def _dist_root(ctx: PluginContext) -> Path:
        if isinstance(ctx.dist_root, str) and ctx.dist_root.strip():
            candidate = Path(ctx.dist_root)
            if candidate.is_absolute():
                return candidate.resolve()
            return (ReleaseBundleBuilder._repo_root(ctx) / candidate).resolve()
        raw = ctx.config.get("dist_root")
        if isinstance(raw, str) and raw.strip():
            candidate = Path(raw)
            if candidate.is_absolute():
                return candidate.resolve()
            return (ReleaseBundleBuilder._repo_root(ctx) / candidate).resolve()
        return Path.cwd() / "dist"

    @staticmethod
    def _workspace_root(ctx: PluginContext) -> Path:
        if isinstance(ctx.workspace_root, str) and ctx.workspace_root.strip():
            candidate = Path(ctx.workspace_root)
            if candidate.is_absolute():
                return candidate.resolve()
            return (ReleaseBundleBuilder._repo_root(ctx) / candidate).resolve()
        return Path.cwd() / ".work" / "native"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            assembly_manifest_path = Path(ctx.subscribe("base.assembler.manifest", "assembly_manifest_path"))
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8201",
                    severity="error",
                    stage=stage,
                    message=f"build bundle requires assembly_manifest_path: {exc}",
                    path="plugin:base.assembler.manifest:assembly_manifest_path",
                )
            )
            return self.make_result(diagnostics)

        if not assembly_manifest_path.exists():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8201",
                    severity="error",
                    stage=stage,
                    message=f"assembly manifest does not exist: {assembly_manifest_path}",
                    path=str(assembly_manifest_path),
                )
            )
            return self.make_result(diagnostics)

        try:
            assembly_manifest = json.loads(assembly_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8201",
                    severity="error",
                    stage=stage,
                    message=f"failed to parse assembly manifest: {exc}",
                    path=str(assembly_manifest_path),
                )
            )
            return self.make_result(diagnostics)

        workspace_root = self._workspace_root(ctx)
        dist_root = self._dist_root(ctx)
        dist_root.mkdir(parents=True, exist_ok=True)
        ctx.dist_root = str(dist_root)

        project_id = str(ctx.config.get("project_id", "project")).strip() or "project"
        release_tag = str(ctx.release_tag).strip() if isinstance(ctx.release_tag, str) else ""
        archive_name = f"{project_id}-{release_tag}.zip" if release_tag else f"{project_id}.zip"
        bundle_path = dist_root / archive_name

        files = assembly_manifest.get("files", [])
        if not isinstance(files, list):
            files = []

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for row in files:
                if not isinstance(row, dict):
                    continue
                rel_path = row.get("path")
                if not isinstance(rel_path, str) or not rel_path.strip():
                    continue
                source_path = workspace_root / rel_path
                if not source_path.exists() or not source_path.is_file():
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E8201",
                            severity="error",
                            stage=stage,
                            message=f"assembly file missing while building bundle: {source_path}",
                            path=str(source_path),
                        )
                    )
                    continue
                archive.write(source_path, arcname=Path(rel_path).as_posix())

        bundle_sha256 = _sha256(bundle_path)
        generated_files = [str(bundle_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("release_bundle_path", str(bundle_path))
            ctx.publish("release_bundle_sha256", bundle_sha256)
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8201",
                severity="info",
                stage=stage,
                message=f"release bundle created: {bundle_path.name}",
                path=str(bundle_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "release_bundle_path": str(bundle_path),
                "release_bundle_sha256": bundle_sha256,
                "generated_files": generated_files,
            },
        )

    def on_run(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class SbomBuilder(BuilderPlugin):
    """Emit minimal SBOM JSON from assembly manifest."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            assembly_manifest = ctx.subscribe("base.assembler.manifest", "assembly_manifest")
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8202",
                    severity="error",
                    stage=stage,
                    message=f"sbom requires assembly_manifest payload: {exc}",
                    path="plugin:base.assembler.manifest:assembly_manifest",
                )
            )
            return self.make_result(diagnostics)

        if not isinstance(assembly_manifest, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8202",
                    severity="error",
                    stage=stage,
                    message="assembly_manifest payload is not an object.",
                    path="plugin:base.assembler.manifest:assembly_manifest",
                )
            )
            return self.make_result(diagnostics)

        dist_root = ReleaseBundleBuilder._dist_root(ctx)
        sbom_root = (
            Path(ctx.sbom_output_dir).resolve()
            if isinstance(ctx.sbom_output_dir, str) and ctx.sbom_output_dir.strip()
            else dist_root / "sbom"
        )
        sbom_root.mkdir(parents=True, exist_ok=True)
        ctx.sbom_output_dir = str(sbom_root)

        sbom_path = sbom_root / "sbom.json"
        files = assembly_manifest.get("files", [])
        sbom_payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "project_id": str(ctx.config.get("project_id", "")),
            "artifacts": files if isinstance(files, list) else [],
        }
        sbom_path.write_text(json.dumps(sbom_payload, ensure_ascii=True, indent=2), encoding="utf-8")

        generated_files = [str(sbom_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("sbom_path", str(sbom_path))
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8202",
                severity="info",
                stage=stage,
                message=f"sbom generated: {sbom_path.name}",
                path=str(sbom_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"sbom_path": str(sbom_path), "generated_files": generated_files},
        )

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class ArtifactFamilySummaryBuilder(BuilderPlugin):
    """Aggregate ADR0093 generation metadata into build artifact-family summary."""

    @staticmethod
    def _as_sorted_strings(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        normalized = {str(item).strip() for item in values if isinstance(item, str) and item.strip()}
        return sorted(normalized)

    @staticmethod
    def _migration_mode(ctx: PluginContext, plugin_id: str) -> str:
        registry = ctx.config.get("plugin_registry")
        specs = getattr(registry, "specs", None)
        if isinstance(specs, dict):
            spec = specs.get(plugin_id)
            if spec is not None:
                raw = getattr(spec, "migration_mode", "legacy")
                if isinstance(raw, str) and raw.strip():
                    token = raw.strip().lower()
                    if token in {"legacy", "migrating", "migrated", "rollback"}:
                        return token
        return "legacy"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        published = ctx.get_published_data()
        families: list[dict[str, Any]] = []
        totals = {
            "plugins": 0,
            "planned_outputs": 0,
            "generated": 0,
            "skipped": 0,
            "obsolete": 0,
            "warnings": 0,
        }

        for plugin_id in sorted(published.keys()):
            payload = published.get(plugin_id)
            if not isinstance(payload, dict):
                continue
            artifact_plan = payload.get("artifact_plan")
            generation_report = payload.get("artifact_generation_report")
            if not isinstance(artifact_plan, dict) and not isinstance(generation_report, dict):
                continue

            planned_entries = self._as_sorted_strings(
                [
                    item.get("path")
                    for item in artifact_plan.get("planned_outputs", [])
                    if isinstance(item, dict) and isinstance(item.get("path"), str)
                ]
                if isinstance(artifact_plan, dict)
                else []
            )
            generated_entries = self._as_sorted_strings(
                generation_report.get("generated", []) if isinstance(generation_report, dict) else []
            )
            skipped_entries = self._as_sorted_strings(
                generation_report.get("skipped", []) if isinstance(generation_report, dict) else []
            )

            issues: list[str] = []
            overlap = sorted(set(generated_entries) & set(skipped_entries))
            if overlap:
                issues.append("generated and skipped overlap")
            if planned_entries:
                unknown_generated = sorted(set(generated_entries) - set(planned_entries))
                unknown_skipped = sorted(set(skipped_entries) - set(planned_entries))
                if unknown_generated:
                    issues.append("generated contains entries outside planned_outputs")
                if unknown_skipped:
                    issues.append("skipped contains entries outside planned_outputs")

            if issues:
                totals["warnings"] += len(issues)
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W8204",
                        severity="warning",
                        stage=stage,
                        message=f"artifact metadata consistency issues for '{plugin_id}': {'; '.join(issues)}",
                        path=f"plugin:{plugin_id}",
                    )
                )

            summary_obj = generation_report.get("summary", {}) if isinstance(generation_report, dict) else {}
            planned_count = len(planned_entries)
            generated_count = len(generated_entries)
            skipped_count = len(skipped_entries)
            obsolete_count = 0
            if isinstance(summary_obj, dict):
                obsolete_raw = summary_obj.get("obsolete_count")
                if isinstance(obsolete_raw, int) and obsolete_raw >= 0:
                    obsolete_count = obsolete_raw

            totals["plugins"] += 1
            totals["planned_outputs"] += planned_count
            totals["generated"] += generated_count
            totals["skipped"] += skipped_count
            totals["obsolete"] += obsolete_count

            artifact_family = ""
            if isinstance(generation_report, dict) and isinstance(generation_report.get("artifact_family"), str):
                artifact_family = generation_report["artifact_family"].strip()
            if (
                not artifact_family
                and isinstance(artifact_plan, dict)
                and isinstance(artifact_plan.get("artifact_family"), str)
            ):
                artifact_family = artifact_plan["artifact_family"].strip()

            families.append(
                {
                    "plugin_id": plugin_id,
                    "migration_mode": self._migration_mode(ctx, plugin_id),
                    "artifact_family": artifact_family,
                    "planned_count": planned_count,
                    "generated_count": generated_count,
                    "skipped_count": skipped_count,
                    "obsolete_count": obsolete_count,
                    "issues": issues,
                }
            )

        payload = {
            "schema_version": 1,
            "project_id": str(ctx.config.get("project_id", "")),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "totals": totals,
            "families": families,
        }

        dist_root = ReleaseBundleBuilder._dist_root(ctx)
        dist_root.mkdir(parents=True, exist_ok=True)
        summary_path = dist_root / "artifact-family-summary.json"
        summary_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

        generated_files = [str(summary_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("artifact_family_summary_path", str(summary_path))
            ctx.publish("artifact_family_summary", payload)
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8204",
                severity="info",
                stage=stage,
                message=f"artifact family summary generated for {totals['plugins']} plugins",
                path=str(summary_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "artifact_family_summary_path": str(summary_path),
                "generated_files": generated_files,
                "artifact_family_plugins": totals["plugins"],
            },
        )

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class GeneratorReadinessEvidenceBuilder(BuilderPlugin):
    """Emit consolidated ADR0093 generator migration evidence for operators."""

    @staticmethod
    def _summary(payload: Any, key: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        value = payload.get(key)
        return value if isinstance(value, dict) else {}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        published = ctx.get_published_data()

        migration_summary = self._summary(
            published.get("base.validator.generator_migration_status"),
            "generator_migration_summary",
        )
        sunset_summary = self._summary(
            published.get("base.validator.generator_sunset"),
            "generator_sunset_summary",
        )
        rollback_summary = self._summary(
            published.get("base.validator.generator_rollback_escalation"),
            "generator_rollback_summary",
        )
        artifact_family_summary = self._summary(
            published.get("base.builder.artifact_family_summary"),
            "artifact_family_summary",
        )

        readiness_status = "green"
        blocking_reasons: list[str] = []
        warning_reasons: list[str] = []

        sunset_errors = sunset_summary.get("errors")
        if isinstance(sunset_errors, int) and sunset_errors > 0:
            readiness_status = "blocked"
            blocking_reasons.append("sunset policy hard-error violations detected")

        rollback_escalated = rollback_summary.get("escalated")
        if isinstance(rollback_escalated, int) and rollback_escalated > 0:
            if readiness_status != "blocked":
                readiness_status = "warning"
            warning_reasons.append("rollback escalation warnings detected")

        rollback_missing_started_at = rollback_summary.get("missing_started_at")
        if isinstance(rollback_missing_started_at, int) and rollback_missing_started_at > 0:
            if readiness_status != "blocked":
                readiness_status = "warning"
            warning_reasons.append("rollback policy metadata gaps detected")

        sunset_warnings = sunset_summary.get("warnings")
        if isinstance(sunset_warnings, int) and sunset_warnings > 0:
            if readiness_status != "blocked":
                readiness_status = "warning"
            warning_reasons.append("sunset policy warnings detected")

        pre_sunset_legacy_targets = sunset_summary.get("pre_sunset_legacy_targets")
        if not isinstance(pre_sunset_legacy_targets, int):
            pre_sunset_legacy_targets = 0
        grace_window_legacy_targets = sunset_summary.get("grace_window_legacy_targets")
        if not isinstance(grace_window_legacy_targets, int):
            grace_window_legacy_targets = 0
        hard_error_legacy_targets = sunset_errors if isinstance(sunset_errors, int) else 0

        evidence = {
            "schema_version": 1,
            "project_id": str(ctx.config.get("project_id", "")),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "readiness": {
                "status": readiness_status,
                "blocking_reasons": blocking_reasons,
                "warning_reasons": sorted(set(warning_reasons)),
            },
            "generator_migration_summary": migration_summary,
            "generator_sunset_summary": sunset_summary,
            "sunset_phase_breakdown": {
                "pre_sunset_legacy_targets": pre_sunset_legacy_targets,
                "grace_window_legacy_targets": grace_window_legacy_targets,
                "hard_error_legacy_targets": hard_error_legacy_targets,
            },
            "generator_rollback_summary": rollback_summary,
            "artifact_family_summary_totals": artifact_family_summary.get("totals", {}),
        }

        dist_root = ReleaseBundleBuilder._dist_root(ctx)
        dist_root.mkdir(parents=True, exist_ok=True)
        evidence_path = dist_root / "generator-readiness-evidence.json"
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=True, indent=2), encoding="utf-8")

        generated_files = [str(evidence_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("generator_readiness_evidence_path", str(evidence_path))
            ctx.publish("generator_readiness_evidence", evidence)
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8205",
                severity="info",
                stage=stage,
                message=f"generator readiness evidence emitted with status={readiness_status}",
                path=str(evidence_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "generator_readiness_evidence_path": str(evidence_path),
                "generated_files": generated_files,
                "generator_readiness_status": readiness_status,
            },
        )

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class ReadinessReportsBuilder(BuilderPlugin):
    """Emit ADR0091-compatible readiness reports from consolidated evidence."""

    @staticmethod
    def _report_status(readiness_status: str) -> str:
        token = readiness_status.strip().lower()
        if token in {"green", "warning", "blocked"}:
            return token
        return "warning"

    @staticmethod
    def _resolve_check_status(*, passed: bool, blocked: bool = False) -> str:
        if blocked:
            return "blocked"
        return "pass" if passed else "warning"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            readiness_evidence = ctx.subscribe(
                "base.builder.generator_readiness_evidence", "generator_readiness_evidence"
            )
        except PluginDataExchangeError as exc:
            published = ctx.get_published_data()
            source_payload = published.get("base.builder.generator_readiness_evidence", {})
            readiness_evidence = (
                source_payload.get("generator_readiness_evidence") if isinstance(source_payload, dict) else None
            )
            if not isinstance(readiness_evidence, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E8206",
                        severity="error",
                        stage=stage,
                        message=f"readiness reports require generator_readiness_evidence payload: {exc}",
                        path="plugin:base.builder.generator_readiness_evidence:generator_readiness_evidence",
                    )
                )
                return self.make_result(diagnostics=diagnostics)
        if not isinstance(readiness_evidence, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8206",
                    severity="error",
                    stage=stage,
                    message="generator_readiness_evidence payload is not an object.",
                    path="plugin:base.builder.generator_readiness_evidence:generator_readiness_evidence",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        readiness = readiness_evidence.get("readiness", {})
        readiness_status = ""
        if isinstance(readiness, dict):
            raw_status = readiness.get("status")
            if isinstance(raw_status, str):
                readiness_status = raw_status
        normalized_status = self._report_status(readiness_status)

        migration_summary = readiness_evidence.get("generator_migration_summary", {})
        sunset_summary = readiness_evidence.get("generator_sunset_summary", {})
        rollback_summary = readiness_evidence.get("generator_rollback_summary", {})
        artifact_totals = readiness_evidence.get("artifact_family_summary_totals", {})
        sunset_phase_breakdown = readiness_evidence.get("sunset_phase_breakdown", {})
        rollback_events = (
            rollback_summary.get("events")
            if isinstance(rollback_summary, dict) and isinstance(rollback_summary.get("events"), list)
            else []
        )

        legacy_count = migration_summary.get("legacy", 0) if isinstance(migration_summary, dict) else 0
        sunset_errors = sunset_summary.get("errors", 0) if isinstance(sunset_summary, dict) else 0
        sunset_warnings = sunset_summary.get("warnings", 0) if isinstance(sunset_summary, dict) else 0
        sunset_pre_sunset = 0
        sunset_grace_window = 0
        if isinstance(sunset_phase_breakdown, dict):
            pre = sunset_phase_breakdown.get("pre_sunset_legacy_targets")
            grace = sunset_phase_breakdown.get("grace_window_legacy_targets")
            if isinstance(pre, int):
                sunset_pre_sunset = pre
            if isinstance(grace, int):
                sunset_grace_window = grace
        if not isinstance(sunset_pre_sunset, int):
            sunset_pre_sunset = 0
        if not isinstance(sunset_grace_window, int):
            sunset_grace_window = 0
        if sunset_pre_sunset == 0 and isinstance(sunset_summary, dict):
            pre = sunset_summary.get("pre_sunset_legacy_targets")
            if isinstance(pre, int):
                sunset_pre_sunset = pre
        if sunset_grace_window == 0 and isinstance(sunset_summary, dict):
            grace = sunset_summary.get("grace_window_legacy_targets")
            if isinstance(grace, int):
                sunset_grace_window = grace
        sunset_hard_error_legacy = 0
        if isinstance(sunset_phase_breakdown, dict):
            hard = sunset_phase_breakdown.get("hard_error_legacy_targets")
            if isinstance(hard, int):
                sunset_hard_error_legacy = hard
        if sunset_hard_error_legacy == 0 and isinstance(sunset_errors, int):
            sunset_hard_error_legacy = sunset_errors
        rollback_escalated = rollback_summary.get("escalated", 0) if isinstance(rollback_summary, dict) else 0
        rollback_missing = rollback_summary.get("missing_started_at", 0) if isinstance(rollback_summary, dict) else 0
        planned_plugins = artifact_totals.get("plugins", 0) if isinstance(artifact_totals, dict) else 0

        checks = [
            {
                "check_id": "migration-legacy-count",
                "status": self._resolve_check_status(passed=isinstance(legacy_count, int) and legacy_count == 0),
                "details": {"legacy": legacy_count},
            },
            {
                "check_id": "sunset-enforcement",
                "status": self._resolve_check_status(
                    passed=isinstance(sunset_warnings, int) and sunset_warnings == 0,
                    blocked=isinstance(sunset_errors, int) and sunset_errors > 0,
                ),
                "details": {
                    "errors": sunset_errors,
                    "warnings": sunset_warnings,
                    "pre_sunset_legacy_targets": sunset_pre_sunset,
                    "grace_window_legacy_targets": sunset_grace_window,
                },
            },
            {
                "check_id": "sunset-hard-error-phase",
                "status": self._resolve_check_status(
                    passed=isinstance(sunset_hard_error_legacy, int) and sunset_hard_error_legacy == 0,
                    blocked=isinstance(sunset_hard_error_legacy, int) and sunset_hard_error_legacy > 0,
                ),
                "details": {"hard_error_legacy_targets": sunset_hard_error_legacy},
            },
            {
                "check_id": "rollback-escalation",
                "status": self._resolve_check_status(
                    passed=(isinstance(rollback_escalated, int) and rollback_escalated == 0)
                    and (isinstance(rollback_missing, int) and rollback_missing == 0)
                ),
                "details": {"escalated": rollback_escalated, "missing_started_at": rollback_missing},
            },
            {
                "check_id": "artifact-family-coverage",
                "status": self._resolve_check_status(passed=isinstance(planned_plugins, int) and planned_plugins > 0),
                "details": {"artifact_family_plugins": planned_plugins},
            },
        ]

        report_payload = {
            "schema_version": 1,
            "profile": "adr0091.restore-readiness.v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "project_id": str(ctx.config.get("project_id", "")),
            "status": normalized_status,
            "checks": checks,
            "source_evidence": {
                "generator_readiness_status": normalized_status,
                "generator_migration_summary": migration_summary if isinstance(migration_summary, dict) else {},
                "generator_sunset_summary": sunset_summary if isinstance(sunset_summary, dict) else {},
                "sunset_phase_breakdown": sunset_phase_breakdown if isinstance(sunset_phase_breakdown, dict) else {},
                "generator_rollback_summary": rollback_summary if isinstance(rollback_summary, dict) else {},
                "artifact_family_summary_totals": artifact_totals if isinstance(artifact_totals, dict) else {},
            },
        }

        dist_root = ReleaseBundleBuilder._dist_root(ctx)
        reports_root = dist_root / "reports"
        reports_root.mkdir(parents=True, exist_ok=True)
        report_path = reports_root / "restore-readiness.json"
        report_path.write_text(json.dumps(report_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        rollback_events_path = reports_root / "rollback-events.json"
        rollback_events_payload = {
            "schema_version": 1,
            "profile": "adr0093.rollback-events.v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "project_id": str(ctx.config.get("project_id", "")),
            "events": rollback_events,
            "summary": {
                "rollback_generators": (
                    rollback_summary.get("rollback_generators", 0) if isinstance(rollback_summary, dict) else 0
                ),
                "escalated": rollback_summary.get("escalated", 0) if isinstance(rollback_summary, dict) else 0,
                "missing_started_at": (
                    rollback_summary.get("missing_started_at", 0) if isinstance(rollback_summary, dict) else 0
                ),
            },
        }
        rollback_events_path.write_text(
            json.dumps(rollback_events_payload, ensure_ascii=True, indent=2), encoding="utf-8"
        )

        generated_files = [str(report_path), str(rollback_events_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("restore_readiness_report_path", str(report_path))
            ctx.publish("restore_readiness_report", report_payload)
            ctx.publish("rollback_events_report_path", str(rollback_events_path))
            ctx.publish("rollback_events_report", rollback_events_payload)
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8206",
                severity="info",
                stage=stage,
                message=f"ADR0091 restore-readiness report emitted with status={normalized_status}",
                path=str(report_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "restore_readiness_report_path": str(report_path),
                "rollback_events_report_path": str(rollback_events_path),
                "generated_files": generated_files,
            },
        )

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)


class ReleaseManifestBuilder(BuilderPlugin):
    """Emit release manifest from bundle + SBOM outputs."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            bundle_path = str(ctx.subscribe("base.builder.bundle", "release_bundle_path"))
            bundle_sha256 = str(ctx.subscribe("base.builder.bundle", "release_bundle_sha256"))
            sbom_path = str(ctx.subscribe("base.builder.sbom", "sbom_path"))
            assembly_manifest_path = str(ctx.subscribe("base.assembler.manifest", "assembly_manifest_path"))
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E8203",
                    severity="error",
                    stage=stage,
                    message=f"release manifest requires build inputs: {exc}",
                    path="build:release-manifest",
                )
            )
            return self.make_result(diagnostics)
        try:
            artifact_family_summary_path = str(
                ctx.subscribe("base.builder.artifact_family_summary", "artifact_family_summary_path")
            )
        except PluginDataExchangeError:
            artifact_family_summary_path = ""
        try:
            generator_readiness_evidence_path = str(
                ctx.subscribe("base.builder.generator_readiness_evidence", "generator_readiness_evidence_path")
            )
        except PluginDataExchangeError:
            generator_readiness_evidence_path = ""
        try:
            restore_readiness_report_path = str(
                ctx.subscribe("base.builder.readiness_reports", "restore_readiness_report_path")
            )
        except PluginDataExchangeError:
            restore_readiness_report_path = ""
        try:
            rollback_events_report_path = str(
                ctx.subscribe("base.builder.readiness_reports", "rollback_events_report_path")
            )
        except PluginDataExchangeError:
            rollback_events_report_path = ""

        dist_root = ReleaseBundleBuilder._dist_root(ctx)
        dist_root.mkdir(parents=True, exist_ok=True)
        manifest_path = dist_root / "release-manifest.json"

        payload: dict[str, Any] = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "project_id": str(ctx.config.get("project_id", "")),
            "release_tag": str(ctx.release_tag or ""),
            "signing_backend": str(ctx.signing_backend or "none"),
            "bundle": {
                "path": bundle_path,
                "sha256": bundle_sha256,
                "size_bytes": Path(bundle_path).stat().st_size if Path(bundle_path).exists() else 0,
            },
            "sbom_path": sbom_path,
            "assembly_manifest_path": assembly_manifest_path,
            "artifact_family_summary_path": artifact_family_summary_path,
            "generator_readiness_evidence_path": generator_readiness_evidence_path,
            "restore_readiness_report_path": restore_readiness_report_path,
            "rollback_events_report_path": rollback_events_report_path,
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

        generated_files = [str(manifest_path)]
        try:
            ctx.publish("generated_files", generated_files)
            ctx.publish("release_manifest_path", str(manifest_path))
        except PluginDataExchangeError:
            pass

        diagnostics.append(
            self.emit_diagnostic(
                code="I8203",
                severity="info",
                stage=stage,
                message=f"release manifest generated: {manifest_path.name}",
                path=str(manifest_path),
            )
        )
        return self.make_result(
            diagnostics=diagnostics,
            output_data={"release_manifest_path": str(manifest_path), "generated_files": generated_files},
        )

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

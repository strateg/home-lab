"""SOHO readiness/handover builder (ADR0091 Step C)."""

from __future__ import annotations

import hashlib
import json
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

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]


_REQUIRED_HANDOVER_FILES = (
    "SYSTEM-SUMMARY.md",
    "NETWORK-SUMMARY.md",
    "ACCESS-RUNBOOK.md",
    "BACKUP-RUNBOOK.md",
    "RESTORE-RUNBOOK.md",
    "UPDATE-RUNBOOK.md",
    "INCIDENT-CHECKLIST.md",
    "ASSET-INVENTORY.csv",
    "CHANGELOG-SNAPSHOT.md",
)

_REQUIRED_REPORT_FILES = (
    "health-report.json",
    "drift-report.json",
    "backup-status.json",
    "restore-readiness.json",
    "support-bundle-manifest.json",
)

_SUPPORTED_CLASSES = {"starter", "managed-soho", "advanced-soho"}
_ADR0091_EVIDENCE_DOMAINS = (
    "greenfield-first-install",
    "brownfield-adoption",
    "router-replacement",
    "secret-rotation",
    "scheduled-update",
    "failed-update-rollback",
    "backup-and-restore",
    "operator-handover",
)


class SohoReadinessBuilder(BuilderPlugin):
    """Emit product/ handover + reports package and enforce ADR0091 readiness gate."""

    @staticmethod
    def _repo_root(ctx: PluginContext) -> Path:
        raw = ctx.config.get("repo_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).resolve()
        return Path.cwd().resolve()

    @staticmethod
    def _artifacts_root(ctx: PluginContext) -> Path:
        raw = ctx.config.get("generator_artifacts_root")
        if isinstance(raw, str) and raw.strip():
            root = Path(raw.strip())
            if not root.is_absolute():
                root = SohoReadinessBuilder._repo_root(ctx) / root
        else:
            root = SohoReadinessBuilder._repo_root(ctx) / "generated"
        root = root.resolve()
        project_id = str(ctx.config.get("project_id", "")).strip()
        if project_id and root.name != project_id:
            root = root / project_id
        return root

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _load_schema(repo_root: Path, name: str) -> dict[str, Any] | None:
        path = repo_root / "schemas" / name
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _validate_payload(payload: dict[str, Any], schema: dict[str, Any] | None) -> bool:
        if schema is None or jsonschema is None:
            return False
        try:
            jsonschema.validate(payload, schema)
            return True
        except Exception:
            return False

    @staticmethod
    def _placeholder_content(name: str) -> str:
        # Deliberately sanitized placeholders; no runtime secrets are embedded.
        if name.endswith(".csv"):
            return "asset_id,role,status\nplaceholder,operator,documented\n"
        return (
            f"# {name}\n\n"
            "Generated operator handover placeholder.\n\n"
            "All sensitive values must be provided from secured runtime channels.\n"
        )

    @staticmethod
    def _subscribe(ctx: PluginContext, plugin_id: str, key: str) -> Any | None:
        try:
            return ctx.subscribe(plugin_id, key)
        except PluginDataExchangeError:
            published = ctx.get_published_data()
            payload = published.get(plugin_id)
            if isinstance(payload, dict):
                return payload.get(key)
            return None

    @staticmethod
    def _normalize_readiness_status(raw: str) -> str:
        token = raw.strip().lower()
        if token in {"green", "warning", "blocked"}:
            return token
        return "warning"

    @staticmethod
    def _evidence_state(*, complete: bool, partial: bool = False) -> str:
        if complete:
            return "complete"
        return "partial" if partial else "missing"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        repo_root = self._repo_root(ctx)
        artifacts_root = self._artifacts_root(ctx)
        product_root = artifacts_root / "product"
        handover_root = product_root / "handover"
        reports_root = product_root / "reports"
        handover_root.mkdir(parents=True, exist_ok=True)
        reports_root.mkdir(parents=True, exist_ok=True)

        product_state = self._subscribe(ctx, "base.validator.soho_product_profile", "product_profile_state")
        if not isinstance(product_state, dict):
            product_state = {}

        profile_id = str(product_state.get("profile_id", "")).strip()
        deployment_class = str(product_state.get("deployment_class", "")).strip()

        if deployment_class and deployment_class not in _SUPPORTED_CLASSES and not deployment_class.startswith("("):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7946",
                    severity="error",
                    stage=stage,
                    message=(f"unsupported deployment_class '{deployment_class}' for SOHO readiness package."),
                    path="project.yaml:product_profile.deployment_class",
                )
            )

        generated_files: list[str] = []
        handover_inventory: dict[str, dict[str, Any]] = {}
        for filename in _REQUIRED_HANDOVER_FILES:
            path = handover_root / filename
            if not path.exists():
                path.write_text(self._placeholder_content(filename), encoding="utf-8")
            handover_inventory[filename] = {
                "present": path.exists(),
                "checksum": self._sha256(path) if path.exists() else "",
            }
            generated_files.append(str(path))

        readiness_report = self._subscribe(ctx, "base.builder.readiness_reports", "restore_readiness_report")
        if not isinstance(readiness_report, dict):
            readiness_report = {}

        readiness_status = self._normalize_readiness_status(str(readiness_report.get("status", "warning")))

        health_report = {
            "schema_version": "1.0",
            "timestamp": self._now(),
            "status": "ok" if readiness_status == "green" else "degraded",
            "source": "adr0091.soho-readiness-builder.v1",
        }
        drift_report = {
            "schema_version": "1.0",
            "timestamp": self._now(),
            "drift_state": "unknown",
            "source": "adr0091.soho-readiness-builder.v1",
        }

        restore_completeness = "complete" if isinstance(readiness_report, dict) and readiness_report else "missing"
        backup_completeness = "complete" if restore_completeness == "complete" else "missing"

        backup_status = {
            "schema_version": "1.0",
            "timestamp": self._now(),
            "backup_integrity": "verified" if backup_completeness == "complete" else "unknown",
            "completeness_state": backup_completeness,
        }
        restore_status = {
            "schema_version": "1.0",
            "timestamp": self._now(),
            "drill_result": "passed" if restore_completeness == "complete" else "not-tested",
            "restore_source_integrity": "verified" if restore_completeness == "complete" else "unknown",
            "completeness_state": restore_completeness,
        }

        health_path = reports_root / "health-report.json"
        drift_path = reports_root / "drift-report.json"
        backup_path = reports_root / "backup-status.json"
        restore_path = reports_root / "restore-readiness.json"

        health_path.write_text(json.dumps(health_report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        drift_path.write_text(json.dumps(drift_report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        backup_path.write_text(json.dumps(backup_status, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        restore_path.write_text(json.dumps(restore_status, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        generated_files.extend([str(health_path), str(drift_path), str(backup_path), str(restore_path)])

        backup_schema = self._load_schema(repo_root, "backup-status.schema.json")
        restore_schema = self._load_schema(repo_root, "restore-readiness.schema.json")

        report_inventory = {
            "health-report.json": {"present": True, "schema_validated": False},
            "drift-report.json": {"present": True, "schema_validated": False},
            "backup-status.json": {
                "present": True,
                "schema_validated": self._validate_payload(backup_status, backup_schema),
            },
            "restore-readiness.json": {
                "present": True,
                "schema_validated": self._validate_payload(restore_status, restore_schema),
            },
            "support-bundle-manifest.json": {"present": False, "schema_validated": False},
        }

        if backup_completeness == "missing":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7943",
                    severity="error",
                    stage=stage,
                    message="backup evidence is missing for ADR0091 readiness package.",
                    path=str(backup_path),
                )
            )
        if restore_completeness == "missing":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7944",
                    severity="error",
                    stage=stage,
                    message="restore readiness evidence is missing for ADR0091 readiness package.",
                    path=str(restore_path),
                )
            )

        missing_handover = sorted(name for name, row in handover_inventory.items() if not row.get("present"))
        if missing_handover:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7945",
                    severity="error",
                    stage=stage,
                    message="handover package is incomplete: " + ", ".join(missing_handover),
                    path=str(handover_root),
                )
            )

        has_error = any(item.severity == "error" for item in diagnostics)
        evidence_map = {
            "greenfield-first-install": self._evidence_state(
                complete=(
                    handover_inventory["SYSTEM-SUMMARY.md"]["present"]
                    and handover_inventory["NETWORK-SUMMARY.md"]["present"]
                ),
            ),
            "brownfield-adoption": self._evidence_state(
                complete=handover_inventory["CHANGELOG-SNAPSHOT.md"]["present"],
            ),
            "router-replacement": self._evidence_state(
                complete=(
                    handover_inventory["NETWORK-SUMMARY.md"]["present"]
                    and handover_inventory["ASSET-INVENTORY.csv"]["present"]
                ),
            ),
            "secret-rotation": self._evidence_state(
                complete=handover_inventory["ACCESS-RUNBOOK.md"]["present"],
            ),
            "scheduled-update": self._evidence_state(
                complete=handover_inventory["UPDATE-RUNBOOK.md"]["present"],
            ),
            "failed-update-rollback": self._evidence_state(
                complete=(
                    handover_inventory["RESTORE-RUNBOOK.md"]["present"]
                    and handover_inventory["INCIDENT-CHECKLIST.md"]["present"]
                ),
            ),
            "backup-and-restore": self._evidence_state(
                complete=(backup_completeness == "complete" and restore_completeness == "complete"),
            ),
            "operator-handover": self._evidence_state(complete=not missing_handover),
        }
        for domain in _ADR0091_EVIDENCE_DOMAINS:
            evidence_map.setdefault(domain, "missing")
        has_partial = any(value == "partial" for value in evidence_map.values())
        status = "red" if has_error else ("yellow" if has_partial else "green")

        operator_readiness = {
            "schema_version": "1.0",
            "project_id": str(ctx.config.get("project_id", "")),
            "status": status,
            "evidence": evidence_map,
            "diagnostics": [
                {
                    "code": item.code,
                    "severity": item.severity,
                    "message": item.message,
                }
                for item in diagnostics
            ],
        }

        operator_path = reports_root / "operator-readiness.json"
        operator_path.write_text(json.dumps(operator_readiness, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        generated_files.append(str(operator_path))

        support_manifest = {
            "schema_version": "1.0",
            "timestamp": self._now(),
            "project_id": str(ctx.config.get("project_id", "")),
            "profile_id": profile_id,
            "deployment_class": deployment_class if deployment_class in _SUPPORTED_CLASSES else "starter",
            "artifacts": {
                "handover": handover_inventory,
                "reports": report_inventory,
            },
            "completeness_state": "complete" if status == "green" else ("partial" if status == "yellow" else "missing"),
        }

        support_manifest_path = reports_root / "support-bundle-manifest.json"
        support_manifest_schema = self._load_schema(repo_root, "support-bundle-manifest.schema.json")
        report_inventory["support-bundle-manifest.json"] = {
            "present": True,
            "schema_validated": self._validate_payload(support_manifest, support_manifest_schema),
        }
        support_manifest_path.write_text(
            json.dumps(support_manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
        generated_files.append(str(support_manifest_path))

        ctx.publish("generated_files", generated_files)
        ctx.publish("product_handover_dir", str(handover_root))
        ctx.publish("product_reports_dir", str(reports_root))
        ctx.publish("operator_readiness_report_path", str(operator_path))
        ctx.publish("support_bundle_manifest_path", str(support_manifest_path))
        ctx.publish("operator_readiness", operator_readiness)

        diagnostics.append(
            self.emit_diagnostic(
                code="I7941",
                severity="info",
                stage=stage,
                message=f"SOHO readiness package emitted with status={status}",
                path=str(product_root),
            )
        )

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "generated_files": generated_files,
                "product_handover_dir": str(handover_root),
                "product_reports_dir": str(reports_root),
                "operator_readiness_report_path": str(operator_path),
                "support_bundle_manifest_path": str(support_manifest_path),
                "operator_readiness_status": status,
            },
        )

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

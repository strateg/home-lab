"""SOHO product profile validator (ADR0089/ADR0091 hardening)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore[assignment]


_SUPPORTED_PROFILE_ID = "soho.standard.v1"
_CORE_BUNDLES = {
    "bundle.edge-routing",
    "bundle.network-segmentation",
    "bundle.secrets-governance",
}
_CLASS_OVERLAYS = {
    "starter": {
        "bundle.remote-access",
        "bundle.operator-workflows",
    },
    "managed-soho": {
        "bundle.remote-access",
        "bundle.backup-restore",
        "bundle.observability",
        "bundle.operator-workflows",
        "bundle.update-management",
    },
    "advanced-soho": {
        "bundle.remote-access",
        "bundle.backup-restore",
        "bundle.observability",
        "bundle.operator-workflows",
        "bundle.update-management",
        "bundle.incident-response",
        "bundle.multi-uplink-resilience",
    },
}
_STATE_FALLBACK = "legacy"
_SOHO_PROFILE_RESOLVER_PLUGIN = "base.compiler.soho_profile_resolver"


class SohoProductProfileValidator(ValidatorJsonPlugin):
    """Validate project-level SOHO profile contract and emit migration state artifact."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        project_manifest = self._load_project_manifest(ctx)
        if project_manifest is None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7941",
                    severity="error",
                    stage=stage,
                    message="project manifest is unavailable; cannot validate SOHO product profile contract.",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics=diagnostics)

        product_profile = project_manifest.get("product_profile")
        bundle_ids = self._bundle_ids(project_manifest)

        if not isinstance(product_profile, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7941",
                    severity="warning",
                    stage=stage,
                    message="project.yaml has no product_profile; project treated as legacy migration_state.",
                    path="project.yaml:product_profile",
                )
            )
            report = self._build_state_report(
                ctx=ctx,
                project_manifest=project_manifest,
                migration_state=_STATE_FALLBACK,
                profile_id="(missing)",
                deployment_class="(missing)",
                bundle_ids=bundle_ids,
                required_bundles=set(),
                available_bundles=set(),
                diagnostics=diagnostics,
            )
            self._write_state_report(ctx=ctx, report=report)
            return self.make_result(diagnostics=diagnostics, output_data={"product_profile_state": report})

        schema_errors = self._validate_schema(product_profile, ctx=ctx)
        for message in schema_errors:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7941",
                    severity="error",
                    stage=stage,
                    message=message,
                    path="project.yaml:product_profile",
                )
            )
        if schema_errors:
            report = self._build_state_report(
                ctx=ctx,
                project_manifest=project_manifest,
                migration_state=str(product_profile.get("migration_state", _STATE_FALLBACK)),
                profile_id=str(product_profile.get("profile_id", "")),
                deployment_class=str(product_profile.get("deployment_class", "")),
                bundle_ids=bundle_ids,
                required_bundles=set(),
                available_bundles=set(),
                diagnostics=diagnostics,
            )
            self._write_state_report(ctx=ctx, report=report)
            return self.make_result(diagnostics=diagnostics, output_data={"product_profile_state": report})

        profile_id = str(product_profile.get("profile_id", "")).strip()
        deployment_class = str(product_profile.get("deployment_class", "")).strip()
        migration_state = str(product_profile.get("migration_state", _STATE_FALLBACK)).strip() or _STATE_FALLBACK

        if profile_id != _SUPPORTED_PROFILE_ID:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7941",
                    severity="error",
                    stage=stage,
                    message=f"unsupported product_profile.profile_id '{profile_id}'; expected '{_SUPPORTED_PROFILE_ID}'.",
                    path="project.yaml:product_profile.profile_id",
                )
            )

        required_bundles, available_bundles, missing_contract_bundles = self._resolve_required_bundles(
            ctx=ctx,
            profile_id=profile_id,
            deployment_class=deployment_class,
        )
        if missing_contract_bundles:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7942",
                    severity="error",
                    stage=stage,
                    message=(
                        "required bundles are not defined in canonical product-bundle catalog: "
                        + ", ".join(sorted(missing_contract_bundles))
                    ),
                    path="topology/product-bundles",
                )
            )
        if not required_bundles:
            required_bundles = set(_CORE_BUNDLES)
            required_bundles.update(_CLASS_OVERLAYS.get(deployment_class, set()))
        missing_bundles = sorted(required_bundles - bundle_ids)

        if missing_bundles:
            if migration_state == "migrated-hard":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7942",
                        severity="error",
                        stage=stage,
                        message=(
                            "migrated-hard project is missing required product bundles: " + ", ".join(missing_bundles)
                        ),
                        path="project.yaml:product_bundles",
                    )
                )
            else:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7942",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"{migration_state} project is missing required product bundles: "
                            + ", ".join(missing_bundles)
                        ),
                        path="project.yaml:product_bundles",
                    )
                )

        previous_state = str(product_profile.get("previous_migration_state", "")).strip()
        if previous_state:
            transition_error = self._validate_transition(
                ctx=ctx, previous_state=previous_state, current_state=migration_state
            )
            if transition_error:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7947",
                        severity="error",
                        stage=stage,
                        message=transition_error,
                        path="project.yaml:product_profile.previous_migration_state",
                    )
                )

        report = self._build_state_report(
            ctx=ctx,
            project_manifest=project_manifest,
            migration_state=migration_state,
            profile_id=profile_id,
            deployment_class=deployment_class,
            bundle_ids=bundle_ids,
            required_bundles=required_bundles,
            available_bundles=available_bundles,
            diagnostics=diagnostics,
        )
        self._write_state_report(ctx=ctx, report=report)
        return self.make_result(diagnostics=diagnostics, output_data={"product_profile_state": report})

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    def _validate_schema(self, payload: dict[str, Any], *, ctx: PluginContext) -> list[str]:
        errors: list[str] = []
        schema_path = self._resolve_repo_root(ctx) / "schemas" / "product-profile.schema.json"
        if not schema_path.exists() or jsonschema is None:
            required = (
                "profile_id",
                "deployment_class",
                "site_class",
                "user_band",
                "operator_mode",
                "release_channel",
                "migration_state",
            )
            for key in required:
                value = payload.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"product_profile.{key} must be a non-empty string.")
            return errors

        try:
            schema_payload = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(payload, schema_payload)
        except Exception as exc:  # pragma: no cover - exercised in integration
            errors.append(f"product_profile schema validation failed: {exc}")
        return errors

    def _validate_transition(self, *, ctx: PluginContext, previous_state: str, current_state: str) -> str | None:
        policy_path = self._resolve_policy_path(ctx)
        if policy_path is None:
            return None
        try:
            policy_payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return None
        transitions = policy_payload.get("allowed_transitions")
        if not isinstance(transitions, dict):
            return None
        allowed = transitions.get(previous_state)
        if not isinstance(allowed, list):
            return f"unknown previous_migration_state '{previous_state}'."
        if current_state not in {str(item) for item in allowed}:
            return f"invalid migration_state transition: {previous_state} -> {current_state}."
        return None

    def _resolve_required_bundles(
        self,
        *,
        ctx: PluginContext,
        profile_id: str,
        deployment_class: str,
    ) -> tuple[set[str], set[str], set[str]]:
        try:
            required_payload = ctx.subscribe(_SOHO_PROFILE_RESOLVER_PLUGIN, "effective_product_bundles")
            available_payload = ctx.subscribe(_SOHO_PROFILE_RESOLVER_PLUGIN, "available_product_bundles")
            resolution_payload = ctx.subscribe(_SOHO_PROFILE_RESOLVER_PLUGIN, "soho_profile_resolution")
        except PluginDataExchangeError:
            required_payload = None
            available_payload = None
            resolution_payload = None

        required: set[str] = set()
        available: set[str] = set()
        missing_catalog: set[str] = set()
        if isinstance(required_payload, list):
            required = {str(item).strip() for item in required_payload if isinstance(item, str) and str(item).strip()}
        if isinstance(available_payload, list):
            available = {
                str(item).strip() for item in available_payload if isinstance(item, str) and str(item).strip()
            }
        if isinstance(resolution_payload, dict):
            missing_raw = resolution_payload.get("missing_bundle_definitions", [])
            if isinstance(missing_raw, list):
                missing_catalog = {
                    str(item).strip() for item in missing_raw if isinstance(item, str) and str(item).strip()
                }

        if required:
            return required, available, missing_catalog

        # Fallback for direct/integration execution without registry bus.
        required = set(_CORE_BUNDLES)
        required.update(_CLASS_OVERLAYS.get(deployment_class, set()))
        return required, available, missing_catalog

    @staticmethod
    def _bundle_ids(project_manifest: dict[str, Any]) -> set[str]:
        raw = project_manifest.get("product_bundles", [])
        if not isinstance(raw, list):
            return set()
        return {str(item).strip() for item in raw if isinstance(item, str) and str(item).strip()}

    @staticmethod
    def _load_project_manifest(ctx: PluginContext) -> dict[str, Any] | None:
        path_raw = ctx.config.get("project_manifest_path")
        if not isinstance(path_raw, str) or not path_raw.strip():
            return None
        path = Path(path_raw.strip())
        if not path.is_absolute():
            repo_root = SohoProductProfileValidator._resolve_repo_root(ctx)
            path = repo_root / path
        if not path.exists():
            return None
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _resolve_repo_root(ctx: PluginContext) -> Path:
        repo_root_raw = ctx.config.get("repo_root")
        if isinstance(repo_root_raw, str) and repo_root_raw.strip():
            return Path(repo_root_raw.strip()).resolve()
        return Path.cwd().resolve()

    def _resolve_policy_path(self, ctx: PluginContext) -> Path | None:
        policy_raw = ctx.config.get("soho_migration_policy_path")
        if not isinstance(policy_raw, str) or not policy_raw.strip():
            return None
        candidate = Path(policy_raw.strip())
        if not candidate.is_absolute():
            candidate = self._resolve_repo_root(ctx) / candidate
        candidate = candidate.resolve()
        if not candidate.exists():
            return None
        return candidate

    def _build_state_report(
        self,
        *,
        ctx: PluginContext,
        project_manifest: dict[str, Any],
        migration_state: str,
        profile_id: str,
        deployment_class: str,
        bundle_ids: set[str],
        required_bundles: set[str],
        available_bundles: set[str],
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any]:
        project_id = str(project_manifest.get("project", ctx.config.get("project_id", "unknown"))).strip() or "unknown"
        has_error = any(item.severity == "error" for item in diagnostics)
        has_warning = any(item.severity == "warning" for item in diagnostics)
        status = "red" if has_error else ("yellow" if has_warning else "green")
        return {
            "schema_version": "1.0",
            "project_id": project_id,
            "profile_id": profile_id,
            "deployment_class": deployment_class,
            "migration_state": migration_state,
            "status": status,
            "bundles": sorted(bundle_ids),
            "required_bundles": sorted(required_bundles),
            "available_bundles": sorted(available_bundles),
            "diagnostics": [
                {
                    "code": item.code,
                    "severity": item.severity,
                    "message": item.message,
                }
                for item in diagnostics
            ],
        }

    @staticmethod
    def _write_state_report(*, ctx: PluginContext, report: dict[str, Any]) -> None:
        output_dir = Path(ctx.output_dir).resolve() if ctx.output_dir else Path.cwd().resolve() / "build"
        diagnostics_dir = output_dir / "diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        path = diagnostics_dir / "product-profile-state.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")

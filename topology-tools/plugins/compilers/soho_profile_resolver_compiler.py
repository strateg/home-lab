"""SOHO product profile resolver compiler plugin (ADR0089 Step A)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage
from yaml_loader import load_yaml_file


class SohoProfileResolverCompiler(CompilerPlugin):
    """Resolve required product bundles from canonical profile and bundle catalogs."""

    _STATE_FALLBACK = "legacy"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        project_manifest = self._load_project_manifest(ctx)
        available_bundles = self._load_available_bundles(ctx=ctx, diagnostics=diagnostics, stage=stage)

        product_profile = project_manifest.get("product_profile") if isinstance(project_manifest, dict) else None
        if not isinstance(product_profile, dict):
            resolution = {
                "profile_present": False,
                "migration_state": self._STATE_FALLBACK,
                "profile_id": "",
                "deployment_class": "",
                "required_bundles": [],
                "available_bundles": sorted(available_bundles),
                "catalog_status": "ok",
            }
            self.publish_if_possible(ctx, "soho_profile_resolution", resolution)
            self.publish_if_possible(ctx, "effective_product_bundles", [])
            self.publish_if_possible(ctx, "available_product_bundles", sorted(available_bundles))
            return self.make_result(diagnostics=diagnostics, output_data=resolution)

        profile_id = str(product_profile.get("profile_id", "")).strip()
        deployment_class = str(product_profile.get("deployment_class", "")).strip()
        migration_state = str(product_profile.get("migration_state", self._STATE_FALLBACK)).strip() or self._STATE_FALLBACK

        required_bundles: list[str] = []
        missing_from_catalog: list[str] = []
        catalog_status = "ok"

        if profile_id:
            payload = self._load_profile_contract(
                ctx=ctx,
                profile_id=profile_id,
                diagnostics=diagnostics,
                stage=stage,
            )
            if isinstance(payload, dict):
                required_bundles = self._resolve_required_bundles(
                    payload=payload,
                    deployment_class=deployment_class,
                    diagnostics=diagnostics,
                    stage=stage,
                )
                missing_from_catalog = sorted(bundle for bundle in required_bundles if bundle not in available_bundles)
                if missing_from_catalog:
                    catalog_status = "bundle-catalog-missing-entries"
            else:
                catalog_status = "profile-not-found"

        resolution = {
            "profile_present": True,
            "migration_state": migration_state,
            "profile_id": profile_id,
            "deployment_class": deployment_class,
            "required_bundles": sorted(set(required_bundles)),
            "missing_bundle_definitions": missing_from_catalog,
            "available_bundles": sorted(available_bundles),
            "catalog_status": catalog_status,
        }
        self.publish_if_possible(ctx, "soho_profile_resolution", resolution)
        self.publish_if_possible(ctx, "effective_product_bundles", resolution["required_bundles"])
        self.publish_if_possible(ctx, "available_product_bundles", resolution["available_bundles"])

        return self.make_result(diagnostics=diagnostics, output_data=resolution)

    @staticmethod
    def publish_if_possible(ctx: PluginContext, key: str, value: Any) -> bool:
        try:
            ctx.publish(key, value)
            return True
        except Exception:
            return False

    def _load_project_manifest(self, ctx: PluginContext) -> dict[str, Any]:
        path_raw = ctx.config.get("project_manifest_path")
        if not isinstance(path_raw, str) or not path_raw.strip():
            return {}
        path = Path(path_raw)
        if not path.is_absolute():
            path = self._repo_root(ctx) / path
        if not path.exists():
            return {}
        payload = load_yaml_file(path) or {}
        return payload if isinstance(payload, dict) else {}

    def _profile_path(self, ctx: PluginContext, profile_id: str) -> Path:
        root = self._product_profiles_root(ctx)
        return root / f"{profile_id}.yaml"

    def _load_profile_contract(
        self,
        *,
        ctx: PluginContext,
        profile_id: str,
        diagnostics: list[PluginDiagnostic],
        stage: Stage,
    ) -> dict[str, Any] | None:
        path = self._profile_path(ctx, profile_id)
        if not path.exists():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7941",
                    severity="error",
                    stage=stage,
                    message=f"SOHO profile contract file not found for profile_id '{profile_id}'.",
                    path=str(path),
                )
            )
            return None
        payload = load_yaml_file(path) or {}
        if not isinstance(payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7941",
                    severity="error",
                    stage=stage,
                    message=f"SOHO profile contract '{profile_id}' must be a YAML mapping/object.",
                    path=str(path),
                )
            )
            return None
        return payload

    def _resolve_required_bundles(
        self,
        *,
        payload: dict[str, Any],
        deployment_class: str,
        diagnostics: list[PluginDiagnostic],
        stage: Stage,
    ) -> list[str]:
        core = payload.get("core_required_bundles", [])
        classes = payload.get("deployment_classes", {})

        core_items = [item.strip() for item in core if isinstance(item, str) and item.strip()] if isinstance(core, list) else []
        class_items: list[str] = []
        class_payload = classes.get(deployment_class) if isinstance(classes, dict) else None
        if isinstance(class_payload, dict):
            raw = class_payload.get("required_bundles", [])
            if isinstance(raw, list):
                class_items = [item.strip() for item in raw if isinstance(item, str) and item.strip()]
        elif deployment_class:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7941",
                    severity="error",
                    stage=stage,
                    message=(
                        f"SOHO deployment_class '{deployment_class}' is not defined in canonical profile contract."
                    ),
                    path=f"profile:deployment_classes.{deployment_class}",
                )
            )
        return sorted(set(core_items + class_items))

    def _load_available_bundles(
        self,
        *,
        ctx: PluginContext,
        diagnostics: list[PluginDiagnostic],
        stage: Stage,
    ) -> set[str]:
        bundles_root = self._product_bundles_root(ctx)
        if not bundles_root.exists() or not bundles_root.is_dir():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7942",
                    severity="error",
                    stage=stage,
                    message=f"SOHO product bundle catalog directory is missing: {bundles_root}",
                    path=str(bundles_root),
                )
            )
            return set()

        result: set[str] = set()
        for path in sorted(bundles_root.glob("*.yaml")):
            payload = load_yaml_file(path) or {}
            if not isinstance(payload, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7942",
                        severity="error",
                        stage=stage,
                        message=f"SOHO bundle contract must be a YAML mapping/object: {path.name}",
                        path=str(path),
                    )
                )
                continue
            bundle_id = payload.get("bundle_id")
            if not isinstance(bundle_id, str) or not bundle_id.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7942",
                        severity="error",
                        stage=stage,
                        message=f"SOHO bundle contract missing non-empty bundle_id: {path.name}",
                        path=str(path),
                    )
                )
                continue
            result.add(bundle_id.strip())
        return result

    @staticmethod
    def _repo_root(ctx: PluginContext) -> Path:
        raw = ctx.config.get("repo_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).resolve()
        return Path.cwd().resolve()

    def _product_profiles_root(self, ctx: PluginContext) -> Path:
        raw = ctx.config.get("product_profiles_root")
        if isinstance(raw, str) and raw.strip():
            root = Path(raw.strip())
            if not root.is_absolute():
                root = self._repo_root(ctx) / root
            return root.resolve()
        return (self._repo_root(ctx) / "topology" / "product-profiles").resolve()

    def _product_bundles_root(self, ctx: PluginContext) -> Path:
        raw = ctx.config.get("product_bundles_root")
        if isinstance(raw, str) and raw.strip():
            root = Path(raw.strip())
            if not root.is_absolute():
                root = self._repo_root(ctx) / root
            return root.resolve()
        return (self._repo_root(ctx) / "topology" / "product-bundles").resolve()

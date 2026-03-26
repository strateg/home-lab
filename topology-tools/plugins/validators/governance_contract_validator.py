"""Governance contract validator for v5 topology root manifest."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kernel.plugin_base import PluginContext, PluginDataExchangeError, PluginResult, Stage, ValidatorYamlPlugin


class GovernanceContractValidator(ValidatorYamlPlugin):
    """Validate core v5 topology manifest governance fields and contracts."""

    _REQUIRED_FRAMEWORK_KEYS = (
        "class_modules_root",
        "object_modules_root",
        "model_lock",
        "layer_contract",
        "capability_catalog",
        "capability_packs",
    )
    _ALLOWED_STATUSES = {"migration", "active", "deprecated"}
    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        raw = ctx.raw_yaml if isinstance(ctx.raw_yaml, dict) else {}

        version = raw.get("version")
        if not isinstance(version, str) or not version:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7813",
                    severity="warning",
                    stage=stage,
                    message="topology version is not set; explicit 5.x version is required.",
                    path="topology:version",
                )
            )
        if not isinstance(version, str) or not version.startswith("5."):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7801",
                    severity="error",
                    stage=stage,
                    message="topology version must be a non-empty string starting with '5.'.",
                    path="topology:version",
                )
            )

        model = raw.get("model")
        if model != "class-object-instance":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7802",
                    severity="error",
                    stage=stage,
                    message="topology model must be 'class-object-instance'.",
                    path="topology:model",
                )
            )

        framework = raw.get("framework")
        if not isinstance(framework, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7803",
                    severity="error",
                    stage=stage,
                    message="framework section must be an object with required paths.",
                    path="topology:framework",
                )
            )
        else:
            for key in self._REQUIRED_FRAMEWORK_KEYS:
                value = framework.get(key)
                if not isinstance(value, str) or not value.strip():
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7803",
                            severity="error",
                            stage=stage,
                            message=f"framework.{key} must be a non-empty string path.",
                            path=f"topology:framework.{key}",
                        )
                    )

        project = raw.get("project")
        if not isinstance(project, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7804",
                    severity="error",
                    stage=stage,
                    message="project section must be an object with active/projects_root.",
                    path="topology:project",
                )
            )
        else:
            active = project.get("active")
            projects_root = project.get("projects_root")
            if not isinstance(active, str) or not active.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7804",
                        severity="error",
                        stage=stage,
                        message="project.active must be a non-empty string.",
                        path="topology:project.active",
                    )
                )
            if not isinstance(projects_root, str) or not projects_root.strip():
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7804",
                        severity="error",
                        stage=stage,
                        message="project.projects_root must be a non-empty string.",
                        path="topology:project.projects_root",
                    )
                )

        meta = raw.get("meta")
        if isinstance(meta, dict):
            self._validate_meta(meta=meta, stage=stage, diagnostics=diagnostics, project=project, version=version)
            self._validate_default_refs(meta=meta, ctx=ctx, stage=stage, diagnostics=diagnostics)

        return self.make_result(diagnostics)

    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

    def _validate_meta(
        self,
        *,
        meta: dict[str, Any],
        project: Any,
        version: Any,
        stage: Stage,
        diagnostics: list[Any],
    ) -> None:
        instance = meta.get("instance")
        status = meta.get("status")

        if not isinstance(instance, str) or not instance.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7805",
                    severity="error",
                    stage=stage,
                    message="meta.instance must be a non-empty string.",
                    path="topology:meta.instance",
                )
            )

        if isinstance(project, dict):
            active = project.get("active")
            if isinstance(active, str) and active and isinstance(instance, str) and instance and active != instance:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7806",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"meta.instance '{instance}' differs from project.active '{active}'. "
                            "Prefer aligned values for deterministic lane selection."
                        ),
                        path="topology:meta.instance",
                    )
                )

        if not isinstance(status, str) or status not in self._ALLOWED_STATUSES:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7807",
                    severity="warning",
                    stage=stage,
                    message=f"meta.status should be one of {sorted(self._ALLOWED_STATUSES)}.",
                    path="topology:meta.status",
                )
            )

        metadata = meta.get("metadata")
        if isinstance(metadata, dict):
            self._validate_metadata(
                metadata=metadata,
                version=version,
                stage=stage,
                diagnostics=diagnostics,
            )

    def _validate_metadata(
        self,
        *,
        metadata: dict[str, Any],
        version: Any,
        stage: Stage,
        diagnostics: list[Any],
    ) -> None:
        created = metadata.get("created")
        last_updated = metadata.get("last_updated")
        if isinstance(created, str) and isinstance(last_updated, str):
            try:
                created_dt = datetime.strptime(created, "%Y-%m-%d").date()
                updated_dt = datetime.strptime(last_updated, "%Y-%m-%d").date()
                if updated_dt < created_dt:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7808",
                            severity="error",
                            stage=stage,
                            message=(
                                f"meta.metadata.last_updated '{last_updated}' is earlier than " f"created '{created}'."
                            ),
                            path="topology:meta.metadata.last_updated",
                        )
                    )
            except ValueError:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7809",
                        severity="warning",
                        stage=stage,
                        message="meta.metadata.created/last_updated should use YYYY-MM-DD format.",
                        path="topology:meta.metadata",
                    )
                )

        changelog = metadata.get("changelog")
        if isinstance(version, str) and version and isinstance(changelog, list) and changelog:
            has_version = any(isinstance(entry, dict) and entry.get("version") == version for entry in changelog)
            if not has_version:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7810",
                        severity="warning",
                        stage=stage,
                        message=f"meta.metadata.changelog does not contain current version '{version}'.",
                        path="topology:meta.metadata.changelog",
                    )
                )

    def _validate_default_refs(
        self,
        *,
        meta: dict[str, Any],
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[Any],
    ) -> None:
        defaults = meta.get("defaults")
        refs = defaults.get("refs") if isinstance(defaults, dict) else None
        if not isinstance(refs, dict):
            return

        sec_ref = refs.get("security_policy_ref")
        mgr_ref = refs.get("network_manager_device_ref")
        if not isinstance(sec_ref, str) and not isinstance(mgr_ref, str):
            return

        rows: list[dict[str, Any]] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
            if isinstance(rows_payload, list):
                rows = [item for item in rows_payload if isinstance(item, dict)]
        except PluginDataExchangeError:
            rows = []

        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        if isinstance(sec_ref, str) and sec_ref:
            sec_row = row_by_id.get(sec_ref)
            if not isinstance(sec_row, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7811",
                        severity="error",
                        stage=stage,
                        message=f"meta.defaults.refs.security_policy_ref '{sec_ref}' does not reference a known instance.",
                        path="topology:meta.defaults.refs.security_policy_ref",
                    )
                )

        if isinstance(mgr_ref, str) and mgr_ref:
            mgr_row = row_by_id.get(mgr_ref)
            if not isinstance(mgr_row, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7812",
                        severity="error",
                        stage=stage,
                        message=(
                            f"meta.defaults.refs.network_manager_device_ref '{mgr_ref}' "
                            "does not reference a known instance."
                        ),
                        path="topology:meta.defaults.refs.network_manager_device_ref",
                    )
                )
            elif mgr_row.get("layer") != "L1":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7812",
                        severity="error",
                        stage=stage,
                        message=(
                            f"meta.defaults.refs.network_manager_device_ref '{mgr_ref}' must target layer L1, "
                            f"got '{mgr_row.get('layer')}'."
                        ),
                        path="topology:meta.defaults.refs.network_manager_device_ref",
                    )
                )
            elif not self._is_network_manager_row(ctx=ctx, row=mgr_row):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7812",
                        severity="error",
                        stage=stage,
                        message=(
                            f"meta.defaults.refs.network_manager_device_ref '{mgr_ref}' "
                            "must reference a network-class device."
                        ),
                        path="topology:meta.defaults.refs.network_manager_device_ref",
                    )
                )

    @staticmethod
    def _looks_like_network_class(class_ref: str) -> bool:
        normalized = class_ref.strip().lower()
        if not normalized:
            return False
        if normalized.startswith("class.network.") or normalized.startswith("class.router"):
            return True
        return ".router" in normalized or ".switch" in normalized

    def _is_network_manager_row(self, *, ctx: PluginContext, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and self._looks_like_network_class(class_ref):
            return True

        if isinstance(class_ref, str):
            class_payload = ctx.classes.get(class_ref) if isinstance(ctx.classes, dict) else None
            if isinstance(class_payload, dict):
                for key in ("required_capabilities", "optional_capabilities"):
                    capabilities = class_payload.get(key)
                    if not isinstance(capabilities, list):
                        continue
                    for capability in capabilities:
                        if isinstance(capability, str) and capability.startswith("cap.net."):
                            return True

        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            capabilities = extensions.get("capabilities")
            if isinstance(capabilities, list):
                for capability in capabilities:
                    if isinstance(capability, str) and capability.startswith("cap.net."):
                        return True
        return False

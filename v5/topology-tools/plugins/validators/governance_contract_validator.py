"""Governance contract validator for v5 topology root manifest."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorYamlPlugin


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

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        raw = ctx.raw_yaml if isinstance(ctx.raw_yaml, dict) else {}

        version = raw.get("version")
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
            self._validate_meta(meta=meta, stage=stage, diagnostics=diagnostics, project=project)

        return self.make_result(diagnostics)

    def _validate_meta(
        self,
        *,
        meta: dict[str, Any],
        project: Any,
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

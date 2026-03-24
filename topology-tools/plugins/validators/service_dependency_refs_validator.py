"""Service dependency and data-asset reference validator."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class ServiceDependencyRefsValidator(ValidatorJsonPlugin):
    """Validate service dependency refs and data asset refs."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _SERVICE_PREFIX = "class.service."

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7848",
                    severity="error",
                    stage=stage,
                    message=f"service_dependency_refs validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        row_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                row_by_id[row_id] = row

        for row in rows:
            class_ref = row.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref.startswith(self._SERVICE_PREFIX):
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = row.get("extensions")
            if not isinstance(extensions, dict):
                continue

            data_asset_refs = extensions.get("data_asset_refs")
            if isinstance(data_asset_refs, list):
                for idx, data_asset_ref in enumerate(data_asset_refs):
                    if not isinstance(data_asset_ref, str) or not data_asset_ref:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7849",
                                severity="error",
                                stage=stage,
                                message="data_asset_refs entries must be non-empty strings.",
                                path=f"{row_prefix}.data_asset_refs[{idx}]",
                            )
                        )
                        continue
                    target = row_by_id.get(data_asset_ref)
                    if not isinstance(target, dict) or target.get("class_ref") != "class.storage.data_asset":
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7849",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Service '{row_id}' data_asset_ref '{data_asset_ref}' must reference "
                                    "class.storage.data_asset instance."
                                ),
                                path=f"{row_prefix}.data_asset_refs[{idx}]",
                            )
                        )

            dependencies = extensions.get("dependencies")
            if isinstance(dependencies, list):
                for idx, dependency in enumerate(dependencies):
                    if not isinstance(dependency, dict):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7850",
                                severity="error",
                                stage=stage,
                                message="dependencies entries must be objects.",
                                path=f"{row_prefix}.dependencies[{idx}]",
                            )
                        )
                        continue
                    dep_ref = dependency.get("service_ref")
                    if not isinstance(dep_ref, str) or not dep_ref:
                        continue
                    target = row_by_id.get(dep_ref)
                    target_class = target.get("class_ref") if isinstance(target, dict) else None
                    if not isinstance(target_class, str) or not target_class.startswith(self._SERVICE_PREFIX):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7850",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Service '{row_id}' dependency service_ref '{dep_ref}' must reference "
                                    "another service instance."
                                ),
                                path=f"{row_prefix}.dependencies[{idx}].service_ref",
                            )
                        )

        return self.make_result(diagnostics)

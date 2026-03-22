"""Certificate reference validator."""

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


class CertificateRefsValidator(ValidatorJsonPlugin):
    """Validate certificate rows that bind to services."""

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
                    code="E7857",
                    severity="error",
                    stage=stage,
                    message=f"certificate_refs validator requires normalized rows: {exc}",
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
            if not self._is_certificate_row(row):
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = row.get("extensions")
            if not isinstance(extensions, dict):
                continue

            self._validate_service_ref(
                row_id=row_id,
                value=extensions.get("service_ref"),
                row_by_id=row_by_id,
                stage=stage,
                path=f"{row_prefix}.service_ref",
                diagnostics=diagnostics,
            )

            used_by = extensions.get("used_by")
            if used_by is None:
                continue
            if not isinstance(used_by, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7857",
                        severity="error",
                        stage=stage,
                        message=f"Certificate '{row_id}' used_by must be a list when set.",
                        path=f"{row_prefix}.used_by",
                    )
                )
                continue

            for idx, binding in enumerate(used_by):
                if not isinstance(binding, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7857",
                            severity="error",
                            stage=stage,
                            message=f"Certificate '{row_id}' used_by entries must be objects.",
                            path=f"{row_prefix}.used_by[{idx}]",
                        )
                    )
                    continue
                self._validate_service_ref(
                    row_id=row_id,
                    value=binding.get("service_ref"),
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.used_by[{idx}].service_ref",
                    diagnostics=diagnostics,
                )

        return self.make_result(diagnostics)

    def _validate_service_ref(
        self,
        *,
        row_id: Any,
        value: Any,
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        path: str,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        if value is None:
            return
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7857",
                    severity="error",
                    stage=stage,
                    message=f"Certificate '{row_id}' service_ref must be a non-empty string when set.",
                    path=path,
                )
            )
            return
        target = row_by_id.get(value)
        target_class = target.get("class_ref") if isinstance(target, dict) else None
        if not isinstance(target_class, str) or not target_class.startswith(self._SERVICE_PREFIX):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7857",
                    severity="error",
                    stage=stage,
                    message=f"Certificate '{row_id}' service_ref '{value}' must reference a service instance.",
                    path=path,
                )
            )

    def _is_certificate_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and "certificate" in class_ref:
            return True
        group = row.get("group")
        return isinstance(group, str) and "certificate" in group

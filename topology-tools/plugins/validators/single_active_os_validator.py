"""Single-active-OS validator for device rows."""

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


class SingleActiveOsValidator(ValidatorJsonPlugin):
    """Enforce that each device row links to at most one active OS instance."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7818",
                    severity="error",
                    stage=stage,
                    message=f"single_active_os validator requires normalized rows: {exc}",
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
            if class_ref in ("class.os", "class.firmware"):
                continue

            os_refs = row.get("os_refs")
            if not isinstance(os_refs, list) or len(os_refs) < 2:
                continue

            active_os_refs: list[str] = []
            for os_ref in os_refs:
                if not isinstance(os_ref, str) or not os_ref:
                    continue
                os_row = row_by_id.get(os_ref)
                if not isinstance(os_row, dict):
                    continue
                if os_row.get("class_ref") != "class.os":
                    continue
                status = os_row.get("status")
                if isinstance(status, str) and status.strip().lower() == "active":
                    active_os_refs.append(os_ref)

            if len(active_os_refs) > 1:
                row_id = row.get("instance")
                group = row.get("group")
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7817",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device instance '{row_id}' has multiple active OS refs: {sorted(active_os_refs)}. "
                            "Only one active OS is allowed per device."
                        ),
                        path=f"instance:{group}:{row_id}.os_refs",
                    )
                )

        return self.make_result(diagnostics)

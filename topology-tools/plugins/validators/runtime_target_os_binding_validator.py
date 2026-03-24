"""Runtime target OS binding validator."""

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


class RuntimeTargetOsBindingValidator(ValidatorJsonPlugin):
    """Warn when service runtime device targets do not expose OS bindings."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _DEVICE_RUNTIME_TYPES = {"docker", "baremetal"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7825",
                    severity="error",
                    stage=stage,
                    message=f"runtime_target_os_binding validator requires normalized rows: {exc}",
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
            runtime = row.get("runtime")
            if not isinstance(runtime, dict):
                continue
            runtime_type = runtime.get("type")
            if runtime_type not in self._DEVICE_RUNTIME_TYPES:
                continue
            target_ref = runtime.get("target_ref")
            if not isinstance(target_ref, str) or not target_ref:
                continue
            target_row = row_by_id.get(target_ref)
            if not isinstance(target_row, dict):
                continue
            os_refs = target_row.get("os_refs")
            if isinstance(os_refs, list) and any(isinstance(item, str) and item for item in os_refs):
                continue

            service_id = row.get("instance")
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7826",
                    severity="warning",
                    stage=stage,
                    message=(
                        f"Service '{service_id}' runtime target '{target_ref}' has no OS bindings (os_refs). "
                        "Runtime governance checks may be incomplete."
                    ),
                    path=f"instance:{row.get('group')}:{service_id}.runtime.target_ref",
                )
            )

        return self.make_result(diagnostics)

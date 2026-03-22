"""Network MTU consistency validator."""

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


class NetworkMtuConsistencyValidator(ValidatorJsonPlugin):
    """Validate jumbo_frames and MTU consistency for VLAN rows."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7840",
                    severity="error",
                    stage=stage,
                    message=f"network_mtu_consistency validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        for row in rows:
            if row.get("class_ref") != "class.network.vlan":
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"

            mtu = self._resolve_field(ctx=ctx, row=row, key="mtu")
            jumbo_frames = self._resolve_field(ctx=ctx, row=row, key="jumbo_frames")
            if not isinstance(jumbo_frames, bool) or not jumbo_frames:
                continue
            if isinstance(mtu, int) and mtu <= 1500:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7840",
                        severity="error",
                        stage=stage,
                        message=f"Network '{row_id}': jumbo_frames=true requires mtu > 1500, got {mtu}.",
                        path=f"{row_prefix}.mtu",
                    )
                )

        return self.make_result(diagnostics)

    @staticmethod
    def _resolve_field(*, ctx: PluginContext, row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict) and key in extensions:
            return extensions.get(key)
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        if isinstance(properties, dict):
            return properties.get(key)
        return None

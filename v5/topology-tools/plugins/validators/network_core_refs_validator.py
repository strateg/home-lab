"""Core network reference validator for VLAN/bridge instance rows."""

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


class NetworkCoreRefsValidator(ValidatorJsonPlugin):
    """Validate foundational network refs (bridge/trust-zone/manager/host)."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7837",
                    severity="error",
                    stage=stage,
                    message=f"network_core_refs validator requires normalized rows: {exc}",
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
            if class_ref == "class.network.vlan":
                self._validate_vlan_refs(ctx=ctx, row=row, row_by_id=row_by_id, stage=stage, diagnostics=diagnostics)
            elif class_ref == "class.network.bridge":
                self._validate_bridge_refs(ctx=ctx, row=row, row_by_id=row_by_id, stage=stage, diagnostics=diagnostics)

        return self.make_result(diagnostics)

    def _validate_vlan_refs(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"

        self._validate_ref(
            ctx=ctx,
            row=row,
            row_by_id=row_by_id,
            field="bridge_ref",
            expected_class="class.network.bridge",
            expected_layer="L2",
            code="E7833",
            stage=stage,
            diagnostics=diagnostics,
            path=f"{row_prefix}.bridge_ref",
        )
        self._validate_ref(
            ctx=ctx,
            row=row,
            row_by_id=row_by_id,
            field="trust_zone_ref",
            expected_class="class.network.trust_zone",
            expected_layer="L2",
            code="E7834",
            stage=stage,
            diagnostics=diagnostics,
            path=f"{row_prefix}.trust_zone_ref",
        )
        self._validate_ref(
            ctx=ctx,
            row=row,
            row_by_id=row_by_id,
            field="managed_by_ref",
            expected_class="class.router",
            expected_layer="L1",
            code="E7835",
            stage=stage,
            diagnostics=diagnostics,
            path=f"{row_prefix}.managed_by_ref",
        )

    def _validate_bridge_refs(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"

        host_ref = self._resolve_field(ctx=ctx, row=row, key="host_ref")
        if host_ref is None:
            return
        if not isinstance(host_ref, str) or not host_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7836",
                    severity="error",
                    stage=stage,
                    message="'host_ref' must be a non-empty instance id string when set.",
                    path=f"{row_prefix}.host_ref",
                )
            )
            return
        target = row_by_id.get(host_ref)
        if not isinstance(target, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7836",
                    severity="error",
                    stage=stage,
                    message=f"Bridge host_ref '{host_ref}' does not reference a known instance.",
                    path=f"{row_prefix}.host_ref",
                )
            )
            return
        target_layer = target.get("layer")
        if target_layer != "L1":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7836",
                    severity="error",
                    stage=stage,
                    message=f"Bridge host_ref '{host_ref}' must target layer L1, got '{target_layer}'.",
                    path=f"{row_prefix}.host_ref",
                )
            )

    def _validate_ref(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        field: str,
        expected_class: str,
        expected_layer: str,
        code: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        path: str,
    ) -> None:
        value = self._resolve_field(ctx=ctx, row=row, key=field)
        if value is None:
            return
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field}' must be a non-empty instance id string when set.",
                    path=path,
                )
            )
            return

        target = row_by_id.get(value)
        if not isinstance(target, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field}' references unknown instance '{value}'.",
                    path=path,
                )
            )
            return
        target_class = target.get("class_ref")
        target_layer = target.get("layer")
        if target_class != expected_class or target_layer != expected_layer:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=(
                        f"'{field}' target '{value}' must reference {expected_class} on layer {expected_layer}; "
                        f"got class '{target_class}' on layer '{target_layer}'."
                    ),
                    path=path,
                )
            )

    def _resolve_field(self, *, ctx: PluginContext, row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict) and key in extensions:
            return extensions.get(key)
        if key in row:
            return row.get(key)
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        if isinstance(properties, dict):
            return properties.get(key)
        return None

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
    _NETWORK_CLASS_EXCLUSIONS = {
        "class.network.bridge",
        "class.network.trust_zone",
        "class.network.firewall_policy",
        "class.network.firewall_rule",
        "class.network.data_link",
        "class.network.physical_link",
        "class.network.qos",
        "class.network.security_matrix",  # ADR-0110: managed_by_ref may be router OR hypervisor
    }

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

        enforcer_resolution: dict[str, Any] | None = None
        enforcer_resolution_error: str | None = None
        for row in rows:
            class_ref = row.get("class_ref")
            if self._is_network_row(row):
                self._validate_vlan_refs(ctx=ctx, row=row, row_by_id=row_by_id, stage=stage, diagnostics=diagnostics)
            elif class_ref == "class.network.security_matrix":
                if enforcer_resolution is None and enforcer_resolution_error is None:
                    try:
                        enforcer_resolution = ctx.subscribe("base.compiler.effective_model", "enforcer_resolution")
                    except PluginDataExchangeError as exc:
                        enforcer_resolution_error = str(exc)
                row_id = row.get("instance")
                group = row.get("group")
                self._validate_enforcer_type_ref(
                    ctx=ctx,
                    row=row,
                    row_by_id=row_by_id,
                    enforcer_resolution=enforcer_resolution,
                    enforcer_resolution_error=enforcer_resolution_error,
                    stage=stage,
                    diagnostics=diagnostics,
                    path=f"instance:{group}:{row_id}.managed_by_ref",
                )
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

    def _validate_enforcer_type_ref(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        enforcer_resolution: dict[str, Any] | None,
        enforcer_resolution_error: str | None,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        path: str,
    ) -> None:
        """N-01 replacement (ADR 0118/0119 D-TYPE-1..3).

        class.network.security_matrix is excluded from _is_network_row's
        generic managed_by_ref -> class.router check (ADR-0110: the enforcer
        may be a router or a hypervisor). This is the dedicated check that
        replaced it: managed_by_ref must resolve to an instance whose
        derived enforcer type (published by base.compiler.capabilities as
        enforcer_resolution) is not none.
        """
        value = self._resolve_field(ctx=ctx, row=row, key="managed_by_ref")
        if value is None:
            return
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7018",
                    severity="error",
                    stage=stage,
                    message="'managed_by_ref' must be a non-empty instance id string when set.",
                    path=path,
                )
            )
            return
        target = row_by_id.get(value)
        if not isinstance(target, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7018",
                    severity="error",
                    stage=stage,
                    message=f"'managed_by_ref' references unknown instance '{value}'.",
                    path=path,
                )
            )
            return
        if enforcer_resolution_error is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7018",
                    severity="error",
                    stage=stage,
                    message=(
                        "Could not obtain enforcer resolution to validate 'managed_by_ref': "
                        f"{enforcer_resolution_error}"
                    ),
                    path=path,
                )
            )
            return
        # enforcer_resolution is keyed by instance id (base.compiler.effective_model):
        # device-kind and OS-family facts live on two different objects under
        # ADR 0064's embedded-OS model, joined only at the instance level.
        resolution = enforcer_resolution.get(value) if isinstance(enforcer_resolution, dict) else None
        enforcer_type = resolution.get("type") if isinstance(resolution, dict) else None
        if enforcer_type is None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7018",
                    severity="error",
                    stage=stage,
                    message=(
                        f"'managed_by_ref' target '{value}' has no resolved enforcer type "
                        "(ADR 0118/0119 D-TYPE-1); it cannot enforce a security matrix."
                    ),
                    path=path,
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

    def _is_network_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if not isinstance(class_ref, str):
            return False
        if not class_ref.startswith("class.network."):
            return False
        if class_ref in self._NETWORK_CLASS_EXCLUSIONS:
            return False
        return row.get("layer") in {None, "L2"}

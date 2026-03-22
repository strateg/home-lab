"""L3 storage reference validator for storage-specific row relations."""

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


class StorageL3RefsValidator(ValidatorJsonPlugin):
    """Validate L3 storage row references (volume->pool, data_asset->volume)."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _L3_LAYER = "L3"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7830",
                    severity="error",
                    stage=stage,
                    message=f"storage_l3_refs validator requires normalized rows: {exc}",
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
            if class_ref == "class.storage.volume":
                self._validate_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="pool_ref",
                    expected_class="class.storage.pool",
                    code="E7831",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.data_asset":
                self._validate_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="volume_ref",
                    expected_class="class.storage.volume",
                    code="E7832",
                    stage=stage,
                    diagnostics=diagnostics,
                )

        return self.make_result(diagnostics)

    def _validate_ref(
        self,
        *,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        field_name: str,
        expected_class: str,
        code: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"
        ref_value = self._get_extension_field(row, field_name)
        if ref_value is None:
            return
        if not isinstance(ref_value, str) or not ref_value:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field_name}' must be a non-empty instance id string when set.",
                    path=f"{row_prefix}.{field_name}",
                )
            )
            return

        target = row_by_id.get(ref_value)
        if not isinstance(target, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field_name}' references unknown instance '{ref_value}'.",
                    path=f"{row_prefix}.{field_name}",
                )
            )
            return

        target_class = target.get("class_ref")
        target_layer = target.get("layer")
        if target_class != expected_class or target_layer != self._L3_LAYER:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=(
                        f"'{field_name}' target '{ref_value}' must reference {expected_class} on layer {self._L3_LAYER}; "
                        f"got class '{target_class}' on layer '{target_layer}'."
                    ),
                    path=f"{row_prefix}.{field_name}",
                )
            )

    @staticmethod
    def _get_extension_field(row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions.get(key)
        return None

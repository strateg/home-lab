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
    """Validate L3 storage row references across storage entity chain."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

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
                    expected_classes={"class.storage.pool"},
                    expected_layers={"L3"},
                    code="E7831",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.data_asset":
                self._validate_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="volume_ref",
                    expected_classes={"class.storage.volume"},
                    expected_layers={"L3"},
                    code="E7832",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.partition":
                self._validate_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="media_attachment_ref",
                    expected_classes={"class.storage.media_attachment"},
                    expected_layers={"L1", "L3"},
                    code="E7860",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.volume_group":
                self._validate_list_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="pv_refs",
                    expected_classes={"class.storage.partition"},
                    expected_layers={"L3"},
                    code="E7861",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.logical_volume":
                self._validate_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="vg_ref",
                    expected_classes={"class.storage.volume_group"},
                    expected_layers={"L3"},
                    code="E7862",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.filesystem":
                self._validate_filesystem_refs(row=row, row_by_id=row_by_id, stage=stage, diagnostics=diagnostics)
            elif class_ref == "class.storage.mount_point":
                self._validate_ref(
                    row=row,
                    row_by_id=row_by_id,
                    field_name="filesystem_ref",
                    expected_classes={"class.storage.filesystem"},
                    expected_layers={"L3"},
                    code="E7864",
                    stage=stage,
                    diagnostics=diagnostics,
                )
            elif class_ref == "class.storage.storage_endpoint":
                self._validate_storage_endpoint_refs(
                    row=row,
                    row_by_id=row_by_id,
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
        expected_classes: set[str],
        expected_layers: set[str],
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
        if target_class not in expected_classes or target_layer not in expected_layers:
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=(
                        f"'{field_name}' target '{ref_value}' must reference classes {sorted(expected_classes)} on "
                        f"layers {sorted(expected_layers)}; got class '{target_class}' on layer '{target_layer}'."
                    ),
                    path=f"{row_prefix}.{field_name}",
                )
            )

    def _validate_list_ref(
        self,
        *,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        field_name: str,
        expected_classes: set[str],
        expected_layers: set[str],
        code: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"

        ref_values = self._get_extension_field(row, field_name)
        if ref_values is None:
            return
        if not isinstance(ref_values, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity="error",
                    stage=stage,
                    message=f"'{field_name}' must be a list when set.",
                    path=f"{row_prefix}.{field_name}",
                )
            )
            return

        for idx, ref_value in enumerate(ref_values):
            if not isinstance(ref_value, str) or not ref_value:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message=f"'{field_name}' entries must be non-empty instance id strings.",
                        path=f"{row_prefix}.{field_name}[{idx}]",
                    )
                )
                continue
            target = row_by_id.get(ref_value)
            if not isinstance(target, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message=f"'{field_name}' references unknown instance '{ref_value}'.",
                        path=f"{row_prefix}.{field_name}[{idx}]",
                    )
                )
                continue
            target_class = target.get("class_ref")
            target_layer = target.get("layer")
            if target_class not in expected_classes or target_layer not in expected_layers:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message=(
                            f"'{field_name}' entry '{ref_value}' must reference classes "
                            f"{sorted(expected_classes)} on layers {sorted(expected_layers)}; "
                            f"got class '{target_class}' on layer '{target_layer}'."
                        ),
                        path=f"{row_prefix}.{field_name}[{idx}]",
                    )
                )

    def _validate_filesystem_refs(
        self,
        *,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"

        lv_ref = self._get_extension_field(row, "lv_ref")
        partition_ref = self._get_extension_field(row, "partition_ref")
        has_lv_ref = isinstance(lv_ref, str) and bool(lv_ref)
        has_partition_ref = isinstance(partition_ref, str) and bool(partition_ref)

        if has_lv_ref and has_partition_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7863",
                    severity="error",
                    stage=stage,
                    message="Filesystem row cannot set both 'lv_ref' and 'partition_ref'.",
                    path=row_prefix,
                )
            )
        elif not has_lv_ref and not has_partition_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7863",
                    severity="error",
                    stage=stage,
                    message="Filesystem row must set one of 'lv_ref' or 'partition_ref'.",
                    path=row_prefix,
                )
            )

        self._validate_ref(
            row=row,
            row_by_id=row_by_id,
            field_name="lv_ref",
            expected_classes={"class.storage.logical_volume"},
            expected_layers={"L3"},
            code="E7863",
            stage=stage,
            diagnostics=diagnostics,
        )
        self._validate_ref(
            row=row,
            row_by_id=row_by_id,
            field_name="partition_ref",
            expected_classes={"class.storage.partition"},
            expected_layers={"L3"},
            code="E7863",
            stage=stage,
            diagnostics=diagnostics,
        )

    def _validate_storage_endpoint_refs(
        self,
        *,
        row: dict[str, Any],
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        self._validate_ref(
            row=row,
            row_by_id=row_by_id,
            field_name="lv_ref",
            expected_classes={"class.storage.logical_volume"},
            expected_layers={"L3"},
            code="E7865",
            stage=stage,
            diagnostics=diagnostics,
        )
        self._validate_ref(
            row=row,
            row_by_id=row_by_id,
            field_name="mount_point_ref",
            expected_classes={"class.storage.mount_point"},
            expected_layers={"L3"},
            code="E7865",
            stage=stage,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _get_extension_field(row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions.get(key)
        return None

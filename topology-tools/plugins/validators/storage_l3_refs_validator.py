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
        backup_policy_ids = self._collect_backup_policy_ids(rows)
        volume_groups_by_name = self._collect_name_index(rows, class_ref="class.storage.volume_group")
        logical_volumes_by_name = self._collect_name_index(rows, class_ref="class.storage.logical_volume")

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
                self._validate_data_asset_backup_policies(
                    row=row,
                    backup_policy_ids=backup_policy_ids,
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
                    volume_groups_by_name=volume_groups_by_name,
                    logical_volumes_by_name=logical_volumes_by_name,
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
        volume_groups_by_name: dict[str, str],
        logical_volumes_by_name: dict[str, str],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"

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

        extensions = self._extensions(row)
        endpoint_path = extensions.get("path")
        has_path = isinstance(endpoint_path, str) and bool(endpoint_path.strip())
        has_lv_ref = isinstance(extensions.get("lv_ref"), str) and bool(str(extensions.get("lv_ref")).strip())
        has_mount_ref = isinstance(extensions.get("mount_point_ref"), str) and bool(
            str(extensions.get("mount_point_ref")).strip()
        )

        infer_from_raw = extensions.get("infer_from")
        if infer_from_raw is None:
            has_infer_from = False
            infer_from: dict[str, Any] = {}
        elif isinstance(infer_from_raw, dict):
            infer_from = infer_from_raw
            has_infer_from = bool(infer_from)
        else:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7866",
                    severity="error",
                    stage=stage,
                    message="'infer_from' must be an object when set.",
                    path=f"{row_prefix}.infer_from",
                )
            )
            infer_from = {}
            has_infer_from = False

        if not any((has_lv_ref, has_mount_ref, has_path, has_infer_from)):
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7866",
                    severity="warning",
                    stage=stage,
                    message="storage_endpoint should define lv_ref, mount_point_ref, path, or infer_from.",
                    path=row_prefix,
                )
            )

        if not has_infer_from:
            return

        endpoint_type = extensions.get("type")
        media_attachment_ref = infer_from.get("media_attachment_ref")
        vg_name = infer_from.get("vg_name")
        lv_name = infer_from.get("lv_name")
        expected_vg_id: str | None = None

        if media_attachment_ref is not None:
            if not isinstance(media_attachment_ref, str) or not media_attachment_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7866",
                        severity="error",
                        stage=stage,
                        message="'infer_from.media_attachment_ref' must be a non-empty instance id string.",
                        path=f"{row_prefix}.infer_from.media_attachment_ref",
                    )
                )
            else:
                media_row = row_by_id.get(media_attachment_ref)
                media_class = media_row.get("class_ref") if isinstance(media_row, dict) else None
                if not isinstance(media_row, dict) or media_class != "class.storage.media_attachment":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7866",
                            severity="error",
                            stage=stage,
                            message=(
                                f"'infer_from.media_attachment_ref' '{media_attachment_ref}' must reference "
                                "class.storage.media_attachment."
                            ),
                            path=f"{row_prefix}.infer_from.media_attachment_ref",
                        )
                    )
        elif endpoint_type == "lvmthin":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7866",
                    severity="error",
                    stage=stage,
                    message="'infer_from.media_attachment_ref' is required for storage_endpoint type 'lvmthin'.",
                    path=f"{row_prefix}.infer_from.media_attachment_ref",
                )
            )

        if vg_name is None:
            if endpoint_type == "lvmthin":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7866",
                        severity="error",
                        stage=stage,
                        message="'infer_from.vg_name' is required for storage_endpoint type 'lvmthin'.",
                        path=f"{row_prefix}.infer_from.vg_name",
                    )
                )
        elif not isinstance(vg_name, str) or not vg_name.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7866",
                    severity="error",
                    stage=stage,
                    message="'infer_from.vg_name' must be a non-empty string when set.",
                    path=f"{row_prefix}.infer_from.vg_name",
                )
            )
        else:
            expected_vg_id = volume_groups_by_name.get(vg_name.strip())
            if expected_vg_id is None:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7867",
                        severity="warning",
                        stage=stage,
                        message=f"'infer_from.vg_name' '{vg_name}' is not present in storage volume_groups.",
                        path=f"{row_prefix}.infer_from.vg_name",
                    )
                )

        if lv_name is None:
            if endpoint_type == "lvmthin":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7866",
                        severity="error",
                        stage=stage,
                        message="'infer_from.lv_name' is required for storage_endpoint type 'lvmthin'.",
                        path=f"{row_prefix}.infer_from.lv_name",
                    )
                )
        elif not isinstance(lv_name, str) or not lv_name.strip():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7866",
                    severity="error",
                    stage=stage,
                    message="'infer_from.lv_name' must be a non-empty string when set.",
                    path=f"{row_prefix}.infer_from.lv_name",
                )
            )
        else:
            logical_volume_id = logical_volumes_by_name.get(lv_name.strip())
            if logical_volume_id is None:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7868",
                        severity="warning",
                        stage=stage,
                        message=f"'infer_from.lv_name' '{lv_name}' is not present in storage logical_volumes.",
                        path=f"{row_prefix}.infer_from.lv_name",
                    )
                )
            elif expected_vg_id:
                logical_volume_row = row_by_id.get(logical_volume_id)
                logical_volume_vg_ref = (
                    self._get_extension_field(logical_volume_row, "vg_ref")
                    if isinstance(logical_volume_row, dict)
                    else None
                )
                if isinstance(logical_volume_vg_ref, str) and logical_volume_vg_ref != expected_vg_id:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7868",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"'infer_from.lv_name' '{lv_name}' belongs to vg '{logical_volume_vg_ref}', "
                                f"expected '{expected_vg_id}'."
                            ),
                            path=f"{row_prefix}.infer_from.lv_name",
                        )
                    )

        if (
            endpoint_type == "lvmthin"
            and isinstance(media_attachment_ref, str)
            and media_attachment_ref
            and expected_vg_id
        ):
            expected_vg_row = row_by_id.get(expected_vg_id)
            expected_vg_pv_refs = (
                self._get_extension_field(expected_vg_row, "pv_refs") if isinstance(expected_vg_row, dict) else None
            )
            if isinstance(expected_vg_pv_refs, list) and expected_vg_pv_refs:
                pv_matches_attachment = False
                for pv_ref in expected_vg_pv_refs:
                    if not isinstance(pv_ref, str):
                        continue
                    partition_row = row_by_id.get(pv_ref)
                    if not isinstance(partition_row, dict):
                        continue
                    partition_attachment = self._get_extension_field(partition_row, "media_attachment_ref")
                    if partition_attachment == media_attachment_ref:
                        pv_matches_attachment = True
                        break
                if not pv_matches_attachment:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7866",
                            severity="error",
                            stage=stage,
                            message=(
                                f"'infer_from.media_attachment_ref' '{media_attachment_ref}' is not linked to any "
                                f"pv_refs in volume group '{expected_vg_id}'."
                            ),
                            path=f"{row_prefix}.infer_from.media_attachment_ref",
                        )
                    )

        if has_lv_ref or has_mount_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="W7866",
                    severity="warning",
                    stage=stage,
                    message="infer_from should not be combined with lv_ref or mount_point_ref in storage_endpoint.",
                    path=row_prefix,
                )
            )

    def _validate_data_asset_backup_policies(
        self,
        *,
        row: dict[str, Any],
        backup_policy_ids: set[str],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"
        extensions = self._extensions(row)

        category = extensions.get("category")
        criticality = extensions.get("criticality")
        engine = extensions.get("engine")

        engine_required_categories = {"database", "cache", "timeseries", "search-index", "object-storage"}
        if isinstance(category, str) and category in engine_required_categories and not engine:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7868",
                    severity="error",
                    stage=stage,
                    message=f"Data asset '{row_id}' category '{category}' requires 'engine'.",
                    path=f"{row_prefix}.engine",
                )
            )

        backup_policy_refs = extensions.get("backup_policy_refs")
        if backup_policy_refs is not None and not isinstance(backup_policy_refs, list):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7867",
                    severity="error",
                    stage=stage,
                    message="'backup_policy_refs' must be a list when set.",
                    path=f"{row_prefix}.backup_policy_refs",
                )
            )
            backup_policy_refs = []

        normalized_refs: list[str] = []
        if isinstance(backup_policy_refs, list):
            for idx, value in enumerate(backup_policy_refs):
                if not isinstance(value, str) or not value:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7867",
                            severity="error",
                            stage=stage,
                            message="'backup_policy_refs' entries must be non-empty strings.",
                            path=f"{row_prefix}.backup_policy_refs[{idx}]",
                        )
                    )
                    continue
                normalized_refs.append(value)
                if value not in backup_policy_ids:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7867",
                            severity="error",
                            stage=stage,
                            message=f"Data asset '{row_id}' backup_policy_ref '{value}' does not exist.",
                            path=f"{row_prefix}.backup_policy_refs[{idx}]",
                        )
                    )

        backup_policy = extensions.get("backup_policy")
        if backup_policy is not None:
            if not isinstance(backup_policy, str) or not backup_policy:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7867",
                        severity="error",
                        stage=stage,
                        message="'backup_policy' must be a non-empty string when set.",
                        path=f"{row_prefix}.backup_policy",
                    )
                )
            elif backup_policy not in {"none", "daily", "weekly", "monthly"} and backup_policy not in backup_policy_ids:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7869",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"Data asset '{row_id}' backup_policy '{backup_policy}' is not a known schedule alias "
                            "and not a known backup policy instance id."
                        ),
                        path=f"{row_prefix}.backup_policy",
                    )
                )

        has_backup_binding = bool(normalized_refs) or (
            isinstance(backup_policy, str) and backup_policy and backup_policy != "none"
        )
        if criticality in {"high", "critical"} and not has_backup_binding:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7867",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Data asset '{row_id}' criticality '{criticality}' requires backup policy binding "
                        "(backup_policy_refs or backup_policy)."
                    ),
                    path=row_prefix,
                )
            )

    def _collect_backup_policy_ids(self, rows: list[dict[str, Any]]) -> set[str]:
        policy_ids: set[str] = set()
        for row in rows:
            if row.get("class_ref") != "class.operations.backup":
                continue
            row_id = row.get("instance")
            if isinstance(row_id, str) and row_id:
                policy_ids.add(row_id)
        return policy_ids

    def _collect_name_index(self, rows: list[dict[str, Any]], *, class_ref: str) -> dict[str, str]:
        index: dict[str, str] = {}
        for row in rows:
            if row.get("class_ref") != class_ref:
                continue
            row_id = row.get("instance")
            if not isinstance(row_id, str) or not row_id:
                continue
            name = self._get_extension_field(row, "name")
            if isinstance(name, str) and name.strip():
                index[name.strip()] = row_id
        return index

    @staticmethod
    def _extensions(row: dict[str, Any]) -> dict[str, Any]:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions
        return {}

    @staticmethod
    def _get_extension_field(row: dict[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, dict):
            return extensions.get(key)
        return None

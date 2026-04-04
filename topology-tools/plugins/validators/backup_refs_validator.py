"""Backup reference validator."""

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


class BackupRefsValidator(ValidatorJsonPlugin):
    """Validate backup target refs and destination refs."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _BACKUP_CLASS = "class.operations.backup"
    _LXC_CLASSES = {"class.compute.workload.container", "class.compute.workload.lxc"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7858",
                    severity="error",
                    stage=stage,
                    message=f"backup_refs validator requires normalized rows: {exc}",
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
            if row.get("class_ref") != self._BACKUP_CLASS:
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = row.get("extensions")
            if not isinstance(extensions, dict):
                continue

            destination_ref = extensions.get("destination_ref")
            if destination_ref is not None:
                self._validate_target(
                    row_id=row_id,
                    field_name="destination_ref",
                    value=destination_ref,
                    expected=lambda target: target.get("class_ref") == "class.storage.pool",
                    expected_label="class.storage.pool instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.destination_ref",
                    diagnostics=diagnostics,
                )

            targets = extensions.get("targets")
            if targets is None:
                continue
            if not isinstance(targets, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7858",
                        severity="error",
                        stage=stage,
                        message=f"Backup '{row_id}' targets must be a list when set.",
                        path=f"{row_prefix}.targets",
                    )
                )
                continue

            for idx, target in enumerate(targets):
                if not isinstance(target, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7858",
                            severity="error",
                            stage=stage,
                            message=f"Backup '{row_id}' targets entries must be objects.",
                            path=f"{row_prefix}.targets[{idx}]",
                        )
                    )
                    continue
                self._validate_target(
                    row_id=row_id,
                    field_name="device_ref",
                    value=target.get("device_ref"),
                    expected=lambda candidate: candidate.get("layer") == "L1",
                    expected_label="L1 device instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.targets[{idx}].device_ref",
                    diagnostics=diagnostics,
                )
                self._validate_target(
                    row_id=row_id,
                    field_name="lxc_ref",
                    value=target.get("lxc_ref"),
                    expected=lambda candidate: candidate.get("class_ref") in self._LXC_CLASSES,
                    expected_label="L4 container workload instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.targets[{idx}].lxc_ref",
                    diagnostics=diagnostics,
                )
                self._validate_target(
                    row_id=row_id,
                    field_name="data_asset_ref",
                    value=target.get("data_asset_ref"),
                    expected=lambda candidate: candidate.get("class_ref") == "class.storage.data_asset",
                    expected_label="class.storage.data_asset instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.targets[{idx}].data_asset_ref",
                    diagnostics=diagnostics,
                )

        return self.make_result(diagnostics)

    def _validate_target(
        self,
        *,
        row_id: Any,
        field_name: str,
        value: Any,
        expected: Any,
        expected_label: str,
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
                    code="E7858",
                    severity="error",
                    stage=stage,
                    message=f"Backup '{row_id}' {field_name} must be a non-empty string when set.",
                    path=path,
                )
            )
            return
        target = row_by_id.get(value)
        if not isinstance(target, dict) or not expected(target):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7858",
                    severity="error",
                    stage=stage,
                    message=f"Backup '{row_id}' {field_name} '{value}' must reference a valid {expected_label}.",
                    path=path,
                )
            )

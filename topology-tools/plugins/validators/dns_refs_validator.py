"""DNS record reference validator."""

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


class DnsRefsValidator(ValidatorJsonPlugin):
    """Validate device/lxc/service refs used by DNS records."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"
    _SERVICE_PREFIX = "class.service."
    _DNS_CLASSES = {"class.service.dns"}
    _LXC_CLASSES = {"class.compute.workload.container", "class.compute.workload.lxc"}

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7856",
                    severity="error",
                    stage=stage,
                    message=f"dns_refs validator requires normalized rows: {exc}",
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
            if not self._is_dns_row(row):
                continue
            row_id = row.get("instance")
            group = row.get("group")
            row_prefix = f"instance:{group}:{row_id}"
            extensions = row.get("extensions")
            if not isinstance(extensions, dict):
                continue

            records = self._extract_records(extensions)
            for idx, record in enumerate(records):
                if not isinstance(record, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7856",
                            severity="error",
                            stage=stage,
                            message="DNS record entries must be objects.",
                            path=f"{row_prefix}.records[{idx}]",
                        )
                    )
                    continue

                self._validate_target_ref(
                    row_id=row_id,
                    record=record,
                    field_name="device_ref",
                    expected_predicate=self._is_l1_device,
                    expected_label="L1 device instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.records[{idx}].device_ref",
                    diagnostics=diagnostics,
                )
                self._validate_target_ref(
                    row_id=row_id,
                    record=record,
                    field_name="lxc_ref",
                    expected_predicate=lambda target: target.get("class_ref") in self._LXC_CLASSES,
                    expected_label="L4 container workload instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.records[{idx}].lxc_ref",
                    diagnostics=diagnostics,
                )
                self._validate_target_ref(
                    row_id=row_id,
                    record=record,
                    field_name="service_ref",
                    expected_predicate=lambda target: self._is_service(target.get("class_ref")),
                    expected_label="service instance",
                    row_by_id=row_by_id,
                    stage=stage,
                    path=f"{row_prefix}.records[{idx}].service_ref",
                    diagnostics=diagnostics,
                )

        return self.make_result(diagnostics)

    def _extract_records(self, extensions: dict[str, Any]) -> list[Any]:
        extracted: list[Any] = []
        direct = extensions.get("records")
        if isinstance(direct, list):
            extracted.extend(direct)

        zones = extensions.get("zones")
        if isinstance(zones, list):
            for zone in zones:
                if not isinstance(zone, dict):
                    continue
                zone_records = zone.get("records")
                if isinstance(zone_records, list):
                    extracted.extend(zone_records)
        return extracted

    def _validate_target_ref(
        self,
        *,
        row_id: Any,
        record: dict[str, Any],
        field_name: str,
        expected_predicate: Any,
        expected_label: str,
        row_by_id: dict[str, dict[str, Any]],
        stage: Stage,
        path: str,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        value = record.get(field_name)
        if value is None:
            return
        if not isinstance(value, str) or not value:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7856",
                    severity="error",
                    stage=stage,
                    message=f"Service '{row_id}' DNS '{field_name}' must be a non-empty string when set.",
                    path=path,
                )
            )
            return
        target = row_by_id.get(value)
        if not isinstance(target, dict) or not expected_predicate(target):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7856",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Service '{row_id}' DNS '{field_name}' '{value}' must reference a valid " f"{expected_label}."
                    ),
                    path=path,
                )
            )

    def _is_dns_row(self, row: dict[str, Any]) -> bool:
        class_ref = row.get("class_ref")
        if class_ref in self._DNS_CLASSES:
            return True
        group = row.get("group")
        return isinstance(group, str) and group in {"dns", "dns_zones"}

    def _is_service(self, class_ref: Any) -> bool:
        return isinstance(class_ref, str) and class_ref.startswith(self._SERVICE_PREFIX)

    @staticmethod
    def _is_l1_device(row: dict[str, Any]) -> bool:
        return row.get("layer") == "L1"

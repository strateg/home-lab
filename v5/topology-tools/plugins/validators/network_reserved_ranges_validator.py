"""Reserved ranges validator for network VLAN instances."""

from __future__ import annotations

import ipaddress
from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class NetworkReservedRangesValidator(ValidatorJsonPlugin):
    """Validate `reserved_ranges` against VLAN CIDR and overlap constraints."""

    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            rows_payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except PluginDataExchangeError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7819",
                    severity="error",
                    stage=stage,
                    message=f"network_reserved_ranges validator requires normalized rows: {exc}",
                    path="pipeline:validate",
                )
            )
            return self.make_result(diagnostics)

        rows = [item for item in rows_payload if isinstance(item, dict)] if isinstance(rows_payload, list) else []
        for row in rows:
            if row.get("class_ref") != "class.network.vlan":
                continue
            self._validate_vlan_row(ctx=ctx, row=row, stage=stage, diagnostics=diagnostics)

        return self.make_result(diagnostics)

    def _validate_vlan_row(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        row_id = row.get("instance")
        group = row.get("group")
        row_prefix = f"instance:{group}:{row_id}"
        cidr, reserved_ranges, ranges_path = self._network_payload(ctx=ctx, row=row, row_prefix=row_prefix)
        if not isinstance(reserved_ranges, list) or not reserved_ranges:
            return
        if not isinstance(cidr, str) or not cidr:
            return
        if cidr.strip().lower() == "dhcp":
            return

        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return

        parsed_ranges: list[tuple[ipaddress._BaseAddress, ipaddress._BaseAddress, str]] = []
        for idx, rng in enumerate(reserved_ranges):
            if not isinstance(rng, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7820",
                        severity="error",
                        stage=stage,
                        message=f"reserved_ranges[{idx}] must be an object with start/end.",
                        path=f"{ranges_path}[{idx}]",
                    )
                )
                continue

            start_str = rng.get("start")
            end_str = rng.get("end")
            purpose = rng.get("purpose", "unknown")
            if not isinstance(start_str, str) or not isinstance(end_str, str) or not start_str or not end_str:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7820",
                        severity="error",
                        stage=stage,
                        message=f"reserved_ranges[{idx}] must define non-empty start and end.",
                        path=f"{ranges_path}[{idx}]",
                    )
                )
                continue

            try:
                start_ip = ipaddress.ip_address(start_str)
                end_ip = ipaddress.ip_address(end_str)
            except ValueError as exc:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7820",
                        severity="error",
                        stage=stage,
                        message=f"reserved_ranges[{idx}] has invalid IP address: {exc}.",
                        path=f"{ranges_path}[{idx}]",
                    )
                )
                continue

            if start_ip not in network or end_ip not in network:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7820",
                        severity="error",
                        stage=stage,
                        message=(
                            f"reserved range {start_str}-{end_str} is outside CIDR '{cidr}' for '{row_id}'."
                        ),
                        path=f"{ranges_path}[{idx}]",
                    )
                )
                continue

            if start_ip > end_ip:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7820",
                        severity="error",
                        stage=stage,
                        message=f"reserved range start '{start_str}' must not be greater than end '{end_str}'.",
                        path=f"{ranges_path}[{idx}]",
                    )
                )
                continue

            parsed_ranges.append((start_ip, end_ip, str(purpose)))

        for i, (start1, end1, purpose1) in enumerate(parsed_ranges):
            for j, (start2, end2, purpose2) in enumerate(parsed_ranges):
                if i >= j:
                    continue
                if start1 <= end2 and start2 <= end1:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7820",
                            severity="error",
                            stage=stage,
                            message=(
                                f"reserved ranges overlap in '{row_id}': "
                                f"{start1}-{end1} ({purpose1}) and {start2}-{end2} ({purpose2})."
                            ),
                            path=ranges_path,
                        )
                    )

    @staticmethod
    def _network_payload(*, ctx: PluginContext, row: dict[str, Any], row_prefix: str) -> tuple[Any, Any, str]:
        extensions = row.get("extensions") if isinstance(row.get("extensions"), dict) else {}
        object_ref = row.get("object_ref")
        object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = object_payload.get("properties") if isinstance(object_payload, dict) else None
        object_cidr = properties.get("cidr") if isinstance(properties, dict) else None
        object_ranges = properties.get("reserved_ranges") if isinstance(properties, dict) else None

        if isinstance(extensions, dict) and "reserved_ranges" in extensions:
            cidr = extensions.get("cidr")
            if cidr is None:
                cidr = row.get("cidr")
            if cidr is None:
                cidr = object_cidr
            return cidr, extensions.get("reserved_ranges"), f"{row_prefix}.extensions.reserved_ranges"
        if "reserved_ranges" in row:
            cidr = row.get("cidr")
            if cidr is None:
                cidr = object_cidr
            return cidr, row.get("reserved_ranges"), f"{row_prefix}.reserved_ranges"
        if isinstance(properties, dict):
            return object_cidr, object_ranges, f"{row_prefix}.reserved_ranges"
        return None, None, f"{row_prefix}.reserved_ranges"

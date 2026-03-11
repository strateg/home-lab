"""Module-level validator for ethernet cable endpoint wiring."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _resolve_topology_tools() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "topology-tools"
        if candidate.is_dir():
            return candidate
    return None


TOPOLOGY_TOOLS = _resolve_topology_tools()
if TOPOLOGY_TOOLS and str(TOPOLOGY_TOOLS) not in sys.path:
    sys.path.insert(0, str(TOPOLOGY_TOOLS))

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorJsonPlugin


class EthernetCableEndpointValidator(ValidatorJsonPlugin):
    """Validate endpoint_a/endpoint_b wiring for ethernet cable instances."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        bindings = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(bindings, dict):
            return self.make_result(diagnostics)

        instance_rows = self._build_instance_index(bindings)
        for group_name, rows in bindings.items():
            if not isinstance(rows, list):
                continue
            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                if not self._is_ethernet_cable_row(row):
                    continue
                prefix = f"instance_bindings.{group_name}[{index}]"
                self._validate_cable_row(
                    ctx=ctx,
                    row=row,
                    row_prefix=prefix,
                    instance_rows=instance_rows,
                    stage=stage,
                    diagnostics=diagnostics,
                )

        return self.make_result(diagnostics)

    @staticmethod
    def _is_ethernet_cable_row(row: dict[str, Any]) -> bool:
        object_ref = row.get("object_ref")
        return object_ref == "obj.network.ethernet_cable"

    @staticmethod
    def _build_instance_index(bindings: dict[str, Any]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for rows in bindings.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                instance_id = row.get("instance")
                if isinstance(instance_id, str) and instance_id and instance_id not in index:
                    index[instance_id] = row
        return index

    def _validate_cable_row(
        self,
        *,
        ctx: PluginContext,
        row: dict[str, Any],
        row_prefix: str,
        instance_rows: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[Any],
    ) -> None:
        for endpoint_name in ("endpoint_a", "endpoint_b"):
            endpoint = row.get(endpoint_name)
            if not isinstance(endpoint, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7304",
                        severity="error",
                        stage=stage,
                        message=f"'{endpoint_name}' must be an object with device_ref and port.",
                        path=f"{row_prefix}.{endpoint_name}",
                    )
                )
                continue

            device_ref = endpoint.get("device_ref")
            port = endpoint.get("port")
            if not isinstance(device_ref, str) or not device_ref:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7304",
                        severity="error",
                        stage=stage,
                        message=f"'{endpoint_name}.device_ref' must be a non-empty string.",
                        path=f"{row_prefix}.{endpoint_name}.device_ref",
                    )
                )
                continue
            if not isinstance(port, str) or not port:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7304",
                        severity="error",
                        stage=stage,
                        message=f"'{endpoint_name}.port' must be a non-empty string.",
                        path=f"{row_prefix}.{endpoint_name}.port",
                    )
                )
                continue

            device_row = instance_rows.get(device_ref)
            if not isinstance(device_row, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7304",
                        severity="error",
                        stage=stage,
                        message=f"Endpoint references unknown device instance '{device_ref}'.",
                        path=f"{row_prefix}.{endpoint_name}.device_ref",
                    )
                )
                continue

            object_ref = device_row.get("object_ref")
            object_payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
            ethernet_ports = self._extract_ethernet_ports(object_payload)
            if not ethernet_ports:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7306",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Device '{device_ref}' (object_ref '{object_ref}') has no ethernet port inventory "
                            "for endpoint validation."
                        ),
                        path=f"{row_prefix}.{endpoint_name}.device_ref",
                    )
                )
                continue

            if port not in ethernet_ports:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7305",
                        severity="error",
                        stage=stage,
                        message=(
                            f"Port '{port}' does not exist on device '{device_ref}'. "
                            f"Known ports: {sorted(ethernet_ports)}"
                        ),
                        path=f"{row_prefix}.{endpoint_name}.port",
                    )
                )

        class_ref = row.get("class_ref")
        if class_ref != "class.network.data_channel":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7304",
                    severity="error",
                    stage=stage,
                    message=("Ethernet cable instance must use class_ref " "'class.network.data_channel'."),
                    path=f"{row_prefix}.class_ref",
                )
            )

        length_m = row.get("length_m")
        if length_m is not None and not isinstance(length_m, (int, float)):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7304",
                    severity="error",
                    stage=stage,
                    message="'length_m' must be numeric when provided.",
                    path=f"{row_prefix}.length_m",
                )
            )
        if isinstance(length_m, (int, float)) and length_m <= 0:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7304",
                    severity="error",
                    stage=stage,
                    message="'length_m' must be greater than zero.",
                    path=f"{row_prefix}.length_m",
                )
            )

        shielding = row.get("shielding")
        if not isinstance(shielding, str) or shielding not in {"utp", "ftp", "stp"}:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7304",
                    severity="error",
                    stage=stage,
                    message="'shielding' must be one of: utp, ftp, stp.",
                    path=f"{row_prefix}.shielding",
                )
            )

    @staticmethod
    def _extract_ethernet_ports(object_payload: Any) -> set[str]:
        if not isinstance(object_payload, dict):
            return set()
        hardware_specs = object_payload.get("hardware_specs")
        if not isinstance(hardware_specs, dict):
            return set()
        interfaces = hardware_specs.get("interfaces")
        if not isinstance(interfaces, dict):
            return set()
        ethernet = interfaces.get("ethernet")
        if not isinstance(ethernet, list):
            return set()
        ports: set[str] = set()
        for item in ethernet:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    ports.add(name)
        return ports

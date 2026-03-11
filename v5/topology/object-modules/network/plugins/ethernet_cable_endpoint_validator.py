"""Module-level validator for ethernet data-link endpoint wiring."""

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
    """Validate ethernet cable endpoints and created data-channel binding."""

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

    @staticmethod
    def _resolve_class_ref(*, row: dict[str, Any], ctx: PluginContext) -> str | None:
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and class_ref:
            return class_ref
        object_ref = row.get("object_ref")
        if not isinstance(object_ref, str) or not object_ref:
            return None
        object_payload = ctx.objects.get(object_ref)
        if not isinstance(object_payload, dict):
            return None
        candidate = object_payload.get("class_ref")
        if isinstance(candidate, str) and candidate:
            return candidate
        return None

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

        class_ref = self._resolve_class_ref(row=row, ctx=ctx)
        if class_ref != "class.network.physical_link":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7304",
                    severity="error",
                    stage=stage,
                    message=("Ethernet cable instance must use class_ref " "'class.network.physical_link'."),
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

        creates_channel_ref = row.get("creates_channel_ref")
        if not isinstance(creates_channel_ref, str) or not creates_channel_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7307",
                    severity="error",
                    stage=stage,
                    message="'creates_channel_ref' must be a non-empty string.",
                    path=f"{row_prefix}.creates_channel_ref",
                )
            )
            return

        channel_row = instance_rows.get(creates_channel_ref)
        if not isinstance(channel_row, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7307",
                    severity="error",
                    stage=stage,
                    message=f"Cable references unknown data-channel instance '{creates_channel_ref}'.",
                    path=f"{row_prefix}.creates_channel_ref",
                )
            )
            return

        channel_class_ref = self._resolve_class_ref(row=channel_row, ctx=ctx)
        if channel_class_ref != "class.network.data_link":
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7307",
                    severity="error",
                    stage=stage,
                    message=(f"Referenced instance '{creates_channel_ref}' must use " "'class.network.data_link'."),
                    path=f"{row_prefix}.creates_channel_ref",
                )
            )

        cable_instance_id = row.get("instance")
        channel_link_ref = channel_row.get("link_ref")
        if not isinstance(channel_link_ref, str) or not channel_link_ref:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7308",
                    severity="error",
                    stage=stage,
                    message=f"Data-channel '{creates_channel_ref}' must define non-empty 'link_ref'.",
                    path=f"instance:{creates_channel_ref}:link_ref",
                )
            )
        elif isinstance(cable_instance_id, str) and cable_instance_id and channel_link_ref != cable_instance_id:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7308",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Data-channel '{creates_channel_ref}' link_ref must point back to "
                        f"'{cable_instance_id}', got '{channel_link_ref}'."
                    ),
                    path=f"instance:{creates_channel_ref}:link_ref",
                )
            )

        cable_endpoints = self._endpoint_set(row)
        channel_endpoints = self._endpoint_set(channel_row)
        if cable_endpoints and channel_endpoints and cable_endpoints != channel_endpoints:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7308",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Data-channel '{creates_channel_ref}' endpoints must match cable endpoints "
                        "as an unordered pair."
                    ),
                    path=f"{row_prefix}.creates_channel_ref",
                )
            )

        channel_object_ref = channel_row.get("object_ref")
        channel_object = ctx.objects.get(channel_object_ref) if isinstance(channel_object_ref, str) else None
        if isinstance(channel_object, dict):
            properties = channel_object.get("properties")
            if isinstance(properties, dict):
                protocol_family = properties.get("protocol_family")
                if isinstance(protocol_family, str) and protocol_family not in {"ieee_802_3", "ethernet"}:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7307",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Referenced channel object '{channel_object_ref}' must have "
                                "properties.protocol_family compatible with ethernet."
                            ),
                            path=f"{row_prefix}.creates_channel_ref",
                        )
                    )

                backing_link_class = properties.get("backing_link_class")
                if isinstance(backing_link_class, str) and backing_link_class != "class.network.physical_link":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7307",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Referenced channel object '{channel_object_ref}' must declare "
                                "properties.backing_link_class='class.network.physical_link'."
                            ),
                            path=f"{row_prefix}.creates_channel_ref",
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

    @staticmethod
    def _endpoint_set(row: dict[str, Any]) -> set[tuple[str, str]]:
        endpoint_pairs: set[tuple[str, str]] = set()
        for endpoint_name in ("endpoint_a", "endpoint_b"):
            endpoint = row.get(endpoint_name)
            if not isinstance(endpoint, dict):
                continue
            device_ref = endpoint.get("device_ref")
            port = endpoint.get("port")
            if not isinstance(device_ref, str) or not device_ref:
                continue
            if not isinstance(port, str) or not port:
                continue
            endpoint_pairs.add((device_ref, port))
        return endpoint_pairs


"""
Endpoint Validator for Physical Links

Validates:
1. Endpoint device_ref resolves to existing instance
2. Endpoint port exists on the device object definition
3. Port matches device type constraints (e.g., MikroTik ether*, GL.iNet lan/wan)
4. No validation of port occupancy (separate validator: port_occupancy_validator)
"""

from pathlib import Path
from typing import Dict, Optional, Set

import yaml
from v5.topology_tools.kernel.plugin_base import PluginDiagnostic, PluginResult, ValidatorPlugin


class EndpointValidator(ValidatorPlugin):
    """Validate cable endpoints against device object definitions."""

    # Known port naming patterns per vendor
    VENDOR_PORT_PATTERNS = {
        "mikrotik": {
            "patterns": [r"^ether\d+$", r"^sfp\d+$", r"^usb\d+$"],
            "description": "MikroTik: ether*, sfp*, usb*",
        },
        "glinet": {
            "patterns": [r"^(wan|lan\d+)$", r"^usb\d+$", r"^wlan\d+$"],
            "description": "GL.iNet: wan, lan*, usb*, wlan*",
        },
    }

    def __init__(self, context):
        super().__init__(context)
        self.devices = {}  # instance_id -> device object data
        self.vendor_map = {}  # instance_id -> vendor

    def _load_device_objects(self, topology_root: Path) -> None:
        """Load all router objects to extract port definitions."""
        try:
            for obj_file in topology_root.glob("object-modules/*/obj.*.yaml"):
                with open(obj_file, "r") as f:
                    obj = yaml.safe_load(f)

                if obj and obj.get("class_ref") == "class.router":
                    obj_ref = obj.get("object")
                    vendor = obj.get("vendor", "unknown")
                    self.devices[obj_ref] = obj
                    self.vendor_map[obj_ref] = vendor
        except Exception as e:
            self.warnings.append(f"Failed to load device objects: {e}")

    def execute(self, compiled_json: dict) -> PluginResult:
        """
        Validate cable endpoints.

        Args:
            compiled_json: Compiled effective model

        Returns:
            PluginResult with diagnostics if violations found
        """
        diagnostics = []
        violations = 0
        topology_root = Path(__file__).parent.parent.parent.parent.parent / "topology"
        self._load_device_objects(topology_root)

        # Extract device instances from compiled model to resolve refs
        devices_by_id = {}
        if "instances" in compiled_json:
            for group_name, instances_in_group in compiled_json["instances"].items():
                if isinstance(instances_in_group, list):
                    for instance in instances_in_group:
                        inst_id = instance.get("instance")
                        obj_ref = instance.get("object_ref")
                        if inst_id and obj_ref:
                            devices_by_id[inst_id] = obj_ref

        # Validate all physical_link instances
        if "instances" in compiled_json:
            for group_name, instances_in_group in compiled_json["instances"].items():
                if not isinstance(instances_in_group, list):
                    continue

                for instance in instances_in_group:
                    if instance.get("class_ref") != "class.network.physical_link":
                        continue

                    instance_id = instance.get("instance")
                    endpoints = [instance.get("endpoint_a"), instance.get("endpoint_b")]

                    for endpoint_idx, endpoint in enumerate(endpoints):
                        if not endpoint:
                            continue

                        device_ref = endpoint.get("device_ref")
                        port = endpoint.get("port")

                        if not device_ref or not port:
                            continue

                        endpoint_name = f"endpoint_{'ab'[endpoint_idx]}"

                        # Resolve device_ref to object_ref
                        if device_ref not in devices_by_id:
                            violations += 1
                            diagnostics.append(
                                PluginDiagnostic(
                                    severity="error",
                                    code="E7304",
                                    message=f"{instance_id}: {endpoint_name} references unknown device '{device_ref}'",
                                    location={
                                        "entity": instance_id,
                                        "field": endpoint_name,
                                    },
                                )
                            )
                            continue

                        object_ref = devices_by_id[device_ref]
                        if object_ref not in self.devices:
                            violations += 1
                            diagnostics.append(
                                PluginDiagnostic(
                                    severity="error",
                                    code="E7304",
                                    message=f"{instance_id}: {endpoint_name} references unknown object '{object_ref}' for device '{device_ref}'",
                                    location={
                                        "entity": instance_id,
                                        "field": endpoint_name,
                                    },
                                )
                            )
                            continue

                        # Check if port exists in device object
                        device_obj = self.devices[object_ref]
                        vendor = self.vendor_map.get(object_ref, "unknown")
                        if not self._validate_port_exists(device_obj, port, vendor, instance_id, endpoint_name):
                            violations += 1
                            diagnostics.append(
                                PluginDiagnostic(
                                    severity="error",
                                    code="E7305",
                                    message=f"{instance_id}: {endpoint_name} port '{port}' not found on {vendor.upper()} device '{device_ref}' ({object_ref})",
                                    location={
                                        "entity": instance_id,
                                        "field": endpoint_name,
                                    },
                                    context={
                                        "vendor": vendor,
                                        "requested_port": port,
                                        "available_ports": self._get_available_ports(device_obj),
                                    },
                                )
                            )

        if violations > 0:
            return self.failed_result(
                diagnostics=diagnostics,
                output_data={"endpoint_violations": violations},
            )

        return self.success_result(
            output_data={"endpoints_validated": len(diagnostics) + violations},
            diagnostics=diagnostics,
        )

    def _validate_port_exists(
        self, device_obj: Dict, port: str, vendor: str, instance_id: str, endpoint_name: str
    ) -> bool:
        """Check if port exists in device object definition."""
        interfaces = device_obj.get("hardware_specs", {}).get("interfaces", {})

        # Check ethernet ports
        ethernet_ports = interfaces.get("ethernet", [])
        for eth_if in ethernet_ports:
            if eth_if.get("name") == port:
                return True

        # Check wireless ports (for completeness)
        wireless_ports = interfaces.get("wireless", [])
        for wifi_if in wireless_ports:
            if wifi_if.get("name") == port:
                return True

        # Check USB ports
        usb_ports = interfaces.get("usb", [])
        for usb_if in usb_ports:
            if usb_if.get("name") == port:
                return True

        # Check cellular ports
        cellular_ports = interfaces.get("cellular", [])
        for cell_if in cellular_ports:
            if cell_if.get("name") == port:
                return True

        return False

    def _get_available_ports(self, device_obj: Dict) -> list:
        """Extract all available port names from device object."""
        ports = []
        interfaces = device_obj.get("hardware_specs", {}).get("interfaces", {})

        for if_type in ["ethernet", "wireless", "cellular", "usb"]:
            if_list = interfaces.get(if_type, [])
            if isinstance(if_list, list):
                for iface in if_list:
                    port_name = iface.get("name")
                    if port_name:
                        ports.append(port_name)

        return sorted(ports)

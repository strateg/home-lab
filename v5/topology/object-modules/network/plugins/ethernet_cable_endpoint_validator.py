"""Module-level validator for ethernet data-link endpoint wiring."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)


class EthernetCableEndpointValidator(ValidatorJsonPlugin):
    """Validate ethernet cable endpoints and created data-channel binding."""

    _PORT_INVENTORY_PLUGIN_ID = "base.validator.ethernet_port_inventory"
    _PORT_INVENTORY_KEY = "ethernet_ports_by_object"

    @staticmethod
    def _subscribe_required(
        ctx: PluginContext,
        *,
        plugin_id: str,
        published_key: str,
    ) -> Any:
        try:
            return ctx.subscribe(plugin_id, published_key)
        except PluginDataExchangeError as exc:
            raise PluginDataExchangeError(
                f"Missing required published key '{published_key}' from '{plugin_id}': {exc}"
            ) from exc

    @staticmethod
    def _normalize_inventory(raw_inventory: Any) -> dict[str, set[str]]:
        normalized: dict[str, set[str]] = {}
        if not isinstance(raw_inventory, dict):
            return normalized
        for object_id, ports in raw_inventory.items():
            if not isinstance(object_id, str) or not object_id:
                continue
            if not isinstance(ports, list):
                continue
            normalized_ports = {port for port in ports if isinstance(port, str) and port}
            if normalized_ports:
                normalized[object_id] = normalized_ports
        return normalized

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        bindings = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(bindings, dict):
            return self.make_result(diagnostics)

        ethernet_inventory: dict[str, set[str]] = {}
        try:
            raw_inventory = self._subscribe_required(
                ctx,
                plugin_id=self._PORT_INVENTORY_PLUGIN_ID,
                published_key=self._PORT_INVENTORY_KEY,
            )
            ethernet_inventory = self._normalize_inventory(raw_inventory)
        except PluginDataExchangeError:
            # Fallback keeps standalone plugin execution deterministic in isolated tests.
            ethernet_inventory = {}
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
                    ethernet_inventory=ethernet_inventory,
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
        ethernet_inventory: dict[str, set[str]],
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
            ethernet_ports = ethernet_inventory.get(object_ref, set()) if isinstance(object_ref, str) else set()
            if not ethernet_ports and isinstance(object_ref, str):
                object_payload = ctx.objects.get(object_ref)
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

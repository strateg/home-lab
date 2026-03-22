"""Global ethernet port inventory publisher for endpoint-aware validators."""

from __future__ import annotations

from typing import Any

from kernel.plugin_base import PluginContext, PluginResult, Stage, ValidatorJsonPlugin


class EthernetPortInventoryValidator(ValidatorJsonPlugin):
    """Publish object ethernet port inventory for lower-level endpoint validators."""

    _PUBLISH_KEY = "ethernet_ports_by_object"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        _ = stage
        diagnostics = []
        inventory: dict[str, list[str]] = {}

        for object_id, payload in ctx.objects.items():
            if not isinstance(object_id, str) or not object_id:
                continue
            if not isinstance(payload, dict):
                continue
            ports = self._extract_ethernet_ports(payload)
            if ports:
                inventory[object_id] = sorted(ports)

        ctx.publish(self._PUBLISH_KEY, inventory)
        return self.make_result(
            diagnostics,
            output_data={
                self._PUBLISH_KEY: inventory,
                "objects_with_ethernet_inventory": len(inventory),
            },
        )

    @staticmethod
    def _extract_ethernet_ports(object_payload: dict[str, Any]) -> set[str]:
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
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if isinstance(name, str) and name:
                ports.add(name)
        return ports

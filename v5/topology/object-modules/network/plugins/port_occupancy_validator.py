"""
Port Occupancy Validator for Physical Links

Policy: Single cable per port (strict enforcement)
- Each endpoint port can have at most ONE physical link attached
- Multiple cables on the same port is rejected with diagnostic E7306

This validator runs after endpoint validation and checks for duplicate port usage
across all cable instances in the compiled model.
"""

from typing import Dict, Set, Tuple

from v5.topology_tools.kernel.plugin_base import PluginDiagnostic, PluginResult, ValidatorPlugin


class PortOccupancyValidator(ValidatorPlugin):
    """Enforce single-cable-per-port policy for physical links."""

    def __init__(self, context):
        super().__init__(context)
        self.port_usage: Dict[Tuple[str, str], str] = {}  # (device, port) -> instance_id

    def execute(self, compiled_json: dict) -> PluginResult:
        """
        Validate that no port is used by multiple physical_link instances.

        Args:
            compiled_json: Compiled effective model

        Returns:
            PluginResult with diagnostics if violations found
        """
        diagnostics = []
        violations = 0

        # Extract all physical_link instances from compiled model
        if "instances" not in compiled_json:
            return self.success_result(output_data={})

        for group_name, instances_in_group in compiled_json["instances"].items():
            if not isinstance(instances_in_group, list):
                continue

            for instance in instances_in_group:
                if instance.get("class_ref") != "class.network.physical_link":
                    continue

                instance_id = instance.get("instance")
                endpoints = [instance.get("endpoint_a"), instance.get("endpoint_b")]

                for endpoint in endpoints:
                    if not endpoint:
                        continue

                    device_ref = endpoint.get("device_ref")
                    port = endpoint.get("port")

                    if not device_ref or not port:
                        continue

                    port_key = (device_ref, port)

                    if port_key in self.port_usage:
                        # Violation: port already used by another cable
                        other_instance = self.port_usage[port_key]
                        violations += 1
                        diagnostics.append(
                            PluginDiagnostic(
                                severity="error",
                                code="E7306",
                                message=f"Port occupancy violation: {device_ref}:{port} already used by {other_instance}, cannot attach {instance_id}",
                                location={
                                    "source_file": f"instances/*/.../{instance_id}.yaml",
                                    "entity": instance_id,
                                    "field": "endpoint_a/endpoint_b",
                                },
                                context={"policy": "single_cable_per_port"},
                            )
                        )
                    else:
                        # Register this port as used by this instance
                        self.port_usage[port_key] = instance_id

        if violations > 0:
            return self.failed_result(
                diagnostics=diagnostics,
                output_data={"port_usage_violations": violations},
            )

        return self.success_result(
            output_data={"port_usage_violations": 0, "ports_validated": len(self.port_usage)},
            diagnostics=diagnostics,
        )

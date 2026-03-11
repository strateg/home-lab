#!/usr/bin/env python3
"""
TUC-0001 Quality Gate: Schema Validation and Reference Resolution

This script validates:
1. Class/object YAML files conform to schema
2. Instance files conform to schema
3. All references (device_ref, link_ref, etc.) resolve to existing entities
4. No dangling cross-layer references
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class TUC0001QualityGate:
    def __init__(self, topology_root: Path):
        self.topology_root = topology_root
        self.errors = []
        self.warnings = []
        self.devices = {}
        self.instances = {}
        self.classes = {}
        self.objects = {}

    def load_instances(self) -> None:
        """Load all instances from sharded tree."""
        instances_root = self.topology_root / "instances"
        if not instances_root.exists():
            self.errors.append(f"Instances root not found: {instances_root}")
            return

        for group_dir in instances_root.iterdir():
            if not group_dir.is_dir() or group_dir.name.startswith("_"):
                continue

            for instance_file in group_dir.glob("*.yaml"):
                try:
                    import yaml

                    with open(instance_file, "r") as f:
                        instance = yaml.safe_load(f)

                    if instance and "instance" in instance:
                        instance_id = instance["instance"]
                        self.instances[instance_id] = {
                            "file": instance_file,
                            "data": instance,
                            "group": group_dir.name,
                        }

                        # Index devices for easy lookup
                        if instance.get("object_ref", "").startswith("class.router") or instance.get(
                            "object_ref", ""
                        ).startswith("obj."):
                            self.devices[instance_id] = instance
                except Exception as e:
                    self.errors.append(f"Failed to parse instance {instance_file}: {e}")

    def validate_references(self) -> None:
        """Validate all cross-references in instances."""
        for instance_id, instance_info in self.instances.items():
            data = instance_info["data"]

            # Check cable endpoints
            if "endpoint_a" in data:
                self._validate_endpoint(instance_id, data["endpoint_a"], "endpoint_a")
            if "endpoint_b" in data:
                self._validate_endpoint(instance_id, data["endpoint_b"], "endpoint_b")

            # Check channel link_ref
            if "link_ref" in data:
                link_ref = data["link_ref"]
                if link_ref not in self.instances:
                    self.errors.append(f"{instance_id}: link_ref '{link_ref}' does not exist")

            # Check cable creates_channel_ref
            if "creates_channel_ref" in data:
                channel_ref = data["creates_channel_ref"]
                if channel_ref not in self.instances:
                    self.errors.append(f"{instance_id}: creates_channel_ref '{channel_ref}' does not exist")

    def _validate_endpoint(self, instance_id: str, endpoint: Dict, field_name: str) -> None:
        """Validate endpoint device_ref and port exist."""
        if not isinstance(endpoint, dict):
            self.errors.append(f"{instance_id}: {field_name} is not a dict")
            return

        device_ref = endpoint.get("device_ref")
        port = endpoint.get("port")

        if not device_ref:
            self.errors.append(f"{instance_id}: {field_name}.device_ref missing")
            return

        if not port:
            self.errors.append(f"{instance_id}: {field_name}.port missing")
            return

        # Check device exists
        if device_ref not in self.devices:
            self.errors.append(f"{instance_id}: {field_name} references unknown device '{device_ref}'")

    def validate_schema(self) -> None:
        """Validate required fields for each instance type."""
        for instance_id, instance_info in self.instances.items():
            data = instance_info["data"]
            object_ref = data.get("object_ref")

            # Cable-specific checks
            if object_ref == "obj.network.ethernet_cable":
                self._validate_cable_schema(instance_id, data)

            # Channel-specific checks
            if object_ref == "obj.network.ethernet_channel":
                self._validate_channel_schema(instance_id, data)

    def validate_port_existence(self) -> None:
        """Validate that endpoints reference existing ports on device objects."""
        # Load router objects to check available ports
        router_objects = {}
        object_modules_root = self.topology_root / "object-modules"

        if object_modules_root.exists():
            for vendor_dir in object_modules_root.iterdir():
                if not vendor_dir.is_dir() or vendor_dir.name.startswith("_"):
                    continue

                for obj_file in vendor_dir.glob("obj.*.yaml"):
                    try:
                        import yaml

                        with open(obj_file, "r") as f:
                            obj = yaml.safe_load(f)

                        if obj and obj.get("class_ref") == "class.router":
                            router_objects[obj.get("object")] = obj
                    except Exception as e:
                        self.errors.append(f"Failed to load router object {obj_file}: {e}")

        # Validate endpoints reference real ports
        for instance_id, instance_info in self.instances.items():
            data = instance_info["data"]
            object_ref = data.get("object_ref")

            if object_ref != "obj.network.ethernet_cable":
                continue

            endpoints = [data.get("endpoint_a"), data.get("endpoint_b")]

            for endpoint_idx, endpoint in enumerate(endpoints):
                if not endpoint:
                    continue

                device_ref = endpoint.get("device_ref")
                port = endpoint.get("port")
                endpoint_name = f"endpoint_{'ab'[endpoint_idx]}"

                if not device_ref or not port:
                    continue

                # Check that device instance exists
                if device_ref not in self.devices:
                    self.errors.append(f"{instance_id}: {endpoint_name}.device_ref '{device_ref}' does not exist")
                    continue

                # Get device object_ref to load its port definitions
                device_obj_ref = self.devices[device_ref].get("object_ref")
                if not device_obj_ref or device_obj_ref not in router_objects:
                    self.errors.append(
                        f"{instance_id}: cannot validate port '{port}' on unknown device object '{device_obj_ref}'"
                    )
                    continue

                # Check that port exists on device object
                device_obj = router_objects[device_obj_ref]
                available_ports = self._extract_ports_from_object(device_obj)

                if port not in available_ports:
                    available_ports_str = ", ".join(sorted(available_ports))
                    self.errors.append(
                        f"{instance_id}: port '{port}' not found on device '{device_ref}' ({device_obj_ref}). Available ports: {available_ports_str}"
                    )

    def _extract_ports_from_object(self, obj: Dict) -> Set[str]:
        """Extract all available port names from a device object."""
        ports = set()
        interfaces = obj.get("hardware_specs", {}).get("interfaces", {})

        for if_type in ["ethernet", "wireless", "cellular", "usb"]:
            if_list = interfaces.get(if_type, [])
            if isinstance(if_list, list):
                for iface in if_list:
                    port_name = iface.get("name")
                    if port_name:
                        ports.add(port_name)

        return ports

    def _validate_cable_schema(self, instance_id: str, data: Dict) -> None:
        """Validate cable instance schema."""
        required = ["endpoint_a", "endpoint_b", "creates_channel_ref", "length_m", "shielding"]
        for field in required:
            if field not in data:
                self.errors.append(f"{instance_id}: cable missing required field '{field}'")

        # Validate enum constraints
        if "shielding" in data and data["shielding"] not in ["utp", "ftp", "stp"]:
            self.errors.append(f"{instance_id}: invalid shielding value '{data['shielding']}'")

        if "category" in data and data["category"] not in ["cat5e", "cat6", "cat6a", "cat7", "cat8"]:
            self.errors.append(f"{instance_id}: invalid cable category '{data['category']}'")

        # Validate numeric ranges
        if "length_m" in data:
            length = data["length_m"]
            if not isinstance(length, (int, float)) or length <= 0 or length > 1000:
                self.errors.append(f"{instance_id}: length_m must be between 0.1 and 1000, got {length}")

    def _validate_channel_schema(self, instance_id: str, data: Dict) -> None:
        """Validate channel instance schema."""
        required = ["endpoint_a", "endpoint_b", "link_ref"]
        for field in required:
            if field not in data:
                self.errors.append(f"{instance_id}: channel missing required field '{field}'")

        # Validate enum constraints
        if "admin_state" in data and data["admin_state"] not in ["up", "down"]:
            self.errors.append(f"{instance_id}: invalid admin_state '{data['admin_state']}'")

        # Validate numeric ranges
        if "negotiated_speed_mbps" in data:
            speed = data["negotiated_speed_mbps"]
            if not isinstance(speed, int) or speed <= 0 or speed > 1000000:
                self.errors.append(f"{instance_id}: negotiated_speed_mbps must be between 1 and 1000000, got {speed}")

    def check_endpoint_consistency(self) -> None:
        """Verify cable and channel endpoints are consistent."""
        for instance_id, instance_info in self.instances.items():
            data = instance_info["data"]

            if data.get("object_ref") != "obj.network.ethernet_cable":
                continue

            cable_endpoints = self._normalize_endpoints(data.get("endpoint_a"), data.get("endpoint_b"))
            channel_ref = data.get("creates_channel_ref")

            if not channel_ref:
                continue

            if channel_ref not in self.instances:
                continue

            channel_data = self.instances[channel_ref]["data"]
            channel_endpoints = self._normalize_endpoints(
                channel_data.get("endpoint_a"), channel_data.get("endpoint_b")
            )

            if cable_endpoints != channel_endpoints:
                self.warnings.append(
                    f"{instance_id}: cable endpoints {cable_endpoints} do not match channel {channel_ref} endpoints {channel_endpoints}"
                )

    def _normalize_endpoints(self, ep_a: Optional[Dict], ep_b: Optional[Dict]) -> str:
        """Normalize endpoints to unordered pair representation."""
        if not ep_a or not ep_b:
            return ""

        pair = tuple(
            sorted(
                [
                    f"{ep_a.get('device_ref')}:{ep_a.get('port')}",
                    f"{ep_b.get('device_ref')}:{ep_b.get('port')}",
                ]
            )
        )
        return "|".join(pair)

    def run(self) -> int:
        """Run all quality gate checks."""
        print("TUC-0001 Quality Gate: Schema & Reference Validation\n")

        self.load_instances()
        print(f"✓ Loaded {len(self.instances)} instances")

        self.validate_schema()
        print(f"✓ Schema validation: {len([e for e in self.errors if 'required' in e or 'invalid' in e])} issues")

        self.validate_references()
        print(f"✓ Reference resolution: {len([e for e in self.errors if 'ref' in e or 'exist' in e])} issues")

        self.validate_port_existence()
        print(f"✓ Port existence validation: {len([e for e in self.errors if 'port' in e.lower()])} issues")

        self.check_endpoint_consistency()
        print(f"✓ Endpoint consistency: {len(self.warnings)} warnings")

        # Report results
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ All quality gates PASSED")
            return 0

        return 1 if self.errors else 0


if __name__ == "__main__":
    topology_root = Path(__file__).parent.parent.parent.parent / "topology"
    gate = TUC0001QualityGate(topology_root)
    sys.exit(gate.run())

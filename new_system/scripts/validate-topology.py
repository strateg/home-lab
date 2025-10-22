#!/usr/bin/env python3
"""
Validate topology.yaml against JSON Schema v7
Provides detailed error messages and validation reports

Usage:
    python3 scripts/validate-topology.py [--topology topology.yaml] [--schema schemas/topology-v2-schema.json]

Requirements:
    pip install jsonschema pyyaml
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Import topology loader with !include support
from topology_loader import load_topology

try:
    from jsonschema import validate, Draft7Validator, ValidationError
    from jsonschema.exceptions import best_match
except ImportError:
    print("❌ Error: jsonschema library not installed")
    print("   Install with: pip install jsonschema")
    sys.exit(1)


class SchemaValidator:
    """Validate topology YAML against JSON Schema"""

    def __init__(self, topology_path: str, schema_path: str):
        self.topology_path = Path(topology_path)
        self.schema_path = Path(schema_path)
        self.topology: Optional[Dict] = None
        self.schema: Optional[Dict] = None
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_files(self) -> bool:
        """Load topology YAML and schema JSON"""
        # Load topology (with !include support)
        try:
            self.topology = load_topology(str(self.topology_path))
            print(f"✓ Loaded topology: {self.topology_path}")
        except FileNotFoundError:
            self.errors.append(f"Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error: {e}")
            return False

        # Load schema
        try:
            with open(self.schema_path) as f:
                self.schema = json.load(f)
            print(f"✓ Loaded schema: {self.schema_path}")
        except FileNotFoundError:
            self.errors.append(f"Schema file not found: {self.schema_path}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON schema parse error: {e}")
            return False

        return True

    def validate_schema(self) -> bool:
        """Validate topology against schema"""
        if not self.topology or not self.schema:
            self.errors.append("Topology or schema not loaded")
            return False

        validator = Draft7Validator(self.schema)

        # Collect all validation errors
        errors_found = False
        for error in sorted(validator.iter_errors(self.topology), key=str):
            errors_found = True
            self._format_error(error)

        return not errors_found

    def _format_error(self, error: ValidationError) -> None:
        """Format validation error for display"""
        # Build path to error
        path = " → ".join([str(p) for p in error.absolute_path]) if error.absolute_path else "root"

        # Error message
        message = error.message

        # Add context
        if error.validator == "required":
            missing_props = error.message.split("'")[1::2]
            self.errors.append(f"Missing required field(s) at '{path}': {', '.join(missing_props)}")

        elif error.validator == "type":
            expected_type = error.validator_value
            self.errors.append(f"Type error at '{path}': expected {expected_type}, got {type(error.instance).__name__}")

        elif error.validator == "pattern":
            pattern = error.validator_value
            value = error.instance
            self.errors.append(f"Pattern mismatch at '{path}': '{value}' does not match pattern '{pattern}'")

        elif error.validator == "enum":
            allowed = error.validator_value
            value = error.instance
            self.errors.append(f"Invalid value at '{path}': '{value}' not in allowed values {allowed}")

        elif error.validator == "minimum" or error.validator == "maximum":
            limit = error.validator_value
            value = error.instance
            self.errors.append(f"Range error at '{path}': {value} violates {error.validator} {limit}")

        else:
            self.errors.append(f"Validation error at '{path}': {message}")

    def check_references(self) -> None:
        """Check that all *_ref fields point to existing IDs"""
        if not self.topology:
            return

        # Collect all IDs
        ids = {
            'devices': set(),
            'networks': set(),
            'bridges': set(),
            'storage': set(),
            'trust_zones': set(),
            'vms': set(),
            'lxc': set(),
            'services': set(),
            'templates': set()
        }

        # Extract device IDs
        for device in self.topology.get('physical_topology', {}).get('devices', []):
            ids['devices'].add(device.get('id'))

        # Extract network IDs
        for network in self.topology.get('logical_topology', {}).get('networks', []):
            ids['networks'].add(network.get('id'))

        # Extract bridge IDs
        for bridge in self.topology.get('logical_topology', {}).get('bridges', []):
            ids['bridges'].add(bridge.get('id'))

        # Extract storage IDs
        for storage in self.topology.get('storage', []):
            ids['storage'].add(storage.get('id'))

        # Extract trust zone IDs
        trust_zones = self.topology.get('logical_topology', {}).get('trust_zones', {})
        ids['trust_zones'] = set(trust_zones.keys())

        # Extract VM IDs
        for vm in self.topology.get('compute', {}).get('vms', []):
            ids['vms'].add(vm.get('id'))

        # Extract LXC IDs
        for lxc in self.topology.get('compute', {}).get('lxc', []):
            ids['lxc'].add(lxc.get('id'))

        # Extract service IDs
        for service in self.topology.get('services', []):
            ids['services'].add(service.get('id'))

        # Extract template IDs
        for tpl in self.topology.get('compute', {}).get('templates', {}).get('lxc', []):
            ids['templates'].add(tpl.get('id'))
        for tpl in self.topology.get('compute', {}).get('templates', {}).get('vms', []):
            ids['templates'].add(tpl.get('id'))

        # Check references
        self._check_network_refs(ids)
        self._check_vm_refs(ids)
        self._check_lxc_refs(ids)
        self._check_service_refs(ids)
        self._check_bridge_refs(ids)

    def _check_network_refs(self, ids: Dict[str, set]) -> None:
        """Check network reference consistency"""
        for network in self.topology.get('logical_topology', {}).get('networks', []):
            net_id = network.get('id')

            # Check trust_zone_ref
            trust_zone_ref = network.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"Network '{net_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            # Check bridge_ref
            bridge_ref = network.get('bridge_ref')
            if bridge_ref and bridge_ref not in ids['bridges']:
                self.errors.append(f"Network '{net_id}': bridge_ref '{bridge_ref}' does not exist")

            # Check managed_by_ref
            managed_by_ref = network.get('managed_by_ref')
            if managed_by_ref:
                all_compute = ids['devices'] | ids['vms'] | ids['lxc']
                if managed_by_ref not in all_compute:
                    self.errors.append(f"Network '{net_id}': managed_by_ref '{managed_by_ref}' does not exist")

    def _check_vm_refs(self, ids: Dict[str, set]) -> None:
        """Check VM reference consistency"""
        for vm in self.topology.get('compute', {}).get('vms', []):
            vm_id = vm.get('id')

            # Check device_ref
            device_ref = vm.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"VM '{vm_id}': device_ref '{device_ref}' does not exist")

            # Check trust_zone_ref
            trust_zone_ref = vm.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"VM '{vm_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            # Check template_ref
            template_ref = vm.get('template_ref')
            if template_ref and template_ref not in ids['templates']:
                self.errors.append(f"VM '{vm_id}': template_ref '{template_ref}' does not exist")

            # Check storage refs
            for disk in vm.get('storage', []):
                storage_ref = disk.get('storage_ref')
                if storage_ref and storage_ref not in ids['storage']:
                    self.errors.append(f"VM '{vm_id}': storage_ref '{storage_ref}' does not exist")

            # Check network refs
            for net in vm.get('networks', []):
                bridge_ref = net.get('bridge_ref')
                if bridge_ref and bridge_ref not in ids['bridges']:
                    self.errors.append(f"VM '{vm_id}': bridge_ref '{bridge_ref}' does not exist")

    def _check_lxc_refs(self, ids: Dict[str, set]) -> None:
        """Check LXC reference consistency"""
        for lxc in self.topology.get('compute', {}).get('lxc', []):
            lxc_id = lxc.get('id')

            # Check device_ref
            device_ref = lxc.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"LXC '{lxc_id}': device_ref '{device_ref}' does not exist")

            # Check trust_zone_ref
            trust_zone_ref = lxc.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"LXC '{lxc_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            # Check template_ref
            template_ref = lxc.get('template_ref')
            if template_ref and template_ref not in ids['templates']:
                self.errors.append(f"LXC '{lxc_id}': template_ref '{template_ref}' does not exist")

            # Check storage refs
            rootfs = lxc.get('storage', {}).get('rootfs', {})
            storage_ref = rootfs.get('storage_ref')
            if storage_ref and storage_ref not in ids['storage']:
                self.errors.append(f"LXC '{lxc_id}': rootfs storage_ref '{storage_ref}' does not exist")

    def _check_service_refs(self, ids: Dict[str, set]) -> None:
        """Check service reference consistency"""
        for service in self.topology.get('services', []):
            svc_id = service.get('id')

            # Check device_ref
            device_ref = service.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"Service '{svc_id}': device_ref '{device_ref}' does not exist")

            # Check vm_ref
            vm_ref = service.get('vm_ref')
            if vm_ref and vm_ref not in ids['vms']:
                self.errors.append(f"Service '{svc_id}': vm_ref '{vm_ref}' does not exist")

            # Check lxc_ref
            lxc_ref = service.get('lxc_ref')
            if lxc_ref and lxc_ref not in ids['lxc']:
                self.errors.append(f"Service '{svc_id}': lxc_ref '{lxc_ref}' does not exist")

            # Check network_ref
            network_ref = service.get('network_ref')
            if network_ref and network_ref not in ids['networks']:
                self.errors.append(f"Service '{svc_id}': network_ref '{network_ref}' does not exist")

            # Check trust_zone_ref
            trust_zone_ref = service.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"Service '{svc_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

    def _check_bridge_refs(self, ids: Dict[str, set]) -> None:
        """Check bridge reference consistency"""
        for bridge in self.topology.get('logical_topology', {}).get('bridges', []):
            bridge_id = bridge.get('id')

            # Check device_ref
            device_ref = bridge.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"Bridge '{bridge_id}': device_ref '{device_ref}' does not exist")

            # Check network_ref
            network_ref = bridge.get('network_ref')
            if network_ref and network_ref not in ids['networks']:
                self.errors.append(f"Bridge '{bridge_id}': network_ref '{network_ref}' does not exist")

    def print_results(self) -> None:
        """Print validation results"""
        print("\n" + "="*70)

        if self.errors:
            print(f"❌ Validation FAILED - {len(self.errors)} error(s) found")
            print("="*70)
            print("\nErrors:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        else:
            print("✅ Validation PASSED")
            print("="*70)
            print("\n✓ Topology is valid according to JSON Schema v7")
            print("✓ All references are consistent")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  - {warning}")

    def validate(self) -> bool:
        """Run full validation"""
        print("="*70)
        print("Topology Schema Validation (JSON Schema v7)")
        print("="*70)
        print()

        # Load files
        if not self.load_files():
            return False

        # Schema validation
        print("\n📋 Step 1: Validating against JSON Schema...")
        schema_valid = self.validate_schema()

        if schema_valid:
            print("✓ Schema validation passed")
        else:
            print(f"✗ Schema validation failed ({len(self.errors)} errors)")

        # Reference validation
        if schema_valid:
            print("\n🔗 Step 2: Checking reference consistency...")
            self.check_references()

            if not self.errors:
                print("✓ All references are valid")
            else:
                print(f"✗ Reference validation failed ({len(self.errors)} errors)")

        return len(self.errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate topology.yaml against JSON Schema v7"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--schema",
        default="schemas/topology-v2-schema.json",
        help="Path to JSON Schema file"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    validator = SchemaValidator(args.topology, args.schema)
    valid = validator.validate()
    validator.print_results()

    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()

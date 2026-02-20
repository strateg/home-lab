#!/usr/bin/env python3
"""
Validate topology.yaml against JSON Schema v7 (v4 layered topology)
Provides detailed error messages and validation reports

Usage:
    python3 scripts/validate-topology.py [--topology topology.yaml] [--schema schemas/topology-v4-schema.json]

Requirements:
    pip install jsonschema pyyaml
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set

# Import topology loader with !include support
from topology_loader import load_topology

try:
    from jsonschema import Draft7Validator, ValidationError
except ImportError:
    print("ERROR Error: jsonschema library not installed")
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
        try:
            self.topology = load_topology(str(self.topology_path))
            print(f"OK Loaded topology: {self.topology_path}")
        except FileNotFoundError:
            self.errors.append(f"Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error: {e}")
            return False

        try:
            with open(self.schema_path) as f:
                self.schema = json.load(f)
            print(f"OK Loaded schema: {self.schema_path}")
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

        errors_found = False
        for error in sorted(validator.iter_errors(self.topology), key=str):
            errors_found = True
            self._format_error(error)

        return not errors_found

    def _format_error(self, error: ValidationError) -> None:
        """Format validation error for display"""
        path = " -> ".join([str(p) for p in error.absolute_path]) if error.absolute_path else "root"
        message = error.message

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
        elif error.validator in ("minimum", "maximum"):
            limit = error.validator_value
            value = error.instance
            self.errors.append(f"Range error at '{path}': {value} violates {error.validator} {limit}")
        else:
            self.errors.append(f"Validation error at '{path}': {message}")

    def _collect_ids(self) -> Dict[str, Set[str]]:
        """Collect IDs by layer for reference validation"""
        ids = {
            'devices': set(),
            'interfaces': set(),
            'networks': set(),
            'bridges': set(),
            'storage': set(),
            'data_assets': set(),
            'trust_zones': set(),
            'network_profiles': set(),
            'vms': set(),
            'lxc': set(),
            'services': set(),
            'templates': set(),
            'security_policies': set(),
        }

        l0 = self.topology.get('L0_meta', {})
        l1 = self.topology.get('L1_foundation', {})
        l2 = self.topology.get('L2_network', {})
        l3 = self.topology.get('L3_data', {})
        l4 = self.topology.get('L4_platform', {})
        l5 = self.topology.get('L5_application', {})

        for policy in l0.get('security_policy', []) or []:
            if isinstance(policy, dict) and policy.get('id'):
                ids['security_policies'].add(policy['id'])

        for device in l1.get('devices', []) or []:
            if isinstance(device, dict) and device.get('id'):
                ids['devices'].add(device['id'])
            for iface in device.get('interfaces', []) or []:
                if isinstance(iface, dict) and iface.get('id'):
                    ids['interfaces'].add(iface['id'])

        for network in l2.get('networks', []) or []:
            if isinstance(network, dict) and network.get('id'):
                ids['networks'].add(network['id'])

        profiles = l2.get('network_profiles', {}) or {}
        ids['network_profiles'] = set(profiles.keys())

        for bridge in l2.get('bridges', []) or []:
            if isinstance(bridge, dict) and bridge.get('id'):
                ids['bridges'].add(bridge['id'])

        for storage in l3.get('storage', []) or []:
            if isinstance(storage, dict) and storage.get('id'):
                ids['storage'].add(storage['id'])

        for asset in l3.get('data_assets', []) or []:
            if isinstance(asset, dict) and asset.get('id'):
                ids['data_assets'].add(asset['id'])

        trust_zones = l2.get('trust_zones', {}) or {}
        ids['trust_zones'] = set(trust_zones.keys())

        for vm in l4.get('vms', []) or []:
            if isinstance(vm, dict) and vm.get('id'):
                ids['vms'].add(vm['id'])

        for lxc in l4.get('lxc', []) or []:
            if isinstance(lxc, dict) and lxc.get('id'):
                ids['lxc'].add(lxc['id'])

        for svc in l5.get('services', []) or []:
            if isinstance(svc, dict) and svc.get('id'):
                ids['services'].add(svc['id'])

        for tpl in l4.get('templates', {}).get('lxc', []) or []:
            if isinstance(tpl, dict) and tpl.get('id'):
                ids['templates'].add(tpl['id'])
        for tpl in l4.get('templates', {}).get('vms', []) or []:
            if isinstance(tpl, dict) and tpl.get('id'):
                ids['templates'].add(tpl['id'])

        return ids

    def check_references(self) -> None:
        """Check that all *_ref fields point to existing IDs"""
        if not self.topology:
            return

        ids = self._collect_ids()

        self._check_network_refs(ids)
        self._check_bridge_refs(ids)
        self._check_physical_links(ids)
        self._check_vm_refs(ids)
        self._check_lxc_refs(ids)
        self._check_service_refs(ids)
        self._check_dns_refs(ids)
        self._check_certificate_refs(ids)
        self._check_backup_refs(ids)
        self._check_security_policy_refs(ids)
        self._check_vlan_tags()

    def _check_vlan_tags(self) -> None:
        """Check VLAN tags for LXC networks against L2 network definitions"""
        l2 = self.topology.get('L2_network', {})
        l4 = self.topology.get('L4_platform', {})

        networks = {n.get('id'): n for n in l2.get('networks', []) or []}
        bridges = {b.get('id'): b for b in l2.get('bridges', []) or []}

        for lxc in l4.get('lxc', []) or []:
            lxc_id = lxc.get('id', 'unknown')
            for nic in lxc.get('networks', []) or []:
                network_ref = nic.get('network_ref')
                vlan_tag = nic.get('vlan_tag')
                bridge_ref = nic.get('bridge_ref')

                if not network_ref or network_ref not in networks:
                    continue

                network = networks[network_ref]
                network_vlan = network.get('vlan')

                if network_vlan is not None:
                    if vlan_tag is None:
                        self.warnings.append(
                            f"LXC '{lxc_id}': network '{network_ref}' uses VLAN {network_vlan} "
                            "but vlan_tag is not set"
                        )
                    elif vlan_tag != network_vlan:
                        self.errors.append(
                            f"LXC '{lxc_id}': vlan_tag {vlan_tag} does not match network '{network_ref}' VLAN {network_vlan}"
                        )
                elif vlan_tag is not None:
                    self.warnings.append(
                        f"LXC '{lxc_id}': vlan_tag {vlan_tag} set but network '{network_ref}' has no VLAN"
                    )

                bridge = bridges.get(bridge_ref) if bridge_ref else None
                if vlan_tag is not None and bridge and bridge.get('vlan_aware') is False:
                    self.warnings.append(
                        f"LXC '{lxc_id}': vlan_tag {vlan_tag} used on non-vlan-aware bridge '{bridge_ref}'"
                    )

    def _check_network_refs(self, ids: Dict[str, Set[str]]) -> None:
        l2 = self.topology.get('L2_network', {})
        for network in l2.get('networks', []) or []:
            net_id = network.get('id')

            trust_zone_ref = network.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"Network '{net_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            profile_ref = network.get('profile_ref')
            if profile_ref and profile_ref not in ids['network_profiles']:
                self.errors.append(f"Network '{net_id}': profile_ref '{profile_ref}' does not exist")

            if not profile_ref:
                required_virtual_fields = ['network_plane', 'segmentation_type', 'transport', 'volatility']
                missing = [f for f in required_virtual_fields if network.get(f) in (None, [], '')]
                if missing:
                    self.warnings.append(
                        f"Network '{net_id}': no profile_ref and missing fields for analysis: {', '.join(missing)}"
                    )

            bridge_ref = network.get('bridge_ref')
            if bridge_ref and bridge_ref not in ids['bridges']:
                self.errors.append(f"Network '{net_id}': bridge_ref '{bridge_ref}' does not exist")

            managed_by_ref = network.get('managed_by_ref')
            if managed_by_ref and managed_by_ref not in ids['devices']:
                self.errors.append(f"Network '{net_id}': managed_by_ref '{managed_by_ref}' does not exist or is not a device")

            interface_ref = network.get('interface_ref')
            if interface_ref and interface_ref not in ids['interfaces']:
                self.errors.append(f"Network '{net_id}': interface_ref '{interface_ref}' does not exist")

    def _check_bridge_refs(self, ids: Dict[str, Set[str]]) -> None:
        l2 = self.topology.get('L2_network', {})
        for bridge in l2.get('bridges', []) or []:
            bridge_id = bridge.get('id')
            device_ref = bridge.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"Bridge '{bridge_id}': device_ref '{device_ref}' does not exist")

            network_ref = bridge.get('network_ref')
            if network_ref and network_ref not in ids['networks']:
                self.errors.append(f"Bridge '{bridge_id}': network_ref '{network_ref}' does not exist")

            for port in bridge.get('ports', []) or []:
                if port not in ids['interfaces']:
                    self.errors.append(f"Bridge '{bridge_id}': port '{port}' does not exist in device interfaces")

    def _check_physical_links(self, ids: Dict[str, Set[str]]) -> None:
        l1 = self.topology.get('L1_foundation', {})
        links = l1.get('physical_links', []) or []
        if not links:
            return

        interface_owner = {}
        for device in l1.get('devices', []) or []:
            device_id = device.get('id')
            for iface in device.get('interfaces', []) or []:
                iface_id = iface.get('id')
                if iface_id:
                    interface_owner[iface_id] = device_id

        for link in links:
            link_id = link.get('id', 'unknown')
            for endpoint_key in ('endpoint_a', 'endpoint_b'):
                endpoint = link.get(endpoint_key, {}) or {}
                device_ref = endpoint.get('device_ref')
                interface_ref = endpoint.get('interface_ref')
                external_ref = endpoint.get('external_ref')

                if device_ref and device_ref not in ids['devices']:
                    self.errors.append(
                        f"Physical link '{link_id}' {endpoint_key}: device_ref '{device_ref}' does not exist"
                    )

                if interface_ref and interface_ref not in ids['interfaces']:
                    self.errors.append(
                        f"Physical link '{link_id}' {endpoint_key}: interface_ref '{interface_ref}' does not exist"
                    )

                if device_ref and interface_ref in interface_owner and interface_owner[interface_ref] != device_ref:
                    owner = interface_owner[interface_ref]
                    self.errors.append(
                        f"Physical link '{link_id}' {endpoint_key}: interface_ref '{interface_ref}' "
                        f"belongs to '{owner}', not '{device_ref}'"
                    )

                if not device_ref and not external_ref:
                    self.errors.append(
                        f"Physical link '{link_id}' {endpoint_key}: either device_ref or external_ref is required"
                    )

    def _check_vm_refs(self, ids: Dict[str, Set[str]]) -> None:
        l4 = self.topology.get('L4_platform', {})
        for vm in l4.get('vms', []) or []:
            vm_id = vm.get('id')
            device_ref = vm.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"VM '{vm_id}': device_ref '{device_ref}' does not exist")

            trust_zone_ref = vm.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"VM '{vm_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            template_ref = vm.get('template_ref')
            if template_ref and template_ref not in ids['templates']:
                self.errors.append(f"VM '{vm_id}': template_ref '{template_ref}' does not exist")

            for disk in vm.get('storage', []) or []:
                storage_ref = disk.get('storage_ref')
                if storage_ref and storage_ref not in ids['storage']:
                    self.errors.append(f"VM '{vm_id}': storage_ref '{storage_ref}' does not exist")

            for net in vm.get('networks', []) or []:
                bridge_ref = net.get('bridge_ref')
                if bridge_ref and bridge_ref not in ids['bridges']:
                    self.errors.append(f"VM '{vm_id}': bridge_ref '{bridge_ref}' does not exist")

    def _check_lxc_refs(self, ids: Dict[str, Set[str]]) -> None:
        l4 = self.topology.get('L4_platform', {})
        for lxc in l4.get('lxc', []) or []:
            lxc_id = lxc.get('id')
            device_ref = lxc.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"LXC '{lxc_id}': device_ref '{device_ref}' does not exist")

            trust_zone_ref = lxc.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"LXC '{lxc_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            template_ref = lxc.get('template_ref')
            if template_ref and template_ref not in ids['templates']:
                self.errors.append(f"LXC '{lxc_id}': template_ref '{template_ref}' does not exist")

            rootfs = lxc.get('storage', {}).get('rootfs', {})
            storage_ref = rootfs.get('storage_ref')
            if storage_ref and storage_ref not in ids['storage']:
                self.errors.append(f"LXC '{lxc_id}': rootfs storage_ref '{storage_ref}' does not exist")

            for net in lxc.get('networks', []) or []:
                bridge_ref = net.get('bridge_ref')
                if bridge_ref and bridge_ref not in ids['bridges']:
                    self.errors.append(f"LXC '{lxc_id}': bridge_ref '{bridge_ref}' does not exist")

    def _check_service_refs(self, ids: Dict[str, Set[str]]) -> None:
        l5 = self.topology.get('L5_application', {})
        for service in l5.get('services', []) or []:
            if not isinstance(service, dict):
                continue
            svc_id = service.get('id')

            device_ref = service.get('device_ref')
            if device_ref and device_ref not in ids['devices']:
                self.errors.append(f"Service '{svc_id}': device_ref '{device_ref}' does not exist")

            vm_ref = service.get('vm_ref')
            if vm_ref and vm_ref not in ids['vms']:
                self.errors.append(f"Service '{svc_id}': vm_ref '{vm_ref}' does not exist")

            lxc_ref = service.get('lxc_ref')
            if lxc_ref and lxc_ref not in ids['lxc']:
                self.errors.append(f"Service '{svc_id}': lxc_ref '{lxc_ref}' does not exist")

            network_ref = service.get('network_ref')
            if network_ref and network_ref not in ids['networks']:
                self.errors.append(f"Service '{svc_id}': network_ref '{network_ref}' does not exist")

            trust_zone_ref = service.get('trust_zone_ref')
            if trust_zone_ref and trust_zone_ref not in ids['trust_zones']:
                self.errors.append(f"Service '{svc_id}': trust_zone_ref '{trust_zone_ref}' does not exist")

            for dep in service.get('dependencies', []) or []:
                dep_ref = dep.get('service_ref')
                if dep_ref and dep_ref not in ids['services']:
                    self.errors.append(f"Service '{svc_id}': dependency service_ref '{dep_ref}' does not exist")

    def _check_dns_refs(self, ids: Dict[str, Set[str]]) -> None:
        l5 = self.topology.get('L5_application', {})
        dns = l5.get('dns', {})
        for zone in dns.get('zones', []) or []:
            for record in zone.get('records', []) or []:
                device_ref = record.get('device_ref')
                if device_ref and device_ref not in ids['devices']:
                    self.errors.append(f"DNS record '{record.get('name')}' references unknown device_ref '{device_ref}'")
                lxc_ref = record.get('lxc_ref')
                if lxc_ref and lxc_ref not in ids['lxc']:
                    self.errors.append(f"DNS record '{record.get('name')}' references unknown lxc_ref '{lxc_ref}'")
                service_ref = record.get('service_ref')
                if service_ref and service_ref not in ids['services']:
                    self.errors.append(f"DNS record '{record.get('name')}' references unknown service_ref '{service_ref}'")

    def _check_certificate_refs(self, ids: Dict[str, Set[str]]) -> None:
        l5 = self.topology.get('L5_application', {})
        certs = l5.get('certificates', {})
        for cert in certs.get('certificates', []) or []:
            service_ref = cert.get('service_ref')
            if service_ref and service_ref not in ids['services']:
                self.errors.append(f"Certificate '{cert.get('id')}' references unknown service_ref '{service_ref}'")
        for cert in certs.get('additional', []) or []:
            for used in cert.get('used_by', []) or []:
                service_ref = used.get('service_ref')
                if service_ref and service_ref not in ids['services']:
                    self.errors.append(f"Certificate '{cert.get('id')}' references unknown service_ref '{service_ref}'")

    def _check_backup_refs(self, ids: Dict[str, Set[str]]) -> None:
        l7 = self.topology.get('L7_operations', {})
        backup = l7.get('backup', {})
        for policy in backup.get('policies', []) or []:
            for target in policy.get('targets', []) or []:
                device_ref = target.get('device_ref')
                if device_ref and device_ref not in ids['devices']:
                    self.errors.append(f"Backup '{policy.get('id')}': device_ref '{device_ref}' does not exist")
                lxc_ref = target.get('lxc_ref')
                if lxc_ref and lxc_ref not in ids['lxc']:
                    self.errors.append(f"Backup '{policy.get('id')}': lxc_ref '{lxc_ref}' does not exist")
                data_asset_ref = target.get('data_asset_ref')
                if data_asset_ref and data_asset_ref not in ids['data_assets']:
                    self.errors.append(f"Backup '{policy.get('id')}': data_asset_ref '{data_asset_ref}' does not exist")

    def _check_security_policy_refs(self, ids: Dict[str, Set[str]]) -> None:
        l2 = self.topology.get('L2_network', {})
        l5 = self.topology.get('L5_application', {})
        l7 = self.topology.get('L7_operations', {})
        valid = ids['security_policies']

        for policy in l2.get('firewall_policies', []) or []:
            ref = policy.get('security_policy_ref')
            if ref and ref not in valid:
                self.errors.append(f"Firewall policy '{policy.get('id')}': security_policy_ref '{ref}' does not exist")

        for svc in l5.get('services', []) or []:
            ref = svc.get('security_policy_ref')
            if ref and ref not in valid:
                self.errors.append(f"Service '{svc.get('id')}': security_policy_ref '{ref}' does not exist")

        backup = l7.get('backup', {})
        for policy in backup.get('policies', []) or []:
            ref = policy.get('security_policy_ref')
            if ref and ref not in valid:
                self.errors.append(f"Backup '{policy.get('id')}': security_policy_ref '{ref}' does not exist")

    def check_version(self) -> None:
        """Check topology version compatibility"""
        if not self.topology:
            return

        version = self.topology.get('L0_meta', {}).get('version', '')
        if not version:
            self.warnings.append("No version specified in L0_meta")
            return

        if not version.startswith('4.'):
            self.errors.append(f"Unsupported topology version: {version} (expected 4.x)")

    def check_ip_overlaps(self) -> None:
        """Check for duplicate/overlapping IP addresses"""
        if not self.topology:
            return

        ip_allocations = {}
        global_ips = {}

        for network in self.topology.get('L2_network', {}).get('networks', []) or []:
            net_id = network.get('id', 'unknown')
            ip_allocations[net_id] = {}

            for alloc in network.get('ip_allocations', []) or []:
                ip = alloc.get('ip', '')
                device_ref = alloc.get('device_ref') or alloc.get('vm_ref') or alloc.get('lxc_ref') or 'unknown'
                ip_addr = ip.split('/')[0] if ip else ''
                if not ip_addr:
                    continue

                if ip_addr in ip_allocations[net_id]:
                    existing = ip_allocations[net_id][ip_addr]
                    self.errors.append(
                        f"Duplicate IP in network '{net_id}': {ip_addr} assigned to both "
                        f"'{existing}' and '{device_ref}'"
                    )
                else:
                    ip_allocations[net_id][ip_addr] = device_ref

                if ip_addr not in global_ips:
                    global_ips[ip_addr] = []
                global_ips[ip_addr].append((net_id, device_ref))

        for lxc in self.topology.get('L4_platform', {}).get('lxc', []) or []:
            lxc_id = lxc.get('id', 'unknown')
            for net in lxc.get('networks', []) or []:
                ip = net.get('ip', '')
                ip_addr = ip.split('/')[0] if ip else ''
                if ip_addr:
                    global_ips.setdefault(ip_addr, []).append(('lxc-config', lxc_id))

        for vm in self.topology.get('L4_platform', {}).get('vms', []) or []:
            vm_id = vm.get('id', 'unknown')
            for net in vm.get('networks', []) or []:
                ip_config = net.get('ip_config', {})
                if isinstance(ip_config, dict):
                    ip = ip_config.get('address', '')
                    ip_addr = ip.split('/')[0] if ip else ''
                    if ip_addr:
                        global_ips.setdefault(ip_addr, []).append(('vm-config', vm_id))

        for ip_addr, locations in global_ips.items():
            if len(locations) >= 2:
                loc_str = ', '.join([f"{net}:{dev}" for net, dev in locations])
                self.warnings.append(f"IP {ip_addr} appears in {len(locations)} places: {loc_str}")

    def print_results(self) -> None:
        """Print validation results"""
        print("\n" + "="*70)

        if self.errors:
            print(f"ERROR Validation FAILED - {len(self.errors)} error(s) found")
            print("="*70)
            print("\nErrors:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        else:
            print("OK Validation PASSED")
            print("="*70)
            print("\nOK Topology version is compatible")
            print("OK Topology is valid according to JSON Schema v7")
            print("OK All references are consistent")
            print("OK No IP address conflicts")

        if self.warnings:
            print(f"\nWARN  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  - {warning}")

    def validate(self) -> bool:
        """Run full validation"""
        print("="*70)
        print("Topology Schema Validation (JSON Schema v7)")
        print("="*70)
        print()

        if not self.load_files():
            return False

        print("\nTAG  Step 1: Checking topology version...")
        self.check_version()
        version = self.topology.get('L0_meta', {}).get('version', 'unknown')
        print(f"OK Topology version: {version}")

        print("\nSTEP Step 2: Validating against JSON Schema...")
        schema_valid = self.validate_schema()

        if schema_valid:
            print("OK Schema validation passed")
        else:
            print(f"X Schema validation failed ({len(self.errors)} errors)")

        if schema_valid:
            print("\nREF Step 3: Checking reference consistency...")
            errors_before = len(self.errors)
            self.check_references()

            if len(self.errors) == errors_before:
                print("OK All references are valid")
            else:
                print(f"X Reference validation failed ({len(self.errors) - errors_before} errors)")

        if schema_valid:
            print("\nNET Step 4: Checking for IP address conflicts...")
            errors_before = len(self.errors)
            self.check_ip_overlaps()

            if len(self.errors) == errors_before:
                print("OK No IP address conflicts found")
            else:
                print(f"X IP conflicts found ({len(self.errors) - errors_before} errors)")

        return len(self.errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate topology.yaml against JSON Schema v7 (v4 layered)"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--schema",
        default="schemas/topology-v4-schema.json",
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

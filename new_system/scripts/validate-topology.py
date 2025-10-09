#!/usr/bin/env python3
"""
Validate topology.yaml schema and consistency

Usage:
    python3 scripts/validate-topology.py [--topology topology.yaml]

Exit codes:
    0: Valid
    1: Validation errors
"""
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Set
import ipaddress


class TopologyValidator:
    def __init__(self, topology_path: str = "topology.yaml"):
        self.topology_path = Path(topology_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.topology: Dict = {}

    def load_topology(self) -> bool:
        """Load and parse YAML file"""
        try:
            with open(self.topology_path) as f:
                self.topology = yaml.safe_load(f)
            return True
        except FileNotFoundError:
            self.errors.append(f"Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parse error: {e}")
            return False

    def validate_required_sections(self) -> None:
        """Check required top-level sections exist"""
        required = ["metadata", "bridges", "networks", "storage"]
        recommended = ["trust_zones", "vms", "lxc", "services"]

        for section in required:
            if section not in self.topology:
                self.errors.append(f"Missing required section: {section}")

        for section in recommended:
            if section not in self.topology:
                self.warnings.append(f"Missing recommended section: {section}")

    def validate_metadata(self) -> None:
        """Check metadata completeness"""
        metadata = self.topology.get("metadata", {})
        required_fields = ["org", "environment", "author", "version"]

        for field in required_fields:
            if field not in metadata:
                self.warnings.append(f"Metadata missing recommended field: {field}")

    def validate_ip_uniqueness(self) -> None:
        """Check for IP address conflicts"""
        ip_allocations: Dict[str, List[str]] = {}

        # Check bridge IPs
        for bridge_name, bridge in self.topology.get("bridges", {}).items():
            addr = bridge.get("address")
            if addr and addr != "dhcp":
                try:
                    ip = addr.split("/")[0]
                    if ip in ip_allocations:
                        ip_allocations[ip].append(f"bridge {bridge_name}")
                    else:
                        ip_allocations[ip] = [f"bridge {bridge_name}"]
                except (ValueError, IndexError):
                    self.errors.append(f"Invalid IP format in bridge {bridge_name}: {addr}")

        # Check VM network IPs
        for vm_name, vm in self.topology.get("vms", {}).items():
            for net_name, net in vm.get("networks", {}).items():
                ip_config = net.get("ip_config")
                if isinstance(ip_config, dict):
                    addr = ip_config.get("address")
                    if addr:
                        try:
                            ip = addr.split("/")[0]
                            if ip in ip_allocations:
                                ip_allocations[ip].append(f"VM {vm_name} {net_name}")
                            else:
                                ip_allocations[ip] = [f"VM {vm_name} {net_name}"]
                        except (ValueError, IndexError):
                            self.errors.append(f"Invalid IP in VM {vm_name} {net_name}: {addr}")

        # Check LXC IPs
        for lxc_name, lxc in self.topology.get("lxc", {}).items():
            net = lxc.get("network", {})
            ip = net.get("ip", "").split("/")[0] if net.get("ip") else None
            if ip:
                if ip in ip_allocations:
                    ip_allocations[ip].append(f"LXC {lxc_name}")
                else:
                    ip_allocations[ip] = [f"LXC {lxc_name}"]

        # Report conflicts
        for ip, locations in ip_allocations.items():
            if len(locations) > 1:
                self.errors.append(f"IP conflict {ip}: {', '.join(locations)}")

    def validate_vmid_uniqueness(self) -> None:
        """Check VMID uniqueness across VMs, LXC, and templates"""
        vmids: Dict[int, List[str]] = {}

        # Check VMs
        for vm_name, vm in self.topology.get("vms", {}).items():
            vmid = vm.get("vmid")
            if vmid:
                if vmid in vmids:
                    vmids[vmid].append(f"VM {vm_name}")
                else:
                    vmids[vmid] = [f"VM {vm_name}"]

        # Check LXC
        for lxc_name, lxc in self.topology.get("lxc", {}).items():
            vmid = lxc.get("vmid")
            if vmid:
                if vmid in vmids:
                    vmids[vmid].append(f"LXC {lxc_name}")
                else:
                    vmids[vmid] = [f"LXC {lxc_name}"]

        # Check templates
        for template_name, template in self.topology.get("templates", {}).get("lxc", {}).items():
            vmid = template.get("vmid")
            if vmid:
                if vmid in vmids:
                    vmids[vmid].append(f"LXC template {template_name}")
                else:
                    vmids[vmid] = [f"LXC template {template_name}"]

        for template_name, template in self.topology.get("templates", {}).get("vms", {}).items():
            vmid = template.get("vmid")
            if vmid:
                if vmid in vmids:
                    vmids[vmid].append(f"VM template {template_name}")
                else:
                    vmids[vmid] = [f"VM template {template_name}"]

        # Report conflicts
        for vmid, locations in vmids.items():
            if len(locations) > 1:
                self.errors.append(f"VMID conflict {vmid}: {', '.join(locations)}")

    def validate_network_cidrs(self) -> None:
        """Check for CIDR overlaps"""
        networks = []
        for net_name, net in self.topology.get("networks", {}).items():
            cidr = net.get("cidr")
            if cidr:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    networks.append((net_name, network))
                except ValueError as e:
                    self.errors.append(f"Invalid CIDR in network {net_name}: {cidr} ({e})")

        # Check overlaps
        for i, (name1, net1) in enumerate(networks):
            for name2, net2 in networks[i+1:]:
                if net1.overlaps(net2):
                    self.warnings.append(f"Network overlap: {name1} ({net1}) and {name2} ({net2})")

    def validate_bridge_references(self) -> None:
        """Check that bridge references are valid"""
        defined_bridges = set(self.topology.get("bridges", {}).keys())

        # Check VM network attachments
        for vm_name, vm in self.topology.get("vms", {}).items():
            for net_name, net in vm.get("networks", {}).items():
                bridge = net.get("bridge")
                if bridge and bridge not in defined_bridges:
                    self.errors.append(f"VM {vm_name} {net_name}: undefined bridge '{bridge}'")

        # Check LXC network attachments
        for lxc_name, lxc in self.topology.get("lxc", {}).items():
            net = lxc.get("network", {})
            bridge = net.get("bridge")
            if bridge and bridge not in defined_bridges:
                self.errors.append(f"LXC {lxc_name}: undefined bridge '{bridge}'")

    def validate_storage_references(self) -> None:
        """Check that storage references are valid"""
        defined_storage = set(self.topology.get("storage", {}).keys())

        # Check VMs
        for vm_name, vm in self.topology.get("vms", {}).items():
            for disk_name, disk in vm.get("disks", {}).items():
                storage = disk.get("storage")
                if storage and storage not in defined_storage:
                    self.errors.append(f"VM {vm_name} {disk_name}: undefined storage '{storage}'")

        # Check LXC
        for lxc_name, lxc in self.topology.get("lxc", {}).items():
            rootfs = lxc.get("rootfs", {})
            storage = rootfs.get("storage")
            if storage and storage not in defined_storage:
                self.errors.append(f"LXC {lxc_name} rootfs: undefined storage '{storage}'")

            for mp_name, mp in lxc.get("mountpoints", {}).items():
                storage = mp.get("storage")
                if storage and storage not in defined_storage:
                    self.errors.append(f"LXC {lxc_name} {mp_name}: undefined storage '{storage}'")

    def validate_trust_zones(self) -> None:
        """Check trust zone definitions and references"""
        defined_zones = set(self.topology.get("trust_zones", {}).keys())

        if not defined_zones:
            self.warnings.append("No trust zones defined - consider adding for security boundaries")
            return

        # Check that zones have required fields
        for zone_id, zone in self.topology.get("trust_zones", {}).items():
            if "name" not in zone:
                self.warnings.append(f"Trust zone '{zone_id}' missing 'name' field")
            if "security_level" not in zone:
                self.warnings.append(f"Trust zone '{zone_id}' missing 'security_level' field")

        # Check network trust_zone references
        for net_id, network in self.topology.get("networks", {}).items():
            trust_zone = network.get("trust_zone")
            if trust_zone:
                if trust_zone not in defined_zones:
                    self.errors.append(f"Network '{net_id}': undefined trust_zone '{trust_zone}'")
            else:
                self.warnings.append(f"Network '{net_id}' has no trust_zone assigned")

        # Check service trust_zone references
        for svc_id, service in self.topology.get("services", {}).items():
            trust_zone = service.get("trust_zone")
            if trust_zone and trust_zone not in defined_zones:
                self.errors.append(f"Service '{svc_id}': undefined trust_zone '{trust_zone}'")

    def validate_network_bridge_consistency(self) -> None:
        """Check that networks reference correct bridges"""
        defined_bridges = set(self.topology.get("bridges", {}).keys())

        for net_id, network in self.topology.get("networks", {}).items():
            bridge = network.get("bridge")
            if bridge and bridge not in defined_bridges:
                self.errors.append(f"Network '{net_id}': undefined bridge '{bridge}'")

    def validate(self) -> bool:
        """Run all validations"""
        if not self.load_topology():
            return False

        self.validate_required_sections()
        self.validate_metadata()
        self.validate_trust_zones()
        self.validate_network_bridge_consistency()
        self.validate_ip_uniqueness()
        self.validate_vmid_uniqueness()
        self.validate_network_cidrs()
        self.validate_bridge_references()
        self.validate_storage_references()

        return len(self.errors) == 0

    def print_results(self) -> None:
        """Print validation results"""
        if self.warnings:
            print("⚠ Warnings:")
            for warning in self.warnings:
                print(f"  - {warning}")
            print()

        if self.errors:
            print("✗ Validation errors:")
            for error in self.errors:
                print(f"  - {error}")
            print()
            print(f"Found {len(self.errors)} error(s)")
        else:
            print("✓ Topology validation passed")
            if self.warnings:
                print(f"  ({len(self.warnings)} warning(s))")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate topology.yaml")
    parser.add_argument("--topology", default="topology.yaml", help="Path to topology.yaml")
    args = parser.parse_args()

    validator = TopologyValidator(args.topology)
    valid = validator.validate()
    validator.print_results()

    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()

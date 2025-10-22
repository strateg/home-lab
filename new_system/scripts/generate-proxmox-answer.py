#!/usr/bin/env python3
"""
Generate Proxmox auto-install answer.toml from topology.yaml
Extracts Proxmox node configuration and generates answer file for unattended installation

Usage:
    python3 generate-proxmox-answer.py [topology.yaml] [output.toml]

Example:
    python3 generate-proxmox-answer.py ../topology.yaml ../bare-metal/answer.toml
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from topology_loader import load_topology


class ProxmoxAnswerGenerator:
    """Generate Proxmox answer.toml from topology.yaml"""

    def __init__(self, topology_path: str):
        """
        Initialize generator

        Args:
            topology_path: Path to topology.yaml
        """
        self.topology_path = Path(topology_path)
        self.topology = load_topology(str(topology_path))
        self.proxmox_node = self._extract_proxmox_node()
        self.validation_errors = []
        self.validation_warnings = []

    def _extract_proxmox_node(self) -> Optional[Dict[str, Any]]:
        """Extract Proxmox hypervisor node from topology"""
        devices = self.topology.get('physical_topology', {}).get('devices', [])

        for device in devices:
            # Find hypervisor device (role can be 'compute', 'proxmox-ve', or 'hypervisor')
            if device.get('type') == 'hypervisor':
                return device

        return None

    def _get_primary_disk(self) -> str:
        """Get primary disk for system installation (SSD)"""
        if not self.proxmox_node:
            return "sda"

        disks = self.proxmox_node.get('specs', {}).get('disks', [])

        # Find SSD for system installation
        for disk in disks:
            if disk.get('type') == 'ssd':
                # Extract device name from path (/dev/sda -> sda)
                device_path = disk.get('device', '/dev/sda')
                return device_path.replace('/dev/', '')

        # Fallback: first disk
        if disks:
            device_path = disks[0].get('device', '/dev/sda')
            return device_path.replace('/dev/', '')

        return "sda"

    def _get_hostname(self) -> str:
        """Get FQDN from topology"""
        if not self.proxmox_node:
            return "proxmox.home.local"

        # Get domain from DNS zone (default: home.local)
        dns_zones = self.topology.get('logical_topology', {}).get('dns', {}).get('zones', [])
        domain = 'home.local'
        if dns_zones:
            domain = dns_zones[0].get('domain', 'home.local')

        # Construct FQDN: {node_id}.{domain}
        node_id = self.proxmox_node.get('id', 'proxmox')
        return f"{node_id}.{domain}"

    def _get_management_ip(self) -> Optional[Dict[str, str]]:
        """
        Extract management network IP configuration for Proxmox node
        Returns dict with 'ip', 'gateway', 'dns' or None for DHCP
        """
        networks = self.topology.get('logical_topology', {}).get('networks', [])

        # Find management network
        mgmt_network = None
        for net in networks:
            if net.get('id') == 'net-management':
                mgmt_network = net
                break

        if not mgmt_network:
            return None

        # Find Proxmox node IP allocation
        allocations = mgmt_network.get('ip_allocations', [])
        for alloc in allocations:
            if alloc.get('device_ref') == self.proxmox_node.get('id'):
                # Extract IP from allocation
                ip_cidr = alloc.get('ip')  # e.g., "10.0.99.1/24"
                gateway = mgmt_network.get('gateway', '10.0.99.1')
                dns_servers = mgmt_network.get('dns', ['1.1.1.1', '8.8.8.8'])

                return {
                    'cidr': ip_cidr,
                    'gateway': gateway,
                    'dns': dns_servers[0] if dns_servers else '1.1.1.1'
                }

        return None

    def _get_metadata(self, key: str, default: Any = None) -> Any:
        """Get value from metadata section"""
        return self.topology.get('metadata', {}).get(key, default)

    def validate(self) -> bool:
        """
        Validate topology for Proxmox auto-install requirements

        Returns:
            True if valid, False if critical errors found
        """
        self.validation_errors = []
        self.validation_warnings = []

        # Check Proxmox node exists
        if not self.proxmox_node:
            self.validation_errors.append("No Proxmox hypervisor found in topology")
            return False

        # Check node has ID
        if not self.proxmox_node.get('id'):
            self.validation_errors.append("Proxmox node missing 'id' field")

        # Check disk configuration
        disks = self.proxmox_node.get('specs', {}).get('disks', [])
        if not disks:
            self.validation_errors.append("Proxmox node has no disks defined")
        else:
            # Check for system disk (SSD)
            has_system_disk = any(d.get('type') == 'ssd' for d in disks)
            if not has_system_disk:
                self.validation_warnings.append("No SSD found for system installation, will use first disk")

            # Check disk devices are specified
            for disk in disks:
                if not disk.get('device'):
                    self.validation_warnings.append(f"Disk {disk.get('id', 'unknown')} missing 'device' field")

        # Check network configuration
        networks = self.topology.get('logical_topology', {}).get('networks', [])
        if not networks:
            self.validation_warnings.append("No networks defined in topology")

        # Check DNS zones for hostname domain
        dns_zones = self.topology.get('logical_topology', {}).get('dns', {}).get('zones', [])
        if not dns_zones:
            self.validation_warnings.append("No DNS zones defined, using default 'home.local'")

        # Check management network
        mgmt_network = None
        for net in networks:
            if net.get('id') == 'net-management':
                mgmt_network = net
                break

        if not mgmt_network:
            self.validation_warnings.append("No management network (net-management) found, using DHCP")
        else:
            # Check if Proxmox node has IP allocation
            allocations = mgmt_network.get('ip_allocations', [])
            has_proxmox_ip = any(
                alloc.get('device_ref') == self.proxmox_node.get('id')
                for alloc in allocations
            )
            if not has_proxmox_ip:
                self.validation_warnings.append(
                    f"Proxmox node '{self.proxmox_node.get('id')}' has no IP allocation in management network"
                )

        return len(self.validation_errors) == 0

    def print_validation_results(self):
        """Print validation errors and warnings"""
        if self.validation_errors:
            print("❌ Validation Errors:")
            for error in self.validation_errors:
                print(f"  - {error}")

        if self.validation_warnings:
            print("⚠️  Validation Warnings:")
            for warning in self.validation_warnings:
                print(f"  - {warning}")

        if not self.validation_errors and not self.validation_warnings:
            print("✓ Topology validation passed")

    def _format_toml_section(self, section: str, data: Dict[str, Any]) -> str:
        """Format a TOML section"""
        lines = [f"[{section}]"]

        for key, value in data.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, (int, float)):
                lines.append(f'{key} = {value}')
            elif isinstance(value, list):
                # Format list of strings
                formatted_list = ', '.join(f'"{v}"' for v in value)
                lines.append(f'{key} = [{formatted_list}]')
            elif isinstance(value, bool):
                lines.append(f'{key} = {str(value).lower()}')

        return '\n'.join(lines)

    def generate(self, root_password_hash: Optional[str] = None,
                 use_dhcp: bool = True) -> str:
        """
        Generate answer.toml content

        Args:
            root_password_hash: SHA-512 password hash (generate with: openssl passwd -6)
            use_dhcp: Use DHCP for initial network config (recommended)

        Returns:
            Generated answer.toml content as string

        Raises:
            ValueError: If topology validation fails
        """
        # Validate topology first
        if not self.validate():
            self.print_validation_results()
            raise ValueError("Topology validation failed")

        if not self.proxmox_node:
            raise ValueError("No Proxmox hypervisor found in topology")

        # Default password hash (proxmox) - MUST BE CHANGED IN PRODUCTION
        if not root_password_hash:
            root_password_hash = "$6$Wx8sYKmgnwHk4BgS$eGr047.zvpBPesQF.sQ13IFcLdPSaIhqJ8eteA5Y0LSwq4Fp2vurgSN9LmWLjvxBPKJCRpt57l.vC9izxPQvn0"

        hostname = self._get_hostname()
        primary_disk = self._get_primary_disk()

        # Build answer.toml content
        sections = []

        # Header
        sections.append("# Proxmox VE 9 Auto-Install Configuration")
        sections.append(f"# Generated from topology.yaml v{self.topology.get('version', '2.2.0')}")
        sections.append("# DO NOT EDIT MANUALLY - Regenerate with scripts/generate-proxmox-answer.py")
        sections.append("# Documentation: https://pve.proxmox.com/wiki/Automated_Installation")
        sections.append("")

        # [global] section
        global_data = {
            'keyboard': 'en-us',
            'country': 'us',
            'timezone': 'UTC',
            'root_password': root_password_hash,
            'mailto': 'admin@home.local',
            'fqdn': hostname,
            'reboot_mode': 'power-off',
        }
        sections.append(self._format_toml_section('global', global_data))
        sections.append("")

        # [disk-setup] section
        sections.append("# ============================================================")
        sections.append("# Disk Configuration")
        sections.append("# ============================================================")
        sections.append("")

        disk_setup_data = {
            'filesystem': 'ext4',
            'disk_list': [primary_disk],
        }
        sections.append(self._format_toml_section('disk-setup', disk_setup_data))
        sections.append("")

        # LVM configuration
        sections.append("# LVM configuration")
        sections.append("# swapsize: Swap size in GB")
        sections.append("# maxroot: Maximum root filesystem size in GB")
        sections.append("# minfree: Minimum free space to leave in LVM pool in GB")
        sections.append("lvm.swapsize = 2")
        sections.append("lvm.maxroot = 50")
        sections.append("lvm.minfree = 10")
        sections.append("lvm.maxvz = 0")
        sections.append("")

        # [network] section
        sections.append("# ============================================================")
        sections.append("# Network Configuration")
        sections.append("# ============================================================")
        sections.append("")

        if use_dhcp:
            # DHCP configuration (recommended for initial setup)
            network_data = {
                'source': 'from-dhcp',
            }
            sections.append(self._format_toml_section('network', network_data))
            sections.append("")
            sections.append("# Static IP configuration will be applied by post-install scripts")
        else:
            # Static IP configuration
            mgmt_ip = self._get_management_ip()
            if mgmt_ip:
                network_data = {
                    'source': 'from-answer',
                    'cidr': mgmt_ip['cidr'],
                    'gateway': mgmt_ip['gateway'],
                    'dns': mgmt_ip['dns'],
                }
                sections.append(self._format_toml_section('network', network_data))
            else:
                # Fallback to DHCP if no management IP found
                network_data = {'source': 'from-dhcp'}
                sections.append(self._format_toml_section('network', network_data))
                sections.append("# No static management IP found in topology, using DHCP")

        sections.append("")

        # [first-boot] section
        sections.append("# ============================================================")
        sections.append("# First-Boot Configuration")
        sections.append("# ============================================================")
        sections.append("")

        first_boot_data = {
            'source': 'from-iso',
            'ordering': 'fully-up',
        }
        sections.append(self._format_toml_section('first-boot', first_boot_data))
        sections.append("")

        # Notes
        sections.append("# ============================================================")
        sections.append("# Notes")
        sections.append("# ============================================================")
        sections.append("#")
        sections.append("# This configuration will:")
        sections.append(f"# 1. Install Proxmox VE 9 on {self.proxmox_node.get('specs', {}).get('model', 'Dell XPS L701X')}")
        sections.append(f"# 2. Hostname: {hostname}")
        sections.append(f"# 3. System disk: {primary_disk}")
        sections.append("# 4. Network: DHCP initially (configured by post-install scripts)")
        sections.append("#")
        sections.append("# After installation:")
        sections.append("# 1. Remove USB drive and boot into Proxmox")
        sections.append("# 2. SSH to Proxmox host")
        sections.append("# 3. Run post-install scripts from /root/post-install/")
        sections.append("# 4. Apply Terraform infrastructure")
        sections.append("# 5. Apply Ansible configuration")
        sections.append("")

        return '\n'.join(sections)

    def save(self, output_path: str, root_password_hash: Optional[str] = None,
             use_dhcp: bool = True) -> None:
        """
        Generate and save answer.toml

        Args:
            output_path: Path to save answer.toml
            root_password_hash: SHA-512 password hash
            use_dhcp: Use DHCP for initial network config
        """
        content = self.generate(root_password_hash, use_dhcp)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content)

        print(f"✓ Generated: {output_path}")
        print(f"  - Hostname: {self._get_hostname()}")
        print(f"  - System disk: {self._get_primary_disk()}")
        print(f"  - Network: {'DHCP' if use_dhcp else 'Static'}")

        # Print warnings if any
        if self.validation_warnings:
            print()
            self.print_validation_results()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Generate Proxmox answer.toml from topology.yaml',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate answer.toml with DHCP (recommended)
  %(prog)s topology.yaml bare-metal/answer.toml

  # Generate with custom password hash
  %(prog)s topology.yaml answer.toml --password "$(openssl passwd -6 'MyPassword')"

  # Generate with static IP (not recommended for auto-install)
  %(prog)s topology.yaml answer.toml --static
        """
    )

    parser.add_argument(
        'topology',
        nargs='?',
        default='topology.yaml',
        help='Path to topology.yaml (default: topology.yaml)'
    )

    parser.add_argument(
        'output',
        nargs='?',
        default='bare-metal/answer.toml',
        help='Output path for answer.toml (default: bare-metal/answer.toml)'
    )

    parser.add_argument(
        '--password',
        help='Root password hash (SHA-512). Generate with: openssl passwd -6 "password"'
    )

    parser.add_argument(
        '--static',
        action='store_true',
        help='Use static IP from topology (default: DHCP)'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate topology structure only (do not generate)'
    )

    args = parser.parse_args()

    # Validate topology exists
    topology_path = Path(args.topology)
    if not topology_path.exists():
        print(f"❌ Error: Topology file not found: {args.topology}")
        return 1

    try:
        # Load and validate
        print(f"Loading topology from: {args.topology}")
        generator = ProxmoxAnswerGenerator(args.topology)

        if args.validate:
            print("✓ Topology loaded successfully")
            print(f"  - Version: {generator.topology.get('version', 'unknown')}")
            print(f"  - Proxmox node: {generator._get_hostname()}")
            print()

            # Run validation
            is_valid = generator.validate()
            generator.print_validation_results()

            return 0 if is_valid else 1

        # Generate answer.toml
        generator.save(
            args.output,
            root_password_hash=args.password,
            use_dhcp=not args.static
        )

        print("")
        print("⚠️  IMPORTANT:")
        print("  1. Review answer.toml before creating USB")
        print("  2. Change root_password hash in production!")
        print("  3. Use: openssl passwd -6 'YourPassword'")

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

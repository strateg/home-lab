#!/usr/bin/env python3
"""
Generate MikroTik RouterOS Terraform configuration from topology v4.0

Usage:
    python3 topology-tools/generate-terraform-mikrotik.py [--topology topology.yaml] [--output generated/terraform-mikrotik/]

Requirements:
    pip install pyyaml jinja2

This script generates Terraform configuration for MikroTik RouterOS using
the terraform-routeros provider. It reads the topology YAML files and creates:
  - provider.tf     - RouterOS provider configuration
  - variables.tf    - Input variables
  - interfaces.tf   - Bridge, VLAN, ports
  - addresses.tf    - IP addresses
  - dhcp.tf         - DHCP servers
  - dns.tf          - DNS settings
  - firewall.tf     - Firewall rules
  - qos.tf          - QoS queue trees
  - vpn.tf          - WireGuard VPN
  - containers.tf   - AdGuard, Tailscale containers
  - outputs.tf      - Infrastructure outputs
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader

from generation.common import load_and_validate_layered_topology, prepare_output_directory


class MikrotikTerraformGenerator:
    """Generate MikroTik RouterOS Terraform configs from topology v4.0"""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = "topology-tools/templates"):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir) / "terraform-mikrotik"
        self.topology: Dict = {}

        self.mikrotik_device: Dict = {}
        self.networks: List[Dict] = []
        self.vlans: List[Dict] = []
        self.lan_ports: List[Dict] = []
        self.firewall_policies: List[Dict] = []
        self.qos: Dict = {}
        self.wireguard: Dict = {}
        self.containers: Dict = {}
        self.dns_records: List[Dict] = []
        self.dns_settings: Dict = {}
        self.dhcp_leases: List[Dict] = []

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology, version_warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=['L0_meta', 'L1_foundation', 'L2_network', 'L5_application'],
            )
            print(f"OK Loaded topology: {self.topology_path}")

            if version_warning:
                print(f"WARN  {version_warning}")

            return True
        except ValueError as e:
            print(f"ERROR {e}")
            return False
        except FileNotFoundError:
            print(f"ERROR Topology file not found: {self.topology_path}")
            return False
        except Exception as e:
            print(f"ERROR Error loading topology: {e}")
            return False

    def extract_mikrotik_data(self) -> bool:
        """Extract MikroTik-relevant data from topology"""
        try:
            for device in self.topology['L1_foundation'].get('devices', []):
                if device.get('id') == 'mikrotik-chateau':
                    self.mikrotik_device = device
                    break

            if not self.mikrotik_device:
                print("ERROR MikroTik device (mikrotik-chateau) not found in L1_foundation")
                return False

            print(f"OK Found MikroTik device: {self.mikrotik_device.get('name', 'Unknown')}")

            self._extract_networks()
            self._extract_vlans()
            self._extract_lan_ports()
            self._extract_firewall_policies()
            self._extract_qos()
            self._extract_wireguard()
            self._extract_containers()
            self._extract_dns()

            return True

        except Exception as e:
            print(f"ERROR Error extracting MikroTik data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _extract_networks(self):
        """Extract networks managed by MikroTik"""
        for network in self.topology['L2_network'].get('networks', []):
            if network.get('managed_by_ref') == 'mikrotik-chateau':
                if network.get('vlan'):
                    network['interface_name'] = f"vlan{network['vlan']}"
                else:
                    network['interface_name'] = 'bridge-lan'
                self.networks.append(network)

        print(f"OK Extracted {len(self.networks)} networks")

    def _extract_vlans(self):
        """Extract VLAN configurations"""
        for network in self.networks:
            vlan_id = network.get('vlan')
            if vlan_id:
                self.vlans.append({
                    'id': vlan_id,
                    'name': network.get('name', f'VLAN {vlan_id}'),
                    'network_ref': network.get('id'),
                    'cidr': network.get('cidr'),
                    'trust_zone_ref': network.get('trust_zone_ref'),
                    'untagged_ports': [],
                })

        print(f"OK Extracted {len(self.vlans)} VLANs")

    def _extract_lan_ports(self):
        """Extract LAN ports for bridge configuration"""
        for interface in self.mikrotik_device.get('interfaces', []):
            if interface.get('type') == 'ethernet' and interface.get('role') == 'lan':
                self.lan_ports.append({
                    'name': interface.get('id', '').replace('if-mikrotik-', ''),
                    'interface': interface.get('physical_name', interface.get('id')),
                    'pvid': 1,
                    'comment': interface.get('description', ''),
                    'tagged_vlans': False,
                })

        print(f"OK Extracted {len(self.lan_ports)} LAN ports")

    def _extract_firewall_policies(self):
        """Extract firewall policies"""
        policies = self.topology['L2_network'].get('firewall_policies', [])

        for policy in policies:
            if policy.get('source_network_ref'):
                for net in self.networks:
                    if net.get('id') == policy['source_network_ref']:
                        policy['source_cidr'] = net.get('cidr')
                        break

            if policy.get('destination_network_ref'):
                for net in self.networks:
                    if net.get('id') == policy['destination_network_ref']:
                        policy['destination_cidr'] = net.get('cidr')
                        break

            self.firewall_policies.append(policy)

        print(f"OK Extracted {len(self.firewall_policies)} firewall policies")

    def _extract_qos(self):
        """Extract QoS configuration"""
        qos_config = self.topology['L2_network'].get('qos', {})

        if qos_config.get('enabled'):
            self.qos = qos_config.copy()

            if 'device_limits' in self.qos:
                for limit in self.qos['device_limits']:
                    network_ref = limit.get('network_ref')
                    for net in self.networks:
                        if net.get('id') == network_ref:
                            limit['target_cidr'] = net.get('cidr')
                            break

            print(f"OK Extracted QoS config with {len(self.qos.get('queues', []))} queues")
        else:
            print("INFO  QoS is disabled in topology")

    def _extract_wireguard(self):
        """Extract WireGuard VPN configuration"""
        for network in self.networks:
            if network.get('vpn_type') == 'wireguard':
                self.wireguard = {
                    'enabled': True,
                    'port': 51820,
                    'server_ip': network.get('gateway', '10.0.200.1'),
                    'network': network.get('cidr', '10.0.200.0/24'),
                    'peers': [],
                }
                print("OK Extracted WireGuard configuration")
                return

        self.wireguard = {'enabled': False}
        print("INFO  WireGuard VPN not configured in topology")

    def _extract_containers(self):
        """Extract container configuration from services"""
        services = self.topology.get('L5_application', {}).get('services', []) or []

        self.containers = {
            'ram_limit_mb': 512,
            'services': []
        }

        for service in services:
            if isinstance(service, dict) and service.get('device_ref') == 'mikrotik-chateau':
                if service.get('container'):
                    self.containers['services'].append({
                        'id': service.get('id'),
                        'name': service.get('name'),
                        'image': service.get('container_image'),
                    })

        print(f"OK Extracted {len(self.containers['services'])} container configurations")

    def _extract_dns(self):
        """Extract DNS records and settings"""
        dns_config = self.topology.get('L5_application', {}).get('dns', {})

        self.dns_settings = dns_config.get('settings', {})

        for zone in dns_config.get('zones', []) or []:
            domain = zone.get('domain', 'home.local')
            for record in zone.get('records', []) or []:
                record['domain'] = domain
                self.dns_records.append(record)

        print(f"OK Extracted {len(self.dns_records)} DNS records")

    def generate_all(self) -> bool:
        """Generate all Terraform files"""
        if prepare_output_directory(self.output_dir):
            print(f"CLEAN Cleaning output directory: {self.output_dir}")

        print(f"DIR Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_file('provider.tf.j2', 'provider.tf')
        success &= self.generate_file('variables.tf.j2', 'variables.tf')
        success &= self.generate_file('interfaces.tf.j2', 'interfaces.tf')
        success &= self.generate_file('addresses.tf.j2', 'addresses.tf')
        success &= self.generate_file('dhcp.tf.j2', 'dhcp.tf')
        success &= self.generate_file('dns.tf.j2', 'dns.tf')
        success &= self.generate_file('firewall.tf.j2', 'firewall.tf')
        success &= self.generate_file('qos.tf.j2', 'qos.tf')
        success &= self.generate_file('vpn.tf.j2', 'vpn.tf')
        success &= self.generate_file('containers.tf.j2', 'containers.tf')
        success &= self.generate_file('outputs.tf.j2', 'outputs.tf')
        success &= self.generate_tfvars_example()

        # Run terraform fmt to normalize formatting
        success &= self.run_terraform_fmt()

        return success

    def run_terraform_fmt(self) -> bool:
        """Run terraform fmt to normalize file formatting"""
        import subprocess
        try:
            result = subprocess.run(
                ["terraform", "fmt"],
                cwd=str(self.output_dir),
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                formatted_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
                if formatted_files and formatted_files[0]:
                    print(f"FMT Formatted {len(formatted_files)} files with terraform fmt")
                else:
                    print("FMT All files already formatted")
                return True
            else:
                print(f"WARN  terraform fmt returned non-zero: {result.stderr}")
                return True  # Non-fatal, files are still valid
        except FileNotFoundError:
            print("WARN  terraform not found in PATH, skipping fmt")
            return True  # Non-fatal
        except Exception as e:
            print(f"WARN  terraform fmt failed: {e}")
            return True  # Non-fatal

    def generate_file(self, template_name: str, output_name: str) -> bool:
        """Generate a single Terraform file from template"""
        try:
            template = self.jinja_env.get_template(template_name)

            mikrotik_mgmt_ip = '192.168.88.1'
            for network in self.networks:
                if network.get('id') == 'net-lan':
                    mikrotik_mgmt_ip = network.get('gateway', '192.168.88.1')
                    break

            context = {
                'topology_version': self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                'mikrotik_device': self.mikrotik_device,
                'mikrotik_mgmt_ip': mikrotik_mgmt_ip,
                'networks': self.networks,
                'vlans': self.vlans,
                'lan_ports': self.lan_ports,
                'firewall_policies': self.firewall_policies,
                'qos': self.qos,
                'wireguard': self.wireguard,
                'containers': self.containers,
                'dns_records': self.dns_records,
                'dns_settings': self.dns_settings,
                'dns_domain': 'home.local',
                'dhcp_leases': self.dhcp_leases,
            }

            content = template.render(**context)

            output_file = self.output_dir / output_name
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating {output_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_tfvars_example(self) -> bool:
        """Generate terraform.tfvars.example"""
        try:
            content = """# =============================================================================
# MikroTik Terraform Variables Example
# Copy this file to terraform.tfvars and fill in your values
# DO NOT commit terraform.tfvars to version control (contains secrets)
# =============================================================================

# MikroTik Connection
mikrotik_host     = \"https://192.168.88.1:8443\"
mikrotik_username = \"terraform\"
mikrotik_password = \"YOUR_SECURE_PASSWORD\"
mikrotik_insecure = true  # Set to false with valid SSL certificate

# WireGuard VPN (generate with: wg genkey)
wireguard_private_key = \"\"

# WireGuard Peers (add your devices)
wireguard_peers = [
  # {
  #   name        = \"phone\"
  #   public_key  = \"generated_public_key_here\"
  #   allowed_ips = [\"10.0.200.10/32\"]
  #   comment     = \"My Phone\"
  # },
  # {
  #   name        = \"laptop\"
  #   public_key  = \"generated_public_key_here\"
  #   allowed_ips = [\"10.0.200.11/32\"]
  #   comment     = \"My Laptop\"
  # }
]

# Container Configuration
adguard_password  = \"\"  # bcrypt hash of admin password
tailscale_authkey = \"\"  # From Tailscale admin console
"""
            output_file = self.output_dir / "terraform.tfvars.example"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating terraform.tfvars.example: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "=" * 70)
        print("MikroTik Terraform Generation Summary")
        print("=" * 70)

        print(f"\nOK Generated Terraform configuration for MikroTik:")
        print(f"  - Device: {self.mikrotik_device.get('name', 'Unknown')}")
        print(f"  - {len(self.networks)} networks")
        print(f"  - {len(self.vlans)} VLANs")
        print(f"  - {len(self.firewall_policies)} firewall policies")
        print(f"  - {len(self.containers.get('services', []))} containers")
        print(f"  - WireGuard: {'Enabled' if self.wireguard.get('enabled') else 'Disabled'}")
        print(f"  - QoS: {'Enabled' if self.qos.get('enabled') else 'Disabled'}")

        print(f"\nOK Output directory: {self.output_dir}")

        print(f"\nWARN  Prerequisites:")
        print(f"  1. Enable REST API on MikroTik (see bootstrap/mikrotik/README.md)")
        print(f"  2. Copy terraform.tfvars.example to terraform.tfvars")
        print(f"  3. Edit terraform.tfvars with your credentials")

        print(f"\nNext steps:")
        print(f"  1. cd {self.output_dir}")
        print(f"  2. terraform init")
        print(f"  3. terraform plan")
        print(f"  4. terraform apply")


def main():
    parser = argparse.ArgumentParser(
        description="Generate MikroTik RouterOS Terraform configuration from topology v4.0"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--output",
        default="generated/terraform-mikrotik",
        help="Output directory for Terraform files (default: generated/terraform-mikrotik/)"
    )
    parser.add_argument(
        "--templates",
        default="topology-tools/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = MikrotikTerraformGenerator(args.topology, args.output, args.templates)

    print("=" * 70)
    print("MikroTik Terraform Generator (Topology v4.0)")
    print("=" * 70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\nSUMMARY Extracting MikroTik configuration...\n")

    if not generator.extract_mikrotik_data():
        print("\nERROR Failed to extract MikroTik data")
        sys.exit(1)

    print("\nGEN Generating Terraform files...\n")

    if not generator.generate_all():
        print("\nERROR Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\nOK MikroTik Terraform generation completed successfully!\n")


if __name__ == "__main__":
    main()

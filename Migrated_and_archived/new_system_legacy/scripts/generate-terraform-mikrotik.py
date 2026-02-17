#!/usr/bin/env python3
"""
Generate MikroTik RouterOS Terraform configuration from topology v3.0

Usage:
    python3 scripts/generate-terraform-mikrotik.py [--topology topology.yaml] [--output generated/terraform-mikrotik/]

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
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
from jinja2 import Environment, FileSystemLoader

# Import topology loader with !include support
from topology_loader import load_topology


class MikrotikTerraformGenerator:
    """Generate MikroTik RouterOS Terraform configs from topology v3.0"""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = "scripts/templates"):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir) / "terraform-mikrotik"
        self.topology: Dict = {}

        # Extracted data for templates
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

        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology = load_topology(str(self.topology_path))
            print(f"✓ Loaded topology: {self.topology_path}")

            # Validate v3.0 structure
            required = ['version', 'physical_topology', 'logical_topology']
            for section in required:
                if section not in self.topology:
                    print(f"❌ Missing required section: {section}")
                    return False

            version = self.topology.get('version', '')
            if not version.startswith('3.'):
                print(f"⚠️  Warning: Topology version {version} - expected 3.x for MikroTik support")

            return True
        except FileNotFoundError:
            print(f"❌ Topology file not found: {self.topology_path}")
            return False
        except Exception as e:
            print(f"❌ Error loading topology: {e}")
            return False

    def extract_mikrotik_data(self) -> bool:
        """Extract MikroTik-relevant data from topology"""
        try:
            # Find MikroTik device
            for device in self.topology['physical_topology'].get('devices', []):
                if device.get('id') == 'mikrotik-chateau':
                    self.mikrotik_device = device
                    break

            if not self.mikrotik_device:
                print("❌ MikroTik device (mikrotik-chateau) not found in physical_topology")
                return False

            print(f"✓ Found MikroTik device: {self.mikrotik_device.get('name', 'Unknown')}")

            # Extract networks managed by MikroTik
            self._extract_networks()

            # Extract VLANs
            self._extract_vlans()

            # Extract LAN ports for bridge
            self._extract_lan_ports()

            # Extract firewall policies
            self._extract_firewall_policies()

            # Extract QoS configuration
            self._extract_qos()

            # Extract WireGuard configuration
            self._extract_wireguard()

            # Extract container configuration
            self._extract_containers()

            # Extract DNS records
            self._extract_dns()

            return True

        except Exception as e:
            print(f"❌ Error extracting MikroTik data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _extract_networks(self):
        """Extract networks managed by MikroTik"""
        for network in self.topology['logical_topology'].get('networks', []):
            if network.get('managed_by_ref') == 'mikrotik-chateau':
                # Add interface name based on VLAN
                if network.get('vlan'):
                    network['interface_name'] = f"vlan{network['vlan']}"
                else:
                    network['interface_name'] = 'bridge-lan'
                self.networks.append(network)

        print(f"✓ Extracted {len(self.networks)} networks")

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
                    'untagged_ports': [],  # To be populated if needed
                })

        print(f"✓ Extracted {len(self.vlans)} VLANs")

    def _extract_lan_ports(self):
        """Extract LAN ports for bridge configuration"""
        # MikroTik Chateau has ether2-ether5 as LAN ports
        for interface in self.mikrotik_device.get('interfaces', []):
            if interface.get('type') == 'ethernet' and interface.get('role') == 'lan':
                self.lan_ports.append({
                    'name': interface.get('id', '').replace('if-mikrotik-', ''),
                    'interface': interface.get('physical_name', interface.get('id')),
                    'pvid': 1,
                    'comment': interface.get('description', ''),
                    'tagged_vlans': False,
                })

        print(f"✓ Extracted {len(self.lan_ports)} LAN ports")

    def _extract_firewall_policies(self):
        """Extract firewall policies"""
        policies = self.topology['logical_topology'].get('firewall_policies', [])

        # Map zone refs to CIDRs
        zone_cidrs = {}
        for network in self.networks:
            zone = network.get('trust_zone_ref')
            if zone and network.get('cidr') and network.get('cidr') != 'dhcp':
                zone_cidrs[zone] = network.get('cidr')

        for policy in policies:
            # Add source CIDR if zone reference exists
            if policy.get('source_network_ref'):
                for net in self.networks:
                    if net.get('id') == policy['source_network_ref']:
                        policy['source_cidr'] = net.get('cidr')
                        break

            # Add destination CIDR
            if policy.get('destination_network_ref'):
                for net in self.networks:
                    if net.get('id') == policy['destination_network_ref']:
                        policy['destination_cidr'] = net.get('cidr')
                        break

            self.firewall_policies.append(policy)

        print(f"✓ Extracted {len(self.firewall_policies)} firewall policies")

    def _extract_qos(self):
        """Extract QoS configuration"""
        qos_config = self.topology['logical_topology'].get('qos', {})

        if qos_config.get('enabled'):
            self.qos = qos_config.copy()

            # Add target CIDRs to device limits
            if 'device_limits' in self.qos:
                for limit in self.qos['device_limits']:
                    network_ref = limit.get('network_ref')
                    for net in self.networks:
                        if net.get('id') == network_ref:
                            limit['target_cidr'] = net.get('cidr')
                            break

            print(f"✓ Extracted QoS config with {len(self.qos.get('queues', []))} queues")
        else:
            print("ℹ  QoS is disabled in topology")

    def _extract_wireguard(self):
        """Extract WireGuard VPN configuration"""
        for network in self.networks:
            if network.get('vpn_type') == 'wireguard':
                self.wireguard = {
                    'enabled': True,
                    'port': 51820,
                    'server_ip': network.get('gateway', '10.0.200.1'),
                    'network': network.get('cidr', '10.0.200.0/24'),
                    'peers': [],  # Peers are added via terraform variables
                }
                print("✓ Extracted WireGuard configuration")
                return

        self.wireguard = {'enabled': False}
        print("ℹ  WireGuard VPN not configured in topology")

    def _extract_containers(self):
        """Extract container configuration from services"""
        # Services can be under 'services.items' (new structure) or 'services' (list)
        services_data = self.topology.get('services', {})
        if isinstance(services_data, dict):
            services = services_data.get('items', [])
        else:
            services = services_data  # Backwards compatibility if it's a list

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

        print(f"✓ Extracted {len(self.containers['services'])} container configurations")

    def _extract_dns(self):
        """Extract DNS records and settings"""
        dns_config = self.topology['logical_topology'].get('dns', {})

        self.dns_settings = dns_config.get('settings', {})

        # Extract records from zones
        for zone in dns_config.get('zones', []):
            domain = zone.get('domain', 'home.local')
            for record in zone.get('records', []):
                record['domain'] = domain
                self.dns_records.append(record)

        print(f"✓ Extracted {len(self.dns_records)} DNS records")

    def generate_all(self) -> bool:
        """Generate all Terraform files"""
        # Clean output directory if it exists
        if self.output_dir.exists():
            print(f"🧹 Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        # Create fresh output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created output directory: {self.output_dir}")

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

        return success

    def generate_file(self, template_name: str, output_name: str) -> bool:
        """Generate a single Terraform file from template"""
        try:
            template = self.jinja_env.get_template(template_name)

            # Find MikroTik management IP
            mikrotik_mgmt_ip = '192.168.88.1'
            for network in self.networks:
                if network.get('id') == 'net-lan':
                    mikrotik_mgmt_ip = network.get('gateway', '192.168.88.1')
                    break

            # Common context for all templates
            context = {
                'topology_version': self.topology.get('version', '3.0.0'),
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
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating {output_name}: {e}")
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
mikrotik_host     = "https://192.168.88.1:8443"
mikrotik_username = "terraform"
mikrotik_password = "YOUR_SECURE_PASSWORD"
mikrotik_insecure = true  # Set to false with valid SSL certificate

# WireGuard VPN (generate with: wg genkey)
wireguard_private_key = ""

# WireGuard Peers (add your devices)
wireguard_peers = [
  # {
  #   name        = "phone"
  #   public_key  = "generated_public_key_here"
  #   allowed_ips = ["10.0.200.10/32"]
  #   comment     = "My Phone"
  # },
  # {
  #   name        = "laptop"
  #   public_key  = "generated_public_key_here"
  #   allowed_ips = ["10.0.200.11/32"]
  #   comment     = "My Laptop"
  # }
]

# Container Configuration
adguard_password  = ""  # bcrypt hash of admin password
tailscale_authkey = ""  # From Tailscale admin console
"""
            output_file = self.output_dir / "terraform.tfvars.example"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating terraform.tfvars.example: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "=" * 70)
        print("MikroTik Terraform Generation Summary")
        print("=" * 70)

        print(f"\n✓ Generated Terraform configuration for MikroTik:")
        print(f"  - Device: {self.mikrotik_device.get('name', 'Unknown')}")
        print(f"  - {len(self.networks)} networks")
        print(f"  - {len(self.vlans)} VLANs")
        print(f"  - {len(self.firewall_policies)} firewall policies")
        print(f"  - {len(self.containers.get('services', []))} containers")
        print(f"  - WireGuard: {'Enabled' if self.wireguard.get('enabled') else 'Disabled'}")
        print(f"  - QoS: {'Enabled' if self.qos.get('enabled') else 'Disabled'}")

        print(f"\n✓ Output directory: {self.output_dir}")

        print(f"\n⚠️  Prerequisites:")
        print(f"  1. Enable REST API on MikroTik (see bootstrap/mikrotik/bootstrap.rsc)")
        print(f"  2. Copy terraform.tfvars.example to terraform.tfvars")
        print(f"  3. Edit terraform.tfvars with your credentials")

        print(f"\nNext steps:")
        print(f"  1. cd {self.output_dir}")
        print(f"  2. terraform init")
        print(f"  3. terraform plan")
        print(f"  4. terraform apply")


def main():
    parser = argparse.ArgumentParser(
        description="Generate MikroTik RouterOS Terraform configuration from topology v3.0"
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
        default="scripts/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = MikrotikTerraformGenerator(args.topology, args.output, args.templates)

    print("=" * 70)
    print("MikroTik Terraform Generator (Topology v3.0)")
    print("=" * 70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\n📊 Extracting MikroTik configuration...\n")

    if not generator.extract_mikrotik_data():
        print("\n❌ Failed to extract MikroTik data")
        sys.exit(1)

    print("\n📝 Generating Terraform files...\n")

    if not generator.generate_all():
        print("\n❌ Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\n✅ MikroTik Terraform generation completed successfully!\n")


if __name__ == "__main__":
    main()

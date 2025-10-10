#!/usr/bin/env python3
"""
Generate Ansible inventory from topology v2.0

Usage:
    python3 scripts/generate-ansible-inventory.py [--topology topology.yaml] [--output generated/ansible]

Requirements:
    pip install pyyaml jinja2
"""

import sys
import yaml
import argparse
import shutil
from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

class AnsibleInventoryGenerator:
    """Generate Ansible inventory from topology v2.0"""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = "scripts/templates"):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        self.topology: Dict = {}

        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def load_topology(self) -> bool:
        """Load topology YAML file"""
        try:
            with open(self.topology_path) as f:
                self.topology = yaml.safe_load(f)
            print(f"✓ Loaded topology: {self.topology_path}")

            # Validate v2.0 structure
            required = ['version', 'physical_topology', 'logical_topology', 'compute']
            for section in required:
                if section not in self.topology:
                    print(f"❌ Missing required section: {section}")
                    return False

            version = self.topology.get('version', '')
            if not version.startswith('2.'):
                print(f"⚠️  Warning: Topology version {version} may not be compatible (expected 2.x)")

            return True
        except FileNotFoundError:
            print(f"❌ Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            print(f"❌ YAML parse error: {e}")
            return False

    def generate_all(self) -> bool:
        """Generate all Ansible inventory files"""
        # Clean output directory if it exists
        if self.output_dir.exists():
            print(f"🧹 Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        # Create fresh output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_hosts()
        success &= self.generate_group_vars()
        success &= self.generate_host_vars()

        return success

    def generate_hosts(self) -> bool:
        """Generate hosts.yml inventory file"""
        try:
            template = self.jinja_env.get_template('ansible/hosts.yml.j2')

            # Extract hosts from compute section
            vms = self.topology['compute'].get('vms', [])
            lxc_containers = self.topology['compute'].get('lxc', [])

            # Get network maps for IP resolution
            networks = {n['id']: n for n in self.topology['logical_topology'].get('networks', [])}

            # Build host information
            lxc_hosts = []
            for lxc in lxc_containers:
                host_info = {
                    'id': lxc['id'],
                    'name': lxc['name'],
                    'vmid': lxc['vmid'],
                    'type': lxc.get('type', 'unknown'),
                    'role': lxc.get('role', 'unknown'),
                    'trust_zone': lxc.get('trust_zone_ref', 'unknown'),
                    'ip': lxc['networks'][0]['ip'].split('/')[0] if lxc.get('networks') else None,
                    'ansible_user': lxc['cloudinit'].get('user', 'root') if lxc.get('cloudinit') else 'root',
                    'ansible_enabled': lxc.get('ansible', {}).get('enabled', False),
                    'playbook': lxc.get('ansible', {}).get('playbook'),
                }
                lxc_hosts.append(host_info)

            vm_hosts = []
            for vm in vms:
                # Find management interface IP
                mgmt_ip = None
                for nic in vm.get('networks', []):
                    if nic.get('role') == 'management' and nic.get('ip_config'):
                        ip_config = nic['ip_config']
                        if isinstance(ip_config, dict):
                            mgmt_ip = ip_config.get('address', '').split('/')[0]
                        break

                host_info = {
                    'id': vm['id'],
                    'name': vm['name'],
                    'vmid': vm['vmid'],
                    'type': vm.get('type', 'unknown'),
                    'role': vm.get('role', 'unknown'),
                    'trust_zone': vm.get('trust_zone_ref', 'unknown'),
                    'ip': mgmt_ip,
                    'ansible_enabled': vm.get('ansible', {}).get('enabled', False),
                }
                vm_hosts.append(host_info)

            # Group hosts by trust zones
            trust_zones = self.topology['logical_topology'].get('trust_zones', {})

            content = template.render(
                lxc_hosts=lxc_hosts,
                vm_hosts=vm_hosts,
                trust_zones=trust_zones,
                topology_version=self.topology.get('version', '2.0.0')
            )

            output_file = self.output_dir / "hosts.yml"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            print(f"  - {len(lxc_hosts)} LXC containers")
            print(f"  - {len(vm_hosts)} VMs")
            return True

        except Exception as e:
            print(f"❌ Error generating hosts.yml: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_group_vars(self) -> bool:
        """Generate group_vars/all.yml"""
        try:
            template = self.jinja_env.get_template('ansible/group_vars_all.yml.j2')

            # Extract network information
            networks = self.topology['logical_topology'].get('networks', [])

            # Find management network
            mgmt_network = None
            for network in networks:
                if 'management' in network.get('id', ''):
                    mgmt_network = network
                    break

            # Find internal network
            internal_network = None
            for network in networks:
                if 'internal' in network.get('id', ''):
                    internal_network = network
                    break

            content = template.render(
                mgmt_network=mgmt_network,
                internal_network=internal_network,
                networks=networks,
                topology_version=self.topology.get('version', '2.0.0')
            )

            group_vars_dir = self.output_dir / "group_vars"
            group_vars_dir.mkdir(parents=True, exist_ok=True)

            output_file = group_vars_dir / "all.yml"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating group_vars/all.yml: {e}")
            return False

    def generate_host_vars(self) -> bool:
        """Generate host_vars for each host"""
        try:
            template = self.jinja_env.get_template('ansible/host_vars.yml.j2')

            host_vars_dir = self.output_dir / "host_vars"
            host_vars_dir.mkdir(parents=True, exist_ok=True)

            count = 0

            # Generate host_vars for LXC containers
            for lxc in self.topology['compute'].get('lxc', []):
                if not lxc.get('ansible', {}).get('enabled', False):
                    continue

                host_vars = lxc.get('ansible', {}).get('vars', {})
                if not host_vars:
                    continue

                content = template.render(
                    host_id=lxc['id'],
                    host_name=lxc['name'],
                    host_type='lxc',
                    host_vars=host_vars
                )

                output_file = host_vars_dir / f"{lxc['name']}.yml"
                output_file.write_text(content)
                count += 1

            if count > 0:
                print(f"✓ Generated: {count} host_vars files in {host_vars_dir}")
            else:
                print(f"  (No host_vars to generate)")

            return True

        except Exception as e:
            print(f"❌ Error generating host_vars: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "="*70)
        print("Ansible Inventory Generation Summary")
        print("="*70)

        lxc = len(self.topology['compute'].get('lxc', []))
        vms = len(self.topology['compute'].get('vms', []))
        services = len(self.topology.get('services', []))

        print(f"\n✓ Generated Ansible inventory for:")
        print(f"  - {lxc} LXC containers")
        print(f"  - {vms} VMs")
        print(f"  - {services} services defined")
        print(f"\n✓ Output directory: {self.output_dir}")
        print(f"\nNext steps:")
        print(f"  1. Review generated inventory: {self.output_dir}/hosts.yml")
        print(f"  2. Test connectivity: ansible all -i {self.output_dir}/hosts.yml -m ping")
        print(f"  3. Run playbooks: ansible-playbook -i {self.output_dir}/hosts.yml playbooks/site.yml")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ansible inventory from topology v2.0"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--output",
        default="generated/ansible/inventory/production",
        help="Output directory for inventory files (default: generated/ansible/inventory/production/)"
    )
    parser.add_argument(
        "--templates",
        default="scripts/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = AnsibleInventoryGenerator(args.topology, args.output, args.templates)

    print("="*70)
    print("Ansible Inventory Generator (Topology v2.0)")
    print("="*70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\n📝 Generating Ansible inventory...\n")

    if not generator.generate_all():
        print("\n❌ Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\n✅ Ansible inventory generation completed successfully!\n")


if __name__ == "__main__":
    main()

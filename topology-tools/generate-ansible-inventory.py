#!/usr/bin/env python3
"""
Generate Ansible inventory from topology v4.0

Usage:
    python3 topology-tools/generate-ansible-inventory.py [--topology topology.yaml] [--output generated/ansible]

Requirements:
    pip install pyyaml jinja2
"""

import sys
import yaml
import argparse
import shutil
from pathlib import Path
from typing import Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Import topology loader with !include support
from topology_loader import load_topology


class AnsibleInventoryGenerator:
    """Generate Ansible inventory from topology v4.0"""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = "topology-tools/templates"):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        self.topology: Dict = {}

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology = load_topology(str(self.topology_path))
            print(f"OK Loaded topology: {self.topology_path}")

            required = ['L0_meta', 'L1_foundation', 'L2_network', 'L4_platform', 'L7_operations']
            for section in required:
                if section not in self.topology:
                    print(f"ERROR Missing required section: {section}")
                    return False

            version = self.topology.get('L0_meta', {}).get('version', '')
            if not version.startswith('4.'):
                print(f"WARN  Warning: Topology version {version} may not be compatible (expected 4.x)")

            return True
        except FileNotFoundError:
            print(f"ERROR Topology file not found: {self.topology_path}")
            return False
        except yaml.YAMLError as e:
            print(f"ERROR YAML parse error: {e}")
            return False

    def generate_all(self) -> bool:
        """Generate all Ansible inventory files"""
        if self.output_dir.exists():
            print(f"CLEAN Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"DIR Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_hosts()
        success &= self.generate_group_vars()
        success &= self.generate_host_vars()

        return success

    def generate_hosts(self) -> bool:
        """Generate hosts.yml inventory file"""
        try:
            template = self.jinja_env.get_template('ansible/hosts.yml.j2')

            vms = self.topology['L4_platform'].get('vms', [])
            lxc_containers = self.topology['L4_platform'].get('lxc', [])

            networks = {n['id']: n for n in self.topology['L2_network'].get('networks', [])}

            ip_map = {}
            for network in self.topology['L2_network'].get('networks', []):
                for alloc in network.get('ip_allocations', []) or []:
                    device_ref = alloc.get('device_ref')
                    ip = alloc.get('ip')
                    if device_ref and ip:
                        if 'management' in network.get('id', '') or device_ref not in ip_map:
                            ip_map[device_ref] = ip

            lxc_hosts = []
            for lxc in lxc_containers:
                host_info = {
                    'id': lxc['id'],
                    'inventory_name': lxc['id'],
                    'name': lxc['name'],
                    'display_name': lxc['name'],
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
                mgmt_ip = None
                for nic in vm.get('networks', []):
                    if nic.get('role') == 'management' and nic.get('ip_config'):
                        ip_config = nic['ip_config']
                        if isinstance(ip_config, dict):
                            mgmt_ip = ip_config.get('address', '').split('/')[0]
                        break

                host_info = {
                    'id': vm['id'],
                    'inventory_name': vm['id'],
                    'name': vm['name'],
                    'display_name': vm['name'],
                    'vmid': vm['vmid'],
                    'type': vm.get('type', 'unknown'),
                    'role': vm.get('role', 'unknown'),
                    'trust_zone': vm.get('trust_zone_ref', 'unknown'),
                    'ip': mgmt_ip,
                    'ansible_enabled': vm.get('ansible', {}).get('enabled', False),
                }
                vm_hosts.append(host_info)

            physical_hosts = []
            managed_types = ['sbc', 'server']
            for device in self.topology['L1_foundation'].get('devices', []):
                if device.get('type') in managed_types:
                    device_id = device['id']
                    device_ip = ip_map.get(device_id)

                    host_info = {
                        'id': device_id,
                        'inventory_name': device_id,
                        'name': device['name'],
                        'display_name': device['name'],
                        'type': device.get('type', 'unknown'),
                        'role': device.get('role', 'unknown'),
                        'model': device.get('model', 'unknown'),
                        'ip': device_ip,
                        'ansible_enabled': True,
                        'description': device.get('description', ''),
                    }
                    physical_hosts.append(host_info)

            trust_zones = self.topology['L2_network'].get('trust_zones', {})

            content = template.render(
                lxc_hosts=lxc_hosts,
                vm_hosts=vm_hosts,
                physical_hosts=physical_hosts,
                trust_zones=trust_zones,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            output_file = self.output_dir / "hosts.yml"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            print(f"  - {len(lxc_hosts)} LXC containers")
            print(f"  - {len(vm_hosts)} VMs")
            print(f"  - {len(physical_hosts)} physical devices")
            return True

        except Exception as e:
            print(f"ERROR Error generating hosts.yml: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_group_vars(self) -> bool:
        """Generate group_vars/all.yml"""
        try:
            template = self.jinja_env.get_template('ansible/group_vars_all.yml.j2')

            networks = self.topology['L2_network'].get('networks', [])

            mgmt_network = None
            for network in networks:
                if 'management' in network.get('id', ''):
                    mgmt_network = network
                    break

            internal_network = None
            for network in networks:
                if 'internal' in network.get('id', ''):
                    internal_network = network
                    break

            ansible_config = self.topology.get('L7_operations', {}).get('ansible', {})

            content = template.render(
                mgmt_network=mgmt_network,
                internal_network=internal_network,
                networks=networks,
                ansible_config=ansible_config,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            group_vars_dir = self.output_dir / "group_vars"
            group_vars_dir.mkdir(parents=True, exist_ok=True)

            output_file = group_vars_dir / "all.yml"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating group_vars/all.yml: {e}")
            return False

    def generate_host_vars(self) -> bool:
        """Generate host_vars for each host"""
        try:
            template = self.jinja_env.get_template('ansible/host_vars.yml.j2')

            host_vars_dir = self.output_dir / "host_vars"
            host_vars_dir.mkdir(parents=True, exist_ok=True)

            count = 0

            for lxc in self.topology['L4_platform'].get('lxc', []):
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

                output_file = host_vars_dir / f"{lxc['id']}.yml"
                output_file.write_text(content, encoding="utf-8")
                count += 1

            if count > 0:
                print(f"OK Generated: {count} host_vars files in {host_vars_dir}")
            else:
                print(f"  (No host_vars to generate)")

            return True

        except Exception as e:
            print(f"ERROR Error generating host_vars: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "="*70)
        print("Ansible Inventory Generation Summary")
        print("="*70)

        lxc = len(self.topology['L4_platform'].get('lxc', []))
        vms = len(self.topology['L4_platform'].get('vms', []))
        services = len(self.topology.get('L5_application', {}).get('services', []))

        print(f"\nOK Generated Ansible inventory for:")
        print(f"  - {lxc} LXC containers")
        print(f"  - {vms} VMs")
        print(f"  - {services} services defined")
        print(f"\nOK Output directory: {self.output_dir}")
        print(f"\nNext steps:")
        print(f"  1. Review generated inventory: {self.output_dir}/hosts.yml")
        print(f"  2. Test connectivity: ansible all -i {self.output_dir}/hosts.yml -m ping")
        print(f"  3. Run playbooks: ansible-playbook -i {self.output_dir}/hosts.yml playbooks/site.yml")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ansible inventory from topology v4.0"
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
        default="topology-tools/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = AnsibleInventoryGenerator(args.topology, args.output, args.templates)

    print("="*70)
    print("Ansible Inventory Generator (Topology v4.0)")
    print("="*70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\nGEN Generating Ansible inventory...\n")

    if not generator.generate_all():
        print("\nERROR Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\nOK Ansible inventory generation completed successfully!\n")


if __name__ == "__main__":
    main()

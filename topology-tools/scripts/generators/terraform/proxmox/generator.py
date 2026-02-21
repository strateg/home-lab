"""
Terraform generator core for Proxmox resources.
"""

import copy
import yaml
from pathlib import Path
from typing import Dict, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

from scripts.generators.common import load_and_validate_layered_topology, prepare_output_directory


class TerraformGenerator:
    """Generate Terraform configs from topology v4.0"""

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
            self.topology, version_warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=['L0_meta', 'L1_foundation', 'L2_network', 'L3_data', 'L4_platform'],
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
        except yaml.YAMLError as e:
            print(f"ERROR YAML parse error: {e}")
            return False

    def _resolve_interface_names(self, bridges: List[Dict]) -> List[Dict]:
        """Resolve logical interface IDs (if-eth-usb) to physical names (enxXXXX)"""
        interface_map = {}
        for device in self.topology['L1_foundation'].get('devices', []):
            if device.get('type') == 'hypervisor':
                for interface in device.get('interfaces', []):
                    interface_id = interface.get('id')
                    physical_name = interface.get('physical_name')
                    if interface_id and physical_name:
                        interface_map[interface_id] = physical_name

        for bridge in bridges:
            if bridge.get('ports'):
                resolved_ports = []
                for port_id in bridge['ports']:
                    if port_id in interface_map:
                        resolved_ports.append(interface_map[port_id])
                    else:
                        print(f"WARN  Warning: Cannot resolve interface '{port_id}' - using as-is")
                        resolved_ports.append(port_id)
                bridge['ports'] = resolved_ports

        return bridges

    def _resolve_lxc_resources(self, lxc_containers: List[Dict]) -> List[Dict]:
        """
        Resolve effective LXC resources for templates.

        Priority:
        1. legacy inline lxc.resources
        2. lxc.resource_profile_ref -> L4 resource_profiles
        3. conservative defaults
        """
        l4 = self.topology.get('L4_platform', {}) or {}
        profiles = l4.get('resource_profiles', []) or []
        profile_map = {
            profile.get('id'): profile
            for profile in profiles
            if isinstance(profile, dict) and profile.get('id')
        }
        resolved: List[Dict] = []

        for container in lxc_containers:
            if not isinstance(container, dict):
                continue
            item = copy.deepcopy(container)
            resources = item.get('resources') if isinstance(item.get('resources'), dict) else None

            if not resources:
                profile_ref = item.get('resource_profile_ref')
                profile = profile_map.get(profile_ref, {}) if profile_ref else {}
                cpu = (profile.get('cpu') or {})
                memory = (profile.get('memory') or {})
                resources = {
                    'cores': cpu.get('cores', 1),
                    'memory_mb': memory.get('mb', 512),
                    'swap_mb': memory.get('swap_mb', 0),
                }
                item['resources'] = resources

            # Keep template comments informative when old semantic fields are removed.
            item.setdefault('type', item.get('platform_type', 'lxc'))
            item.setdefault('role', item.get('resource_profile_ref', 'resource-profile'))
            resolved.append(item)

        return resolved

    def generate_all(self) -> bool:
        """Generate all Terraform files"""
        if prepare_output_directory(self.output_dir):
            print(f"CLEAN Cleaning output directory: {self.output_dir}")

        print(f"DIR Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_versions()
        success &= self.generate_provider()
        success &= self.generate_bridges()
        success &= self.generate_vms()
        success &= self.generate_lxc()
        success &= self.generate_variables()
        success &= self.generate_outputs()

        return success

    def generate_provider(self) -> bool:
        """Generate provider.tf with Proxmox configuration"""
        try:
            template = self.jinja_env.get_template('terraform/proxmox/provider.tf.j2')

            proxmox_device = None
            for device in self.topology['L1_foundation'].get('devices', []):
                if device.get('type') == 'hypervisor' and device.get('role') == 'compute':
                    proxmox_device = device
                    break

            if not proxmox_device:
                print("WARN  Warning: No Proxmox hypervisor found in L1_foundation")

            mgmt_network = None
            for network in self.topology['L2_network'].get('networks', []):
                if 'management' in network.get('id', ''):
                    mgmt_network = network
                    break

            content = template.render(
                proxmox_device=proxmox_device,
                mgmt_network=mgmt_network
            )

            output_file = self.output_dir / "provider.tf"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating provider.tf: {e}")
            return False

    def generate_versions(self) -> bool:
        """Generate versions.tf with required Terraform and provider versions"""
        try:
            template = self.jinja_env.get_template('terraform/proxmox/versions.tf.j2')

            content = template.render(
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            output_file = self.output_dir / "versions.tf"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating versions.tf: {e}")
            return False

    def generate_bridges(self) -> bool:
        """Generate bridges.tf with network bridge resources"""
        try:
            template = self.jinja_env.get_template('terraform/proxmox/bridges.tf.j2')

            bridges = self.topology['L2_network'].get('bridges', [])

            bridges = copy.deepcopy(bridges)
            bridges = self._resolve_interface_names(bridges)

            content = template.render(
                bridges=bridges,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            output_file = self.output_dir / "bridges.tf"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file} ({len(bridges)} bridges)")
            return True

        except Exception as e:
            print(f"ERROR Error generating bridges.tf: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_vms(self) -> bool:
        """Generate vms.tf with VM resources"""
        try:
            template = self.jinja_env.get_template('terraform/proxmox/vms.tf.j2')

            vms = self.topology['L4_platform'].get('vms', [])
            storage_map = {s['id']: s for s in self.topology.get('L3_data', {}).get('storage', [])}
            bridge_map = {b['id']: b for b in self.topology['L2_network'].get('bridges', [])}

            content = template.render(
                vms=vms,
                storage_map=storage_map,
                bridge_map=bridge_map,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            output_file = self.output_dir / "vms.tf"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file} ({len(vms)} VMs)")
            return True

        except Exception as e:
            print(f"ERROR Error generating vms.tf: {e}")
            return False

    def generate_lxc(self) -> bool:
        """Generate lxc.tf with LXC container resources"""
        try:
            template = self.jinja_env.get_template('terraform/proxmox/lxc.tf.j2')

            lxc_containers = self.topology['L4_platform'].get('lxc', [])
            lxc_containers = self._resolve_lxc_resources(lxc_containers)
            storage_map = {s['id']: s for s in self.topology.get('L3_data', {}).get('storage', [])}
            bridge_map = {b['id']: b for b in self.topology['L2_network'].get('bridges', [])}

            content = template.render(
                lxc_containers=lxc_containers,
                storage_map=storage_map,
                bridge_map=bridge_map,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            output_file = self.output_dir / "lxc.tf"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file} ({len(lxc_containers)} containers)")
            return True

        except Exception as e:
            print(f"ERROR Error generating lxc.tf: {e}")
            return False

    def generate_variables(self) -> bool:
        """Generate variables.tf and terraform.tfvars.example"""
        try:
            vars_template = self.jinja_env.get_template('terraform/proxmox/variables.tf.j2')
            vars_content = vars_template.render()

            vars_file = self.output_dir / "variables.tf"
            vars_file.write_text(vars_content, encoding="utf-8")
            print(f"OK Generated: {vars_file}")

            tfvars_template = self.jinja_env.get_template('terraform/proxmox/terraform.tfvars.example.j2')

            mgmt_network = None
            for network in self.topology['L2_network'].get('networks', []):
                if 'management' in network.get('id', ''):
                    mgmt_network = network
                    break

            tfvars_content = tfvars_template.render(
                mgmt_network=mgmt_network
            )

            tfvars_file = self.output_dir / "terraform.tfvars.example"
            tfvars_file.write_text(tfvars_content, encoding="utf-8")
            print(f"OK Generated: {tfvars_file}")

            return True

        except Exception as e:
            print(f"ERROR Error generating variables: {e}")
            return False

    def generate_outputs(self) -> bool:
        """Generate outputs.tf with infrastructure outputs"""
        try:
            template = self.jinja_env.get_template('terraform/proxmox/outputs.tf.j2')

            bridges = self.topology['L2_network'].get('bridges', [])
            lxc_containers = self.topology['L4_platform'].get('lxc', [])
            vms = self.topology['L4_platform'].get('vms', [])
            storage = self.topology.get('L3_data', {}).get('storage', [])
            devices = self.topology['L1_foundation'].get('devices', [])

            content = template.render(
                bridges=bridges,
                lxc_containers=lxc_containers,
                vms=vms,
                storage=storage,
                devices=devices,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0')
            )

            output_file = self.output_dir / "outputs.tf"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating outputs.tf: {e}")
            return False

    def print_summary(self) -> None:
        """Print generation summary."""
        print("\n" + "="*70)
        print("Terraform Generation Summary")
        print("="*70)

        bridges = len(self.topology['L2_network'].get('bridges', []))
        vms = len(self.topology['L4_platform'].get('vms', []))
        lxc = len(self.topology['L4_platform'].get('lxc', []))

        print(f"\nOK Generated Terraform configuration for:")
        print(f"  - {bridges} network bridges")
        print(f"  - {vms} VMs")
        print(f"  - {lxc} LXC containers")
        print(f"\nOK Output directory: {self.output_dir}")
        print(f"\n Note: Using bpg/proxmox provider v0.85+ for automated bridge creation")
        print(f"   If bridges fail to create, see BRIDGES.md for manual setup")
        print(f"\nNext steps:")
        print(f"  1. Verify physical interface names in topology/L1-foundation.yaml")
        print(f"     - if-eth-usb -> check actual USB Ethernet name (enxXXXX)")
        print(f"     - if-eth-builtin -> check actual built-in Ethernet name (enp3s0)")
        print(f"  2. Copy terraform.tfvars.example to terraform.tfvars")
        print(f"  3. Edit terraform.tfvars with your credentials")
        print(f"  4. Run: cd {self.output_dir} && terraform init -upgrade")
        print(f"  5. Run: terraform plan")
        print(f"  6. Run: terraform apply")

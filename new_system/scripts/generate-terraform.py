#!/usr/bin/env python3
"""
Generate Terraform configuration from topology v2.0

Usage:
    python3 scripts/generate-terraform.py [--topology topology.yaml] [--output generated/terraform/]

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

# Import topology loader with !include support
from topology_loader import load_topology

class TerraformGenerator:
    """Generate Terraform configs from topology v2.0"""

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
        """Load topology YAML file (with !include support)"""
        try:
            self.topology = load_topology(str(self.topology_path))
            print(f"✓ Loaded topology: {self.topology_path}")

            # Validate v2.0 structure
            required = ['version', 'physical_topology', 'logical_topology', 'compute', 'storage']
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
        """Generate all Terraform files"""
        # Clean output directory if it exists
        if self.output_dir.exists():
            print(f"🧹 Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        # Create fresh output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created output directory: {self.output_dir}")

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
            template = self.jinja_env.get_template('terraform/provider.tf.j2')

            # Get Proxmox device from physical topology
            proxmox_device = None
            for device in self.topology['physical_topology'].get('devices', []):
                if device.get('type') == 'hypervisor' and device.get('role') == 'compute':
                    proxmox_device = device
                    break

            if not proxmox_device:
                print("⚠️  Warning: No Proxmox hypervisor found in physical_topology")

            # Find management network for API endpoint
            mgmt_network = None
            for network in self.topology['logical_topology'].get('networks', []):
                if 'management' in network.get('id', ''):
                    mgmt_network = network
                    break

            content = template.render(
                proxmox_device=proxmox_device,
                mgmt_network=mgmt_network
            )

            output_file = self.output_dir / "provider.tf"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating provider.tf: {e}")
            return False

    def generate_versions(self) -> bool:
        """Generate versions.tf with required Terraform and provider versions"""
        try:
            template = self.jinja_env.get_template('terraform/versions.tf.j2')

            content = template.render(
                topology_version=self.topology.get('version', '2.0.0')
            )

            output_file = self.output_dir / "versions.tf"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating versions.tf: {e}")
            return False

    def generate_bridges(self) -> bool:
        """Generate bridges.tf with network bridge resources"""
        try:
            template = self.jinja_env.get_template('terraform/bridges.tf.j2')

            bridges = self.topology['logical_topology'].get('bridges', [])

            content = template.render(
                bridges=bridges,
                topology_version=self.topology.get('version', '2.0.0')
            )

            output_file = self.output_dir / "bridges.tf"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file} ({len(bridges)} bridges)")
            return True

        except Exception as e:
            print(f"❌ Error generating bridges.tf: {e}")
            return False

    def generate_vms(self) -> bool:
        """Generate vms.tf with VM resources"""
        try:
            template = self.jinja_env.get_template('terraform/vms.tf.j2')

            vms = self.topology['compute'].get('vms', [])
            storage_map = {s['id']: s for s in self.topology.get('storage', [])}
            bridge_map = {b['id']: b for b in self.topology['logical_topology'].get('bridges', [])}

            content = template.render(
                vms=vms,
                storage_map=storage_map,
                bridge_map=bridge_map,
                topology_version=self.topology.get('version', '2.0.0')
            )

            output_file = self.output_dir / "vms.tf"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file} ({len(vms)} VMs)")
            return True

        except Exception as e:
            print(f"❌ Error generating vms.tf: {e}")
            return False

    def generate_lxc(self) -> bool:
        """Generate lxc.tf with LXC container resources"""
        try:
            template = self.jinja_env.get_template('terraform/lxc.tf.j2')

            lxc_containers = self.topology['compute'].get('lxc', [])
            storage_map = {s['id']: s for s in self.topology.get('storage', [])}
            bridge_map = {b['id']: b for b in self.topology['logical_topology'].get('bridges', [])}

            content = template.render(
                lxc_containers=lxc_containers,
                storage_map=storage_map,
                bridge_map=bridge_map,
                topology_version=self.topology.get('version', '2.0.0')
            )

            output_file = self.output_dir / "lxc.tf"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file} ({len(lxc_containers)} containers)")
            return True

        except Exception as e:
            print(f"❌ Error generating lxc.tf: {e}")
            return False

    def generate_variables(self) -> bool:
        """Generate variables.tf and terraform.tfvars.example"""
        try:
            # variables.tf
            vars_template = self.jinja_env.get_template('terraform/variables.tf.j2')
            vars_content = vars_template.render()

            vars_file = self.output_dir / "variables.tf"
            vars_file.write_text(vars_content)
            print(f"✓ Generated: {vars_file}")

            # terraform.tfvars.example
            tfvars_template = self.jinja_env.get_template('terraform/terraform.tfvars.example.j2')

            # Get management network info
            mgmt_network = None
            for network in self.topology['logical_topology'].get('networks', []):
                if 'management' in network.get('id', ''):
                    mgmt_network = network
                    break

            tfvars_content = tfvars_template.render(
                mgmt_network=mgmt_network
            )

            tfvars_file = self.output_dir / "terraform.tfvars.example"
            tfvars_file.write_text(tfvars_content)
            print(f"✓ Generated: {tfvars_file}")

            return True

        except Exception as e:
            print(f"❌ Error generating variables: {e}")
            return False

    def generate_outputs(self) -> bool:
        """Generate outputs.tf with infrastructure outputs"""
        try:
            template = self.jinja_env.get_template('terraform/outputs.tf.j2')

            # Gather all data for outputs
            bridges = self.topology['logical_topology'].get('bridges', [])
            lxc_containers = self.topology['compute'].get('lxc', [])
            vms = self.topology['compute'].get('vms', [])
            storage = self.topology.get('storage', [])
            devices = self.topology['physical_topology'].get('devices', [])

            content = template.render(
                bridges=bridges,
                lxc_containers=lxc_containers,
                vms=vms,
                storage=storage,
                devices=devices,
                topology_version=self.topology.get('version', '2.0.0')
            )

            output_file = self.output_dir / "outputs.tf"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating outputs.tf: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "="*70)
        print("Terraform Generation Summary")
        print("="*70)

        vms = len(self.topology['compute'].get('vms', []))
        lxc = len(self.topology['compute'].get('lxc', []))
        bridges = len(self.topology['logical_topology'].get('bridges', []))

        print(f"\n✓ Generated Terraform configuration for:")
        print(f"  - {bridges} network bridges")
        print(f"  - {vms} VMs")
        print(f"  - {lxc} LXC containers")
        print(f"\n✓ Output directory: {self.output_dir}")
        print(f"\nNext steps:")
        print(f"  1. Copy terraform.tfvars.example to terraform.tfvars")
        print(f"  2. Edit terraform.tfvars with your credentials")
        print(f"  3. Run: cd {self.output_dir} && terraform init")
        print(f"  4. Run: terraform plan")
        print(f"  5. Run: terraform apply")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Terraform configuration from topology v2.0"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--output",
        default="generated/terraform",
        help="Output directory for Terraform files (default: generated/terraform/)"
    )
    parser.add_argument(
        "--templates",
        default="scripts/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = TerraformGenerator(args.topology, args.output, args.templates)

    print("="*70)
    print("Terraform Configuration Generator (Topology v2.0)")
    print("="*70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\n📝 Generating Terraform files...\n")

    if not generator.generate_all():
        print("\n❌ Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\n✅ Terraform generation completed successfully!\n")


if __name__ == "__main__":
    main()

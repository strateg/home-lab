#!/usr/bin/env python3
"""
Generate documentation from topology v2.0

Usage:
    python3 scripts/generate-docs.py [--topology topology.yaml] [--output generated/docs/]

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
from datetime import datetime

# Import topology loader with !include support
from topology_loader import load_topology

class DocumentationGenerator:
    """Generate documentation from topology v2.0"""

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
        """Generate all documentation files"""
        # Clean output directory if it exists
        if self.output_dir.exists():
            print(f"🧹 Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        # Create fresh output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_network_diagram()
        success &= self.generate_ip_allocation()
        success &= self.generate_services_inventory()
        success &= self.generate_devices_inventory()
        success &= self.generate_overview()

        return success

    def generate_network_diagram(self) -> bool:
        """Generate network diagram in Mermaid format"""
        try:
            template = self.jinja_env.get_template('docs/network-diagram.md.j2')

            networks = self.topology['logical_topology'].get('networks', [])
            bridges = self.topology['logical_topology'].get('bridges', [])
            trust_zones = self.topology['logical_topology'].get('trust_zones', {})
            vms = self.topology['compute'].get('vms', [])
            lxc = self.topology['compute'].get('lxc', [])

            content = template.render(
                networks=networks,
                bridges=bridges,
                trust_zones=trust_zones,
                vms=vms,
                lxc=lxc,
                topology_version=self.topology.get('version', '2.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "network-diagram.md"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating network-diagram.md: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_ip_allocation(self) -> bool:
        """Generate IP allocation table"""
        try:
            template = self.jinja_env.get_template('docs/ip-allocation.md.j2')

            networks = self.topology['logical_topology'].get('networks', [])

            # Collect all IP allocations
            allocations = []
            for network in networks:
                for allocation in network.get('ip_allocations', []):
                    allocations.append({
                        'network': network['id'],
                        'cidr': network['cidr'],
                        'ip': allocation['ip'],
                        'device': allocation.get('device_ref', allocation.get('vm_ref', allocation.get('lxc_ref', 'unknown'))),
                        'interface': allocation.get('interface', '-'),
                        'description': allocation.get('description', '')
                    })

            content = template.render(
                networks=networks,
                allocations=allocations,
                topology_version=self.topology.get('version', '2.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "ip-allocation.md"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating ip-allocation.md: {e}")
            return False

    def generate_services_inventory(self) -> bool:
        """Generate services inventory"""
        try:
            template = self.jinja_env.get_template('docs/services.md.j2')

            services = self.topology.get('services', [])

            # Enrich services with host information
            lxc_map = {lxc['id']: lxc for lxc in self.topology['compute'].get('lxc', [])}
            vm_map = {vm['id']: vm for vm in self.topology['compute'].get('vms', [])}

            enriched_services = []
            for service in services:
                enriched = service.copy()

                # Get host info
                if 'lxc_ref' in service:
                    host = lxc_map.get(service['lxc_ref'], {})
                    enriched['host_name'] = host.get('name', 'unknown')
                    enriched['host_type'] = 'LXC'
                elif 'vm_ref' in service:
                    host = vm_map.get(service['vm_ref'], {})
                    enriched['host_name'] = host.get('name', 'unknown')
                    enriched['host_type'] = 'VM'
                elif 'device_ref' in service:
                    enriched['host_name'] = service['device_ref']
                    enriched['host_type'] = 'Device'
                else:
                    enriched['host_name'] = 'unknown'
                    enriched['host_type'] = 'unknown'

                enriched_services.append(enriched)

            content = template.render(
                services=enriched_services,
                topology_version=self.topology.get('version', '2.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "services.md"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating services.md: {e}")
            return False

    def generate_devices_inventory(self) -> bool:
        """Generate devices inventory"""
        try:
            template = self.jinja_env.get_template('docs/devices.md.j2')

            devices = self.topology['physical_topology'].get('devices', [])
            vms = self.topology['compute'].get('vms', [])
            lxc = self.topology['compute'].get('lxc', [])
            storage = self.topology.get('storage', [])

            content = template.render(
                devices=devices,
                vms=vms,
                lxc=lxc,
                storage=storage,
                topology_version=self.topology.get('version', '2.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "devices.md"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating devices.md: {e}")
            return False

    def generate_overview(self) -> bool:
        """Generate infrastructure overview"""
        try:
            template = self.jinja_env.get_template('docs/overview.md.j2')

            metadata = self.topology.get('metadata', {})
            devices = self.topology['physical_topology'].get('devices', [])
            networks = self.topology['logical_topology'].get('networks', [])
            vms = self.topology['compute'].get('vms', [])
            lxc = self.topology['compute'].get('lxc', [])
            services = self.topology.get('services', [])
            storage = self.topology.get('storage', [])

            # Calculate statistics
            stats = {
                'total_devices': len(devices),
                'total_vms': len(vms),
                'total_lxc': len(lxc),
                'total_networks': len(networks),
                'total_services': len(services),
                'total_storage': len(storage),
            }

            content = template.render(
                metadata=metadata,
                stats=stats,
                topology_version=self.topology.get('version', '2.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "overview.md"
            output_file.write_text(content)
            print(f"✓ Generated: {output_file}")
            return True

        except Exception as e:
            print(f"❌ Error generating overview.md: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "="*70)
        print("Documentation Generation Summary")
        print("="*70)

        print(f"\n✓ Generated documentation:")
        print(f"  - Network diagram (Mermaid)")
        print(f"  - IP allocation table")
        print(f"  - Services inventory")
        print(f"  - Devices inventory")
        print(f"  - Infrastructure overview")
        print(f"\n✓ Output directory: {self.output_dir}")
        print(f"\nFiles created:")
        for file in sorted(self.output_dir.glob("*.md")):
            print(f"  - {file.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate documentation from topology v2.0"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--output",
        default="generated/docs",
        help="Output directory for documentation (default: generated/docs/)"
    )
    parser.add_argument(
        "--templates",
        default="scripts/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = DocumentationGenerator(args.topology, args.output, args.templates)

    print("="*70)
    print("Documentation Generator (Topology v2.0)")
    print("="*70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\n📝 Generating documentation...\n")

    if not generator.generate_all():
        print("\n❌ Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\n✅ Documentation generation completed successfully!\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate documentation from topology v4.0

Usage:
    python3 topology-tools/generate-docs.py [--topology topology.yaml] [--output generated/docs/]

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
from datetime import datetime

# Import topology loader with !include support
from topology_loader import load_topology


class DocumentationGenerator:
    """Generate documentation from topology v4.0"""

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

        # Add custom filters for Mermaid diagram generation
        self.jinja_env.filters['mermaid_id'] = self._mermaid_id

    @staticmethod
    def _mermaid_id(value: str) -> str:
        """Convert string to valid Mermaid node ID (alphanumeric + underscore)"""
        if not value:
            return 'unknown'
        return value.replace('-', '_').replace('.', '_').replace(' ', '_').replace('/', '_')

    def _get_resolved_networks(self):
        """Resolve L2 networks with optional network profile defaults."""
        l2 = self.topology.get('L2_network', {})
        profiles = l2.get('network_profiles', {}) or {}
        resolved = []

        for network in l2.get('networks', []) or []:
            merged = {}
            profile_ref = network.get('profile_ref')
            if profile_ref and profile_ref in profiles and isinstance(profiles[profile_ref], dict):
                merged.update(profiles[profile_ref])
            merged.update(network)
            resolved.append(merged)

        return resolved

    def load_topology(self) -> bool:
        """Load topology YAML file (with !include support)"""
        try:
            self.topology = load_topology(str(self.topology_path))
            print(f"OK Loaded topology: {self.topology_path}")

            required = ['L0_meta', 'L1_foundation', 'L2_network', 'L4_platform']
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
        """Generate all documentation files"""
        if self.output_dir.exists():
            print(f"CLEAN Cleaning output directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"DIR Created output directory: {self.output_dir}")

        success = True
        success &= self.generate_network_diagram()
        success &= self.generate_ip_allocation()
        success &= self.generate_services_inventory()
        success &= self.generate_devices_inventory()
        success &= self.generate_overview()

        # Visual diagrams (Phase 1)
        success &= self.generate_physical_topology()
        success &= self.generate_vlan_topology()
        success &= self.generate_trust_zones()
        success &= self.generate_service_dependencies()

        # Visual diagrams (Phase 2)
        success &= self.generate_storage_topology()
        success &= self.generate_monitoring_topology()
        success &= self.generate_vpn_topology()

        # Visual diagrams (Phase 3)
        success &= self.generate_qos_topology()
        success &= self.generate_certificates_topology()
        success &= self.generate_ups_topology()

        # Index & navigation (Phase 4)
        success &= self.generate_diagrams_index()

        return success

    def generate_network_diagram(self) -> bool:
        """Generate network diagram in Mermaid format"""
        try:
            template = self.jinja_env.get_template('docs/network-diagram.md.j2')

            networks = self._get_resolved_networks()
            bridges = self.topology['L2_network'].get('bridges', [])
            trust_zones = self.topology['L2_network'].get('trust_zones', {})
            vms = self.topology['L4_platform'].get('vms', [])
            lxc = self.topology['L4_platform'].get('lxc', [])

            content = template.render(
                networks=networks,
                bridges=bridges,
                trust_zones=trust_zones,
                vms=vms,
                lxc=lxc,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "network-diagram.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating network-diagram.md: {e}")
            import traceback
            traceback.print_exc()
            return False

    def generate_ip_allocation(self) -> bool:
        """Generate IP allocation table"""
        try:
            template = self.jinja_env.get_template('docs/ip-allocation.md.j2')

            networks = self._get_resolved_networks()

            allocations = []
            for network in networks:
                for allocation in network.get('ip_allocations', []) or []:
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
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "ip-allocation.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating ip-allocation.md: {e}")
            return False

    def generate_services_inventory(self) -> bool:
        """Generate services inventory"""
        try:
            template = self.jinja_env.get_template('docs/services.md.j2')

            services = self.topology.get('L5_application', {}).get('services', [])

            lxc_map = {lxc['id']: lxc for lxc in self.topology['L4_platform'].get('lxc', [])}
            vm_map = {vm['id']: vm for vm in self.topology['L4_platform'].get('vms', [])}

            enriched_services = []
            for service in services:
                enriched = service.copy()

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
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "services.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating services.md: {e}")
            return False

    def generate_devices_inventory(self) -> bool:
        """Generate devices inventory"""
        try:
            template = self.jinja_env.get_template('docs/devices.md.j2')

            devices = self.topology['L1_foundation'].get('devices', [])
            vms = self.topology['L4_platform'].get('vms', [])
            lxc = self.topology['L4_platform'].get('lxc', [])
            storage = self.topology.get('L3_data', {}).get('storage', [])

            content = template.render(
                devices=devices,
                vms=vms,
                lxc=lxc,
                storage=storage,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "devices.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating devices.md: {e}")
            return False

    def generate_overview(self) -> bool:
        """Generate infrastructure overview"""
        try:
            template = self.jinja_env.get_template('docs/overview.md.j2')

            metadata = self.topology.get('L0_meta', {}).get('metadata', {})
            devices = self.topology['L1_foundation'].get('devices', [])
            networks = self.topology['L2_network'].get('networks', [])
            vms = self.topology['L4_platform'].get('vms', [])
            lxc = self.topology['L4_platform'].get('lxc', [])
            services = self.topology.get('L5_application', {}).get('services', [])
            storage = self.topology.get('L3_data', {}).get('storage', [])

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
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "overview.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating overview.md: {e}")
            return False

    def generate_physical_topology(self) -> bool:
        """Generate physical infrastructure topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/physical-topology.md.j2')

            devices = self.topology['L1_foundation'].get('devices', [])
            locations = self.topology['L1_foundation'].get('locations', [])
            physical_links = self.topology['L1_foundation'].get('data_links', [])

            content = template.render(
                devices=devices,
                locations=locations,
                physical_links=physical_links,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "physical-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating physical-topology.md: {e}")
            return False

    def generate_vlan_topology(self) -> bool:
        """Generate VLAN topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/vlan-topology.md.j2')

            networks = self._get_resolved_networks()
            bridges = self.topology['L2_network'].get('bridges', [])

            content = template.render(
                networks=networks,
                bridges=bridges,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "vlan-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating vlan-topology.md: {e}")
            return False

    def generate_trust_zones(self) -> bool:
        """Generate trust zone security diagram"""
        try:
            template = self.jinja_env.get_template('docs/trust-zones.md.j2')

            trust_zones = self.topology['L2_network'].get('trust_zones', {})
            firewall_policies = self.topology['L2_network'].get('firewall_policies', [])
            networks = self._get_resolved_networks()

            content = template.render(
                trust_zones=trust_zones,
                firewall_policies=firewall_policies,
                networks=networks,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "trust-zones.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating trust-zones.md: {e}")
            return False

    def generate_service_dependencies(self) -> bool:
        """Generate service dependency diagram"""
        try:
            template = self.jinja_env.get_template('docs/service-dependencies.md.j2')

            services = self.topology.get('L5_application', {}).get('services', [])
            lxc = self.topology['L4_platform'].get('lxc', [])

            content = template.render(
                services=services,
                lxc=lxc,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "service-dependencies.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating service-dependencies.md: {e}")
            return False

    def generate_storage_topology(self) -> bool:
        """Generate storage topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/storage-topology.md.j2')

            storage = self.topology.get('L3_data', {}).get('storage', [])
            data_assets = self.topology.get('L3_data', {}).get('data_assets', [])
            devices = self.topology['L1_foundation'].get('devices', [])

            content = template.render(
                storage=storage,
                data_assets=data_assets,
                devices=devices,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "storage-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating storage-topology.md: {e}")
            return False

    def generate_monitoring_topology(self) -> bool:
        """Generate monitoring topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/monitoring-topology.md.j2')

            observability = self.topology.get('L6_observability', {})
            services = self.topology.get('L5_application', {}).get('services', [])
            healthchecks = observability.get('healthchecks', [])
            network_monitoring = observability.get('network_monitoring', [])
            alerts = observability.get('alerts', [])
            notification_channels = observability.get('notification_channels', [])
            dashboard = observability.get('dashboard', {})

            content = template.render(
                services=services,
                healthchecks=healthchecks,
                network_monitoring=network_monitoring,
                alerts=alerts,
                notification_channels=notification_channels,
                dashboard=dashboard,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "monitoring-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating monitoring-topology.md: {e}")
            return False

    def generate_vpn_topology(self) -> bool:
        """Generate VPN topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/vpn-topology.md.j2')

            networks = self.topology['L2_network'].get('networks', [])
            firewall_policies = self.topology['L2_network'].get('firewall_policies', [])
            trust_zones = self.topology['L2_network'].get('trust_zones', {})
            services = self.topology.get('L5_application', {}).get('services', [])
            devices = self.topology['L1_foundation'].get('devices', [])

            vpn_networks = [net for net in networks if net.get('vpn_type')]
            vpn_network_ids = {net['id'] for net in vpn_networks}
            vpn_services = [svc for svc in services if svc.get('type') == 'vpn']

            vpn_access = {}
            for policy in firewall_policies:
                if policy.get('action') != 'accept':
                    continue
                source_network = policy.get('source_network_ref')
                if source_network not in vpn_network_ids:
                    continue

                destinations = []
                if policy.get('destination_zones_ref'):
                    destinations.extend(policy['destination_zones_ref'])
                if policy.get('destination_zone_ref'):
                    destinations.append(policy['destination_zone_ref'])
                if policy.get('destination_network_ref'):
                    destinations.append(policy['destination_network_ref'])
                if not destinations:
                    continue

                vpn_access.setdefault(source_network, set()).update(destinations)

            vpn_access_list = [
                {"network_id": net_id, "destinations": sorted(list(zones))}
                for net_id, zones in sorted(vpn_access.items())
            ]

            content = template.render(
                vpn_networks=vpn_networks,
                vpn_services=vpn_services,
                vpn_access=vpn_access_list,
                trust_zones=trust_zones,
                devices=devices,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "vpn-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating vpn-topology.md: {e}")
            return False

    def generate_qos_topology(self) -> bool:
        """Generate QoS topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/qos-topology.md.j2')

            qos = self.topology['L2_network'].get('qos', {})
            networks = self.topology['L2_network'].get('networks', [])
            devices = self.topology['L1_foundation'].get('devices', [])

            content = template.render(
                qos=qos,
                networks=networks,
                devices=devices,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "qos-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating qos-topology.md: {e}")
            return False

    def generate_certificates_topology(self) -> bool:
        """Generate certificates topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/certificates-topology.md.j2')

            certificates = self.topology.get('L5_application', {}).get('certificates', {})
            services = self.topology.get('L5_application', {}).get('services', [])
            devices = self.topology['L1_foundation'].get('devices', [])

            content = template.render(
                certificates=certificates,
                services=services,
                devices=devices,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "certificates-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating certificates-topology.md: {e}")
            return False

    def generate_ups_topology(self) -> bool:
        """Generate UPS topology diagram"""
        try:
            template = self.jinja_env.get_template('docs/ups-topology.md.j2')

            l7_power = (self.topology.get('L7_operations', {}) or {}).get('power_resilience', {}) or {}
            ups = l7_power.get('policies', []) or []
            devices = self.topology['L1_foundation'].get('devices', [])
            healthchecks = self.topology.get('L6_observability', {}).get('healthchecks', [])
            alerts = self.topology.get('L6_observability', {}).get('alerts', [])

            content = template.render(
                ups=ups,
                devices=devices,
                healthchecks=healthchecks,
                alerts=alerts,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "ups-topology.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating ups-topology.md: {e}")
            return False

    def generate_diagrams_index(self) -> bool:
        """Generate diagrams index and navigation page"""
        try:
            template = self.jinja_env.get_template('docs/diagrams-index.md.j2')

            docs_index = {
                "core": [
                    {"title": "Infrastructure Overview", "file": "overview.md", "description": "Summary and metadata"},
                    {"title": "Network Diagram", "file": "network-diagram.md", "description": "Layered network map"},
                    {"title": "IP Allocation", "file": "ip-allocation.md", "description": "Address assignments"},
                    {"title": "Services Inventory", "file": "services.md", "description": "Service catalog"},
                    {"title": "Devices Inventory", "file": "devices.md", "description": "Hardware and platform inventory"},
                ],
                "phase1": [
                    {"title": "Physical Topology", "file": "physical-topology.md", "description": "Physical devices and links"},
                    {"title": "VLAN Topology", "file": "vlan-topology.md", "description": "VLAN segmentation and trunking"},
                    {"title": "Trust Zones", "file": "trust-zones.md", "description": "Security zones and firewall matrix"},
                    {"title": "Service Dependencies", "file": "service-dependencies.md", "description": "Application dependency graph"},
                ],
                "phase2": [
                    {"title": "Storage Topology", "file": "storage-topology.md", "description": "Storage pools and data assets"},
                    {"title": "Monitoring Topology", "file": "monitoring-topology.md", "description": "Observability pipeline"},
                    {"title": "VPN Topology", "file": "vpn-topology.md", "description": "Remote access and VPN scope"},
                ],
                "phase3": [
                    {"title": "QoS Topology", "file": "qos-topology.md", "description": "Traffic classes and limits"},
                    {"title": "Certificates Topology", "file": "certificates-topology.md", "description": "PKI and cert distribution"},
                    {"title": "UPS Topology", "file": "ups-topology.md", "description": "Power protection and shutdown flow"},
                ],
            }

            total_docs = sum(len(items) for items in docs_index.values())

            content = template.render(
                docs_index=docs_index,
                total_docs=total_docs,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )

            output_file = self.output_dir / "diagrams-index.md"
            output_file.write_text(content, encoding="utf-8")
            print(f"OK Generated: {output_file}")
            return True

        except Exception as e:
            print(f"ERROR Error generating diagrams-index.md: {e}")
            return False

    def print_summary(self):
        """Print generation summary"""
        print("\n" + "="*70)
        print("Documentation Generation Summary")
        print("="*70)

        print(f"\nOK Generated documentation:")
        print(f"  Core:")
        print(f"    - Network diagram (Mermaid)")
        print(f"    - IP allocation table")
        print(f"    - Services inventory")
        print(f"    - Devices inventory")
        print(f"    - Infrastructure overview")
        print(f"  Visual Diagrams:")
        print(f"    - Physical topology (Mermaid)")
        print(f"    - VLAN topology (Mermaid)")
        print(f"    - Trust zones (Mermaid)")
        print(f"    - Service dependencies (Mermaid)")
        print(f"    - Storage topology (Mermaid)")
        print(f"    - Monitoring topology (Mermaid)")
        print(f"    - VPN topology (Mermaid)")
        print(f"    - QoS topology (Mermaid)")
        print(f"    - Certificates topology (Mermaid)")
        print(f"    - UPS topology (Mermaid)")
        print(f"  Navigation:")
        print(f"    - Diagrams index")
        print(f"\nOK Output directory: {self.output_dir}")
        print(f"\nFiles created:")
        for file in sorted(self.output_dir.glob("*.md")):
            print(f"  - {file.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate documentation from topology v4.0"
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
        default="topology-tools/templates",
        help="Directory containing Jinja2 templates"
    )

    args = parser.parse_args()

    generator = DocumentationGenerator(args.topology, args.output, args.templates)

    print("="*70)
    print("Documentation Generator (Topology v4.0)")
    print("="*70)
    print()

    if not generator.load_topology():
        sys.exit(1)

    print("\nGEN Generating documentation...\n")

    if not generator.generate_all():
        print("\nERROR Generation failed with errors")
        sys.exit(1)

    generator.print_summary()
    print("\nOK Documentation generation completed successfully!\n")


if __name__ == "__main__":
    main()

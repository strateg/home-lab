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
import re
import json
import base64
from pathlib import Path
from typing import Dict
from urllib.parse import quote
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

# Import topology loader with !include support
from topology_loader import load_topology
from docs_diagrams import DiagramDocumentationGenerator


class DocumentationGenerator:
    """Generate documentation from topology v4.0"""

    ICON_NODE_RE = re.compile(
        r'^(?P<indent>\s*)(?P<node_id>[A-Za-z0-9_]+)@\{\s*'
        r'(?:(?!\}\s*$).)*?icon:\s*"(?P<icon>[^"]+)"'
        r'(?:(?!\}\s*$).)*?label:\s*"(?P<label>[^"]*)"'
        r'(?:(?!\}\s*$).)*?\}\s*$'
    )

    def __init__(
        self,
        topology_path: str,
        output_dir: str,
        templates_dir: str = "topology-tools/templates",
        mermaid_icons: bool = True,
        mermaid_icon_nodes: bool = True,
    ):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        self.mermaid_icons = mermaid_icons
        self.mermaid_icon_nodes = mermaid_icon_nodes
        self.topology: Dict = {}
        self._icon_pack_cache = None
        self._icon_data_uri_cache = {}

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Add custom filters for Mermaid diagram generation
        self.jinja_env.filters['mermaid_id'] = self._mermaid_id
        self.diagram_generator = DiagramDocumentationGenerator(self)

    def _load_icon_packs(self):
        if self._icon_pack_cache is not None:
            return self._icon_pack_cache

        mapping = {
            "mdi": "mdi",
            "si": "simple-icons",
            "logos": "logos",
        }
        packs = {}
        base_dir = Path.cwd() / "node_modules" / "@iconify-json"
        for prefix, package_dir in mapping.items():
            icon_file = base_dir / package_dir / "icons.json"
            if not icon_file.exists():
                continue
            try:
                data = json.loads(icon_file.read_text(encoding="utf-8"))
                packs[prefix] = data
            except Exception:
                # Ignore malformed local packs and fall back to remote URL mode.
                continue

        self._icon_pack_cache = packs
        return packs

    @staticmethod
    def _icon_svg_from_pack(pack: Dict, icon_name: str) -> str:
        if not isinstance(pack, dict):
            return ""
        icons = pack.get("icons", {}) or {}
        icon = icons.get(icon_name)
        if not isinstance(icon, dict):
            return ""
        body = icon.get("body")
        if not body:
            return ""
        width = icon.get("width", pack.get("width", 24))
        height = icon.get("height", pack.get("height", 24))
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">{body}</svg>'

    def _local_icon_src(self, icon_id: str) -> str:
        if icon_id in self._icon_data_uri_cache:
            return self._icon_data_uri_cache[icon_id]
        if ":" not in (icon_id or ""):
            return ""
        prefix, icon_name = icon_id.split(":", 1)
        packs = self._load_icon_packs()
        pack = packs.get(prefix)
        if not pack:
            return ""
        svg = self._icon_svg_from_pack(pack, icon_name)
        if not svg:
            return ""
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        data_uri = f"data:image/svg+xml;base64,{encoded}"
        self._icon_data_uri_cache[icon_id] = data_uri
        return data_uri

    def _icon_html(self, icon_id: str) -> str:
        """
        Build HTML icon label.
        Prefer local icon assets from installed Iconify JSON packs.
        Fallback to remote Iconify API if local packs are unavailable.
        """
        local_src = self._local_icon_src(icon_id)
        if local_src:
            return f"<img src='{local_src}' height='16'/>"

        safe_icon = quote(icon_id or "mdi:help-circle-outline", safe="")
        return f"<img src='https://api.iconify.design/{safe_icon}.svg' height='16'/>"

    def transform_mermaid_icons_for_compat(self, content: str) -> str:
        """
        Convert Mermaid icon-node syntax to regular nodes with inline HTML icons.
        This keeps icon visuals for renderers that do not support `@{ icon: ... }`.
        """
        if not self.mermaid_icons or self.mermaid_icon_nodes:
            return content

        converted_lines = []
        for line in content.splitlines():
            match = self.ICON_NODE_RE.match(line)
            if not match:
                converted_lines.append(line)
                continue

            indent = match.group("indent")
            node_id = match.group("node_id")
            icon_id = match.group("icon")
            label = match.group("label").replace('"', '\\"')
            icon_html = self._icon_html(icon_id)
            converted_lines.append(f'{indent}{node_id}["{icon_html} {label}"]')

        return "\n".join(converted_lines)

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
        success &= self.diagram_generator.generate_all()

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
                network_icons={
                    net.get('id'): self.diagram_generator._network_icon(net)
                    for net in networks
                    if isinstance(net, dict) and net.get('id')
                },
                lxc_icons={
                    item.get('id'): (
                        'mdi:docker'
                        if 'docker' in str(item.get('type', '')).lower()
                        else 'mdi:cube-outline'
                    )
                    for item in lxc
                    if isinstance(item, dict) and item.get('id')
                },
                zone_icons=self.diagram_generator.ZONE_ICON_MAP,
                use_mermaid_icons=self.mermaid_icons,
                mermaid_icon_pack_hint=self.diagram_generator.ICON_PACK_HINT,
                topology_version=self.topology.get('L0_meta', {}).get('version', '4.0.0'),
                generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            content = self.transform_mermaid_icons_for_compat(content)

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
        for item in self.diagram_generator.summary_items():
            print(f"    - {item}")
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
    parser.add_argument(
        "--mermaid-icons",
        action="store_true",
        dest="mermaid_icons",
        help="Enable Mermaid icon-node syntax (requires Mermaid renderer with icon-node support)"
    )
    parser.add_argument(
        "--no-mermaid-icons",
        action="store_false",
        dest="mermaid_icons",
        help="Disable Mermaid icon-node syntax and use plain Mermaid nodes"
    )
    parser.add_argument(
        "--mermaid-icon-nodes",
        action="store_true",
        dest="mermaid_icon_nodes",
        help="Emit raw Mermaid `@{ icon: ... }` node syntax (default; requires Mermaid with icon-node support)"
    )
    parser.add_argument(
        "--mermaid-icon-compat",
        action="store_false",
        dest="mermaid_icon_nodes",
        help="Use compatibility icon rendering: convert icon-nodes into standard nodes with inline icons"
    )
    parser.set_defaults(mermaid_icons=True, mermaid_icon_nodes=True)

    args = parser.parse_args()

    generator = DocumentationGenerator(
        args.topology,
        args.output,
        args.templates,
        mermaid_icons=args.mermaid_icons,
        mermaid_icon_nodes=args.mermaid_icon_nodes,
    )

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

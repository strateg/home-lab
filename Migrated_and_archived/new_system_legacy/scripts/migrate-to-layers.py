#!/usr/bin/env python3
"""
Migrate topology v3 to OSI-layer architecture v4

This script reorganizes the current topology structure into a 7-layer
architecture following OSI model principles:

L0: Meta       - version, defaults, global policies
L1: Foundation - physical devices, interfaces, UPS
L2: Network    - networks, bridges, trust zones, firewall, DNS, QoS
L3: Data       - storage pools, backup policies
L4: Platform   - VMs, LXC containers, templates, ansible config
L5: Application - services, certificates
L6: Observability - monitoring, healthchecks, alerts, dashboards
L7: Operations - workflows, runbooks, documentation, notes

Usage:
    python3 scripts/migrate-to-layers.py [--dry-run]
"""

import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Import topology loader
from topology_loader import load_topology


class LayerMigrator:
    """Migrate topology to OSI-layer architecture"""

    LAYER_HEADER = """# Layer {level}: {name} - {description}
# Part of Home Lab Topology v4.0.0 (OSI-Layer Architecture)
# Dependencies: {dependencies}
# Provides: {provides}
# Edit this file then regenerate: python3 scripts/regenerate-all.py

"""

    LAYERS = {
        0: {
            'name': 'Meta',
            'file': 'L0-meta.yaml',
            'description': 'Project metadata and global policies',
            'dependencies': 'None (root layer)',
            'provides': 'version, defaults, policies for all layers',
        },
        1: {
            'name': 'Foundation',
            'file': 'L1-foundation.yaml',
            'description': 'Physical infrastructure',
            'dependencies': 'L0 (meta) for defaults',
            'provides': 'device_id, interface_id, disk_id for upper layers',
        },
        2: {
            'name': 'Network',
            'file': 'L2-network.yaml',
            'description': 'Network infrastructure',
            'dependencies': 'L1 (foundation) for device_ref, interface_ref',
            'provides': 'network_id, bridge_id, trust_zone_id for upper layers',
        },
        3: {
            'name': 'Data',
            'file': 'L3-data.yaml',
            'description': 'Storage and backup',
            'dependencies': 'L1 (device_ref, disk_ref), L2 (network access)',
            'provides': 'storage_id, backup_policy_id for upper layers',
        },
        4: {
            'name': 'Platform',
            'file': 'L4-platform.yaml',
            'description': 'Compute resources',
            'dependencies': 'L1 (device_ref), L2 (network_ref, bridge_ref), L3 (storage_ref)',
            'provides': 'vm_id, lxc_id for upper layers',
        },
        5: {
            'name': 'Application',
            'file': 'L5-application.yaml',
            'description': 'Services and applications',
            'dependencies': 'L1 (device_ref), L2 (network_ref), L4 (lxc_ref, vm_ref)',
            'provides': 'service_id, certificate_id for upper layers',
        },
        6: {
            'name': 'Observability',
            'file': 'L6-observability.yaml',
            'description': 'Monitoring and alerting',
            'dependencies': 'L1 (device_ref), L4 (lxc_ref), L5 (service_ref)',
            'provides': 'healthcheck_id, alert_id for upper layers',
        },
        7: {
            'name': 'Operations',
            'file': 'L7-operations.yaml',
            'description': 'Workflows and documentation',
            'dependencies': 'All lower layers (L1-L6)',
            'provides': 'Nothing (top layer)',
        },
    }

    def __init__(self, topology_dir: Path, dry_run: bool = False):
        self.topology_dir = topology_dir
        self.dry_run = dry_run
        self.topology: Dict[str, Any] = {}
        self.layers: Dict[int, Dict[str, Any]] = {i: {} for i in range(8)}

    def load_current_topology(self) -> bool:
        """Load current topology with all includes"""
        try:
            topology_path = self.topology_dir.parent / 'topology.yaml'
            self.topology = load_topology(str(topology_path))
            print(f"✓ Loaded current topology from {topology_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to load topology: {e}")
            return False

    def migrate(self) -> bool:
        """Run the migration"""
        print("\n" + "=" * 70)
        print("Topology Migration: v3 → v4 (OSI-Layer Architecture)")
        print("=" * 70)

        if not self.load_current_topology():
            return False

        print("\n📦 Reorganizing content into layers...\n")

        # Extract content into layers
        self._extract_l0_meta()
        self._extract_l1_foundation()
        self._extract_l2_network()
        self._extract_l3_data()
        self._extract_l4_platform()
        self._extract_l5_application()
        self._extract_l6_observability()
        self._extract_l7_operations()

        if self.dry_run:
            print("\n🔍 DRY RUN - No files written")
            self._print_summary()
            return True

        # Write layer files
        print("\n📝 Writing layer files...\n")
        for level in range(8):
            self._write_layer(level)

        # Update main topology.yaml
        self._write_main_topology()

        # Clean up old files
        self._cleanup_old_files()

        self._print_summary()
        return True

    def _extract_l0_meta(self):
        """Extract Layer 0: Meta"""
        metadata = self.topology.get('metadata', {})
        security = self.topology.get('security', {})

        self.layers[0] = {
            'version': self.topology.get('version', '4.0.0'),
            'schema_version': '1.0',
            'project': {
                'name': 'Home Lab',
                'description': metadata.get('description', 'Infrastructure-as-Data home lab'),
                'org': metadata.get('org', 'home-lab'),
                'environment': metadata.get('environment', 'production'),
                'maintainer': metadata.get('author', 'admin'),
            },
            'changelog': [
                {
                    'version': '4.0.0',
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'changes': [
                        'Migrated to OSI-layer architecture',
                        'Introduced layer-based reference system',
                    ]
                }
            ],
            'defaults': {
                'dns': {
                    'nameservers': ['192.168.88.1', '1.1.1.1'],
                    'searchdomain': 'home.local',
                },
                'timezone': 'UTC',
                'locale': 'en_US.UTF-8',
            },
            'policies': {
                'ssh': security.get('proxmox', {}).get('ssh', {
                    'permit_root_login': 'prohibit-password',
                    'password_authentication': False,
                }),
                'firewall': {
                    'default_action': 'drop',
                    'log_blocked': True,
                },
            },
        }
        print("  ✓ L0: Meta extracted")

    def _extract_l1_foundation(self):
        """Extract Layer 1: Foundation (physical devices)"""
        physical = self.topology.get('physical_topology', {})

        self.layers[1] = {
            'locations': physical.get('locations', []),
            'devices': physical.get('devices', []),
            'ups': physical.get('ups', []),
        }
        print(f"  ✓ L1: Foundation extracted ({len(self.layers[1].get('devices', []))} devices)")

    def _extract_l2_network(self):
        """Extract Layer 2: Network"""
        logical = self.topology.get('logical_topology', {})

        self.layers[2] = {
            'trust_zones': logical.get('trust_zones', {}),
            'networks': logical.get('networks', []),
            'bridges': logical.get('bridges', []),
            'routing': logical.get('routing', []),
            'firewall_policies': logical.get('firewall_policies', []),
            'dns': logical.get('dns', {}),
            'qos': logical.get('qos', {}),
        }
        print(f"  ✓ L2: Network extracted ({len(self.layers[2].get('networks', []))} networks)")

    def _extract_l3_data(self):
        """Extract Layer 3: Data (storage and backup)"""
        storage = self.topology.get('storage', [])
        backup = self.topology.get('backup', {})

        self.layers[3] = {
            'storage_pools': storage,
            'backup_policies': backup.get('policies', []),
            'backup_schedule': backup.get('schedule', {}),
            'retention': backup.get('retention', {}),
        }
        print(f"  ✓ L3: Data extracted ({len(storage)} storage pools)")

    def _extract_l4_platform(self):
        """Extract Layer 4: Platform (compute)"""
        compute = self.topology.get('compute', {})
        ansible_cfg = self.topology.get('ansible', {})

        self.layers[4] = {
            'vms': compute.get('vms', []),
            'lxc': compute.get('lxc', []),
            'templates': compute.get('templates', {}),
            'ansible_config': {
                'group_vars': ansible_cfg.get('group_vars', {}),
                'host_vars': ansible_cfg.get('host_vars', {}),
                'config': ansible_cfg.get('config', {}),
            },
        }
        lxc_count = len(self.layers[4].get('lxc', []))
        vm_count = len(self.layers[4].get('vms', []))
        print(f"  ✓ L4: Platform extracted ({lxc_count} LXC, {vm_count} VMs)")

    def _extract_l5_application(self):
        """Extract Layer 5: Application (services)"""
        services_data = self.topology.get('services', {})
        security = self.topology.get('security', {})

        # Handle both list and dict with 'items' key
        if isinstance(services_data, dict):
            services = services_data.get('items', [])
            certificates = services_data.get('ssl_certificates', {})
        else:
            services = services_data
            certificates = {}

        self.layers[5] = {
            'services': services,
            'certificates': certificates or security.get('certificates', {}),
        }
        print(f"  ✓ L5: Application extracted ({len(services)} services)")

    def _extract_l6_observability(self):
        """Extract Layer 6: Observability"""
        monitoring = self.topology.get('monitoring', {})

        self.layers[6] = {
            'healthchecks': monitoring.get('healthchecks', []),
            'alerts': monitoring.get('alerts', []),
            'notification_channels': monitoring.get('notification_channels', []),
            'dashboards': monitoring.get('dashboards', []),
            'metrics': monitoring.get('metrics', {}),
        }
        hc_count = len(self.layers[6].get('healthchecks', []))
        alert_count = len(self.layers[6].get('alerts', []))
        print(f"  ✓ L6: Observability extracted ({hc_count} healthchecks, {alert_count} alerts)")

    def _extract_l7_operations(self):
        """Extract Layer 7: Operations"""
        workflows = self.topology.get('workflows', {})
        documentation = self.topology.get('documentation', {})
        notes = self.topology.get('notes', [])

        self.layers[7] = {
            'workflows': workflows,
            'runbooks': [],  # New section
            'documentation': documentation,
            'notes': notes,
        }
        print("  ✓ L7: Operations extracted")

    def _write_layer(self, level: int):
        """Write a single layer file"""
        layer_info = self.LAYERS[level]
        output_path = self.topology_dir / layer_info['file']

        header = self.LAYER_HEADER.format(
            level=level,
            name=layer_info['name'],
            description=layer_info['description'],
            dependencies=layer_info['dependencies'],
            provides=layer_info['provides'],
        )

        content = yaml.dump(
            self.layers[level],
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )

        with open(output_path, 'w') as f:
            f.write(header)
            f.write(content)

        print(f"  ✓ Written: {output_path.name}")

    def _write_main_topology(self):
        """Write updated main topology.yaml"""
        main_topology = f"""# Home Lab Topology v4.0.0 - OSI-Layer Architecture
#
# This file uses !include directives to load modular layer files.
# Layers are processed in order L0 → L7 (dependencies resolved bottom-up).
#
# Layer Structure:
#   L0: Meta        - version, defaults, policies
#   L1: Foundation  - physical devices, interfaces
#   L2: Network     - networks, bridges, firewall
#   L3: Data        - storage, backup policies
#   L4: Platform    - VMs, LXC containers
#   L5: Application - services, certificates
#   L6: Observability - monitoring, alerts
#   L7: Operations  - workflows, documentation
#
# Edit layer files then regenerate: python3 scripts/regenerate-all.py

version: "4.0.0"

# Load layers in dependency order
meta: !include topology/L0-meta.yaml
foundation: !include topology/L1-foundation.yaml
network: !include topology/L2-network.yaml
data: !include topology/L3-data.yaml
platform: !include topology/L4-platform.yaml
application: !include topology/L5-application.yaml
observability: !include topology/L6-observability.yaml
operations: !include topology/L7-operations.yaml
"""

        output_path = self.topology_dir.parent / 'topology.yaml'
        with open(output_path, 'w') as f:
            f.write(main_topology)

        print(f"\n  ✓ Written: topology.yaml (main file)")

    def _cleanup_old_files(self):
        """Remove old topology files"""
        old_files = [
            'metadata.yaml',
            'physical.yaml',
            'logical.yaml',
            'compute.yaml',
            'storage.yaml',
            'services.yaml',
            'ansible.yaml',
            'workflows.yaml',
            'security.yaml',
            'backup.yaml',
            'monitoring.yaml',
            'documentation.yaml',
            'notes.yaml',
        ]

        print("\n🧹 Cleaning up old files...")
        for old_file in old_files:
            old_path = self.topology_dir / old_file
            if old_path.exists():
                old_path.unlink()
                print(f"  ✓ Removed: {old_file}")

    def _print_summary(self):
        """Print migration summary"""
        print("\n" + "=" * 70)
        print("Migration Summary")
        print("=" * 70)

        print("\n📁 New layer structure:")
        for level in range(8):
            info = self.LAYERS[level]
            content = self.layers[level]
            items = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in content.values())
            print(f"  L{level}: {info['file']:25} ({items} items)")

        print("\n✅ Migration completed!")
        print("\nNext steps:")
        print("  1. Review generated layer files in topology/")
        print("  2. Run: python3 scripts/validate-topology.py")
        print("  3. Run: python3 scripts/regenerate-all.py")
        print("  4. Test: terraform plan && ansible-playbook --check")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate topology to OSI-layer architecture"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--topology-dir",
        default="topology",
        help="Path to topology directory"
    )

    args = parser.parse_args()

    topology_dir = Path(args.topology_dir)
    if not topology_dir.exists():
        print(f"✗ Topology directory not found: {topology_dir}")
        sys.exit(1)

    migrator = LayerMigrator(topology_dir, dry_run=args.dry_run)

    if not migrator.migrate():
        print("\n✗ Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

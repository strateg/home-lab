"""
Topology Loader - Layer-aware YAML loader with !include support

Supports both:
- v3: Modular structure (metadata.yaml, physical.yaml, etc.)
- v4: OSI-layer structure (L0-meta.yaml, L1-foundation.yaml, etc.)

Layer architecture (v4):
  L0: Meta        - version, defaults, policies
  L1: Foundation  - physical devices, interfaces
  L2: Network     - networks, bridges, firewall
  L3: Data        - storage, backup policies
  L4: Platform    - VMs, LXC containers
  L5: Application - services, certificates
  L6: Observability - monitoring, alerts
  L7: Operations  - workflows, documentation
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Layer definitions for v4 architecture
LAYER_ORDER = [
    ('L0', 'meta', 'L0-meta.yaml'),
    ('L1', 'foundation', 'L1-foundation.yaml'),
    ('L2', 'network', 'L2-network.yaml'),
    ('L3', 'data', 'L3-data.yaml'),
    ('L4', 'platform', 'L4-platform.yaml'),
    ('L5', 'application', 'L5-application.yaml'),
    ('L6', 'observability', 'L6-observability.yaml'),
    ('L7', 'operations', 'L7-operations.yaml'),
]

# Mapping from v3 sections to v4 layers
V3_TO_V4_MAPPING = {
    'metadata': 'meta',
    'physical_topology': 'foundation',
    'logical_topology': 'network',
    'storage': 'data',
    'backup': 'data',
    'compute': 'platform',
    'ansible': 'platform',
    'services': 'application',
    'security': 'application',
    'monitoring': 'observability',
    'workflows': 'operations',
    'documentation': 'operations',
    'notes': 'operations',
}


class IncludeLoader(yaml.SafeLoader):
    """Custom YAML loader with !include support"""

    def __init__(self, stream):
        self._root = Path(stream.name).parent if hasattr(stream, 'name') else Path.cwd()
        super().__init__(stream)


def include_constructor(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Construct !include directive"""
    include_path = loader.construct_scalar(node)
    full_path = loader._root / include_path

    if not full_path.exists():
        raise FileNotFoundError(f"Included file not found: {full_path}")

    with open(full_path, 'r') as f:
        return yaml.load(f, IncludeLoader)


# Register the !include constructor
yaml.add_constructor('!include', include_constructor, IncludeLoader)


def load_topology(topology_path: str) -> Dict[str, Any]:
    """
    Load topology YAML with !include support

    Automatically detects v3 or v4 structure and normalizes to common format.

    Args:
        topology_path: Path to main topology.yaml file

    Returns:
        Dictionary with merged topology data

    Raises:
        FileNotFoundError: If topology file not found
        yaml.YAMLError: If YAML parsing fails

    Example:
        >>> topology = load_topology('topology.yaml')
        >>> print(topology['version'])
        4.0.0
    """
    topology_file = Path(topology_path)

    if not topology_file.exists():
        raise FileNotFoundError(f"Topology file not found: {topology_path}")

    with open(topology_file, 'r') as f:
        topology = yaml.load(f, IncludeLoader)

    # Detect and normalize structure
    version = topology.get('version', '3.0.0')
    if version.startswith('4.'):
        # v4 layer structure - normalize to v3 compatible format for generators
        return _normalize_v4_to_v3(topology)
    else:
        # v3 or earlier - return as-is
        return topology


def _normalize_v4_to_v3(topology: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize v4 layer structure to v3 format for backwards compatibility

    This allows existing generators to work with both formats.
    """
    normalized = {
        'version': topology.get('version', '4.0.0'),
    }

    # L0: Meta -> metadata + policies
    meta = topology.get('meta', {})
    normalized['metadata'] = meta.get('project', {})
    # Merge policies into security (for v3 compatibility)

    # L1: Foundation -> physical_topology
    foundation = topology.get('foundation', {})
    normalized['physical_topology'] = {
        'locations': foundation.get('locations', []),
        'devices': foundation.get('devices', []),
        'ups': foundation.get('ups', []),
    }

    # L2: Network -> logical_topology
    network = topology.get('network', {})
    normalized['logical_topology'] = {
        'trust_zones': network.get('trust_zones', {}),
        'networks': network.get('networks', []),
        'bridges': network.get('bridges', []),
        'routing': network.get('routing', []),
        'firewall_policies': network.get('firewall_policies', []),
        'dns': network.get('dns', {}),
        'qos': network.get('qos', {}),
    }

    # L3: Data -> storage + backup
    data = topology.get('data', {})
    normalized['storage'] = data.get('storage_pools', [])
    normalized['backup'] = {
        'policies': data.get('backup_policies', []),
        'schedule': data.get('backup_schedule', {}),
        'retention': data.get('retention', {}),
    }

    # L4: Platform -> compute + ansible
    platform = topology.get('platform', {})
    normalized['compute'] = {
        'vms': platform.get('vms', []),
        'lxc': platform.get('lxc', []),
        'templates': platform.get('templates', {}),
    }
    normalized['ansible'] = platform.get('ansible_config', {})

    # L5: Application -> services + security (certificates)
    application = topology.get('application', {})
    normalized['services'] = {
        'items': application.get('services', []),
        'ssl_certificates': application.get('certificates', {}),
    }
    # Merge certificates into security for v3 compat
    normalized['security'] = {
        'certificates': application.get('certificates', {}),
        'policies': meta.get('policies', {}),
    }

    # L6: Observability -> monitoring
    observability = topology.get('observability', {})
    normalized['monitoring'] = {
        'healthchecks': observability.get('healthchecks', []),
        'alerts': observability.get('alerts', []),
        'notification_channels': observability.get('notification_channels', []),
        'dashboards': observability.get('dashboards', []),
        'metrics': observability.get('metrics', {}),
    }

    # L7: Operations -> workflows + documentation + notes
    operations = topology.get('operations', {})
    normalized['workflows'] = operations.get('workflows', {})
    normalized['documentation'] = operations.get('documentation', {})
    normalized['notes'] = operations.get('notes', [])

    return normalized


def load_layer(topology_path: str, layer: str) -> Dict[str, Any]:
    """
    Load a specific layer from v4 topology

    Args:
        topology_path: Path to main topology.yaml
        layer: Layer name ('meta', 'foundation', 'network', etc.) or ID ('L0', 'L1', etc.)

    Returns:
        Layer data as dictionary

    Example:
        >>> foundation = load_layer('topology.yaml', 'L1')
        >>> print(foundation['devices'][0]['name'])
        Gamayun
    """
    # Normalize layer identifier
    layer_lower = layer.lower()
    layer_key = None

    for lid, lname, lfile in LAYER_ORDER:
        if layer_lower == lid.lower() or layer_lower == lname:
            layer_key = lname
            break

    if not layer_key:
        raise ValueError(f"Unknown layer: {layer}")

    topology = load_topology(topology_path)
    version = topology.get('version', '3.0.0')

    if version.startswith('4.'):
        # Direct v4 layer access
        topology_file = Path(topology_path)
        with open(topology_file, 'r') as f:
            raw_topology = yaml.load(f, IncludeLoader)
        return raw_topology.get(layer_key, {})
    else:
        # Map v3 section to layer
        for v3_section, v4_layer in V3_TO_V4_MAPPING.items():
            if v4_layer == layer_key:
                return topology.get(v3_section, {})
        return {}


def get_layer_level(layer: str) -> int:
    """Get numeric level of a layer (0-7)"""
    for lid, lname, _ in LAYER_ORDER:
        if layer.upper() == lid or layer.lower() == lname:
            return int(lid[1])
    return -1


def validate_reference_direction(
    source_layer: str,
    target_id: str,
    reference_index: Dict[str, Tuple[str, Any]]
) -> Optional[str]:
    """
    Validate that a reference points downward (to lower layer)

    Args:
        source_layer: Layer containing the reference
        target_id: ID being referenced
        reference_index: Mapping of id -> (layer, data)

    Returns:
        Error message if invalid, None if valid
    """
    if target_id not in reference_index:
        return f"Unknown reference: {target_id}"

    source_level = get_layer_level(source_layer)
    target_layer, _ = reference_index[target_id]
    target_level = get_layer_level(target_layer)

    if target_level > source_level:
        return f"Invalid upward reference: {source_layer} -> {target_layer} ({target_id})"

    return None


def validate_modular_structure(topology_path: str) -> bool:
    """
    Validate that topology structure is complete

    Supports both v3 modular and v4 layer structures.

    Args:
        topology_path: Path to main topology.yaml

    Returns:
        True if structure is valid, False otherwise
    """
    topology_file = Path(topology_path)
    topology_dir = topology_file.parent / 'topology'

    if not topology_dir.exists():
        print(f"Warning: topology/ directory not found")
        return False

    # Try v4 layer structure first
    v4_files = [f for _, _, f in LAYER_ORDER]
    v4_missing = [f for f in v4_files if not (topology_dir / f).exists()]

    if not v4_missing:
        print(f"Detected: v4 OSI-layer structure (8 layers)")
        return True

    # Try v3 modular structure
    v3_files = [
        'metadata.yaml', 'physical.yaml', 'logical.yaml', 'compute.yaml',
        'storage.yaml', 'services.yaml', 'ansible.yaml', 'workflows.yaml',
        'security.yaml', 'backup.yaml', 'monitoring.yaml', 'documentation.yaml',
    ]
    v3_missing = [f for f in v3_files if not (topology_dir / f).exists()]

    if not v3_missing:
        print(f"Detected: v3 modular structure (12 modules)")
        return True

    # Report what's missing
    if len(v4_missing) < len(v3_missing):
        print(f"Warning: Incomplete v4 structure, missing:")
        for f in v4_missing:
            print(f"  - topology/{f}")
    else:
        print(f"Warning: Incomplete v3 structure, missing:")
        for f in v3_missing:
            print(f"  - topology/{f}")

    return False


def get_topology_version(topology_path: str) -> str:
    """Get topology version without full load"""
    with open(topology_path, 'r') as f:
        for line in f:
            if line.strip().startswith('version:'):
                return line.split(':', 1)[1].strip().strip('"\'')
    return 'unknown'


def is_v4_structure(topology_path: str) -> bool:
    """Check if topology uses v4 layer structure"""
    version = get_topology_version(topology_path)
    return version.startswith('4.')


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        topology_path = sys.argv[1]
    else:
        topology_path = 'topology.yaml'

    print(f"Loading topology from: {topology_path}")
    print()

    # Validate structure
    validate_modular_structure(topology_path)
    print()

    try:
        topology = load_topology(topology_path)
        version = topology.get('version', 'unknown')
        print(f"Successfully loaded topology v{version}")
        print(f"Sections: {list(topology.keys())}")

        # Show layer info for v4
        if version.startswith('4.'):
            print("\nLayer structure:")
            for lid, lname, lfile in LAYER_ORDER:
                layer_data = load_layer(topology_path, lname)
                items = len(layer_data) if isinstance(layer_data, dict) else 0
                print(f"  {lid}: {lname:15} ({items} top-level keys)")

    except Exception as e:
        print(f"Error loading topology: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

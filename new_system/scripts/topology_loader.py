"""
Topology Loader - YAML loader with !include support
Handles loading modular topology files
"""

import yaml
from pathlib import Path
from typing import Any, Dict


class IncludeLoader(yaml.SafeLoader):
    """Custom YAML loader with !include support"""

    def __init__(self, stream):
        self._root = Path(stream.name).parent if hasattr(stream, 'name') else Path.cwd()
        super().__init__(stream)


def include_constructor(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Construct !include directive"""
    # Get the path from the node
    include_path = loader.construct_scalar(node)

    # Resolve relative to the file containing the !include
    full_path = loader._root / include_path

    if not full_path.exists():
        raise FileNotFoundError(f"Included file not found: {full_path}")

    # Load the included file
    with open(full_path, 'r') as f:
        return yaml.load(f, IncludeLoader)


# Register the !include constructor
yaml.add_constructor('!include', include_constructor, IncludeLoader)


def load_topology(topology_path: str) -> Dict[str, Any]:
    """
    Load topology YAML with !include support

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
        2.2.0
    """
    topology_file = Path(topology_path)

    if not topology_file.exists():
        raise FileNotFoundError(f"Topology file not found: {topology_path}")

    with open(topology_file, 'r') as f:
        topology = yaml.load(f, IncludeLoader)

    return topology


def validate_modular_structure(topology_path: str) -> bool:
    """
    Validate that modular structure is complete

    Args:
        topology_path: Path to main topology.yaml

    Returns:
        True if all modules exist, False otherwise
    """
    topology_dir = Path(topology_path).parent / 'topology'

    if not topology_dir.exists():
        print(f"⚠️  Warning: topology/ directory not found")
        return False

    # Expected module files
    expected_modules = [
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
    ]

    missing_modules = []
    for module in expected_modules:
        module_path = topology_dir / module
        if not module_path.exists():
            missing_modules.append(module)

    if missing_modules:
        print(f"⚠️  Warning: Missing module files:")
        for module in missing_modules:
            print(f"  - topology/{module}")
        return False

    return True


if __name__ == '__main__':
    # Test the loader
    import sys

    if len(sys.argv) > 1:
        topology_path = sys.argv[1]
    else:
        topology_path = 'topology.yaml'

    print(f"Loading topology from: {topology_path}")

    try:
        topology = load_topology(topology_path)
        print(f"✓ Successfully loaded topology v{topology.get('version', 'unknown')}")
        print(f"  - Sections: {list(topology.keys())}")
    except Exception as e:
        print(f"❌ Error loading topology: {e}")
        sys.exit(1)

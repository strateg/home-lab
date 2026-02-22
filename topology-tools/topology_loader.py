"""
Topology Loader - YAML loader with include directives.
Handles loading modular topology files.
"""

from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


class IncludeLoader(yaml.SafeLoader):
    """Custom YAML loader with include directive support."""

    def __init__(self, stream):
        self._root = Path(stream.name).parent if hasattr(stream, 'name') else Path.cwd()
        super().__init__(stream)


def _load_yaml(path: Path) -> Any:
    """Load YAML file with IncludeLoader preserving include semantics."""
    with open(path, 'r', encoding='utf-8') as file_handle:
        return yaml.load(file_handle, IncludeLoader)


def _iter_yaml_files_sorted(directory: Path) -> Iterable[Path]:
    """Yield YAML files under directory in deterministic lexicographic order."""
    files = [
        candidate
        for candidate in directory.rglob('*')
        if candidate.is_file()
        and candidate.suffix.lower() in {'.yaml', '.yml'}
        and not candidate.name.startswith('_')
    ]
    return sorted(files, key=lambda item: item.relative_to(directory).as_posix())


def include_constructor(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Construct !include directive."""
    include_path = loader.construct_scalar(node)
    full_path = loader._root / include_path

    if not full_path.exists():
        raise FileNotFoundError(f"Included file not found: {full_path}")

    return _load_yaml(full_path)


def include_dir_sorted_constructor(loader: IncludeLoader, node: yaml.Node) -> Any:
    """Construct !include_dir_sorted directive."""
    include_path = loader.construct_scalar(node)
    full_path = loader._root / include_path

    if not full_path.exists():
        raise FileNotFoundError(f"Included directory not found: {full_path}")
    if not full_path.is_dir():
        raise NotADirectoryError(f"Expected directory for !include_dir_sorted: {full_path}")

    items = []
    for yaml_file in _iter_yaml_files_sorted(full_path):
        loaded = _load_yaml(yaml_file)
        if loaded is None:
            continue
        if isinstance(loaded, list):
            items.extend(loaded)
            continue
        items.append(loaded)
    return items


# Register include constructors
yaml.add_constructor('!include', include_constructor, IncludeLoader)
yaml.add_constructor('!include_dir_sorted', include_dir_sorted_constructor, IncludeLoader)


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
        print(f"WARN  Warning: topology/ directory not found")
        return False

    # Expected module files (L0-L7)
    expected_modules = [
        'L0-meta.yaml',
        'L1-foundation.yaml',
        'L2-network.yaml',
        'L3-data.yaml',
        'L4-platform.yaml',
        'L5-application.yaml',
        'L6-observability.yaml',
        'L7-operations.yaml',
    ]

    missing_modules = []
    for module in expected_modules:
        module_path = topology_dir / module
        if not module_path.exists():
            missing_modules.append(module)

    if missing_modules:
        print(f"WARN  Warning: Missing module files:")
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
        version = topology.get('L0_meta', {}).get('version', 'unknown')
        print(f"OK Successfully loaded topology v{version}")
        print(f"  - Sections: {list(topology.keys())}")
    except Exception as e:
        print(f"ERROR Error loading topology: {e}")
        sys.exit(1)

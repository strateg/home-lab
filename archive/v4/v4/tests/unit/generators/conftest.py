"""Pytest fixtures for generator tests."""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


@pytest.fixture
def repo_root() -> Path:
    """Get repository root path."""
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def fixtures_dir() -> Path:
    """Get fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_topology_minimal(fixtures_dir: Path) -> Dict[str, Any]:
    """Load minimal sample topology for testing."""
    fixture_path = fixtures_dir / "sample_topology_minimal.yaml"
    if not fixture_path.exists():
        # Return a minimal in-memory topology if file doesn't exist
        return {
            "L0_meta": {
                "version": "4.0.0",
                "metadata": {
                    "org": "test-lab",
                    "environment": "test",
                },
            },
            "L1_foundation": {
                "locations": {},
                "devices": {},
            },
            "L2_network": {
                "networks": {},
            },
            "L3_data": {},
            "L4_platform": {},
            "L5_application": {},
            "L6_observability": {},
            "L7_operations": {},
        }

    with open(fixture_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_topology_full(fixtures_dir: Path) -> Dict[str, Any]:
    """Load full sample topology with all layers."""
    fixture_path = fixtures_dir / "sample_topology_full.yaml"
    if not fixture_path.exists():
        pytest.skip("Full topology fixture not available")

    with open(fixture_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Temporary directory for generated files."""
    output_dir = tmp_path / "generated"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture
def temp_topology_file(tmp_path: Path, sample_topology_minimal: Dict[str, Any]) -> Path:
    """Create a temporary topology file."""
    topology_file = tmp_path / "test_topology.yaml"
    with open(topology_file, "w") as f:
        yaml.dump(sample_topology_minimal, f)
    return topology_file


@pytest.fixture
def generator_config_basic(temp_topology_file: Path, temp_output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    """Default generator configuration for testing."""
    return {
        "topology_path": str(temp_topology_file),
        "output_dir": str(temp_output_dir),
        "templates_dir": str(repo_root / "topology-tools" / "templates"),
        "skip_components": [],
        "dry_run": False,
        "verbose": False,
    }


@pytest.fixture
def mock_device_spec() -> Dict[str, Any]:
    """Mock device specification."""
    return {
        "id": "test-device-01",
        "type": "server",
        "name": "test-server",
        "device_class": "compute",
        "role": "application",
        "location": "rack-01",
        "vendor": "Dell",
        "model": "PowerEdge R740",
        "management_ip": "192.168.1.100",
    }


@pytest.fixture
def mock_network_config() -> Dict[str, Any]:
    """Mock network configuration."""
    return {
        "id": "net-mgmt",
        "name": "management",
        "cidr": "192.168.1.0/24",
        "gateway": "192.168.1.1",
        "vlan_id": 10,
        "type": "management",
    }


@pytest.fixture
def mock_resource_spec() -> Dict[str, Any]:
    """Mock resource specification."""
    return {
        "cpu": 8,
        "cores": 4,
        "sockets": 2,
        "memory_mb": 16384,
        "disk_gb": 500,
    }

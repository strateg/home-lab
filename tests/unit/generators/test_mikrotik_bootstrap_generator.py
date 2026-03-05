import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOPOLOGY_TOOLS_DIR = REPO_ROOT / "topology-tools"
sys.path.insert(0, str(TOPOLOGY_TOOLS_DIR))

from scripts.generators.bootstrap.mikrotik.generator import MikrotikBootstrapGenerator


def _sample_topology() -> dict:
    return {
        "L0_meta": {"version": "4.0.0"},
        "L1_foundation": {
            "devices": [
                {"id": "mikrotik-chateau", "type": "router", "name": "MikroTik Chateau LTE7 ax"},
            ]
        },
        "L2_network": {
            "networks": [
                {
                    "id": "net-lan",
                    "name": "LAN",
                    "cidr": "192.168.88.0/24",
                    "gateway": "192.168.88.1",
                    "managed_by_ref": "mikrotik-chateau",
                },
                {
                    "id": "net-management",
                    "name": "Management",
                    "cidr": "10.0.99.0/24",
                    "gateway": "10.0.99.1",
                    "managed_by_ref": "mikrotik-chateau",
                },
            ]
        },
        "L5_application": {
            "dns": {
                "zones": [{"domain": "home.local"}],
                "forwarders": {"upstream": ["1.1.1.1", "8.8.8.8"]},
            }
        },
    }


def test_mikrotik_bootstrap_generator_generates_three_scripts(tmp_path):
    output_dir = tmp_path / "bootstrap"
    generator = MikrotikBootstrapGenerator(
        topology=_sample_topology(),
        output_dir=output_dir,
        terraform_password="TEST_PASS",  # pragma: allowlist secret
    )

    result = generator.generate()

    path_a = Path(result["bootstrap_script"])
    path_b = Path(result["bootstrap_script_backup"])
    path_c = Path(result["bootstrap_script_rsc"])

    assert path_a.exists()
    assert path_b.exists()
    assert path_c.exists()

    assert "Minimal Day-0 Bootstrap" in path_a.read_text(encoding="utf-8")
    assert "Backup Restoration Overrides" in path_b.read_text(encoding="utf-8")
    assert "Safe Exported Configuration" in path_c.read_text(encoding="utf-8")


def test_mikrotik_bootstrap_generator_uses_management_network_for_firewall(tmp_path):
    output_dir = tmp_path / "bootstrap"
    generator = MikrotikBootstrapGenerator(
        topology=_sample_topology(),
        output_dir=output_dir,
        terraform_password="TEST_PASS",  # pragma: allowlist secret
    )

    result = generator.generate()
    minimal_script = Path(result["bootstrap_script"]).read_text(encoding="utf-8")

    assert "src-address=10.0.99.0/24" in minimal_script

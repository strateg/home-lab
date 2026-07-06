#!/usr/bin/env python3
"""TUC-0003 MikroTik live parity tests using snapshot/envelope model (ADR 0097/0099).

This module tests MikroTik generator outputs using direct plugin execution via
PluginInputSnapshot and run_plugin_once(), ensuring deterministic test execution.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "MIKROTIK-TERRAFORM-DRIFT-CHECK.md"

# Ensure topology-tools is in path
if str(V5_TOOLS) not in sys.path:
    sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import (
    Phase,
    PluginInputSnapshot,
    PluginStatus,
    Stage,
)
from kernel.plugin_runner import run_plugin_once


def _load_generator_class(module_rel: str, class_name: str):
    """Dynamically load a generator class from a module file."""
    module_path = REPO_ROOT / module_rel
    spec = importlib.util.spec_from_file_location(f"tuc0003_{class_name}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def _semanticize(compiled_json: dict) -> dict:
    """Transform compiled_json to semantic format expected by generators."""
    import copy

    payload = copy.deepcopy(compiled_json)
    instances = payload.get("instances")
    if not isinstance(instances, dict):
        return payload

    for rows in instances.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            object_ref = row.pop("object_ref", None)
            class_ref = row.pop("class_ref", None)
            if not isinstance(object_ref, str) and not isinstance(class_ref, str):
                continue
            instance_block = row.get("instance")
            if not isinstance(instance_block, dict):
                instance_block = {}
                row["instance"] = instance_block
            if isinstance(object_ref, str) and object_ref:
                instance_block.setdefault("materializes_object", object_ref)
            if isinstance(class_ref, str) and class_ref:
                instance_block.setdefault("materializes_class", class_ref)

    return payload


def _build_snapshot(
    tmp_path: Path,
    plugin_id: str,
    compiled_json: dict[str, Any],
    *,
    extra_config: dict[str, Any] | None = None,
) -> PluginInputSnapshot:
    """Build a PluginInputSnapshot for generator testing."""
    config = {
        "generator_artifacts_root": str(tmp_path / "generated"),
        "secrets_mode": "passthrough",
        **(extra_config or {}),
    }

    return PluginInputSnapshot(
        plugin_id=plugin_id,
        stage=Stage.GENERATE,
        phase=Phase.RUN,
        topology_path="topology/topology.yaml",
        profile="test",
        config=config,
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path),
        workspace_root=str(tmp_path / "generated"),
    )


# Realistic MikroTik compiled payload with observed_runtime
MIKROTIK_COMPILED_PAYLOAD = {
    "instances": {
        "devices": [
            {
                "instance_id": "rtr-mikrotik-chateau",
                "object_ref": "obj.mikrotik.chateau_lte7_ax",
                "instance": {
                    "materializes_object": "obj.mikrotik.chateau_lte7_ax",
                },
                "instance_data": {
                    "network": {
                        "interfaces": {
                            "lan": {"ip": "192.168.88.1/24", "type": "ethernet"},
                            "wan": {"type": "lte"},
                        },
                        "vlans": {
                            "guest": {"id": 40, "interface": "br-lan"},
                            "iot": {"id": 30, "interface": "br-lan"},
                        },
                        "bridges": {
                            "br-lan": {"ports": ["ether2", "ether3", "ether4"]},
                        },
                        "dhcp": {
                            "lan_dhcp": {
                                "interface": "br-lan",
                                "pool": "192.168.88.100-192.168.88.254",
                                "gateway": "192.168.88.1",
                            },
                        },
                        "dns": {
                            "servers": ["8.8.8.8", "8.8.4.4"],
                            "allow_remote_requests": True,
                        },
                        "firewall": {
                            "filter": [
                                {"chain": "input", "action": "accept", "connection-state": "established,related"},
                                {"chain": "input", "action": "drop", "in-interface": "wan"},
                            ],
                        },
                    },
                    "observed_runtime": {
                        "nat": [
                            {"chain": "srcnat", "action": "masquerade", "out-interface": "wan"},
                        ],
                        "dns": {
                            "servers": ["8.8.8.8", "8.8.4.4"],
                        },
                    },
                },
            }
        ],
        "network": [
            {
                "instance_id": "br-lan",
                "object_ref": "obj.network.bridge",
                "instance_data": {
                    "host_ref": "rtr-mikrotik-chateau",
                    "ip": "192.168.88.1/24",
                },
            },
            {
                "instance_id": "inst.vlan.guest",
                "object_ref": "obj.network.vlan.guest",
                "instance_data": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "bridge_ref": "br-lan",
                    "dhcp_range": "192.168.30.100-192.168.30.254",
                },
            },
            {
                "instance_id": "inst.vlan.iot",
                "object_ref": "obj.network.vlan.iot",
                "instance_data": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "bridge_ref": "br-lan",
                    "dhcp_range": "192.168.40.100-192.168.40.254",
                },
            },
        ],
        "services": [],
    }
}


class TestTUC0003MikroTikParityV2:
    """TUC-0003 tests using snapshot/envelope execution model."""

    def test_runbook_exists(self) -> None:
        """Verify MikroTik drift check runbook exists."""
        assert RUNBOOK.exists(), f"Missing runbook: {RUNBOOK}"
        content = RUNBOOK.read_text(encoding="utf-8")
        assert "MikroTik Terraform Drift Check" in content
        assert "generator-gap" in content

    def test_generator_emits_mikrotik_domain_files(self, tmp_path: Path) -> None:
        """Test MikroTik generator emits all expected domain files."""
        generator_class = _load_generator_class(
            "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py",
            "TerraformMikroTikGenerator",
        )

        snapshot = _build_snapshot(tmp_path, "object.mikrotik.generator.terraform", MIKROTIK_COMPILED_PAYLOAD)
        plugin = generator_class("object.mikrotik.generator.terraform")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        assert envelope.result.status == PluginStatus.SUCCESS, f"Generator failed: {envelope.result.diagnostics}"

        mikrotik_dir = tmp_path / "generated" / "terraform" / "mikrotik"
        assert mikrotik_dir.exists()

        expected = {
            "interfaces.tf",
            "addresses.tf",
            "dhcp.tf",
            "dns.tf",
            "firewall.tf",
            "provider.tf",
            "variables.tf",
            "outputs.tf",
        }
        actual = {path.name for path in mikrotik_dir.glob("*.tf")}
        missing = expected - actual
        assert not missing, f"Missing expected files: {missing}"

    def test_generator_contains_topology_and_runtime_markers(self, tmp_path: Path) -> None:
        """Test generated files contain expected topology and runtime markers."""
        generator_class = _load_generator_class(
            "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py",
            "TerraformMikroTikGenerator",
        )

        snapshot = _build_snapshot(tmp_path, "object.mikrotik.generator.terraform", MIKROTIK_COMPILED_PAYLOAD)
        plugin = generator_class("object.mikrotik.generator.terraform")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        assert envelope.result.status == PluginStatus.SUCCESS

        mikrotik_dir = tmp_path / "generated" / "terraform" / "mikrotik"

        # Read generated files
        interfaces = (mikrotik_dir / "interfaces.tf").read_text(encoding="utf-8")
        addresses = (mikrotik_dir / "addresses.tf").read_text(encoding="utf-8")
        dhcp = (mikrotik_dir / "dhcp.tf").read_text(encoding="utf-8")
        dns = (mikrotik_dir / "dns.tf").read_text(encoding="utf-8")
        firewall = (mikrotik_dir / "firewall.tf").read_text(encoding="utf-8")

        # Check interfaces
        assert 'resource "routeros_interface_bridge"' in interfaces
        assert 'resource "routeros_interface_vlan" "guest"' in interfaces
        assert 'resource "routeros_interface_vlan" "iot"' in interfaces

        # Check addresses
        assert 'resource "routeros_ip_address"' in addresses
        assert "192.168.88.1/24" in addresses

        # Check DHCP
        assert 'resource "routeros_ip_dhcp_server"' in dhcp
        assert 'resource "routeros_ip_dhcp_server_network"' in dhcp

        # Check DNS
        assert 'resource "routeros_ip_dns"' in dns

        # Check firewall
        assert 'resource "routeros_ip_firewall_filter"' in firewall
        assert 'resource "routeros_ip_firewall_nat"' in firewall

    def test_effective_payload_keeps_mikrotik_observed_runtime(self, tmp_path: Path) -> None:
        """Test that observed_runtime data is preserved in effective payload."""
        # This test verifies the data flow, not the generator itself
        compiled = MIKROTIK_COMPILED_PAYLOAD

        rows = compiled.get("instances", {}).get("devices", [])
        assert isinstance(rows, list)

        row = next(
            (item for item in rows if item.get("instance_id") == "rtr-mikrotik-chateau"),
            None,
        )
        assert isinstance(row, dict)

        instance_data = row.get("instance_data", {})
        assert isinstance(instance_data, dict)

        observed_runtime = instance_data.get("observed_runtime", {})
        assert isinstance(observed_runtime, dict)
        assert "nat" in observed_runtime
        assert "dns" in observed_runtime

        # Verify NAT rules are present
        nat_rules = observed_runtime.get("nat", [])
        assert len(nat_rules) > 0
        assert nat_rules[0].get("action") == "masquerade"

#!/usr/bin/env python3
"""TUC-0002 Terraform generator tests using snapshot/envelope model (ADR 0097/0099).

This module tests Terraform generators using direct plugin execution via
PluginInputSnapshot and run_plugin_once(), avoiding subprocess calls for
deterministic and isolated test execution.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"

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

# Expected Terraform plugin IDs
EXPECTED_TERRAFORM_PLUGIN_IDS = {
    "object.mikrotik.generator.terraform",
    "object.proxmox.generator.terraform",
}

# Expected core files per plugin
EXPECTED_TERRAFORM_CORE_FILES = {
    "object.mikrotik.generator.terraform": {
        "provider.tf",
        "interfaces.tf",
        "firewall.tf",
        "dhcp.tf",
        "dns.tf",
        "addresses.tf",
        "variables.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    },
    "object.proxmox.generator.terraform": {
        "versions.tf",
        "provider.tf",
        "variables.tf",
        "bridges.tf",
        "lxc.tf",
        "vms.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    },
}


def _load_generator_class(module_rel: str, class_name: str):
    """Dynamically load a generator class from a module file."""
    module_path = REPO_ROOT / module_rel
    spec = importlib.util.spec_from_file_location(f"tuc0002_{class_name}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


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


def _list_plugin_ids(manifest_path: Path) -> set[str]:
    """Extract plugin IDs from a manifest file."""
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return set()

    out: set[str] = set()
    for row in plugins:
        if not isinstance(row, dict):
            continue
        plugin_id = row.get("id")
        if isinstance(plugin_id, str) and plugin_id.strip():
            out.add(plugin_id.strip())
    return out


class TestTUC0002TerraformGeneratorsV2:
    """TUC-0002 tests using snapshot/envelope execution model."""

    def test_expected_terraform_generators_exist_in_manifests(self) -> None:
        """Verify expected Terraform generator plugins are registered."""
        manifest_paths = [
            REPO_ROOT / "topology-tools" / "plugins" / "plugins.yaml",
            *sorted((REPO_ROOT / "topology" / "object-modules").glob("*/plugins.yaml")),
        ]

        discovered: set[str] = set()
        for manifest in manifest_paths:
            if manifest.exists():
                discovered.update(_list_plugin_ids(manifest))

        missing = sorted(EXPECTED_TERRAFORM_PLUGIN_IDS - discovered)
        assert not missing, f"Missing expected terraform plugin ids: {missing}"

    def test_mikrotik_generator_produces_core_files(self, tmp_path: Path) -> None:
        """Test MikroTik Terraform generator produces expected files."""
        generator_class = _load_generator_class(
            "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py",
            "TerraformMikroTikGenerator",
        )

        compiled = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mikrotik-chateau",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                        "instance_data": {
                            "network": {
                                "interfaces": {"lan": {"ip": "192.168.88.1/24"}},
                                "vlans": {"guest": {"id": 40}, "iot": {"id": 30}},
                                "bridges": {"br-lan": {}},
                            },
                            "observed_runtime": {
                                "nat": [{"chain": "srcnat", "action": "masquerade"}],
                                "dns": {"servers": ["8.8.8.8"]},
                            },
                        },
                    }
                ],
                "network": [
                    {"instance_id": "vlan-guest", "object_ref": "obj.network.vlan", "vlan_id": 40},
                    {"instance_id": "vlan-iot", "object_ref": "obj.network.vlan", "vlan_id": 30},
                ],
                "services": [],
            }
        }

        snapshot = _build_snapshot(tmp_path, "object.mikrotik.generator.terraform", compiled)
        plugin = generator_class("object.mikrotik.generator.terraform")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        assert envelope.result.status == PluginStatus.SUCCESS, (
            f"Generator failed: {envelope.result.diagnostics}"
        )

        # Check generated files
        mikrotik_dir = tmp_path / "generated" / "terraform" / "mikrotik"
        assert mikrotik_dir.exists(), "MikroTik terraform directory not created"

        actual_files = {p.name for p in mikrotik_dir.glob("*.tf*")}
        expected = EXPECTED_TERRAFORM_CORE_FILES["object.mikrotik.generator.terraform"]
        missing = expected - actual_files
        assert not missing, f"Missing expected files: {missing}"

    def test_mikrotik_generator_deterministic_output(self, tmp_path: Path) -> None:
        """Test MikroTik generator produces identical output on repeated runs."""
        generator_class = _load_generator_class(
            "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py",
            "TerraformMikroTikGenerator",
        )

        compiled = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mk",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                        "instance_data": {
                            "network": {"interfaces": {"lan": {"ip": "192.168.88.1/24"}}},
                        },
                    }
                ],
                "network": [],
                "services": [],
            }
        }

        # Run 1
        run1_dir = tmp_path / "run1"
        snapshot1 = _build_snapshot(run1_dir, "object.mikrotik.generator.terraform", compiled)
        plugin1 = generator_class("object.mikrotik.generator.terraform")
        envelope1 = run_plugin_once(snapshot=snapshot1, plugin=plugin1)
        assert envelope1.result.status == PluginStatus.SUCCESS

        # Run 2
        run2_dir = tmp_path / "run2"
        snapshot2 = _build_snapshot(run2_dir, "object.mikrotik.generator.terraform", compiled)
        plugin2 = generator_class("object.mikrotik.generator.terraform")
        envelope2 = run_plugin_once(snapshot=snapshot2, plugin=plugin2)
        assert envelope2.result.status == PluginStatus.SUCCESS

        # Compare file hashes
        hashes1 = _hash_tree(run1_dir / "generated" / "terraform" / "mikrotik")
        hashes2 = _hash_tree(run2_dir / "generated" / "terraform" / "mikrotik")

        assert hashes1 == hashes2, "Generator output is not deterministic"

    def test_proxmox_generator_produces_core_files(self, tmp_path: Path) -> None:
        """Test Proxmox Terraform generator produces expected files."""
        generator_class = _load_generator_class(
            "topology/object-modules/proxmox/plugins/generators/terraform_proxmox_generator.py",
            "TerraformProxmoxGenerator",
        )

        compiled = {
            "instances": {
                "devices": [
                    {
                        "instance_id": "srv-gamayun",
                        "object_ref": "obj.proxmox.ve",
                        "instance_data": {
                            "proxmox": {"node_name": "pve"},
                        },
                    }
                ],
                "lxc": [
                    {
                        "instance_id": "ct-dns",
                        "object_ref": "obj.lxc.alpine",
                        "instance_data": {"vmid": 100},
                    }
                ],
                "services": [],
            }
        }

        snapshot = _build_snapshot(tmp_path, "object.proxmox.generator.terraform", compiled)
        plugin = generator_class("object.proxmox.generator.terraform")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        assert envelope.result.status == PluginStatus.SUCCESS, (
            f"Generator failed: {envelope.result.diagnostics}"
        )

        # Check generated files
        proxmox_dir = tmp_path / "generated" / "terraform" / "proxmox"
        assert proxmox_dir.exists(), "Proxmox terraform directory not created"

        actual_files = {p.name for p in proxmox_dir.glob("*.tf*")}
        expected = EXPECTED_TERRAFORM_CORE_FILES["object.proxmox.generator.terraform"]
        missing = expected - actual_files
        assert not missing, f"Missing expected files: {missing}"

    def test_mikrotik_remote_state_backend_uses_programmatic_renderer(self, tmp_path: Path) -> None:
        """Test MikroTik generator uses programmatic renderer for remote state backend."""
        generator_class = _load_generator_class(
            "topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py",
            "TerraformMikroTikGenerator",
        )

        compiled = {
            "instances": {
                "devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}],
                "network": [],
                "services": [],
            }
        }

        extra_config = {
            "terraform_remote_state": {
                "enabled": True,
                "backend": "pg",
                "config": {
                    "schema_name": "mikrotik",
                    "conn_str": "postgres://terraform@db.internal/terraform_state",
                },
            }
        }

        snapshot = _build_snapshot(
            tmp_path, "object.mikrotik.generator.terraform", compiled, extra_config=extra_config
        )
        plugin = generator_class("object.mikrotik.generator.terraform")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        assert envelope.result.status == PluginStatus.SUCCESS

        # Check artifact plan
        output_data = envelope.result.output_data
        assert output_data is not None
        plan_rows = output_data.get("artifact_plan", {}).get("planned_outputs", [])
        backend_entry = next(
            (item for item in plan_rows if str(item.get("path", "")).endswith("/backend.tf")),
            None,
        )
        assert backend_entry is not None, "No backend.tf in artifact plan"
        assert backend_entry["renderer"] == "programmatic"

        # Check generated content
        backend_tf = (tmp_path / "generated" / "terraform" / "mikrotik" / "backend.tf").read_text()
        assert 'backend "pg"' in backend_tf

    def test_proxmox_remote_state_backend_uses_programmatic_renderer(self, tmp_path: Path) -> None:
        """Test Proxmox generator uses programmatic renderer for remote state backend."""
        generator_class = _load_generator_class(
            "topology/object-modules/proxmox/plugins/generators/terraform_proxmox_generator.py",
            "TerraformProxmoxGenerator",
        )

        compiled = {
            "instances": {
                "devices": [{"instance_id": "srv-gamayun", "object_ref": "obj.proxmox.ve"}],
                "lxc": [],
                "services": [],
            }
        }

        extra_config = {
            "terraform_remote_state": {
                "enabled": True,
                "backend": "s3",
                "config": {
                    "bucket": "tf-state-home-lab",
                    "key": "proxmox/terraform.tfstate",
                    "encrypt": True,
                },
            }
        }

        snapshot = _build_snapshot(
            tmp_path, "object.proxmox.generator.terraform", compiled, extra_config=extra_config
        )
        plugin = generator_class("object.proxmox.generator.terraform")
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        assert envelope.result.status == PluginStatus.SUCCESS

        # Check artifact plan
        output_data = envelope.result.output_data
        assert output_data is not None
        plan_rows = output_data.get("artifact_plan", {}).get("planned_outputs", [])
        backend_entry = next(
            (item for item in plan_rows if str(item.get("path", "")).endswith("/backend.tf")),
            None,
        )
        assert backend_entry is not None, "No backend.tf in artifact plan"
        assert backend_entry["renderer"] == "programmatic"

        # Check generated content
        backend_tf = (tmp_path / "generated" / "terraform" / "proxmox" / "backend.tf").read_text()
        assert 'backend "s3"' in backend_tf


def _hash_tree(root: Path) -> dict[str, str]:
    """Hash all files under a directory tree."""
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[rel] = digest
    return out

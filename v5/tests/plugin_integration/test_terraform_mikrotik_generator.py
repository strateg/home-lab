#!/usr/bin/env python3
"""Integration checks for Terraform MikroTik generator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.generators.terraform_mikrotik_generator import TerraformMikroTikGenerator


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )


def _compiled_fixture() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-mk",
                    "object_ref": "obj.mikrotik.chateau_lte7_ax",
                    "capabilities": [
                        "cap.net.overlay.vpn.wireguard.server",
                        "cap.net.l3.qos.basic",
                    ],
                },
                {"instance_id": "srv-gamayun", "object_ref": "obj.proxmox.ve"},
            ],
            "network": [
                {"instance_id": "inst.net.wan", "object_ref": "obj.network.l2_segment"},
                {"instance_id": "inst.net.lan", "object_ref": "obj.network.l2_segment"},
            ],
            "services": [
                {"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}},
                {"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}},
            ],
        }
    }


def test_terraform_mikrotik_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("base.generator.terraform_mikrotik")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "terraform" / "mikrotik"
    expected_files = {
        "provider.tf",
        "interfaces.tf",
        "firewall.tf",
        "dhcp.tf",
        "dns.tf",
        "addresses.tf",
        "qos.tf",
        "vpn.tf",
        "containers.tf",
        "variables.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    }
    assert expected_files.issubset({path.name for path in target_dir.iterdir()})

    firewall_tf = (target_dir / "firewall.tf").read_text(encoding="utf-8")
    assert "inst.net.lan" in firewall_tf
    assert "inst.net.wan" in firewall_tf
    assert firewall_tf.index("inst.net.lan") < firewall_tf.index("inst.net.wan")


def test_terraform_mikrotik_generator_reports_projection_error(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("base.generator.terraform_mikrotik")
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9201" for diag in result.diagnostics)


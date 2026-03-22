#!/usr/bin/env python3
"""Integration checks for Terraform MikroTik generator plugin."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage


def _load_generator_class():
    module_path = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "terraform_mikrotik_generator.py"
    spec = importlib.util.spec_from_file_location("test_object_mikrotik_terraform_generator", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformMikroTikGenerator


TerraformMikroTikGenerator = _load_generator_class()


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    capability_templates = [
        {"capability_key": "has_qos", "template": "terraform/qos.tf.j2", "output_file": "qos.tf"},
        {"capability_key": "has_wireguard", "template": "terraform/vpn.tf.j2", "output_file": "vpn.tf"},
        {"capability_key": "has_containers", "template": "terraform/containers.tf.j2", "output_file": "containers.tf"},
    ]
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "capability_templates": capability_templates,
        },
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


def test_terraform_mikrotik_generator_derives_host_from_projection(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("base.generator.terraform_mikrotik")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    tfvars = (tmp_path / "generated" / "terraform" / "mikrotik" / "terraform.tfvars.example").read_text(
        encoding="utf-8"
    )
    assert 'mikrotik_host = "https://rtr-mk:8443"' in tfvars


def test_terraform_mikrotik_generator_prefers_configured_host(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("base.generator.terraform_mikrotik")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["mikrotik_api_host"] = "https://router-api.example.invalid:9443"

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    tfvars = (tmp_path / "generated" / "terraform" / "mikrotik" / "terraform.tfvars.example").read_text(
        encoding="utf-8"
    )
    assert 'mikrotik_host = "https://router-api.example.invalid:9443"' in tfvars


def test_terraform_mikrotik_generator_respects_capability_template_config(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("base.generator.terraform_mikrotik")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["capability_templates"] = [
        {"capability_key": "has_wireguard", "template": "terraform/vpn.tf.j2", "output_file": "vpn.tf"}
    ]

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "terraform" / "mikrotik"
    generated = {path.name for path in target_dir.iterdir()}
    assert "vpn.tf" in generated
    assert "qos.tf" not in generated
    assert "containers.tf" not in generated


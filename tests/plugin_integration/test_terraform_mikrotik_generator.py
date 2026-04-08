#!/usr/bin/env python3
"""Integration checks for Terraform MikroTik generator plugin."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage


def _load_generator_class():
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "generators"
        / "terraform_mikrotik_generator.py"
    )
    spec = importlib.util.spec_from_file_location("test_object_mikrotik_terraform_generator", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformMikroTikGenerator


TerraformMikroTikGenerator = _load_generator_class()


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    capability_templates = {
        "qos": {"enabled_by": "capabilities.has_qos", "template": "terraform/qos.tf.j2", "output": "qos.tf"},
        "wireguard": {
            "enabled_by": "capabilities.has_wireguard",
            "template": "terraform/vpn.tf.j2",
            "output": "vpn.tf",
        },
        "containers": {
            "enabled_by": "capabilities.has_containers",
            "template": "terraform/containers.tf.j2",
            "output": "containers.tf",
        },
    }
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path / "build"),
        config={
            "generator_artifacts_root": str(tmp_path / "generated"),
            "capability_templates": capability_templates,
        },
    )


def _compiled_fixture() -> dict:
    return _semanticize(
        {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mk",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                        "capabilities": [
                            "cap.net.overlay.vpn.wireguard.server",
                            "cap.net.l3.qos.basic",
                            "cap.net.platform.containers",
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
    )


def _semanticize(compiled_json: dict) -> dict:
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


def test_terraform_mikrotik_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
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
    assert not (target_dir / "backend.tf").exists()
    assert result.output_data is not None
    assert result.output_data["artifact_plan"]["artifact_family"] == "terraform.mikrotik"
    assert result.output_data["terraform_ir"]["artifact_family"] == "terraform.mikrotik"
    assert result.output_data["terraform_ir"]["ir_version"] == "1.0"
    assert result.output_data["artifact_generation_report"]["summary"]["generated_count"] == len(
        result.output_data["terraform_mikrotik_files"]
    )
    for contract_file in result.output_data["artifact_contract_files"]:
        assert Path(contract_file).exists()

    firewall_tf = (target_dir / "firewall.tf").read_text(encoding="utf-8")
    assert "inst.net.lan" in firewall_tf
    assert "inst.net.wan" in firewall_tf
    assert firewall_tf.index("inst.net.lan") < firewall_tf.index("inst.net.wan")


def test_terraform_mikrotik_generator_reports_projection_error(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9201" for diag in result.diagnostics)


def test_terraform_mikrotik_generator_derives_host_from_projection(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    tfvars = (tmp_path / "generated" / "terraform" / "mikrotik" / "terraform.tfvars.example").read_text(
        encoding="utf-8"
    )
    assert 'mikrotik_host = "https://rtr-mk:8443"' in tfvars


def test_terraform_mikrotik_generator_prefers_configured_host(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["mikrotik_api_host"] = "https://router-api.example.invalid:9443"

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    tfvars = (tmp_path / "generated" / "terraform" / "mikrotik" / "terraform.tfvars.example").read_text(
        encoding="utf-8"
    )
    assert 'mikrotik_host = "https://router-api.example.invalid:9443"' in tfvars


def test_terraform_mikrotik_generator_respects_capability_template_config(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["capability_templates"] = {
        "wireguard": {
            "enabled_by": "capabilities.has_wireguard",
            "template": "terraform/vpn.tf.j2",
            "output": "vpn.tf",
        }
    }

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "terraform" / "mikrotik"
    generated = {path.name for path in target_dir.iterdir()}
    assert "vpn.tf" in generated
    assert "qos.tf" not in generated
    assert "containers.tf" not in generated


def test_terraform_mikrotik_generator_keeps_legacy_capability_template_compatibility(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["capability_templates"] = [
        {"capability_key": "has_wireguard", "template": "terraform/vpn.tf.j2", "output_file": "vpn.tf"}
    ]

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "terraform" / "mikrotik"
    generated = {path.name for path in target_dir.iterdir()}
    assert "vpn.tf" in generated


def test_terraform_mikrotik_generator_emits_backend_tf_when_remote_state_enabled(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["terraform_remote_state"] = {
        "enabled": True,
        "backend": "pg",
        "config": {
            "conn_str": "postgres://terraform@db.internal/terraform_state",
            "schema_name": "mikrotik",
        },
    }

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    backend_tf = (tmp_path / "generated" / "terraform" / "mikrotik" / "backend.tf").read_text(encoding="utf-8")
    assert 'backend "pg"' in backend_tf
    assert 'schema_name = "mikrotik"' in backend_tf
    assert 'conn_str = "postgres://terraform@db.internal/terraform_state"' in backend_tf
    plan_outputs = result.output_data["artifact_plan"]["planned_outputs"]
    backend_entry = next(item for item in plan_outputs if str(item.get("path", "")).endswith("/backend.tf"))
    assert backend_entry["renderer"] == "programmatic"


def _full_topology_fixture() -> dict:
    return _semanticize(
        {
            "instances": {
                "devices": [
                    {
                        "instance_id": "rtr-mikrotik-chateau",
                        "object_ref": "obj.mikrotik.chateau_lte7_ax",
                        "instance_data": {
                            "observed_runtime": {
                                "lan": {
                                    "gateway_ref": "inst.vlan.lan",
                                    "dhcp_pool": "192.168.88.10-192.168.88.254",
                                    "dhcp_server": "defconf",
                                    "dhcp_lease_time": "30m",
                                    "bridge_interface": "bridge",
                                },
                                "dns": {"servers": ["1.1.1.1", "8.8.8.8"]},
                                "nat": [
                                    {"chain": "srcnat", "action": "masquerade", "out_interface": "ether1"},
                                    {
                                        "chain": "dstnat",
                                        "action": "dst-nat",
                                        "protocol": "tcp",
                                        "dst_port": 8080,
                                        "to_addresses": "172.18.0.2",
                                        "to_ports": 80,
                                    },
                                ],
                            }
                        },
                    }
                ],
                "network": [
                    {
                        "instance_id": "inst.bridge.containers",
                        "object_ref": "obj.network.bridge.containers",
                        "instance_data": {
                            "host_ref": "rtr-mikrotik-chateau",
                            "ip": "172.18.0.1/24",
                            "cidr": "172.18.0.0/24",
                        },
                    },
                    {
                        "instance_id": "inst.vlan.lan",
                        "object_ref": "obj.network.vlan.lan",
                        "instance_data": {
                            "trust_zone_ref": "inst.trust_zone.user",
                            "dhcp_range": "192.168.88.10-192.168.88.254",
                            "ip_allocations": [
                                {"device_ref": "rtr-mikrotik-chateau", "ip": "192.168.88.1/24"},
                            ],
                        },
                    },
                    {
                        "instance_id": "inst.vlan.guest",
                        "object_ref": "obj.network.vlan.guest",
                        "instance_data": {
                            "trust_zone_ref": "inst.trust_zone.guest",
                            "dhcp_range": "192.168.30.100-192.168.30.200",
                        },
                    },
                    {
                        "instance_id": "inst.vlan.iot",
                        "object_ref": "obj.network.vlan.iot",
                        "instance_data": {
                            "trust_zone_ref": "inst.trust_zone.iot",
                            "dhcp_range": "192.168.40.100-192.168.40.200",
                        },
                    },
                    {
                        "instance_id": "inst.vlan.management",
                        "object_ref": "obj.network.vlan.management",
                        "instance_data": {"trust_zone_ref": "inst.trust_zone.management"},
                    },
                    {
                        "instance_id": "inst.vlan.servers",
                        "object_ref": "obj.network.vlan.servers",
                        "instance_data": {"trust_zone_ref": "inst.trust_zone.servers"},
                    },
                ],
                "firewall": [
                    {
                        "instance_id": "inst.fw.established_related",
                        "object_ref": "obj.network.firewall_policy.established_related",
                        "instance_data": {"chain": "forward", "managed_by_ref": "rtr-mikrotik-chateau"},
                    },
                    {
                        "instance_id": "inst.fw.default_deny",
                        "object_ref": "obj.network.firewall_policy.default_deny",
                        "instance_data": {"chain": "forward", "managed_by_ref": "rtr-mikrotik-chateau"},
                    },
                    {
                        "instance_id": "inst.fw.guest_isolated",
                        "object_ref": "obj.network.firewall_policy.guest_isolated",
                        "instance_data": {},
                    },
                    {
                        "instance_id": "inst.fw.iot_isolated",
                        "object_ref": "obj.network.firewall_policy.iot_isolated",
                        "instance_data": {},
                    },
                ],
                "services": [],
            }
        }
    )


def test_terraform_mikrotik_generator_reflects_full_network_topology(tmp_path: Path) -> None:
    generator = TerraformMikroTikGenerator("object.mikrotik.generator.terraform")
    ctx = _ctx(tmp_path, _full_topology_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "terraform" / "mikrotik"

    interfaces_tf = (target_dir / "interfaces.tf").read_text(encoding="utf-8")
    assert 'resource "routeros_interface_bridge" "containers"' in interfaces_tf
    assert 'resource "routeros_interface_vlan" "guest"' in interfaces_tf
    assert 'resource "routeros_interface_vlan" "iot"' in interfaces_tf
    assert 'resource "routeros_interface_vlan" "management"' in interfaces_tf
    assert 'resource "routeros_interface_vlan" "servers"' in interfaces_tf
    assert 'resource "routeros_interface_vlan" "lan"' not in interfaces_tf

    addresses_tf = (target_dir / "addresses.tf").read_text(encoding="utf-8")
    assert 'address   = "172.18.0.1/24"' in addresses_tf
    assert 'address   = "192.168.88.1/24"' in addresses_tf
    assert 'address   = "192.168.30.1/24"' in addresses_tf

    dhcp_tf = (target_dir / "dhcp.tf").read_text(encoding="utf-8")
    assert 'resource "routeros_ip_dhcp_server" "lan_dhcp"' in dhcp_tf
    assert 'resource "routeros_ip_dhcp_server_network" "lan_network"' in dhcp_tf
    assert 'resource "routeros_ip_dhcp_server" "guest_dhcp"' in dhcp_tf
    assert 'resource "routeros_ip_dhcp_server" "iot_dhcp"' in dhcp_tf

    firewall_tf = (target_dir / "firewall.tf").read_text(encoding="utf-8")
    assert 'resource "routeros_ip_firewall_nat" "runtime_nat_1"' in firewall_tf
    assert 'resource "routeros_ip_firewall_nat" "runtime_nat_2"' in firewall_tf
    assert 'src_address = "192.168.30.0/24"' in firewall_tf
    assert 'dst_address = "10.0.30.0/24"' in firewall_tf

#!/usr/bin/env python3
"""Integration checks for Terraform Proxmox generator plugin."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.generators.shared_helper_loader import load_capability_helpers

get_capability_templates = load_capability_helpers().get_capability_templates


def _load_generator_class():
    module_path = (
        V5_ROOT
        / "topology"
        / "object-modules"
        / "proxmox"
        / "plugins"
        / "generators"
        / "terraform_proxmox_generator.py"
    )
    spec = importlib.util.spec_from_file_location("test_object_proxmox_terraform_generator", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformProxmoxGenerator


TerraformProxmoxGenerator = _load_generator_class()


def _load_projection_module():
    module_path = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "projections.py"
    spec = importlib.util.spec_from_file_location("test_object_proxmox_projection_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_proxmox_projection = _load_projection_module().build_proxmox_projection


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
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
                {"instance_id": "srv-gamayun", "object_ref": "obj.proxmox.ve"},
                {"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"},
            ],
            "lxc": [
                {"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"},
                {"instance_id": "lxc-grafana", "object_ref": "obj.proxmox.lxc.debian12.base"},
            ],
            "services": [
                {"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}},
                {"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}},
            ],
        }
    }


def test_terraform_proxmox_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = TerraformProxmoxGenerator("object.proxmox.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    target_dir = tmp_path / "generated" / "terraform" / "proxmox"
    expected_files = {
        "versions.tf",
        "provider.tf",
        "variables.tf",
        "bridges.tf",
        "lxc.tf",
        "vms.tf",
        "outputs.tf",
        "terraform.tfvars.example",
    }
    assert expected_files.issubset({path.name for path in target_dir.iterdir()})
    assert not (target_dir / "backend.tf").exists()

    lxc_tf = (target_dir / "lxc.tf").read_text(encoding="utf-8")
    assert "lxc-grafana" in lxc_tf
    assert "lxc-redis" in lxc_tf
    assert lxc_tf.index("lxc-grafana") < lxc_tf.index("lxc-redis")


def test_terraform_proxmox_generator_reports_projection_error(tmp_path: Path) -> None:
    generator = TerraformProxmoxGenerator("object.proxmox.generator.terraform")
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9101" for diag in result.diagnostics)


def test_terraform_proxmox_generator_derives_api_url_from_projection(tmp_path: Path) -> None:
    generator = TerraformProxmoxGenerator("object.proxmox.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    tfvars = (tmp_path / "generated" / "terraform" / "proxmox" / "terraform.tfvars.example").read_text(encoding="utf-8")
    assert 'proxmox_api_url = "https://srv-gamayun:8006/api2/json"' in tfvars


def test_terraform_proxmox_generator_prefers_configured_api_url(tmp_path: Path) -> None:
    generator = TerraformProxmoxGenerator("object.proxmox.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["proxmox_api_url"] = "https://pve-api.example.invalid:8443/api2/json"

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    tfvars = (tmp_path / "generated" / "terraform" / "proxmox" / "terraform.tfvars.example").read_text(encoding="utf-8")
    assert 'proxmox_api_url = "https://pve-api.example.invalid:8443/api2/json"' in tfvars


def test_terraform_proxmox_generator_resolves_declarative_capability_template_config(tmp_path: Path) -> None:
    config = {
        "capability_templates": {
            "ceph": {
                "enabled_by": "capabilities.has_ceph",
                "template": "terraform/ceph.tf.j2",
                "output": "ceph.tf",
            },
            "ha": {
                "enabled_by": "capabilities.has_ha",
                "template": "terraform/ha.tf.j2",
                "output": "ha.tf",
            },
        }
    }

    templates = get_capability_templates({"has_ceph": True, "has_ha": False}, config)

    assert templates == {"ceph.tf": "terraform/ceph.tf.j2"}


def test_terraform_proxmox_generator_keeps_legacy_capability_template_compatibility(tmp_path: Path) -> None:
    config = {
        "capability_templates": [
            {"capability_key": "has_ceph", "template": "terraform/ceph.tf.j2", "output_file": "ceph.tf"},
            {"capability_key": "has_ha", "template": "terraform/ha.tf.j2", "output_file": "ha.tf"},
        ]
    }

    templates = get_capability_templates({"has_ceph": False, "has_ha": True}, config)

    assert templates == {"ha.tf": "terraform/ha.tf.j2"}


def test_proxmox_projection_derives_capability_flags_from_rows() -> None:
    projection = build_proxmox_projection(
        {
            "instances": {
                "devices": [
                    {
                        "instance_id": "srv-pve-a",
                        "object_ref": "obj.proxmox.ve",
                        "capabilities": ["cap.storage.pool.ceph", "cap.cluster.ha"],
                    },
                    {
                        "instance_id": "srv-pve-b",
                        "object_ref": "obj.proxmox.ve",
                    },
                ],
                "lxc": [
                    {
                        "instance_id": "lxc-app",
                        "object_ref": "obj.proxmox.lxc.debian12.base",
                        "derived_capabilities": ["cap.vm.cloud_init"],
                    }
                ],
                "services": [],
            }
        }
    )

    assert projection["capabilities"]["has_ceph"] is True
    assert projection["capabilities"]["has_ha"] is True
    assert projection["capabilities"]["has_cloud_init"] is True


def test_terraform_proxmox_generator_emits_backend_tf_when_remote_state_enabled(tmp_path: Path) -> None:
    generator = TerraformProxmoxGenerator("object.proxmox.generator.terraform")
    ctx = _ctx(tmp_path, _compiled_fixture())
    ctx.config["terraform_remote_state"] = {
        "enabled": True,
        "backend": "s3",
        "config": {
            "bucket": "tf-state-home-lab",
            "region": "eu-central-1",
            "key": "proxmox/terraform.tfstate",
            "encrypt": True,
        },
    }

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    backend_tf = (tmp_path / "generated" / "terraform" / "proxmox" / "backend.tf").read_text(encoding="utf-8")
    assert 'backend "s3"' in backend_tf
    assert 'bucket = "tf-state-home-lab"' in backend_tf
    assert 'key = "proxmox/terraform.tfstate"' in backend_tf
    assert "encrypt = true" in backend_tf

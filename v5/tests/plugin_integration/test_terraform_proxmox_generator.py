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


def _load_generator_class():
    module_path = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "terraform_proxmox_generator.py"
    spec = importlib.util.spec_from_file_location("test_object_proxmox_terraform_generator", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TerraformProxmoxGenerator


TerraformProxmoxGenerator = _load_generator_class()


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
    generator = TerraformProxmoxGenerator("base.generator.terraform_proxmox")
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

    lxc_tf = (target_dir / "lxc.tf").read_text(encoding="utf-8")
    assert "lxc-grafana" in lxc_tf
    assert "lxc-redis" in lxc_tf
    assert lxc_tf.index("lxc-grafana") < lxc_tf.index("lxc-redis")


def test_terraform_proxmox_generator_reports_projection_error(tmp_path: Path) -> None:
    generator = TerraformProxmoxGenerator("base.generator.terraform_proxmox")
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9101" for diag in result.diagnostics)

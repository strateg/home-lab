#!/usr/bin/env python3
"""Integration checks for bootstrap generator plugins."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage
from plugins.generators.bootstrap_mikrotik_generator import BootstrapMikroTikGenerator
from plugins.generators.bootstrap_orangepi_generator import BootstrapOrangePiGenerator
from plugins.generators.bootstrap_proxmox_generator import BootstrapProxmoxGenerator


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
                {"instance_id": "srv-orangepi5", "object_ref": "obj.orangepi.rk3588.debian"},
            ]
        }
    }


def test_bootstrap_proxmox_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox")
    result = generator.execute(_ctx(tmp_path, _compiled_fixture()), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "srv-gamayun"
    assert (root / "answer.toml.example").exists()
    assert (root / "README.md").exists()
    assert (root / "post-install" / "01-install-terraform.sh").exists()
    assert (root / "post-install" / "06-enable-zswap.sh").exists()


def test_bootstrap_mikrotik_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = BootstrapMikroTikGenerator("base.generator.bootstrap_mikrotik")
    result = generator.execute(_ctx(tmp_path, _compiled_fixture()), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "rtr-mk"
    assert (root / "init-terraform.rsc").exists()
    assert (root / "backup-restore-overrides.rsc").exists()
    assert (root / "terraform.tfvars.example").exists()


def test_bootstrap_orangepi_generator_writes_expected_files(tmp_path: Path) -> None:
    generator = BootstrapOrangePiGenerator("base.generator.bootstrap_orangepi")
    result = generator.execute(_ctx(tmp_path, _compiled_fixture()), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "srv-orangepi5" / "cloud-init"
    assert (root / "user-data.example").exists()
    assert (root / "meta-data").exists()
    assert (root / "README.md").exists()


def test_bootstrap_generators_report_projection_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})
    generators = [
        (BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox"), "E9401"),
        (BootstrapMikroTikGenerator("base.generator.bootstrap_mikrotik"), "E9501"),
        (BootstrapOrangePiGenerator("base.generator.bootstrap_orangepi"), "E9601"),
    ]
    for generator, code in generators:
        result = generator.execute(ctx, Stage.GENERATE)
        assert result.status == PluginStatus.FAILED
        assert any(diag.code == code for diag in result.diagnostics)


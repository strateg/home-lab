#!/usr/bin/env python3
"""Contract checks: template-only rendering and generator publish metadata."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage  # noqa: E402
from plugins.generators.ansible_inventory_generator import AnsibleInventoryGenerator  # noqa: E402
from plugins.generators.bootstrap_mikrotik_generator import BootstrapMikroTikGenerator  # noqa: E402
from plugins.generators.bootstrap_orangepi_generator import BootstrapOrangePiGenerator  # noqa: E402
from plugins.generators.bootstrap_proxmox_generator import BootstrapProxmoxGenerator  # noqa: E402
from plugins.generators.terraform_mikrotik_generator import TerraformMikroTikGenerator  # noqa: E402
from plugins.generators.terraform_proxmox_generator import TerraformProxmoxGenerator  # noqa: E402


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )


@pytest.mark.parametrize(
    ("generator", "compiled_json", "expected_writes"),
    [
        (
            TerraformProxmoxGenerator("base.generator.terraform_proxmox"),
            {
                "instances": {
                    "l1_devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "l4_lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                    "l5_services": [{"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}}],
                }
            },
            8,
        ),
        (
            TerraformMikroTikGenerator("base.generator.terraform_mikrotik"),
            {
                "instances": {
                    "l1_devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}],
                    "l2_network": [{"instance_id": "inst.net.lan", "object_ref": "obj.network.l2_segment"}],
                    "l5_services": [{"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}}],
                }
            },
            12,
        ),
        (
            AnsibleInventoryGenerator("base.generator.ansible_inventory"),
            {
                "instances": {
                    "l1_devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "l4_lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                }
            },
            4,
        ),
        (
            BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox"),
            {"instances": {"l1_devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}]}},
            9,
        ),
        (
            BootstrapMikroTikGenerator("base.generator.bootstrap_mikrotik"),
            {"instances": {"l1_devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}]}},
            4,
        ),
        (
            BootstrapOrangePiGenerator("base.generator.bootstrap_orangepi"),
            {"instances": {"l1_devices": [{"instance_id": "srv-opi", "object_ref": "obj.orangepi.rk3588.debian"}]}},
            3,
        ),
    ],
)
def test_generator_outputs_are_template_rendered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    generator,
    compiled_json: dict,
    expected_writes: int,
) -> None:
    writes: list[tuple[Path, str]] = []
    renders: list[str] = []

    def _render_template(ctx, template_name: str, context: dict) -> str:
        renders.append(template_name)
        return f"TEMPLATE::{template_name}"

    def _write_text_atomic(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        _ = encoding
        writes.append((path, content))

    monkeypatch.setattr(generator, "render_template", _render_template)
    monkeypatch.setattr(generator, "write_text_atomic", _write_text_atomic)

    result = generator.execute(_ctx(tmp_path, compiled_json), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    assert len(writes) == expected_writes
    assert len(renders) == expected_writes
    assert all(content.startswith("TEMPLATE::") for _, content in writes)


@pytest.mark.parametrize(
    ("generator", "compiled_json", "published_key"),
    [
        (
            TerraformProxmoxGenerator("base.generator.terraform_proxmox"),
            {
                "instances": {
                    "l1_devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "l4_lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                    "l5_services": [{"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}}],
                }
            },
            "terraform_proxmox_files",
        ),
        (
            TerraformMikroTikGenerator("base.generator.terraform_mikrotik"),
            {
                "instances": {
                    "l1_devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}],
                    "l2_network": [{"instance_id": "inst.net.lan", "object_ref": "obj.network.l2_segment"}],
                    "l5_services": [{"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}}],
                }
            },
            "terraform_mikrotik_files",
        ),
        (
            AnsibleInventoryGenerator("base.generator.ansible_inventory"),
            {
                "instances": {
                    "l1_devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "l4_lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                }
            },
            "ansible_inventory_files",
        ),
        (
            BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox"),
            {"instances": {"l1_devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}]}},
            "bootstrap_proxmox_files",
        ),
        (
            BootstrapMikroTikGenerator("base.generator.bootstrap_mikrotik"),
            {"instances": {"l1_devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}]}},
            "bootstrap_mikrotik_files",
        ),
        (
            BootstrapOrangePiGenerator("base.generator.bootstrap_orangepi"),
            {"instances": {"l1_devices": [{"instance_id": "srv-opi", "object_ref": "obj.orangepi.rk3588.debian"}]}},
            "bootstrap_orangepi_files",
        ),
    ],
)
def test_generator_publishes_metadata_in_registry_context(
    tmp_path: Path,
    generator,
    compiled_json: dict,
    published_key: str,
) -> None:
    ctx = _ctx(tmp_path, compiled_json)
    ctx._set_execution_context(generator.plugin_id, set())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    published = set(ctx.get_published_keys(generator.plugin_id))
    assert "generated_dir" in published
    assert "generated_files" in published
    assert published_key in published

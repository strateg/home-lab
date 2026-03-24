#!/usr/bin/env python3
"""Contract checks: template-only rendering and generator publish metadata."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage  # noqa: E402
from plugins.generators.ansible_inventory_generator import AnsibleInventoryGenerator  # noqa: E402

# Plugin manifest paths
MIKROTIK_MANIFEST = V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins.yaml"
PROXMOX_MANIFEST = V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins.yaml"
ORANGEPI_MANIFEST = V5_ROOT / "topology" / "object-modules" / "orangepi" / "plugins.yaml"


def _load_plugin_config(manifest_path: Path, plugin_id: str) -> dict:
    """Load plugin config from manifest YAML."""
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    for row in plugins:
        if isinstance(row, dict) and row.get("id") == plugin_id:
            return row.get("config", {})
    return {}


def _load_generator_class(module_rel_path: str, class_name: str):
    module_path = V5_ROOT / module_rel_path
    spec = importlib.util.spec_from_file_location(f"test_{class_name.lower()}_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


BootstrapMikroTikGenerator = _load_generator_class(
    "topology/object-modules/mikrotik/plugins/bootstrap_mikrotik_generator.py",
    "BootstrapMikroTikGenerator",
)
BootstrapOrangePiGenerator = _load_generator_class(
    "topology/object-modules/orangepi/plugins/bootstrap_orangepi_generator.py",
    "BootstrapOrangePiGenerator",
)
BootstrapProxmoxGenerator = _load_generator_class(
    "topology/object-modules/proxmox/plugins/bootstrap_proxmox_generator.py",
    "BootstrapProxmoxGenerator",
)
TerraformMikroTikGenerator = _load_generator_class(
    "topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py",
    "TerraformMikroTikGenerator",
)
TerraformProxmoxGenerator = _load_generator_class(
    "topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py",
    "TerraformProxmoxGenerator",
)


def _ctx(tmp_path: Path, compiled_json: dict, plugin_config: dict | None = None) -> PluginContext:
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
    config = {
        "generator_artifacts_root": str(tmp_path / "generated"),
        "capability_templates": capability_templates,
    }
    if plugin_config:
        config.update(plugin_config)
    return PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config=config,
    )


@pytest.mark.parametrize(
    ("generator", "compiled_json", "expected_writes", "manifest_path", "plugin_id"),
    [
        (
            TerraformProxmoxGenerator("base.generator.terraform_proxmox"),
            {
                "instances": {
                    "devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                    "services": [{"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}}],
                }
            },
            8,
            None,
            None,
        ),
        (
            TerraformMikroTikGenerator("base.generator.terraform_mikrotik"),
            {
                "instances": {
                    "devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}],
                    "network": [{"instance_id": "inst.net.lan", "object_ref": "obj.network.l2_segment"}],
                    "services": [{"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}}],
                }
            },
            9,  # Without capability-driven files (qos, vpn, containers)
            None,
            None,
        ),
        (
            AnsibleInventoryGenerator("base.generator.ansible_inventory"),
            {
                "instances": {
                    "devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                }
            },
            4,
            None,
            None,
        ),
        (
            BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox"),
            {"instances": {"devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}]}},
            9,
            PROXMOX_MANIFEST,
            "base.generator.bootstrap_proxmox",
        ),
        (
            BootstrapMikroTikGenerator("base.generator.bootstrap_mikrotik"),
            {"instances": {"devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}]}},
            4,
            MIKROTIK_MANIFEST,
            "base.generator.bootstrap_mikrotik",
        ),
        (
            BootstrapOrangePiGenerator("base.generator.bootstrap_orangepi"),
            {"instances": {"devices": [{"instance_id": "srv-opi", "object_ref": "obj.orangepi.rk3588.debian"}]}},
            3,
            ORANGEPI_MANIFEST,
            "base.generator.bootstrap_orangepi",
        ),
    ],
)
def test_generator_outputs_are_template_rendered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    generator,
    compiled_json: dict,
    expected_writes: int,
    manifest_path: Path | None,
    plugin_id: str | None,
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

    plugin_config = _load_plugin_config(manifest_path, plugin_id) if manifest_path and plugin_id else None
    result = generator.execute(_ctx(tmp_path, compiled_json, plugin_config), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    assert len(writes) == expected_writes
    assert len(renders) == expected_writes
    assert all(content.startswith("TEMPLATE::") for _, content in writes)


@pytest.mark.parametrize(
    ("generator", "compiled_json", "published_key", "manifest_path", "plugin_id"),
    [
        (
            TerraformProxmoxGenerator("base.generator.terraform_proxmox"),
            {
                "instances": {
                    "devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                    "services": [{"instance_id": "svc-redis", "runtime": {"target_ref": "lxc-redis"}}],
                }
            },
            "terraform_proxmox_files",
            None,
            None,
        ),
        (
            TerraformMikroTikGenerator("base.generator.terraform_mikrotik"),
            {
                "instances": {
                    "devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}],
                    "network": [{"instance_id": "inst.net.lan", "object_ref": "obj.network.l2_segment"}],
                    "services": [{"instance_id": "svc-snmp", "runtime": {"target_ref": "rtr-mk"}}],
                }
            },
            "terraform_mikrotik_files",
            None,
            None,
        ),
        (
            AnsibleInventoryGenerator("base.generator.ansible_inventory"),
            {
                "instances": {
                    "devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}],
                    "lxc": [{"instance_id": "lxc-redis", "object_ref": "obj.proxmox.lxc.debian12.redis"}],
                }
            },
            "ansible_inventory_files",
            None,
            None,
        ),
        (
            BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox"),
            {"instances": {"devices": [{"instance_id": "srv-pve", "object_ref": "obj.proxmox.ve"}]}},
            "bootstrap_proxmox_files",
            PROXMOX_MANIFEST,
            "base.generator.bootstrap_proxmox",
        ),
        (
            BootstrapMikroTikGenerator("base.generator.bootstrap_mikrotik"),
            {"instances": {"devices": [{"instance_id": "rtr-mk", "object_ref": "obj.mikrotik.chateau_lte7_ax"}]}},
            "bootstrap_mikrotik_files",
            MIKROTIK_MANIFEST,
            "base.generator.bootstrap_mikrotik",
        ),
        (
            BootstrapOrangePiGenerator("base.generator.bootstrap_orangepi"),
            {"instances": {"devices": [{"instance_id": "srv-opi", "object_ref": "obj.orangepi.rk3588.debian"}]}},
            "bootstrap_orangepi_files",
            ORANGEPI_MANIFEST,
            "base.generator.bootstrap_orangepi",
        ),
    ],
)
def test_generator_publishes_metadata_in_registry_context(
    tmp_path: Path,
    generator,
    compiled_json: dict,
    published_key: str,
    manifest_path: Path | None,
    plugin_id: str | None,
) -> None:
    plugin_config = _load_plugin_config(manifest_path, plugin_id) if manifest_path and plugin_id else None
    ctx = _ctx(tmp_path, compiled_json, plugin_config)
    ctx._set_execution_context(generator.plugin_id, set())

    result = generator.execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    published = set(ctx.get_published_keys(generator.plugin_id))
    assert "generated_dir" in published
    assert "generated_files" in published
    assert published_key in published

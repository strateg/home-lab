#!/usr/bin/env python3
"""Generators must consume projection contract, not compiled_json internals."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = V5_ROOT / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext, PluginStatus, Stage  # noqa: E402
from plugins.generators import ansible_inventory_generator as ansible_module  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


proxmox_module = _load_module(
    "object_proxmox_terraform_generator",
    V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "terraform_proxmox_generator.py",
)
mikrotik_module = _load_module(
    "object_mikrotik_terraform_generator",
    V5_ROOT / "topology" / "object-modules" / "mikrotik" / "plugins" / "terraform_mikrotik_generator.py",
)
bootstrap_proxmox_module = _load_module(
    "object_proxmox_bootstrap_generator",
    V5_ROOT / "topology" / "object-modules" / "proxmox" / "plugins" / "bootstrap_proxmox_generator.py",
)


def _ctx(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=compiled_json,
        output_dir=str(tmp_path / "build"),
        config={"generator_artifacts_root": str(tmp_path / "generated")},
    )


@pytest.mark.parametrize(
    ("module", "builder_name", "generator_factory", "projection", "probe_file", "probe_text"),
    [
        (
            proxmox_module,
            "build_proxmox_projection",
            lambda: proxmox_module.TerraformProxmoxGenerator("base.generator.terraform_proxmox"),
            {
                "proxmox_nodes": [{"instance_id": "srv-probe"}],
                "lxc": [{"instance_id": "lxc-probe"}],
                "services": [{"instance_id": "svc-probe"}],
                "counts": {"proxmox_nodes": 1, "lxc": 1, "services": 1},
            },
            Path("terraform/proxmox/lxc.tf"),
            "lxc-probe",
        ),
        (
            mikrotik_module,
            "build_mikrotik_projection",
            lambda: mikrotik_module.TerraformMikroTikGenerator("base.generator.terraform_mikrotik"),
            {
                "routers": [{"instance_id": "rtr-probe"}],
                "networks": [{"instance_id": "inst.net.probe"}],
                "services": [{"instance_id": "svc-probe"}],
                "counts": {"routers": 1, "networks": 1, "services": 1},
            },
            Path("terraform/mikrotik/interfaces.tf"),
            "rtr-probe",
        ),
        (
            ansible_module,
            "build_ansible_projection",
            lambda: ansible_module.AnsibleInventoryGenerator("base.generator.ansible_inventory"),
            {
                "hosts": [
                    {
                        "instance_id": "host-probe",
                        "object_ref": "obj.probe.device",
                        "inventory_group": "devices",
                    }
                ],
                "counts": {"hosts": 1},
            },
            Path("ansible/inventory/production/hosts.yml"),
            "host-probe",
        ),
        (
            bootstrap_proxmox_module,
            "build_bootstrap_projection",
            lambda: bootstrap_proxmox_module.BootstrapProxmoxGenerator("base.generator.bootstrap_proxmox"),
            {
                "proxmox_nodes": [{"instance_id": "srv-probe"}],
                "mikrotik_nodes": [],
                "orangepi_nodes": [],
                "counts": {"proxmox_nodes": 1, "mikrotik_nodes": 0, "orangepi_nodes": 0},
            },
            Path("bootstrap/srv-probe/README.md"),
            "srv-probe",
        ),
    ],
)
def test_generator_uses_projection_contract_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module,
    builder_name: str,
    generator_factory,
    projection: dict,
    probe_file: Path,
    probe_text: str,
) -> None:
    monkeypatch.setattr(module, builder_name, lambda _: projection)
    ctx = _ctx(tmp_path, {"not_instances": "raw internals should not be used"})

    result = generator_factory().execute(ctx, Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    rendered = (tmp_path / "generated" / probe_file).read_text(encoding="utf-8")
    assert probe_text in rendered

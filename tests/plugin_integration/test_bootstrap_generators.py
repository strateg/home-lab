#!/usr/bin/env python3
"""Integration checks for bootstrap generator plugins."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

import pytest
from kernel.plugin_base import PluginContext, PluginStatus, Stage

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
    "topology/object-modules/mikrotik/plugins/generators/bootstrap_mikrotik_generator.py",
    "BootstrapMikroTikGenerator",
)
BootstrapOrangePiGenerator = _load_generator_class(
    "topology/object-modules/orangepi/plugins/generators/bootstrap_orangepi_generator.py",
    "BootstrapOrangePiGenerator",
)
BootstrapProxmoxGenerator = _load_generator_class(
    "topology/object-modules/proxmox/plugins/generators/bootstrap_proxmox_generator.py",
    "BootstrapProxmoxGenerator",
)


def _ctx(tmp_path: Path, compiled_json: dict, plugin_config: dict | None = None) -> PluginContext:
    config = {"generator_artifacts_root": str(tmp_path / "generated")}
    if plugin_config:
        config.update(plugin_config)
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        compiled_json=_semanticize(compiled_json),
        output_dir=str(tmp_path / "build"),
        config=config,
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


def _compiled_fixture_with_contract_mechanism() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "rtr-contract",
                    "object_ref": "obj.custom.router",
                    "object": {
                        "initialization_contract": {
                            "version": "1.0.0",
                            "mechanism": "netinstall",
                            "bootstrap": {"template": "bootstrap/init-terraform.rsc.j2"},
                        }
                    },
                }
            ]
        }
    }


def _compiled_fixture_with_proxmox_contract_mechanism() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "srv-contract",
                    "object_ref": "obj.custom.hypervisor",
                    "object": {
                        "initialization_contract": {
                            "version": "1.0.0",
                            "mechanism": "unattended_install",
                            "bootstrap": {
                                "template": "bootstrap/answer.toml.j2",
                                "post_install": "bootstrap/post-install-minimal.sh.j2",
                            },
                        }
                    },
                }
            ]
        }
    }


def _compiled_fixture_with_orangepi_contract_mechanism() -> dict:
    return {
        "instances": {
            "devices": [
                {
                    "instance_id": "opi-contract",
                    "object_ref": "obj.custom.edge",
                    "object": {
                        "initialization_contract": {
                            "version": "1.0.0",
                            "mechanism": "cloud_init",
                            "bootstrap": {
                                "template": "bootstrap/user-data.example.j2",
                                "outputs": {
                                    "user_data": "user-data.example",
                                    "meta_data": "meta-data",
                                },
                            },
                        }
                    },
                }
            ]
        }
    }


def _assert_artifact_contract_output(result, expected_family: str) -> None:
    artifact_plan = result.output_data.get("artifact_plan")
    artifact_report = result.output_data.get("artifact_generation_report")
    contract_files = result.output_data.get("artifact_contract_files")

    assert isinstance(artifact_plan, dict)
    assert isinstance(artifact_report, dict)
    assert artifact_plan.get("artifact_family") == expected_family
    assert artifact_report.get("artifact_family") == expected_family
    assert artifact_plan.get("schema_version") == "1.0"
    assert artifact_report.get("schema_version") == "1.0"
    assert isinstance(contract_files, list) and contract_files
    for path in contract_files:
        assert Path(path).exists(), f"Missing contract artifact file: {path}"


def test_bootstrap_proxmox_generator_writes_expected_files(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(PROXMOX_MANIFEST, "object.proxmox.generator.bootstrap")
    generator = BootstrapProxmoxGenerator("object.proxmox.generator.bootstrap")
    result = generator.execute(_ctx(tmp_path, _compiled_fixture(), plugin_config), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "srv-gamayun"
    assert (root / "answer.toml").exists()
    assert (root / "answer.toml.example").exists()
    assert (root / "post-install-minimal.sh").exists()
    assert (root / "README.md").exists()
    _assert_artifact_contract_output(result, "bootstrap.proxmox")


def test_bootstrap_proxmox_generator_uses_initialization_contract_mechanism(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(PROXMOX_MANIFEST, "object.proxmox.generator.bootstrap")
    generator = BootstrapProxmoxGenerator("object.proxmox.generator.bootstrap")
    result = generator.execute(
        _ctx(tmp_path, _compiled_fixture_with_proxmox_contract_mechanism(), plugin_config),
        Stage.GENERATE,
    )

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "srv-contract"
    assert (root / "answer.toml").exists()
    assert (root / "answer.toml.example").exists()
    assert (root / "post-install-minimal.sh").exists()


def test_bootstrap_proxmox_generator_fails_when_contract_template_is_invalid(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(PROXMOX_MANIFEST, "object.proxmox.generator.bootstrap")
    generator = BootstrapProxmoxGenerator("object.proxmox.generator.bootstrap")
    compiled = _compiled_fixture_with_proxmox_contract_mechanism()
    compiled["instances"]["devices"][0]["object"]["initialization_contract"]["bootstrap"]["template"] = (  # type: ignore[index]
        "bootstrap/does-not-exist.toml.j2"
    )

    result = generator.execute(_ctx(tmp_path, compiled, plugin_config), Stage.GENERATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9402" for diag in result.diagnostics)


def test_bootstrap_mikrotik_generator_writes_expected_files(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(MIKROTIK_MANIFEST, "object.mikrotik.generator.bootstrap")
    generator = BootstrapMikroTikGenerator("object.mikrotik.generator.bootstrap")
    result = generator.execute(_ctx(tmp_path, _compiled_fixture(), plugin_config), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "rtr-mk"
    assert (root / "init-terraform.rsc").exists()
    assert (root / "backup-restore-overrides.rsc").exists()
    assert (root / "terraform.tfvars.example").exists()
    _assert_artifact_contract_output(result, "bootstrap.mikrotik")


def test_bootstrap_mikrotik_generator_uses_initialization_contract_mechanism(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(MIKROTIK_MANIFEST, "object.mikrotik.generator.bootstrap")
    generator = BootstrapMikroTikGenerator("object.mikrotik.generator.bootstrap")
    result = generator.execute(
        _ctx(tmp_path, _compiled_fixture_with_contract_mechanism(), plugin_config), Stage.GENERATE
    )

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "rtr-contract"
    assert (root / "init-terraform.rsc").exists()


def test_bootstrap_mikrotik_generator_fails_when_contract_template_is_invalid(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(MIKROTIK_MANIFEST, "object.mikrotik.generator.bootstrap")
    generator = BootstrapMikroTikGenerator("object.mikrotik.generator.bootstrap")
    compiled = _compiled_fixture_with_contract_mechanism()
    compiled["instances"]["devices"][0]["object"]["initialization_contract"]["bootstrap"]["template"] = (  # type: ignore[index]
        "bootstrap/does-not-exist.rsc.j2"
    )

    result = generator.execute(_ctx(tmp_path, compiled, plugin_config), Stage.GENERATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E9502" for diag in result.diagnostics)


def test_bootstrap_orangepi_generator_writes_expected_files(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(ORANGEPI_MANIFEST, "object.orangepi.generator.bootstrap")
    generator = BootstrapOrangePiGenerator("object.orangepi.generator.bootstrap")
    result = generator.execute(_ctx(tmp_path, _compiled_fixture(), plugin_config), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "srv-orangepi5" / "cloud-init"
    assert (root / "user-data.example").exists()
    assert (root / "meta-data").exists()
    assert (root / "README.md").exists()
    _assert_artifact_contract_output(result, "bootstrap.orangepi")


def test_bootstrap_orangepi_generator_uses_initialization_contract_mechanism(tmp_path: Path) -> None:
    plugin_config = _load_plugin_config(ORANGEPI_MANIFEST, "object.orangepi.generator.bootstrap")
    generator = BootstrapOrangePiGenerator("object.orangepi.generator.bootstrap")
    result = generator.execute(
        _ctx(tmp_path, _compiled_fixture_with_orangepi_contract_mechanism(), plugin_config),
        Stage.GENERATE,
    )

    assert result.status == PluginStatus.SUCCESS
    root = tmp_path / "generated" / "bootstrap" / "opi-contract" / "cloud-init"
    assert (root / "user-data.example").exists()
    assert (root / "meta-data").exists()


def test_bootstrap_generators_report_projection_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"instances": {"devices": [{}]}})
    generators = [
        (BootstrapProxmoxGenerator("object.proxmox.generator.bootstrap"), "E9401"),
        (BootstrapMikroTikGenerator("object.mikrotik.generator.bootstrap"), "E9501"),
        (BootstrapOrangePiGenerator("object.orangepi.generator.bootstrap"), "E9601"),
    ]
    for generator, code in generators:
        result = generator.execute(ctx, Stage.GENERATE)
        assert result.status == PluginStatus.FAILED
        assert any(diag.code == code for diag in result.diagnostics)


@pytest.mark.parametrize(
    ("generator_cls", "plugin_id", "manifest_path", "stale_rel_path", "expected_family"),
    [
        (
            BootstrapProxmoxGenerator,
            "object.proxmox.generator.bootstrap",
            PROXMOX_MANIFEST,
            Path("bootstrap/srv-gamayun/stale.proxmox.tmp"),
            "bootstrap.proxmox",
        ),
        (
            BootstrapMikroTikGenerator,
            "object.mikrotik.generator.bootstrap",
            MIKROTIK_MANIFEST,
            Path("bootstrap/rtr-mk/stale.mikrotik.tmp"),
            "bootstrap.mikrotik",
        ),
        (
            BootstrapOrangePiGenerator,
            "object.orangepi.generator.bootstrap",
            ORANGEPI_MANIFEST,
            Path("bootstrap/srv-orangepi5/cloud-init/stale.orangepi.tmp"),
            "bootstrap.orangepi",
        ),
    ],
)
def test_bootstrap_generators_obsolete_delete_uses_output_prefix_ownership(
    tmp_path: Path,
    generator_cls,
    plugin_id: str,
    manifest_path: Path,
    stale_rel_path: Path,
    expected_family: str,
) -> None:
    plugin_config = _load_plugin_config(manifest_path, plugin_id)
    plugin_config["artifact_obsolete_action"] = "delete"
    stale_path = tmp_path / "generated" / stale_rel_path
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("# stale\n", encoding="utf-8")

    generator = generator_cls(plugin_id)
    result = generator.execute(_ctx(tmp_path, _compiled_fixture(), plugin_config), Stage.GENERATE)

    assert result.status == PluginStatus.SUCCESS
    report = result.output_data["artifact_generation_report"]
    assert report["artifact_family"] == expected_family
    expected_stale_path = Path("generated") / stale_rel_path
    stale_entry = next(item for item in report["obsolete"] if item["path"] == expected_stale_path.as_posix())
    assert stale_entry["action"] == "delete"
    assert stale_entry["ownership_proven"] is True
    assert stale_entry["ownership_method"] == "output_prefix_match"

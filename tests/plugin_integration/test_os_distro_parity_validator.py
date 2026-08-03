#!/usr/bin/env python3
"""Integration tests for OS distribution parity validator plugin."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.os_distro_parity"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _context() -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects={},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _os_row(instance: str, object_ref: str) -> dict:
    return {
        "group": "os",
        "instance": instance,
        "class_ref": "class.os",
        "object_ref": object_ref,
    }


def test_os_distro_parity_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def test_os_distro_parity_accepts_matching_distribution_token() -> None:
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("inst.os.ubuntu.2404.x86_64.oci", "obj.os.ubuntu.24.04.x86_64.cloud")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_rejects_generic_object_for_named_distribution() -> None:
    """The regression this validator exists for: ubuntu instance on a generic object."""
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("inst.os.ubuntu.2404.x86_64.oci", "obj.os.linux.generic.x86_64")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7816" for diag in result.diagnostics)


def test_os_distro_parity_rejects_unrelated_distribution() -> None:
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("inst.os.armbian.26.5.arm64.edge", "obj.os.debian.12.arm64.edge")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7816" for diag in result.diagnostics)


def test_os_distro_parity_rejects_non_os_object_ref() -> None:
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("inst.os.ubuntu.2404.x86_64.oci", "obj.oracle.cloud_vm")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7816" for diag in result.diagnostics)


def test_os_distro_parity_accepts_generic_instance_on_generic_object() -> None:
    """inst.os.linux.generic.* is honestly generic and must not be flagged."""
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("inst.os.linux.generic.x86_64", "obj.os.linux.generic.x86_64")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_accepts_product_tokens_diverging_from_properties() -> None:
    """Token parity, not properties: proxmox declares debian, android declares aosp."""
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.proxmox.ve.9", "obj.os.proxmox.ve.9"),
            _os_row("inst.os.android.15.arm64.boox", "obj.os.android.15.arm64"),
            _os_row("inst.os.sailfish.finnlayson.arm64.jolla", "obj.os.sailfish.5.arm64"),
            _os_row("inst.os.debian.12.proxmox.lxc", "obj.os.debian.12.proxmox.lxc"),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_ignores_non_os_rows() -> None:
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [
            {
                "group": "devices",
                "instance": "srv-orangepi5",
                "class_ref": "class.compute.edge_node",
                "object_ref": "obj.orangepi.rk3588.sbc",
            }
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_ignores_rows_without_object_ref() -> None:
    """Unresolvable refs belong to base.validator.reference, not to this plugin."""
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [{"group": "os", "instance": "inst.os.ubuntu.2404.x86_64.oci", "class_ref": "class.os"}],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_ignores_identifiers_outside_convention() -> None:
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("legacy-os-row", "obj.os.linux.generic.x86_64")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_token_comparison_is_case_insensitive() -> None:
    registry = _registry()
    ctx = _context()
    _publish_rows(
        ctx,
        [_os_row("inst.os.Ubuntu.2404.x86_64.oci", "obj.os.UBUNTU.24.04.x86_64.cloud")],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_distro_parity_requires_compiler_rows() -> None:
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_os_distro_parity_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "base.compiler.instance_rows",
                "kind": "compiler",
                "entry": f"{(V5_TOOLS / 'plugins/compilers/instance_rows_compiler.py').as_posix()}:InstanceRowsCompiler",
                "api_version": "1.x",
                "stages": ["compile"],
                "phase": "run",
                "order": 43,
            },
            {
                "id": PLUGIN_ID,
                "kind": "validator_json",
                "entry": (
                    f"{(V5_TOOLS / 'plugins/validators/os_distro_parity_validator.py').as_posix()}"
                    ":OsDistroParityValidator"
                ),
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 117,
                "depends_on": ["base.compiler.instance_rows"],
                "consumes": [
                    {"from_plugin": "base.compiler.instance_rows", "key": "normalized_rows", "required": True}
                ],
            },
        ],
    }
    _write_manifest(manifest, payload)
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    ctx = _context()

    results = registry.execute_stage(Stage.VALIDATE, ctx, parallel_plugins=False)

    assert len(results) == 1
    assert results[0].status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in results[0].diagnostics)

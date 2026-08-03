#!/usr/bin/env python3
"""Integration tests for software_contract.os_obj_refs allow-list validator."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

PLUGIN_ID = "base.validator.os_obj_refs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _context(objects: dict | None = None) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
    )


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows", "normalized_rows", rows)


def _os_row(instance: str, object_ref: str) -> dict:
    return {"group": "os", "instance": instance, "class_ref": "class.os", "object_ref": object_ref}


def _host_row(instance: str, object_ref: str, os_refs: list[str]) -> dict:
    return {
        "group": "docker",
        "instance": instance,
        "class_ref": "class.compute.workload.docker",
        "object_ref": object_ref,
        "os_refs": os_refs,
    }


def _objects(allow: list[str] | None) -> dict:
    contract: dict = {}
    if allow is not None:
        contract["os_obj_refs"] = allow
    return {"obj.host.generic": {"software_contract": contract}}


def test_os_obj_refs_manifest_requires_normalized_rows() -> None:
    registry = _registry()
    normalized_rows = registry.specs[PLUGIN_ID].consumes[0]
    assert normalized_rows["required"] is True


def test_os_obj_refs_accepts_binding_inside_allow_list() -> None:
    registry = _registry()
    ctx = _context(_objects(["obj.os.debian.12.arm64.container_base"]))
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.base", "obj.os.debian.12.arm64.container_base"),
            _host_row("docker-grafana", "obj.host.generic", ["inst.os.base"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_rejects_binding_outside_allow_list() -> None:
    """The regression this validator exists for: container bound the host edge profile."""
    registry = _registry()
    ctx = _context(_objects(["obj.os.debian.12.arm64.container_base"]))
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.edge", "obj.os.debian.12.arm64.edge"),
            _host_row("docker-grafana", "obj.host.generic", ["inst.os.edge"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E7842" for diag in result.diagnostics)


def test_os_obj_refs_reports_each_offending_binding() -> None:
    registry = _registry()
    ctx = _context(_objects(["obj.os.allowed"]))
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.bad_a", "obj.os.denied.a"),
            _os_row("inst.os.bad_b", "obj.os.denied.b"),
            _host_row("host-1", "obj.host.generic", ["inst.os.bad_a", "inst.os.bad_b"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert len([d for d in result.diagnostics if d.code == "E7842"]) == 2


def test_os_obj_refs_accepts_multi_entry_allow_list() -> None:
    """Dual-boot: both bindings permitted by a two-entry allow-list."""
    registry = _registry()
    ctx = _context(_objects(["obj.os.armbian.26.5.arm64.edge", "obj.os.ubuntu.24.10.arm64.desktop"]))
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.armbian", "obj.os.armbian.26.5.arm64.edge"),
            _os_row("inst.os.ubuntu", "obj.os.ubuntu.24.10.arm64.desktop"),
            _host_row("srv-orangepi5", "obj.host.generic", ["inst.os.armbian", "inst.os.ubuntu"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_skips_object_without_allow_list() -> None:
    registry = _registry()
    ctx = _context(_objects(None))
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.anything", "obj.os.whatever"),
            _host_row("device-1", "obj.host.generic", ["inst.os.anything"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_treats_empty_allow_list_as_undeclared() -> None:
    """An empty list means 'undeclared', not 'forbid everything'."""
    registry = _registry()
    ctx = _context(_objects([]))
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.anything", "obj.os.whatever"),
            _host_row("device-1", "obj.host.generic", ["inst.os.anything"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_skips_unresolvable_os_ref() -> None:
    registry = _registry()
    ctx = _context(_objects(["obj.os.allowed"]))
    _publish_rows(ctx, [_host_row("device-1", "obj.host.generic", ["inst.os.missing"])])

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_skips_non_os_targets() -> None:
    registry = _registry()
    ctx = _context(_objects(["obj.os.allowed"]))
    _publish_rows(
        ctx,
        [
            {"group": "firmware", "instance": "inst.fw.a", "class_ref": "class.firmware", "object_ref": "obj.fw.a"},
            _host_row("device-1", "obj.host.generic", ["inst.fw.a"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_skips_os_rows_themselves() -> None:
    registry = _registry()
    ctx = _context(_objects(["obj.os.allowed"]))
    _publish_rows(
        ctx,
        [
            {
                "group": "os",
                "instance": "inst.os.a",
                "class_ref": "class.os",
                "object_ref": "obj.host.generic",
                "os_refs": ["inst.os.b"],
            },
            _os_row("inst.os.b", "obj.os.denied"),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_skips_row_with_unknown_object() -> None:
    registry = _registry()
    ctx = _context({})
    _publish_rows(
        ctx,
        [
            _os_row("inst.os.a", "obj.os.denied"),
            _host_row("device-1", "obj.host.missing", ["inst.os.a"]),
        ],
    )

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.SUCCESS
    assert result.diagnostics == []


def test_os_obj_refs_requires_compiler_rows() -> None:
    registry = _registry()
    ctx = _context()

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(diag.code == "E8003" for diag in result.diagnostics)


def test_os_obj_refs_execute_stage_requires_committed_normalized_rows(tmp_path: Path) -> None:
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
                    f"{(V5_TOOLS / 'plugins/validators/os_obj_refs_validator.py').as_posix()}" ":OsObjRefsValidator"
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

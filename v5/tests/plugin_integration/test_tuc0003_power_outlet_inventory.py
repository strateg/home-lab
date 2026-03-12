#!/usr/bin/env python3
"""Integration checks for TUC-0003 power outlet inventory validation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V5_TOOLS = REPO_ROOT / "v5" / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

PLUGIN_ID = "base.validator.power_source_refs"


def _load_compiler_module():
    module_path = REPO_ROOT / "v5" / "topology-tools" / "compile-topology.py"
    spec = importlib.util.spec_from_file_location("compile_topology_module_tuc0003", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _publish_rows(ctx: PluginContext, rows: list[dict]) -> None:
    ctx._set_execution_context("base.compiler.instance_rows", set())
    ctx.publish("normalized_rows", rows)
    ctx._clear_execution_context()


def test_tuc0003_compile_keeps_power_outlet_bindings(tmp_path: Path):
    mod = _load_compiler_module()
    out_dir = mod.REPO_ROOT / "v5-build" / "test-tuc0003" / tmp_path.name
    output_json = out_dir / "effective-topology.json"

    compiler = mod.V5Compiler(
        manifest_path=mod.DEFAULT_MANIFEST,
        output_json=output_json,
        diagnostics_json=out_dir / "diagnostics.json",
        diagnostics_txt=out_dir / "diagnostics.txt",
        error_catalog_path=mod.DEFAULT_ERROR_CATALOG,
        strict_model_lock=True,
        fail_on_warning=False,
        require_new_model=False,
        enable_plugins=True,
        plugins_manifest_path=mod.DEFAULT_PLUGINS_MANIFEST,
    )

    exit_code = compiler.run()
    assert exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    l1_rows = payload.get("instances", {}).get("l1_devices", [])
    by_source_id = {row.get("source_id"): row for row in l1_rows if isinstance(row, dict)}

    mikrotik = by_source_id.get("rtr-mikrotik-chateau")
    slate = by_source_id.get("rtr-slate")
    assert isinstance(mikrotik, dict)
    assert isinstance(slate, dict)
    assert mikrotik.get("instance_data", {}).get("power", {}).get("outlet_ref") == "outlet_01"
    assert slate.get("instance_data", {}).get("power", {}).get("outlet_ref") == "outlet_02"


def test_tuc0003_validator_rejects_undeclared_outlet():
    registry = _registry()
    rows = [
        {
            "group": "l1_devices",
            "instance": "pdu-rack",
            "layer": "L1",
            "class_ref": "class.power.pdu",
            "object_ref": "obj.pdu.generic.managed",
            "extensions": {},
        },
        {
            "group": "l1_devices",
            "instance": "router-1",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.1",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "outlet_99"}},
        },
    ]
    objects = {
        "obj.pdu.generic.managed": {
            "object": "obj.pdu.generic.managed",
            "class_ref": "class.power.pdu",
            "properties": {
                "power": {
                    "outlets": [
                        "outlet_01",
                        "outlet_02",
                    ]
                }
            },
        },
        "obj.router.1": {"object": "obj.router.1", "class_ref": "class.router"},
    }
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7806" for d in result.diagnostics)


def test_tuc0003_validator_rejects_outlet_when_source_has_no_inventory():
    registry = _registry()
    rows = [
        {
            "group": "l1_devices",
            "instance": "pdu-rack",
            "layer": "L1",
            "class_ref": "class.power.pdu",
            "object_ref": "obj.pdu.generic.managed",
            "extensions": {},
        },
        {
            "group": "l1_devices",
            "instance": "router-1",
            "layer": "L1",
            "class_ref": "class.router",
            "object_ref": "obj.router.1",
            "extensions": {"power": {"source_ref": "pdu-rack", "outlet_ref": "outlet_01"}},
        },
    ]
    objects = {
        "obj.pdu.generic.managed": {
            "object": "obj.pdu.generic.managed",
            "class_ref": "class.power.pdu",
            # no properties.power.outlets on purpose
        },
        "obj.router.1": {"object": "obj.router.1", "class_ref": "class.router"},
    }
    ctx = PluginContext(
        topology_path="v5/topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        classes={},
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )
    _publish_rows(ctx, rows)

    result = registry.execute_plugin(PLUGIN_ID, ctx, Stage.VALIDATE)
    assert result.status == PluginStatus.FAILED
    assert any(d.code == "E7806" for d in result.diagnostics)

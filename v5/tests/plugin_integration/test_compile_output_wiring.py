#!/usr/bin/env python3
"""Integration checks for plugin compile output wiring in orchestrator helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from compiler_runtime import CompileInputs, apply_plugin_compile_outputs


def _inputs() -> CompileInputs:
    return CompileInputs(
        class_map={},
        object_map={},
        catalog_ids=set(),
        packs_map={},
        instance_payload={"instance_bindings": {}},
        rows=[],
        lock_payload=None,
        instance_source_mode="sharded-only",
    )


def test_compile_output_wiring_is_key_based_not_plugin_id_based():
    diagnostics = []
    inputs = _inputs()
    plugin_ctx = SimpleNamespace(
        plugin_outputs={
            "custom.module_loader": {
                "class_map": {"class.router": {"payload": {}}},
                "object_map": {"obj.router": {"payload": {}}},
            },
            "custom.instance_rows": {"normalized_rows": [{"instance": "rtr-1"}]},
            "custom.model_lock_loader": {
                "lock_payload": {"core_model_version": "1.0.0"},
                "model_lock_loaded": True,
            },
            "custom.capability_contract_loader": {
                "catalog_ids": ["cap.net.interface.ethernet"],
                "packs_map": {"pack.router.test": {"capabilities": []}},
            },
        },
        config={},
        model_lock={},
    )

    def _owner(rule_name: str) -> str:
        if rule_name in {"model_lock_data", "module_maps", "instance_rows", "capability_contract_data"}:
            return "plugin"
        return "core"

    apply_plugin_compile_outputs(
        inputs=inputs,
        plugin_ctx=plugin_ctx,
        compilation_owner=_owner,
        add_diag=lambda **payload: diagnostics.append(payload),
    )

    assert inputs.class_map == {"class.router": {"payload": {}}}
    assert inputs.object_map == {"obj.router": {"payload": {}}}
    assert inputs.rows == [{"instance": "rtr-1"}]
    assert inputs.lock_payload == {"core_model_version": "1.0.0"}
    assert inputs.catalog_ids == {"cap.net.interface.ethernet"}
    assert inputs.packs_map == {"pack.router.test": {"capabilities": []}}
    assert plugin_ctx.model_lock == {"core_model_version": "1.0.0"}
    assert plugin_ctx.config["model_lock_loaded"] is True
    assert diagnostics == []


def test_compile_output_wiring_reports_ambiguous_output_key():
    diagnostics = []
    inputs = _inputs()
    plugin_ctx = SimpleNamespace(
        plugin_outputs={
            "plugin.a": {"normalized_rows": [{"instance": "rtr-a"}]},
            "plugin.b": {"normalized_rows": [{"instance": "rtr-b"}]},
        },
        config={},
        model_lock={},
    )

    apply_plugin_compile_outputs(
        inputs=inputs,
        plugin_ctx=plugin_ctx,
        compilation_owner=lambda rule_name: "plugin" if rule_name == "instance_rows" else "core",
        add_diag=lambda **payload: diagnostics.append(payload),
    )

    assert diagnostics
    assert any(diag.get("code") == "E6901" for diag in diagnostics)
    assert any(diag.get("stage") == "compile" for diag in diagnostics)
    assert any("Ambiguous plugin compile output" in str(diag.get("message")) for diag in diagnostics)

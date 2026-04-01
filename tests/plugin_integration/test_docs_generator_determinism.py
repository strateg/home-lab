#!/usr/bin/env python3
"""Determinism checks for docs generator output (ADR0079 quality gate)."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus  # noqa: E402
from kernel.plugin_base import Stage  # noqa: E402

PLUGIN_ID = "base.generator.docs"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context(tmp_path: Path, compiled_json: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
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
                {
                    "instance_id": "srv-b",
                    "object_ref": "obj.compute.server.b",
                    "class_ref": "class.compute.hypervisor",
                    "status": "mapped",
                    "layer": "L1",
                },
                {
                    "instance_id": "srv-a",
                    "object_ref": "obj.compute.server.a",
                    "class_ref": "class.compute.hypervisor",
                    "status": "mapped",
                    "layer": "L1",
                },
            ],
            "network": [
                {
                    "instance_id": "inst.trust_zone.servers",
                    "object_ref": "obj.network.trust_zone.servers",
                    "class_ref": "class.network.trust_zone",
                    "status": "mapped",
                },
                {
                    "instance_id": "inst.vlan.servers",
                    "object_ref": "obj.network.vlan.servers",
                    "class_ref": "class.network.vlan",
                    "status": "mapped",
                    "instance_data": {"trust_zone_ref": "inst.trust_zone.servers", "managed_by_ref": "rtr-a"},
                },
            ],
            "services": [
                {
                    "instance_id": "svc-z",
                    "object_ref": "obj.service.z",
                    "class_ref": "class.service.web_ui",
                    "status": "mapped",
                    "instance_data": {"dependencies": [{"service_ref": "svc-a"}]},
                },
                {
                    "instance_id": "svc-a",
                    "object_ref": "obj.service.a",
                    "class_ref": "class.service.database",
                    "status": "mapped",
                    "instance_data": {},
                },
            ],
            "firewall": [],
            "pools": [],
            "data-assets": [],
            "operations": [],
            "observability": [],
            "qos": [],
            "data-channels": [],
            "physical-links": [],
            "power": [],
            "lxc": [],
            "vms": [],
        }
    }


def _render_docs(tmp_path: Path, compiled_json: dict) -> dict[str, str]:
    registry = _registry()
    result = registry.execute_plugin(PLUGIN_ID, _context(tmp_path, compiled_json), Stage.GENERATE)
    assert result.status == PluginStatus.SUCCESS
    docs_root = tmp_path / "generated" / "docs"
    contents: dict[str, str] = {}
    for path in sorted(docs_root.glob("*.md")):
        contents[path.name] = path.read_text(encoding="utf-8")
    return contents


def test_docs_generator_is_deterministic_for_repeated_runs(tmp_path: Path) -> None:
    fixture = _compiled_fixture()
    first = _render_docs(tmp_path / "run1", fixture)
    second = _render_docs(tmp_path / "run2", fixture)
    assert first == second


def test_docs_generator_is_order_invariant_for_input_rows(tmp_path: Path) -> None:
    fixture = _compiled_fixture()
    reordered = copy.deepcopy(fixture)
    for rows in reordered["instances"].values():
        if isinstance(rows, list):
            rows.reverse()
    baseline = _render_docs(tmp_path / "baseline", fixture)
    variant = _render_docs(tmp_path / "variant", reordered)
    assert baseline == variant

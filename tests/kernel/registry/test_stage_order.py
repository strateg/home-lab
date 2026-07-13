#!/usr/bin/env python3
"""Execution-order resolution tests (kernel/registry side).

Split verbatim from tests/test_plugin_registry.py in S9 of
docs/analysis/PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07.md.
Calls stay facade-level (PluginRegistry.get_execution_order);
the implementation lives in kernel/registry/dependency_resolver.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

V5_TOOLS = Path(__file__).resolve().parents[3] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginRegistry  # noqa: E402
from kernel.plugin_base import Phase, Stage  # noqa: E402

REFERENCE_VALIDATOR_ENTRY = "plugins/validators/reference_validator.py:ReferenceValidator"


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_stage_order_prefers_order_over_manifest_insertion(tmp_path: Path):
    """Independent plugins should be ordered by numeric order, not load order."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "zmod.validator_json.second",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 188,
                "depends_on": [],
            },
            {
                "id": "amod.validator_json.first",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "depends_on": [],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    order = registry.get_execution_order(Stage.VALIDATE)
    assert order == ["amod.validator_json.first", "zmod.validator_json.second"]


def test_stage_order_uses_id_as_tiebreaker(tmp_path: Path):
    """Plugins with same order should be sorted lexically by plugin ID."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "zmod.validator_json.b",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "depends_on": [],
            },
            {
                "id": "amod.validator_json.a",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 100,
                "depends_on": [],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    order = registry.get_execution_order(Stage.VALIDATE)
    assert order == ["amod.validator_json.a", "zmod.validator_json.b"]


def test_stage_order_respects_depends_on_over_numeric_order(tmp_path: Path):
    """Dependency relation must dominate numeric order."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "amod.validator_json.base",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 188,
                "depends_on": [],
            },
            {
                "id": "zmod.validator_json.dep",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "order": 91,
                "depends_on": ["amod.validator_json.base"],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    order = registry.get_execution_order(Stage.VALIDATE)
    assert order == ["amod.validator_json.base", "zmod.validator_json.dep"]


def test_execution_order_filters_by_phase(tmp_path: Path):
    """Execution order must be resolved independently for each phase."""
    manifest = tmp_path / "plugins.yaml"
    payload = {
        "schema_version": 1,
        "plugins": [
            {
                "id": "phase.validator_json.init",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "init",
                "order": 91,
            },
            {
                "id": "phase.validator_json.run",
                "kind": "validator_json",
                "entry": REFERENCE_VALIDATOR_ENTRY,
                "api_version": "1.x",
                "stages": ["validate"],
                "phase": "run",
                "order": 91,
                "depends_on": ["phase.validator_json.init"],
            },
        ],
    }
    _write_manifest(manifest, payload)

    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)

    init_order = registry.get_execution_order(Stage.VALIDATE, phase=Phase.INIT)
    run_order = registry.get_execution_order(Stage.VALIDATE, phase=Phase.RUN)

    assert init_order == ["phase.validator_json.init"]
    assert run_order == ["phase.validator_json.run"]

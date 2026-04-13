#!/usr/bin/env python3
"""Focused plugin execution ordering tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginCycleError, PluginLoadError, PluginRegistry  # noqa: E402
from kernel.plugin_base import Phase, Stage  # noqa: E402


def _write_manifest(path: Path, plugins: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"schema_version": 1, "plugins": plugins}, sort_keys=False), encoding="utf-8")


def _plugin(
    plugin_id: str,
    *,
    kind: str = "validator_json",
    stages: list[str] | None = None,
    phase: str = "run",
    order: int = 100,
    depends_on: list[str] | None = None,
) -> dict:
    family = {
        "compiler": "compilers",
        "validator_json": "validators",
    }.get(kind, "validators")
    return {
        "id": plugin_id,
        "kind": kind,
        "entry": f"{family}/reference_validator.py:ReferenceValidator",
        "api_version": "1.x",
        "stages": stages or ["validate"],
        "phase": phase,
        "order": order,
        "depends_on": depends_on or [],
    }


def _registry(manifest: Path) -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(manifest)
    assert registry.get_load_errors() == []
    return registry


def test_execution_order_detects_cycles(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        [
            _plugin("cycle.validator_json.a", depends_on=["cycle.validator_json.b"]),
            _plugin("cycle.validator_json.b", depends_on=["cycle.validator_json.a"]),
        ],
    )
    registry = _registry(manifest)

    with pytest.raises(PluginCycleError) as exc_info:
        registry.get_execution_order(Stage.VALIDATE)

    assert exc_info.value.cycle == [
        "cycle.validator_json.a",
        "cycle.validator_json.b",
        "cycle.validator_json.a",
    ]


def test_execution_order_resolves_diamond_dependencies_before_numeric_order(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        [
            _plugin(
                "diamond.validator_json.join",
                order=91,
                depends_on=["diamond.validator_json.left", "diamond.validator_json.right"],
            ),
            _plugin("diamond.validator_json.right", order=93, depends_on=["diamond.validator_json.base"]),
            _plugin("diamond.validator_json.left", order=92, depends_on=["diamond.validator_json.base"]),
            _plugin("diamond.validator_json.base", order=188),
        ],
    )
    registry = _registry(manifest)

    assert registry.get_execution_order(Stage.VALIDATE) == [
        "diamond.validator_json.base",
        "diamond.validator_json.left",
        "diamond.validator_json.right",
        "diamond.validator_json.join",
    ]


def test_execution_order_uses_order_then_plugin_id_for_ready_ties(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        [
            _plugin("tie.validator_json.z", order=120),
            _plugin("tie.validator_json.b", order=100),
            _plugin("tie.validator_json.a", order=100),
        ],
    )
    registry = _registry(manifest)

    assert registry.get_execution_order(Stage.VALIDATE) == [
        "tie.validator_json.a",
        "tie.validator_json.b",
        "tie.validator_json.z",
    ]


def test_execution_order_allows_backward_stage_and_phase_dependencies(tmp_path: Path) -> None:
    manifest = tmp_path / "plugins.yaml"
    _write_manifest(
        manifest,
        [
            _plugin("phase.compiler.pre", kind="compiler", stages=["compile"], phase="pre", order=31),
            _plugin(
                "phase.compiler.run",
                kind="compiler",
                stages=["compile"],
                phase="run",
                order=32,
                depends_on=["phase.compiler.pre"],
            ),
            _plugin("phase.validator_json.run", order=91, depends_on=["phase.compiler.run"]),
        ],
    )
    registry = _registry(manifest)

    assert registry.resolve_dependencies() == [
        "phase.compiler.pre",
        "phase.compiler.run",
        "phase.validator_json.run",
    ]
    assert registry.get_execution_order(Stage.COMPILE, phase=Phase.PRE) == ["phase.compiler.pre"]
    assert registry.get_execution_order(Stage.COMPILE, phase=Phase.RUN) == ["phase.compiler.run"]
    assert registry.get_execution_order(Stage.VALIDATE, phase=Phase.RUN) == ["phase.validator_json.run"]


def test_execution_order_rejects_forward_stage_and_phase_dependencies(tmp_path: Path) -> None:
    forward_stage_manifest = tmp_path / "forward-stage.yaml"
    _write_manifest(
        forward_stage_manifest,
        [
            _plugin(
                "forward.compiler.run",
                kind="compiler",
                stages=["compile"],
                order=31,
                depends_on=["forward.validator_json.run"],
            ),
            _plugin("forward.validator_json.run", order=91),
        ],
    )
    stage_registry = _registry(forward_stage_manifest)

    with pytest.raises(PluginLoadError, match="Forward stage/phase dependency is not allowed"):
        stage_registry.resolve_dependencies()

    forward_phase_manifest = tmp_path / "forward-phase.yaml"
    _write_manifest(
        forward_phase_manifest,
        [
            _plugin("forward_phase.validator_json.run", order=91, depends_on=["forward_phase.validator_json.post"]),
            _plugin("forward_phase.validator_json.post", phase="post", order=92),
        ],
    )
    phase_registry = _registry(forward_phase_manifest)

    with pytest.raises(PluginLoadError, match="Forward stage/phase dependency is not allowed"):
        phase_registry.resolve_dependencies()

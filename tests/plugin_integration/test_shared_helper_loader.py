#!/usr/bin/env python3
"""Tests for shared helper loader context-root resolution."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
if str(V5_TOOLS) not in sys.path:
    sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext  # noqa: E402
from plugins.generators.shared_helper_loader import (  # noqa: E402
    load_bootstrap_helpers,
    load_router_port_validator_base,
)


def test_load_bootstrap_helpers_uses_context_object_modules_root(tmp_path: Path) -> None:
    object_modules_root = tmp_path / "object-modules"
    helper_path = object_modules_root / "_shared" / "plugins" / "bootstrap_helpers.py"
    helper_path.parent.mkdir(parents=True)
    helper_path.write_text("def marker():\n    return 'ok'\n", encoding="utf-8")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"object_modules_root": str(object_modules_root)},
    )

    module = load_bootstrap_helpers(ctx=ctx)
    assert Path(str(module.__file__)).resolve() == helper_path.resolve()


def test_load_router_port_validator_base_uses_context_class_modules_root(tmp_path: Path) -> None:
    class_modules_root = tmp_path / "class-modules"
    base_path = class_modules_root / "router" / "plugins" / "router_port_validator_base.py"
    base_path.parent.mkdir(parents=True)
    base_path.write_text("class RouterPortValidatorBase:\n    pass\n", encoding="utf-8")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"class_modules_root": str(class_modules_root)},
    )

    module = load_router_port_validator_base(ctx=ctx)
    assert Path(str(module.__file__)).resolve() == base_path.resolve()

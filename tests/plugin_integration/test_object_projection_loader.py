#!/usr/bin/env python3
"""Tests for object projection loader discovery contract."""

from __future__ import annotations

import sys
from pathlib import Path

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.plugin_base import PluginContext  # noqa: E402
from plugins.generators.object_projection_loader import (  # noqa: E402
    discover_object_projection_paths,
    load_object_projection_module,
)


def test_discover_object_projection_paths_contains_known_modules() -> None:
    paths = discover_object_projection_paths()
    assert "mikrotik" in paths
    assert "proxmox" in paths
    assert all(path.name == "projections.py" for path in paths.values())


def test_discover_object_projection_paths_ignores_missing_projection_files(tmp_path: Path) -> None:
    (tmp_path / "mikrotik" / "plugins").mkdir(parents=True)
    (tmp_path / "mikrotik" / "plugins" / "projections.py").write_text("# ok\n", encoding="utf-8")
    (tmp_path / "cloud" / "plugins").mkdir(parents=True)
    (tmp_path / "cloud" / "plugins" / "helper.py").write_text("# helper\n", encoding="utf-8")

    paths = discover_object_projection_paths(object_modules_root=tmp_path)
    assert sorted(paths) == ["mikrotik"]


def test_discover_object_projection_paths_ignores_service_directories(tmp_path: Path) -> None:
    (tmp_path / "mikrotik" / "plugins").mkdir(parents=True)
    (tmp_path / "mikrotik" / "plugins" / "projections.py").write_text("# ok\n", encoding="utf-8")
    (tmp_path / "_shared" / "plugins").mkdir(parents=True)
    (tmp_path / "_shared" / "plugins" / "projections.py").write_text("# helper\n", encoding="utf-8")
    (tmp_path / "_internal" / "plugins").mkdir(parents=True)
    (tmp_path / "_internal" / "plugins" / "projections.py").write_text("# helper\n", encoding="utf-8")

    paths = discover_object_projection_paths(object_modules_root=tmp_path)

    assert sorted(paths) == ["mikrotik"]


def test_load_object_projection_module_unknown_id_lists_discovered_modules() -> None:
    try:
        load_object_projection_module("unknown-object")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown projection module id")

    paths = discover_object_projection_paths()
    assert "Unknown object projection module 'unknown-object'" in message
    for known_id in sorted(paths):
        assert known_id in message


def test_discover_object_projection_paths_uses_context_root(tmp_path: Path) -> None:
    (tmp_path / "custom" / "plugins").mkdir(parents=True)
    (tmp_path / "custom" / "plugins" / "projections.py").write_text("# ok\n", encoding="utf-8")
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={"object_modules_root": str(tmp_path)},
    )

    paths = discover_object_projection_paths(ctx=ctx)
    assert sorted(paths) == ["custom"]

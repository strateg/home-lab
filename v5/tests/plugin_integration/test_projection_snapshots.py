#!/usr/bin/env python3
"""Snapshot contract checks for generator projection helpers."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Callable

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from plugins.generators.object_projection_loader import (  # noqa: E402
    load_bootstrap_projection_module,
    load_object_projection_module,
)
from plugins.generators.projections import build_ansible_projection  # noqa: E402

_PROXMOX_PROJECTIONS = load_object_projection_module("proxmox")
_MIKROTIK_PROJECTIONS = load_object_projection_module("mikrotik")
_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()

build_proxmox_projection = _PROXMOX_PROJECTIONS.build_proxmox_projection
build_mikrotik_projection = _MIKROTIK_PROJECTIONS.build_mikrotik_projection
build_bootstrap_projection = _BOOTSTRAP_PROJECTIONS.build_bootstrap_projection

FixtureBuilder = Callable[[dict], dict]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_compiled_fixture() -> dict:
    root = Path(__file__).resolve().parents[1]
    return _load_json(root / "fixtures" / "projections" / "compiled_fixture.json")


def _mutate_order(compiled_json: dict) -> dict:
    mutated = deepcopy(compiled_json)
    instances = mutated.get("instances", {})
    for rows in instances.values():
        if isinstance(rows, list):
            rows.reverse()
    return mutated


@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("proxmox", build_proxmox_projection),
        ("mikrotik", build_mikrotik_projection),
        ("ansible", build_ansible_projection),
        ("bootstrap", build_bootstrap_projection),
    ],
)
def test_projection_matches_golden_snapshot(name: str, builder: FixtureBuilder) -> None:
    fixture = _load_compiled_fixture()
    actual = builder(fixture)
    golden_path = Path(__file__).resolve().parents[1] / "fixtures" / "projections" / f"{name}_projection.golden.json"
    expected = _load_json(golden_path)
    assert actual == expected


@pytest.mark.parametrize(
    "builder",
    [
        build_proxmox_projection,
        build_mikrotik_projection,
        build_ansible_projection,
        build_bootstrap_projection,
    ],
)
def test_projection_snapshot_is_stable_for_input_order(builder: FixtureBuilder) -> None:
    fixture = _load_compiled_fixture()
    reordered = _mutate_order(fixture)
    assert builder(fixture) == builder(reordered)

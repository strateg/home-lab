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
from plugins.generators.projections.ansible import build_ansible_projection  # noqa: E402

_PROXMOX_PROJECTIONS = load_object_projection_module("proxmox")
_MIKROTIK_PROJECTIONS = load_object_projection_module("mikrotik")

import importlib.util as _importlib_util

_CAPABILITY_FLAGS_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "topology"
    / "object-modules"
    / "mikrotik"
    / "plugins"
    / "compilers"
    / "capability_flags_compiler.py"
)
_capability_flags_spec = _importlib_util.spec_from_file_location(
    "test_projection_snapshots_capability_flags_compiler", _CAPABILITY_FLAGS_MODULE_PATH
)
_capability_flags_module = _importlib_util.module_from_spec(_capability_flags_spec)
_capability_flags_spec.loader.exec_module(_capability_flags_module)
# W07 migration order item 1: matches what the real compiler derives for zero
# routers (all keys present, all False) - not an empty dict, which the golden
# snapshot and templates do not treat the same way.
_EMPTY_CAPABILITY_FLAGS = _capability_flags_module._derive_capability_flags([])
_BOOTSTRAP_PROJECTIONS = load_bootstrap_projection_module()

build_proxmox_projection = _PROXMOX_PROJECTIONS.build_proxmox_projection
_raw_build_mikrotik_projection = _MIKROTIK_PROJECTIONS.build_mikrotik_projection


def build_mikrotik_projection(compiled_json: dict, **kwargs) -> dict:
    """The compiler's channels are required arguments; these fixtures state them empty.

    `base.compiler.security_matrix` owns zone membership and address-domain CIDRs,
    and the projection derives no substitute. Omitting the argument is an error;
    passing `{}` is a fixture saying it declares no matrices and no domains. A
    test that cares about zone or CIDR content passes a real mapping.

    `capability_flags` (W07 migration order item 1) is likewise required and
    defaulted empty the same way: these fixtures are not about capability-driven
    flag content.
    """
    kwargs.setdefault("composed_matrices_by_enforcer", {})
    kwargs.setdefault("vlan_cidr_map", {})
    kwargs.setdefault("capability_flags", _EMPTY_CAPABILITY_FLAGS)
    return _raw_build_mikrotik_projection(compiled_json, **kwargs)


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

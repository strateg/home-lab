#!/usr/bin/env python3
"""Parity test: inline wavefront algorithm vs compute_wavefronts (S5 gate).

PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07 S5 risk control: before
replacing the inline wavefront loop of `_execute_phase_parallel` with
`compute_wavefronts`, prove both implementations produce identical
wavefront grouping and intra-wavefront (order, plugin_id) tie-break
ordering (ADR 0063 §6) on dependency-graph fixtures.

The reference implementation below is a verbatim extraction of the
inline grouping logic from plugin_registry._execute_phase_parallel
as of commit fc798774 (pre-S5).
"""

from __future__ import annotations

import heapq
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel.scheduler.parallel_executor import compute_wavefronts  # noqa: E402


def _inline_reference_wavefronts(
    plugin_ids: list[str],
    specs: dict[str, SimpleNamespace],
    sort_key: Callable[[str], tuple[int, str]],
) -> list[list[str]]:
    """Inline wavefront grouping extracted from pre-S5 _execute_phase_parallel."""
    if not plugin_ids:
        return []

    plugin_set = set(plugin_ids)
    indegree: dict[str, int] = {plugin_id: 0 for plugin_id in plugin_ids}
    dependents: dict[str, list[str]] = {plugin_id: [] for plugin_id in plugin_ids}

    for plugin_id in plugin_ids:
        spec = specs.get(plugin_id)
        if spec is None:
            continue
        for dep_id in spec.depends_on:
            if dep_id not in plugin_set:
                continue
            indegree[plugin_id] += 1
            dependents[dep_id].append(plugin_id)

    ready: list[tuple[int, str]] = []
    for plugin_id in plugin_ids:
        if indegree[plugin_id] == 0:
            heapq.heappush(ready, sort_key(plugin_id))

    wavefronts: list[list[str]] = []
    while ready:
        wavefront: list[str] = []
        while ready:
            _, plugin_id = heapq.heappop(ready)
            wavefront.append(plugin_id)

        if not wavefront:
            break

        wavefronts.append(wavefront)
        # Pre-S5 inline code iterated sorted(wavefront, key=sort_key); the
        # wavefront is already heap-ordered, kept verbatim for fidelity.
        for plugin_id in sorted(wavefront, key=sort_key):
            for dependent_id in dependents[plugin_id]:
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    heapq.heappush(ready, sort_key(dependent_id))

    return wavefronts


def _graph(
    entries: dict[str, tuple[int, list[str]]],
) -> tuple[list[str], dict[str, SimpleNamespace], Callable[[str], tuple[int, str]]]:
    """Build (plugin_ids, specs, sort_key) from {id: (order, depends_on)}."""
    plugin_ids = list(entries)
    specs = {
        plugin_id: SimpleNamespace(depends_on=list(deps)) for plugin_id, (_, deps) in entries.items()
    }
    orders = {plugin_id: order for plugin_id, (order, _) in entries.items()}

    def sort_key(plugin_id: str) -> tuple[int, str]:
        return (orders[plugin_id], plugin_id)

    return plugin_ids, specs, sort_key


GRAPH_FIXTURES: dict[str, dict[str, tuple[int, list[str]]]] = {
    "empty": {},
    "single": {"a": (100, [])},
    "independent_tie_break_on_id": {
        "z": (100, []),
        "b": (100, []),
        "a": (100, []),
    },
    "independent_tie_break_on_order": {
        "a": (300, []),
        "b": (100, []),
        "c": (200, []),
    },
    "chain": {
        "a": (100, []),
        "b": (100, ["a"]),
        "c": (100, ["b"]),
    },
    "diamond_order_vs_dependency": {
        # join has the lowest order but must wait for both branches
        "join": (91, ["left", "right"]),
        "right": (93, ["base"]),
        "left": (92, ["base"]),
        "base": (188, []),
    },
    "two_components_with_ties": {
        "x1": (100, []),
        "x2": (100, ["x1"]),
        "y1": (100, []),
        "y2": (100, ["y1"]),
        "y3": (50, ["y1", "x1"]),
    },
    "external_dependencies_ignored": {
        "a": (100, ["outside.the.set"]),
        "b": (100, ["a", "another.outsider"]),
    },
    "wide_fan_in_fan_out": {
        "root": (100, []),
        "m1": (103, ["root"]),
        "m2": (102, ["root"]),
        "m3": (101, ["root"]),
        "sink": (100, ["m1", "m2", "m3"]),
        "late": (999, []),
    },
}


@pytest.mark.parametrize("fixture_name", sorted(GRAPH_FIXTURES))
def test_wavefront_parity_on_fixture(fixture_name: str) -> None:
    plugin_ids, specs, sort_key = _graph(GRAPH_FIXTURES[fixture_name])

    inline = _inline_reference_wavefronts(plugin_ids, specs, sort_key)
    extracted = compute_wavefronts(plugin_ids, specs, sort_key)

    assert extracted == inline


def test_wavefront_parity_with_missing_spec() -> None:
    plugin_ids, specs, sort_key = _graph(
        {
            "a": (100, []),
            "ghost": (100, []),
            "b": (100, ["a", "ghost"]),
        }
    )
    del specs["ghost"]  # specs.get() returns None: no edges contributed

    inline = _inline_reference_wavefronts(plugin_ids, specs, sort_key)
    extracted = compute_wavefronts(plugin_ids, specs, sort_key)

    assert extracted == inline
    # ghost still participates as a node with indegree 0
    assert "ghost" in extracted[0]


def test_wavefront_parity_on_seeded_random_dags() -> None:
    """Property check on random DAGs with heavy order ties (tie-break stress)."""
    rng = random.Random(20260712)

    for _ in range(200):
        node_count = rng.randint(1, 24)
        plugin_ids = [f"p{i:02d}" for i in range(node_count)]
        rng.shuffle(plugin_ids)

        entries: dict[str, tuple[int, list[str]]] = {}
        for index, plugin_id in enumerate(plugin_ids):
            # Few distinct order values => many ties broken by plugin_id
            order = rng.choice([50, 100, 100, 100, 200])
            # Edges only from earlier shuffled positions => acyclic
            candidates = plugin_ids[:index]
            deps = rng.sample(candidates, k=rng.randint(0, min(3, len(candidates))))
            if rng.random() < 0.1:
                deps.append("external.dep.not.in.set")
            entries[plugin_id] = (order, deps)

        ids, specs, sort_key = _graph(entries)
        inline = _inline_reference_wavefronts(ids, specs, sort_key)
        extracted = compute_wavefronts(ids, specs, sort_key)

        assert extracted == inline
        assert sorted(pid for wave in extracted for pid in wave) == sorted(ids)

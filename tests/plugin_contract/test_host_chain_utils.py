#!/usr/bin/env python3
"""Unit tests for host_chain_utils module (ADR 0107 D11)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from host_chain_utils import (  # noqa: E402
    build_host_ref_graph,
    detect_cycle,
    extract_host_ref,
    get_host_at_level,
    get_root_host,
    topological_sort_hosts,
    traverse_host_chain,
)


class TestExtractHostRef:
    """Tests for extract_host_ref function."""

    def test_extracts_host_ref_from_top_level(self) -> None:
        row = {"host_ref": "srv-gamayun", "other": "data"}
        assert extract_host_ref(row) == "srv-gamayun"

    def test_extracts_host_ref_from_extensions(self) -> None:
        row = {"extensions": {"host_ref": "srv-gamayun"}, "other": "data"}
        assert extract_host_ref(row) == "srv-gamayun"

    def test_prefers_extensions_over_top_level(self) -> None:
        row = {"host_ref": "top-level", "extensions": {"host_ref": "from-extensions"}}
        assert extract_host_ref(row) == "from-extensions"

    def test_extracts_device_ref_as_alias(self) -> None:
        row = {"device_ref": "srv-gamayun"}
        assert extract_host_ref(row) == "srv-gamayun"

    def test_returns_none_when_missing(self) -> None:
        row = {"other": "data"}
        assert extract_host_ref(row) is None

    def test_returns_none_for_empty_string(self) -> None:
        row = {"host_ref": ""}
        assert extract_host_ref(row) is None

    def test_returns_none_for_non_string(self) -> None:
        row = {"host_ref": 123}
        assert extract_host_ref(row) is None


class TestDetectCycle:
    """Tests for detect_cycle function."""

    def test_detects_simple_cycle(self) -> None:
        graph = {"a": "b", "b": "a"}
        cycle = detect_cycle(graph, "a")
        assert cycle is not None
        assert set(cycle) == {"a", "b"}

    def test_detects_longer_cycle(self) -> None:
        graph = {"a": "b", "b": "c", "c": "a"}
        cycle = detect_cycle(graph, "a")
        assert cycle is not None
        assert "a" in cycle

    def test_no_cycle_in_dag(self) -> None:
        graph = {"a": "b", "b": "c", "c": None}
        assert detect_cycle(graph, "a") is None

    def test_no_cycle_when_chain_ends(self) -> None:
        graph = {"a": "b", "b": "c"}
        # c is not in graph, so chain ends
        assert detect_cycle(graph, "a") is None


class TestTraverseHostChain:
    """Tests for traverse_host_chain function."""

    def test_traverses_simple_chain(self) -> None:
        lookup = {
            "docker-app": {"host_ref": "lxc-docker"},
            "lxc-docker": {"host_ref": "srv-gamayun"},
            "srv-gamayun": {},
        }
        chain = traverse_host_chain("docker-app", lookup)
        assert chain == ["lxc-docker", "srv-gamayun"]

    def test_empty_chain_for_root(self) -> None:
        lookup = {"srv-gamayun": {}}
        chain = traverse_host_chain("srv-gamayun", lookup)
        assert chain == []

    def test_handles_missing_instance(self) -> None:
        lookup = {}
        chain = traverse_host_chain("nonexistent", lookup)
        assert chain == []

    def test_respects_max_depth(self) -> None:
        # Create a very long chain
        lookup = {
            "a": {"host_ref": "b"},
            "b": {"host_ref": "c"},
            "c": {"host_ref": "d"},
            "d": {"host_ref": "e"},
            "e": {},
        }
        chain = traverse_host_chain("a", lookup, max_depth=2)
        assert len(chain) <= 2


class TestGetHostAtLevel:
    """Tests for get_host_at_level function."""

    def test_level_1_returns_immediate_host(self) -> None:
        lookup = {
            "docker-app": {"host_ref": "lxc-docker"},
            "lxc-docker": {"host_ref": "srv-gamayun"},
            "srv-gamayun": {},
        }
        assert get_host_at_level("docker-app", lookup, 1) == "lxc-docker"

    def test_level_2_returns_parent_host(self) -> None:
        lookup = {
            "docker-app": {"host_ref": "lxc-docker"},
            "lxc-docker": {"host_ref": "srv-gamayun"},
            "srv-gamayun": {},
        }
        assert get_host_at_level("docker-app", lookup, 2) == "srv-gamayun"

    def test_level_0_returns_none(self) -> None:
        lookup = {"docker-app": {"host_ref": "lxc-docker"}}
        assert get_host_at_level("docker-app", lookup, 0) is None

    def test_exceeding_depth_returns_none(self) -> None:
        lookup = {"a": {"host_ref": "b"}, "b": {}}
        assert get_host_at_level("a", lookup, 3) is None


class TestGetRootHost:
    """Tests for get_root_host function."""

    def test_returns_physical_device(self) -> None:
        lookup = {
            "docker-app": {"host_ref": "lxc-docker"},
            "lxc-docker": {"host_ref": "srv-gamayun"},
            "srv-gamayun": {},
        }
        assert get_root_host("docker-app", lookup) == "srv-gamayun"

    def test_returns_none_for_root_device(self) -> None:
        lookup = {"srv-gamayun": {}}
        assert get_root_host("srv-gamayun", lookup) is None


class TestBuildHostRefGraph:
    """Tests for build_host_ref_graph function."""

    def test_builds_graph_from_lookup(self) -> None:
        lookup = {
            "a": {"host_ref": "b"},
            "b": {"host_ref": "c"},
            "c": {},
        }
        graph = build_host_ref_graph(lookup)
        assert graph == {"a": "b", "b": "c", "c": None}

    def test_applies_filter_function(self) -> None:
        lookup = {
            "workload-a": {"host_ref": "srv", "layer": "L4"},
            "srv": {"layer": "L1"},
        }
        # Only include L4 layers
        graph = build_host_ref_graph(
            lookup,
            filter_fn=lambda _id, data: data.get("layer") == "L4",
        )
        assert "workload-a" in graph
        assert "srv" not in graph


class TestTopologicalSortHosts:
    """Tests for topological_sort_hosts function."""

    def test_sorts_leaf_to_root(self) -> None:
        lookup = {
            "docker-app": {"host_ref": "lxc-docker", "workload_defaults": {}},
            "lxc-docker": {"host_ref": "srv-gamayun", "workload_defaults": {}},
            "srv-gamayun": {"workload_defaults": {}},
        }
        hosts_with_defaults = {"docker-app", "lxc-docker", "srv-gamayun"}
        sorted_hosts, cycles = topological_sort_hosts(lookup, hosts_with_defaults)

        assert len(cycles) == 0
        # srv-gamayun should come before lxc-docker which should come before docker-app
        assert sorted_hosts.index("srv-gamayun") < sorted_hosts.index("lxc-docker")
        assert sorted_hosts.index("lxc-docker") < sorted_hosts.index("docker-app")

    def test_detects_cycles(self) -> None:
        lookup = {
            "a": {"host_ref": "b", "workload_defaults": {}},
            "b": {"host_ref": "a", "workload_defaults": {}},
        }
        hosts_with_defaults = {"a", "b"}
        sorted_hosts, cycles = topological_sort_hosts(lookup, hosts_with_defaults)

        assert len(cycles) > 0

    def test_handles_independent_hosts(self) -> None:
        lookup = {
            "host1": {"workload_defaults": {}},
            "host2": {"workload_defaults": {}},
        }
        hosts_with_defaults = {"host1", "host2"}
        sorted_hosts, cycles = topological_sort_hosts(lookup, hosts_with_defaults)

        assert len(cycles) == 0
        assert set(sorted_hosts) == {"host1", "host2"}

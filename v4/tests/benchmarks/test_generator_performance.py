"""Benchmark tests for generators (Phase 6).

Performance benchmarks to track generator performance over time.
"""

from pathlib import Path

import pytest
from scripts.generators.common import PerformanceProfiler


def _minimal_topology():
    """Minimal topology for benchmarks."""
    return {
        "L0_meta": {"version": "4.0.0"},
        "L1_foundation": {
            "devices": [{"id": f"dev-{i}", "type": "server", "name": f"Server {i}"} for i in range(10)],
            "locations": [{"id": "loc-1", "name": "Location 1"}],
        },
        "L2_network": {
            "networks": [{"id": f"net-{i}", "name": f"Network {i}", "cidr": f"10.0.{i}.0/24"} for i in range(5)]
        },
        "L3_data": {},
        "L4_platform": {},
        "L5_application": {},
    }


@pytest.mark.benchmark
class TestGeneratorPerformance:
    """Performance benchmarks for generators."""

    def test_topology_loading_performance(self, benchmark, tmp_path):
        """Benchmark topology loading."""
        import yaml
        from scripts.generators.common import load_topology_cached

        topology = _minimal_topology()
        topology_file = tmp_path / "topology.yaml"
        topology_file.write_text(yaml.dump(topology), encoding="utf-8")

        def load():
            return load_topology_cached(topology_file)

        result = benchmark(load)
        assert result is not None

    def test_ip_resolver_v2_performance(self, benchmark):
        """Benchmark IpResolverV2 creation and resolution."""
        from scripts.generators.common import IpRef, IpResolverV2

        topology = _minimal_topology()
        topology["L4_platform"]["lxc"] = [
            {"id": f"lxc-{i}", "networks": [{"network_ref": "net-0", "ip": f"10.0.0.{i+10}"}]} for i in range(20)
        ]

        def resolve():
            resolver = IpResolverV2(topology)
            ref = IpRef(lxc_ref="lxc-5", network_ref="net-0")
            return resolver.resolve(ref)

        result = benchmark(resolve)
        assert result is not None

    def test_icon_manager_loading_performance(self, benchmark):
        """Benchmark IconManager pack loading."""
        from scripts.generators.docs.icons import IconManager

        def load_packs():
            manager = IconManager(icon_mode="icon-nodes")
            manager.scan_packs()
            return manager

        result = benchmark(load_packs)
        assert result is not None

    def test_template_rendering_performance(self, benchmark, tmp_path):
        """Benchmark template rendering."""
        from jinja2 import DictLoader, Environment

        template_str = """
        {% for device in devices %}
        Device: {{ device.name }}
        {% endfor %}
        """

        env = Environment(loader=DictLoader({"test.j2": template_str}))
        template = env.get_template("test.j2")

        context = {"devices": [{"name": f"Device {i}"} for i in range(100)]}

        def render():
            return template.render(**context)

        result = benchmark(render)
        assert len(result) > 0


@pytest.mark.benchmark
class TestProfilerOverhead:
    """Test profiler overhead."""

    def test_profiler_enabled_overhead(self, benchmark):
        """Measure profiler overhead when enabled."""
        profiler = PerformanceProfiler(enabled=True)

        def operation_with_profiler():
            with profiler.measure("test_op"):
                sum(range(1000))

        benchmark(operation_with_profiler)

    def test_profiler_disabled_overhead(self, benchmark):
        """Measure profiler overhead when disabled."""
        profiler = PerformanceProfiler(enabled=False)

        def operation_without_profiler():
            with profiler.measure("test_op"):
                sum(range(1000))

        benchmark(operation_without_profiler)


@pytest.mark.benchmark
class TestDataResolverPerformance:
    """Benchmark DataResolver operations."""

    def test_storage_pool_resolution(self, benchmark):
        """Benchmark storage pool resolution."""
        from scripts.generators.docs.data import DataResolver

        topology = _minimal_topology()
        topology["L3_data"]["storage_endpoints"] = [
            {
                "id": f"storage-{i}",
                "platform": "proxmox",
                "name": f"Storage {i}",
            }
            for i in range(20)
        ]

        def resolve():
            resolver = DataResolver(topology)
            return resolver.resolve_storage_pools_for_docs()

        result = benchmark(resolve)
        assert len(result) > 0

    def test_network_resolution(self, benchmark):
        """Benchmark network resolution with profiles."""
        from scripts.generators.docs.data import DataResolver

        topology = _minimal_topology()
        topology["L2_network"]["network_profiles"] = {"profile-1": {"mtu": 1500, "vlan": 10}}
        topology["L2_network"]["networks"] = [
            {
                "id": f"net-{i}",
                "name": f"Network {i}",
                "cidr": f"10.0.{i}.0/24",
                "profile_ref": "profile-1",
            }
            for i in range(50)
        ]

        def resolve():
            resolver = DataResolver(topology)
            return resolver.get_resolved_networks()

        result = benchmark(resolve)
        assert len(result) > 0

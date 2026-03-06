"""Unit tests for Phase 4 improvements."""

import pytest

from scripts.generators.common import GeneratorConfig, GeneratorContext, IpRef, IpResolverV2, ResolvedIp


class TestIpRef:
    """Test IpRef dataclass."""

    def test_lxc_ref_creation(self):
        """Test creating IpRef for LXC."""
        ref = IpRef(lxc_ref="lxc-1", network_ref="net-mgmt")
        assert ref.lxc_ref == "lxc-1"
        assert ref.network_ref == "net-mgmt"
        assert ref.target_type == "lxc"

    def test_vm_ref_creation(self):
        """Test creating IpRef for VM."""
        ref = IpRef(vm_ref="vm-1", network_ref="net-mgmt")
        assert ref.vm_ref == "vm-1"
        assert ref.target_type == "vm"

    def test_requires_exactly_one_target(self):
        """Test validation that exactly one target is required."""
        with pytest.raises(ValueError, match="exactly one target ref"):
            IpRef(network_ref="net-mgmt")  # No target

        with pytest.raises(ValueError, match="exactly one target ref"):
            IpRef(lxc_ref="lxc-1", vm_ref="vm-1", network_ref="net-mgmt")  # Two targets

    def test_from_dict(self):
        """Test creating IpRef from dictionary."""
        data = {"lxc_ref": "lxc-1", "network_ref": "net-mgmt"}
        ref = IpRef.from_dict(data)
        assert ref.lxc_ref == "lxc-1"
        assert ref.network_ref == "net-mgmt"

    def test_frozen(self):
        """Test that IpRef is immutable."""
        ref = IpRef(lxc_ref="lxc-1", network_ref="net-mgmt")
        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.10+
            ref.lxc_ref = "lxc-2"


class TestResolvedIp:
    """Test ResolvedIp dataclass."""

    def test_resolved_ip_creation(self):
        """Test creating ResolvedIp."""
        resolved = ResolvedIp(
            ip="192.168.1.10",
            source_type="lxc",
            source_id="lxc-1",
            network_ref="net-mgmt",
        )
        assert resolved.ip == "192.168.1.10"
        assert resolved.source_type == "lxc"
        assert resolved.ip_without_cidr == "192.168.1.10"

    def test_ip_without_cidr_strips_notation(self):
        """Test that CIDR notation is stripped."""
        resolved = ResolvedIp(
            ip="192.168.1.10/24",
            source_type="lxc",
            source_id="lxc-1",
            network_ref="net-mgmt",
        )
        assert resolved.ip_without_cidr == "192.168.1.10"


class TestIpResolverV2:
    """Test modern IP resolver."""

    def _minimal_topology(self):
        return {
            "L2_network": {
                "networks": [
                    {
                        "id": "net-mgmt",
                        "ip_allocations": [
                            {"host_os_ref": "hos-1", "ip": "192.168.1.10/24"},
                        ],
                    }
                ]
            },
            "L4_platform": {
                "lxc": [
                    {
                        "id": "lxc-1",
                        "networks": [
                            {"network_ref": "net-mgmt", "ip": "192.168.1.20/24"},
                        ],
                    }
                ],
                "vms": [
                    {
                        "id": "vm-1",
                        "networks": [
                            {"network_ref": "net-mgmt", "ip_config": {"address": "192.168.1.30/24"}},
                        ],
                    }
                ],
            },
            "L5_application": {"services": []},
        }

    def test_resolve_lxc_ip(self):
        """Test resolving LXC IP."""
        topology = self._minimal_topology()
        resolver = IpResolverV2(topology)

        ref = IpRef(lxc_ref="lxc-1", network_ref="net-mgmt")
        resolved = resolver.resolve(ref)

        assert resolved is not None
        assert resolved.ip == "192.168.1.20"
        assert resolved.source_type == "lxc"
        assert resolved.source_id == "lxc-1"

    def test_resolve_vm_ip(self):
        """Test resolving VM IP."""
        topology = self._minimal_topology()
        resolver = IpResolverV2(topology)

        ref = IpRef(vm_ref="vm-1", network_ref="net-mgmt")
        resolved = resolver.resolve(ref)

        assert resolved is not None
        assert resolved.ip == "192.168.1.30"
        assert resolved.source_type == "vm"

    def test_resolve_host_os_ip(self):
        """Test resolving host OS IP."""
        topology = self._minimal_topology()
        resolver = IpResolverV2(topology)

        ref = IpRef(host_os_ref="hos-1", network_ref="net-mgmt")
        resolved = resolver.resolve(ref)

        assert resolved is not None
        assert resolved.ip == "192.168.1.10"
        assert resolved.source_type == "host_os"

    def test_resolve_nonexistent_ref(self):
        """Test resolving nonexistent reference returns None."""
        topology = self._minimal_topology()
        resolver = IpResolverV2(topology)

        ref = IpRef(lxc_ref="nonexistent", network_ref="net-mgmt")
        resolved = resolver.resolve(ref)

        assert resolved is None

    def test_resolve_dict_backward_compat(self):
        """Test backward compatibility with dict input."""
        topology = self._minimal_topology()
        resolver = IpResolverV2(topology)

        resolved = resolver.resolve_dict({"lxc_ref": "lxc-1", "network_ref": "net-mgmt"})

        assert resolved is not None
        assert resolved.ip == "192.168.1.20"


class TestGeneratorContext:
    """Test GeneratorContext."""

    def test_context_lazy_loads_topology(self, tmp_path):
        """Test that topology is lazily loaded."""
        from pathlib import Path

        # Create minimal config
        config = GeneratorConfig(
            topology_path=Path("topology.yaml"),
            output_dir=tmp_path,
            templates_dir=Path("templates"),
        )

        context = GeneratorContext(config=config)

        # Topology not loaded yet
        assert context._topology is None

        # Access triggers load (will fail if file doesn't exist, but that's expected)

    def test_should_generate_all_by_default(self, tmp_path):
        """Test that all components generated by default."""
        from pathlib import Path

        config = GeneratorConfig(
            topology_path=Path("topology.yaml"),
            output_dir=tmp_path,
            templates_dir=Path("templates"),
        )
        context = GeneratorContext(config=config)

        assert context.should_generate("any-component") is True

    def test_should_generate_selective(self, tmp_path):
        """Test selective component generation."""
        from pathlib import Path

        config = GeneratorConfig(
            topology_path=Path("topology.yaml"),
            output_dir=tmp_path,
            templates_dir=Path("templates"),
            components=["bridges", "vms"],
        )
        context = GeneratorContext(config=config)

        assert context.should_generate("bridges") is True
        assert context.should_generate("vms") is True
        assert context.should_generate("lxc") is False

    def test_logging_respects_verbose(self, tmp_path, capsys):
        """Test that verbose logging respects config."""
        from pathlib import Path

        config = GeneratorConfig(
            topology_path=Path("topology.yaml"),
            output_dir=tmp_path,
            templates_dir=Path("templates"),
            verbose=False,
        )
        context = GeneratorContext(config=config)

        context.log_verbose("This should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""

        context.log_info("This should appear")
        captured = capsys.readouterr()
        assert "This should appear" in captured.out

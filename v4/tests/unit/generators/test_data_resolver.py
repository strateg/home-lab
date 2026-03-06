"""Unit tests for docs.data.DataResolver module."""

from typing import Any, Dict

import pytest

from scripts.generators.docs.data import DataResolver


class TestDataResolver:
    """Test DataResolver class."""

    def test_initialization(self, sample_topology_minimal):
        """Test DataResolver initialization."""
        resolver = DataResolver(sample_topology_minimal)

        assert resolver.topology == sample_topology_minimal

    def test_get_resolved_networks_empty(self):
        """Test network resolution with no networks."""
        topology = {
            "L2_network": {
                "networks": [],
            }
        }
        resolver = DataResolver(topology)

        networks = resolver.get_resolved_networks()

        assert networks == []

    def test_get_resolved_networks_with_profiles(self):
        """Test network resolution with profiles."""
        topology = {
            "L2_network": {
                "network_profiles": {
                    "standard": {
                        "vlan": 10,
                        "mtu": 1500,
                    }
                },
                "networks": [
                    {
                        "id": "net-1",
                        "name": "Network 1",
                        "profile_ref": "standard",
                        "cidr": "192.168.1.0/24",
                    }
                ],
            }
        }
        resolver = DataResolver(topology)

        networks = resolver.get_resolved_networks()

        assert len(networks) == 1
        assert networks[0]["id"] == "net-1"
        assert networks[0]["vlan"] == 10  # From profile
        assert networks[0]["mtu"] == 1500  # From profile
        assert networks[0]["cidr"] == "192.168.1.0/24"  # Direct

    def test_build_l1_storage_views_empty(self):
        """Test storage views with no devices."""
        topology = {
            "L1_foundation": {
                "devices": [],
                "media_registry": [],
                "media_attachments": [],
            }
        }
        resolver = DataResolver(topology)

        views = resolver.build_l1_storage_views()

        assert isinstance(views, dict)
        assert "rows_by_device" in views
        assert "media_by_id" in views
        assert len(views["rows_by_device"]) == 0

    def test_build_l1_storage_views_with_device(self):
        """Test storage views with device and empty slot."""
        topology = {
            "L1_foundation": {
                "devices": [
                    {
                        "id": "device-1",
                        "specs": {
                            "storage_slots": [
                                {
                                    "id": "slot-1",
                                    "bus": "sata",
                                    "mount": "soldered",
                                    "name": "M.2 Slot 1",
                                }
                            ]
                        },
                    }
                ],
                "media_registry": [],
                "media_attachments": [],
            }
        }
        resolver = DataResolver(topology)

        views = resolver.build_l1_storage_views()

        assert "device-1" in views["rows_by_device"]
        rows = views["rows_by_device"]["device-1"]
        assert len(rows) == 1
        assert rows[0]["slot_id"] == "slot-1"
        assert rows[0]["attachment_state"] == "empty"
        assert rows[0]["media"] is None

    def test_resolve_storage_pools_legacy(self):
        """Test storage pool resolution with legacy storage."""
        topology = {
            "L1_foundation": {},
            "L3_data": {"storage": [{"id": "pool-1", "type": "local", "device_ref": "device-1"}]},
        }
        resolver = DataResolver(topology)

        pools = resolver.resolve_storage_pools_for_docs()

        assert len(pools) == 1
        assert pools[0]["id"] == "pool-1"

    def test_resolve_storage_pools_empty(self):
        """Test storage pool resolution with no storage."""
        topology = {"L1_foundation": {}, "L3_data": {}}
        resolver = DataResolver(topology)

        pools = resolver.resolve_storage_pools_for_docs()

        assert pools == []

    def test_resolve_data_assets_empty(self):
        """Test data asset resolution with no assets."""
        topology = {
            "L3_data": {"data_assets": []},
            "L4_platform": {},
            "L5_application": {},
        }
        resolver = DataResolver(topology)

        assets = resolver.resolve_data_assets_for_docs()

        assert assets == []

    def test_resolve_data_assets_basic(self):
        """Test data asset resolution with basic asset."""
        topology = {
            "L3_data": {"data_assets": [{"id": "asset-1", "name": "Data Asset 1"}]},
            "L4_platform": {},
            "L5_application": {},
        }
        resolver = DataResolver(topology)

        assets = resolver.resolve_data_assets_for_docs()

        assert len(assets) == 1
        assert assets[0]["asset"]["id"] == "asset-1"
        assert "storage_endpoint_refs" in assets[0]
        assert "runtime_refs" in assets[0]

    def test_apply_service_runtime_compat_fields_no_services(self):
        """Test compatibility enrichment with no services."""
        topology = {
            "L2_network": {},
            "L4_platform": {},
            "L5_application": {"services": []},
        }
        resolver = DataResolver(topology)

        # Should not raise an error
        resolver.apply_service_runtime_compat_fields()

        assert topology["L5_application"]["services"] == []

    def test_apply_service_runtime_compat_fields_lxc(self):
        """Test compatibility enrichment for LXC service."""
        topology = {
            "L2_network": {},
            "L4_platform": {"lxc": [{"id": "lxc-1", "device_ref": "device-1", "networks": [{"network_ref": "net-1"}]}]},
            "L5_application": {
                "services": [
                    {
                        "id": "service-1",
                        "runtime": {
                            "type": "lxc",
                            "target_ref": "lxc-1",
                        },
                    }
                ]
            },
        }
        resolver = DataResolver(topology)

        resolver.apply_service_runtime_compat_fields()

        services = topology["L5_application"]["services"]
        assert services[0]["lxc_ref"] == "lxc-1"
        assert services[0]["device_ref"] == "device-1"
        assert services[0]["network_ref"] == "net-1"


class TestDataResolverIntegration:
    """Integration tests for DataResolver."""

    def test_full_workflow_with_minimal_topology(self, sample_topology_minimal):
        """Test complete workflow with minimal topology."""
        resolver = DataResolver(sample_topology_minimal)

        # Should not raise errors
        networks = resolver.get_resolved_networks()
        views = resolver.build_l1_storage_views()
        pools = resolver.resolve_storage_pools_for_docs()
        assets = resolver.resolve_data_assets_for_docs()
        resolver.apply_service_runtime_compat_fields()

        assert isinstance(networks, list)
        assert isinstance(views, dict)
        assert isinstance(pools, list)
        assert isinstance(assets, list)

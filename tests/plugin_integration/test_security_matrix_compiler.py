#!/usr/bin/env python3
"""Integration tests for security matrix compiler plugin (ADR 0110)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginStatus
from kernel.plugin_base import Stage
from plugins.compilers import security_matrix_compiler as sm_module

from tests.helpers.plugin_execution import publish_for_test, run_plugin_for_test

PLUGIN_ID = "base.compiler.security_matrix"


def _create_plugin():
    return sm_module.SecurityMatrixCompiler(PLUGIN_ID)


def _create_ctx(
    *,
    rows: list | None = None,
    objects: dict | None = None,
) -> PluginContext:
    """Create a PluginContext with normalized_rows pre-published."""
    ctx = PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        config={},
        objects=objects or {},
        instance_bindings={"instance_bindings": {}},
    )
    if rows is not None:
        publish_for_test(
            ctx,
            "base.compiler.instance_rows",
            "normalized_rows",
            rows,
        )
    return ctx


# =============================================================================
# R1-R6 Matrix Calculation Tests
# =============================================================================


class TestMatrixCalculation:
    """Tests for _calculate_matrix R1-R6 rules."""

    def test_r1_same_zone_allows(self):
        """R1: Traffic within same zone is allowed."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.user": {
                "name": "user",
                "security_level": 3,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            }
        }

        matrix = plugin._calculate_matrix(zones, [], "perimeter")

        cell = matrix["inst.trust_zone.user"]["inst.trust_zone.user"]
        assert cell["action"] == "allow"
        assert cell["rule"] == "R1"
        assert "same zone" in cell["reason"]

    def test_r1b_internal_plane_same_zone_denies(self):
        """R1b: Internal plane requires explicit override for same zone."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.servers": {
                "name": "servers",
                "security_level": 4,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            }
        }

        matrix = plugin._calculate_matrix(zones, [], "internal")

        cell = matrix["inst.trust_zone.servers"]["inst.trust_zone.servers"]
        assert cell["action"] == "deny"
        assert cell["rule"] == "R1b"

    def test_r2_isolated_zone_denies_internal(self):
        """R2: Isolated zone cannot reach non-untrusted zones."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.guest": {
                "name": "guest",
                "security_level": 0,
                "isolated": True,
                "vlans": [],
                "cidrs": [],
            },
            "inst.trust_zone.user": {
                "name": "user",
                "security_level": 3,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
        }

        matrix = plugin._calculate_matrix(zones, [], "perimeter")

        cell = matrix["inst.trust_zone.guest"]["inst.trust_zone.user"]
        assert cell["action"] == "deny"
        assert cell["rule"] == "R2"
        assert "isolated zone cannot reach" in cell["reason"]
        assert cell["log"] is True

    def test_r2_isolated_zone_allows_untrusted(self):
        """R2: Isolated zone CAN reach untrusted (internet)."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.guest": {
                "name": "guest",
                "security_level": 0,
                "isolated": True,
                "vlans": [],
                "cidrs": [],
            },
            "inst.trust_zone.untrusted": {
                "name": "untrusted zone",
                "security_level": 0,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
        }

        matrix = plugin._calculate_matrix(zones, [], "perimeter")

        cell = matrix["inst.trust_zone.guest"]["inst.trust_zone.untrusted"]
        assert cell["action"] == "allow"
        assert cell["rule"] == "R2"
        assert "can reach untrusted" in cell["reason"]

    def test_r3_downhill_allows(self):
        """R3: Higher security level can reach lower (downhill)."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.management": {
                "name": "management",
                "security_level": 5,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
            "inst.trust_zone.user": {
                "name": "user",
                "security_level": 3,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
        }

        matrix = plugin._calculate_matrix(zones, [], "perimeter")

        cell = matrix["inst.trust_zone.management"]["inst.trust_zone.user"]
        assert cell["action"] == "allow"
        assert cell["rule"] == "R3"
        assert "downhill" in cell["reason"]
        assert "5" in cell["reason"] and "3" in cell["reason"]

    def test_r4_uphill_denies(self):
        """R4: Lower security level cannot reach higher (uphill)."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.user": {
                "name": "user",
                "security_level": 3,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
            "inst.trust_zone.management": {
                "name": "management",
                "security_level": 5,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
        }

        matrix = plugin._calculate_matrix(zones, [], "perimeter")

        cell = matrix["inst.trust_zone.user"]["inst.trust_zone.management"]
        assert cell["action"] == "deny"
        assert cell["rule"] == "R4"
        assert "uphill" in cell["reason"]
        assert cell["log"] is True

    def test_r5_same_level_denies(self):
        """R5: Same security level without override is denied."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.guest": {
                "name": "guest",
                "security_level": 0,
                "isolated": False,  # Not isolated for this test
                "vlans": [],
                "cidrs": [],
            },
            "inst.trust_zone.untrusted": {
                "name": "untrusted",
                "security_level": 0,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
        }

        matrix = plugin._calculate_matrix(zones, [], "perimeter")

        cell = matrix["inst.trust_zone.guest"]["inst.trust_zone.untrusted"]
        assert cell["action"] == "deny"
        assert cell["rule"] == "R5"
        assert "same level" in cell["reason"]

    def test_r6_policy_override_takes_precedence(self):
        """R6: Explicit policy_override is checked first."""
        plugin = _create_plugin()
        zones = {
            "inst.trust_zone.user": {
                "name": "user",
                "security_level": 3,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
            "inst.trust_zone.servers": {
                "name": "servers",
                "security_level": 4,
                "isolated": False,
                "vlans": [],
                "cidrs": [],
            },
        }
        policy_overrides = [
            {
                "name": "user-to-servers-db",
                "from_zone_ref": "inst.trust_zone.user",
                "to_zone_ref": "inst.trust_zone.servers",
                "action": "allow",
                "ports": [5432, 6379],
                "log": False,
            }
        ]

        matrix = plugin._calculate_matrix(zones, policy_overrides, "perimeter")

        # Without override, user→servers would be R4 DENY (uphill)
        cell = matrix["inst.trust_zone.user"]["inst.trust_zone.servers"]
        assert cell["action"] == "allow"
        assert cell["rule"] == "R6"
        assert "policy_override" in cell["reason"]
        assert cell["ports"] == [5432, 6379]


class TestPolicyOverrideMatching:
    """Tests for _find_policy_override."""

    def test_exact_ref_match(self):
        """Exact zone ref matching."""
        plugin = _create_plugin()
        overrides = [
            {
                "from_zone_ref": "inst.trust_zone.user",
                "to_zone_ref": "inst.trust_zone.servers",
                "action": "allow",
            }
        ]

        result = plugin._find_policy_override(
            "inst.trust_zone.user",
            "inst.trust_zone.servers",
            overrides,
        )

        assert result is not None
        assert result["action"] == "allow"

    def test_suffix_match(self):
        """Suffix-based matching for obj vs inst refs."""
        plugin = _create_plugin()
        overrides = [
            {
                "from_zone_ref": "obj.network.trust_zone.user",
                "to_zone_ref": "obj.network.trust_zone.servers",
                "action": "allow",
            }
        ]

        result = plugin._find_policy_override(
            "inst.trust_zone.user",
            "inst.trust_zone.servers",
            overrides,
        )

        assert result is not None
        assert result["action"] == "allow"

    def test_no_match_returns_none(self):
        """No matching override returns None."""
        plugin = _create_plugin()
        overrides = [
            {
                "from_zone_ref": "inst.trust_zone.guest",
                "to_zone_ref": "inst.trust_zone.servers",
                "action": "deny",
            }
        ]

        result = plugin._find_policy_override(
            "inst.trust_zone.user",
            "inst.trust_zone.servers",
            overrides,
        )

        assert result is None


class TestStatistics:
    """Tests for _compute_statistics."""

    def test_counts_allow_deny(self):
        """Statistics correctly count allow/deny actions."""
        plugin = _create_plugin()
        matrix = {
            "zone_a": {
                "zone_a": {"action": "allow"},
                "zone_b": {"action": "deny"},
                "zone_c": {"action": "allow"},
            },
            "zone_b": {
                "zone_a": {"action": "deny"},
                "zone_b": {"action": "allow"},
                "zone_c": {"action": "deny"},
            },
        }
        overrides = [{"name": "test1"}, {"name": "test2"}]

        stats = plugin._compute_statistics(matrix, overrides)

        assert stats["total_pairs"] == 6
        assert stats["allow"] == 3
        assert stats["deny"] == 3
        assert stats["override"] == 2


# =============================================================================
# Integration Tests
# =============================================================================


class TestSecurityMatrixCompilerIntegration:
    """Integration tests for full execute() method."""

    def test_empty_rows_returns_empty_matrices(self):
        """No rows produces no matrices."""
        plugin = _create_plugin()
        ctx = _create_ctx(rows=[])

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert result.status == PluginStatus.SUCCESS
        # Empty rows = no output_data or matrix_count == 0
        if result.output_data:
            assert result.output_data.get("matrix_count", 0) == 0

    def test_publishes_security_matrices(self):
        """Compiler publishes security_matrices for downstream plugins."""
        plugin = _create_plugin()
        rows = [
            # Trust zones
            {
                "instance": "inst.trust_zone.management",
                "object_ref": "obj.network.trust_zone.management",
                "extensions": {"security_level": 5, "isolated": False, "name": "management"},
            },
            {
                "instance": "inst.trust_zone.user",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False, "name": "user"},
            },
            # VLANs with trust_zone_ref
            {
                "instance": "inst.vlan.user",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.10.0/24"},
            },
            # Security matrix
            {
                "instance": "inst.security_matrix.mikrotik",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "zone_refs": ["inst.trust_zone.management", "inst.trust_zone.user"],
                },
            },
        ]
        ctx = _create_ctx(rows=rows)

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert result.status == PluginStatus.SUCCESS
        assert result.output_data["matrix_count"] == 1
        assert "security_matrices" in ctx.get_published_keys(PLUGIN_ID)

    def test_zone_vlans_mapping(self):
        """Compiler builds zone_vlans mapping from VLAN trust_zone_ref."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.trust_zone.user",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False},
            },
            {
                "instance": "inst.vlan.user",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.10.0/24"},
            },
            {
                "instance": "inst.vlan.user_wireless",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.11.0/24"},
            },
            {
                "instance": "inst.security_matrix.mikrotik",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {"zone_refs": ["inst.trust_zone.user"]},
            },
        ]
        ctx = _create_ctx(rows=rows)

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert result.status == PluginStatus.SUCCESS
        assert "zone_vlans" in ctx.get_published_keys(PLUGIN_ID)

    def test_missing_zone_ref_emits_error(self):
        """Unknown zone_ref in security_matrix emits E7852."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.security_matrix.mikrotik",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {"zone_refs": ["inst.trust_zone.nonexistent"]},
            },
        ]
        ctx = _create_ctx(rows=rows)

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert result.has_errors
        assert any(d.code == "E7852" for d in result.diagnostics)

    def test_matrix_without_zone_refs_emits_warning(self):
        """Security matrix without zone_refs emits W7870."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.security_matrix.empty",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {},
            },
        ]
        # Object without zone_refs
        objects = {
            "obj.network.security_matrix.soho": {}
        }
        ctx = _create_ctx(rows=rows, objects=objects)

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert any(d.code == "W7870" for d in result.diagnostics)

    def test_vlan_cidr_map_published(self):
        """Compiler publishes vlan_cidr_map for address list generation."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.trust_zone.user",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False},
            },
            {
                "instance": "inst.vlan.user",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.10.0/24"},
            },
            {
                "instance": "inst.security_matrix.mikrotik",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {"zone_refs": ["inst.trust_zone.user"]},
            },
        ]
        ctx = _create_ctx(rows=rows)

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert result.status == PluginStatus.SUCCESS
        assert "vlan_cidr_map" in ctx.get_published_keys(PLUGIN_ID)

    def test_matrix_by_enforcer_published(self):
        """Compiler publishes matrix_by_enforcer for generator lookup."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.trust_zone.user",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False},
            },
            {
                "instance": "inst.security_matrix.mikrotik",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "zone_refs": ["inst.trust_zone.user"],
                },
            },
        ]
        ctx = _create_ctx(rows=rows)

        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )

        assert result.status == PluginStatus.SUCCESS
        assert "matrix_by_enforcer" in ctx.get_published_keys(PLUGIN_ID)


class TestZoneDataExtraction:
    """Tests for _extract_zone_data."""

    def test_extracts_from_extensions(self):
        """Zone data extracted from row extensions."""
        plugin = _create_plugin()
        row = {
            "instance": "inst.trust_zone.user",
            "object_ref": "obj.network.trust_zone.user",
            "extensions": {"security_level": 3, "isolated": False, "name": "user"},
        }
        ctx = _create_ctx(rows=[])

        result = plugin._extract_zone_data(row, row["extensions"], ctx)

        assert result is not None
        assert result["security_level"] == 3
        assert result["isolated"] is False
        assert result["name"] == "user"

    def test_falls_back_to_object_properties(self):
        """Zone data falls back to object properties."""
        plugin = _create_plugin()
        row = {
            "instance": "inst.trust_zone.user",
            "object_ref": "obj.network.trust_zone.user",
            "extensions": {},
        }
        objects = {
            "obj.network.trust_zone.user": {
                "properties": {
                    "security_level": 3,
                    "isolated": False,
                    "name": "user zone",
                }
            }
        }
        ctx = _create_ctx(rows=[], objects=objects)

        result = plugin._extract_zone_data(row, row["extensions"], ctx)

        assert result is not None
        assert result["security_level"] == 3
        assert result["name"] == "user zone"

    def test_returns_none_without_security_level(self):
        """Returns None if security_level is missing."""
        plugin = _create_plugin()
        row = {
            "instance": "inst.trust_zone.unknown",
            "object_ref": "obj.network.trust_zone.unknown",
            "extensions": {"isolated": False},
        }
        ctx = _create_ctx(rows=[])

        result = plugin._extract_zone_data(row, row["extensions"], ctx)

        assert result is None

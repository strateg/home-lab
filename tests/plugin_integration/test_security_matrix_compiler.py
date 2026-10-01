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
                "class_ref": "class.network.trust_zone",
                "object_ref": "obj.network.trust_zone.management",
                "extensions": {"security_level": 5, "isolated": False, "name": "management"},
            },
            {
                "instance": "inst.trust_zone.user",
                "class_ref": "class.network.trust_zone",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False, "name": "user"},
            },
            # VLANs with trust_zone_ref
            {
                "instance": "inst.vlan.user",
                "class_ref": "class.network.vlan",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.10.0/24"},
            },
            # Security matrix
            {
                "instance": "inst.security_matrix.mikrotik",
                "class_ref": "class.network.security_matrix",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "enforcement_plane": "perimeter",
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
                "class_ref": "class.network.trust_zone",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False},
            },
            {
                "instance": "inst.vlan.user",
                "class_ref": "class.network.vlan",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.10.0/24"},
            },
            {
                "instance": "inst.vlan.user_wireless",
                "class_ref": "class.network.vlan",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.11.0/24"},
            },
            {
                "instance": "inst.security_matrix.mikrotik",
                "class_ref": "class.network.security_matrix",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "enforcement_plane": "perimeter",
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
        assert "zone_vlans" in ctx.get_published_keys(PLUGIN_ID)

    def test_missing_zone_ref_emits_error(self):
        """Unknown zone_ref in security_matrix emits E7852."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.security_matrix.mikrotik",
                "class_ref": "class.network.security_matrix",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "enforcement_plane": "perimeter",
                    "zone_refs": ["inst.trust_zone.nonexistent"],
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

        assert result.has_errors
        assert any(d.code == "E7852" for d in result.diagnostics)

    def test_matrix_without_zone_refs_emits_warning(self):
        """Security matrix without zone_refs emits W7870."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.security_matrix.empty",
                "class_ref": "class.network.security_matrix",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {},
            },
        ]
        # Object without zone_refs
        objects = {"obj.network.security_matrix.soho": {}}
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
                "class_ref": "class.network.trust_zone",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False},
            },
            {
                "instance": "inst.vlan.user",
                "class_ref": "class.network.vlan",
                "object_ref": "obj.network.vlan.user",
                "extensions": {"trust_zone_ref": "inst.trust_zone.user", "cidr": "192.168.10.0/24"},
            },
            {
                "instance": "inst.security_matrix.mikrotik",
                "class_ref": "class.network.security_matrix",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "enforcement_plane": "perimeter",
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
        assert "vlan_cidr_map" in ctx.get_published_keys(PLUGIN_ID)

    def test_scopes_by_enforcer_published(self):
        """Compiler publishes scopes_by_enforcer, replacing matrix_by_enforcer."""
        plugin = _create_plugin()
        rows = [
            {
                "instance": "inst.trust_zone.user",
                "class_ref": "class.network.trust_zone",
                "object_ref": "obj.network.trust_zone.user",
                "extensions": {"security_level": 3, "isolated": False},
            },
            {
                "instance": "inst.security_matrix.mikrotik",
                "class_ref": "class.network.security_matrix",
                "object_ref": "obj.network.security_matrix.soho",
                "extensions": {
                    "managed_by_ref": "rtr-mikrotik-chateau",
                    "enforcement_plane": "perimeter",
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
        assert "scopes_by_enforcer" in ctx.get_published_keys(PLUGIN_ID)
        assert "matrix_by_enforcer" not in ctx.get_published_keys(PLUGIN_ID)


class TestScopesByEnforcer:
    """Counterexamples and positive controls for the enforcer/scope index.

    ADR 0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md section 5.4.
    `matrix_by_enforcer` was a one-entry-per-enforcer dict that silently
    dropped a scope whenever one enforcer held more than one, and whose
    surviving entry depended on input row order - a D4 permutation violation
    reproduced against the real compiler before this fix. `scopes_by_enforcer`
    is the replacement: complete membership, deterministic order, and it is a
    defect in these tests if any of the counterexamples below still pass by
    refusing every case rather than by handling the multiplicity.
    """

    @staticmethod
    def _zone(instance: str, security_level: int = 3) -> dict:
        return {
            "instance": instance,
            "class_ref": "class.network.trust_zone",
            "object_ref": f"obj.network.trust_zone.{instance.rsplit('.', 1)[-1]}",
            "extensions": {"security_level": security_level, "isolated": False},
        }

    @staticmethod
    def _matrix(instance: str, *, managed_by_ref=None, enforcement_plane=None, zone_refs=None, status=None) -> dict:
        extensions: dict = {"zone_refs": zone_refs or []}
        if managed_by_ref is not None:
            extensions["managed_by_ref"] = managed_by_ref
        if enforcement_plane is not None:
            extensions["enforcement_plane"] = enforcement_plane
        row = {
            "instance": instance,
            "class_ref": "class.network.security_matrix",
            "object_ref": "obj.network.security_matrix.soho",
            "extensions": extensions,
        }
        if status is not None:
            row["status"] = status
        return row

    @staticmethod
    def _subscribe(ctx, key: str):
        """Read a published value the way a real consumer does.

        `ctx.subscribe` is scope-gated: it only works inside another plugin's
        declared execution context. `run_plugin_for_test`/`publish_for_test`
        already open one with this same private API for exactly this reason;
        this mirrors them rather than reading the legacy full-registry dump
        the legacy full-registry dump, which the plugin_integration contract test
        forbids because it lets a test see values no real consumer declared.
        """
        ctx._set_execution_context("test.consumer.scopes_by_enforcer", {PLUGIN_ID})
        try:
            return ctx.subscribe(PLUGIN_ID, key)
        finally:
            ctx._clear_execution_context()

    def _run(self, rows: list[dict]):
        plugin = _create_plugin()
        ctx = _create_ctx(rows=rows)
        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )
        published_keys = set(ctx.get_published_keys(PLUGIN_ID))
        scopes_by_enforcer = self._subscribe(ctx, "scopes_by_enforcer") if "scopes_by_enforcer" in published_keys else {}
        security_matrices = self._subscribe(ctx, "security_matrices") if "security_matrices" in published_keys else {}
        return result, scopes_by_enforcer, list(security_matrices)

    def test_two_scopes_on_one_enforcer_are_both_retained(self):
        """The defect this channel replaces: two scopes on one enforcer, not one."""
        rows = [
            self._zone("inst.trust_zone.user"),
            self._zone("inst.trust_zone.dmz", security_level=1),
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.shared",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.shared",
                          enforcement_plane="internal", zone_refs=["inst.trust_zone.dmz"]),
        ]
        result, scopes_by_enforcer, _ = self._run(rows)

        # Warning-only: several scopes on one enforcer is permitted by the
        # model (ADR 0119 D1.1), so this does not block the compile.
        assert result.status == PluginStatus.PARTIAL
        assert any(d.code == "W7012" for d in result.diagnostics)
        assert scopes_by_enforcer == {
            "rtr.shared": ["inst.security_matrix.a", "inst.security_matrix.b"],
        }

    def test_reversed_input_order_is_byte_identical(self):
        """D4: the published channel must not depend on row order."""
        zones = [self._zone("inst.trust_zone.user"), self._zone("inst.trust_zone.dmz", security_level=1)]
        m_a = self._matrix("inst.security_matrix.a", managed_by_ref="rtr.shared",
                            enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"])
        m_b = self._matrix("inst.security_matrix.b", managed_by_ref="rtr.shared",
                            enforcement_plane="internal", zone_refs=["inst.trust_zone.dmz"])

        _, forward_scopes, forward_order = self._run(zones + [m_a, m_b])
        _, reverse_scopes, reverse_order = self._run(zones + [m_b, m_a])

        assert forward_scopes == reverse_scopes
        assert forward_order == reverse_order

    def test_two_enforcers_one_scope_each_no_cross_attribution(self):
        rows = [
            self._zone("inst.trust_zone.user"),
            self._zone("inst.trust_zone.dmz", security_level=1),
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.one",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.two",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.dmz"]),
        ]
        result, scopes_by_enforcer, _ = self._run(rows)

        assert result.status == PluginStatus.SUCCESS
        assert not result.diagnostics
        assert scopes_by_enforcer == {
            "rtr.one": ["inst.security_matrix.a"],
            "rtr.two": ["inst.security_matrix.b"],
        }

    def test_unattributed_scope_is_refused(self):
        """N-05: a scope with no managed_by_ref compiled clean and said nothing."""
        rows = [
            self._zone("inst.trust_zone.user"),
            self._matrix("inst.security_matrix.orphan", zone_refs=["inst.trust_zone.user"]),
        ]
        result, scopes_by_enforcer, security_matrices = self._run(rows)

        assert result.status == PluginStatus.FAILED
        assert any(d.code == "E7010" for d in result.diagnostics)
        assert scopes_by_enforcer == {}
        assert "inst.security_matrix.orphan" not in security_matrices

    def test_disabled_unattributed_scope_is_exempt(self):
        """status: disabled is the one declared exemption from E7010 - the
        present shape of inst.security_matrix.proxmox, which must keep
        compiling clean rather than newly block the pipeline."""
        rows = [
            self._zone("inst.trust_zone.user"),
            self._matrix("inst.security_matrix.orphan", zone_refs=["inst.trust_zone.user"], status="disabled"),
        ]
        result, scopes_by_enforcer, security_matrices = self._run(rows)

        assert result.status == PluginStatus.SUCCESS
        assert not any(d.code == "E7010" for d in result.diagnostics)
        assert scopes_by_enforcer == {}
        assert "inst.security_matrix.orphan" not in security_matrices

    def test_scope_with_no_plane_anywhere_is_refused(self):
        rows = [
            self._zone("inst.trust_zone.user"),
            self._matrix("inst.security_matrix.noplane", managed_by_ref="rtr.one",
                          zone_refs=["inst.trust_zone.user"]),
        ]
        result, scopes_by_enforcer, _ = self._run(rows)

        assert result.status == PluginStatus.FAILED
        assert any(d.code == "E7011" for d in result.diagnostics)
        assert scopes_by_enforcer == {}

    def test_full_permutation_is_byte_identical(self):
        zones = [self._zone("inst.trust_zone.user"), self._zone("inst.trust_zone.dmz", security_level=1)]
        matrices = [
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.one",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.one",
                          enforcement_plane="internal", zone_refs=["inst.trust_zone.dmz"]),
            self._matrix("inst.security_matrix.c", managed_by_ref="rtr.two",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
        ]

        _, forward_scopes, forward_order = self._run(zones + matrices)
        _, reverse_scopes, reverse_order = self._run(zones + list(reversed(matrices)))

        assert forward_scopes == reverse_scopes
        assert forward_order == reverse_order

    def test_positive_control_single_scope_topology_is_unaffected(self):
        """The real project's current shape: one enforcer, one scope, clean."""
        rows = [
            self._zone("inst.trust_zone.user"),
            self._matrix("inst.security_matrix.mikrotik", managed_by_ref="rtr-mikrotik-chateau",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
        ]
        result, scopes_by_enforcer, _ = self._run(rows)

        assert result.status == PluginStatus.SUCCESS
        assert not result.diagnostics
        assert scopes_by_enforcer == {"rtr-mikrotik-chateau": ["inst.security_matrix.mikrotik"]}


class TestComposedMatricesByEnforcer:
    """Counterexamples and positive controls for compile-stage composition.

    ADR 0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md section 5c,
    D-COMP-1..4. Reuses TestScopesByEnforcer's row-building helpers.
    """

    _zone = staticmethod(TestScopesByEnforcer._zone)

    @staticmethod
    def _matrix(instance: str, *, managed_by_ref=None, enforcement_plane=None,
                zone_refs=None, policy_overrides=None) -> dict:
        extensions: dict = {"zone_refs": zone_refs or []}
        if managed_by_ref is not None:
            extensions["managed_by_ref"] = managed_by_ref
        if enforcement_plane is not None:
            extensions["enforcement_plane"] = enforcement_plane
        if policy_overrides is not None:
            extensions["policy_overrides"] = policy_overrides
        return {
            "instance": instance,
            "class_ref": "class.network.security_matrix",
            "object_ref": "obj.network.security_matrix.soho",
            "extensions": extensions,
        }

    def _run(self, rows: list[dict]):
        plugin = _create_plugin()
        ctx = _create_ctx(rows=rows)
        result = run_plugin_for_test(
            plugin,
            ctx,
            Stage.COMPILE,
            consumes_keys={"base.compiler.instance_rows"},
        )
        published_keys = set(ctx.get_published_keys(PLUGIN_ID))
        composed = (
            TestScopesByEnforcer._subscribe(ctx, "composed_matrices_by_enforcer")
            if "composed_matrices_by_enforcer" in published_keys
            else {}
        )
        return result, composed

    def test_disjoint_scopes_compose_cleanly(self):
        rows = [
            self._zone("inst.trust_zone.user"),
            self._zone("inst.trust_zone.dmz", security_level=1),
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.shared",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.shared",
                          enforcement_plane="internal", zone_refs=["inst.trust_zone.dmz"]),
        ]
        result, composed = self._run(rows)

        assert result.status == PluginStatus.PARTIAL  # W7012 still fires; see 5b
        assert not any(d.code in ("E7013", "E7014") for d in result.diagnostics)
        assert set(composed.keys()) == {"rtr.shared"}
        assert set(composed["rtr.shared"]["zones"].keys()) == {
            "inst.trust_zone.user", "inst.trust_zone.dmz",
        }

    def test_overlapping_zones_are_refused(self):
        """D-COMP-1: the same zone claimed by two scopes on one enforcer."""
        rows = [
            self._zone("inst.trust_zone.user"),
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.shared",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.shared",
                          enforcement_plane="internal", zone_refs=["inst.trust_zone.user"]),
        ]
        result, composed = self._run(rows)

        assert result.status == PluginStatus.FAILED
        assert any(d.code == "E7013" for d in result.diagnostics)
        assert "rtr.shared" not in composed

    def test_colliding_override_names_are_refused(self):
        """D-COMP-2: the same override name declared by two scopes on one enforcer."""
        override = {"name": "admin-access", "from_zone_ref": "inst.trust_zone.user",
                    "to_zone_ref": "inst.trust_zone.user", "action": "accept"}
        rows = [
            self._zone("inst.trust_zone.user"),
            self._zone("inst.trust_zone.dmz", security_level=1),
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.shared",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"],
                          policy_overrides=[dict(override)]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.shared",
                          enforcement_plane="internal", zone_refs=["inst.trust_zone.dmz"],
                          policy_overrides=[dict(override)]),
        ]
        result, composed = self._run(rows)

        assert result.status == PluginStatus.FAILED
        assert any(d.code == "E7014" for d in result.diagnostics)
        assert "rtr.shared" not in composed

    def test_composition_is_order_independent(self):
        """D-COMP-4: same composed output regardless of row order."""
        zones = [self._zone("inst.trust_zone.user"), self._zone("inst.trust_zone.dmz", security_level=1)]
        m_a = self._matrix("inst.security_matrix.a", managed_by_ref="rtr.shared",
                            enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"])
        m_b = self._matrix("inst.security_matrix.b", managed_by_ref="rtr.shared",
                            enforcement_plane="internal", zone_refs=["inst.trust_zone.dmz"])

        _, forward = self._run(zones + [m_a, m_b])
        _, reverse = self._run(zones + [m_b, m_a])

        assert forward == reverse

    def test_two_enforcers_compose_independently(self):
        rows = [
            self._zone("inst.trust_zone.user"),
            self._zone("inst.trust_zone.dmz", security_level=1),
            self._matrix("inst.security_matrix.a", managed_by_ref="rtr.one",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
            self._matrix("inst.security_matrix.b", managed_by_ref="rtr.two",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.dmz"]),
        ]
        result, composed = self._run(rows)

        assert result.status == PluginStatus.SUCCESS
        assert set(composed.keys()) == {"rtr.one", "rtr.two"}
        assert set(composed["rtr.one"]["zones"].keys()) == {"inst.trust_zone.user"}
        assert set(composed["rtr.two"]["zones"].keys()) == {"inst.trust_zone.dmz"}

    def test_positive_control_single_scope_composition_is_a_no_op(self):
        """The real project's current shape: composing one scope changes nothing."""
        rows = [
            self._zone("inst.trust_zone.user"),
            self._matrix("inst.security_matrix.mikrotik", managed_by_ref="rtr-mikrotik-chateau",
                          enforcement_plane="perimeter", zone_refs=["inst.trust_zone.user"]),
        ]
        result, composed = self._run(rows)

        assert result.status == PluginStatus.SUCCESS
        assert not result.diagnostics
        assert composed["rtr-mikrotik-chateau"]["zones"].keys() == {"inst.trust_zone.user"}
        assert composed["rtr-mikrotik-chateau"]["policy_overrides"] == []


class TestZoneDataExtraction:
    """Tests for _extract_zone_data."""

    def test_extracts_from_extensions(self):
        """Zone data extracted from row extensions."""
        plugin = _create_plugin()
        row = {
            "instance": "inst.trust_zone.user",
            "class_ref": "class.network.trust_zone",
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
            "class_ref": "class.network.trust_zone",
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
            "class_ref": "class.network.trust_zone",
            "object_ref": "obj.network.trust_zone.unknown",
            "extensions": {"isolated": False},
        }
        ctx = _create_ctx(rows=[])

        result = plugin._extract_zone_data(row, row["extensions"], ctx)

        assert result is None

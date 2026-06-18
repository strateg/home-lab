#!/usr/bin/env python3
"""Integration tests for @on directive resolution in object defaults (ADR 0107).

Test Use Case: Host Placement Defaults via Object Templates
============================================================

Scenario: LXC workloads should inherit network, DNS, and trust zone settings
from their placement host without explicit declaration in each instance file.

Given:
  - A Proxmox host (srv-gamayun) with workload_defaults section
  - An LXC object template with @on directives in defaults section
  - An LXC instance that references the object and host

When:
  - The topology is compiled

Then:
  - The @on directives in object defaults are resolved
  - The instance inherits values from host's workload_defaults
  - Instance-specific values override inherited defaults
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

V5_TOOLS = Path(__file__).resolve().parents[2] / "topology-tools"
sys.path.insert(0, str(V5_TOOLS))

from kernel import PluginContext, PluginRegistry, PluginStatus
from kernel.plugin_base import Stage

from tests.helpers.plugin_execution import publish_for_test

ON_PREPARE_PLUGIN_ID = "base.compiler.instance_rows_on_prepare"
HOST_INDEX_PLUGIN_ID = "base.compiler.instance_host_index"


def _registry() -> PluginRegistry:
    registry = PluginRegistry(V5_TOOLS)
    registry.load_manifest(V5_TOOLS / "plugins" / "plugins.yaml")
    return registry


def _context_with_objects(objects: dict) -> PluginContext:
    return PluginContext(
        topology_path="topology/topology.yaml",
        profile="test",
        model_lock={},
        classes={},
        objects=objects,
        instance_bindings={"instance_bindings": {}},
    )


def _publish_prepared_rows(ctx: PluginContext, rows: list[dict]) -> None:
    publish_for_test(ctx, "base.compiler.instance_rows_prepare", "prepared_rows", rows)


def _publish_host_index(ctx: PluginContext, index: dict) -> None:
    publish_for_test(ctx, HOST_INDEX_PLUGIN_ID, "host_workload_defaults_index", index)


# =============================================================================
# Test Case 1: Basic @on resolution from object defaults
# =============================================================================


def test_on_directive_resolves_from_object_defaults():
    """@on directives in object defaults are resolved from host workload_defaults.

    Use Case:
        Object template defines: network.vlan_ref: "@on:host.network.vlan_ref"
        Host defines: workload_defaults.network.vlan_ref: "inst.vlan.servers"
        Result: Instance gets network.vlan_ref = "inst.vlan.servers"
    """
    registry = _registry()

    # Object template with @on directive in defaults
    objects = {
        "obj.test.lxc.base": {
            "@object": "obj.test.lxc.base",
            "defaults": {
                "network": {
                    "vlan_ref": "@on:host.network.vlan_ref",
                    "bridge_ref": "@on:host.network.bridge_ref",
                },
                "trust_zone_ref": "@on:host.trust_zone_ref",
            },
        }
    }

    ctx = _context_with_objects(objects)

    # Host with workload_defaults
    host_index = {
        "srv-test": {
            "network": {
                "vlan_ref": "inst.vlan.servers",
                "bridge_ref": "inst.bridge.vmbr0",
            },
            "trust_zone_ref": "inst.trust_zone.servers",
        }
    }

    # Prepared row for LXC instance
    prepared_rows = [
        {
            "instance": "lxc-test",
            "object_ref": "obj.test.lxc.base",
            "row_path": "instance_bindings.lxc[0]",
            "row": {
                "host_ref": "srv-test",
                "network": {
                    "ip": "10.0.30.10/24",  # Instance-specific value
                },
            },
        }
    ]

    _publish_prepared_rows(ctx, prepared_rows)
    _publish_host_index(ctx, host_index)

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert errors == [], f"Unexpected errors: {errors}"

    # Check resolved values
    on_prepared = result.output_data.get("on_prepared_rows", [])
    assert len(on_prepared) == 1

    resolved_row = on_prepared[0]["row"]

    # Values from object defaults @on resolution
    assert resolved_row["network"]["vlan_ref"] == "inst.vlan.servers"
    assert resolved_row["network"]["bridge_ref"] == "inst.bridge.vmbr0"
    assert resolved_row["trust_zone_ref"] == "inst.trust_zone.servers"

    # Instance-specific value preserved
    assert resolved_row["network"]["ip"] == "10.0.30.10/24"


# =============================================================================
# Test Case 2: Instance values override object defaults
# =============================================================================


def test_instance_values_override_object_defaults():
    """Instance explicit values override @on resolved values from object defaults.

    Use Case:
        Object template: network.gateway: "@on:host.network.gateway"
        Host: workload_defaults.network.gateway: "10.0.30.1"
        Instance: network.gateway: "10.0.30.254"  (explicit override)
        Result: Instance gets network.gateway = "10.0.30.254"
    """
    registry = _registry()

    objects = {
        "obj.test.lxc.custom": {
            "@object": "obj.test.lxc.custom",
            "defaults": {
                "network": {
                    "gateway": "@on:host.network.gateway",
                    "vlan_ref": "@on:host.network.vlan_ref",
                },
            },
        }
    }

    ctx = _context_with_objects(objects)

    host_index = {
        "srv-test": {
            "network": {
                "gateway": "10.0.30.1",
                "vlan_ref": "inst.vlan.servers",
            },
        }
    }

    prepared_rows = [
        {
            "instance": "lxc-custom",
            "object_ref": "obj.test.lxc.custom",
            "row_path": "instance_bindings.lxc[0]",
            "row": {
                "host_ref": "srv-test",
                "network": {
                    "gateway": "10.0.30.254",  # Explicit override
                    "ip": "10.0.30.50/24",
                },
            },
        }
    ]

    _publish_prepared_rows(ctx, prepared_rows)
    _publish_host_index(ctx, host_index)

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS

    on_prepared = result.output_data.get("on_prepared_rows", [])
    resolved_row = on_prepared[0]["row"]

    # Instance value wins over @on resolved value
    assert resolved_row["network"]["gateway"] == "10.0.30.254"

    # @on resolved value used when no instance override
    assert resolved_row["network"]["vlan_ref"] == "inst.vlan.servers"


# =============================================================================
# Test Case 3: Optional @on with default value
# =============================================================================


def test_optional_on_with_default_value():
    """Optional @on directive uses default value when path not found.

    Use Case:
        Object template: dns.searchdomain: "@on:host.dns.searchdomain?:local"
        Host: workload_defaults has no dns.searchdomain
        Result: Instance gets dns.searchdomain = "local"
    """
    registry = _registry()

    objects = {
        "obj.test.lxc.optional": {
            "@object": "obj.test.lxc.optional",
            "defaults": {
                "dns": {
                    "nameserver": "@on:host.dns.nameserver?",
                    "searchdomain": "@on:host.dns.searchdomain?:local",
                },
            },
        }
    }

    ctx = _context_with_objects(objects)

    # Host without dns section
    host_index = {
        "srv-test": {
            "network": {"vlan_ref": "inst.vlan.servers"},
            # No dns section
        }
    }

    prepared_rows = [
        {
            "instance": "lxc-optional",
            "object_ref": "obj.test.lxc.optional",
            "row_path": "instance_bindings.lxc[0]",
            "row": {
                "host_ref": "srv-test",
            },
        }
    ]

    _publish_prepared_rows(ctx, prepared_rows)
    _publish_host_index(ctx, host_index)

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    # PARTIAL status expected due to warnings
    assert result.status in (PluginStatus.SUCCESS, PluginStatus.PARTIAL)

    # Should have warnings for optional paths not found
    warnings = [d for d in result.diagnostics if d.severity == "warning"]
    assert any("W6814" in w.code for w in warnings)

    on_prepared = result.output_data.get("on_prepared_rows", [])
    resolved_row = on_prepared[0]["row"]

    # Default value used
    assert resolved_row["dns"]["searchdomain"] == "local"

    # No default, optional returns None
    assert resolved_row["dns"]["nameserver"] is None


# =============================================================================
# Test Case 4: Deep merge of nested structures
# =============================================================================


def test_deep_merge_nested_structures():
    """Deep merge correctly combines object defaults with instance values.

    Use Case:
        Object defaults: storage.rootfs.pool_ref: "@on:host.storage.default_pool_ref"
        Instance: storage.rootfs.size_gb: 20
        Result: storage.rootfs has both pool_ref and size_gb
    """
    registry = _registry()

    objects = {
        "obj.test.lxc.storage": {
            "@object": "obj.test.lxc.storage",
            "defaults": {
                "storage": {
                    "rootfs": {
                        "pool_ref": "@on:host.storage.default_pool_ref",
                    },
                },
            },
        }
    }

    ctx = _context_with_objects(objects)

    host_index = {
        "srv-test": {
            "storage": {
                "default_pool_ref": "inst.storage.pool.local_lvm",
            },
        }
    }

    prepared_rows = [
        {
            "instance": "lxc-storage",
            "object_ref": "obj.test.lxc.storage",
            "row_path": "instance_bindings.lxc[0]",
            "row": {
                "host_ref": "srv-test",
                "storage": {
                    "rootfs": {
                        "size_gb": 20,  # Instance-specific
                    },
                },
            },
        }
    ]

    _publish_prepared_rows(ctx, prepared_rows)
    _publish_host_index(ctx, host_index)

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS

    on_prepared = result.output_data.get("on_prepared_rows", [])
    resolved_row = on_prepared[0]["row"]

    # Both values present after deep merge
    assert resolved_row["storage"]["rootfs"]["pool_ref"] == "inst.storage.pool.local_lvm"
    assert resolved_row["storage"]["rootfs"]["size_gb"] == 20


# =============================================================================
# Test Case 5: No object defaults - instance values only
# =============================================================================


def test_no_object_defaults_passes_through():
    """Instance without object defaults passes through unchanged.

    Use Case:
        Object template has no defaults section
        Instance has explicit values
        Result: Instance values pass through unchanged
    """
    registry = _registry()

    objects = {
        "obj.test.lxc.nodefaults": {
            "@object": "obj.test.lxc.nodefaults",
            # No defaults section
        }
    }

    ctx = _context_with_objects(objects)

    host_index = {
        "srv-test": {
            "network": {"vlan_ref": "inst.vlan.servers"},
        }
    }

    prepared_rows = [
        {
            "instance": "lxc-nodefaults",
            "object_ref": "obj.test.lxc.nodefaults",
            "row_path": "instance_bindings.lxc[0]",
            "row": {
                "host_ref": "srv-test",
                "network": {
                    "ip": "10.0.30.100/24",
                },
            },
        }
    ]

    _publish_prepared_rows(ctx, prepared_rows)
    _publish_host_index(ctx, host_index)

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS

    on_prepared = result.output_data.get("on_prepared_rows", [])
    resolved_row = on_prepared[0]["row"]

    # Instance value unchanged
    assert resolved_row["network"]["ip"] == "10.0.30.100/24"

    # No vlan_ref added (no @on in object defaults)
    assert "vlan_ref" not in resolved_row.get("network", {})

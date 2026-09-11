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

    # No default, optional @on paths are stripped (not merged as None)
    # This prevents validator errors for fields that don't apply to all hosts
    assert "nameserver" not in resolved_row["dns"]


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


# =============================================================================
# v2 network intent through the same inheritance chain (ADR 0118, W09)
# =============================================================================


def test_a_v2_attachment_inherits_from_the_host_through_on_directives():
    """The migration path, proved rather than assumed.

    Migrating a workload to v2 is a per-host change: the object module pulls
    `network.network_ref` and `network.gateway` from the host with `@on`, the host
    declares them in v1 shape, and an instance that adds v2 attachments beside
    them produces a mixed effective block - which is what `E7004` forbids and what
    migrating one real source actually hit.

    So the question W09 has to answer first is whether the v2 shape can travel the
    same chain at all. `_get_nested_value` walks a dotted path of arbitrary depth,
    so it should; this asserts it does, because "should" is not a migration plan.
    """
    registry = _registry()

    objects = {
        "obj.test.docker.v2": {
            "@object": "obj.test.docker.v2",
            "defaults": {
                "network": {
                    "schema_version": 2,
                    "attachments": {
                        "primary": {
                            "network_ref": "@on:host.network.attachments.primary.network_ref",
                            "driver": "@on:host.network.attachments.primary.driver?",
                        }
                    },
                }
            },
        }
    }
    ctx = _context_with_objects(objects)

    host_index = {
        "srv-test": {
            "network": {
                "schema_version": 2,
                "attachments": {"primary": {"network_ref": "inst.vlan.servers", "driver": "macvlan"}},
            }
        }
    }

    prepared_rows = [
        {
            "instance": "docker-test",
            "object_ref": "obj.test.docker.v2",
            "row_path": "instance_bindings.docker[0]",
            "row": {
                "host_ref": "srv-test",
                # The instance states only what is its own: the address.
                "network": {"attachments": {"primary": {"address": {"allocation": "static", "host": 210}}}},
            },
        }
    ]

    _publish_prepared_rows(ctx, prepared_rows)
    _publish_host_index(ctx, host_index)

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    assert result.status == PluginStatus.SUCCESS
    assert [d for d in result.diagnostics if d.severity == "error"] == []

    resolved = result.output_data["on_prepared_rows"][0]["row"]
    attachment = resolved["network"]["attachments"]["primary"]

    assert attachment["network_ref"] == "inst.vlan.servers"
    assert attachment["driver"] == "macvlan"
    # The instance's own value survives the merge beside the inherited ones.
    assert attachment["address"] == {"allocation": "static", "host": 210}
    assert resolved["network"]["schema_version"] == 2


def test_an_inherited_v2_block_carries_no_v1_key():
    """What makes the migrated block clean, and therefore acceptable to E7004.

    The v1 chain injects `network_ref` and `gateway` at block level. A v2 chain
    must put the reference inside the attachment and leave the gateway to the
    address domain, or the merged block is mixed and the migration cannot land.
    """
    registry = _registry()

    objects = {
        "obj.test.docker.v2": {
            "@object": "obj.test.docker.v2",
            "defaults": {
                "network": {
                    "schema_version": 2,
                    "attachments": {"primary": {"network_ref": "@on:host.network.attachments.primary.network_ref"}},
                }
            },
        }
    }
    ctx = _context_with_objects(objects)
    _publish_prepared_rows(
        ctx,
        [
            {
                "instance": "docker-test",
                "object_ref": "obj.test.docker.v2",
                "row_path": "instance_bindings.docker[0]",
                "row": {"host_ref": "srv-test", "network": {}},
            }
        ],
    )
    _publish_host_index(
        ctx,
        {"srv-test": {"network": {"schema_version": 2, "attachments": {"primary": {"network_ref": "inst.vlan.servers"}}}}},
    )

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)
    block = result.output_data["on_prepared_rows"][0]["row"]["network"]

    v1_keys = {"vlan_ref", "bridge_ref", "host", "ip", "gateway"} & set(block)
    assert not v1_keys, f"the inherited v2 block carries version 1 keys {sorted(v1_keys)}"


def test_a_missing_host_attachment_is_reported_not_silently_dropped():
    """A required @on into a v2 path that the host does not declare.

    Silence here would leave an attachment with no network_ref, which the
    validator would then report as a shape error at a path pointing at the
    instance - sending the author to the wrong file.
    """
    registry = _registry()

    objects = {
        "obj.test.docker.v2": {
            "@object": "obj.test.docker.v2",
            "defaults": {
                "network": {
                    "schema_version": 2,
                    "attachments": {"primary": {"network_ref": "@on:host.network.attachments.primary.network_ref"}},
                }
            },
        }
    }
    ctx = _context_with_objects(objects)
    _publish_prepared_rows(
        ctx,
        [
            {
                "instance": "docker-test",
                "object_ref": "obj.test.docker.v2",
                "row_path": "instance_bindings.docker[0]",
                "row": {"host_ref": "srv-test", "network": {}},
            }
        ],
    )
    _publish_host_index(ctx, {"srv-test": {"network": {"schema_version": 2, "attachments": {}}}})

    result = registry.execute_plugin(ON_PREPARE_PLUGIN_ID, ctx, Stage.COMPILE)

    codes = [d.code for d in result.diagnostics]
    assert "E6810" in codes, f"a missing required host path must be reported, got {codes}"

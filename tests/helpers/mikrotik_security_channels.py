"""The channels the MikroTik generator consumes, for tests that render it.

`object.mikrotik.generator.terraform` consumes `composed_matrices_by_enforcer`
and `vlan_cidr_map` from `base.compiler.security_matrix`, both declared
`required: true`. `composed_matrices_by_enforcer` replaced `security_matrices`
(ADR 0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md sections 5c/5d,
N-07): the projection used to re-derive R1-R6 itself and now reads the
compiler's already-composed plan per enforcer instead. The projection derives
no substitute for either channel, so a test that runs the generator has to say
what they hold - an omission is a blocked run, which is the point of the
contract and is covered by its own negative test.

It also consumes `capability_flags` from `object.mikrotik.compiler.
capability_flags` (W07 migration order item 1, 2026-09-29),
`wireguard_tunnels` from `object.mikrotik.compiler.wireguard_tunnels` (W07
migration order item 4a, 2026-09-29) and `containers` from `object.mikrotik.
compiler.containers` (W07 migration order item 4b, 2026-09-29), all three
likewise `required: true`. Unlike the matrix/CIDR pair, these three are not
published empty: capability-, tunnel- and container-driven tests need them
to reflect the fixture's own routers, so `publish_empty_channels` derives
all three from `ctx.compiled_json` the same way the real compile-stage
plugins do.

These helpers make the statement one line. Passing empty mappings for the
matrix/CIDR channels means "this fixture declares no matrices and no address
domains", which is true of every fixture that is about template selection,
host derivation or file inventory rather than about zone content.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path as _Path
from typing import Any

SECURITY_MATRIX_COMPILER = "base.compiler.security_matrix"
CAPABILITY_FLAGS_COMPILER = "object.mikrotik.compiler.capability_flags"
WIREGUARD_TUNNELS_COMPILER = "object.mikrotik.compiler.wireguard_tunnels"
CONTAINERS_COMPILER = "object.mikrotik.compiler.containers"
CHANNEL_KEYS = ("composed_matrices_by_enforcer", "vlan_cidr_map")


def _load_module(entry_filename: str, class_or_func_owner_label: str):
    module_path = (
        _Path(__file__).resolve().parents[2]
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / entry_filename
    )
    spec = importlib.util.spec_from_file_location(
        f"mikrotik_security_channels_{class_or_func_owner_label}", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CAPABILITY_FLAGS_MODULE = _load_module("capability_flags_compiler.py", "capability_flags")
_EMPTY_CAPABILITY_FLAGS = _CAPABILITY_FLAGS_MODULE._derive_capability_flags([])

_WIREGUARD_TUNNELS_MODULE = _load_module("wireguard_tunnels_compiler.py", "wireguard_tunnels")
_EMPTY_WIREGUARD_TUNNELS = _WIREGUARD_TUNNELS_MODULE._extract_wireguard_tunnels([], set(), {})

_CONTAINERS_MODULE = _load_module("containers_compiler.py", "containers")
_EMPTY_CONTAINERS = _CONTAINERS_MODULE._extract_containers([], set())


def _mikrotik_router_ids(compiled_json: Any) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    """(router instance ids, network-group rows, routeros_container-group rows)."""
    if not isinstance(compiled_json, dict):
        return set(), [], []
    instances = compiled_json.get("instances")
    if not isinstance(instances, dict):
        return set(), [], []
    devices = instances.get("devices", [])
    if not isinstance(devices, list):
        devices = []
    network_rows = instances.get("network", [])
    if not isinstance(network_rows, list):
        network_rows = []
    container_rows = instances.get("routeros_container", [])
    if not isinstance(container_rows, list):
        container_rows = []
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    router_ids: set[str] = set()
    for row in devices:
        if not isinstance(row, dict) or not resolved_object_ref(row).startswith("obj.mikrotik."):
            continue
        instance_id = row.get("instance_id")
        if isinstance(instance_id, str) and instance_id:
            router_ids.add(instance_id)
    return router_ids, network_rows, container_rows


def _derive_capability_flags_for(compiled_json: Any) -> dict[str, bool]:
    """Same derivation the real compile-stage compiler performs (W07 item 1)."""
    if not isinstance(compiled_json, dict):
        return dict(_EMPTY_CAPABILITY_FLAGS)
    instances = compiled_json.get("instances", {})
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    routers = [
        row for row in devices if isinstance(row, dict) and resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    return _CAPABILITY_FLAGS_MODULE._derive_capability_flags(routers)


def _derive_wireguard_tunnels_for(compiled_json: Any) -> dict[str, Any]:
    """Same derivation the real compile-stage compiler performs (W07 item 4a)."""
    if not isinstance(compiled_json, dict):
        return dict(_EMPTY_WIREGUARD_TUNNELS)
    router_ids, network_rows, _ = _mikrotik_router_ids(compiled_json)
    return _WIREGUARD_TUNNELS_MODULE._extract_wireguard_tunnels(network_rows, router_ids, {})


def _derive_containers_for(compiled_json: Any) -> list[dict[str, Any]]:
    """Same derivation the real compile-stage compiler performs (W07 item 4b)."""
    if not isinstance(compiled_json, dict):
        return list(_EMPTY_CONTAINERS)
    router_ids, _, container_rows = _mikrotik_router_ids(compiled_json)
    return _CONTAINERS_MODULE._extract_containers(container_rows, router_ids)


def publish_empty_channels(ctx: Any) -> None:
    """Publish the matrix/CIDR channels empty, and capability_flags/
    wireguard_tunnels/containers derived from `ctx.compiled_json` (empty
    input still produces the full shape the real compilers would, not a
    bare `{}`/`[]`, so golden-snapshot and template-selection fixtures
    compare equal to production output)."""
    from tests.helpers.plugin_execution import publish_for_test

    for key in CHANNEL_KEYS:
        publish_for_test(ctx, SECURITY_MATRIX_COMPILER, key, {})
    compiled_json = getattr(ctx, "compiled_json", None)
    publish_for_test(
        ctx, CAPABILITY_FLAGS_COMPILER, "capability_flags", _derive_capability_flags_for(compiled_json)
    )
    publish_for_test(
        ctx, WIREGUARD_TUNNELS_COMPILER, "wireguard_tunnels", _derive_wireguard_tunnels_for(compiled_json)
    )
    publish_for_test(ctx, CONTAINERS_COMPILER, "containers", _derive_containers_for(compiled_json))


def empty_channel_subscriptions() -> dict[tuple[str, str], Any]:
    """The same, as the `subscriptions` mapping of a `PluginInputSnapshot`.

    No `compiled_json` is available at this call site, so `capability_flags`,
    `wireguard_tunnels` and `containers` are the all-empty defaults rather
    than a per-fixture derivation.
    """
    from kernel.plugin_base import SubscriptionValue

    subscriptions = {
        (SECURITY_MATRIX_COMPILER, key): SubscriptionValue(from_plugin=SECURITY_MATRIX_COMPILER, key=key, value={})
        for key in CHANNEL_KEYS
    }
    subscriptions[(CAPABILITY_FLAGS_COMPILER, "capability_flags")] = SubscriptionValue(
        from_plugin=CAPABILITY_FLAGS_COMPILER, key="capability_flags", value=dict(_EMPTY_CAPABILITY_FLAGS)
    )
    subscriptions[(WIREGUARD_TUNNELS_COMPILER, "wireguard_tunnels")] = SubscriptionValue(
        from_plugin=WIREGUARD_TUNNELS_COMPILER, key="wireguard_tunnels", value=dict(_EMPTY_WIREGUARD_TUNNELS)
    )
    subscriptions[(CONTAINERS_COMPILER, "containers")] = SubscriptionValue(
        from_plugin=CONTAINERS_COMPILER, key="containers", value=list(_EMPTY_CONTAINERS)
    )
    return subscriptions


__all__ = [
    "CAPABILITY_FLAGS_COMPILER",
    "CHANNEL_KEYS",
    "CONTAINERS_COMPILER",
    "SECURITY_MATRIX_COMPILER",
    "WIREGUARD_TUNNELS_COMPILER",
    "empty_channel_subscriptions",
    "publish_empty_channels",
]

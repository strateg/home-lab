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
capability_flags` (W07 migration order item 1, 2026-09-29), likewise
`required: true`. Unlike the other two, this one is not published empty:
capability-driven template selection tests need it to reflect the fixture's
own routers, so `publish_empty_channels` derives it from `ctx.compiled_json`
the same way the real compile-stage plugin does.

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
CHANNEL_KEYS = ("composed_matrices_by_enforcer", "vlan_cidr_map")


def _load_capability_flags_module():
    module_path = (
        _Path(__file__).resolve().parents[2]
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "compilers"
        / "capability_flags_compiler.py"
    )
    spec = importlib.util.spec_from_file_location("mikrotik_security_channels_capability_flags", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CAPABILITY_FLAGS_MODULE = _load_capability_flags_module()
_EMPTY_CAPABILITY_FLAGS = _CAPABILITY_FLAGS_MODULE._derive_capability_flags([])


def _derive_capability_flags_for(compiled_json: Any) -> dict[str, bool]:
    """Same derivation the real compile-stage compiler performs (W07 item 1)."""
    if not isinstance(compiled_json, dict):
        return dict(_EMPTY_CAPABILITY_FLAGS)
    instances = compiled_json.get("instances")
    devices = instances.get("devices", []) if isinstance(instances, dict) else []
    if not isinstance(devices, list):
        devices = []
    resolved_object_ref = _CAPABILITY_FLAGS_MODULE._resolved_object_ref
    routers = [
        row for row in devices if isinstance(row, dict) and resolved_object_ref(row).startswith("obj.mikrotik.")
    ]
    return _CAPABILITY_FLAGS_MODULE._derive_capability_flags(routers)


def publish_empty_channels(ctx: Any) -> None:
    """Publish the matrix/CIDR channels empty, and capability_flags derived
    from `ctx.compiled_json` (empty routers still produce the full all-False
    dict the real compiler would, not a bare `{}`, so golden-snapshot and
    template-selection fixtures compare equal to production output)."""
    from tests.helpers.plugin_execution import publish_for_test

    for key in CHANNEL_KEYS:
        publish_for_test(ctx, SECURITY_MATRIX_COMPILER, key, {})
    compiled_json = getattr(ctx, "compiled_json", None)
    publish_for_test(
        ctx, CAPABILITY_FLAGS_COMPILER, "capability_flags", _derive_capability_flags_for(compiled_json)
    )


def empty_channel_subscriptions() -> dict[tuple[str, str], Any]:
    """The same, as the `subscriptions` mapping of a `PluginInputSnapshot`.

    No `compiled_json` is available at this call site, so `capability_flags`
    is the all-False default rather than a per-fixture derivation.
    """
    from kernel.plugin_base import SubscriptionValue

    subscriptions = {
        (SECURITY_MATRIX_COMPILER, key): SubscriptionValue(from_plugin=SECURITY_MATRIX_COMPILER, key=key, value={})
        for key in CHANNEL_KEYS
    }
    subscriptions[(CAPABILITY_FLAGS_COMPILER, "capability_flags")] = SubscriptionValue(
        from_plugin=CAPABILITY_FLAGS_COMPILER, key="capability_flags", value=dict(_EMPTY_CAPABILITY_FLAGS)
    )
    return subscriptions


__all__ = [
    "CAPABILITY_FLAGS_COMPILER",
    "CHANNEL_KEYS",
    "SECURITY_MATRIX_COMPILER",
    "empty_channel_subscriptions",
    "publish_empty_channels",
]

"""The channels the MikroTik generator consumes, for tests that render it.

`object.mikrotik.generator.terraform` consumes `security_matrices` and
`vlan_cidr_map` from `base.compiler.security_matrix`, both declared
`required: true`. The projection derives no substitute for either, so a test
that runs the generator has to say what those channels hold - an omission is a
blocked run, which is the point of the contract and is covered by its own
negative test.

These helpers make the statement one line. Passing empty mappings means "this
fixture declares no matrices and no address domains", which is true of every
fixture that is about template selection, host derivation or file inventory
rather than about zone content.
"""

from __future__ import annotations

from typing import Any

SECURITY_MATRIX_COMPILER = "base.compiler.security_matrix"
CHANNEL_KEYS = ("security_matrices", "vlan_cidr_map")


def publish_empty_channels(ctx: Any) -> None:
    """Publish both channels as empty mappings onto a legacy PluginContext."""
    from tests.helpers.plugin_execution import publish_for_test

    for key in CHANNEL_KEYS:
        publish_for_test(ctx, SECURITY_MATRIX_COMPILER, key, {})


def empty_channel_subscriptions() -> dict[tuple[str, str], Any]:
    """The same, as the `subscriptions` mapping of a `PluginInputSnapshot`."""
    from kernel.plugin_base import SubscriptionValue

    return {
        (SECURITY_MATRIX_COMPILER, key): SubscriptionValue(from_plugin=SECURITY_MATRIX_COMPILER, key=key, value={})
        for key in CHANNEL_KEYS
    }


__all__ = [
    "CHANNEL_KEYS",
    "SECURITY_MATRIX_COMPILER",
    "empty_channel_subscriptions",
    "publish_empty_channels",
]

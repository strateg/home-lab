"""Unit checks for record identity and inheritance.

Each test states one rule of the accepted model. Where a rule exists to prevent a
specific failure, the test name says which failure.
"""

from __future__ import annotations

import pytest

from netmodel.identity import (
    IdentityError,
    RecordIdentity,
    active_records,
    is_enabled,
    merge_collection,
    merge_inherited,
    rejected_derived_overrides,
    resolve_reference,
    validate_local_key,
)


@pytest.mark.parametrize("key", ["backend", "primary", "dns", "_internal", "wan0", "A"])
def test_valid_local_keys(key: str) -> None:
    assert validate_local_key(key) == key


@pytest.mark.parametrize(
    "key",
    [
        "wan-uplink",  # hyphen: the @on path syntax cannot express it
        "net.primary",  # dot: makes a reference path ambiguous
        "@primary",  # @: reserved for semantic metadata
        "1st",  # digit first
        "",
        "два",  # non-ASCII
    ],
)
def test_invalid_local_keys(key: str) -> None:
    with pytest.raises(IdentityError):
        validate_local_key(key)


def test_identity_is_scoped_and_needs_no_parsing() -> None:
    ident = RecordIdentity(project="home-lab", owner="docker-adguard", kind="attachment", local_key="backend")

    assert ident.reference == ("home-lab", "docker-adguard", "attachment", "backend")


def test_identity_rejects_an_empty_scope() -> None:
    with pytest.raises(IdentityError):
        RecordIdentity(project="", owner="docker-adguard", kind="attachment", local_key="backend")


def test_same_key_in_different_owners_are_different_records() -> None:
    a = RecordIdentity(project="home-lab", owner="docker-adguard", kind="attachment", local_key="backend")
    b = RecordIdentity(project="home-lab", owner="docker-mosquitto", kind="attachment", local_key="backend")

    assert a != b and a.reference != b.reference


def test_nested_mappings_merge() -> None:
    base = {"interface": "eth0", "address": {"allocation": "static"}, "default_route": True}
    override = {"network_ref": "inst.vlan.servers", "address": {"host": 60}}

    assert merge_inherited(base, override) == {
        "interface": "eth0",
        "address": {"allocation": "static", "host": 60},
        "default_route": True,
        "network_ref": "inst.vlan.servers",
    }


def test_value_lists_replace_whole_rather_than_extend() -> None:
    """A selector list that grew by inheritance would widen access silently."""
    base = {"source_refs": ["inst.vlan.lan", "inst.vlan.user"]}
    override = {"source_refs": ["inst.vlan.lan"]}

    assert merge_inherited(base, override) == {"source_refs": ["inst.vlan.lan"]}


def test_an_explicit_null_overrides_and_absence_inherits() -> None:
    base = {"gateway": "10.0.0.1", "announcement": "interface_address"}

    assert merge_inherited(base, {"gateway": None}) == {"gateway": None, "announcement": "interface_address"}
    assert merge_inherited(base, {}) == base


def test_collection_inherits_records_the_override_does_not_mention() -> None:
    base = {"primary": {"interface": "eth0"}, "backup": {"interface": "eth1"}}
    override = {"primary": {"network_ref": "inst.vlan.servers"}}

    merged = merge_collection(base, override)

    assert merged["primary"] == {"interface": "eth0", "network_ref": "inst.vlan.servers"}
    assert merged["backup"] == {"interface": "eth1"}


def test_collection_merge_does_not_mutate_its_inputs() -> None:
    base = {"primary": {"address": {"allocation": "static"}}}
    override = {"primary": {"address": {"host": 60}}}

    merge_collection(base, override)

    assert base == {"primary": {"address": {"allocation": "static"}}}
    assert override == {"primary": {"address": {"host": 60}}}


def test_invalid_keys_are_refused_on_either_side() -> None:
    with pytest.raises(IdentityError):
        merge_collection({"wan-uplink": {}}, {})
    with pytest.raises(IdentityError):
        merge_collection({}, {"net.primary": {}})


def test_rename_is_a_new_record_and_carries_nothing_over() -> None:
    """Nothing about the old record transfers: not its address, not its approval."""
    base = {"primary": {"interface": "eth0", "address": {"host": 60}}}
    override = {"uplink": {"network_ref": "inst.vlan.servers"}}

    merged = merge_collection(base, override)

    assert merged["uplink"] == {"network_ref": "inst.vlan.servers"}
    assert "address" not in merged["uplink"]
    assert "primary" in merged, "the old key is still there until it is disabled or removed"


def test_only_an_explicit_false_disables() -> None:
    assert is_enabled({}) is True
    assert is_enabled({"enabled": True}) is True
    assert is_enabled({"enabled": False}) is False


@pytest.mark.parametrize("value", [None, "false", 0, []])
def test_enabled_refuses_anything_but_a_boolean(value: object) -> None:
    with pytest.raises(IdentityError):
        is_enabled({"enabled": value})


def test_disabling_an_inherited_record_leaves_it_present_but_inactive() -> None:
    merged = merge_collection({"legacy": {"interface": "eth9"}}, {"legacy": {"enabled": False}})

    assert "legacy" in merged
    assert active_records(merged) == {}


def test_reference_to_a_disabled_record_is_an_error_not_a_miss() -> None:
    collection = {"backend": {"enabled": False}}

    with pytest.raises(IdentityError, match="disabled"):
        resolve_reference(collection, "backend")


def test_reference_to_an_unknown_record_is_an_error() -> None:
    with pytest.raises(IdentityError, match="unknown"):
        resolve_reference({"backend": {}}, "frontend")


def test_reference_resolves_an_active_record() -> None:
    collection = {"backend": {"interface": "eth0"}}

    assert resolve_reference(collection, "backend") == {"interface": "eth0"}


def test_derived_overrides_on_a_consumer_record_are_reported() -> None:
    record = {"network_ref": "inst.vlan.servers", "host": 60, "gateway": "10.0.100.1", "zone": "servers"}

    assert rejected_derived_overrides(record, ("gateway", "zone", "routing_domain")) == ["gateway", "zone"]

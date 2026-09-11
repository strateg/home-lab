"""The first end-to-end pass of the model over the real topology.

It runs read-only and changes nothing. Its value is the blocked list: a measured
distance between the sources and the target model, rather than an estimate.

The numbers are pinned deliberately. If a number moves, either the topology
gained the data or the reader lost it, and both are worth stopping for.
"""

from __future__ import annotations

import pytest

from netmodel.intent import build_inventory
from netmodel.snapshot import DEFAULT_SNAPSHOT, load_snapshot


@pytest.fixture(scope="module")
def inventory():
    if not DEFAULT_SNAPSHOT.exists():
        pytest.skip(f"{DEFAULT_SNAPSHOT} absent; run `task netmodel:snapshot` first")
    return build_inventory(load_snapshot())


def test_every_workload_network_block_becomes_an_attachment(inventory) -> None:
    """Attachment is the part the sources already express."""
    assert inventory.summary()["attachments"] == 24
    assert not [entry for entry in inventory.blocked if entry.what == "attachment"]


def test_attachments_cover_both_vlans_and_bridges(inventory) -> None:
    refs = {candidate.network_ref for candidate in inventory.attachments}

    assert any(ref.startswith("inst.vlan.") for ref in refs)
    assert "inst.bridge.containers" in refs, "a bridge-attached workload must not be lost"


def test_no_service_can_be_published_yet(inventory) -> None:
    """Zero is the honest answer, and it is not a failure of the model."""
    assert inventory.summary()["publication_candidates"] == 0
    assert inventory.summary()["blocked"] == 29


def test_the_blocked_reasons_separate_data_gaps_from_modelling_questions(inventory) -> None:
    """Four distinct causes, not one undifferentiated backlog.

    A missing policy owner is a decision nobody has recorded. A missing source
    restriction is flow data only the running network can supply. A runtime
    target that is a device rather than a workload is neither: it is a service on
    the device itself, which the model expresses as a host attachment, and it
    needs a modelling answer rather than a measurement.
    """
    counts = {"no policy owner": 0, "no source restriction declared": 0, "no ports declared": 0, "device target": 0}
    for entry in inventory.blocked:
        for part in entry.reason.split("; "):
            if "has no attachment" in part:
                counts["device target"] += 1
            elif part in counts:
                counts[part] += 1

    assert counts == {
        "no policy owner": 29,
        "no source restriction declared": 26,
        "no ports declared": 24,
        "device target": 7,
    }


def test_a_policy_owner_is_missing_everywhere(inventory) -> None:
    """The one gap no amount of traffic observation will close."""
    blocked_on_owner = [entry for entry in inventory.blocked if "no policy owner" in entry.reason]

    assert len(blocked_on_owner) == inventory.summary()["blocked"]


def test_nothing_in_the_inventory_authorizes_anything(inventory) -> None:
    """A candidate is a proposal. There is no grant type in this module at all."""
    import netmodel.intent as intent_module

    exported = set(intent_module.__all__)
    assert not (exported & {"Grant", "authorize", "resolve_grant", "AuthorizedSet"})

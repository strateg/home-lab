"""SEC-STATE: sessions across an epoch change.

The failure the obligation names is an old established or related flow surviving
past its deadline, and the reason it is easy to miss is mechanical: a stateful
enforcer accepts the first packet by matching a rule and every packet after it by
matching the session. Removing the rule stops nothing already running.

So the tests here are mostly about the gap between editing a source and ending a
connection - *live revocation is a time-bounded transition, not a property of
source editing* - and about reverse traffic, which belongs to the authorization
that admitted the session rather than needing one of its own.
"""

from __future__ import annotations

import pytest

from netmodel.interpret import Endpoints
from netmodel.state import (
    Epoch,
    Ledger,
    Revocation,
    Session,
    StateError,
    related_sessions,
    survivors,
    unauthorized_reverse,
)

DNS = Endpoints("zone.lan", "zone.mgmt", "udp", 53)
SSH = Endpoints("zone.guest", "zone.mgmt", "tcp", 22)


def epoch(epoch_id: str, *flows: Endpoints) -> Epoch:
    return Epoch(epoch_id=epoch_id, authorized=frozenset(item.key() for item in flows))


def session(session_id: str, endpoints: Endpoints, *, epoch_id="epoch.old", at=0, related_to=None) -> Session:
    return Session(
        session_id=session_id,
        forward=endpoints,
        epoch_id=epoch_id,
        established_at=at,
        related_to=related_to,
    )


# --- the deadline is what makes a revocation one ---------------------------------


def test_a_revocation_without_a_positive_deadline_is_refused() -> None:
    """A revocation with no deadline is not a lenient one. It is an open permit."""
    for deadline in (0, -1):
        with pytest.raises(StateError, match="unbounded permit"):
            Revocation(epoch_id="epoch.new", deadline_ticks=deadline)


def test_a_session_inside_its_deadline_is_not_a_violation() -> None:
    """Revocation is a transition and transitions take time."""
    active = epoch("epoch.new")  # authorizes nothing
    running = [session("s1", SSH, at=100)]

    found = survivors(sessions=running, active=active, revocation=Revocation("epoch.new", 30), now_ticks=120)

    assert found == []


def test_a_session_past_its_deadline_is_reported() -> None:
    active = epoch("epoch.new")
    running = [session("s1", SSH, at=100)]

    found = survivors(sessions=running, active=active, revocation=Revocation("epoch.new", 30), now_ticks=140)

    assert found, "a session outliving its deadline is exactly what the obligation forbids"
    assert {item.direction for item in found} == {"forward", "reverse"}
    assert all(item.session_id == "s1" for item in found)


def test_removing_the_permit_does_not_end_the_session() -> None:
    """The mechanical fact behind the whole obligation, asserted directly.

    The new epoch authorizes nothing; the session established under the old one
    is still there. Editing the source produced a new desired state and stopped
    no traffic.
    """
    old = epoch("epoch.old", SSH)
    new = epoch("epoch.new")
    running = [session("s1", SSH, epoch_id="epoch.old", at=0)]

    assert old.admits(SSH) and not new.admits(SSH)

    ledger = Ledger()
    for item in running:
        ledger.add(item)

    assert ledger.carried_over(new) == running, "the session outlives the epoch that authorized it"
    assert survivors(sessions=running, active=new, revocation=Revocation("epoch.new", 10), now_ticks=100)


def test_a_session_the_new_epoch_still_authorizes_is_left_alone() -> None:
    """Not everything carried over is a survivor; only what is no longer allowed."""
    new = epoch("epoch.new", DNS)
    running = [session("s1", DNS, epoch_id="epoch.old", at=0)]

    assert survivors(sessions=running, active=new, revocation=Revocation("epoch.new", 10), now_ticks=1000) == []


# --- reverse traffic belongs to the session --------------------------------------


def test_the_reverse_tuple_mirrors_endpoints_and_keeps_the_service_port() -> None:
    """Swapping the port too would describe a different connection."""
    reverse = session("s1", DNS).reverse()

    assert reverse == Endpoints("zone.mgmt", "zone.lan", "udp", 53)


def test_a_revoked_session_is_reported_in_both_directions() -> None:
    """A reverse packet for a revoked session is what an operator actually sees."""
    found = survivors(
        sessions=[session("s1", SSH, at=0)],
        active=epoch("epoch.new"),
        revocation=Revocation("epoch.new", 10),
        now_ticks=100,
    )

    directions = {item.direction: item.flow for item in found}
    assert directions["forward"] == SSH.key()
    assert directions["reverse"] == ("zone.mgmt", "zone.guest", "tcp", 22)


def test_a_reverse_flow_needing_its_own_permit_is_reported_not_repaired() -> None:
    """The model must not silently add a broad reverse rule.

    An epoch that authorizes the forward direction and not the return one is
    describing half of a working connection as unauthorized. That is a modelling
    defect, and hiding it behind a permissive reverse rule is how a broad accept
    nobody meant gets into a plan.
    """
    forward_only = epoch("epoch.new", DNS)

    reported = unauthorized_reverse(sessions=[session("s1", DNS)], active=forward_only)

    assert len(reported) == 1
    assert reported[0].direction == "reverse"
    assert reported[0].flow == ("zone.mgmt", "zone.lan", "udp", 53)


def test_an_epoch_authorizing_both_directions_reports_nothing() -> None:
    both = epoch("epoch.new", DNS, Endpoints("zone.mgmt", "zone.lan", "udp", 53))

    assert unauthorized_reverse(sessions=[session("s1", DNS)], active=both) == []


# --- related flows inherit the parent's fate --------------------------------------


def test_a_related_session_is_reported_with_its_parent() -> None:
    """A child connection has no rule of its own; it lives because the parent did."""
    running = [
        session("s1", SSH, at=0),
        session("s1.data", Endpoints("zone.guest", "zone.mgmt", "tcp", 2222), at=5, related_to="s1"),
    ]

    found = survivors(
        sessions=running, active=epoch("epoch.new"), revocation=Revocation("epoch.new", 10), now_ticks=100
    )

    related = [item for item in found if item.related_to == "s1"]
    assert related, "a related flow surviving is named in the obligation"
    assert "related to s1" in str(related[0])


def test_related_sessions_are_findable_from_the_parent() -> None:
    running = [
        session("s1", SSH),
        session("s1.data", SSH, related_to="s1"),
        session("s2", DNS),
    ]

    assert [item.session_id for item in related_sessions(running, "s1")] == ["s1.data"]


# --- the model reads no clock -------------------------------------------------------


def test_time_is_a_supplied_tick_and_never_read_from_a_clock() -> None:
    """Otherwise the same inputs answer differently on different days.

    The contract keeps timestamps out of semantic identity and forbids one
    universal timeout; both a deadline and a current tick are arguments.
    """
    import ast
    import inspect
    from pathlib import Path

    signature = inspect.signature(survivors)
    assert signature.parameters["now_ticks"].default is inspect.Parameter.empty

    module = Path(__file__).resolve().parents[2] / "netmodel" / "state.py"
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not (imported & {"time", "datetime", "calendar"})


# --- not vacuous ----------------------------------------------------------------------


def test_the_survivor_check_can_report_and_can_stay_silent() -> None:
    """A checker that never fires and one that always fires are both useless."""
    revoked = epoch("epoch.new")
    still_allowed = epoch("epoch.new", SSH)
    running = [session("s1", SSH, at=0)]
    revocation = Revocation("epoch.new", 10)

    assert survivors(sessions=running, active=revoked, revocation=revocation, now_ticks=100)
    assert survivors(sessions=running, active=still_allowed, revocation=revocation, now_ticks=100) == []
    assert survivors(sessions=[], active=revoked, revocation=revocation, now_ticks=100) == []


def test_a_survivor_message_names_the_session_the_age_and_the_deadline() -> None:
    found = survivors(
        sessions=[session("s1", SSH, at=10)],
        active=epoch("epoch.new"),
        revocation=Revocation("epoch.new", 30),
        now_ticks=200,
    )

    rendered = str(found[0])
    assert "s1" in rendered and "190 ticks old" in rendered and "deadline 30" in rendered

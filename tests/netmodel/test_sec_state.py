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
    NEW_CONNECTION,
    ORPHANED_RELATED,
    STALE_SESSION,
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


def revocation(*, effective_at: int = 100, deadline: int = 30, revoked="epoch.old", new="epoch.new") -> Revocation:
    """The transition under test: which epoch ends, which replaces it, from when."""
    return Revocation(
        epoch_id=revoked, superseded_by=new, effective_at=effective_at, deadline_ticks=deadline
    )


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
            revocation(deadline=deadline)


def test_a_revocation_must_name_the_transition_it_belongs_to() -> None:
    """Without the epoch that replaces this one there is nothing to measure from."""
    with pytest.raises(StateError, match="epoch replacing this one"):
        Revocation(epoch_id="epoch.old", superseded_by="", effective_at=0, deadline_ticks=10)
    with pytest.raises(StateError, match="cannot supersede itself"):
        Revocation(epoch_id="epoch.old", superseded_by="epoch.old", effective_at=0, deadline_ticks=10)
    with pytest.raises(StateError, match="effective_at"):
        Revocation(epoch_id="epoch.old", superseded_by="epoch.new", effective_at=-1, deadline_ticks=10)


def test_a_revocation_from_another_transition_is_refused() -> None:
    """It says nothing about this one, and answering with it answers a different question."""
    with pytest.raises(StateError, match="says nothing about this one"):
        survivors(
            sessions=[session("s1", SSH)],
            active=epoch("epoch.new"),
            revocation=revocation(new="epoch.other"),
            now_ticks=1000,
        )

    # The epoch being revoked cannot also be the one in force. That is refused at
    # construction rather than here: a revocation whose two ends are the same
    # epoch describes no transition, whatever it is later compared against.
    with pytest.raises(StateError, match="cannot supersede itself"):
        Revocation(epoch_id="epoch.new", superseded_by="epoch.new", effective_at=0, deadline_ticks=10)


# --- the deadline runs from the revocation, not from the session --------------------


def test_a_long_running_session_is_not_expired_by_the_epoch_change_itself() -> None:
    """The defect this replaced: `now - established_at` measured the wrong interval.

    A session opened at tick 0, a revocation effective at 100 with a 10-tick
    deadline, asked at tick 100. Its age is 100 and the deadline is 10, so the old
    comparison reported it immediately - before the agreed grace had begun.
    """
    found = survivors(
        sessions=[session("s1", SSH, at=0)],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=100, deadline=10),
        now_ticks=100,
    )

    assert found == [], "the grace period starts when revocation does"


@pytest.mark.parametrize(
    ("now", "expected"),
    [(100, False), (109, False), (110, False), (111, True), (1000, True)],
)
def test_the_deadline_is_absolute_and_checked_at_its_boundary(now: int, expected: bool) -> None:
    """effective_at 100 + deadline 10 = 110. At 110 it is not yet past."""
    found = survivors(
        sessions=[session("s1", SSH, at=0)],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=100, deadline=10),
        now_ticks=now,
    )

    assert bool(found) is expected
    if found:
        assert {item.kind for item in found} == {STALE_SESSION}
        assert found[0].deadline == 110


def test_a_connection_opened_after_the_revocation_gets_no_grace() -> None:
    """A different failure, and it was reported as the same one.

    Nothing is winding this session down - it was opened under a policy that does
    not authorize it, which says the new policy is not actually in force. Giving
    it the transition's grace period would excuse exactly the thing the grace
    period is not for.
    """
    found = survivors(
        sessions=[session("s2", SSH, at=105)],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=100, deadline=10),
        now_ticks=106,
    )

    assert found, "a new unauthorized connection is a violation immediately"
    assert {item.kind for item in found} == {NEW_CONNECTION}
    assert "new connection rather than one the transition is winding down" in str(found[0])


def test_the_two_kinds_are_distinguished_in_one_run() -> None:
    found = survivors(
        sessions=[session("old", SSH, at=0), session("new", DNS, at=105)],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=100, deadline=10),
        now_ticks=200,
    )

    kinds = {item.session_id: item.kind for item in found}
    assert kinds == {"old": STALE_SESSION, "new": NEW_CONNECTION}


def test_a_session_past_its_deadline_is_reported() -> None:
    found = survivors(
        sessions=[session("s1", SSH, at=100)],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=120, deadline=30),
        now_ticks=200,
    )

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
    assert survivors(
        sessions=running, active=new, revocation=revocation(effective_at=10, deadline=10), now_ticks=100
    )


def test_a_session_the_new_epoch_still_authorizes_is_left_alone() -> None:
    """Not everything carried over is a survivor; only what is no longer allowed."""
    new = epoch("epoch.new", DNS)
    running = [session("s1", DNS, epoch_id="epoch.old", at=0)]

    assert survivors(sessions=running, active=new, revocation=revocation(), now_ticks=1000) == []


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
        revocation=revocation(effective_at=10, deadline=10),
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


def test_a_related_session_is_judged_by_its_parent_not_by_its_own_tuple() -> None:
    """A child connection has no rule of its own; it lives because the parent did.

    The data connection runs on 2222, which no epoch mentions in either
    direction. Asking about its own tuple answers a different question - and
    would report every related session as unauthorized under every epoch.
    """
    control = session("s1", SSH, at=0)
    data = session("s1.data", Endpoints("zone.guest", "zone.mgmt", "tcp", 2222), at=5, related_to="s1")

    found = survivors(
        sessions=[control, data],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=10, deadline=10),
        now_ticks=100,
    )

    related = [item for item in found if item.related_to == "s1"]
    assert related, "a related flow surviving is named in the obligation"
    assert "related to s1" in str(related[0])


def test_a_related_session_survives_while_its_parent_is_authorized() -> None:
    """Inheritance is the whole point, and it has to work in both directions.

    The epoch authorizes the control connection and says nothing about port 2222.
    Judged on its own the data connection is unauthorized; judged by its parent -
    which is what admitted it - it is fine.
    """
    control = session("s1", SSH, at=0)
    data = session("s1.data", Endpoints("zone.guest", "zone.mgmt", "tcp", 2222), at=5, related_to="s1")

    found = survivors(
        sessions=[control, data],
        active=epoch("epoch.new", SSH),
        revocation=revocation(effective_at=10, deadline=10),
        now_ticks=1000,
    )

    assert found == [], "a related session inherits its parent's authorization"


def test_a_chain_of_related_sessions_follows_to_its_root() -> None:
    chain = [
        session("root", SSH, at=0),
        session("child", Endpoints("zone.guest", "zone.mgmt", "tcp", 2222), at=1, related_to="root"),
        session("grandchild", Endpoints("zone.guest", "zone.mgmt", "tcp", 3333), at=2, related_to="child"),
    ]

    assert (
        survivors(
            sessions=chain,
            active=epoch("epoch.new", SSH),
            revocation=revocation(effective_at=10, deadline=10),
            now_ticks=1000,
        )
        == []
    )
    revoked = survivors(
        sessions=chain,
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=10, deadline=10),
        now_ticks=1000,
    )
    assert {item.session_id for item in revoked} == {"root", "child", "grandchild"}


def test_a_related_session_whose_parent_is_not_listed_is_reported() -> None:
    """There is nothing to inherit from, and assuming authorization would be inventing it."""
    orphan = session("orphan", Endpoints("zone.guest", "zone.mgmt", "tcp", 2222), at=0, related_to="gone")

    found = survivors(
        sessions=[orphan],
        active=epoch("epoch.new", SSH),
        revocation=revocation(effective_at=10, deadline=10),
        now_ticks=20,
    )

    assert {item.kind for item in found} == {ORPHANED_RELATED}
    assert "not in the session set" in str(found[0])


def test_a_cycle_of_related_sessions_is_an_orphan_not_a_hang() -> None:
    cycle = [
        session("a", SSH, at=0, related_to="b"),
        session("b", SSH, at=0, related_to="a"),
    ]

    found = survivors(
        sessions=cycle,
        active=epoch("epoch.new", SSH),
        revocation=revocation(effective_at=10, deadline=10),
        now_ticks=20,
    )

    assert {item.kind for item in found} == {ORPHANED_RELATED}


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
    transition = revocation(effective_at=10, deadline=10)

    assert survivors(sessions=running, active=revoked, revocation=transition, now_ticks=100)
    assert survivors(sessions=running, active=still_allowed, revocation=transition, now_ticks=100) == []
    assert survivors(sessions=[], active=revoked, revocation=transition, now_ticks=100) == []


def test_a_survivor_message_names_the_session_the_age_and_the_absolute_deadline() -> None:
    found = survivors(
        sessions=[session("s1", SSH, at=10)],
        active=epoch("epoch.new"),
        revocation=revocation(effective_at=20, deadline=30),
        now_ticks=200,
    )

    rendered = str(found[0])
    assert "s1" in rendered and "190 ticks old" in rendered
    assert "deadline 50" in rendered, "the deadline an operator needs is the absolute one"

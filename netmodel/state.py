"""Sessions across an epoch change — SEC-STATE.

*Forward and reverse admitted session traffic remains authorized under the active
epoch; revocations meet the declared deadline.* The counterexample is an old
established or related flow surviving past its deadline, and it is worth being
precise about why that is easy to miss.

A stateful enforcer accepts the first packet of a session by matching a rule and
accepts every packet after it by matching **the session**. So removing the rule
stops nothing that is already running. The contract puts it plainly: *live
revocation is a time-bounded transition, not a property of source editing.*
Editing the source produces a new desired epoch; the sessions established under
the old one keep flowing until something ends them, and if nothing does, the
permit was revoked only on paper.

Two consequences shape this module.

**Reverse traffic is part of the authorization, not a separate grant.** A session
admitted forward carries return packets whose tuple is the mirror image. They are
authorized because the session was, and modelling them as an independent flow
needing its own permit produces either a broad reverse rule nobody meant or a
model that says half of every working connection is unauthorized.

**A deadline is per profile, and required.** There is no default here; the
contract says not to invent one universal timeout, and a revocation with no stated
deadline is not a revocation with a generous one - it is an unbounded permit.

**The deadline runs from the revocation, not from the session.** The first version
compared `now - established_at` against the deadline, which measures the wrong
interval: a connection that had been running for an hour was over its deadline the
instant the epoch changed, before the agreed grace had begun, and a connection
opened just before the change got a full grace period counted from its own start.
The model also had no way to say *when* revocation began. `Revocation` now carries
`effective_at`, the deadline is absolute, and a session opened after that moment
gets no grace at all - it is not a session the transition is winding down, it is a
new connection under a policy that does not authorize it. Those are different
failures and they are reported as different kinds.

**A revocation belongs to a transition.** `epoch_id` names the epoch being
revoked and `superseded_by` names the one replacing it, and both are checked
against the active epoch. A revocation carrying the wrong pair says nothing about
this transition, and using it would be answering a question nobody asked.

**A related session inherits its parent's fate.** A data connection spawned by a
control connection is authorized because its parent was, so it is judged by the
parent's authorization rather than its own tuple - which is usually on a port no
rule mentions. Filtering them in a helper and judging them individually elsewhere
meant the inheritance existed in the documentation and not in the check.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from netmodel.interpret import Endpoints


class StateError(ValueError):
    """Raised when a session, epoch or revocation is malformed."""


@dataclass(frozen=True, slots=True)
class Epoch:
    """One policy epoch and the flows it authorizes."""

    epoch_id: str
    authorized: frozenset[tuple[str, str, str, int]]

    def admits(self, endpoints: Endpoints) -> bool:
        return endpoints.key() in self.authorized


@dataclass(frozen=True, slots=True)
class Session:
    """A connection admitted under some epoch, still running.

    `established_at` is a monotonic tick rather than a wall clock: the model
    compares it with a deadline, and reading a clock would make the same inputs
    answer differently on different days.
    """

    session_id: str
    forward: Endpoints
    epoch_id: str
    established_at: int
    related_to: str | None = None

    def __post_init__(self) -> None:
        if not str(self.session_id or "").strip():
            raise StateError("a session must be identifiable to be revoked")
        if self.established_at < 0:
            raise StateError(f"{self.session_id}: established_at must not be negative")

    def reverse(self) -> Endpoints:
        """The return direction of the same session.

        Source and destination swap; the port stays the service port, because it
        identifies the session rather than the direction. A reverse tuple with the
        ports swapped as well would describe a different connection.
        """
        return Endpoints(
            source=self.forward.destination,
            destination=self.forward.source,
            protocol=self.forward.protocol,
            port=self.forward.port,
        )


@dataclass(frozen=True, slots=True)
class Revocation:
    """An instruction to end sessions: which transition, when it began, how long.

    `epoch_id` is the epoch being revoked and `superseded_by` the one replacing
    it. `effective_at` is the tick the revocation began - the moment the model
    could not express at all, and without which a deadline has nothing to be
    measured from.
    """

    epoch_id: str
    superseded_by: str
    effective_at: int
    deadline_ticks: int

    def __post_init__(self) -> None:
        if self.deadline_ticks <= 0:
            raise StateError(
                f"{self.epoch_id}: a revocation deadline must be positive; "
                "a revocation with no deadline is an unbounded permit"
            )
        if self.effective_at < 0:
            raise StateError(f"{self.epoch_id}: effective_at must not be negative")
        if not str(self.superseded_by or "").strip():
            raise StateError(
                f"{self.epoch_id}: a revocation must name the epoch replacing this one; "
                "without it there is no transition to bind the deadline to"
            )
        if self.superseded_by == self.epoch_id:
            raise StateError(f"{self.epoch_id}: an epoch cannot supersede itself")

    @property
    def deadline_at(self) -> int:
        """The absolute tick after which a carried-over session is a violation."""
        return self.effective_at + self.deadline_ticks


# The three ways a session can be a violation. They are named rather than merged
# because the operator response differs: a stale session is ended, a new
# connection means the new policy is not actually in force, and an orphan means
# the ledger cannot say what authorized it.
STALE_SESSION = "stale_session"
NEW_CONNECTION = "new_connection"
ORPHANED_RELATED = "orphaned_related"


@dataclass(frozen=True, slots=True)
class Survivor:
    """A session still running that the active epoch no longer authorizes."""

    session_id: str
    flow: tuple[str, str, str, int]
    direction: str
    established_at: int
    age: int
    deadline: int
    related_to: str | None = None
    kind: str = STALE_SESSION

    def __str__(self) -> str:
        source, destination, protocol, port = self.flow
        related = f" (related to {self.related_to})" if self.related_to else ""
        where = f"{self.session_id}{related} {direction_label(self.direction)} {source} -> {destination} {protocol}/{port}"
        if self.kind == NEW_CONNECTION:
            return (
                f"{where} was opened at tick {self.established_at}, after the revocation took "
                "effect, and the active epoch does not authorize it; this is a new connection "
                "rather than one the transition is winding down"
            )
        if self.kind == ORPHANED_RELATED:
            return (
                f"{where} is related to {self.related_to}, which is not in the session set; "
                "an inherited authorization cannot be checked against a parent nobody listed"
            )
        return (
            f"{where} is {self.age} ticks old, deadline {self.deadline}, "
            "and the active epoch does not authorize it"
        )


def direction_label(direction: str) -> str:
    return {"forward": "forward", "reverse": "reverse"}.get(direction, direction)


def survivors(
    *,
    sessions: Iterable[Session],
    active: Epoch,
    revocation: Revocation,
    now_ticks: int,
) -> list[Survivor]:
    """Sessions the active epoch does not authorize and that time no longer excuses.

    Three distinct failures, and conflating them was the defect:

    * a **stale session** established before the revocation took effect and still
      running after `effective_at + deadline_ticks`. Inside that window it is not
      a violation - revocation is a transition and transitions take time.
    * a **new connection** opened at or after `effective_at` that the active epoch
      does not authorize. No grace applies: nothing is winding it down, and its
      existence says the new policy is not actually in force.
    * an **orphaned related** session whose parent is not in the set. Its
      authorization is inherited, so without the parent there is nothing to
      inherit from, and calling that authorized would be an assumption.

    A related session is judged by its **parent's** forward authorization. Its own
    tuple is typically on a port no rule mentions, so asking about it directly
    answers a different question.

    Both directions are reported for a session in violation: a reverse packet
    arriving for a revoked session is exactly what an operator sees.
    """
    listed = {session.session_id: session for session in sessions}
    if revocation.superseded_by != active.epoch_id:
        raise StateError(
            f"revocation supersedes {revocation.superseded_by!r} and the active epoch is "
            f"{active.epoch_id!r}; a revocation from another transition says nothing about this one"
        )
    found: list[Survivor] = []
    for session in sorted(listed.values(), key=lambda item: item.session_id):
        authority, orphan = _authority_for(session, listed)
        if orphan:
            found.extend(_both_directions(session, revocation, now_ticks, ORPHANED_RELATED))
            continue
        if active.admits(authority.forward):
            continue

        if session.established_at >= revocation.effective_at:
            found.extend(_both_directions(session, revocation, now_ticks, NEW_CONNECTION))
        elif now_ticks > revocation.deadline_at:
            found.extend(_both_directions(session, revocation, now_ticks, STALE_SESSION))
    return found


def _authority_for(
    session: Session, listed: Mapping[str, Session]
) -> tuple[Session, bool]:
    """The session whose authorization decides this one, and whether it is missing.

    A chain of related sessions is followed to its root. A cycle is treated as an
    orphan: it names a parent that cannot be an authority for anything.
    """
    seen: set[str] = set()
    current = session
    while current.related_to is not None:
        if current.related_to in seen:
            return session, True
        seen.add(current.related_to)
        parent = listed.get(current.related_to)
        if parent is None:
            return session, True
        current = parent
    return current, False


def _both_directions(
    session: Session, revocation: Revocation, now_ticks: int, kind: str
) -> list[Survivor]:
    return [
        Survivor(
            session_id=session.session_id,
            flow=endpoints.key(),
            direction=direction,
            established_at=session.established_at,
            age=now_ticks - session.established_at,
            deadline=revocation.deadline_at,
            related_to=session.related_to,
            kind=kind,
        )
        for direction, endpoints in (("forward", session.forward), ("reverse", session.reverse()))
    ]


def unauthorized_reverse(*, sessions: Iterable[Session], active: Epoch) -> list[Survivor]:
    """Sessions the epoch authorizes forward but whose reverse it does not admit.

    This is not a defect in the sources; it is a defect in a model that treats a
    return packet as an independent flow needing its own permit. It is reported
    so the difference is visible rather than silently repaired by a broad reverse
    rule.
    """
    reported: list[Survivor] = []
    for session in sorted(sessions, key=lambda item: item.session_id):
        if not active.admits(session.forward):
            continue
        if active.admits(session.reverse()):
            continue
        reported.append(
            Survivor(
                session_id=session.session_id,
                flow=session.reverse().key(),
                direction="reverse",
                established_at=session.established_at,
                age=0,
                deadline=0,
                related_to=session.related_to,
            )
        )
    return reported


@dataclass
class Ledger:
    """Sessions grouped by the epoch that admitted them."""

    by_epoch: dict[str, list[Session]] = field(default_factory=dict)

    def add(self, session: Session) -> None:
        self.by_epoch.setdefault(session.epoch_id, []).append(session)

    def carried_over(self, active: Epoch) -> list[Session]:
        """Everything established under some other epoch and still listed."""
        return [
            session
            for epoch_id, items in sorted(self.by_epoch.items())
            if epoch_id != active.epoch_id
            for session in sorted(items, key=lambda item: item.session_id)
        ]


def related_sessions(sessions: Iterable[Session], parent_id: str) -> list[Session]:
    """Sessions a parent spawned. They inherit its fate, not their own rule."""
    return [session for session in sessions if session.related_to == parent_id]


__all__ = [
    "NEW_CONNECTION",
    "ORPHANED_RELATED",
    "STALE_SESSION",
    "Epoch",
    "Ledger",
    "Revocation",
    "Session",
    "StateError",
    "Survivor",
    "related_sessions",
    "survivors",
    "unauthorized_reverse",
]

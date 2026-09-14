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
    """An instruction to end sessions, with the deadline that makes it one."""

    epoch_id: str
    deadline_ticks: int

    def __post_init__(self) -> None:
        if self.deadline_ticks <= 0:
            raise StateError(
                f"{self.epoch_id}: a revocation deadline must be positive; "
                "a revocation with no deadline is an unbounded permit"
            )


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

    def __str__(self) -> str:
        source, destination, protocol, port = self.flow
        related = f" (related to {self.related_to})" if self.related_to else ""
        return (
            f"{self.session_id}{related} {direction_label(self.direction)} "
            f"{source} -> {destination} {protocol}/{port} is {self.age} ticks old, "
            f"deadline {self.deadline}, and the active epoch does not authorize it"
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
    """Sessions past the deadline that the active epoch does not authorize.

    A session inside its deadline is not a violation: revocation is a transition
    and transitions take time. What the obligation forbids is one that is still
    running after the deadline the profile declared.

    Both directions are checked against the same authorization. A session whose
    forward flow is authorized carries its reverse; a session whose forward flow
    is not carries nothing, and its reverse is reported as well, because a
    reverse packet arriving for a revoked session is exactly the observable an
    operator would see.
    """
    found: list[Survivor] = []
    for session in sorted(sessions, key=lambda item: item.session_id):
        age = now_ticks - session.established_at
        if age <= revocation.deadline_ticks:
            continue
        if active.admits(session.forward):
            continue
        for direction, endpoints in (("forward", session.forward), ("reverse", session.reverse())):
            found.append(
                Survivor(
                    session_id=session.session_id,
                    flow=endpoints.key(),
                    direction=direction,
                    established_at=session.established_at,
                    age=age,
                    deadline=revocation.deadline_ticks,
                    related_to=session.related_to,
                )
            )
    return found


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

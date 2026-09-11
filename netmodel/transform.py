"""Destination translation, and what it must not lose.

A publication with a translating mechanism changes where a packet goes. It does
not change who was allowed to send it, and the difference is the whole of SEC-NAT:
*authorization survives every composed transform without merging differently
authorized originals*.

The failure the obligation names is concrete. Two publications map to one backend.
One is an approved permit, the other is not. If the plan is evaluated in backend
coordinates, both arrive as the same tuple, and the unauthorized one is accepted
because the authorized one made the rule exist. Nothing in the rendered ruleset
looks wrong afterwards - the two flows became one before any rule saw them.

So a transform here never rewrites the original. It records it. Applying two
transforms composes the path and keeps the same original, because the client-facing
tuple is a property of the flow, not of the last hop that touched it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Iterable

from netmodel.interpret import Endpoints, FlowEvent


class TransformError(ValueError):
    """Raised when a transform is malformed or would lose the original."""


@dataclass(frozen=True, slots=True)
class DestinationNat:
    """A publication's frontend-to-backend mapping."""

    publication_id: str
    frontend: Endpoints
    backend_destination: str
    backend_port: int

    def __post_init__(self) -> None:
        if not str(self.publication_id or "").strip():
            raise TransformError("a transform must name the publication it realizes")
        if self.backend_port < 1 or self.backend_port > 65535:
            raise TransformError(f"{self.publication_id}: backend port {self.backend_port} is not a port")

    def matches(self, event: FlowEvent) -> bool:
        current = event.current
        return (
            current.destination == self.frontend.destination
            and current.protocol == self.frontend.protocol
            and current.port == self.frontend.port
            and current.source in {self.frontend.source, current.source}
        )


def apply_nat(transform: DestinationNat, event: FlowEvent) -> FlowEvent:
    """Translate the destination, preserving the original tuple.

    If the event already carries an original, it is kept: a second transform
    composes onto the path and does not become the new origin. The client-facing
    tuple is a property of the flow.
    """
    if not transform.matches(event):
        raise TransformError(
            f"{transform.publication_id} does not match {event.current.key()}; "
            "applying it anyway would invent a path"
        )

    original = event.original if event.original is not None else event.current
    publication = event.publication_id or transform.publication_id

    return replace(
        event,
        destination=transform.backend_destination,
        port=transform.backend_port,
        original=original,
        publication_id=publication,
    )


def compose(event: FlowEvent, *transforms: DestinationNat) -> FlowEvent:
    """Apply transforms in path order. The original survives all of them."""
    for transform in transforms:
        event = apply_nat(transform, event)
    return event


def merges_distinct_originals(
    events: Iterable[FlowEvent], *, decided_by: Callable[[FlowEvent], str | None]
) -> list[tuple[str, str, str]]:
    """Flows that one decision covers although they began differently.

    The first version of this compared current tuples for equality, which is
    wrong and the tests said so: a destination NAT preserves the source, so two
    flows from different zones to one backend never become the same tuple. They
    are still a collapse, because one rule written in backend coordinates decides
    both, and that rule cannot see which frontend authorized which.

    So the grouping is by **decision**, not by tuple. `decided_by` returns
    whatever identifies the decision - a rule origin, a position - and the
    function stays ignorant of how the decision was reached, which keeps it from
    importing the algebra it is meant to be checked against.

    A decision covering one original many times is not a merge. A decision
    covering two originals is the counterexample SEC-NAT names.
    """
    by_decision: dict[str, list[FlowEvent]] = {}
    for event in events:
        decision = decided_by(event)
        if decision is None:
            continue
        by_decision.setdefault(decision, []).append(event)

    collapses: list[tuple[str, str, str]] = []
    for decision, covered in sorted(by_decision.items()):
        originals = {event.authorizing.key(): event for event in covered}
        if len(originals) < 2:
            continue
        ordered = [originals[key] for key in sorted(originals)]
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                collapses.append(
                    (
                        decision,
                        f"{left.authorizing.key()} via {left.publication_id}",
                        f"{right.authorizing.key()} via {right.publication_id}",
                    )
                )
    return collapses


__all__ = ["DestinationNat", "TransformError", "apply_nat", "compose", "merges_distinct_originals"]

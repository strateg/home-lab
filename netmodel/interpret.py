"""Read a plan and say what it does to a flow. Nothing else.

This is `Exec(R, f, path, state)` from the ADR 0119 formal contract, reduced to
the bounded subset the model supports: a first-match walk over rules ordered for
one execution context, returning accept, deny or unsupported.

**It knows nothing about intent.** It does not import `netmodel.policy` or
`netmodel.lower`, and a test asserts that. The reason is the whole design of G3:
if the oracle shared the producer's decision code, a differential between them
would prove only that the code agrees with itself. An oracle is worth having when
it can disagree.

`unsupported` is a real verdict, not a soft deny. A plan containing something this
interpreter cannot evaluate must say so, because silently treating it as a deny
would report a safe result for a rule set nobody understood - and treating it as
an accept needs no comment. It is a third outcome and callers handle it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class Verdict(Enum):
    ACCEPT = "accept"
    DENY = "deny"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class Endpoints:
    """One tuple of who, to whom, over what."""

    source: str
    destination: str
    protocol: str
    port: int

    def key(self) -> tuple[str, str, str, int]:
        return (self.source, self.destination, self.protocol, self.port)


@dataclass(frozen=True, slots=True)
class FlowEvent:
    """One concrete flow, with both tuples the formal contract requires.

    The fields on the event are the **current** coordinates - what a rule at this
    point in the path matches on. `original` holds the client-facing tuple the
    flow arrived with, and is `None` when nothing has transformed it.

    Keeping both is what makes SEC-NAT checkable at all. Authorization is decided
    in original coordinates; a destination NAT changes where a packet goes, never
    who was allowed to send it. Discard the original and two frontends mapped to
    one backend become indistinguishable after translation, which is exactly the
    collapse the obligation names.
    """

    source: str
    destination: str
    protocol: str
    port: int
    enforcer: str
    routing_domain: str
    family: str
    hook: str
    chain: str
    original: Endpoints | None = None
    publication_id: str | None = None

    @property
    def current(self) -> Endpoints:
        return Endpoints(self.source, self.destination, self.protocol, self.port)

    @property
    def authorizing(self) -> Endpoints:
        """The tuple authorization is decided on: the original if there is one."""
        return self.original if self.original is not None else self.current


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: Verdict
    matched: str | None
    position: int | None

    def __str__(self) -> str:
        if self.matched is None:
            return f"{self.verdict.value} (no rule matched)"
        return f"{self.verdict.value} by {self.matched} at position {self.position}"


def _context_matches(entry, event: FlowEvent) -> bool:
    context = entry.rule.context
    return (
        context.enforcer == event.enforcer
        and context.routing_domain == event.routing_domain
        and context.family == event.family
        and context.hook == event.hook
        and context.chain == event.chain
    )


def _flow_matches(entry, event: FlowEvent) -> bool:
    flow = entry.rule.flow
    if event.source not in flow.sources or event.destination not in flow.destinations:
        return False
    # A terminal is not a special matching rule. It closes its scope because it
    # is built with the scope's endpoints and an any-transport, and those are
    # properties of the rule rather than of the flag.
    #
    # Reading the flag as "ignore the transport" was the divergence a review
    # found on the framework side: a terminal stating `tcp/53` was interpreted as
    # an unconditional deny while a consumer received the narrow predicate, so
    # one plan meant two things. Honouring the field turns that into an unmatched
    # flow, which `unterminated` reports.
    # An ordinary rule may also constrain every transport. That is a shape a rule
    # can have, not a property of being terminal - the sources' one mandatory
    # deny is exactly this, and reading it as a ports rule with no ports would
    # match nothing at all.
    if flow.protocol == "any" and flow.ports is None:
        return True
    return event.protocol == flow.protocol and event.port in (flow.ports or frozenset())


def unterminated(plan: Sequence, space: Sequence[FlowEvent]) -> list[FlowEvent]:
    """Flows inside the probed space that reach no rule at all.

    Not an accept and not a deny: the outcome belongs to whatever the backend
    does by default, and on a default-allow enforcer that is an open flow. A
    plan whose terminal does not cover the residue of its scope leaves exactly
    these behind, and they are a failure in their own right - not a consequence
    of somebody having declared that the flow must keep working.

    It is deliberately not repaired by reading an unmatched flow as a deny. That
    would credit the plan with a rule it does not carry.
    """
    return [event for event in space if interpret(plan, event).verdict is Verdict.UNSUPPORTED]


def interpret(plan: Sequence, event: FlowEvent) -> Decision:
    """First match wins, in the order the plan was emitted.

    No rule matching is not an accept. A plan with no terminal rule that matches
    nothing leaves the outcome to the backend's own default, which this
    interpreter does not know - so it says `unsupported` rather than inventing
    one. Default-deny is a property of a backend, not of a rule list.
    """
    for entry in plan:
        if not _context_matches(entry, event):
            continue
        if not _flow_matches(entry, event):
            continue
        verdict = Verdict.ACCEPT if entry.rule.effect.value == "permit" else Verdict.DENY
        return Decision(verdict=verdict, matched=entry.rule.origin, position=entry.position)

    return Decision(verdict=Verdict.UNSUPPORTED, matched=None, position=None)


def accepted_flows(plan: Sequence, events: Sequence[FlowEvent]) -> list[FlowEvent]:
    """Every event this plan accepts. The `Accept(R)` of the formal contract."""
    return [event for event in events if interpret(plan, event).verdict is Verdict.ACCEPT]


__all__ = ["Decision", "FlowEvent", "Verdict", "accepted_flows", "interpret", "unterminated"]

"""SEC-NAT: authorization survives a transform without merging distinct originals.

The obligation names its counterexample, and it is worth stating plainly because
nothing about it looks wrong afterwards: an approved frontend and an unauthorized
direct or backend flow collapse. Two publications map to one backend; one is
permitted and one is not; and if the plan is evaluated in backend coordinates the
two arrive as the same tuple. The unauthorized flow is then accepted by a rule
that exists because of the authorized one, and the rendered ruleset is clean.

The split these tests pin: a rule matches the **current** tuple, because that is
what a device does at that point in the path. Authorization is decided on the
**original**, because a destination NAT changes where a packet goes and never who
was allowed to send it.
"""

from __future__ import annotations

import dataclasses

import pytest

from netmodel.interpret import Endpoints, FlowEvent, Verdict, interpret
from netmodel.lower import lower
from netmodel.plan import ExecutionContext
from netmodel.policy import (
    BINDING_DESTINATION,
    BINDING_SOURCE,
    Activation,
    Binding,
    Effect,
    PolicyTemplate,
    authorize,
    resolve_grant,
)
from netmodel.transform import DestinationNat, TransformError, apply_nat, compose, merges_distinct_originals

CONTEXT = ExecutionContext(
    enforcer="rtr-chateau", routing_domain="main", family="ipv4", hook="forward", chain="managed"
)
ENDPOINTS = ("zone.lan", "zone.guest", "backend.web")


def event(source: str, destination: str, protocol: str, port: int, **extra) -> FlowEvent:
    return FlowEvent(
        source=source,
        destination=destination,
        protocol=protocol,
        port=port,
        enforcer=CONTEXT.enforcer,
        routing_domain=CONTEXT.routing_domain,
        family=CONTEXT.family,
        hook=CONTEXT.hook,
        chain=CONTEXT.chain,
        **extra,
    )


def permit(policy_id: str, port: int) -> PolicyTemplate:
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=BINDING_SOURCE,
        destination=BINDING_DESTINATION,
        protocol="tcp",
        ports=frozenset({port}),
        owner="infra-admin",
        rationale="published service",
    )


def grant_for(policy_id: str, port: int, *, source: str, destination: str):
    template = permit(policy_id, port)
    return resolve_grant(
        template,
        Binding(
            binding_id=f"bind.{policy_id}",
            policy_id=policy_id,
            sources=frozenset({source}),
            destinations=frozenset({destination}),
            approved=True,
        ),
    )


# --- the original survives -------------------------------------------------------


def test_a_transform_records_the_original_rather_than_replacing_it() -> None:
    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )

    translated = apply_nat(nat, event("zone.lan", "edge.public", "tcp", 443))

    assert translated.current.key() == ("zone.lan", "backend.web", "tcp", 8080)
    assert translated.authorizing.key() == ("zone.lan", "edge.public", "tcp", 443)
    assert translated.publication_id == "pub.web"


def test_composing_two_transforms_keeps_the_first_original() -> None:
    """The client-facing tuple is a property of the flow, not of the last hop."""
    first = DestinationNat(
        publication_id="pub.edge",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="proxy.internal",
        backend_port=8443,
    )
    second = DestinationNat(
        publication_id="pub.proxy",
        frontend=Endpoints("zone.lan", "proxy.internal", "tcp", 8443),
        backend_destination="backend.web",
        backend_port=8080,
    )

    result = compose(event("zone.lan", "edge.public", "tcp", 443), first, second)

    assert result.current.key() == ("zone.lan", "backend.web", "tcp", 8080)
    assert result.authorizing.key() == ("zone.lan", "edge.public", "tcp", 443)


def test_an_untransformed_flow_authorizes_on_its_own_tuple() -> None:
    direct = event("zone.guest", "backend.web", "tcp", 8080)

    assert direct.original is None
    assert direct.authorizing.key() == direct.current.key()


def test_applying_a_transform_that_does_not_match_is_refused() -> None:
    """Applying it anyway would invent a path the flow never took."""
    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )

    with pytest.raises(TransformError, match="does not match"):
        apply_nat(nat, event("zone.lan", "edge.other", "tcp", 443))


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_a_backend_port_outside_the_range_is_refused(port: int) -> None:
    with pytest.raises(TransformError, match="not a port"):
        DestinationNat(
            publication_id="pub.web",
            frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
            backend_destination="backend.web",
            backend_port=port,
        )


# --- the collapse the obligation names ---------------------------------------------


def _broad_backend_plan():
    """What a naive publication lowering emits: a rule in backend coordinates.

    The frontend's source restriction is not carried into it, which is the shape
    the obligation is about - the rule can no longer tell which frontend, or
    whether there was one.
    """
    template = PolicyTemplate(
        policy_id="policy.backend",
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=BINDING_SOURCE,
        destination=BINDING_DESTINATION,
        protocol="tcp",
        ports=frozenset({8080}),
        owner="infra-admin",
        rationale="published service",
    )
    grant = resolve_grant(
        template,
        Binding(
            binding_id="bind.backend",
            policy_id="policy.backend",
            sources=frozenset(ENDPOINTS),  # every zone: the restriction was lost
            destinations=frozenset({"backend.web"}),
            approved=True,
        ),
    )
    return lower(grants=[grant], guards={}, context=CONTEXT, endpoints=ENDPOINTS, protocols=("tcp",))


def _decider(plan):
    def decide(item: FlowEvent) -> str | None:
        decision = interpret(plan, item)
        return decision.matched if decision.verdict is Verdict.ACCEPT else None

    return decide


def test_one_backend_rule_covering_two_origins_is_detected_as_a_collapse() -> None:
    """The counterexample, grouped by the decision that covers both.

    A destination NAT preserves the source, so these two never become the same
    tuple - the first version of this test assumed they would and was wrong. They
    are a collapse because one rule decides both and cannot see which frontend
    authorized which.
    """
    plan = _broad_backend_plan()
    approved = DestinationNat(
        publication_id="pub.approved",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    unapproved = DestinationNat(
        publication_id="pub.unapproved",
        frontend=Endpoints("zone.guest", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    events = [
        apply_nat(approved, event("zone.lan", "edge.public", "tcp", 443)),
        apply_nat(unapproved, event("zone.guest", "edge.public", "tcp", 443)),
    ]

    collapses = merges_distinct_originals(events, decided_by=_decider(plan))

    assert collapses, "one rule covers two different originals and nothing noticed"
    decision, left, right = collapses[0]
    assert decision == "binding:bind.backend"
    assert "pub.approved" in left + right and "pub.unapproved" in left + right


def test_flows_decided_by_different_rules_are_not_a_collapse() -> None:
    plan = _broad_backend_plan()
    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    translated = apply_nat(nat, event("zone.lan", "edge.public", "tcp", 443))
    elsewhere = event("zone.guest", "backend.web", "tcp", 9090)  # no rule accepts this

    assert merges_distinct_originals([translated, elsewhere], decided_by=_decider(plan)) == []


def test_one_origin_decided_many_times_is_not_a_collapse() -> None:
    """One client reaching one backend twice is not a merge of two authorizations."""
    plan = _broad_backend_plan()
    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    once = apply_nat(nat, event("zone.lan", "edge.public", "tcp", 443))

    assert merges_distinct_originals([once, once], decided_by=_decider(plan)) == []


# --- the split: rules match current, authorization decides on original --------------


def test_a_rule_matches_the_current_tuple_because_that_is_what_a_device_sees() -> None:
    grant = grant_for("policy.backend", 8080, source="zone.lan", destination="backend.web")
    plan = lower(grants=[grant], guards={}, context=CONTEXT, endpoints=ENDPOINTS, protocols=("tcp",))

    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    translated = apply_nat(nat, event("zone.lan", "edge.public", "tcp", 443))

    assert interpret(plan, translated).verdict is Verdict.ACCEPT


def test_a_backend_rule_accepts_an_unauthorized_direct_flow_and_the_model_says_so() -> None:
    """The whole point, demonstrated end to end.

    The rule was emitted for a published path but written in backend
    coordinates without the frontend's source restriction. A flow reaching the
    backend directly matches it. The interpreter accepts - correctly, that is
    what the device would do - and the intent, asked about the same flow in its
    own coordinates, never permitted it.

    Reading only the interpreter would call this fine. Reading only the intent
    would call it impossible. The obligation is the comparison.
    """
    plan = _broad_backend_plan()
    frontend_only = grant_for("policy.frontend", 443, source="zone.lan", destination="edge.public")
    authorized = authorize([frontend_only], {})

    direct = event("zone.guest", "backend.web", "tcp", 8080)

    assert interpret(plan, direct).verdict is Verdict.ACCEPT, "the broad backend rule must match"
    key = direct.authorizing
    assert not authorized.admits(
        key.source, key.destination, key.protocol, key.port
    ), "the intent authorizes a frontend path only; the direct flow rides in on the backend rule"


def test_sec_nat_holds_when_authorization_is_decided_on_the_original() -> None:
    """The positive case: a published flow is authorized by its client tuple."""
    frontend_grant = grant_for("policy.frontend", 443, source="zone.lan", destination="edge.public")
    backend_grant = grant_for("policy.backend", 8080, source="zone.lan", destination="backend.web")
    plan = lower(grants=[backend_grant], guards={}, context=CONTEXT, endpoints=ENDPOINTS, protocols=("tcp",))
    authorized = authorize([frontend_grant], {})

    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    translated = apply_nat(nat, event("zone.lan", "edge.public", "tcp", 443))

    accepted = interpret(plan, translated).verdict is Verdict.ACCEPT
    key = translated.authorizing
    permitted = authorized.admits(key.source, key.destination, key.protocol, key.port)

    assert accepted and permitted, "an approved published flow must be both carried and authorized"


def test_deciding_authorization_on_the_current_tuple_admits_what_the_intent_refused() -> None:
    """The mutant: ask the intent about backend coordinates instead of original.

    An earlier version of this test claimed that discarding the original hides
    the collapse. It does not - the sources still differ, so the collapse is
    still reported, only with less to say about which publication. The real
    damage is elsewhere, and this is it: decide authorization on where the packet
    ended up rather than where it came from, and a flow the intent refused is
    permitted by the rule that exists for a different one.
    """
    plan = _broad_backend_plan()
    frontend_grant = grant_for("policy.frontend", 443, source="zone.lan", destination="edge.public")
    authorized = authorize([frontend_grant], {})

    nat = DestinationNat(
        publication_id="pub.web",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    translated = apply_nat(nat, event("zone.lan", "edge.public", "tcp", 443))

    correct = translated.authorizing
    mutated = translated.current

    assert authorized.admits(correct.source, correct.destination, correct.protocol, correct.port)
    assert not authorized.admits(
        mutated.source, mutated.destination, mutated.protocol, mutated.port
    ), "deciding on current coordinates asks the intent a question it was never asked"
    assert interpret(plan, translated).verdict is Verdict.ACCEPT


def test_discarding_the_original_loses_which_publication_not_the_collapse() -> None:
    """Stated accurately, because the first attempt overclaimed.

    Without the original both flows still differ by source, so the collapse is
    still found. What is lost is the client-facing tuple in the report - the
    thing an author needs to know which publication to narrow.
    """
    plan = _broad_backend_plan()
    approved = DestinationNat(
        publication_id="pub.approved",
        frontend=Endpoints("zone.lan", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    unapproved = DestinationNat(
        publication_id="pub.unapproved",
        frontend=Endpoints("zone.guest", "edge.public", "tcp", 443),
        backend_destination="backend.web",
        backend_port=8080,
    )
    events = [
        apply_nat(approved, event("zone.lan", "edge.public", "tcp", 443)),
        apply_nat(unapproved, event("zone.guest", "edge.public", "tcp", 443)),
    ]
    decide = _decider(plan)

    with_original = merges_distinct_originals(events, decided_by=decide)
    forgetful = merges_distinct_originals(
        [dataclasses.replace(item, original=None) for item in events], decided_by=decide
    )

    assert with_original and forgetful, "both find the collapse"
    assert "443" in " ".join(with_original[0]), "the client-facing port is in the report"
    assert "443" not in " ".join(forgetful[0]), "and is gone once the original is discarded"

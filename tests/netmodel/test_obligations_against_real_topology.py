"""The obligations, run against the topology that actually exists.

Everything in W06 so far has been checked on fixtures, and fixtures agree with
whatever the author of the fixture believed. This runs the same machinery over
the real compiled model: the eight zone-to-zone policy overrides two security
matrices declare, lowered into a plan, interpreted, and compared with the algebra.

The point is not a green tick. It is to find out what the model cannot express
about real sources - the blocked list is the honest measure of distance, and it
has been worth more than the passing cases every time it has been run.
"""

from __future__ import annotations

import itertools

import pytest

from netmodel.interpret import FlowEvent, Verdict, accepted_flows, interpret
from netmodel.lower import lower
from netmodel.plan import ExecutionContext
from netmodel.policy import (
    Activation,
    Binding,
    Effect,
    PolicyError,
    PolicyTemplate,
    authorize,
    resolve_grant,
)
from netmodel.snapshot import (
    DEFAULT_SNAPSHOT,
    SnapshotMissing,
    load_snapshot,
    read_security_matrices,
    read_zone_policy_overrides,
)

CONTEXT = ExecutionContext(
    enforcer="rtr-mikrotik-chateau",
    routing_domain="main",
    family="ipv4",
    hook="forward",
    chain="managed",
)


@pytest.fixture(scope="module")
def model():
    try:
        return load_snapshot()
    except SnapshotMissing:
        pytest.skip(f"{DEFAULT_SNAPSHOT} absent; run `task netmodel:snapshot` first")


@pytest.fixture(scope="module")
def overrides(model):
    found = read_zone_policy_overrides(model)
    assert found, "no policy overrides in the snapshot; this differential would prove nothing"
    return found


def _template(override: dict, index: int) -> tuple[PolicyTemplate, list[int], str]:
    """One override as a policy template, or a reason it cannot be one."""
    from netmodel.policy import ANY_TRANSPORT

    ports = override.get("ports")
    accept = override.get("action") == "accept"
    if not isinstance(ports, dict) or not ports:
        # An override naming no transport constrains every transport. The model
        # refused this until the framework compiler needed it, which left the
        # sources' one mandatory deny outside the model - the gap this
        # differential was written to surface.
        protocol, numbers = ANY_TRANSPORT, None
    else:
        protocol, numbers = sorted(ports.items())[0]
        if not isinstance(numbers, list) or not numbers:
            raise ValueError(f"ports.{protocol} is empty")

    name = str(override.get("name") or f"override-{index}")
    template = PolicyTemplate(
        policy_id=f"policy.{name}",
        effect=Effect.PERMIT if accept else Effect.DENY,
        activation=Activation.BINDING_ONLY if accept else Activation.SCOPE_GUARD,
        direction="transit",
        source="{binding: source}" if accept else frozenset({override["from_zone_ref"]}),
        destination="{binding: destination}" if accept else frozenset({override["to_zone_ref"]}),
        protocol=protocol,
        ports=None if numbers is None else frozenset(int(item) for item in numbers),
        owner=str(override.get("matrix_ref") or "unknown"),
        rationale=str(override.get("comment") or "no comment in source"),
    )
    return template, [] if numbers is None else [int(item) for item in numbers], protocol


def _intent(overrides: list[dict]):
    """Derive grants and guards from the real overrides, recording what will not fit."""
    grants = []
    guards: dict[str, PolicyTemplate] = {}
    blocked: list[tuple[str, str]] = []

    for index, override in enumerate(overrides):
        name = str(override.get("name") or f"override-{index}")
        try:
            template, _, _ = _template(override, index)
        except (ValueError, PolicyError, KeyError) as exc:
            blocked.append((name, str(exc)))
            continue

        if template.effect is Effect.DENY:
            guards[f"guard.{name}"] = template
            continue
        try:
            grants.append(
                resolve_grant(
                    template,
                    Binding(
                        binding_id=f"bind.{name}",
                        policy_id=template.policy_id,
                        sources=frozenset({override["from_zone_ref"]}),
                        destinations=frozenset({override["to_zone_ref"]}),
                        approved=True,
                    ),
                )
            )
        except PolicyError as exc:
            blocked.append((name, str(exc)))
    return grants, guards, blocked


def _flow_space(grants, guards):
    """Concrete flows to ask about, including transports no permit mentions.

    An any-transport guard states no ports, so it contributes nothing to a space
    built from what the rules name - and the guard would then never be tested
    anywhere it matters. A few transports outside the permitted set are added for
    exactly that reason.
    """
    from netmodel.policy import ANY_TRANSPORT

    endpoints = sorted(
        {item for grant in grants for item in grant.flow.sources | grant.flow.destinations}
        | {item for guard in guards.values() for item in guard.source | guard.destination}
    )
    protocols = sorted(
        {grant.flow.protocol for grant in grants}
        | {g.protocol for g in guards.values() if g.protocol != ANY_TRANSPORT}
        | {"tcp", "udp"}
    )
    ports = sorted(
        {port for grant in grants for port in (grant.flow.ports or frozenset())}
        | {port for g in guards.values() for port in (g.ports or frozenset())}
        | {22, 9999}
    )
    return (
        [
            FlowEvent(
                source=source,
                destination=destination,
                protocol=protocol,
                port=port,
                enforcer=CONTEXT.enforcer,
                routing_domain=CONTEXT.routing_domain,
                family=CONTEXT.family,
                hook=CONTEXT.hook,
                chain=CONTEXT.chain,
            )
            for source, destination, protocol, port in itertools.product(endpoints, endpoints, protocols, ports)
        ],
        endpoints,
        protocols,
    )


# --- what the sources contain -----------------------------------------------------


def test_the_snapshot_carries_the_matrices_this_reads(model) -> None:
    matrices = read_security_matrices(model)

    assert len(matrices) >= 2, "fewer matrices than expected; the differential is measuring less than it should"


def test_the_real_overrides_can_be_expressed_as_intent(overrides) -> None:
    """The blocked list, which is the measurement worth having."""
    grants, guards, blocked = _intent(overrides)

    assert grants or guards, "nothing from the real sources became intent"
    # Recorded rather than asserted away: three overrides declare no ports, and
    # the model has no shape for a zone rule without a transport constraint.
    assert len(blocked) == len(overrides) - len(grants) - len(guards)
    for name, reason in blocked:
        assert reason, f"{name} was dropped without a reason"


def test_the_only_thing_blocked_is_the_absence_of_ports(overrides) -> None:
    """If something else starts failing, the reason should be visible here."""
    _, _, blocked = _intent(overrides)
    reasons = {reason.split(";")[0] for _, reason in blocked}

    assert reasons <= {"no ports"}, reasons


def test_the_only_mandatory_deny_in_the_sources_is_now_expressible() -> None:
    """The gap this differential was written to find, and its closure.

    Three of the eight overrides carry no ports, and one is the only `drop` in
    the topology: `servers-to-management-deny`. The model refused an unbounded
    port set, so the strongest restriction in the sources sat outside the model
    and the guard-precedence test below skipped.

    An override naming no transport constrains every transport, and that is now
    its own shape rather than an absence. The deny derives, the guard test runs,
    and SEC-AUTH is measured with it present.
    """
    from netmodel.policy import ANY_TRANSPORT
    from netmodel.snapshot import load_snapshot, read_zone_policy_overrides

    try:
        overrides = read_zone_policy_overrides(load_snapshot())
    except SnapshotMissing:
        pytest.skip("snapshot absent")

    denies = [item for item in overrides if item.get("action") == "drop"]
    assert len(denies) == 1, f"the source deny inventory changed: {[item.get('name') for item in denies]}"
    assert not denies[0].get("ports"), "the deny now carries ports; this test describes the wrong source"

    _, guards, blocked = _intent(overrides)

    assert guards, "the portless deny did not derive as a guard"
    guard = next(iter(guards.values()))
    assert guard.protocol == ANY_TRANSPORT and guard.ports is None
    assert blocked == [], f"something is still inexpressible: {blocked}"


def test_sec_auth_holds_for_the_real_intent(overrides) -> None:
    grants, guards, _ = _intent(overrides)
    space, endpoints, protocols = _flow_space(grants, guards)
    assert space, "empty flow space; SEC-AUTH would hold vacuously"

    plan = lower(grants=grants, guards=guards, context=CONTEXT, endpoints=endpoints, protocols=protocols)
    authorized = authorize(grants, guards)

    accepted = {(item.source, item.destination, item.protocol, item.port) for item in accepted_flows(plan, space)}
    assert accepted, "the plan accepts nothing from the real intent; the check would be vacuous"

    unauthorized = {key for key in accepted if not authorized.admits(*key)}
    assert not unauthorized, f"the plan accepts what the real intent does not authorize: {sorted(unauthorized)}"


def test_sec_avail_carries_every_real_permit(overrides) -> None:
    grants, guards, _ = _intent(overrides)
    space, endpoints, protocols = _flow_space(grants, guards)
    plan = lower(grants=grants, guards=guards, context=CONTEXT, endpoints=endpoints, protocols=protocols)
    accepted = {(item.source, item.destination, item.protocol, item.port) for item in accepted_flows(plan, space)}

    # An any-transport permit names no port, so it contributes no concrete
    # required flow. That is honest rather than convenient: "every port" is not a
    # finite requirement, and enumerating one would invent an objective nobody
    # stated.
    required = {
        (source, destination, grant.flow.protocol, port)
        for grant in grants
        if grant.flow.ports is not None
        for source in grant.flow.sources
        for destination in grant.flow.destinations
        for port in grant.flow.ports
    }
    assert required, "no required flows derived; SEC-AVAIL would have nothing to check"

    assert not (required - accepted), f"the plan drops permitted flows: {sorted(required - accepted)}"


def test_a_derived_guard_beats_the_permits_it_overlaps(overrides) -> None:
    """Guards must win where they apply - checked on whatever the sources give.

    Today they give none: the single deny is portless and inexpressible, which
    `test_the_model_cannot_express_the_only_mandatory_deny_in_the_sources`
    records. Skipping is honest here; asserting that guards exist would fail for
    a reason this test is not about, and quietly passing an empty loop would be
    worse.
    """
    grants, guards, _ = _intent(overrides)
    if not guards:
        pytest.skip("no expressible deny in the sources yet; see the deny-inexpressible test")

    space, endpoints, protocols = _flow_space(grants, guards)
    plan = lower(grants=grants, guards=guards, context=CONTEXT, endpoints=endpoints, protocols=protocols)

    checked = 0
    for guard_id, guard in guards.items():
        for source in guard.source:
            for destination in guard.destination:
                # An any-transport guard must deny every flow between its
                # endpoints, including transports no permit mentions - which is
                # exactly where a guard narrowed to somebody's port list leaks.
                candidates = [
                    item
                    for item in space
                    if item.source == source
                    and item.destination == destination
                    and (guard.ports is None or (item.protocol == guard.protocol and item.port in guard.ports))
                ]
                for probe in candidates:
                    decision = interpret(plan, probe)
                    assert decision.verdict is Verdict.DENY, (
                        f"{guard_id} does not deny {source} -> {destination} " f"{probe.protocol}/{probe.port}"
                    )
                    checked += 1

    assert checked >= 4, f"only {checked} flows checked against the guards; the test is not exercising them"
    space, endpoints, protocols = _flow_space(grants, guards)
    plan = lower(grants=grants, guards=guards, context=CONTEXT, endpoints=endpoints, protocols=protocols)

    unmatched = [item for item in space if interpret(plan, item).verdict is Verdict.UNSUPPORTED]

    assert unmatched == [], "a flow inside the declared scope reached no rule at all"

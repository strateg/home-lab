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
    ports = override.get("ports")
    if not isinstance(ports, dict) or not ports:
        raise ValueError("no ports; the model has no shape for a portless zone rule")
    protocol, numbers = sorted(ports.items())[0]
    if not isinstance(numbers, list) or not numbers:
        raise ValueError(f"ports.{protocol} is empty")

    accept = override.get("action") == "accept"
    name = str(override.get("name") or f"override-{index}")
    template = PolicyTemplate(
        policy_id=f"policy.{name}",
        effect=Effect.PERMIT if accept else Effect.DENY,
        activation=Activation.BINDING_ONLY if accept else Activation.SCOPE_GUARD,
        direction="transit",
        source="{binding: source}" if accept else frozenset({override["from_zone_ref"]}),
        destination="{binding: destination}" if accept else frozenset({override["to_zone_ref"]}),
        protocol=protocol,
        ports=frozenset(int(item) for item in numbers),
        owner=str(override.get("matrix_ref") or "unknown"),
        rationale=str(override.get("comment") or "no comment in source"),
    )
    return template, [int(item) for item in numbers], protocol


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
    endpoints = sorted(
        {item for grant in grants for item in grant.flow.sources | grant.flow.destinations}
        | {item for guard in guards.values() for item in guard.source | guard.destination}
    )
    protocols = sorted({grant.flow.protocol for grant in grants} | {g.protocol for g in guards.values()})
    ports = sorted(
        {port for grant in grants for port in grant.flow.ports} | {p for g in guards.values() for p in g.ports}
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


def test_the_model_cannot_express_the_only_mandatory_deny_in_the_sources() -> None:
    """The finding this differential was written to produce, recorded as a test.

    Three of the eight real overrides carry no ports, and one of them is the only
    `drop` in the whole topology: `servers-to-management-deny`. The model refuses
    an unbounded port set on purpose - an empty selector is an error, not "any",
    and a constraint that is not about ports is a separate shape - so the
    strongest guard the sources actually contain is currently inexpressible.

    That is a migration finding, not a model defect: the source states "deny
    everything from servers to management" and the target model wants that said
    as a bounded set or as a typed non-port constraint. But it is worth a failing
    signal rather than a note, because a model that silently expressed four
    permits and dropped the one deny would look like progress.

    This test passes while the gap exists and fails when it closes, at which
    point the deny must be re-derived and SEC-AUTH re-measured with it present.
    """
    from netmodel.snapshot import load_snapshot, read_zone_policy_overrides

    try:
        overrides = read_zone_policy_overrides(load_snapshot())
    except SnapshotMissing:
        pytest.skip("snapshot absent")

    denies = [item for item in overrides if item.get("action") == "drop"]
    assert len(denies) == 1, f"the source deny inventory changed: {[item.get('name') for item in denies]}"

    portless_denies = [item for item in denies if not item.get("ports")]
    assert portless_denies, (
        "the deny now carries ports and the model can express it - derive it as a guard, "
        "re-run SEC-AUTH with it present, and delete this test"
    )


# --- the obligations, on real intent -------------------------------------------------


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

    required = {
        (source, destination, grant.flow.protocol, port)
        for grant in grants
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

    for guard_id, guard in guards.items():
        for source in guard.source:
            for destination in guard.destination:
                for port in guard.ports:
                    event = next(
                        (
                            item
                            for item in space
                            if (item.source, item.destination, item.protocol, item.port)
                            == (source, destination, guard.protocol, port)
                        ),
                        None,
                    )
                    if event is None:
                        continue
                    decision = interpret(plan, event)
                    assert (
                        decision.verdict is Verdict.DENY
                    ), f"{guard_id} does not deny {source} -> {destination} {guard.protocol}/{port}"


def test_the_terminal_deny_closes_the_real_scope(overrides) -> None:
    grants, guards, _ = _intent(overrides)
    space, endpoints, protocols = _flow_space(grants, guards)
    plan = lower(grants=grants, guards=guards, context=CONTEXT, endpoints=endpoints, protocols=protocols)

    unmatched = [item for item in space if interpret(plan, item).verdict is Verdict.UNSUPPORTED]

    assert unmatched == [], "a flow inside the declared scope reached no rule at all"

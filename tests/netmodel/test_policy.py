"""Checks for the policy algebra.

Two groups. The first states the rules directly. The second states properties the
algebra must hold whatever the inputs, because those are the claims that would be
expensive to discover are false only after a deployment.
"""

from __future__ import annotations

import pytest

from netmodel.policy import (
    BINDING_DESTINATION,
    BINDING_SOURCE,
    Activation,
    Binding,
    Effect,
    Flow,
    PolicyError,
    PolicyTemplate,
    authorize,
    find_conflicts,
    resolve_grant,
)

LAN = frozenset({"inst.vlan.lan"})
GUEST = frozenset({"inst.vlan.guest"})
MGMT = frozenset({"inst.vlan.management"})


def permit(policy_id: str = "policy.dns", *, ports=frozenset({53}), protocol: str = "udp") -> PolicyTemplate:
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=BINDING_SOURCE,
        destination=BINDING_DESTINATION,
        protocol=protocol,
        ports=ports,
        owner="infra-admin",
        rationale="DNS for LAN clients",
    )


def guard(
    policy_id: str = "guard.no_guest_to_mgmt", *, ports=frozenset({22, 53}), protocol: str = "udp"
) -> PolicyTemplate:
    return PolicyTemplate(
        policy_id=policy_id,
        effect=Effect.DENY,
        activation=Activation.SCOPE_GUARD,
        direction="transit",
        source=GUEST,
        destination=MGMT,
        protocol=protocol,
        ports=ports,
        owner="security",
        rationale="guest must not reach management",
    )


def bound(template: PolicyTemplate, *, sources=LAN, destinations=MGMT, approved: bool = True) -> Binding:
    return Binding(
        binding_id=f"bind.{template.policy_id}",
        policy_id=template.policy_id,
        sources=sources,
        destinations=destinations,
        approved=approved,
    )


# --- the rules -------------------------------------------------------------


@pytest.mark.parametrize(
    ("effect", "activation"),
    [(Effect.PERMIT, Activation.SCOPE_GUARD), (Effect.DENY, Activation.BINDING_ONLY)],
)
def test_only_two_baseline_modes_exist(effect: Effect, activation: Activation) -> None:
    with pytest.raises(PolicyError, match="baseline mode"):
        PolicyTemplate(
            policy_id="policy.x",
            effect=effect,
            activation=activation,
            direction="ingress",
            source=GUEST,
            destination=MGMT,
            protocol="tcp",
            ports=frozenset({443}),
            owner="o",
            rationale="r",
        )


def test_a_template_alone_authorizes_nothing() -> None:
    """There is no path from a template to an authorized flow without a binding."""
    assert authorize([], {"g": guard()}).flows == ()


def test_an_unapproved_binding_is_not_a_grant() -> None:
    template = permit()

    with pytest.raises(PolicyError, match="not approved"):
        resolve_grant(template, bound(template, approved=False))


def test_owner_and_rationale_are_not_approval() -> None:
    template = permit()
    assert template.owner and template.rationale

    with pytest.raises(PolicyError, match="not approved"):
        resolve_grant(template, bound(template, approved=False))


@pytest.mark.parametrize("empty_side", ["sources", "destinations"])
def test_a_binding_must_name_both_sides(empty_side: str) -> None:
    kwargs = {"sources": LAN, "destinations": MGMT, empty_side: frozenset()}

    with pytest.raises(PolicyError):
        Binding(binding_id="b", policy_id="policy.dns", **kwargs)


@pytest.mark.parametrize("field_name", ["sources", "destinations", "ports"])
def test_an_empty_selector_is_an_error_not_any(field_name: str) -> None:
    kwargs = {"sources": LAN, "destinations": MGMT, "protocol": "udp", "ports": frozenset({53})}
    kwargs[field_name] = frozenset()

    with pytest.raises(PolicyError):
        Flow(**kwargs)


def test_a_guard_cannot_carry_an_unbound_parameter() -> None:
    with pytest.raises(PolicyError, match="concrete"):
        PolicyTemplate(
            policy_id="guard.x",
            effect=Effect.DENY,
            activation=Activation.SCOPE_GUARD,
            direction="transit",
            source=BINDING_SOURCE,
            destination=MGMT,
            protocol="tcp",
            ports=frozenset({22}),
            owner="o",
            rationale="r",
        )


def test_a_binding_that_does_not_intersect_its_template_is_an_error() -> None:
    template = PolicyTemplate(
        policy_id="policy.scoped",
        effect=Effect.PERMIT,
        activation=Activation.BINDING_ONLY,
        direction="ingress",
        source=LAN,
        destination=BINDING_DESTINATION,
        protocol="udp",
        ports=frozenset({53}),
        owner="o",
        rationale="r",
    )

    with pytest.raises(PolicyError, match="empty resolved set"):
        resolve_grant(template, bound(template, sources=GUEST))


def test_a_permit_overlapping_a_guard_is_refused_with_a_concrete_witness() -> None:
    template = permit(ports=frozenset({53}))
    grant = resolve_grant(template, bound(template, sources=GUEST, destinations=MGMT))

    conflicts = find_conflicts([grant], {"guard.no_guest_to_mgmt": guard()})

    assert len(conflicts) == 1
    assert conflicts[0].witness == ("inst.vlan.guest", "inst.vlan.management", "udp", 53)
    assert "matches both" in str(conflicts[0])

    with pytest.raises(PolicyError, match="matches both"):
        authorize([grant], {"guard.no_guest_to_mgmt": guard()})


def test_a_narrower_permit_does_not_defeat_a_guard() -> None:
    """Specificity is not authorization: the narrower permit still conflicts."""
    narrow = permit("policy.narrow", ports=frozenset({53}))
    grant = resolve_grant(narrow, bound(narrow, sources=GUEST, destinations=MGMT))

    with pytest.raises(PolicyError):
        authorize([grant], {"g": guard(ports=frozenset({22, 53, 443}))})


def test_a_permit_beside_a_guard_is_fine_when_they_do_not_overlap() -> None:
    template = permit()
    grant = resolve_grant(template, bound(template, sources=LAN, destinations=MGMT))

    authorized = authorize([grant], {"g": guard()})

    assert authorized.admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)
    assert not authorized.admits("inst.vlan.guest", "inst.vlan.management", "udp", 53)


def test_different_protocols_do_not_intersect() -> None:
    template = permit(protocol="tcp")
    grant = resolve_grant(template, bound(template, sources=GUEST, destinations=MGMT))

    assert find_conflicts([grant], {"g": guard(protocol="udp")}) == []


# --- the properties --------------------------------------------------------


def _grant(source, destination, ports, policy_id="policy.p"):
    template = permit(policy_id, ports=ports)
    return resolve_grant(template, bound(template, sources=source, destinations=destination))


def test_removing_a_permit_cannot_enlarge_the_authorized_set() -> None:
    a = _grant(LAN, MGMT, frozenset({53}), "policy.a")
    b = _grant(LAN, MGMT, frozenset({443}), "policy.b")

    full = authorize([a, b], {})
    reduced = authorize([a], {})

    assert full.admits("inst.vlan.lan", "inst.vlan.management", "udp", 443)
    assert not reduced.admits("inst.vlan.lan", "inst.vlan.management", "udp", 443)
    assert reduced.admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)


def test_adding_a_guard_cannot_enlarge_the_authorized_set() -> None:
    grant = _grant(GUEST, MGMT, frozenset({53}))

    assert authorize([grant], {}).admits("inst.vlan.guest", "inst.vlan.management", "udp", 53)
    with pytest.raises(PolicyError):
        authorize([grant], {"g": guard()})


def test_default_deny_is_the_absence_of_a_permit_not_a_guard_over_everything() -> None:
    """Nothing is authorized without a permit, and that needs no deny to say so."""
    empty = authorize([], {})

    assert not empty.admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)
    assert empty.flows == ()

    # And a guard elsewhere does not prevent an unrelated, properly bound permit.
    grant = _grant(LAN, MGMT, frozenset({53}))
    assert authorize([grant], {"g": guard()}).admits("inst.vlan.lan", "inst.vlan.management", "udp", 53)


def test_delivery_facts_never_appear_in_the_algebra() -> None:
    """Publication, NAT and connection state have no representation here.

    The strongest guarantee the module offers is structural: there is nowhere for
    a delivery fact to enter, so none can become a permission.
    """
    import ast
    from pathlib import Path

    module_path = Path(__file__).resolve().parents[2] / "netmodel" / "policy.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    # Identifiers the logic uses, not the prose that explains it. The docstring
    # names these concepts on purpose, to say they grant nothing.
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            identifiers.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr.lower())
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            identifiers.add(node.name.lower())
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg.lower())

    # Compare whole segments: a substring test flags "destination" for "nat".
    segments = {segment for name in identifiers for segment in name.split("_")}
    forbidden = {"dnat", "snat", "nat", "established", "conntrack", "publication", "mechanism", "frontend"}

    assert not (
        segments & forbidden
    ), f"delivery concepts must not participate in authorization, found {sorted(segments & forbidden)}"

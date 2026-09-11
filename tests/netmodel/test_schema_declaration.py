"""The registered v2 schemas must match what the reference model proved.

A schema written beside a reference implementation, rather than derived from it,
drifts from it immediately. These checks tie each declaration in a class file to
the rules the model enforces, so the two cannot disagree silently.

Three shapes are declared, one per layer that owns it:

* attachments, on `class.compute.workload` (L4);
* publications, on `class.service` (L5);
* policies and bindings, on `class.network.firewall_policy` (L2).

They also record the state of those declarations, which changed once the
enforcing consumer was written: `base.validator.network_intent_schema` reads all
three along class lineage and refuses an instance that violates them. The tests
that asserted nobody read them are inverted rather than deleted, because "the
consumer disappeared" is a failure worth being told about.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from yaml_loader import load_yaml_file

from netmodel.identity import LOCAL_KEY_RE
from netmodel.policy import _ALLOWED_MODES
from netmodel.snapshot import DEFAULT_SNAPSHOT, SnapshotMissing, load_snapshot

WORKLOAD_CLASS = REPO_ROOT / "topology/class-modules/L4-platform/compute/workload/class.compute.workload.yaml"
SERVICE_CLASS = REPO_ROOT / "topology/class-modules/L5-application/service/class.service.yaml"
POLICY_CLASS = REPO_ROOT / "topology/class-modules/L2-network/network/class.network.firewall_policy.yaml"

ATTACHMENTS = (load_yaml_file(WORKLOAD_CLASS) or {})["network_intent_schema"]
PUBLICATIONS = (load_yaml_file(SERVICE_CLASS) or {})["service_publication_schema"]
POLICIES = (load_yaml_file(POLICY_CLASS) or {})["policy_intent_schema"]

DECLARATIONS = {
    "attachments": (WORKLOAD_CLASS, ATTACHMENTS, "network_intent_schema", "network_intent_version"),
    "publications": (SERVICE_CLASS, PUBLICATIONS, "service_publication_schema", "service_publication_version"),
    "policies": (POLICY_CLASS, POLICIES, "policy_intent_schema", "policy_intent_version"),
}


# --- what every declaration must satisfy ------------------------------------


@pytest.mark.parametrize("name", sorted(DECLARATIONS))
def test_each_shape_is_declared_on_its_base_class_only_once(name: str) -> None:
    """Fourteen service classes carrying fourteen copies is the failure mode."""
    path, _, key, _ = DECLARATIONS[name]
    declaring = sorted(p.name for p in path.parent.glob("*.yaml") if key in p.read_text(encoding="utf-8"))

    assert declaring == [path.name]


@pytest.mark.parametrize("name", sorted(DECLARATIONS))
def test_the_version_is_scoped_and_not_the_manifest_token(name: str) -> None:
    _, schema, _, semantic_name = DECLARATIONS[name]
    description = schema["schema_version"]["description"]

    assert schema["schema_version"]["enum"] == [2]
    assert semantic_name in description
    assert "@version" in description, "the distinction from the manifest token must be stated where it is declared"


@pytest.mark.parametrize("name", sorted(DECLARATIONS))
def test_each_declaration_names_the_consumer_that_enforces_it(name: str) -> None:
    """A declaration should say what reads it, so a reader can go and check."""
    path, _, _, _ = DECLARATIONS[name]
    text = path.read_text(encoding="utf-8")

    assert "base.validator.network_intent_schema" in text, "a declaration should name what enforces it"

    # The phrase, not the bare word: a permit template is legitimately described
    # as inert until a binding names a subject, and matching that would be a test
    # flagging correct prose.
    for stale in ("currently inert", "constrains no instance", "G1 closes when an enforcing consumer"):
        assert stale.lower() not in text.lower(), f"the declaration still says {stale!r} after it became enforced"


@pytest.mark.parametrize(
    ("name", "collection"),
    [("attachments", "attachments"), ("publications", "publications"), ("policies", "policies")],
)
def test_record_keys_follow_the_model_grammar(name: str, collection: str) -> None:
    _, schema, _, _ = DECLARATIONS[name]

    assert schema[collection]["key_pattern"] == LOCAL_KEY_RE.pattern


@pytest.mark.parametrize(
    ("name", "collection"),
    [("attachments", "attachments"), ("publications", "publications"), ("policies", "policies")],
)
def test_enabled_is_an_explicit_false_not_a_deletion(name: str, collection: str) -> None:
    _, schema, _, _ = DECLARATIONS[name]
    enabled = schema[collection]["value"]["properties"]["enabled"]

    assert enabled["type"] == "boolean"
    assert enabled["default"] is True


def test_key_pattern_accepts_and_rejects_what_the_model_does() -> None:
    pattern = re.compile(ATTACHMENTS["attachments"]["key_pattern"])

    for accepted in ("backend", "primary", "_internal", "wan0"):
        assert pattern.match(accepted)
    for rejected in ("wan-uplink", "net.primary", "@primary", "1st"):
        assert not pattern.match(rejected)


# --- attachments (L4) -------------------------------------------------------


def test_static_allocation_uses_the_address_form_the_model_resolves() -> None:
    address = ATTACHMENTS["attachments"]["value"]["properties"]["address"]

    assert "static" in address["properties"]["allocation"]["enum"]
    assert address["properties"]["host"]["type"] == "integer"
    assert (
        "host" not in ATTACHMENTS["attachments"]["value"]["properties"]
    ), "host belongs inside address; a second host field beside it is the ambiguity the model removed"


def test_derived_fields_are_named_as_forbidden_on_the_attachment() -> None:
    forbidden = set(ATTACHMENTS["attachments"]["value"]["derived_and_forbidden_here"])

    assert {"ip", "gateway", "zone", "routing_domain", "address_family"} <= forbidden


# --- publications (L5) ------------------------------------------------------


def test_every_service_class_reaches_the_publication_shape_through_lineage() -> None:
    """A declaration nothing inherits from is a declaration for one class."""
    concrete = sorted(SERVICE_CLASS.parent.glob("class.service.*.yaml"))
    assert len(concrete) == 14, [p.name for p in concrete]

    for path in concrete:
        payload = load_yaml_file(path) or {}
        assert payload.get("@extends") == "class.service", path.name


def test_the_publication_base_is_abstract() -> None:
    assert (load_yaml_file(SERVICE_CLASS) or {}).get("@abstract") is True


def test_a_publication_cannot_name_who_may_connect() -> None:
    """The structural guarantee: there is no field in which to write a permit.

    A publication is a delivery fact. Under `A = (P and C) \\ D` it contributes
    to C and never to P, and the way to keep that true is to leave nowhere for a
    source selector to be authored.
    """
    properties = PUBLICATIONS["publications"]["value"]["properties"]
    segments = {segment for name in properties for segment in name.split("_")}
    forbidden = {"source", "sources", "from", "allowed", "permit", "action", "policy", "allow"}

    assert not (segments & forbidden), f"a publication must not carry {sorted(segments & forbidden)}"


def test_the_omission_of_a_source_selector_is_declared_not_accidental() -> None:
    named = set(PUBLICATIONS["publications"]["value"]["forbidden_here"])

    assert {"allowed_from", "source", "sources", "permit", "action"} <= named


def test_publication_delivery_facts_are_derived_not_authored() -> None:
    forbidden = set(PUBLICATIONS["publications"]["value"]["derived_and_forbidden_here"])

    assert {"address", "external_address", "nat_rule", "firewall_rule", "rule_position", "zone"} <= forbidden


def test_a_translating_mechanism_is_still_not_authorization() -> None:
    mechanism = PUBLICATIONS["publications"]["value"]["properties"]["mechanism"]

    assert set(mechanism["enum"]) == {"direct", "destination_nat", "reverse_proxy", "tunnel"}
    assert mechanism["default"] == "direct"


def test_a_publication_needs_an_endpoint_a_protocol_and_a_port() -> None:
    assert PUBLICATIONS["publications"]["value"]["required"] == ["endpoint_ref", "protocol", "port"]


# --- policies and bindings (L2) ---------------------------------------------


def test_the_declared_modes_are_exactly_the_ones_the_model_admits() -> None:
    """The tie that stops the schema and the algebra from drifting apart."""
    declared = {(entry["effect"], entry["activation"]) for entry in POLICIES["allowed_modes"]["items"]}
    modelled = {(effect.value, activation.value) for effect, activation in _ALLOWED_MODES}

    assert declared == modelled


def test_effect_and_activation_enums_admit_no_value_outside_those_modes() -> None:
    properties = POLICIES["policies"]["value"]["properties"]
    effects = {effect.value for effect, _ in _ALLOWED_MODES}
    activations = {activation.value for _, activation in _ALLOWED_MODES}

    assert set(properties["effect"]["enum"]) == effects
    assert set(properties["activation"]["enum"]) == activations


def test_owner_and_rationale_are_required_and_are_not_approval() -> None:
    required = set(POLICIES["policies"]["value"]["required"])
    assert {"owner", "rationale"} <= required

    rationale = POLICIES["policies"]["value"]["properties"]["rationale"]["description"]
    assert "not approval" in rationale.replace("are not", "not")


def test_approval_defaults_to_refusal() -> None:
    approved = POLICIES["bindings"]["value"]["properties"]["approved"]

    assert approved["type"] == "boolean"
    assert approved["default"] is False
    assert "approved" not in POLICIES["bindings"]["value"]["required"]


def test_a_binding_must_name_both_sides() -> None:
    assert {"sources", "destinations", "policy_ref"} == set(POLICIES["bindings"]["value"]["required"])


def test_a_binding_cannot_restate_the_effect_it_binds() -> None:
    forbidden = set(POLICIES["bindings"]["value"]["forbidden_here"])

    assert {"effect", "action", "position", "priority"} <= forbidden


def test_rule_position_is_derived_never_authored() -> None:
    """Positions come from execution precedence, not from an author's number."""
    forbidden = set(POLICIES["policies"]["value"]["derived_and_forbidden_here"])

    assert {"position", "priority", "order"} <= forbidden


def test_the_terminal_deny_is_named_as_a_backend_obligation() -> None:
    text = POLICY_CLASS.read_text(encoding="utf-8")

    assert "E7082" in text, "ADR 0119 ties the terminal drop-all to this code; the declaration must say so"
    assert "E7854" not in text, (
        "E7854 belongs to storage media inventory and has since three months before ADR 0110 claimed it; "
        "see the erratum in docs/diagnostics-catalog.md"
    )


def test_ports_are_bounded_and_a_non_port_constraint_is_a_separate_shape() -> None:
    ports = POLICIES["policies"]["value"]["properties"]["ports"]

    assert ports["items"]["minimum"] == 1 and ports["items"]["maximum"] == 65535
    assert "not about ports" in ports["description"]


# --- what the declarations do not yet do ------------------------------------


def test_nothing_in_the_runtime_reads_class_property_schemas() -> None:
    """The measurement behind the word inert, kept honest by rechecking it."""
    roots = [REPO_ROOT / "topology-tools", REPO_ROOT / "scripts"]
    readers = [
        path
        for root in roots
        for path in root.rglob("*.py")
        if "property_schemas" in path.read_text(encoding="utf-8", errors="ignore")
    ]

    assert readers == [], f"property_schemas now has a consumer: {readers}; the declaration is no longer inert"


def test_the_v2_declarations_have_an_enforcing_consumer() -> None:
    """The inversion that makes G1 real.

    This test asserted the opposite until the enforcing validator existed: that
    nothing read the declarations, and that registering one therefore constrained
    no instance. It is kept, inverted, because the claim it measures is the one
    that matters - a schema with no consumer is a comment, and the way to notice
    that the consumer has been deleted is to assert it is there.
    """
    roots = [REPO_ROOT / "topology-tools", REPO_ROOT / "scripts"]
    keys = ("network_intent_schema", "service_publication_schema", "policy_intent_schema")
    readers = sorted(
        {
            path.as_posix()
            for root in roots
            for path in root.rglob("*.py")
            for key in keys
            if key in path.read_text(encoding="utf-8", errors="ignore")
        }
    )

    assert readers, "no runtime module reads the v2 declarations; they constrain nothing"
    assert any("network_intent_schema_validator" in path for path in readers)


def test_the_consumer_resolves_all_three_shapes() -> None:
    """One consumer for three declarations, which is why they were declared first."""
    sys.path.insert(0, str(REPO_ROOT / "topology-tools"))
    from plugins.validators.network_intent_schema_validator import SHAPES

    assert {shape.schema_key for shape in SHAPES} == {
        "network_intent_schema",
        "service_publication_schema",
        "policy_intent_schema",
    }


def test_a_consumer_must_walk_lineage_because_the_compiler_does_not_merge_it() -> None:
    """Measured, not assumed: a child class does not carry its parent's payload.

    The compiler records `lineage` and `parent_class` but leaves the parent's
    fields on the parent. A validator that reads only the class an instance names
    would find no schema at all on any concrete workload or service.
    """
    try:
        model = load_snapshot()
    except SnapshotMissing:
        pytest.skip(f"{DEFAULT_SNAPSHOT} absent; run `task netmodel:snapshot` first")

    classes = model["classes"]

    for base, key, child in (
        ("class.compute.workload", "network_intent_schema", "class.compute.workload.lxc"),
        ("class.service", "service_publication_schema", "class.service.proxy"),
    ):
        assert key in classes[base], f"{key} missing from {base} in the compiled model"
        assert (
            key not in classes[child]
        ), f"{key} appeared on {child}; the merge assumption changed, update the consumer"
        assert classes[child]["lineage"] == [base, child]

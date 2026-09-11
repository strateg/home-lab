"""The registered v2 attachment schema must match what the model proved.

A schema written beside a reference implementation, rather than derived from it,
drifts from it immediately. These checks tie the declaration in the class file to
the rules the model enforces, so the two cannot disagree silently.

They also record the state of the declaration: it is inert. Nothing in the
runtime reads class property schemas, so registering one constrains no instance.
That is deliberate at this point and is not the end of G1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from yaml_loader import load_yaml_file

from netmodel.identity import LOCAL_KEY_RE

CLASS_FILE = REPO_ROOT / "topology/class-modules/L4-platform/compute/workload/class.compute.workload.yaml"
SCHEMA = (load_yaml_file(CLASS_FILE) or {}).get("network_intent_schema") or {}


def test_the_schema_is_declared_on_the_base_class_only_once() -> None:
    """Fourteen service classes carrying fourteen copies is the failure mode."""
    workload_dir = CLASS_FILE.parent
    declaring = [path.name for path in workload_dir.glob("*.yaml") if "network_intent_schema" in path.read_text()]

    assert declaring == [CLASS_FILE.name]


def test_key_pattern_matches_the_model_grammar() -> None:
    assert SCHEMA["attachments"]["key_pattern"] == LOCAL_KEY_RE.pattern


def test_key_pattern_accepts_and_rejects_what_the_model_does() -> None:
    pattern = re.compile(SCHEMA["attachments"]["key_pattern"])

    for accepted in ("backend", "primary", "_internal", "wan0"):
        assert pattern.match(accepted)
    for rejected in ("wan-uplink", "net.primary", "@primary", "1st"):
        assert not pattern.match(rejected)


def test_static_allocation_uses_the_address_form_the_model_resolves() -> None:
    address = SCHEMA["attachments"]["value"]["properties"]["address"]

    assert "static" in address["properties"]["allocation"]["enum"]
    assert address["properties"]["host"]["type"] == "integer"
    assert (
        "host" not in SCHEMA["attachments"]["value"]["properties"]
    ), "host belongs inside address; a second host field beside it is the ambiguity the model removed"


def test_derived_fields_are_named_as_forbidden_on_the_consumer() -> None:
    forbidden = set(SCHEMA["attachments"]["value"]["derived_and_forbidden_here"])

    assert {"ip", "gateway", "zone", "routing_domain", "address_family"} <= forbidden


def test_the_version_is_scoped_and_not_the_manifest_token() -> None:
    description = SCHEMA["schema_version"]["description"]

    assert SCHEMA["schema_version"]["enum"] == [2]
    assert "network_intent_version" in description
    assert "@version" in description, "the distinction from the manifest token must be stated where it is declared"


def test_the_declaration_states_that_it_is_not_yet_enforced() -> None:
    """If this ever stops being true, the comment has to change with it."""
    text = CLASS_FILE.read_text(encoding="utf-8")

    assert "inert" in text
    assert "property_schemas" in text, "the reason it is inert must be named, not implied"


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

"""Differential check: the reference merge agrees with the engine in the pipeline.

The reference model is only useful if it predicts what the pipeline will actually
do. Inheritance is the place that matters most, because the whole named-mapping
decision rests on the claim that the repository's existing merge already provides
the right semantics.

So the two are run against the same inputs and compared. Cases are chosen for the
distinctions the accepted model makes: a nested mapping merging, a value list
replacing rather than extending, an explicit null differing from an absent key,
and false and zero surviving rather than being treated as unset.

Agreement on these cases is not proof of agreement everywhere. It is the evidence
that the named-mapping decision does not depend on an engine change, and a
regression alarm if either side moves.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "topology-tools"))

from plugins.compilers.instance_rows_on_prepare_compiler import InstanceRowsOnPrepareCompiler

from netmodel.identity import merge_inherited

CASES = {
    "nested mapping merges": (
        {"interface": "eth0", "address": {"allocation": "static"}, "default_route": True},
        {"network_ref": "inst.vlan.servers", "address": {"host": 60}},
    ),
    "value list replaces": ({"source_refs": ["a", "b"]}, {"source_refs": ["a"]}),
    "explicit null overrides": ({"gateway": "10.0.0.1", "other": 1}, {"gateway": None}),
    "absent key inherits": ({"gateway": "10.0.0.1"}, {}),
    "new key is added": ({"a": 1}, {"b": 2}),
    "scalar replaces mapping": ({"address": {"host": 1}}, {"address": "192.0.2.5"}),
    "mapping replaces scalar": ({"address": "192.0.2.5"}, {"address": {"host": 1}}),
    "false survives": ({"enabled": True}, {"enabled": False}),
    "zero survives": ({"host": 60}, {"host": 0}),
    "empty mapping changes nothing": ({"address": {"host": 1}}, {"address": {}}),
}


@pytest.mark.parametrize(
    ("name", "case"), sorted(CASES.items()), ids=lambda value: value if isinstance(value, str) else ""
)
def test_reference_merge_matches_the_pipeline_engine(name: str, case: tuple[dict, dict]) -> None:
    base, override = case

    assert merge_inherited(base, override) == InstanceRowsOnPrepareCompiler._deep_merge(base, override), name


def test_false_and_zero_are_not_treated_as_unset_by_either_side() -> None:
    """The one that would be silent if it broke.

    An inherited true replacing an authored false re-enables something the author
    switched off, and no error would be raised anywhere.
    """
    merged_reference = merge_inherited({"enabled": True, "host": 60}, {"enabled": False, "host": 0})
    merged_pipeline = InstanceRowsOnPrepareCompiler._deep_merge(
        {"enabled": True, "host": 60}, {"enabled": False, "host": 0}
    )

    assert merged_reference == merged_pipeline == {"enabled": False, "host": 0}


def test_instance_identifiers_stay_a_separate_namespace() -> None:
    """Local-key grammar must not be read as a rule about instance ids.

    Real instance identifiers contain dots and hyphens. Applying the local-key
    grammar to them would condemn most of the repository, which is why the rule is
    scoped to embedded record keys.
    """
    from netmodel.identity import LOCAL_KEY_RE

    instance_ids = [path.stem for path in (REPO_ROOT / "projects/home-lab/topology/instances/network").glob("*.yaml")]

    assert instance_ids, "expected network instances to be present"
    assert not any(LOCAL_KEY_RE.match(instance_id) for instance_id in instance_ids)

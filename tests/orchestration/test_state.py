from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestration.deploy.state import (  # noqa: E402
    StateTransitionError,
    build_default_node_state,
    can_transition,
    transition_node_state,
)


def test_can_transition_accepts_legal_edges() -> None:
    assert can_transition("pending", "bootstrapping") is True
    assert can_transition("bootstrapping", "initialized") is True
    assert can_transition("initialized", "verified") is True
    assert can_transition("verified", "pending") is True


def test_can_transition_rejects_illegal_edges() -> None:
    assert can_transition("pending", "verified") is False
    assert can_transition("failed", "verified") is False


def test_transition_node_state_updates_fields_and_history() -> None:
    node = build_default_node_state(node_id="rtr-a", mechanism="netinstall")

    transition_node_state(node, to_state="bootstrapping", action="bootstrap", increment_attempt=True)

    assert node["status"] == "bootstrapping"
    assert node["attempt_count"] == 1
    assert node["last_action"] == "bootstrap"
    assert isinstance(node["history"], list)
    assert node["history"][-1]["from_state"] == "pending"
    assert node["history"][-1]["to_state"] == "bootstrapping"


def test_transition_node_state_raises_on_illegal_transition() -> None:
    node = build_default_node_state(node_id="rtr-a", mechanism="netinstall")
    with pytest.raises(StateTransitionError, match="Illegal state transition"):
        transition_node_state(node, to_state="verified", action="skip")


def test_transition_node_state_caps_history_to_ten_entries() -> None:
    node = build_default_node_state(node_id="rtr-a", mechanism="netinstall")
    for _ in range(12):
        transition_node_state(node, to_state="bootstrapping", action="force-start")
        transition_node_state(node, to_state="failed", action="force-fail")
        transition_node_state(node, to_state="bootstrapping", action="retry")
        transition_node_state(node, to_state="initialized", action="boot-ok")
        transition_node_state(node, to_state="verified", action="verify-ok")
        transition_node_state(node, to_state="pending", action="reset", allow_same_state=False)

    assert len(node["history"]) == 10

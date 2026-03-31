"""
ADR 0083 scaffold: initialization state machine helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"bootstrapping"},
    "bootstrapping": {"initialized", "failed"},
    "initialized": {"verified", "failed"},
    "verified": {"bootstrapping", "pending"},
    "failed": {"bootstrapping"},
}


class StateTransitionError(ValueError):
    """Raised when a requested state transition is not legal."""


@dataclass(frozen=True)
class StateTransition:
    from_state: str
    to_state: str
    action: str
    timestamp: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_status(status: str | None) -> str:
    value = (status or "").strip().lower()
    return value or "pending"


def can_transition(from_state: str, to_state: str) -> bool:
    source = normalize_status(from_state)
    target = normalize_status(to_state)
    allowed = LEGAL_TRANSITIONS.get(source, set())
    return target in allowed


def assert_transition(from_state: str, to_state: str) -> None:
    if not can_transition(from_state, to_state):
        raise StateTransitionError(
            f"Illegal state transition: {normalize_status(from_state)} -> {normalize_status(to_state)}"
        )


def build_default_node_state(*, node_id: str, mechanism: str, status: str = "pending") -> dict[str, Any]:
    return {
        "id": node_id,
        "mechanism": mechanism,
        "status": normalize_status(status),
        "last_action": "discovered",
        "last_action_at": utc_now(),
        "last_error": None,
        "attempt_count": 0,
        "imported": False,
        "history": [],
    }


def transition_node_state(
    node_state: dict[str, Any],
    *,
    to_state: str,
    action: str,
    increment_attempt: bool = False,
    last_error: str | None = None,
    imported: bool | None = None,
    allow_same_state: bool = False,
) -> StateTransition:
    from_state = normalize_status(str(node_state.get("status", "pending")))
    target = normalize_status(to_state)
    if from_state != target:
        assert_transition(from_state, target)
    elif not allow_same_state:
        raise StateTransitionError(f"State is already '{target}'")

    timestamp = utc_now()
    transition = StateTransition(
        from_state=from_state,
        to_state=target,
        action=action.strip() or "update",
        timestamp=timestamp,
    )

    node_state["status"] = target
    node_state["last_action"] = transition.action
    node_state["last_action_at"] = transition.timestamp
    node_state["last_error"] = last_error
    if imported is not None:
        node_state["imported"] = bool(imported)
    if increment_attempt:
        node_state["attempt_count"] = int(node_state.get("attempt_count", 0)) + 1

    history = node_state.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "timestamp": transition.timestamp,
            "from_state": transition.from_state,
            "to_state": transition.to_state,
            "action": transition.action,
        }
    )
    if len(history) > 10:
        history = history[-10:]
    node_state["history"] = history
    return transition

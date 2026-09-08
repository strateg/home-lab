"""Shared helpers for framework policy path resolution (ADR 0093)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def resolve_repo_root(config: dict[str, Any]) -> Path:
    """Resolve repo root from config or default to 3 parents up from caller."""
    raw = config.get("repo_root")
    if isinstance(raw, str) and raw.strip():
        return Path(raw.strip()).resolve()
    # Default: assume topology-tools/plugins/validators/<this_file>
    return Path(__file__).resolve().parents[3]


def resolve_framework_root(config: dict[str, Any]) -> Path | None:
    """Resolve framework root from class/object modules root config."""
    class_modules_root_raw = config.get("class_modules_root")
    if isinstance(class_modules_root_raw, str) and class_modules_root_raw.strip():
        class_modules_root = Path(class_modules_root_raw.strip()).resolve()
        return class_modules_root.parent.parent
    object_modules_root_raw = config.get("object_modules_root")
    if isinstance(object_modules_root_raw, str) and object_modules_root_raw.strip():
        object_modules_root = Path(object_modules_root_raw.strip()).resolve()
        return object_modules_root.parent.parent
    return None


def resolve_policy_path(*, config: dict[str, Any], value: str) -> Path:
    """Resolve policy path from repo root or framework root."""
    candidate = Path(value.strip())
    if candidate.is_absolute():
        return candidate.resolve()
    repo_path = (resolve_repo_root(config) / candidate).resolve()
    if repo_path.exists():
        return repo_path
    framework_root = resolve_framework_root(config)
    if framework_root is not None:
        framework_path = (framework_root / candidate).resolve()
        if framework_path.exists():
            return framework_path
    return repo_path


def parse_policy_date(value: Any) -> datetime | None:
    """Parse YYYY-MM-DD date string to datetime with UTC timezone."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None

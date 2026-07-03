"""Shared Mermaid rendering helpers for projection builders (ADR 0112)."""

from __future__ import annotations

from plugins.icons.icon_manager import IconManager

_ICONS = IconManager()

# Trust zone colour palette for Mermaid classDef
_ZONE_CLASS_COLOUR: dict[str, str] = {
    "untrusted": "fill:#ff6b6b,stroke:#c92a2a,color:#fff",
    "user": "fill:#74c0fc,stroke:#1864ab,color:#000",
    "servers": "fill:#51cf66,stroke:#2b8a3e,color:#000",
    "management": "fill:#da77f2,stroke:#9c36b5,color:#fff",
    "guest": "fill:#ffd43b,stroke:#fab005,color:#000",
    "iot": "fill:#ffd43b,stroke:#fab005,color:#000",
}
_ZONE_CLASS_DEFAULT = "fill:#e9ecef,stroke:#868e96,color:#000"


def _icon_for_class(class_ref: str, *, fallback: str = "mdi:devices") -> str:
    """Return the best matching Mermaid icon for a class_ref."""
    return _ICONS.icon_for_class(class_ref, fallback=fallback)


def _zone_label(instance_id: str) -> str:
    """Extract human-readable zone name from instance_id like inst.trust_zone.servers."""
    parts = instance_id.rsplit(".", 1)
    return parts[-1].replace("_", " ").title() if parts else instance_id


def _safe_id(value: str) -> str:
    """Make a string safe for use as a Mermaid node ID.

    Replaces characters that are not alphanumeric or underscore.
    Mermaid node IDs should contain only: a-z A-Z 0-9 _

    Transformations:
    - '.' → '_'  (dot to underscore)
    - '-' → '_'  (dash to underscore)
    - '@' → '_'  (at-sign to underscore, for service@host notation)
    """
    return value.replace(".", "_").replace("-", "_").replace("@", "_")

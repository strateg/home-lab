"""Framework-shared capability helper utilities for object generators (ADR0078, ADR0086, ADR0106).

ADR 0106 accessor functions:
- get_all_capabilities(obj) — Return all capabilities including derived ones
- has_capability(obj, cap) — Check if object has capability (enabled or derived)
- filter_by_capability(objects, cap) — Filter objects having specified capability
- group_by_capability_prefix(objects, prefix) — Group objects by capability prefix

Strict error model (ADR 0106 D4):
- E8020: Cannot detect platform from cap.os.*
- E8021: Missing cap.bootstrap.* capability
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class CapabilityError(Exception):
    """Error raised when required capability is missing (ADR 0106 D4)."""

    def __init__(self, code: str, message: str, object_id: str = "") -> None:
        self.code = code
        self.message = message
        self.object_id = object_id
        super().__init__(f"{code}: {message}")


def get_all_capabilities(obj: dict[str, Any]) -> set[str]:
    """Return all capabilities for an object including derived ones (ADR 0106 D3).

    Collects capabilities from:
    - enabled_capabilities list
    - derived_capabilities list (from capability compiler)
    - capabilities dict (legacy format)

    Args:
        obj: Object dict with capability fields

    Returns:
        Set of all capability strings
    """
    caps: set[str] = set()

    # enabled_capabilities list (declared in object definition)
    enabled = obj.get("enabled_capabilities")
    if isinstance(enabled, list):
        for item in enabled:
            if isinstance(item, str) and item.strip():
                caps.add(item.strip())

    # derived_capabilities list (from capability compiler)
    derived = obj.get("derived_capabilities")
    if isinstance(derived, list):
        for item in derived:
            if isinstance(item, str) and item.strip():
                caps.add(item.strip())

    # capabilities dict (legacy format for backward compat)
    capabilities = obj.get("capabilities")
    if isinstance(capabilities, dict):
        for key, value in capabilities.items():
            if isinstance(key, str) and value:
                caps.add(f"cap.{key}" if not key.startswith("cap.") else key)
    elif isinstance(capabilities, list):
        for item in capabilities:
            if isinstance(item, str) and item.strip():
                caps.add(item.strip())

    return caps


def has_capability(obj: dict[str, Any], cap: str) -> bool:
    """Check if object has capability (enabled or derived) (ADR 0106 D3).

    Args:
        obj: Object dict with capability fields
        cap: Capability string to check (e.g., 'cap.os.routeros')

    Returns:
        True if the object has the specified capability
    """
    return cap in get_all_capabilities(obj)


def filter_by_capability(objects: list[dict[str, Any]], cap: str) -> list[dict[str, Any]]:
    """Filter objects having specified capability (ADR 0106 D3).

    Args:
        objects: List of object dicts
        cap: Capability string to filter by

    Returns:
        List of objects that have the specified capability
    """
    return [obj for obj in objects if has_capability(obj, cap)]


def group_by_capability_prefix(
    objects: list[dict[str, Any]], prefix: str
) -> dict[str, list[dict[str, Any]]]:
    """Group objects by capability prefix (ADR 0106 D3).

    Example:
        group_by_capability_prefix(devices, "cap.bootstrap.")
        Returns: {
            "cap.bootstrap.cloud_init": [device1, device2],
            "cap.bootstrap.netinstall": [device3],
        }

    Args:
        objects: List of object dicts
        prefix: Capability prefix to group by (e.g., 'cap.bootstrap.')

    Returns:
        Dict mapping capability to list of objects with that capability
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in objects:
        caps = get_all_capabilities(obj)
        for cap in caps:
            if cap.startswith(prefix):
                groups[cap].append(obj)
    return dict(groups)


def get_bootstrap_capability(obj: dict[str, Any]) -> str:
    """Get bootstrap capability for object (ADR 0106 D4).

    Strict error: raises CapabilityError if no bootstrap capability found.

    Args:
        obj: Object dict with capability fields

    Returns:
        Bootstrap capability string (e.g., 'cap.bootstrap.cloud_init')

    Raises:
        CapabilityError: E8021 if no bootstrap capability found
    """
    caps = get_all_capabilities(obj)
    for cap in caps:
        if cap.startswith("cap.bootstrap."):
            return cap
    object_id = obj.get("object_ref", obj.get("@object", "unknown"))
    raise CapabilityError(
        code="E8021",
        message=f"Missing cap.bootstrap.* capability for object '{object_id}'. "
        "Add initialization_contract.mechanism to object definition.",
        object_id=str(object_id),
    )


def get_platform_capability(obj: dict[str, Any]) -> str:
    """Get platform/OS capability for object (ADR 0106 D4).

    Strict error: raises CapabilityError if no platform capability found.

    Args:
        obj: Object dict with capability fields

    Returns:
        Platform capability string (e.g., 'cap.os.routeros', 'cap.os.proxmox')

    Raises:
        CapabilityError: E8020 if no platform capability found
    """
    caps = get_all_capabilities(obj)
    for cap in caps:
        if cap.startswith("cap.os."):
            return cap
    object_id = obj.get("object_ref", obj.get("@object", "unknown"))
    raise CapabilityError(
        code="E8020",
        message=f"Cannot detect platform for object '{object_id}'. "
        "Ensure cap.os.* capability is derived from OS definition.",
        object_id=str(object_id),
    )


def get_platform_type(obj: dict[str, Any]) -> str:
    """Get platform type string from object capabilities (ADR 0106).

    Returns platform type suitable for generator dispatch:
    - 'mikrotik' if has cap.os.routeros
    - 'proxmox' if has cap.os.proxmox
    - 'linux' if has cap.os.linux
    - 'unknown' if no platform capability

    This is a convenience wrapper that does not raise errors.

    Args:
        obj: Object dict with capability fields

    Returns:
        Platform type string
    """
    caps = get_all_capabilities(obj)

    # Priority order for platform detection
    if "cap.os.routeros" in caps:
        return "mikrotik"
    if "cap.os.proxmox" in caps:
        return "proxmox"
    if "cap.os.debian" in caps or "cap.os.ubuntu" in caps:
        return "linux"
    if "cap.os.linux" in caps:
        return "linux"
    if "cap.os.bsd" in caps:
        return "bsd"
    if "cap.os.windows" in caps:
        return "windows"

    return "unknown"


def capability_expression_enabled(capabilities: dict[str, Any], enabled_by: str) -> bool:
    """Check if a capability expression evaluates to truthy value.

    Args:
        capabilities: Dict of capability flags (e.g., {"has_ceph": True}).
        enabled_by: Dot-separated expression, optionally prefixed with "capabilities.".

    Returns:
        True if the expression resolves to a truthy value.
    """
    expr = enabled_by.strip()
    if not expr:
        return False
    if expr.startswith("capabilities."):
        expr = expr[len("capabilities.") :]

    current: Any = capabilities
    for segment in expr.split("."):
        if not isinstance(current, dict):
            return False
        current = current.get(segment)
    return bool(current)


def get_capability_templates(
    capabilities: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, str]:
    """Resolve capability-driven templates from plugin config.

    Args:
        capabilities: Dict of capability flags from projection.
        config: Plugin config containing capability_templates mapping.

    Returns:
        Dict mapping output_file -> template_path for enabled capabilities.
    """
    result: dict[str, str] = {}
    cap_templates = config.get("capability_templates")

    # Normalize cap_templates to list of mappings
    # ADR0078 specifies dict format, but support legacy list format for compatibility
    mappings: list[dict[str, Any]] = []
    if isinstance(cap_templates, dict):
        mappings = [m for m in cap_templates.values() if isinstance(m, dict)]
    elif isinstance(cap_templates, list):
        # Legacy list format: [{"capability_key": ..., "template": ..., "output_file": ...}]
        mappings = [m for m in cap_templates if isinstance(m, dict)]
    else:
        return result

    for mapping in mappings:
        enabled_by = mapping.get("enabled_by")
        # TODO(ADR0078-cleanup): Remove capability_key fallback after v5.1 migration
        if not isinstance(enabled_by, str) or not enabled_by.strip():
            cap_key = mapping.get("capability_key", "")
            if isinstance(cap_key, str) and cap_key.strip():
                enabled_by = f"capabilities.{cap_key.strip()}"

        template = mapping.get("template", "")
        output_file = mapping.get("output")
        # TODO(ADR0078-cleanup): Remove output_file fallback after v5.1 migration
        if not isinstance(output_file, str) or not output_file.strip():
            output_file = mapping.get("output_file", "")

        if not isinstance(enabled_by, str) or not enabled_by.strip() or not template or not output_file:
            continue

        if capability_expression_enabled(capabilities, enabled_by):
            result[str(output_file)] = str(template)

    return result

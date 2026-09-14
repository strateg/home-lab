"""Read-only reader for the compiled effective model.

The reference model is exercised against the real topology from its first commit,
so it cannot drift into fiction: a claim it cannot express on current sources is a
failing test rather than a note. This module is the only place that touches a
file, and it only ever reads.

Produce the snapshot with `task netmodel:snapshot`, which runs the compiler in
passthrough mode with no strict model lock and redirects artifacts into `build/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from netmodel.domains import AddressDomain, parse_address, parse_prefix

DEFAULT_SNAPSHOT = Path("build/netmodel/effective.json")

# Instance-id prefixes that identify an addressable L2 domain today. The target
# model selects by declared kind rather than by identifier shape; until the schema
# carries that, the prefix is the honest selector. It is deliberately narrower
# than a substring test: `obj.network.routing_policy.vpn_vlan` contains "vlan" and
# is not a VLAN.
_DOMAIN_PREFIXES = {
    "inst.vlan.": "vlan",
    "inst.bridge.": "bridge",
}


class SnapshotMissing(FileNotFoundError):
    """Raised when the effective-model snapshot has not been produced."""


def load_snapshot(path: Path | str = DEFAULT_SNAPSHOT) -> dict[str, Any]:
    snapshot = Path(path)
    if not snapshot.exists():
        raise SnapshotMissing(
            f"{snapshot} not found; run `task netmodel:snapshot` to produce it from the real topology"
        )
    return json.loads(snapshot.read_text(encoding="utf-8"))


def _object_properties(model: dict[str, Any], object_ref: str) -> dict[str, Any]:
    objects = model.get("objects")
    if not isinstance(objects, dict):
        return {}
    entry = objects.get(object_ref)
    if not isinstance(entry, dict):
        return {}
    properties = entry.get("properties")
    return properties if isinstance(properties, dict) else {}


def object_ref(row: dict[str, Any]) -> str:
    """Resolve the object a row extends.

    The row's `object` key holds resolved metadata, not the reference; the
    reference lives in the `instance` block. Reading `object` as a string yields
    an empty ref and silently loses every object-level default, which is how six
    VLANs first appeared to declare no prefix at all.
    """
    instance_block = row.get("instance")
    if isinstance(instance_block, dict):
        for field in ("extends_object", "materializes_object"):
            value = instance_block.get(field)
            if isinstance(value, str) and value:
                return value
    return ""


def _effective_field(row: dict[str, Any], model: dict[str, Any], field: str) -> Any:
    """Instance value wins; the object supplies the default.

    An explicit None check preserves a declared 0 or False, which a truthiness
    test would silently replace with the object's value.
    """
    instance_data = row.get("instance_data")
    if isinstance(instance_data, dict):
        value = instance_data.get(field)
        if value is not None:
            return value
    return _object_properties(model, object_ref(row)).get(field)


def read_domains(model: dict[str, Any]) -> list[AddressDomain]:
    """Build address domains from the network instances of the effective model."""
    instances = model.get("instances")
    rows = instances.get("network") if isinstance(instances, dict) else None
    if not isinstance(rows, list):
        return []

    domains: list[AddressDomain] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        instance_id = str(row.get("instance_id") or "").strip()
        kind = next((k for prefix, k in _DOMAIN_PREFIXES.items() if instance_id.startswith(prefix)), None)
        if kind is None:
            continue

        prefix_value = _effective_field(row, model, "cidr")
        gateway_value = _effective_field(row, model, "gateway")
        zone_value = _effective_field(row, model, "trust_zone_ref")

        domains.append(
            AddressDomain(
                domain_id=instance_id,
                kind=kind,
                prefix=parse_prefix(prefix_value if isinstance(prefix_value, str) else None),
                gateway=parse_address(gateway_value if isinstance(gateway_value, str) else None),
                trust_zone_ref=str(zone_value).strip() if isinstance(zone_value, str) else None,
            )
        )
    return sorted(domains, key=lambda d: d.domain_id)


def read_zone_overlay_networks(model: dict[str, Any]) -> dict[str, list[str]]:
    """Overlay CIDRs a trust zone enumerates on itself.

    This is the inverted membership direction the target model removes: the zone
    lists networks instead of the network declaring its zone. The reader exposes
    it so the gap between today's sources and the target model is measurable
    rather than assumed. Nothing in the model consumes it.
    """
    instances = model.get("instances")
    rows = instances.get("network") if isinstance(instances, dict) else None
    if not isinstance(rows, list):
        return {}

    overlays: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        instance_id = str(row.get("instance_id") or "").strip()
        if not instance_id.startswith("inst.trust_zone."):
            continue
        declared = _effective_field(row, model, "additional_networks")
        if not isinstance(declared, list):
            continue
        cidrs = [str(entry.get("cidr", "")).strip() for entry in declared if isinstance(entry, dict)]
        cidrs = [cidr for cidr in cidrs if cidr]
        if cidrs:
            overlays[instance_id] = sorted(cidrs)
    return overlays


# --- security matrices: the intent that exists in the sources today --------------


def _class_of(row: dict[str, Any]) -> str | None:
    payload = row.get("class")
    lineage = payload.get("lineage") if isinstance(payload, dict) else None
    if isinstance(lineage, list) and lineage:
        return lineage[-1]
    class_ref = row.get("class_ref")
    return class_ref if isinstance(class_ref, str) else None


def read_security_matrices(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Every security matrix row, whatever instance group it landed in.

    Selected by declared class rather than by identifier prefix, for the reason
    W05 records: a prefix selector can only see what its author happened to name
    that way.
    """
    instances = model.get("instances")
    if not isinstance(instances, Mapping):
        return []
    return [
        row
        for group in instances.values()
        if isinstance(group, list)
        for row in group
        if isinstance(row, dict) and _class_of(row) == "class.network.security_matrix"
    ]


def read_zone_policy_overrides(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Zone-to-zone overrides, flattened, each tagged with its matrix.

    This is where the authorization intent actually lives in the sources today.
    It is v1 shaped - an action, a zone pair and a port map - and reading it is
    how the target model gets something real to be checked against before any
    source is migrated.
    """
    flattened: list[dict[str, Any]] = []
    for row in read_security_matrices(model):
        matrix_id = row.get("instance_id")
        data = row.get("instance_data")
        overrides = data.get("policy_overrides") if isinstance(data, Mapping) else None
        if not isinstance(overrides, list):
            continue
        for override in overrides:
            if not isinstance(override, Mapping):
                continue
            flattened.append({**override, "matrix_ref": matrix_id})
    return flattened

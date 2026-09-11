"""Read the real topology into the target model, and report what will not fit.

This is the derive half of derive, review, freeze. It reads the compiled model and
produces the attachments and publication candidates the target model would hold,
together with the reason each one that cannot be expressed is blocked.

Nothing here authorizes anything. A candidate is a proposal for a human to
confirm, narrow or reject; it is never counted as a permit, and rejecting one is
a valid outcome. The point of running it now, before any schema is registered, is
that the blocked list is the real measure of how far the sources are from the
model - a number nobody has to estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from netmodel.domains import AddressDomain
from netmodel.snapshot import object_ref, read_domains

# Workload groups whose instances attach to a network.
_WORKLOAD_GROUPS = ("lxc", "docker", "routeros_container", "vm")


@dataclass(frozen=True, slots=True)
class AttachmentCandidate:
    """A workload's connection to one address domain, as the model would hold it."""

    owner: str
    local_key: str
    network_ref: str
    host: int | None
    kind: str


@dataclass(frozen=True, slots=True)
class Blocked:
    """Something the model cannot express from the sources as they stand."""

    owner: str
    what: str
    reason: str


@dataclass
class Inventory:
    attachments: list[AttachmentCandidate] = field(default_factory=list)
    publications: list[str] = field(default_factory=list)
    blocked: list[Blocked] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {
            "attachments": len(self.attachments),
            "publication_candidates": len(self.publications),
            "blocked": len(self.blocked),
        }


def _instance_rows(model: Mapping[str, Any], group: str) -> list[dict]:
    instances = model.get("instances")
    rows = instances.get(group) if isinstance(instances, Mapping) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def derive_attachments(model: Mapping[str, Any], domains: list[AddressDomain]) -> Inventory:
    """One attachment per workload network block, or a reason it is blocked.

    A workload that names a network the model does not hold as a domain is
    blocked rather than attached to a guess. That is the case worth counting:
    it is where the source and the model actually disagree.
    """
    known = {domain.domain_id for domain in domains}
    inventory = Inventory()

    for group in _WORKLOAD_GROUPS:
        for row in _instance_rows(model, group):
            owner = str(row.get("instance_id") or "").strip()
            data = row.get("instance_data")
            network = data.get("network") if isinstance(data, Mapping) else None
            if not isinstance(network, Mapping):
                continue

            network_ref = str(network.get("vlan_ref") or network.get("bridge_ref") or "").strip()
            if not network_ref:
                inventory.blocked.append(
                    Blocked(owner=owner, what="attachment", reason="no network reference in the network block")
                )
                continue
            if network_ref not in known:
                inventory.blocked.append(
                    Blocked(owner=owner, what="attachment", reason=f"network {network_ref} is not a modeled domain")
                )
                continue

            host = network.get("host")
            inventory.attachments.append(
                AttachmentCandidate(
                    owner=owner,
                    local_key="primary",
                    network_ref=network_ref,
                    host=host if isinstance(host, int) and not isinstance(host, bool) else None,
                    kind=group,
                )
            )
    return inventory


def derive_publication_candidates(model: Mapping[str, Any], inventory: Inventory) -> Inventory:
    """A publication candidate needs a runtime target, ports and a source.

    Each missing piece is recorded separately, because they are not the same
    problem: a missing runtime target is a modelling question, while a missing
    source restriction is flow data that only the running network can supply.
    """
    attached = {candidate.owner for candidate in inventory.attachments}

    for row in _instance_rows(model, "services"):
        owner = str(row.get("instance_id") or "").strip()
        data = row.get("instance_data")
        data = data if isinstance(data, Mapping) else {}

        # `runtime` is a row-level key, not part of instance_data. Reading it from
        # the wrong place reports every service as having no runtime target, which
        # is how this was first written and is a much worse claim than the truth.
        runtime = row.get("runtime")
        target = str(runtime.get("target_ref") or "").strip() if isinstance(runtime, Mapping) else ""
        ports = data.get("ports")
        security = data.get("security")
        allowed_from = security.get("allowed_from") if isinstance(security, Mapping) else None

        missing: list[str] = []
        if not target:
            missing.append("no runtime target")
        elif target not in attached:
            missing.append(f"runtime target {target} has no attachment")
        if not isinstance(ports, Mapping) or not ports:
            missing.append("no ports declared")
        if not isinstance(allowed_from, list) or not allowed_from:
            missing.append("no source restriction declared")
        if not str(data.get("owner") or "").strip():
            missing.append("no policy owner")

        if missing:
            inventory.blocked.append(Blocked(owner=owner, what="publication", reason="; ".join(missing)))
        else:
            inventory.publications.append(owner)
    return inventory


def build_inventory(model: Mapping[str, Any]) -> Inventory:
    domains = read_domains(model)
    inventory = derive_attachments(model, domains)
    return derive_publication_candidates(model, inventory)


def render_report(inventory: Inventory) -> str:
    lines = [f"attachments: {len(inventory.attachments)}", f"publication candidates: {len(inventory.publications)}"]
    for candidate in sorted(inventory.attachments, key=lambda c: c.owner):
        host = "-" if candidate.host is None else str(candidate.host)
        lines.append(f"  attach {candidate.owner:34} {candidate.network_ref:28} host={host}")
    for owner in sorted(inventory.publications):
        lines.append(f"  publish {owner}")
    lines.append(f"blocked: {len(inventory.blocked)}")
    for entry in sorted(inventory.blocked, key=lambda b: (b.what, b.owner)):
        lines.append(f"  {entry.what:12} {entry.owner:34} {entry.reason}")
    return "\n".join(lines)


__all__ = [
    "AttachmentCandidate",
    "Blocked",
    "Inventory",
    "build_inventory",
    "derive_attachments",
    "derive_publication_candidates",
    "object_ref",
    "render_report",
]

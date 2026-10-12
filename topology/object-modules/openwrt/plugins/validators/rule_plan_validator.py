#!/usr/bin/env python3
"""Validates the lowered OpenWrt firewall_rule plan before anything renders it.

Forwardings express "this zone may reach that zone"; rules express everything
narrower. They are the only sections on this backend whose correctness depends
on more than presence, which is what these two codes are about.

**E9902 - match tuples in one chain must be disjoint.** uapi exposes no ordering
control. There is no `position`, `index` or `place_before` anywhere in its
OpenAPI surface, and Terraform creates independent resources in parallel, so the
order the sections land in a chain is not something this repo can specify. The
consequence is that a chain's sections must be an unambiguous specification on
their own: two overlapping tuples are either contradictory, in which case
enforcement depends on an order nothing controls, or identical, in which case
two Terraform resources claim one uci section. Both are refused. A narrow tuple
strictly inside a wider one with the same target is redundant but unambiguous,
and is left alone - the generator emits one entry per protocol precisely so that
differing port sets never collapse into one wider grant.

Overlap is computed, not compared. Port sets intersect as sets, but destination
prefixes are compared as networks: `10.0.0.0/8` and `10.77.1.0/24` overlap
without being equal, and set equality would miss exactly the case that matters.

**E9903 - the plan must carry the arity each field renders at.** The provider is
asymmetric: on `uapi_firewall_rule`, `src_zone` and `dest_zone` are strings
while `proto`, `dest_port`, `dest_ip`, `src_ip` and `src_port` are lists; on
redirect and nat the match fields are scalars and only `proto` stays a list. The
cost of getting it wrong is not a type error - fw4 drops the entire section and
says nothing, so the rule silently does not exist while Terraform reports
success.

The renderer reaches that arity by iterating what the plan hands it, which makes
a scalar where a list belongs worse than a mismatch: `ports: {tcp: "80"}`
iterates the string and renders `dest_port = ["8", "0"]`, a syntactically valid
section matching two absurd ports. This check refuses those shapes at the plan
level, where the authored intent is still visible, rather than leaving them to
be read back out of rendered HCL.
"""

from __future__ import annotations

import ipaddress
from typing import Any

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)

_PERMIT_TARGETS = frozenset({"accept", "allow"})


def _networks(cidrs: list[str]) -> list[ipaddress._BaseNetwork]:
    """Parse what parses. Malformed prefixes are E9905/reference territory."""
    parsed: list[ipaddress._BaseNetwork] = []
    for cidr in cidrs:
        try:
            parsed.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            continue
    return parsed


def _prefixes_overlap(left: list[str], right: list[str]) -> bool:
    """Unrestricted on either side covers everything, so it always overlaps."""
    if not left or not right:
        return True
    left_nets, right_nets = _networks(left), _networks(right)
    if not left_nets or not right_nets:
        return True
    return any(a.overlaps(b) for a in left_nets for b in right_nets)


def _tuples_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_proto, right_proto = left["proto"], right["proto"]
    if left_proto is not None and right_proto is not None and left_proto != right_proto:
        return False

    left_ports, right_ports = left["ports"], right["ports"]
    if left_ports and right_ports and not (left_ports & right_ports):
        return False

    return _prefixes_overlap(left["cidrs"], right["cidrs"])


class OpenwrtRulePlanValidator(ValidatorJsonPlugin):
    """Refuses a lowered rule plan that cannot render into an ordered-free chain."""

    _ZONES_PLUGIN_ID = "object.openwrt.compiler.zones"
    _ZONES_KEY = "openwrt_zones"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        try:
            plans = ctx.subscribe(self._ZONES_PLUGIN_ID, self._ZONES_KEY)
        except PluginDataExchangeError:
            # Optional in the manifest: a project with no OpenWrt enforcer never
            # produces this channel, and that is not a defect.
            return self.make_result(diagnostics=diagnostics)

        if not isinstance(plans, dict):
            return self.make_result(diagnostics=diagnostics)

        for enforcer_id in sorted(plans):
            plan = plans.get(enforcer_id)
            if not isinstance(plan, dict):
                continue
            rules = plan.get("rules")
            if not isinstance(rules, list):
                rules = []

            # Input rules are firewall_rule sections too, and they share the
            # chain with nothing else - but two of them can still collide with
            # each other if two services resolve to one protocol and port, and
            # that collision is two Terraform resources claiming one section.
            # Normalized into the same tuple shape so one implementation checks
            # both rather than a second one drifting from the first.
            rules = list(rules) + [
                {
                    "src": entry.get("src"),
                    "dest": "<input>",
                    "dest_cidrs": [],
                    "ports": {str(entry.get("proto")): [entry.get("port")]},
                    "target": entry.get("target") or "ACCEPT",
                    "rule": f"input:{entry.get('service')}",
                }
                for entry in plan.get("input_rules") or []
                if isinstance(entry, dict)
            ]
            if not rules:
                continue

            arity = self._check_arity(enforcer_id, rules, stage)
            diagnostics.extend(arity)
            # Disjointness is computed from the flattened tuples, and flattening
            # a rule whose arity is wrong would compare shapes the renderer
            # would never produce. Report the arity defect and stop there.
            if arity:
                continue
            diagnostics.extend(self._check_disjointness(enforcer_id, rules, stage))

        return self.make_result(diagnostics=diagnostics)

    # ------------------------------------------------------------------
    # E9903
    # ------------------------------------------------------------------

    def _check_arity(
        self,
        enforcer_id: str,
        rules: list[Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        def refuse(index: int, field: str, detail: str) -> None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E9903",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Enforcer '{enforcer_id}': lowered rule #{index} carries '{field}' at the wrong "
                        f"arity - {detail}. fw4 drops a section whose match field has the wrong arity "
                        "without reporting anything, so the rule silently does not exist while Terraform "
                        "reports success."
                    ),
                    path=f"instance:{enforcer_id}.openwrt_zones.rules[{index}].{field}",
                )
            )

        for index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                refuse(index, "<rule>", f"the entry is {type(rule).__name__}, not a mapping")
                continue

            # src_zone / dest_zone render as strings. A list here renders as a
            # list into a string-typed provider attribute.
            for field in ("src", "dest"):
                value = rule.get(field)
                if not isinstance(value, str) or not value.strip():
                    refuse(
                        index,
                        field,
                        f"a zone endpoint renders as a single string, got {type(value).__name__}",
                    )

            cidrs = rule.get("dest_cidrs")
            if cidrs is not None and not isinstance(cidrs, list):
                refuse(
                    index,
                    "dest_cidrs",
                    f"dest_ip renders as a list, got {type(cidrs).__name__} - a bare string is "
                    "iterated character by character",
                )

            ports = rule.get("ports")
            if ports is None:
                continue
            if not isinstance(ports, dict):
                refuse(index, "ports", f"expected a protocol mapping, got {type(ports).__name__}")
                continue
            for proto in sorted(ports, key=str):
                values = ports.get(proto)
                if not isinstance(values, list):
                    refuse(
                        index,
                        f"ports.{proto}",
                        f"dest_port renders as a list, got {type(values).__name__} - a bare string "
                        'is iterated character by character, so "80" renders as ["8", "0"]',
                    )

        return diagnostics

    # ------------------------------------------------------------------
    # E9902
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Mirror the renderer: one tuple per protocol, zones as the chain key.

        The destination the tuple lands in is the *local* zone (`dest`), not the
        remote zone a permit was authored against: that is the zone whose chain
        the section is installed in, and so the scope disjointness has to hold
        within. A permit to a remote zone is narrowed by `dest_cidrs` instead,
        which is why prefixes participate in the overlap test at all.
        """
        flat: list[dict[str, Any]] = []
        for index, rule in enumerate(rules):
            ports = rule.get("ports") or {}
            target = str(rule.get("target") or "ACCEPT")
            cidrs = [item for item in rule.get("dest_cidrs") or [] if isinstance(item, str)]
            protocols = sorted(ports, key=str) if ports else [None]
            for proto in protocols:
                flat.append(
                    {
                        "index": index,
                        "src": rule.get("src"),
                        "dest": rule.get("dest"),
                        "proto": proto,
                        "ports": {str(port) for port in (ports.get(proto) or [])} if proto else set(),
                        "cidrs": cidrs,
                        "target": target,
                        "permit": target.strip().lower() in _PERMIT_TARGETS,
                        "remote_zone": rule.get("remote_zone"),
                    }
                )
        return flat

    def _check_disjointness(
        self,
        enforcer_id: str,
        rules: list[Any],
        stage: Stage,
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []

        chains: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
        for entry in self._flatten([rule for rule in rules if isinstance(rule, dict)]):
            chains.setdefault((entry["src"], entry["dest"]), []).append(entry)

        for chain in sorted(chains, key=lambda key: (str(key[0]), str(key[1]))):
            entries = chains[chain]
            for position, left in enumerate(entries):
                for right in entries[position + 1 :]:
                    if not _tuples_overlap(left, right):
                        continue

                    identical = (
                        left["proto"] == right["proto"]
                        and left["ports"] == right["ports"]
                        and sorted(left["cidrs"]) == sorted(right["cidrs"])
                    )
                    if left["permit"] != right["permit"]:
                        reason = (
                            f"opposing targets ({left['target']} and {right['target']}). With no ordering "
                            "control in the uapi surface, which one wins is not something this repo can "
                            "specify - on firewall4 a denial is expressed as an absent forwarding for "
                            "exactly this reason"
                        )
                    elif identical:
                        reason = (
                            "identical match tuples. Two Terraform resources would claim one uci section, "
                            "and the plan says the same thing twice without saying which is intended"
                        )
                    else:
                        # Same target, one tuple narrower than the other:
                        # redundant but unambiguous. Not a defect.
                        continue

                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E9902",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Enforcer '{enforcer_id}': lowered rules #{left['index']} and "
                                f"#{right['index']} both match in the {chain[0]} -> {chain[1]} chain "
                                f"(proto {left['proto'] or 'any'}/{right['proto'] or 'any'}) with "
                                f"{reason}. Make the match tuples disjoint."
                            ),
                            path=f"instance:{enforcer_id}.openwrt_zones.rules[{left['index']}]",
                        )
                    )

        return diagnostics

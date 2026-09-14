"""Check the published plan against the order it claims to satisfy (ADR 0119, G3).

G3 says validation independently checks the complete plan. *Independently* is the
whole requirement: a validator that called the compiler's sort would compare the
sort with itself and report agreement, which is what "do not make the generator
and the oracle share the same decision code and call agreement proof" forbids.

So this re-derives the required precedence from the rules themselves and checks
the emitted positions against it. It never sorts anything. The two can therefore
disagree, which is the only condition under which their agreement means something.

Three things are checked, and each has a failure that looks fine from the other
side:

* a precedence **cycle** - rules that each require the other first, which no
  order satisfies and which a producer can emit without noticing, because it
  emitted them one at a time;
* an emitted order that **violates an edge** it must satisfy - a mandatory deny
  after a permit it constrains, or anything after the terminal;
* a scope with **no terminal deny**. On a default-allow backend that is an open
  scope, and it is invisible in a rule list that otherwise reads correctly.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from plugins.validators.strict_admission import content_digest

from kernel.plugin_base import (
    PluginContext,
    PluginDataExchangeError,
    PluginDiagnostic,
    PluginResult,
    Stage,
    ValidatorJsonPlugin,
)

PLAN_PLUGIN_ID = "base.compiler.security_plan"
PLAN_KEY = "security_plan"
ROWS_PLUGIN_ID = "base.compiler.instance_rows"
ROWS_KEY = "normalized_rows"
MATRIX_CLASS = "class.network.security_matrix"
ANY_TRANSPORT = "any"

# Representatives of "some value nobody enumerated". Their identity does not
# matter; that they are outside every list the sources and the plan contain is
# the whole point, and a test asserts that rather than trusting the constant.
_PORT_OUTSIDE_ANY_ENUMERATION = 64999
_PROTOCOL_OUTSIDE_ANY_ENUMERATION = "sctp"


class SecurityPlanValidator(ValidatorJsonPlugin):
    """Independent order and termination check over the published plan."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        try:
            plan = ctx.subscribe(PLAN_PLUGIN_ID, PLAN_KEY)
        except PluginDataExchangeError as exc:
            return self.make_result(
                [
                    self.emit_diagnostic(
                        code="E7008",
                        severity="error",
                        stage=stage,
                        message=f"security plan validator requires the published plan: {exc}",
                        path="pipeline:validate",
                    )
                ]
            )

        # The source intent, read independently. Not reconstructed from the plan
        # and not from `expected_overrides`, which the compiler also produces: a
        # compiler can lose a rule and its own record of that rule in one edit,
        # and that is precisely the case this check exists to catch.
        source = self._source_obligations(ctx)
        if not source["available"]:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7008",
                    severity="error",
                    stage=stage,
                    message=(
                        "the source intent is not available, so the plan was checked for order and "
                        "termination only; completeness against the sources did not run"
                    ),
                    path="pipeline:validate",
                )
            )
        diagnostics.extend(self._check_coverage(plan=plan, source=source, stage=stage))
        diagnostics.extend(self._check_semantics(plan=plan, source=source, stage=stage))

        rules = plan.get("rules") if isinstance(plan, Mapping) else None
        declared = plan.get("scopes") if isinstance(plan, Mapping) else None
        declared_scopes = [str(item) for item in declared] if isinstance(declared, list) else []
        rules = rules if isinstance(rules, list) else []

        by_scope: dict[str, list[Mapping[str, Any]]] = {scope: [] for scope in declared_scopes}
        for rule in rules:
            if isinstance(rule, Mapping):
                by_scope.setdefault(str(rule.get("scope")), []).append(rule)

        # A declared scope with no rules is checked, not skipped. Returning early
        # on an empty rule list meant a plan that declared two scopes and emitted
        # nothing passed - and a scope absent from the rules cannot be reported as
        # unterminated, so the omission hid itself.
        for scope in sorted(by_scope):
            diagnostics.extend(self._check_scope(scope=scope, rules=by_scope[scope], stage=stage))

        # What was checked, and of what. The digest is computed from the plan's
        # content here rather than read from the payload's own `digest` field: a
        # payload that supplies its own identity can be edited to agree with
        # itself, and admission has to bind the plan that was examined.
        errors = sum(1 for item in diagnostics if item.severity == "error")
        record = {
            "plan_digest": content_digest(plan),
            "errors": errors,
            "warnings": sum(1 for item in diagnostics if item.severity == "warning"),
            "complete": source["available"],
            "checked_scopes": sorted(by_scope),
        }
        ctx.publish("security_plan_verification", record)

        return self.make_result(diagnostics, output_data={"security_plan_verification": record})

    def _check_scope(
        self, *, scope: str, rules: Sequence[Mapping[str, Any]], stage: Stage
    ) -> list[PluginDiagnostic]:
        diagnostics: list[PluginDiagnostic] = []
        path = f"security_plan:{scope}"

        terminals = [rule for rule in rules if rule.get("terminal")]
        if not terminals:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7082",
                    severity="error",
                    stage=stage,
                    message=(
                        f"scope '{scope}' has no terminal default deny. On a default-allow backend "
                        "that leaves the scope open, and a rule list without one reads correctly."
                    ),
                    path=path,
                )
            )
        for terminal in terminals:
            if terminal.get("effect") != "deny":
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7082",
                        severity="error",
                        stage=stage,
                        message=(
                            f"scope '{scope}' terminal '{terminal.get('origin')}' has effect "
                            f"{terminal.get('effect')!r}. A terminal that accepts closes nothing and "
                            "shadows every rule after it; the scope has no valid terminal deny."
                        ),
                        path=path,
                    )
                )
        if len(terminals) > 1:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7082",
                    severity="error",
                    stage=stage,
                    message=(
                        f"scope '{scope}' has {len(terminals)} terminal rules; only one can be last, "
                        "and the others are unreachable rules that prove nothing."
                    ),
                    path=path,
                )
            )

        diagnostics.extend(self._check_positions(scope=scope, rules=rules, stage=stage, path=path))

        edges = self._required_edges(rules)
        cycle = self._find_cycle(rules, edges)
        if cycle is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7080",
                    severity="error",
                    stage=stage,
                    message=f"scope '{scope}' precedence cycle: {' -> '.join(cycle)}",
                    path=path,
                )
            )
            return diagnostics

        for earlier, later in sorted(edges):
            first, second = rules[earlier], rules[later]
            if self._position(first) >= self._position(second):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E7081",
                        severity="error",
                        stage=stage,
                        message=(
                            f"scope '{scope}': '{first.get('origin')}' at position {self._position(first)} "
                            f"must precede '{second.get('origin')}' at position {self._position(second)}"
                        ),
                        path=path,
                    )
                )
        return diagnostics

    def _check_positions(
        self, *, scope: str, rules: Sequence[Mapping[str, Any]], stage: Stage, path: str
    ) -> list[PluginDiagnostic]:
        """Positions must be unique and consecutive from zero within the scope.

        Two rules on one position have no defined order, only the appearance of
        one - and the edge check cannot see it, because rules with no precedence
        relation between them are compared with nothing. A gap is as bad: it
        invites someone to fill it and changes what "after" means.
        """
        if not rules:
            return []

        positions = [self._position(rule) for rule in rules]
        expected = list(range(len(rules)))
        if sorted(positions) == expected:
            return []

        duplicates = sorted({value for value in positions if positions.count(value) > 1})
        detail = (
            f"positions {duplicates} are used more than once"
            if duplicates
            else f"positions {sorted(positions)} are not consecutive from zero"
        )
        return [
            self.emit_diagnostic(
                code="E7081",
                severity="error",
                stage=stage,
                message=f"scope '{scope}': {detail}; an order with a gap or a tie is not an order",
                path=path,
            )
        ]

    @staticmethod
    def _position(rule: Mapping[str, Any]) -> int:
        position = rule.get("position")
        return position if isinstance(position, int) else -1

    @staticmethod
    def _required_edges(rules: Sequence[Mapping[str, Any]]) -> set[tuple[int, int]]:
        """Edges execution semantics require, re-derived from the rules.

        A terminal default deny is a role, not an effect. Counting it among the
        denies would put it before every permit and after every rule at once,
        which is a cycle rather than an order - and this validator would then
        report a defect it had invented.
        """
        edges: set[tuple[int, int]] = set()
        for i, left in enumerate(rules):
            for j, right in enumerate(rules):
                if i == j:
                    continue
                if right.get("terminal") and not left.get("terminal"):
                    edges.add((i, j))
                elif (
                    not left.get("terminal")
                    and not right.get("terminal")
                    and left.get("effect") == "deny"
                    and right.get("effect") == "permit"
                ):
                    edges.add((i, j))
        return edges

    @staticmethod
    def _find_cycle(
        rules: Sequence[Mapping[str, Any]], edges: set[tuple[int, int]]
    ) -> list[str] | None:
        """Iterative depth-first search. Recursion here would fail on a long chain."""
        outgoing: dict[int, list[int]] = {index: [] for index in range(len(rules))}
        for source, target in edges:
            outgoing[source].append(target)

        state = {index: 0 for index in range(len(rules))}  # 0 new, 1 on stack, 2 done
        for start in range(len(rules)):
            if state[start] != 0:
                continue
            stack: list[tuple[int, int]] = [(start, 0)]
            path: list[int] = []
            state[start] = 1
            path.append(start)
            while stack:
                node, cursor = stack[-1]
                neighbours = sorted(outgoing[node])
                if cursor < len(neighbours):
                    stack[-1] = (node, cursor + 1)
                    neighbour = neighbours[cursor]
                    if state[neighbour] == 1:
                        loop = path[path.index(neighbour) :] + [neighbour]
                        return [str(rules[index].get("origin")) for index in loop]
                    if state[neighbour] == 0:
                        state[neighbour] = 1
                        path.append(neighbour)
                        stack.append((neighbour, 0))
                else:
                    state[node] = 2
                    stack.pop()
                    if path and path[-1] == node:
                        path.pop()
        return None



    # --- the source side, read independently ------------------------------------

    def _source_obligations(self, ctx: PluginContext) -> dict[str, Any]:
        """Derive what the sources require, without looking at the plan.

        This is a second lowering, and deliberately so. A validator that read the
        compiler's own summary of what it produced could only ever confirm the
        compiler's arithmetic; the two have to be able to disagree.
        """
        try:
            payload = ctx.subscribe(ROWS_PLUGIN_ID, ROWS_KEY)
        except PluginDataExchangeError:
            return {
            "available": False,
            "scopes": set(),
            "permits": [],
            "guards": [],
            "availability": [],
            "availability_declared": set(),
            "availability_attested": set(),
        }

        rows = [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
        scopes: set[str] = set()
        permits: list[dict[str, Any]] = []
        guards: list[dict[str, Any]] = []
        availability: list[dict[str, Any]] = []
        # Scopes that state a Q at all, even an empty one. An explicitly empty Q
        # is a claim - "nothing here has to keep working" - and absent data is
        # not. Reporting them the same way would let a missing declaration read
        # as a decision somebody made.
        declared_scopes: set[str] = set()
        # Scopes whose empty Q carries an owner and a reason. An empty list is a
        # value; a decision that nothing here has to keep working is a claim, and
        # for strict admission the difference is the provenance behind it.
        attested: set[str] = set()

        for row in rows:
            if self._class_of(row) != MATRIX_CLASS:
                continue
            scope = row.get("instance") or row.get("instance_id")
            if not isinstance(scope, str):
                continue
            scopes.add(scope)
            extensions = row.get("extensions")
            overrides = extensions.get("policy_overrides") if isinstance(extensions, Mapping) else None
            if not isinstance(overrides, list):
                continue
            for override in overrides:
                if not isinstance(override, Mapping):
                    continue
                entry = self._obligation(override, scope)
                if entry is None:
                    continue
                (guards if entry["effect"] == "deny" else permits).append(entry)

            declared = extensions.get("availability_requirements") if isinstance(extensions, Mapping) else None
            if isinstance(declared, list):
                declared_scopes.add(scope)
                if not declared:
                    waiver = extensions.get("availability_waiver") if isinstance(extensions, Mapping) else None
                    owner = str((waiver or {}).get("owner") or "").strip() if isinstance(waiver, Mapping) else ""
                    reason = (
                        str((waiver or {}).get("rationale") or "").strip() if isinstance(waiver, Mapping) else ""
                    )
                    if owner and reason:
                        attested.add(scope)
                for requirement in declared:
                    if not isinstance(requirement, Mapping):
                        continue
                    entry = self._obligation({**requirement, "action": "accept"}, scope)
                    if entry is not None:
                        availability.append(entry)

        return {
            "available": True,
            "scopes": scopes,
            "permits": permits,
            "guards": guards,
            "availability": availability,
            "availability_declared": declared_scopes,
            "availability_attested": attested,
        }

    @staticmethod
    def _class_of(row: Mapping[str, Any]) -> str | None:
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and class_ref:
            return class_ref
        payload = row.get("class")
        lineage = payload.get("lineage") if isinstance(payload, Mapping) else None
        return lineage[-1] if isinstance(lineage, list) and lineage else None

    @staticmethod
    def _obligation(override: Mapping[str, Any], scope: str) -> dict[str, Any] | None:
        name = str(override.get("name") or "").strip()
        source = override.get("from_zone_ref")
        destination = override.get("to_zone_ref")
        action = override.get("action")
        if not name or not isinstance(source, str) or not isinstance(destination, str):
            return None
        if action not in ("accept", "drop", "reject"):
            return None

        ports = override.get("ports")
        transports: list[tuple[str, tuple[int, ...] | None]]
        if not isinstance(ports, Mapping) or not ports:
            transports = [(ANY_TRANSPORT, None)]
        else:
            transports = []
            for protocol, numbers in sorted(ports.items()):
                if not isinstance(numbers, list) or not numbers:
                    return None
                transports.append((str(protocol), tuple(sorted(int(item) for item in numbers))))

        return {
            "name": name,
            "scope": scope,
            "effect": "permit" if action == "accept" else "deny",
            "source": source,
            "destination": destination,
            "transports": transports,
        }

    # --- traceable coverage -------------------------------------------------------

    def _check_coverage(
        self, *, plan: Mapping[str, Any], source: Mapping[str, Any], stage: Stage
    ) -> list[PluginDiagnostic]:
        """Every source scope and every mandatory deny must appear in the plan.

        Behavioural equivalence does not cover this. A terminal deny can make the
        outcome identical while a guard the source states is simply gone - the
        verdict is the same and the restriction is not there, so coverage is
        traced against the source rather than inferred from behaviour.
        """
        if not source.get("available"):
            return []

        diagnostics: list[PluginDiagnostic] = []
        rules = plan.get("rules") if isinstance(plan, Mapping) else []
        rules = rules if isinstance(rules, list) else []

        planned_scopes = {str(rule.get("scope")) for rule in rules if isinstance(rule, Mapping)}
        declared = plan.get("scopes") if isinstance(plan, Mapping) else []
        planned_scopes |= {str(item) for item in declared} if isinstance(declared, list) else set()

        # The endpoint set is closed by contract, and this is where that is
        # enforced. The probe space enumerates endpoints, so a rule naming one no
        # source declares is not merely undeclared - it sits outside every check
        # the space can perform, and its rule would be examined by nothing.
        declared_endpoints = {
            item[side]
            for item in [*source["permits"], *source["guards"], *source["availability"]]
            for side in ("source", "destination")
        }
        if declared_endpoints:
            for rule in rules:
                if not isinstance(rule, Mapping) or rule.get("terminal"):
                    continue
                unknown = sorted(
                    (set(rule.get("sources") or []) | set(rule.get("destinations") or []))
                    - declared_endpoints
                )
                if unknown:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7095",
                            severity="error",
                            stage=stage,
                            message=(
                                f"rule '{rule.get('origin')}' names endpoints {unknown} that no source "
                                "declares; the endpoint set is closed because the probe space enumerates it"
                            ),
                            path=f"security_plan:{rule.get('scope')}",
                        )
                    )

        for scope in sorted(source["scopes"] - planned_scopes):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7091",
                    severity="error",
                    stage=stage,
                    message=(
                        f"the sources declare scope '{scope}' and the plan has no representation of it; "
                        "an absent scope cannot be reported as unterminated, so the omission hides itself"
                    ),
                    path="security_plan:coverage",
                )
            )

        planned = {
            (str(rule.get("scope")), str(rule.get("origin")), self._transport_key(rule))
            for rule in rules
            if isinstance(rule, Mapping) and not rule.get("terminal")
        }
        # Denies and permits are both traced, with different codes. A missing deny
        # is a lost restriction; a missing permit is lowering incompleteness and
        # explicitly not an availability failure, because nothing declared that
        # the flow has to keep working. Reporting them alike would make the
        # weaker fact excuse the stronger one.
        for entry, prefix, code, noun in (
            *((guard, "guard", "E7090", "a mandatory deny") for guard in source["guards"]),
            *((permit, "binding", "E7093", "a permit") for permit in source["permits"]),
        ):
            for protocol, ports in entry["transports"]:
                key = (entry["scope"], f"{prefix}:{entry['name']}", (protocol, ports))
                if key in planned:
                    continue
                described = protocol if ports is None else f"{protocol}/{list(ports)}"
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message=(
                            f"scope '{entry['scope']}': the source states {noun} "
                            f"'{entry['name']}' on {described} and the plan carries no such rule"
                        ),
                        path=f"security_plan:{entry['scope']}",
                    )
                )
        return diagnostics

    @staticmethod
    def _transport_key(rule: Mapping[str, Any]) -> tuple[str, tuple[int, ...] | None]:
        transport = rule.get("transport") or {}
        if transport.get("kind") == "any":
            return (ANY_TRANSPORT, None)
        return (str(transport.get("protocol")), tuple(sorted(transport.get("ports") or [])))

    # --- two-way semantic comparison ------------------------------------------------

    def _check_semantics(
        self, *, plan: Mapping[str, Any], source: Mapping[str, Any], stage: Stage
    ) -> list[PluginDiagnostic]:
        """SEC-AUTH and SEC-AVAIL over a flow space the plan did not choose.

        The space is built from the source obligations. Building it from the
        plan's own rules would make a deleted UDP rule vanish from the check
        along with itself, and one-way inclusion is not enough either: an empty
        plan accepts nothing outside the authorized set and satisfies SEC-AUTH
        perfectly while carrying nothing at all.
        """
        if not source.get("available"):
            return []

        rules = plan.get("rules") if isinstance(plan, Mapping) else []
        rules = [item for item in rules if isinstance(item, Mapping)] if isinstance(rules, list) else []
        if not source["permits"] and not source["guards"]:
            return []

        diagnostics: list[PluginDiagnostic] = []
        for scope in sorted(source["scopes"]):
            scoped = [rule for rule in rules if str(rule.get("scope")) == scope]
            space = self._flow_space(source, scope, scoped)
            authorized = self._authorized(source, scope, space)
            required = self._required(source, scope)

            empty_and_unattested = (
                scope in source["availability_declared"]
                and not any(item["scope"] == scope for item in source["availability"])
                and scope not in source["availability_attested"]
            )
            if scope not in source["availability_declared"] or empty_and_unattested:
                diagnostics.append(
                    self.emit_diagnostic(
                        code="W7002",
                        severity="warning",
                        stage=stage,
                        message=(
                            f"scope '{scope}' has no attested availability requirement, so SEC-AVAIL is "
                            "unverified rather than satisfied. An empty list is a value; deciding that "
                            "nothing here has to keep working is a claim, and needs an owner and a reason"
                        ),
                        path=f"security_plan:{scope}",
                    )
                )

            # `Q subseteq A`, checked before the plan is asked anything. A required
            # flow a mandatory deny forbids is a contradiction between two source
            # statements, and it blocks the model - it is not settled by weakening
            # the guard, nor by quietly dropping the requirement.
            diagnostics.extend(self._check_requirements_are_permitted(source, scope, stage))

            for flow in space:
                verdict, origin = self._interpret(scoped, flow)
                accepted = verdict == "accept"

                if accepted and flow not in authorized:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7083",
                            severity="error",
                            stage=stage,
                            message=(
                                f"scope '{scope}' accepts {flow[0]} -> {flow[1]} {flow[2]}/{flow[3]} "
                                f"via '{origin}', which the source does not authorize"
                            ),
                            path=f"security_plan:{scope}",
                        )
                    )
                elif flow in required and not accepted:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7084",
                            severity="error",
                            stage=stage,
                            message=(
                                f"scope '{scope}' does not carry {flow[0]} -> {flow[1]} {flow[2]}/{flow[3]}, "
                                "which the source permits and no source deny overrides"
                            ),
                            path=f"security_plan:{scope}",
                        )
                    )
        return diagnostics

    @staticmethod
    def _flow_space(
        source: Mapping[str, Any], scope: str, rules: Sequence[Mapping[str, Any]]
    ) -> list[tuple[str, str, str, int]]:
        """Concrete flows to ask about: the intent's, plus whatever the plan touches.

        The intent contributes independently, which is the load-bearing part - a
        rule deleted from the plan still has its flows probed, so the loss cannot
        vanish along with itself.

        The plan's own coordinates are added on top, and they have to be: a rule
        smuggled in on a port the sources never mention would otherwise never be
        asked about. Deriving the space *from* the plan would hide losses;
        deriving it *only* from the intent hides additions. The union hides
        neither, and the two contributions stay separable.
        """
        entries = [item for item in [*source["permits"], *source["guards"]] if item["scope"] == scope]
        endpoints = {item["source"] for item in entries} | {item["destination"] for item in entries}
        protocols = {
            protocol for item in entries for protocol, _ in item["transports"] if protocol != ANY_TRANSPORT
        }
        ports = {port for item in entries for _, values in item["transports"] for port in (values or ())}

        for rule in rules:
            endpoints |= set(rule.get("sources") or [])
            endpoints |= set(rule.get("destinations") or [])
            transport = rule.get("transport") or {}
            if transport.get("kind") == "any":
                continue
            if transport.get("protocol"):
                protocols.add(str(transport["protocol"]))
            ports |= {int(item) for item in (transport.get("ports") or [])}

        # Representatives from outside the enumerated values, one per equivalence
        # class the enumeration cannot cover.
        #
        # Union of intent and plan coordinates is necessary and not sufficient. A
        # wildcard permit agrees with the authorization on every value anyone
        # listed and permits more beyond them, so the probes have to include a
        # value nobody listed - otherwise "matches on all probes" is a property
        # of the probe set rather than of the rule.
        #
        # Ports and protocols get a representative each. Endpoints do not: they
        # are opaque atoms drawn from a closed set the sources enumerate, so
        # there is no "other endpoint" class to sample. Inventing one would test
        # a zone that does not exist.
        ports.add(_PORT_OUTSIDE_ANY_ENUMERATION)
        protocols.add(_PROTOCOL_OUTSIDE_ANY_ENUMERATION)
        return [
            (left, right, protocol, port)
            for left in sorted(endpoints)
            for right in sorted(endpoints)
            for protocol in sorted(protocols or {"tcp"})
            for port in sorted(ports)
        ]

    @staticmethod
    def _covers(entry: Mapping[str, Any], protocol: str, port: int) -> bool:
        for entry_protocol, entry_ports in entry["transports"]:
            if entry_protocol == ANY_TRANSPORT:
                return True
            if entry_protocol == protocol and entry_ports and port in entry_ports:
                return True
        return False

    def _authorized(
        self, source: Mapping[str, Any], scope: str, space: Sequence[tuple[str, str, str, int]]
    ) -> set[tuple[str, str, str, int]]:
        """`(P and C) minus D`: what the source allows, over the probed space.

        An any-transport permit authorizes every transport between its endpoints,
        so it belongs here in full. It does *not* belong in the required set -
        those are different questions, and the first version of this answered the
        second one for both. The independent check then reported six accepted
        flows as unauthorized on the real topology when the source permits them
        explicitly: a false positive found by running the check rather than by
        reading it.
        """
        permitted = {
            flow
            for flow in space
            for entry in source["permits"]
            if entry["scope"] == scope
            and entry["source"] == flow[0]
            and entry["destination"] == flow[1]
            and self._covers(entry, flow[2], flow[3])
        }
        denied = {
            flow
            for flow in permitted
            for entry in source["guards"]
            if entry["scope"] == scope
            and entry["source"] == flow[0]
            and entry["destination"] == flow[1]
            and self._covers(entry, flow[2], flow[3])
        }
        return permitted - denied

    def _check_requirements_are_permitted(
        self, source: Mapping[str, Any], scope: str, stage: Stage
    ) -> list[PluginDiagnostic]:
        """`Q subseteq A`. A requirement a guard forbids is a contradiction, not a permit."""
        diagnostics: list[PluginDiagnostic] = []
        for entry in source["availability"]:
            if entry["scope"] != scope:
                continue
            for protocol, values in entry["transports"]:
                for port in values or ():
                    conflicting = [
                        guard["name"]
                        for guard in source["guards"]
                        if guard["scope"] == scope
                        and guard["source"] == entry["source"]
                        and guard["destination"] == entry["destination"]
                        and self._covers(guard, protocol, port)
                    ]
                    if not conflicting:
                        continue
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7092",
                            severity="error",
                            stage=stage,
                            message=(
                                f"scope '{scope}': requirement '{entry['name']}' needs "
                                f"{entry['source']} -> {entry['destination']} {protocol}/{port}, "
                                f"which mandatory deny {conflicting} forbids. Two source statements "
                                "contradict; resolve them rather than weakening either."
                            ),
                            path=f"security_plan:{scope}",
                        )
                    )
        return diagnostics

    def _required(self, source: Mapping[str, Any], scope: str) -> set[tuple[str, str, str, int]]:
        """Flows a declared availability requirement says must work.

        **Not derived from permits.** A permit is permission; an availability
        objective is a separate statement that something has to keep working, and
        turning every permit into one invents a claim nobody made and then
        reports it as met. The first version of this did exactly that - for finite
        permits, having already excluded any-transport ones for the same reason
        without noticing the reason applied to both.

        Nothing in the sources declares availability today, so this is empty and
        SEC-AVAIL is *unverified*, which `W7002` says out loud.
        """
        required: set[tuple[str, str, str, int]] = set()
        for entry in source["availability"]:
            if entry["scope"] != scope:
                continue
            for protocol, values in entry["transports"]:
                if protocol == ANY_TRANSPORT:
                    continue
                for port in values or ():
                    required.add((entry["source"], entry["destination"], protocol, port))

        return {
            flow
            for flow in required
            if not any(
                entry["scope"] == scope
                and entry["source"] == flow[0]
                and entry["destination"] == flow[1]
                and self._covers(entry, flow[2], flow[3])
                for entry in source["guards"]
            )
        }

    @staticmethod
    def _interpret(rules: Sequence[Mapping[str, Any]], flow: tuple[str, str, str, int]) -> tuple[str, str]:
        """First match wins, over the plan's own emitted order."""
        source, destination, protocol, port = flow
        for rule in sorted(rules, key=lambda item: item.get("position", 0)):
            if source not in (rule.get("sources") or []) and not rule.get("terminal"):
                continue
            if rule.get("terminal"):
                if source not in (rule.get("sources") or []) and rule.get("sources"):
                    continue
                if destination not in (rule.get("destinations") or []) and rule.get("destinations"):
                    continue
                return "deny", str(rule.get("origin"))
            if destination not in (rule.get("destinations") or []):
                continue
            transport = rule.get("transport") or {}
            if transport.get("kind") != "any":
                if transport.get("protocol") != protocol or port not in (transport.get("ports") or []):
                    continue
            return ("accept" if rule.get("effect") == "permit" else "deny", str(rule.get("origin")))
        return "unsupported", ""


__all__ = ["SecurityPlanValidator"]

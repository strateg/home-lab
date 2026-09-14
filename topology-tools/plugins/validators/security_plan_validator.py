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

        return self.make_result(diagnostics)

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


__all__ = ["SecurityPlanValidator"]

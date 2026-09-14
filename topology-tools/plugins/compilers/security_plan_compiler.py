"""Lower zone policy into an ordered, digest-identified plan (ADR 0119, gate G3).

The plan is the thing every later obligation is checked against, so it has to be
produced by the pipeline rather than derived in a test. This compiler reads the
security matrices, turns their zone-to-zone overrides into rules, orders them by
execution precedence, closes each scope with a terminal deny, and publishes the
result with a digest.

Four decisions carried over from the reference model, each because the obvious
alternative is wrong in a way that only shows up later:

**Order comes from execution semantics, never from provenance.** A mandatory deny
is evaluated before the permits it constrains; everything precedes the terminal.
Sorting by matrix name or declaration order would make the plan change when the
pipeline's scheduling does.

**The terminal deny is the plan's, not a template's.** ADR 0119 D4: a terminal a
template appends is one the plan cannot reason about, and "is anything executable
after the drop-all" is exactly what the plan must answer. `E7082` is its code -
`E7854`, which ADR 0110 named, belongs to storage media inventory and has since
three months before that ADR claimed it.

**What cannot be lowered is published, not dropped.** An override with no ports
has no representation here: an empty port set is an error rather than "any". It
goes into `unlowerable` with a reason, because a plan that silently omitted the
sources' only mandatory deny would look complete.

**The digest covers meaning and nothing else.** No timestamps, no matrix file
order. A digest that moved every run could not tell an unchanged plan from a
changed one, which is the only thing it is for.

This shares no code with `netmodel`, which sits outside framework distribution; a
differential test runs both over the same input and requires the same plan.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginResult, Stage

MATRIX_CLASS = "class.network.security_matrix"


# Protocol tokens the bounded algebra implements. A name outside this set is not
# a protocol it has not heard of - it is a shape it cannot reason about, and
# `!tcp` lowering as a protocol literally named "!tcp" was the demonstration.
_SUPPORTED_PROTOCOLS = frozenset({"tcp", "udp", "sctp", "icmp"})


def _unsupported_transport(protocol: str, numbers: Any) -> str:
    """Why this transport selector cannot be lowered, or an empty string.

    Refusal rather than approximation, and the reason is not fastidiousness: the
    probe classes that make the semantic check meaningful are derived from the
    shapes the algebra supports. A range or a negation lowered as if understood
    produces a plan the checks cannot see past, and they would then report it
    clean.

    Measured before this existed: a port range raised a TypeError the registry
    turned into a plugin with no output, and `!tcp` was accepted as a protocol
    named "!tcp" - two rules emitted, nothing reported.
    """
    if protocol not in _SUPPORTED_PROTOCOLS:
        return (
            f"unsupported protocol selector {protocol!r}; the bounded algebra implements "
            f"{sorted(_SUPPORTED_PROTOCOLS)} and refuses shapes it cannot reason about"
        )
    if not isinstance(numbers, list):
        return f"ports.{protocol} must be a list of integers, got {type(numbers).__name__}"
    for item in numbers:
        if isinstance(item, bool) or not isinstance(item, int):
            return (
                f"unsupported port selector {item!r} under {protocol}; ranges, conditions and "
                "expressions are not implemented, and approximating one would hide it from every check"
            )
        if item < 1 or item > 65535:
            return f"port {item} under {protocol} is not a port"
    return ""


def _base(origin: str, effect: str, scope: str, source: str, destination: str) -> dict[str, Any]:
    return {
        "origin": origin,
        "effect": effect,
        "terminal": False,
        "scope": scope,
        "sources": [source],
        "destinations": [destination],
    }


TERMINAL_ORIGIN = "plan:terminal-default-deny"

# Role ranks. A terminal deny is a role, not an effect: treating it as one more
# deny puts it before every permit and after every rule at once, which is a cycle
# rather than an order.
_RANK_DENY = 0
_RANK_PERMIT = 1
_RANK_TERMINAL = 2


class SecurityPlanCompiler(CompilerPlugin):
    """Publish the ordered security plan and what could not be lowered."""

    _PUBLISH_KEY = "security_plan"
    _ROWS_PLUGIN_ID = "base.compiler.instance_rows"
    _ROWS_KEY = "normalized_rows"

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        rows = self._rows(ctx)
        overrides, matrices = self._overrides(ctx, rows)

        rules: list[dict[str, Any]] = []
        unlowerable: list[dict[str, Any]] = []
        # How many overrides each scope declared, so a consumer can check the plan
        # against the intent rather than against itself.
        expected: dict[str, int] = {}

        for override in overrides:
            expected[str(override.get("matrix_ref"))] = expected.get(str(override.get("matrix_ref")), 0) + 1
            lowered, reason = self._lower_one(override)
            if not lowered:
                unlowerable.append({**{k: override.get(k) for k in ("name", "matrix_ref")}, "reason": reason})
            else:
                rules.extend(lowered)

        # Every matrix is a scope, whether or not anything in it lowered. Deriving
        # scopes from successful rules alone let a wholly unrepresentable matrix
        # disappear from the plan entirely - and a scope that is absent cannot be
        # reported as unterminated, so the omission hid itself.
        scopes = sorted(matrices)
        for scope in scopes:
            rules.append(self._terminal(scope))

        ordered = self._order(rules)
        # No partial success. A scope with even one override this lowering cannot
        # represent is blocked for strict use in its entirety: the remaining rules
        # are a subset of the intent, and a subset of a restriction is a weaker
        # restriction. The plan is still published, because a shadow plan is worth
        # analysing - but it is labelled, and nothing downstream may treat a
        # blocked scope as eligible.
        blocked = sorted({str(item.get("matrix_ref")) for item in unlowerable})
        # Two different claims, and conflating them was the mistake. Lowering
        # every legacy override of a scope says the compiler represented what was
        # written; it says nothing about whether those overrides were approved,
        # nor whether an independent check has passed. Strict eligibility needs
        # confirmed bindings and independent validation, neither of which exists
        # yet, so nothing is strict-eligible and the field says so rather than
        # inheriting a completeness result.
        lowering_complete = [scope for scope in scopes if scope not in blocked]
        strict_eligible: list[str] = []

        payload = {
            "schema_version": 1,
            # Legacy shape until approved bindings exist. `action: accept` in a
            # security matrix is an authored override, not an approved bound
            # permit, and calling the result a strict plan would make an approval
            # boundary out of a field name. F2 of the post-fix review.
            "provenance": "legacy_shadow",
            "lowering_complete": lowering_complete,
            "strict_eligible": strict_eligible,
            "strict_blocked_reason": (
                "provenance is legacy_shadow: these overrides are authored, not approved bound "
                "permits, and no independent validation of the specialized plan exists yet"
            ),
            "blocked_scopes": blocked,
            "expected_overrides": {scope: expected.get(scope, 0) for scope in scopes},
            "matrices": sorted(matrices),
            "scopes": scopes,
            "rules": ordered,
            "unlowerable": unlowerable,
            "digest": self._digest(ordered),
        }
        ctx.publish(self._PUBLISH_KEY, payload)
        # Also returned on the result: that is the shape every other plugin uses,
        # and it is what a test reads. Reaching into the publish registry works
        # and is banned for a reason - it couples a test to a private structure
        # that the envelope contract is meant to replace.
        return self.make_result([], output_data={self._PUBLISH_KEY: payload})

    # --- inputs -------------------------------------------------------------

    def _rows(self, ctx: PluginContext) -> list[Mapping[str, Any]]:
        try:
            payload = ctx.subscribe(self._ROWS_PLUGIN_ID, self._ROWS_KEY)
        except Exception:  # noqa: BLE001 - absence is reported by the validator that owns it
            return []
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    @staticmethod
    def _class_of(row: Mapping[str, Any]) -> str | None:
        class_ref = row.get("class_ref")
        if isinstance(class_ref, str) and class_ref:
            return class_ref
        payload = row.get("class")
        lineage = payload.get("lineage") if isinstance(payload, Mapping) else None
        return lineage[-1] if isinstance(lineage, list) and lineage else None

    def _overrides(
        self, ctx: PluginContext, rows: Sequence[Mapping[str, Any]]
    ) -> tuple[list[dict[str, Any]], set[str]]:
        """Flatten every matrix's overrides, each tagged with the matrix it came from.

        Selected by declared class, not by identifier prefix: a prefix selector
        only ever sees what its author happened to name that way.
        """
        flattened: list[dict[str, Any]] = []
        matrices: set[str] = set()

        for row in rows:
            if self._class_of(row) != MATRIX_CLASS:
                continue
            matrix_ref = row.get("instance") or row.get("instance_id")
            if not isinstance(matrix_ref, str):
                continue
            matrices.add(matrix_ref)
            overrides = self._field(ctx=ctx, row=row, key="policy_overrides")
            if not isinstance(overrides, list):
                continue
            for override in overrides:
                if isinstance(override, Mapping):
                    flattened.append({**override, "matrix_ref": matrix_ref})

        flattened.sort(key=lambda item: (str(item.get("matrix_ref")), str(item.get("name"))))
        return flattened, matrices

    @staticmethod
    def _field(*, ctx: PluginContext, row: Mapping[str, Any], key: str) -> Any:
        extensions = row.get("extensions")
        if isinstance(extensions, Mapping) and key in extensions:
            return extensions.get(key)
        object_ref = row.get("object_ref")
        payload = ctx.objects.get(object_ref) if isinstance(object_ref, str) else None
        properties = payload.get("properties") if isinstance(payload, Mapping) else None
        return properties.get(key) if isinstance(properties, Mapping) else None

    # --- lowering -------------------------------------------------------------

    def _lower_one(self, override: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
        """One override becomes one rule *per protocol*, or nothing with a reason.

        It used to take `sorted(ports.items())[0]` and emit a single rule. On
        `{tcp: [53], udp: [53]}` that produced the TCP rule and dropped UDP
        silently, with an empty `unlowerable` - for a permit a lost service, for
        a deny a lost restriction, and in neither case a diagnostic. A source
        selector spanning several protocols is several rules; a lowering that
        cannot say that must refuse, not choose.
        """
        name = str(override.get("name") or "").strip()
        source = override.get("from_zone_ref")
        destination = override.get("to_zone_ref")
        action = override.get("action")

        if not name:
            return [], "the override has no name and cannot be traced back to a source"
        if not (isinstance(source, str) and isinstance(destination, str)):
            return [], "the override does not name both zones"
        if action not in ("accept", "drop", "reject"):
            return [], f"unknown action {action!r}"

        origin = f"{'binding' if action == 'accept' else 'guard'}:{name}"
        effect = "permit" if action == "accept" else "deny"
        scope = str(override.get("matrix_ref"))

        ports = override.get("ports")
        if ports is not None and not isinstance(ports, Mapping):
            # A wrong type is not a missing value. `ports: "tcp:443"` became an
            # any-transport permit here, turning a typo into the broadest rule
            # the model can express.
            return [], (
                f"ports must be a mapping of protocol to port list, got {type(ports).__name__}; "
                "a malformed selector is not an absent one"
            )
        if not ports:
            # An override that names no transport constrains every transport.
            # Represented as its own kind rather than as an empty list, which
            # reads as "nothing", or as an enumeration of well-known service
            # ports, which would narrow a deny to the ports someone thought of.
            return (
                [
                    {
                        **_base(origin, effect, scope, source, destination),
                        "transport": {"kind": "any"},
                    }
                ],
                "",
            )

        lowered: list[dict[str, Any]] = []
        for protocol, numbers in sorted(ports.items()):
            unsupported = _unsupported_transport(str(protocol), numbers)
            if unsupported:
                return [], unsupported
            if not isinstance(numbers, list) or not numbers:
                return [], f"ports.{protocol} is empty"
            lowered.append(
                {
                    **_base(origin, effect, scope, source, destination),
                    "transport": {
                        "kind": "ports",
                        "protocol": str(protocol),
                        "ports": sorted(int(item) for item in numbers),
                    },
                }
            )
        return lowered, ""

    @staticmethod
    def _terminal(scope: str) -> dict[str, Any]:
        return {
            "origin": TERMINAL_ORIGIN,
            "effect": "deny",
            "terminal": True,
            "scope": scope,
            "sources": [],
            "destinations": [],
            "transport": {"kind": "any"},
        }

    @staticmethod
    def _order(rules: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Canonical order, with ties broken by the full rule rather than a hash.

        A hash maps many rules onto few slots, and two rules on one slot have no
        defined order at all - only the appearance of one.
        """

        def rank(rule: Mapping[str, Any]) -> int:
            if rule.get("terminal"):
                return _RANK_TERMINAL
            return _RANK_DENY if rule.get("effect") == "deny" else _RANK_PERMIT

        def key(rule: Mapping[str, Any]) -> tuple:
            transport = rule.get("transport") or {}
            return (
                str(rule.get("scope")),
                rank(rule),
                tuple(sorted(rule.get("sources") or [])),
                tuple(sorted(rule.get("destinations") or [])),
                str(transport.get("kind")),
                str(transport.get("protocol") or ""),
                tuple(sorted(transport.get("ports") or [])),
                str(rule.get("origin")),
            )

        # Positions are per scope, and consecutive from zero within it. A global
        # counter looked harmless in a two-matrix topology and put a terminal at
        # position 1 with five rules after it - correct per scope, and a rule list
        # that drops everything after position 1 if a consumer ever flattens it.
        # Each scope is an independent list; numbering them as one is an invitation.
        ordered: list[dict[str, Any]] = []
        position_in_scope: dict[str, int] = {}
        for rule in sorted(rules, key=key):
            scope = str(rule.get("scope"))
            position = position_in_scope.get(scope, 0)
            position_in_scope[scope] = position + 1
            ordered.append({**rule, "position": position})
        return ordered

    @staticmethod
    def _digest(ordered: Sequence[Mapping[str, Any]]) -> str:
        """Identity over what affects authorization, and nothing that records when."""
        payload = [
            {
                "position": rule["position"],
                "scope": rule["scope"],
                "effect": rule["effect"],
                "terminal": rule["terminal"],
                "sources": rule["sources"],
                "destinations": rule["destinations"],
                "transport": rule["transport"],
                "origin": rule["origin"],
            }
            for rule in ordered
        ]
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return "sha256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = ["SecurityPlanCompiler", "TERMINAL_ORIGIN"]

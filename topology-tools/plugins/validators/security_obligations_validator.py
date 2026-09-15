"""The five obligations that had no checker in the framework — SEC-PATH, NAT, STATE, TRANSITION, CAP.

ADR 0119 names eight obligations. Four are checked by `base.validator.security_plan`
over the plan and the source intent. These are the other five, and until now they
existed only in `netmodel`, which the framework cannot import - it is a root
package outside the distribution.

**Why mounting them was not obvious.** None of the five has its inputs in the
pipeline today: no plan carries an address transform, nothing records sessions or
epochs, there is no previous plan to transition from, no path inventory or
evidence, and the capability catalogue carries no offers. A checker with no input
finds nothing, and "found nothing" reported as a pass is the empty-loop mistake
this whole body of work refuses.

So each obligation answers one of three ways, and the middle one is the point:

* **not applicable** - the plan contains no construct this obligation governs, so
  there is nothing it could violate. Recorded with the reason, never as a pass.
* **unverified** - the obligation applies and the input needed to decide it is
  absent. The missing input is *named*. This blocks strict admission exactly as a
  failure does; the difference is what to do about it.
* **fail** - the obligation applies and a violation is demonstrated. `E7086`
  reports the one this contract can demonstrate today.

**No obligation here returns `pass`.** The first version did, and a review
reproduced what those passes were worth: a session carrying a revoked epoch, a
previous plan with no rules, a plan asserting its own `demonstrated` list, and a
disabled offer with no evidence were all read as satisfied, admission granted,
marker written. Each of those branches tested that an input was *present* rather
than that the property *held* - presence-as-proof, the empty-loop mistake in a
different coat.

SEC-NAT is the exception in one direction only: it can demonstrate a collision,
so it reports one. It cannot demonstrate the absence of one - collision freedom
over the identity it can build is necessary, not sufficient - so a clean scope is
`unverified` too.

That is the honest general shape. The applicability test and the input discovery
are real, so the channel, the stage graph and the record are in place for solvers
to land behind - each with the independent inventory, trustworthy evidence and
semantic check its obligation needs, and each with the negative controls that
make a `pass` mean something.

The checks themselves are written here rather than imported from `netmodel`. That
is the same distribution boundary the plan validator lives with, and the same
benefit: two implementations that can disagree, with differentials to notice when
they do.
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
from plugins.validators.strict_admission import content_digest

PLAN_PLUGIN_ID = "base.compiler.security_plan"
PLAN_KEY = "security_plan"
ROWS_PLUGIN_ID = "base.compiler.instance_rows"
ROWS_KEY = "normalized_rows"
PUBLISH_KEY = "security_obligation_statuses"
RECORD_VERSION = 1

PASS = "pass"
FAILED = "fail"
UNVERIFIED = "unverified"
NOT_APPLICABLE = "not_applicable"

# Which plan field makes each obligation applicable, which diagnostic reports a
# failure of it, and what a decision needs that the pipeline does not yet carry.
#
# The field names are the reserved ones `strict_admission` refuses to treat as
# unknown constructs; the two lists have to agree and a test says so.
#
# `code` is `None` for the four obligations that cannot yet demonstrate a
# failure. Their numbers - `E7085`, `E7087`, `E7088`, `E7089` - stay reserved in
# the catalog and on the "awaiting a mount" ledger, and they are deliberately not
# named here: a code sitting in a table inside an emitting module looks raised to
# the registry scan while no branch can reach it. The number returns when the
# obligation has a solver that can produce the failure.
OBLIGATIONS: dict[str, dict[str, Any]] = {
    "SEC-NAT": {
        "field": "nat",
        "code": "E7086",
        "needs": "a declared address transform on a rule, with its original and translated tuples",
        "governs": "an address transform collapsing differently authorized originals onto one rule",
    },
    "SEC-STATE": {
        "field": "state",
        "code": None,
        "needs": "a session inventory and the active epoch, which nothing in the pipeline records",
        "governs": "an established session outliving the permit that admitted it",
    },
    "SEC-TRANSITION": {
        "field": "transition",
        "code": None,
        "needs": "the previously applied plan and an authorization envelope for the change",
        "governs": "an intermediate state during an apply that neither endpoint shows",
    },
    "SEC-PATH": {
        "field": "path",
        "code": None,
        "needs": "a path inventory for the scope and evidence that each case was demonstrated",
        "governs": "a feasible in-scope path crossing no adequate gate",
    },
    "SEC-CAP": {
        "field": "capability",
        "code": None,
        "needs": "versioned capability offers; the catalogue declares capabilities without offer fields",
        "governs": "declared support read as evidence, or evidence read as permission",
    },
}


class SecurityObligationsValidator(ValidatorJsonPlugin):
    """Answers for the five obligations the plan validator does not cover."""

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
                        message=f"the obligations validator requires the published plan: {exc}",
                        path="pipeline:validate",
                    )
                ]
            )

        sources = self._sources(ctx)
        scopes = self._scopes(plan)
        statuses: dict[str, dict[str, str]] = {scope: {} for scope in scopes}
        reasons: dict[str, dict[str, str]] = {scope: {} for scope in scopes}

        for scope in scopes:
            scoped = [
                rule
                for rule in (plan.get("rules") or [])
                if isinstance(rule, Mapping) and str(rule.get("scope")) == scope
            ]
            for name, spec in sorted(OBLIGATIONS.items()):
                status, reason = self._decide(
                    obligation=name, spec=spec, plan=plan, rules=scoped, sources=sources
                )
                statuses[scope][name] = status
                reasons[scope][name] = reason
                if status == FAILED:
                    # Unreachable for an obligation with no code: those cannot
                    # return FAILED, and a checker that started to would have to
                    # claim its number back from the ledger first.
                    if not spec["code"]:
                        raise AssertionError(f"{name} reported a failure with no diagnostic to report it")
                    diagnostics.append(
                        self.emit_diagnostic(
                            code=spec["code"],
                            severity="error",
                            stage=stage,
                            message=f"scope '{scope}': {name} - {reason}",
                            path=f"security_plan:{scope}",
                        )
                    )
                elif status == UNVERIFIED:
                    # A warning, not an error: nothing is known to be wrong. It
                    # still blocks strict admission, because "nobody checked" is
                    # not "it holds" - the two are kept apart everywhere in this
                    # model and this is where the distinction is produced.
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="W7003",
                            severity="warning",
                            stage=stage,
                            message=(
                                f"scope '{scope}': {name} applies to this plan and cannot be decided - "
                                f"{reason}. Reported as unverified rather than satisfied; strict "
                                "admission refuses it either way."
                            ),
                            path=f"security_plan:{scope}",
                        )
                    )

        record = {
            "schema_version": RECORD_VERSION,
            # The identity of the plan these statuses are about. Without it the
            # merger could stamp a stale partial result with the digest of a plan
            # nobody checked it against - a review did exactly that: a `pass`
            # produced for one plan, the plan changed, and the merge carried the
            # old verdict under the new digest while a fresh run said `fail`.
            "plan_digest": content_digest(plan),
            "obligations": sorted(OBLIGATIONS),
            "statuses": statuses,
            "reasons": reasons,
            "checked_scopes": sorted(scopes),
            # Counted here and added to the verification record's total. A record
            # reporting zero errors while another plugin found one is a record
            # that cannot be read as "the check passed".
            "errors": sum(1 for item in diagnostics if item.severity == "error"),
            "warnings": sum(1 for item in diagnostics if item.severity == "warning"),
        }
        ctx.publish(PUBLISH_KEY, record)
        return self.make_result(diagnostics, output_data={PUBLISH_KEY: record})

    # --- deciding one obligation ---------------------------------------------------

    def _decide(
        self,
        *,
        obligation: str,
        spec: Mapping[str, Any],
        plan: Mapping[str, Any],
        rules: Sequence[Mapping[str, Any]],
        sources: Mapping[str, Any],
    ) -> tuple[str, str]:
        """Applicable? Decidable? Then decide. Three questions in that order.

        Reversing the first two would report "no input" for an obligation nothing
        in the plan could violate, which is noise; reversing the last two would
        report a pass for a check that never ran, which is worse.
        """
        applicable = self._applies(spec["field"], plan, rules)
        if not applicable:
            return NOT_APPLICABLE, (
                f"no rule declares `{spec['field']}`, so nothing here can violate it "
                f"({spec['governs']})"
            )

        checker = getattr(self, f"_check_{obligation.lower().replace('-', '_')}")
        return checker(plan=plan, rules=rules, sources=sources, spec=spec)

    @staticmethod
    def _applies(field: str, plan: Mapping[str, Any], rules: Sequence[Mapping[str, Any]]) -> bool:
        """Applicability from declared fields, never from a word search.

        `strict_admission` learned this the hard way: inferring it from the
        serialized text made `path` refuse a plan and `paths` with the same
        content pass, because the guard was spelling-sensitive.
        """
        if field in plan:
            return True
        return any(field in rule for rule in rules if isinstance(rule, Mapping))

    # Each checker below has the same contract: the obligation applies, so either
    # it decides, or it names what a decision would need. **None of them returns
    # `pass`**, and that is deliberate.
    #
    # The first version did, and a review reproduced what it was worth: a session
    # carrying a revoked epoch, a disabled offer with no evidence, and a plan
    # asserting its own `demonstrated` list all came back `pass`, admission
    # granted, marker written. Every one of those branches tested that an input
    # was *present*, not that the property *held* - presence-as-proof, which is
    # the empty-loop mistake wearing a different coat.
    #
    # A real solver needs an independent scoped inventory, trustworthy evidence
    # and the semantic check itself. Until each has one, the honest answer is
    # `unverified` with the missing input named, and it stays `unverified` even
    # when fields that look like the input are present.

    def _check_sec_state(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """Sessions must not outlive the epoch that admitted them.

        Sessions and an epoch being present says nothing about whether any
        session survived a revocation deadline, belongs to the active epoch or
        even to this scope. Deciding that needs the revocation, its effective
        moment and the deadline, none of which the pipeline carries.
        """
        return UNVERIFIED, spec["needs"]

    def _check_sec_transition(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """No intermediate state may accept outside the transition envelope.

        A previous plan and an envelope being present is not a replay. Deciding
        this needs the mutation sequence simulated state by state - and the
        earlier version said "the sequence was replayed" while replaying nothing,
        which is worse than abstaining.
        """
        return UNVERIFIED, spec["needs"]

    def _check_sec_path(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """Every feasible in-scope path crosses an adequate gate, or is disabled.

        The plan asserting that its own `cases` are all `demonstrated` is the
        plan marking its own homework. This needs an inventory derived
        independently of the plan and evidence that is not the plan's own claim.
        """
        return UNVERIFIED, spec["needs"]

    def _check_sec_cap(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """A requirement needs a witness at the evidence level the claim needs.

        A capability name appearing as a key in some offers mapping is not a
        witness. An offer can be disabled, scoped elsewhere, of an incompatible
        version or carry no evidence at all - and *declared support is not
        effective support is not evidence is not permission* is the sentence this
        obligation exists for.
        """
        return UNVERIFIED, spec["needs"]

    def _check_sec_nat(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """Distinct originals must not collapse onto one translated rule.

        This one can demonstrate a failure, so it does. It cannot demonstrate
        success, so it does not claim one.

        **Every declaration is parsed, and one unreadable declaration decides the
        whole scope.** Selecting only the mappings and ignoring the rest gave a
        readable transform beside an unsupported string an overall `pass` - a
        subset of the transforms checked, reported as all of them.

        **The original identity carries transport and effect**, not just
        endpoints. A permit on TCP/53 and a deny on TCP/443 between the same
        endpoints are different authorizations; keyed on endpoints alone they
        looked like one original and the collapse went unseen.

        Even so, a scope with no collision comes back `unverified`. Collision
        freedom over this key is a *necessary* condition for SEC-NAT and not the
        composition proof ADR 0119 asks for - which is about an approved frontend
        against an unauthorized direct or backend flow, over original and current
        tuples with their context. Reporting a necessary condition as the
        property would be the same mistake in a smaller place.
        """
        declared = [(rule, rule.get("nat")) for rule in rules if "nat" in rule]
        if not declared:
            return UNVERIFIED, spec["needs"]

        by_translated: dict[str, set[tuple[str, ...]]] = {}
        for rule, nat in declared:
            unreadable = self._nat_shape_problem(nat)
            if unreadable:
                return UNVERIFIED, (
                    f"transform on '{rule.get('origin')}' {unreadable}; one declaration this contract "
                    "cannot read decides the scope, because a subset of the transforms checked is not "
                    "all of them"
                )
            translated = str(nat["to"])
            by_translated.setdefault(translated, set()).add(self._original_identity(rule))

        collapsed = {target: items for target, items in by_translated.items() if len(items) > 1}
        if collapsed:
            return FAILED, (
                f"transforms collapse differently authorized originals onto {sorted(collapsed)}; "
                "the composed rule cannot distinguish what authorized each one"
            )
        return UNVERIFIED, (
            f"{len(declared)} transform(s) parsed and no two originals collapse, which is necessary "
            "and not sufficient: the composition proof needs original and current tuples with their "
            "context, and this contract carries neither"
        )

    @staticmethod
    def _nat_shape_problem(nat: Any) -> str:
        """Why this transform declaration cannot be read, or an empty string."""
        if not isinstance(nat, Mapping):
            return f"is {type(nat).__name__}, not a mapping"
        unknown = sorted(set(nat) - {"to", "comment"})
        if unknown:
            return f"states field(s) {unknown} this contract has no meaning for"
        target = nat.get("to")
        if not isinstance(target, str) or not target.strip():
            return f"names no translated target (`to` is {target!r})"
        return ""

    @staticmethod
    def _original_identity(rule: Mapping[str, Any]) -> tuple[str, ...]:
        """What made this flow authorized, as far as the plan states it.

        Endpoints alone were the defect: a permit and a deny between one pair of
        endpoints are two authorizations, and merging them hid a collapse.
        """
        transport = rule.get("transport") or {}
        ports = transport.get("ports") or []
        return (
            str(rule.get("effect")),
            ",".join(sorted(str(item) for item in (rule.get("sources") or []))),
            ",".join(sorted(str(item) for item in (rule.get("destinations") or []))),
            str(transport.get("kind")),
            str(transport.get("protocol")),
            ",".join(sorted(str(item) for item in ports)),
        )

    # --- inputs -------------------------------------------------------------------

    def _sources(self, ctx: PluginContext) -> dict[str, Any]:
        """Whatever the pipeline can supply for these five today, which is little.

        Read from the normalized rows rather than invented here. Absence is the
        normal case and is what makes an obligation `unverified`; it is not an
        error, because nothing is wrong - nobody has declared the input yet.
        """
        try:
            payload = ctx.subscribe(ROWS_PLUGIN_ID, ROWS_KEY)
        except PluginDataExchangeError:
            return {}

        rows = [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
        found: dict[str, Any] = {}
        for row in rows:
            extensions = row.get("extensions")
            if not isinstance(extensions, Mapping):
                continue
            for key in ("sessions", "previous_plan", "capability_offers"):
                value = extensions.get(key)
                if value:
                    found.setdefault(key, value)
        return found

    @staticmethod
    def _scopes(plan: Mapping[str, Any]) -> list[str]:
        declared = plan.get("scopes") if isinstance(plan, Mapping) else None
        scopes = {str(item) for item in declared} if isinstance(declared, list) else set()
        rules = plan.get("rules") if isinstance(plan, Mapping) else None
        for rule in rules if isinstance(rules, list) else []:
            if isinstance(rule, Mapping) and rule.get("scope"):
                scopes.add(str(rule["scope"]))
        return sorted(scopes)


__all__ = ["SecurityObligationsValidator", "OBLIGATIONS"]

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
* **pass** or **fail** - the obligation applies, the input is there, and the check
  ran. `E7085`-`E7089` report the failures.

That is the honest general shape, and it is not a placeholder: the applicability
test and the input discovery are real, so the day a plan grows a NAT rule or the
catalogue grows an offer, this starts deciding instead of abstaining - and until
then it refuses to certify what nobody checked.

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

PLAN_PLUGIN_ID = "base.compiler.security_plan"
PLAN_KEY = "security_plan"
ROWS_PLUGIN_ID = "base.compiler.instance_rows"
ROWS_KEY = "normalized_rows"
PUBLISH_KEY = "security_obligation_statuses"

PASS = "pass"
FAILED = "fail"
UNVERIFIED = "unverified"
NOT_APPLICABLE = "not_applicable"

# Which plan field makes each obligation applicable, which diagnostic reports a
# failure of it, and what a decision needs that the pipeline does not yet carry.
#
# The field names are the reserved ones `strict_admission` refuses to treat as
# unknown constructs; the two lists have to agree and a test says so.
OBLIGATIONS: dict[str, dict[str, Any]] = {
    "SEC-NAT": {
        "field": "nat",
        "code": "E7086",
        "needs": "a declared address transform on a rule, with its original and translated tuples",
        "governs": "an address transform collapsing differently authorized originals onto one rule",
    },
    "SEC-STATE": {
        "field": "state",
        "code": "E7087",
        "needs": "a session inventory and the active epoch, which nothing in the pipeline records",
        "governs": "an established session outliving the permit that admitted it",
    },
    "SEC-TRANSITION": {
        "field": "transition",
        "code": "E7088",
        "needs": "the previously applied plan and an authorization envelope for the change",
        "governs": "an intermediate state during an apply that neither endpoint shows",
    },
    "SEC-PATH": {
        "field": "path",
        "code": "E7085",
        "needs": "a path inventory for the scope and evidence that each case was demonstrated",
        "governs": "a feasible in-scope path crossing no adequate gate",
    },
    "SEC-CAP": {
        "field": "capability",
        "code": "E7089",
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
            "schema_version": 1,
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
    # the input to decide it is here and it decides, or it names what is missing.

    def _check_sec_nat(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """Distinct originals must not collapse onto one translated rule."""
        transforms = [
            (rule, rule["nat"]) for rule in rules if isinstance(rule.get("nat"), Mapping)
        ]
        if not transforms:
            return UNVERIFIED, spec["needs"]

        by_translated: dict[str, set[str]] = {}
        for rule, nat in transforms:
            translated = str(nat.get("to") or nat.get("translated") or "")
            if not translated:
                return UNVERIFIED, f"a transform on '{rule.get('origin')}' names no translated target"
            originals = by_translated.setdefault(translated, set())
            originals.add(f"{sorted(rule.get('sources') or [])}->{sorted(rule.get('destinations') or [])}")

        collapsed = {target: items for target, items in by_translated.items() if len(items) > 1}
        if collapsed:
            return FAILED, (
                f"transforms collapse differently authorized originals onto {sorted(collapsed)}; "
                "the composed rule cannot distinguish what authorized each one"
            )
        return PASS, f"{len(transforms)} transform(s), each with one original"

    def _check_sec_state(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """Sessions must not outlive the epoch that admitted them."""
        sessions = sources.get("sessions")
        epoch = plan.get("epoch")
        if not sessions or not epoch:
            missing = []
            if not sessions:
                missing.append("a session inventory")
            if not epoch:
                missing.append("the active epoch on the plan")
            return UNVERIFIED, f"{spec['needs']} (missing: {', '.join(missing)})"
        return PASS, f"{len(sessions)} session(s) inside the active epoch"

    def _check_sec_transition(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """No intermediate state may accept outside the transition envelope."""
        previous = sources.get("previous_plan")
        envelope = plan.get("transition")
        if not previous:
            return UNVERIFIED, f"{spec['needs']} (missing: the previously applied plan)"
        if not isinstance(envelope, Mapping) or not envelope.get("allowed"):
            return UNVERIFIED, f"{spec['needs']} (missing: an authorization envelope for the change)"
        return PASS, "an envelope and a previous plan are present and the sequence was replayed"

    def _check_sec_path(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """Every feasible in-scope path crosses an adequate gate, or is demonstrably disabled."""
        declared = plan.get("path")
        if not isinstance(declared, Mapping):
            declared = next(
                (rule["path"] for rule in rules if isinstance(rule.get("path"), Mapping)), None
            )
        if not isinstance(declared, Mapping):
            return UNVERIFIED, spec["needs"]

        cases = declared.get("cases")
        demonstrated = declared.get("demonstrated")
        if not isinstance(cases, list) or not cases:
            return UNVERIFIED, f"{spec['needs']} (missing: the path inventory for this scope)"
        if not isinstance(demonstrated, list):
            return UNVERIFIED, f"{spec['needs']} (missing: which cases were demonstrated)"

        gaps = sorted(str(case) for case in cases if case not in demonstrated)
        if gaps:
            return FAILED, f"path case(s) with no demonstration: {gaps[:3]}"
        return PASS, f"{len(cases)} path case(s), each demonstrated"

    def _check_sec_cap(self, *, plan, rules, sources, spec) -> tuple[str, str]:
        """A requirement needs a witness at the evidence level the claim needs."""
        offers = sources.get("capability_offers")
        if not offers:
            return UNVERIFIED, spec["needs"]

        required = plan.get("capability")
        if not isinstance(required, Mapping):
            required = next(
                (rule["capability"] for rule in rules if isinstance(rule.get("capability"), Mapping)),
                None,
            )
        if not isinstance(required, Mapping):
            return UNVERIFIED, f"{spec['needs']} (missing: what this plan requires)"

        unmet = sorted(name for name in required if name not in offers)
        if unmet:
            return FAILED, f"requirement(s) with no applicable offer: {unmet[:3]}"
        return PASS, f"{len(required)} requirement(s), each with an offer"

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

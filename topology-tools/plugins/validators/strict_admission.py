"""The admission contract every strict backend consumer must use.

Nothing renders the security plan yet, and that is precisely why this exists now.
"No renderer" prevents application; it does not constitute a boundary, and a
boundary written after the first consumer arrives is written around it.

What admission binds is a **chain**, and each link is checked here rather than
assumed:

    approval -> the exact intent that was checked -> the verification -> the plan

The 2026-09-14 review found the chain open at both ends. `approved=True` was read
for its truthiness alone, so an approval issued for a different scope admitted
this plan; and `complete` meant only that the source input was readable, so a
record reporting an unverified obligation was a pass. Both are now refusals.

Conditions, each refusing something that would otherwise look like progress:

1. `legacy_shadow` is refused **regardless of lowering completeness**. Lowering
   every override says the compiler represented what was written; it says nothing
   about whether anyone approved it.
2. The verification record must be complete in shape. A missing `errors` field is
   not zero errors, and a missing obligation status is not a pass - an absent
   field is an unanswered question, and this is where unanswered questions are
   refused rather than defaulted.
3. A plan changed after checking loses admission - including when its own digest
   is recomputed to match. Admission compares a digest **it computes** against the
   one the verifier recorded; trusting the digest a payload presents would let a
   mutated plan certify itself.
4. The approval must name the same intent the verifier checked, by digest, and
   must cover the scopes being admitted. An approval that names nothing is a
   boolean, and a boolean cannot say what it approved.
5. Every obligation applicable to *this plan* must have passed for *each scope
   being admitted*. Obligations the framework cannot check yet are listed with
   the construct that makes them applicable: a plan containing that construct is
   refused, and a plan containing none of it does not need the check.
6. A refusal never enables a legacy path. Falling back on refusal turns the
   boundary into a preference, and the unapproved plan runs anyway.

`availability_waiver` with an owner and a rationale makes a statement traceable.
It is not authority: whether that person may waive it, and whether the waiver was
agreed, belong to admission and are not properties of two filled-in strings.

**No producer of approvals exists.** Nothing in the topology declares an approver,
so in the real pipeline every plan is refused at condition 4 - after being refused
at condition 1 for provenance. That is the honest state, and the contract is
written now so the first consumer meets a boundary instead of defining one.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

STRICT_PROVENANCE = "strict"
RECORD_VERSION = 1
PASS = "pass"

# What an independent verification record must state. Every one of these is
# required: the review's `MISSING_RECORD_FIELDS` counterexample was a record with
# no `errors` and no `checked_scopes` that was admitted, because absence read as
# zero and as "nothing to disagree with".
REQUIRED_RECORD_FIELDS = (
    "schema_version",
    "plan_digest",
    "intent_digest",
    "evidence_digest",
    "errors",
    "warnings",
    "checked_scopes",
    "obligations",
    "source_available",
)

# What an approval must state. `approved: True` on its own is not an approval of
# anything in particular, which is what let an unrelated approval admit a plan.
# `evidence_digest` is separate from `intent_digest` on purpose. A waiver's owner
# and rationale are not part of the permission set - changing them leaves the
# semantics identical - but they are the evidence on which otherwise unverified
# availability is discharged. Folding them into semantic identity would make an
# unrelated plan look changed; leaving them out entirely let a previous approval
# admit a statement somebody else now signs.
REQUIRED_APPROVAL_FIELDS = (
    "approved",
    "approved_by",
    "intent_digest",
    "evidence_digest",
    "scopes",
    "epoch",
)

# Obligations the framework checks today, in the plugin that publishes the record.
CHECKED_OBLIGATIONS = ("SEC-ORDER", "SEC-COVER", "SEC-AUTH", "SEC-AVAIL")

# The plan shape this contract understands, stated as a closed set. Anything else
# is refused before admission rather than ignored.
#
# The first version searched the serialized plan for quoted words, and a review
# showed what that is worth: `path` made SEC-PATH applicable and refused the
# plan, while `paths` carrying identical content was admitted, because the guard
# was spelling-sensitive rather than shape-aware. Absence of a spelling is not
# evidence that an obligation does not apply.
KNOWN_PLAN_FIELDS = frozenset(
    {
        "schema_version",
        "provenance",
        "scopes",
        "matrices",
        "rules",
        "lowering_complete",
        "strict_eligible",
        "strict_blocked_reason",
        "blocked_scopes",
        "expected_overrides",
        "unlowerable",
        "digest",
        "epoch",
    }
)

KNOWN_RULE_FIELDS = frozenset(
    {"origin", "effect", "terminal", "scope", "sources", "destinations", "transport", "position"}
)

KNOWN_TRANSPORT_FIELDS = frozenset({"kind", "protocol", "ports"})

# Values, not only key names. Closing the set of *fields* left the set of
# *meanings* open: a review admitted `transport.kind: not_implemented`, a
# transport with no `kind` at all, and `schema_version: 999`. A field whose value
# this contract cannot interpret is exactly as unadmittable as a field it has
# never heard of - in the first case the renderer would read a token nobody
# defined, in the second it would read a plan written to a grammar nobody here
# knows.
PLAN_SCHEMA_VERSION = 1
KNOWN_TRANSPORT_KINDS = frozenset({"ports", "any"})
KNOWN_EFFECTS = frozenset({"permit", "deny"})

# Obligations implemented in `netmodel` and not mounted in any framework plugin,
# each with the *declared field* that would make it applicable. These names are
# reserved: a plan may carry them, and carrying one makes the obligation
# applicable, so the plan is refused until the check is mounted. Every other
# unknown field is refused outright as an unsupported construct - which is how a
# differently spelled variant of one of these is caught.
DEFERRED_OBLIGATION_FIELDS: dict[str, str] = {
    "nat": "SEC-NAT",
    "state": "SEC-STATE",
    "transition": "SEC-TRANSITION",
    "path": "SEC-PATH",
    "capability": "SEC-CAP",
}

DEFERRED_OBLIGATIONS: tuple[str, ...] = tuple(sorted(set(DEFERRED_OBLIGATION_FIELDS.values())))


class AdmissionError(ValueError):
    """Raised when an admission decision is asked for with malformed inputs."""


@dataclass(frozen=True, slots=True)
class Admission:
    """The verdict, and why. A refusal is a normal outcome and names its reasons."""

    admitted: bool
    reasons: tuple[str, ...] = ()
    plan_digest: str = ""
    intent_digest: str = ""
    inputs_digest: str = ""
    scopes: tuple[str, ...] = ()

    # Never true. A refusal that permitted a fallback would be a preference, and
    # the unapproved plan would run anyway - which is the failure this whole
    # boundary exists to prevent. It is a field rather than a comment so a
    # consumer reading the verdict has to see it.
    legacy_fallback_permitted: bool = field(default=False, init=False)

    def __str__(self) -> str:
        if self.admitted:
            return f"admitted {list(self.scopes)}, plan {self.plan_digest[:19]}"
        return "refused: " + "; ".join(self.reasons)


def content_digest(payload: Any) -> str:
    """A digest of what is actually here, computed rather than accepted.

    The payload's **own top-level** `digest` is excluded, because a payload that
    supplies its own identity can be edited to agree with itself.

    Nothing else is excluded. The first version stripped every field named
    `digest` at any depth, which made a nested reference's digest invisible to
    identity: changing `evidence_ref.digest` left the plan's identity unchanged
    and kept its admission. A nested reference is not supported here, and
    `nested_digest_fields` refuses it rather than digesting around it.
    """
    if isinstance(payload, Mapping):
        body = {key: value for key, value in payload.items() if key != "digest"}
    else:
        body = payload
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256-" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def nested_digest_fields(payload: Any, *, _path: str = "") -> list[str]:
    """Paths of `digest` fields below the top level, which this contract refuses.

    A nested digest is a reference to content that is not here. Admitting it
    would mean admitting something whose identity this decision never saw, so the
    shape is rejected instead of silently included or silently excluded.
    """
    found: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in sorted(payload.items()):
            here = f"{_path}.{key}" if _path else str(key)
            if key == "digest" and _path:
                found.append(here)
            found.extend(nested_digest_fields(value, _path=here))
    elif isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            found.extend(nested_digest_fields(item, _path=f"{_path}[{index}]"))
    return found


def _fields_present(plan: Mapping[str, Any]) -> set[str]:
    """Declared field names anywhere in the plan's known structure."""
    present = set(plan.keys())
    rules = plan.get("rules")
    for rule in rules if isinstance(rules, list) else []:
        if isinstance(rule, Mapping):
            present |= set(rule.keys())
    return present


def unsupported_constructs(plan: Mapping[str, Any]) -> list[str]:
    """Fields this contract has no meaning for, which it refuses rather than ignores.

    A plan is a closed shape here. An unknown field may carry semantics no
    obligation was checked against, and admitting it would mean admitting
    whatever it means. The reserved deferred-obligation names are not unknown -
    they make their obligation applicable instead.
    """
    known_plan = KNOWN_PLAN_FIELDS | set(DEFERRED_OBLIGATION_FIELDS)
    known_rule = KNOWN_RULE_FIELDS | set(DEFERRED_OBLIGATION_FIELDS)

    found = [f"plan.{name}" for name in sorted(set(plan.keys()) - known_plan)]

    rules = plan.get("rules")
    for index, rule in enumerate(rules if isinstance(rules, list) else []):
        if not isinstance(rule, Mapping):
            found.append(f"plan.rules[{index}] is not a mapping")
            continue
        found.extend(f"plan.rules[{index}].{name}" for name in sorted(set(rule.keys()) - known_rule))
        transport = rule.get("transport")
        if isinstance(transport, Mapping):
            found.extend(
                f"plan.rules[{index}].transport.{name}"
                for name in sorted(set(transport.keys()) - KNOWN_TRANSPORT_FIELDS)
            )
    return found


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _transport_errors(where: str, transport: Any) -> list[str]:
    """A transport this contract can act on, or the reason it cannot."""
    if not isinstance(transport, Mapping):
        return [f"{where} is not a mapping"]

    kind = transport.get("kind")
    if kind is None:
        # The case that slipped through: no `kind` at all. A consumer would have
        # to guess, and every guess is a rule it was never authorized to write.
        return [f"{where}.kind is absent; a transport with no kind has no meaning here"]
    if kind not in KNOWN_TRANSPORT_KINDS:
        return [f"{where}.kind is {kind!r}; this contract acts on {sorted(KNOWN_TRANSPORT_KINDS)}"]

    if kind == "any":
        extra = sorted(set(transport) - {"kind"})
        return [f"{where}.{name} is stated beside kind 'any', which constrains nothing" for name in extra]

    errors: list[str] = []
    protocol = transport.get("protocol")
    if not isinstance(protocol, str) or not protocol:
        errors.append(f"{where}.protocol is {protocol!r}; kind 'ports' needs a named protocol")

    ports = transport.get("ports")
    if not isinstance(ports, list) or not ports:
        errors.append(f"{where}.ports is {ports!r}; kind 'ports' needs a non-empty port list")
    else:
        bad = [
            item
            for item in ports
            if isinstance(item, bool) or not isinstance(item, int) or not 1 <= item <= 65535
        ]
        if bad:
            errors.append(f"{where}.ports contains {bad!r}, which are not ports in 1-65535")
    return errors


def malformed_constructs(plan: Mapping[str, Any]) -> list[str]:
    """Fields whose *values* this contract cannot act on.

    `unsupported_constructs` closes the set of field names. This closes the set
    of meanings, which a review found still open: a plan declaring
    `schema_version: 999` or a transport kind nobody implemented was admitted,
    because the key was spelled correctly.
    """
    errors: list[str] = []

    version = plan.get("schema_version")
    if version != PLAN_SCHEMA_VERSION:
        errors.append(
            f"plan.schema_version is {version!r}; this contract reads {PLAN_SCHEMA_VERSION} and cannot "
            "know what a later grammar means by the fields it recognises"
        )

    for name in ("scopes", "lowering_complete", "strict_eligible", "blocked_scopes"):
        if name in plan and not _string_list(plan[name]):
            errors.append(f"plan.{name} is not a list of non-empty names")

    rules = plan.get("rules")
    if not isinstance(rules, list):
        errors.append(f"plan.rules is {type(rules).__name__}, not a list")
        return errors

    for index, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            continue  # reported by unsupported_constructs
        where = f"plan.rules[{index}]"

        effect = rule.get("effect")
        if effect not in KNOWN_EFFECTS:
            errors.append(f"{where}.effect is {effect!r}; this contract acts on {sorted(KNOWN_EFFECTS)}")

        if not isinstance(rule.get("terminal"), bool):
            errors.append(f"{where}.terminal is {rule.get('terminal')!r}, which is not a boolean")

        position = rule.get("position")
        if isinstance(position, bool) or not isinstance(position, int):
            errors.append(f"{where}.position is {position!r}, which is not an index")

        scope = rule.get("scope")
        if not isinstance(scope, str) or not scope:
            errors.append(f"{where}.scope is {scope!r}; every rule belongs to a named scope")

        for side in ("sources", "destinations"):
            if side in rule and not isinstance(rule[side], list):
                errors.append(f"{where}.{side} is not a list")

        errors.extend(_transport_errors(f"{where}.transport", rule.get("transport")))
    return errors


def applicable_obligations(plan: Mapping[str, Any]) -> tuple[str, ...]:
    """Which obligations this particular plan has to have passed.

    The four checked ones always apply. A deferred one applies when the plan
    declares the field that carries the construct it governs. Together with
    `unsupported_constructs` - which refuses every field that is neither known
    nor reserved - this is the fail-closed guard the keyword search was only
    described as being.
    """
    present = _fields_present(plan)
    deferred = tuple(
        sorted({obligation for field, obligation in DEFERRED_OBLIGATION_FIELDS.items() if field in present})
    )
    return (*CHECKED_OBLIGATIONS, *deferred)


def _missing(payload: Mapping[str, Any], required: Iterable[str]) -> list[str]:
    return [name for name in required if name not in payload]


def evaluate(
    *,
    plan: Mapping[str, Any] | None,
    verification: Mapping[str, Any] | None,
    approved_intent: Mapping[str, Any] | None = None,
    scopes: Sequence[str] | None = None,
    expected_epoch: str | None = None,
) -> Admission:
    """Decide admission from the plan, the verification record and an approval.

    `verification` is what an independent check recorded: the digest of the plan
    it examined, the digest of the intent it examined it against, and a status
    per obligation per scope. It is not taken from the plan.

    `scopes` names what is being admitted. It defaults to the plan's
    `strict_eligible`, and nothing outside that list can be requested: admission
    is per scope, so a renderer receives the projection that was admitted rather
    than the whole plan.

    `expected_epoch` is the epoch the caller is operating in, and it has no
    default. Requiring the approval to carry a non-empty epoch string, as the
    first version did, bound nothing: with no plan epoch to compare against, the
    same verified plan was admitted under `old-epoch` and `new-epoch` alike. This
    boundary cannot manufacture freshness - it can only refuse to decide without
    being told which epoch the decision is for.
    """
    reasons: list[str] = []

    if not isinstance(plan, Mapping):
        return Admission(admitted=False, reasons=("there is no plan to admit",))

    unsupported = unsupported_constructs(plan)
    if unsupported:
        reasons.append(
            f"the plan carries construct(s) this contract has no meaning for: {unsupported}. An "
            "unknown field may carry semantics no obligation was checked against"
        )

    malformed = malformed_constructs(plan)
    if malformed:
        reasons.append(f"the plan carries value(s) this contract cannot act on: {malformed}")

    if not str(expected_epoch or "").strip():
        reasons.append(
            "no expected epoch was supplied, so this decision cannot be epoch-qualified; an approval "
            "carrying any epoch string would be accepted"
        )

    nested = nested_digest_fields(plan)
    if nested:
        reasons.append(
            f"the plan carries nested digest field(s) {nested}; a reference to content this decision "
            "cannot see is not supported, and digesting around it would leave that content unbound"
        )

    digest = content_digest(plan)

    provenance = str(plan.get("provenance") or "")
    if provenance != STRICT_PROVENANCE:
        reasons.append(
            f"provenance is {provenance or 'unset'!r}; a strict path admits only {STRICT_PROVENANCE!r}, "
            "and completeness of lowering does not substitute for approval"
        )

    eligible = [str(item) for item in (plan.get("strict_eligible") or [])]
    requested = [str(item) for item in scopes] if scopes is not None else list(eligible)
    if not requested:
        reasons.append("no scope is strict-eligible")
    outside = sorted(set(requested) - set(eligible))
    if outside:
        reasons.append(f"scope(s) {outside} are not strict-eligible in this plan and cannot be requested")

    record_digest = ""
    intent_digest = ""
    evidence_digest = ""
    if not isinstance(verification, Mapping):
        reasons.append("no independent verification record; an unchecked plan is not admissible")
    else:
        missing = _missing(verification, REQUIRED_RECORD_FIELDS)
        if missing:
            reasons.append(
                f"the verification record is missing {missing}; an absent field is an unanswered "
                "question, and an unanswered question is not a pass"
            )
        if verification.get("schema_version") != RECORD_VERSION:
            reasons.append(
                f"verification record version {verification.get('schema_version')!r}; this contract "
                f"reads version {RECORD_VERSION}"
            )

        record_digest = str(verification.get("plan_digest") or "")
        intent_digest = str(verification.get("intent_digest") or "")
        evidence_digest = str(verification.get("evidence_digest") or "")
        if not record_digest:
            reasons.append("the verification record names no plan; it cannot be bound to this one")
        elif record_digest != digest:
            reasons.append(
                f"the verified plan was {record_digest[:19]} and this one is {digest[:19]}; "
                "a plan changed after checking is not the plan that was checked"
            )
        if not intent_digest:
            reasons.append(
                "the verification record names no intent; without it an approval cannot be tied to "
                "what was actually checked"
            )
        if not evidence_digest:
            # Without this, an empty digest in the record silently disabled the
            # comparison below and any approval's evidence matched.
            reasons.append(
                "the verification record names no evidence; an empty digest compares equal to nothing "
                "and would let any attestation stand"
            )
        # `is not True`, not falsiness. The string "false" is truthy, and a
        # boundary that accepts a type it never asked for is deciding on a value
        # it did not read.
        if verification.get("source_available") is not True:
            reasons.append(
                "the independent check could not read the source intent, so completeness against the "
                "sources did not run"
            )
        errors = verification.get("errors")
        if not isinstance(errors, int) or isinstance(errors, bool):
            reasons.append(f"the verification record reports errors={errors!r}, which is not a count")
        elif errors:
            reasons.append(f"the independent check reported {errors} error(s)")

        checked = {str(item) for item in (verification.get("checked_scopes") or [])}
        unchecked = sorted(set(requested) - checked)
        if unchecked:
            reasons.append(f"scope(s) {unchecked} were never checked by the verifier")

        reasons.extend(_obligation_reasons(plan, verification, requested))

    reasons.extend(_scope_consistency_reasons(plan, requested))

    approval_digest = ""
    if not isinstance(approved_intent, Mapping):
        reasons.append("no approved intent; authored overrides are not approved bound permits")
    else:
        approval_digest = content_digest(approved_intent)
        missing = _missing(approved_intent, REQUIRED_APPROVAL_FIELDS)
        if missing:
            reasons.append(f"the approval is missing {missing}; a bare boolean approves nothing in particular")
        # `is not True`: `approved: "false"` is a truthy string, and reading it as
        # consent is the whole of this boundary failing on a type it never asked
        # for. The same goes for 1, "no", and any other stand-in for a boolean.
        if approved_intent.get("approved") is not True:
            reasons.append(
                f"the approval's `approved` is {approved_intent.get('approved')!r}, not the boolean "
                "True; consent is not inferred from a value's truthiness"
            )
        if not str(approved_intent.get("approved_by") or "").strip():
            reasons.append("the approval names no approver")
        if not str(approved_intent.get("epoch") or "").strip():
            reasons.append("the approval names no epoch, so it cannot be revoked or superseded")

        approved_for = str(approved_intent.get("intent_digest") or "")
        if not approved_for:
            reasons.append("the approval names no intent; it cannot be bound to what was checked")
        elif approved_for != intent_digest:
            reasons.append(
                f"the approval is for intent {approved_for[:19]} and the verifier checked "
                f"{intent_digest[:19]}; an approval of other inputs is not an approval of these"
            )

        approved_evidence = str(approved_intent.get("evidence_digest") or "")
        if not approved_evidence:
            reasons.append("the approval names no evidence; a waiver it never saw would discharge SEC-AVAIL")
        elif approved_evidence != evidence_digest:
            reasons.append(
                f"the approval was given against evidence {approved_evidence[:19]} and the verifier "
                f"recorded {evidence_digest[:19]}; an attestation signed by somebody else is not the "
                "one that was approved"
            )

        covered = {str(item) for item in (approved_intent.get("scopes") or [])}
        uncovered = sorted(set(requested) - covered)
        if uncovered:
            reasons.append(f"the approval does not cover scope(s) {uncovered}")

        approval_epoch = str(approved_intent.get("epoch") or "")
        wanted_epoch = str(expected_epoch or "").strip()
        if wanted_epoch and approval_epoch != wanted_epoch:
            reasons.append(f"the approval is for epoch {approval_epoch!r} and this decision is for {wanted_epoch!r}")

        plan_epoch = str(plan.get("epoch") or "")
        if plan_epoch and plan_epoch != approval_epoch:
            reasons.append(f"the plan is epoch {plan_epoch!r} and the approval is for {approval_epoch!r}")

    return Admission(
        admitted=not reasons,
        reasons=tuple(reasons),
        plan_digest=digest,
        intent_digest=intent_digest,
        inputs_digest=approval_digest,
        scopes=tuple(sorted(requested)) if not reasons else (),
    )


def _scope_consistency_reasons(plan: Mapping[str, Any], requested: Sequence[str]) -> list[str]:
    """The plan's own scope lists must agree with what is being admitted.

    The review admitted a plan whose `strict_eligible` named a scope its
    `lowering_complete` did not, whose `unlowerable` was non-empty and whose
    `blocked_scopes` was empty. Only non-emptiness of eligibility was checked, so
    three fields that contradicted each other went unread.
    """
    reasons: list[str] = []
    wanted = set(requested)

    declared = {str(item) for item in (plan.get("scopes") or [])}
    unknown = sorted(wanted - declared) if declared else sorted(wanted)
    if unknown:
        reasons.append(f"scope(s) {unknown} are not declared in the plan")

    # Any blocked scope refuses the whole plan, not only a requested one. Scoped
    # admission narrows within a fully lowered plan; it does not let a plan with
    # a scope nobody could lower through on the strength of its other scopes. The
    # blocked scope's restrictions are absent from whatever is rendered, and a
    # partial ruleset reaching a device that previously carried that scope is the
    # open-scope failure this whole contract is about.
    blocked = {str(item) for item in (plan.get("blocked_scopes") or [])}
    if blocked:
        reasons.append(f"scopes blocked by unlowerable intent: {sorted(blocked)}")

    complete = {str(item) for item in (plan.get("lowering_complete") or [])}
    incomplete = sorted(wanted - complete)
    if incomplete:
        reasons.append(
            f"scope(s) {incomplete} are strict-eligible but not lowering-complete; a subset of a "
            "restriction is a weaker restriction"
        )

    unlowerable_scopes = {
        str(item.get("matrix_ref") or item.get("scope") or "")
        for item in (plan.get("unlowerable") or [])
        if isinstance(item, Mapping)
    }
    leaking = sorted(wanted & unlowerable_scopes)
    if leaking:
        reasons.append(f"scope(s) {leaking} have intent the compiler could not lower")
    if unlowerable_scopes and not blocked:
        reasons.append(
            "the plan reports unlowerable intent and no blocked scope; the two records disagree and "
            "the disagreement is not resolved in favour of the permissive one"
        )
    return reasons


def _obligation_reasons(
    plan: Mapping[str, Any], verification: Mapping[str, Any], requested: Sequence[str]
) -> list[str]:
    """Every applicable obligation must read `pass` for every requested scope."""
    reasons: list[str] = []
    statuses = verification.get("obligations")
    if not isinstance(statuses, Mapping):
        return ["the verification record states no obligation statuses"]

    for scope in sorted(set(requested)):
        per_scope = statuses.get(scope)
        if not isinstance(per_scope, Mapping):
            reasons.append(f"scope '{scope}' has no obligation statuses in the verification record")
            continue
        for obligation in applicable_obligations(plan):
            status = per_scope.get(obligation)
            if status == PASS:
                continue
            if status is None:
                reasons.append(
                    f"scope '{scope}': {obligation} has no status; the obligation applies to this plan "
                    "and a missing status is not a pass"
                )
            else:
                reasons.append(f"scope '{scope}': {obligation} is {status!r}, not {PASS!r}")
    return reasons


def admitted_projection(plan: Mapping[str, Any], admission: Admission) -> dict[str, Any]:
    """The part of the plan that was admitted, detached, and only for that plan.

    Admission is per scope, so handing a renderer the whole plan would hand it
    scopes no approval covered. A refusal has no projection at all.

    Two things the first version got wrong, both found by review:

    * it filtered by scope name and never checked that the plan it was given was
      the plan that had been admitted. A caller could evaluate one plan, change
      it, and take a projection of the changed rules stamped with the old
      admitted digest. Identity is re-established here, against a snapshot taken
      first - hashing the caller's object and copying it afterwards would leave
      the same window open, only narrower.
    * it returned the plan's own rule mappings, so editing a rule in the
      projection edited the plan. What comes back is detached.

    A plan that is not the admitted one raises rather than returning empty: it
    means the caller holds two different objects and believes they are one, and
    an empty ruleset handed to a firewall renderer is not a safe way to say so.
    """
    if not admission.admitted:
        return {}

    snapshot = copy.deepcopy(dict(plan))
    digest = content_digest(snapshot)
    if digest != admission.plan_digest:
        raise AdmissionError(
            f"this plan is {digest[:19]} and the admission was for {admission.plan_digest[:19]}; "
            "a projection of a plan that was never admitted is not a projection"
        )

    scopes = set(admission.scopes)
    rules = [
        rule
        for rule in (snapshot.get("rules") or [])
        if isinstance(rule, Mapping) and str(rule.get("scope")) in scopes
    ]
    return {
        "schema_version": snapshot.get("schema_version"),
        "provenance": snapshot.get("provenance"),
        "scopes": sorted(scopes),
        "rules": rules,
        "plan_digest": admission.plan_digest,
        "intent_digest": admission.intent_digest,
    }


def strict_artifacts(paths: Sequence[Any]) -> list[str]:
    """Which of these paths exist. A refusal must leave none of them behind."""
    from pathlib import Path

    return [str(item) for item in paths if Path(item).exists()]


__all__ = [
    "CHECKED_OBLIGATIONS",
    "DEFERRED_OBLIGATIONS",
    "DEFERRED_OBLIGATION_FIELDS",
    "KNOWN_PLAN_FIELDS",
    "KNOWN_RULE_FIELDS",
    "PASS",
    "RECORD_VERSION",
    "REQUIRED_APPROVAL_FIELDS",
    "REQUIRED_RECORD_FIELDS",
    "STRICT_PROVENANCE",
    "Admission",
    "AdmissionError",
    "admitted_projection",
    "applicable_obligations",
    "content_digest",
    "malformed_constructs",
    "evaluate",
    "nested_digest_fields",
    "strict_artifacts",
    "unsupported_constructs",
]

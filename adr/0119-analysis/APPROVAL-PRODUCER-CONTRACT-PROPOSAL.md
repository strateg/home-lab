# Approval producer contract — implementation proposal

Date: 2026-09-15. Status: **Proposed; not accepted or implemented**.

Parent decisions: ADR0118 D4/D7 (explicit bound policies, L7 approval ownership),
ADR0119 and its formal/assurance contracts (approval of resolved semantics,
independent verification, scoped evidence), ADR0086 (lifecycle and manifest bus).
This proposal does not change those decisions, qualify a backend or close G3.

## 1. Decision requested

Adopt a **signed, source-controlled L7 review decision**, authenticated against an
**operator-pinned authority context**, and a **validate-stage approval producer**
with a fixed manifest channel. The producer verifies an existing decision; it
never decides that a human approved merely because compilation or tests passed.

The initial purpose is `offline_intent`: approval of exact resolved intent and
its supporting statements for a named project/profile/scope/epoch. It is not
approval of a deployment, rollback, live evidence exception or arbitrary future
backend realization. Those remain separate gates and operation authorities.

The baseline trust mechanism is a signed review envelope verified with pinned
public keys. Git stores the review/audit record; a commit, author email, branch,
CODEOWNERS entry or an `approved_by` string is not authentication by itself. No
Git hosting service, network lookup or online PKI is required for this baseline.
The signature adapter must use a reviewed library and a fixed versioned format;
unknown algorithms/encodings are refused, not negotiated from the payload. Exact
signing-tool integration is an implementation detail to freeze and test before
this proposal is called implemented; custom cryptography is not proposed.

## 2. Four distinct facts

| Fact | Authority | What it cannot establish |
| --- | --- | --- |
| A proposal names useful traffic | Candidate author / workload owner | Permission |
| A principal approved resolved intent | Authenticated, scope-authorized L7 approver | Correct lowering or live enforcement |
| A plan preserves that intent | Independent security-plan verifier | Approval authority |
| An artifact may be written for this run | Admission over all three inputs and trusted run context | Activation or backend qualification |

`Candidate` remains distinct from an approved binding/grant. An approval record
contains references and review claims, **not a second copy of rules/selectors**.
Changing a candidate into authored strict intent is an explicit reviewed source
operation. The approval plugin must not promote legacy matrices or rewrite plan
provenance, `strict_eligible`, Q, guards, verification statuses or digests.

## 3. Who is the approver?

An approver is a stable authenticated principal bound to a pinned public-key
identity and a versioned scope delegation. It is not inferred from a device
owner, repository author, OS user, free-text waiver owner or successful CI run.

The authority context supplies:

- principal/key identities, enabled state and validity;
- permitted project, purpose, profile, exact scopes and epoch bounds;
- authority to approve an availability waiver where one is used;
- separation-of-duties policy and authenticated proposer identities;
- authority-policy revision and revocation snapshot identity.

Baseline separation: the approver is not any authenticated proposer of the
reviewed change set, consistent with the existing `netmodel.candidates.promote`
contract. A different spelling of the same identity does not count as another
person. Self-approval is not enabled as a convenience fallback for a single
operator; changing that policy needs an explicit separate decision.

**No real person/key is appointed by this document.** The operator must supply
an actual independent principal, public key and scoped delegation. Empty or
unprovisioned authority means unverified/refused approval, not a default
`security-lead` identity. The user must authorize that bootstrap outside the
proposed policy change itself.

## 4. Sources and the trust boundary

### 4.1 Review decision: project source, not generated output

Add a versioned L7 approval record through the existing Class -> Object -> Instance
model. Planned ownership is an operations approval class/object and concrete
records under the project's operations instances. The exact class/object IDs
and schema must be registered at implementation; no active topology schema is
silently extended by this proposal.

Reusable objects supply shape only. Concrete principal, scope, decision, epoch,
review reference and digests belong to the reviewed instance. The record is
included in `normalized_rows`; no private filesystem traversal inside a validator
or generator is needed. Signed records contain no private keys or credentials.

A generated review packet may help a person inspect resolved semantics and sign
the decision, but remains a candidate artifact. Neither the packet generator nor
the compiler can sign as an approver or commit an approval automatically.

### 4.2 Authority and run context: separately pinned input

The authority snapshot cannot be trusted merely because it sits next to the
approval record. The execution entrypoint pins the authorized authority-policy
revision/key set from an operator-controlled context outside the proposed change.
A candidate must not add its own key/delegation and approve itself in one run.

A planned `base.discoverer.approval_context` accepts that explicit entrypoint
input and publishes `approval_context` at `pipeline_shared` scope. The context
contains public trust/delegation data, project/profile/purpose, expected epoch,
evaluation time and source/revision identities. It exposes no signing key.

The pin and its provenance must survive the runtime snapshot. Passing an
arbitrary project-authored YAML path/hash as both the authority and its own pin
is not a trusted bootstrap. Trusting arbitrary changed framework code/manifests
is outside this data-level boundary: operator-approved executable code remains a
prerequisite, not something a content digest proves.

The publisher does not invent missing context from the approval's own epoch or
principal. Missing input produces an explicit unavailable context; no fallback
to environment variables, local username or permissive defaults.

## 5. Signed review subject

A closed versioned envelope carries the following logical fields:

| Field group | Required meaning |
| --- | --- |
| Envelope | Schema/signature-profile version, unique decision ID, `approve` or `reject` enum |
| Purpose | Exactly `offline_intent` for the baseline |
| Subject | Project, strict profile, contract/model version and reviewed scope-inventory identity |
| Scope | Sorted unique exact scope IDs and binding/change-set references; no wildcard or implicit inheritance |
| Semantics | Independently reproducible `intent_digest` |
| Statements/evidence | `evidence_digest`, including the actual availability waiver statement if applicable |
| Time/context | Epoch, authority-policy revision, issuance and bounded validity |
| Identity/audit | Claimed approver, authenticated proposer/change reference, rationale and review reference |
| Signature | Verification material identifying a key in the pinned authority context |

The claimed principal must equal the signer identity derived by verification;
matching text in two payload fields proves nothing. All decision claims above
are signed with purpose/version domain separation. Parsing is closed and typed:
unknown fields/versions, duplicate keys, ambiguous encodings and invalid scalar
or collection types are rejected before hashing/interpretation. There is no
truthiness conversion from `"approve"`, `"false"`, `1` or a stringified digest.

Scope inventory and binding references must be bound into the canonical subject
contract. They cannot be dropped merely because the current legacy validator's
intent hash does not yet model them. Evidence identity remains separate from
semantic identity; re-attestation can invalidate approval without changing the
plan's semantic digest.

The plan digest is **not** the semantic approval subject in this baseline. The
verifier binds the current plan to the approved intent/evidence; admission then
binds its verdict to that exact plan. Approval of an exact deployable bundle is a
separate operation with its own subject. A backend/profile/scope change that
changes review assumptions requires a new subject, even if port tuples coincide.

Approval records, signatures and runtime timestamps are excluded from the
semantic intent hash itself. Otherwise approval would have to sign a digest
containing its own signature. Canonical subject construction must be shared as a
representation contract, not by importing the compiler's lowering decisions into
the independent verifier.

## 6. Stage graph and the producer's declared channel

Planned IDs/keys below are part of the proposal, **not currently registered
plugins**. Numeric orders/timeouts and diagnostics are allocated only after
manifest/registry checks during implementation.

| Producer | Stage | Output | Consumer |
| --- | --- | --- | --- |
| `base.discoverer.approval_context` (new) | discover | `approval_context` | approval validator, admission consumer |
| `base.compiler.instance_rows` (existing) | compile | `normalized_rows` including typed L7 review records | approval validator, semantic verifier |
| Strict intent/plan compiler path (must be implemented from real typed sources) | compile | candidate plan and reproducible review subject | semantic verifier |
| `base.validator.security_plan` (existing, strict-source support required) | validate | `security_plan_verification`, extended subject identity | approval validator, admission consumer |
| `base.validator.network_approval` (new) | validate | `network_approval` | admission consumer on generate |

`base.validator.network_approval` declares `depends_on` and `consumes` for the
context publisher, normalized rows and the semantic verifier; it publishes only
its own `network_approval`. Same-stage dependency places it after the verifier;
use the scheduler dependency contract, not a magic numeric order. The plugin is
a validator because it authenticates/checks an externally made decision. It is
not an independent grant compiler or a new lifecycle stage.

All payloads cross the manifest bus (`ctx.subscribe` / `ctx.publish`). Consumers
subscribe to the exact named publisher/key; no caller-selectable approval
provider, direct file read, registry bypass or test environment fallback. The
existing fixture's `STRICT_WRITER_APPROVAL_FILE` and `STRICT_WRITER_EPOCH` are
not a production interface.

Required semantic inputs may use `required: false` at registry level **only** to
ensure the plugin runs and emits a visible missing-input result, as the existing
validator does. The plugin itself requires them to verify approval. Tests must
prove that missing producer, absent publication and `None` payload all block the
writer; scheduler skip is not success.

### Why there is no cycle

The compiler builds a **non-authorizing candidate plan** for review/checking
without consuming a validate-stage approval result. The independent verifier
checks its conditional preservation against the resolved intended policy; it
does not authenticate the review decision or mint grants. Approval authentication
and subject binding follow in validate. Only admission can permit consumption.

Two runs are normal: derive/review/freeze first; record a real signed decision;
then replay compile/validate/admission. In the second run the reviewed L7 record
is already an input, not something manufactured from the current green result.

This requires an explicit non-authorizing candidate representation and strict
source path. It must not reuse an active grant type for an unapproved candidate
or add `approved=True` to make compilation possible. Conditional validation is
not evaluation of an active `P_e` until approval is established.

## 7. Output and admission

`network_approval` is a typed result, not a bare boolean:

- `status`: `verified`, `rejected` or `unverified`;
- exact subject identifiers, epoch, intent/evidence digests;
- authenticated approver identity, decision ID/digest and review reference;
- authority-policy/context digests and verification-profile version;
- approved exact scopes and verified waiver authorization, where applicable;
- structured reason codes and source paths, including missing input/authority.

`verified` means the external decision is authentic, authorized, valid in this
context and matches the independently checked subject. It does not override a
failed or unverified semantic obligation. A valid rejection is `rejected`, not
an error in the signature checker and never a grant. Missing proof is
`unverified`; malformed or contradictory approval is refused with diagnostics.

Admission must consume this full result together with the independent plan
record and the **same trusted context**. Merely copying its inner fields into
the current caller-supplied `approved_intent` dict loses authority/context
binding. Implement a production entrypoint that checks these identities and
fixed producer provenance before calling the bounded decision logic. Existing
unit-test injection remains a test facility, not a production approval path.

For the current verdict scope, require one valid decision covering the exact
review subject and all requested scopes. Do not union partial approvals into a
new decision that nobody signed. Conflicting decisions for the same subject or
ambiguous supersession refuse; never select one by discovery order or timestamp
alone. Rejection, expiry or revocation cannot be displaced by an older approve.
A superseding decision explicitly references its predecessor and is checked
against the pinned authority state; unresolved history blocks admission.

Expected epoch and evaluation time come from the trusted context, not the signed
record under examination. Approval validity/delegation revocation are checked for
this run. This does not implement F4 session revocation or deployment rollback.
Changes to context/authority/evidence invalidate cached approval verification;
changing a plan invalidates its admission/projection as already enforced.

No approval result rewrites `legacy_shadow`. No rejection enables legacy fallback
or clears a mandatory Q/guard. Optional candidate rejection may remain a green
review result; a requested strict write without valid approval is refused and
leaves no strict artifact.

## 8. First real positive path: two milestones, not one claim

**M1 — authentic producer on actual sources.** Provision the real authority pin,
principal and delegation; add a real L7 signed decision; obtain a verified output
through the declared channel. A legacy plan must still be refused. This proves
that approval is not a fabricated fixture, not that strict sources exist.

**M2 — offline strict candidate from real typed intent.** Implement the production
compiler/verifier path for explicitly bound non-legacy policies with real Q or an
authorized waiver. No test helper changes provenance or edits record fields.
Replay the same source-controlled reviewed intent and decision through the normal
six-stage scheduler. The declared admission consumer produces the bounded
approved projection, while a revoked/mismatched decision produces none.

The current matrix-only `legacy_shadow` path cannot satisfy M2 merely by adding
this producer. Source promotion/lowering and independent strict-source
verification are explicit prerequisites, not hidden scope inside a loader.

M1/M2 advance G3; they do not establish all path/state/capability obligations,
backend artifacts, live read-back or production activation. Those retain their
own evidence levels and gates.

## 9. Acceptance matrix before implementation closure

1. Real positive replay from typed project sources, genuine signed review and
   operator-pinned public authority; no patched verdict/provenance, no private
   signing key available to compiler/validator/generator.
2. Correct signature by an unauthorized principal refuses; authorized key with
   wrong scope/project/purpose/profile/epoch refuses; spoofed approver text and
   self-approval by an alias refuse.
3. Candidate edits its own authority record/key/delegation: cannot establish the
   operator pin. Expired/disabled/revoked delegation refuses.
4. Change intent, scope inventory, binding set or model contract: old approval
   refuses. Change waiver owner/rationale: evidence binding refuses even when
   semantic identity is unchanged.
5. Unknown schema/signature profile, malformed types, duplicate keys, missing
   digests, missing context, absent producer/channel and broken signature refuse.
6. Two conflicting decisions or unproved supersession refuse deterministically;
   input permutation cannot select a more permissive decision.
7. Approval present but semantic record fails/unverified, terminal narrowed or plan
   mutated after verification: no admission and no writer output.
8. Authenticated legacy approval still cannot admit `legacy_shadow`.
9. Deleting required Q/guard/scope from both plan and compiler summary remains
   visible to independent intent checking; approval cannot waive those errors.
10. Positive and negative writer controls run at generate through the real
    scheduler. Missing inputs produce explicit diagnostics/results rather than
    a silently skipped checker. No files or legacy fallback on refusal.
11. Authority/context change invalidates cached verification; semantic digests
    exclude signature/runtime timestamps and remain deterministic on replay.
12. Manifest validation, exact `task test:plugin-contract`, targeted integration,
    signature-adapter tests and framework lock checks are recorded separately.
    New diagnostic IDs are registered before emission; no numbers reserved here.

## 10. Implementation sequence and unprovisioned inputs

1. Review/accept this contract; settle the versioned signing adapter and trusted
   entrypoint pin representation with test vectors. Do not start with a loader
   returning `{approved: true}`.
2. Register L7 schema/object and typed context/result schemas; add context
   publisher and approval validator manifests; validate phase ordering and
   deterministic producer selection.
3. Implement authentication/delegation/subject checks and production admission
   adapter; retain legacy refusal. Demonstrate M1 before claiming M2.
4. Complete strict typed-source lowering/verification and explicitly reviewed
   source migration needed for M2; then collect its normal-pipeline evidence.
5. Review remaining G3 obligations and their independent inventory/witness gates.

Unprovisioned by design: actual approver/key/delegation, separately authorized
trust root and first real reviewed strict scope. These must be supplied by the
operator/reviewer; this proposal assigns none and grants no authority.

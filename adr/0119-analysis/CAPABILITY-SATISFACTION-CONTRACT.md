# ADR 0118/0119 — Capability satisfaction contract

**Status:** accepted target-design amendment, rev 3.2, 2026-09-11, adopted at the
user's direction. **Not implemented or backend-qualified.** This is a shared
normative supplement to [ADR 0118 D6.1](../0118-universal-container-network-model.md)
and [ADR 0119 D2.1](../0119-firewall-rule-ordering-contract.md), not a third ADR or
a replacement for [ADR 0106](../0106-capability-driven-plugin-architecture.md).
Main ADRs prevail if these documents diverge. The historical independent reviews
of rev 3.1 are not independent review evidence for this amendment.

Enforcer/scope cardinality, adapter dispatch identity and apply ownership follow
[ADR 0119 D1-D1.1 rev 3.4](../0119-firewall-rule-ordering-contract.md).
Adapter selection must be unambiguous before validation; canonical selection of
proven-equivalent strategies inside the selected contract is a separate operation.
This supplement supplies satisfaction evidence, not a competing type registry or
authority to group scopes by device identity alone.

## 1. Decision and boundaries

Capabilities become **requirements-to-evidence contracts**, not only dispatch
flags. Distinguish four questions:

| Question | Authoritative input / result |
|---|---|
| What does intent require? | Derived requirements from bindings, attachments, publications, routes and profile |
| What can a component offer? | Versioned declared support contract, conditions and limits |
| What applies in this configuration? | Derived join with concrete placement, enabled features, context and owner |
| What has been demonstrated? | Scoped validation, qualification and fresh observed evidence |

Declared support != effective support != evidence != permission.
Existing C->O->I remains the source model; effective capability is not a fourth
authored entity or database. Existing ADR 0106 classification remains valid.
Set membership alone cannot prove network semantics. No new runtime stage,
generic plugin framework, automatic topology repair or capability registry is
introduced by this design.

## 2. Three conceptual contracts

These are facets of security intent, plan and evidence, not three mandatory
plugins. Names below are conceptual: G1 must register schemas, metadata contexts
and manifest channels before using them in topology or runtime.

### 2.1 Requirement

A requirement carries:
- stable identity: source owner/local record, semantic obligation and context;
- source field/default/@on provenance, binding and policy epoch where relevant;
- capability reference(s) and typed required behavior, not a product-name test;
- subject roles, address family/routing domain, path/state applicability;
- bounds and prerequisites, including resource/revocation/availability limits;
- evidence needed for each claim/gate and explicit inactive/planned status.

Core derives requirements from complete intent/profile. Adapter specialization
may add implementation prerequisites with provenance to the original obligation;
it cannot delete, narrow or waive a core requirement. Disabled/planned intent
remains visible but is not an active grant or an activation requirement until
selected; disabling a publication does not remove independent guards or bindings.

Authors do not duplicate inferred requirements in a second list on every service.
Explicit constraints remain in their existing owning intent/profile. An unmet
requirement cannot be removed merely because the chosen backend lacks support.

### 2.2 Offer

An offer describes one subject/provider role and includes:
- stable contract identity/version, existing catalog capability references;
- applicable device/runtime and adapter/provider versions, including limits;
- concrete context selectors: family, domain, interface, hook/chain or state;
- supported predicates, transforms, provenance and state operations;
- required mode/configuration, offload restrictions and prerequisite offers;
- capacity bounds and supported deadlines, with units and explicit unknowns;
- operation owner, delegation/reconciliation prerequisites where mutation is needed;
- qualification evidence references, explicitly absent when not yet qualified.

Conflicting bodies for the same offer identity/version are errors, not overrides
selected by discovery order. Contract content is hash-bound, not trusted by a
version label alone.

Catalog/class contracts own reusable meaning; object/adapter contracts own support
declarations; instance placement/configuration determines applicability. Observation
is evidence about that placement, not an independent desired-state source.
Packs group reusable declarations; they are not certification bundles.

Conditions are evaluated at the phase that needs them. Distinguish expected
post-transition configuration from observed preflight state. A feature that is
currently off may be enabled by an authorized, qualified transition; do not treat
that as evidence it is already effective, or reject the planned enablement merely
because it is not yet applied.

A capability identifier is not a parameter container: represent revocation
bounds in typed data, not names such as cap.revoke_under_5_seconds. Do not create
a boolean for every product/version/hook combination. Unsupported and unknown
values are explicit; unknown is not an unlimited capacity or a wildcard.

### 2.3 Resolution evidence

Each result records requirement identity, claim/gate, status, chosen strategy,
contributing offers/versions, contexts/path cases covered, evaluated conditions,
evidence references, missing facts/counterexamples and invalidation dependencies.
Evidence binds intent/plan digests, subject identity and exact scope.

| Status | Meaning | Consequence |
|---|---|---|
| satisfied | Adequate witness at the evidence level required for this claim | This requirement is discharged for this claim only |
| unsatisfied | Demonstrated incompatibility or violated required bound | Block the affected candidate/claim; explain the source-level remedy |
| unverified | Evidence is missing, unknown, stale or conflicting | Block the affected readiness/activation claim; do not report support |

Not-applicable is a justified scope/applicability decision, not a fourth way to
pass a failed requirement. For a selected profile, missing inventory blocks a
complete claim; an empty loop is not proof. A failed candidate or explanatory
report may still be emitted, but cannot become runnable strict artifacts.

**Relation to the pre-existing `unsupported` verdict (rev 3.2a).** ADR 0119's
enforcement decision function already returns accept, deny or `unsupported`
([formal contract](FORMAL-CONTRACT.md) §1), and the architecture proposal uses
`unsupported` for intra-zone flows with no adequate enforcer. That verdict belongs
to the flow-authorization domain and is **not** a fourth capability status.
The mapping is one-directional and must not be inverted:

| Capability resolution | Permitted flow verdict | Forbidden rendering |
|---|---|---|
| unsatisfied | `unsupported` for the affected flow, or a reviewed source/topology change | `deny` presented as enforced protection; requirement deleted |
| unverified | `unsupported` for the affected claim, with the missing fact named | `unsupported` reported as a closed scope decision |
| satisfied at level L | Flow verdict decided by SEC-AUTH, not by SEC-CAP | `accept` inferred from satisfaction |

A flow labelled `unsupported` keeps its requirement in the inventory. Writing
`unsupported` never converts unverified into not-applicable, and never permits a
report to say "supported".

## 3. Composition, alternatives and non-circular resolution

Support is checked per relevant path/state across device/runtime, adapter,
owner-authorized operations and actual execution contexts. It is **not** the
union of capabilities on all devices. Selected witnesses must be jointly feasible
within one plan: check shared/aggregate capacity, mutually exclusive modes and
consistent ownership across requirements, not just each offer in isolation.
A router's forward filter does not establish
same-bridge isolation. A device feature unusable through the authorized adapter
does not qualify the proposed transition.

The core first derives obligations and bounded path requirements. Specialization
evaluates declared offers and finite strategies, adding their prerequisites.
Validation independently checks the complete specialized plan and witness coverage.
Use a bounded acyclic prerequisite graph with a canonical order; reject cycles,
unresolved dependencies or unknown predicate/transform relations. A strategy
cannot use the property it is supposed to prove as its only prerequisite.

Alternative strategies are allowed when they satisfy the **same** semantics:
for original-flow authorization, original tuple matching, an adequate earlier
gate or preserved connection identity may be valid. The earlier gate must cover
all relevant entry paths; connection identity must resist merging/spoofing and
remain valid through reverse traffic, state changes and revocation.

Declare alternatives and conditions in typed data, not executable expressions.
For equivalent valid strategies use a canonical semantic key; input order and
timing never select the winner. Record rejection reasons for alternatives.
A change in topology, authorization, transition/outage envelope or trust boundary
is not an equivalent fallback: propose it for review. Do not silently move to
host networking, change the resource writer, widen selectors or downgrade to legacy.

Adding an offer never enlarges P_e or A_e. Capability failure does not remove
required Q_e flows, suppress a deny, or turn an all-drop plan into success.
SEC-CAP is necessary but does not replace other [formal obligations](FORMAL-CONTRACT.md).

## 4. Evidence levels, gate behavior and freshness

| Claim | Required capability evidence | Absent later-stage evidence |
|---|---|---|
| Design-reviewed | Complete requirements, ownership, bounded contracts and explicit open assumptions | No implemented support claim |
| Offline-validated (G1-G4) | Compatible versioned offers, checked plan/conditions and independent model/artifact evidence | Live checks remain unverified activation prerequisites; an offline candidate bundle is allowed |
| Backend-tested (G6-G8 as applicable) | Reproducible conformance/fault tests for exact backend/version/mode and scope | No claim about the current deployment |
| Live-observed / activation | Fresh preflight of effective prerequisites; post-apply semantic read-back and positive/negative path evidence | No activation on missing preconditions; no completion claim on missing postconditions |

Post-apply evidence cannot be demanded before the transition that produces it.
Instead preflight checks qualified capability and current prerequisites; observed
success checks the resulting state. All required gates/approvals still apply.
A live packet sample does not replace independent model checks or all-path coverage.

Bind requirement semantics, selected offer/contract versions, strategy and relevant
configuration conditions into deterministic intent/plan artifacts; bind those
artifacts and qualification evidence hashes into the existing bundle manifest.
Keep timestamps/live observations out of semantic plan identity, but hash evidence
artifacts and bind the external execution journal to exact bundle/epoch/subjects.
A fresh observation of identical semantics need not produce a new semantic plan.

### 4.1 Digest inputs: semantic core versus evidence annex (rev 3.2a)

Rev 3.2 states both that offer contract content is hash-bound (§2.2) and that a
fresh identical observation must not perturb the semantic plan. Those two rules
are only compatible if the offer is split, because §2.2 lists **qualification
evidence references** as offer content: recording a new qualification run would
otherwise change the offer hash, hence the plan digest, hence the artifacts.
Without the split the determinism claim is unsound. The split is normative:

| Part | Content | Digest binding |
|---|---|---|
| Offer semantic core | contract identity/version, subject/provider role, applicable device-runtime and adapter/provider version ranges, context selectors, supported predicates/transforms/state operations, required mode/configuration, offload restrictions, prerequisite offers, capacity bounds and declared unknowns, operation owner and delegation prerequisites | Enters the offer core hash, and through the selected witness the semantic plan digest |
| Offer evidence annex | qualification evidence references, evidence producer/test versions, observation results, freshness windows consumed, expiry timestamps | Hashed as an evidence artifact and bound to the bundle manifest; **never** an input to the semantic plan digest |

Consequences that implementations must preserve:

1. A change in the semantic core invalidates the affected resolution and produces
   a different plan digest, even when the catalog capability IDs are unchanged.
2. A change confined to the evidence annex changes evidence status and freshness
   only. It can move a claim between satisfied, unsatisfied and unverified, and it
   can block activation, but it must not rewrite the semantic plan or its artifacts.
3. A resolution record therefore cites two hashes: the offer core hash it was
   computed against, and the evidence artifact hash it was evidenced by. A record
   with only one of them is incomplete, not merely terse.
4. Declared unknowns are part of the semantic core. Replacing `unknown` with a
   concrete bound is a semantic change requiring revalidation, not a refresh.

An implementation that cannot separate these two parts must report the offer as
unverified rather than assert either determinism or freshness.

Invalidate affected resolution on offer/adapter/provider/device version change,
mode, interface/domain/path, owner/delegation, identity or relevant configuration
change, evidence expiry, revoked qualification or observed drift. Unknown dependency
impact invalidates the whole affected scope. Freshness windows are profile-owned,
not a universal constant. A new offer cannot silently reuse an older witness.
Changed semantic contracts require revalidation even when catalog IDs are unchanged;
authorization/transition changes additionally require appropriate approval.

An offer's own assertion is not qualification. Record evidence producer, test
version, target and trust basis; use independent reference checks and separately
reviewed qualification. Observation must neither mint a capability declaration
nor approve a permit. Conflicting observations stay unverified pending resolution.

## 5. Repository integration and ontology reuse

At review baseline 493867d5:
- capability_helpers.has_capability is set membership, not satisfaction checking;
- capability_compiler owns object-derived capabilities and effective OS/firmware
  maps, not live per-instance configuration evidence;
- capability_contract_loader_compiler publishes catalog_ids and packs_map, not
  rich support semantics; the existing contract validator checks declarations;
- effective_model remains the sole compiled_json owner.

Four further baseline facts constrain where offers can live (rev 3.2a):

- **The catalog reaches runtime as identifiers only.** The loader extracts
  `@capability` per entry and publishes a sorted set; `title`, `summary`, `domain`,
  `layer`, `stability`, `vendor` and `adr_refs` are documentation and are not read
  by any plugin. An offer therefore **cannot** be expressed by adding fields to
  `capability-catalog.yaml`: those fields would be silently inert.
- **The catalog is a closed vocabulary.** The contract validator rejects any
  class- or object-declared capability outside `catalog_ids`. Every identifier a
  derived requirement or an offer references must first be registered in the
  catalog; there is no permissive mode and no vendor escape outside packs.
- **A discover-stage seam already exists.** `discover_capability_preflight`
  verifies catalog/packs presence and publishes `capability_preflight_ok`. Offer
  and descriptor discovery extends that declared seam; it does not add a stage.
  `capability_derivation.py` holds the shared derivation helpers reused by both
  the compiler and the validator, and must not be forked for a network path.
- **`topology-tools/check-capability-contract.py` is not this seam.** It is a
  standalone ADR 0062 checker whose default catalog path
  (`topology/class-modules/router/capability-catalog.yaml`) does not exist in the
  tree. It is not authority for this contract and must not be extended for it.

Extend these declared seams; do not duplicate catalog/OS derivation in a network
compiler. Requirements are derived after effective-model inputs are available;
offers/prerequisites must be available before specialized-plan validation.
No effective_model -> network plan -> effective_model cycle is allowed.
All exchanges retain depends_on/consumes/produces, pipeline_shared lifetime where
cross-stage, snapshot/outbox/envelope rules and framework->class->object->project
discovery. Generator rendering does not perform capability negotiation.

Reuse existing namespaces: cap.net.* for L1 device features, cap.firewall.* for
L2 policy capabilities, cap.workload.* for L4, cap.operations.* for L7 operations.
cap.os.* classifies OS; do not add duplicate cap.platform.* or cap.can_access.*.
Legacy catalog entries are not reclassified by this amendment. A catalog flag
such as cap.firewall.security_matrix.pve is not qualified Proxmox support.

safe_mode and state_restore declarations do not prove an authorized rollback.
State operations remain within the ADR 0057/0119 owner boundary. A feature only
available through an unauthorized second writer is unsatisfied for that plan,
not a reason to bypass Terraform. Recovery may retain guards instead of restoring
a revision whose grants the current epoch has revoked.

## 6. Worked design cases (not backend support claims)

| Intent / situation | Derived need | Resolution example |
|---|---|---|
| Direct LXC service | Attachment compatibility, trusted source identity, all-path authorization | Routed filter offer alone leaves host/bridge path unverified; no direct-isolation claim |
| DNS frontend -> DNAT backend | Delivery transform plus SEC-NAT/SEC-AUTH, direct-backend distinction | cap.net.l3.translation.dnat is relevant but insufficient; require a scoped identity-preserving strategy and evidence |
| Two frontends share backend | Preserve different approved source sets after transform | An undifferentiated backend accept fails; earlier gate works only with proved coverage of every entry |
| Same-workload shared stack | Identity separation required by binding | Shared IP without trusted distinction is unsatisfied; stronger boundary is a reviewed topology proposal |
| Tunnel-only egress | Route control, tunnel-state/fallback guard, bounded control-plane grants | Healthy-tunnel evidence alone leaves down/unknown paths unverified; extension qualification still required |
| Permit removed, sessions established | Revocation deadline and current-epoch safe recovery | state_restore alone cannot discharge SEC-STATE/TRANSITION; revoked grants must not return |
| Required feature exists but disabled or in another VRF | Effective applicability in exact placement | Unsatisfied when disabled/wrong scope violates the required phase; unverified when required state is unknown |
| All offline checks pass, no live observation yet | Activation prerequisites | Offline satisfied, activation unverified; candidate build allowed, apply/completion claims blocked as appropriate |

These examples add no new authoring keys. Concrete executable cases are A25-A32
in [migration/acceptance](../0118-analysis/MIGRATION-AND-ACCEPTANCE.md), assigned
to W03/W04/W06/W07/W08/W10/W11 in the [implementation plan](../0118-analysis/IMPLEMENTATION-PLAN.md).
No capability catalog, runtime, tests or live configuration are implemented here.

## 7. Vocabulary debt for the known enforcement gaps (rev 3.2a)

The worked cases above are expressible only if identifiers exist for what they
constrain. Because the catalog is a closed, identifier-only vocabulary (§5), the
enforcement gaps recorded by earlier reviews are **not yet expressible** as derived
requirements. Naming that debt is part of this contract; filling it is W03 at G1.

Verified at baseline 493867d5 by direct inspection of the tree:

| Known gap | Observed state | Requirement class needed | Vocabulary status | Existing acceptance anchor |
|---|---|---|---|---|
| Acceleration bypass | `fasttrack-connection` filter rendered live in `generated/home-lab/terraform/mikrotik/vpn.tf`, sourced from `topology/object-modules/mikrotik/templates/terraform/vpn.tf.j2` and gated by `projections.py` `fasttrack.enabled` | Per-path acceleration state: enforced, verifiably excluded, or unverified | **Absent.** No `fasttrack`/`offload` identifier exists in the catalog | A11, A26 |
| Runtime firewall hook | Docker `DOCKER-USER` sees packets after DNAT; the nftables backend has no equivalent pre-provided chain | Hook/chain availability and pre-transform position, per runtime and per family | **Absent.** No hook, chain, `nft`/`iptables` or position identifier exists | A08, A26, A28 |
| Address family | Enforcement expressed only for IPv4 | Family applicability, with absence resolving to unverified rather than out-of-scope | **Absent.** No `cap.*.ipv6` or family selector exists; `cap.net.l3.routing.static` merely mentions IPv6 in prose | A11, A31 |
| Proxmox enforcement | `firewall_proxmox_generator.py` is a declared STUB returning success with no output; `projections.py` returns `status: "stub"` | Backend realization status distinct from catalog declaration | Identifier exists (`cap.firewall.security_matrix.pve`, experimental) but asserts nothing about the generator | A26, A31 |
| Container attachment enforcement | `generated/home-lab/terraform/proxmox/lxc.tf` is a four-line `locals` baseline listing nine LXC instances and rendering no resource; no `firewall` key appears in any `projects/home-lab/topology/instances/lxc/**` file | Per-attachment guard presence, and unrendered-realization status | **Absent.** `cap.workload.network.*` names attachment mode, not guard presence | A06, A07, A26 |
| Untracked-state admission | `zone_firewall.tf.j2` input chain accepts `established,related,untracked` unconditionally | Connection-tracking completeness on the admitting path | Identifier exists (`cap.firewall.connection_tracking`) but carries no state-set semantics | A11, A13, A15 |

Rules that follow from this table:

1. Until an identifier exists, the corresponding requirement resolves to
   **unverified**, never to not-applicable and never to silent absence. An
   inventory that cannot name a path has not proved the path is absent.
2. New identifiers are registered in `capability-catalog.yaml` before any offer,
   requirement or test references them; the closed-vocabulary validator will
   otherwise reject the declaration rather than warn.
3. Registering an identifier is declaration, not qualification, and not permission
   to change any generator, template or instance. Every row above stays open until
   its acceptance anchor is evidenced at the required level.
4. These are existing recorded gaps mapped onto SEC-CAP. They introduce no new
   acceptance IDs; A01-A32 remain the acceptance register, W01-W12 the work register.

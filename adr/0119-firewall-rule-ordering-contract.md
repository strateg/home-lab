# ADR 0119: Firewall Rule Ordering Contract

- Status: Accepted
- Revised: 2026-09-15 rev 3.4 (D1.1 corrected after review: scope identity and cardinality, adapter resolution, separation stated over six distinctions)
- Revised: 2026-09-15 rev 3.3 (D1.1: enforcer type and enforcer instance as separate axes; type resolved from capability, artifacts per instance)
- Revised: 2026-09-11 rev 3.2a (SPC supplement: SEC-CAP digest split, anchored Omega_g, status mapping)
- Revised: 2026-09-11 rev 3.2 (scoped capability resolution, SEC-CAP and evidence freshness)
- Revised: 2026-09-10 rev 3.1 (applicability review: ownership, routing/NAT, contexts and migration scope)
- Revised: 2026-09-10 rev 3 (final architecture proposal; implementation choices deferred)
- Date: 2026-09-09
- Revised: 2026-09-10 (authorization-preserving compilation and verified application)
- Revised: 2026-09-10 rev 2 (SPC rebuild: plan ownership vs enforcer scope, legacy
  terminal-rule obligation, provisional diagnostic identity; no decision withdrawn)
- Related: ADR-0086, ADR-0090, ADR-0094, ADR-0106, ADR-0110, ADR-0118
- Scope: Lowering network intent into deterministic, verified enforcement plans
- Implementation: Not implemented; no backend has qualified under this contract
- Analysis: [Formal obligations](0119-analysis/FORMAL-CONTRACT.md), [assurance profile](0119-analysis/ASSURANCE-PROFILE.md)

- Final design: [Architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
- Historical implementation exploration (not adopted): [Analysis](0118-analysis/FINAL-IMPLEMENTATION-PROPOSAL.md),
  [verification evidence](0118-analysis/FINAL-PROPOSAL-EVIDENCE-2026-09-10.md)

- Implementation planning: [Reviewed gate plan](0118-analysis/IMPLEMENTATION-PLAN.md),
  [review and corrections, 2026-09-11](0118-analysis/IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md)

- Pending implementation proposal (not accepted): [Approval producer contract](0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md), 2026-09-15. No gate or deployment authority granted.

- Enforcer-axis implementation evidence: [conformance record](0118-analysis/ENFORCER-AXIS-CONFORMANCE.md). Open implementation rows are not closed by rev 3.4.

- Implementation readiness and next-change specification: [readiness record](0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md), 2026-09-28. Sequencing of the open rows and a bounded channel-contract specification; no gate closed and no capability-axis decision taken there.

## Context

Independent matrix, publication, VPN and baseline generators currently compete
for chain positions. A shared `place_before` target cannot establish the
authorization semantics or actual installed order.

The old P1-P7 ranges, hash offsets and specificity scores did not establish
safety. A mandatory deny must not be bypassed by a more specific permit.
An accept-all ruleset has a terminal action for every packet but violates
authorization. This edition replaces the earlier D1-D9 in full.

## Decision

### D1. Authorize first, order second

ADR 0118 owns intent. This ADR owns its executable meaning:

```text
topology intent -> normalized security intent -> enforcement plan
               -> validated artifacts -> immutable bundle
               -> guarded apply -> observed-state evidence
```

One logical security-plan authority owns the canonical plan, including filter, NAT,
routing, state and dispatch dependencies. Backend-neutral semantics belong to
framework/core; platform object modules own capabilities and lowering/rendering,
not a second derivation of zone membership, grants or conflicts. Backend-specific
requirements enter through declared contracts before validation. This is ownership,
not a runtime visibility ACL; ADR 0086 remains in force.
Source compilers may publish declared
intent fragments; generators render the validated plan and do not create
independent permits, reorder it, or rediscover topology. Device baseline and VPN
rules must participate too. Unknown pre-existing rules are not assumed harmless.

**Plan ownership does not replace enforcer ownership.** ADR 0110's M1-B rule
stands: one security matrix instance names exactly one enforcer through
`managed_by_ref`. What changes is that the ordering algorithm is no longer
per-matrix. The relation is one logical plan authority producing one projection
per scope:

```text
intent fragments (matrices, publications, baseline, VPN)
   -> one logical security-plan authority
      -> per-scope plan projection (each scope names exactly one enforcer)
         -> rendering by the adapter selected for that scope's target context
            -> one owned resource set per apply unit
```

Two enforcers therefore keep independent rule sets and independent capability
qualification, while overlapping or conflicting intent between them is resolved
once in the plan semantics, instead of by whichever generator ran last. Nothing here
enables a disabled enforcer or merges two enforcement planes.

**Scope identity is not enforcer identity, and the cardinality runs one way.**
`managed_by_ref` is a reference from a scope to its enforcer; it is not a name for
the scope. One scope names exactly one enforcer. **One enforcer may hold several
scopes**, including scopes on different enforcement planes - the accepted design
already permits several disjoint contexts on one device. A scope therefore carries
its own stable identity, and nothing downstream may key a scope by the enforcer it
names. An index from enforcer to scope is a one-to-many relation: it either carries
every scope, in a deterministic order, or it refuses the multiplicity it cannot
represent with a diagnostic. Keeping one entry per enforcer silently is a lost
scope, and if the entry that survives depends on input order it also breaks D4.

Separate planes on one device are a **semantic** separation of intent. They are not
evidence that the device's chains, hooks, address sets or resources are isolated
from one another; composition across scopes sharing an enforcer must be validated
rather than assumed, and ownership of every shared resource resolved to one writer.

### D1.1 Enforcer type and enforcer instance are separate axes

The chain above separates type, instance, scope and apply ownership. Conflating
these distinctions shapes a universal model around whichever backend was
implemented first.

**Type.** An enforcer has a type, and the type is a property of the topology, not
of the codebase. It is resolved from declared enforcement capabilities through
the existing ADR 0106 classification and derivation contracts; OS classification
alone does not select an enforcement mechanism. It is never inferred
from an object or instance identifier, and never from which object module happens
to own a generator. A type that exists only because code for it exists is not a
model of the network.

A type names a **family of enforcement semantics**. It does not by itself select
what renders a scope. That selection is a separate, closed resolution with an
explicit outcome:

> For each target context, exactly one compatible versioned adapter - a rendering
> and realization contract - is resolved. Zero is an unsupported enforcer, reported
> as such and never rendered approximately. More than one is an ambiguity that
> blocks the selection; there is no priority order, no first match and no fallback.

Resolution carries provenance: which declarations were considered, which were
compatible, and why one remained. OS classification and enforcement-mechanism
selection are distinct questions, and a device may declare a generic enforcement
capability alongside a specific one, or several enforcement mechanisms at once -
those are inputs to the resolution, not answers. Several implementations of a type
may exist; only one may own a selected target resource set. The selected adapter's
identity and version are pinned before validation, enter the plan's verifiable
identity under D2, and a change to either invalidates the affected resolution.
This is a distinction inside the existing capability and offer contracts, not a
second authored registry.

Adapter identity selection is distinct from D2.1 strategy selection. Canonical
selection among proven-equivalent strategies inside the selected adapter contract
does not permit choosing among unresolved competing adapters by priority.

Resolving an adapter this way is dispatch, which ADR 0106 already governs. It is
not evidence that the enforcer can carry the plan: that remains SEC-CAP's
question, answered by scoped witnesses under D2.1, and capability membership
never substitutes for it.

**Instance, and what separation actually means.** Two enforcers of one type have
distinct identities; each may be referenced by multiple scopes. Projections retain
those scope identities and their target enforcer. Grouping projections into an
apply unit must not erase scope attribution or target identity; grouping is not
authorization to merge their policy semantics.

Separation is stated over six distinctions, because collapsing them is how a
transport detail becomes an architectural requirement:

| Distinction | What it fixes |
|---|---|
| Enforcer identity | Which device enforces; stable, referenced by scopes |
| Scope / context | Which intent, plane and bounded contexts; its own identity |
| Connection binding | Endpoint, target selector and credential reference used to reach a target |
| Resource identity and writer | Which concrete resources a scope owns, and the single writer of each |
| State namespace | Where applied state for those resources is recorded |
| Apply / transaction unit | What is applied, rolled back and recovered together |

What is required is **unambiguous target selection and a single writer per
resource**, with each rule attributable to one scope. Globally unique endpoints or
credentials are *not* required: several explicitly addressed targets may legitimately
share one management endpoint and principal, and distinct directories prove neither
distinct resources nor independent failure. Sharing a connection binding, a state
namespace or an apply unit across scopes is permitted only where the coupling is
declared and its reconciliation and recovery are validated - and independent scope
attribution must never be presented as an independent failure domain.

Enforcement plane (perimeter or internal) is a further orthogonal axis. It says
what part of the path a scope covers, not what its enforcer is, how many scopes
that enforcer holds, or what renders them.

For every accepted flow there must be a current explicit permit and no applicable
mandatory deny. Required legitimate flows must also work: blocking everything is
not successful implementation. These are separate soundness and availability
obligations, not a claim to prevent information exfiltration in allowed traffic.

### D2. Versioned IR, explicit ownership

The proposed projection contract has three immutable records:

| Record | Required content |
|---|---|
| Security intent | Schema/profile version, canonical source refs, attachments, publications, policy bindings, selector/identity snapshot and validity; derived capability requirements and provenance |
| Enforcement plan | Intent digest, selected versioned capability offers/strategies/conditions, execution contexts, typed matches/effects, ordered rules, transforms, path coverage, state/revocation and transition requirements |
| Validation evidence | Plan digest, validator/tool versions, obligation-linked capability resolution witnesses, required evidence levels, scope/assumptions, counterexamples and unsupported properties |

An execution context includes scope, enforcer, enforcer type, the selected
adapter's identity and version, routing domain, address family, hook and chain,
together with the modes that apply. The type and adapter belong in the context
because a hook or chain name only has meaning under one and renders differently
across adapter versions; the scope says which intent the context serves and the
enforcer which device carries it. Rules carry stable semantic identity, source
provenance and policy/publication binding where applicable. A NAT action includes
its target tuple,
not merely the string `dst-nat`. Original and transformed tuples are distinct.

Freshness expiry is part of the input contract. Unknown identities, stale dynamic
sets, unsupported predicates, unresolved paths and unbounded transformations
are blocking errors in strict mode. Empty selectors are never `any`.

The concrete manifest channel names and schemas must be registered in the
implementation PR; these conceptual record names are not existing runtime APIs.

### D2.1 Capability satisfaction is scoped and evidence-relative

The [shared contract](0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md) defines
requirements, offers and resolution evidence as facets of D2 records, not three
mandatory new plugins or an independent registry. SEC-CAP requires each applicable
requirement on every relevant path/state to have a compositional witness:
device/runtime + adapter/version + owner-authorized operations + execution context.
An offer on a different device/hook/family/VRF is not interchangeable support.
Selected witnesses must compose into one jointly feasible plan, including shared
capacity, compatible configuration modes and consistent ownership.

Resolution is satisfied, unsatisfied or unverified **at a named evidence level**.
Known incompatibility blocks the affected executable candidate. Missing later live
evidence leaves an offline candidate possible, but blocks activation or the
corresponding qualification claim. Unknown/stale evidence never means supported.
Incomplete path or requirement inventories cannot yield vacuous success.

Strategies are bounded declarative alternatives, with typed conditions and limits,
not arbitrary scripts. Original tuple matching, an adequate earlier gate, or
preserved connection identity may satisfy the same obligation only with complete
path/state proof. Equivalent valid alternatives use deterministic canonical
selection; topology/security/transition changes require review, not auto-fallback.
Capability satisfaction is necessary, not a substitute for SEC-AUTH/AVAIL or the
other obligations, and never enlarges approved P_e or A_e.

Bind selected offer/contract versions, strategy and semantic conditions to the
plan and bundle digests. Evidence records bind those digests, exact subject,
versions/configuration and freshness. Live timestamps remain outside semantic
digests; evidence artifacts still have integrity hashes. Relevant version, mode,
ownership, path or condition changes invalidate the affected resolution. Offers
are not self-attesting qualification; observation cannot grant permissions.

Rev 3.2a makes that boundary decidable: an offer has a semantic core, which enters
the plan digest, and an evidence annex, which does not. Qualification evidence
references belong to the annex, so recording a qualification run changes evidence
status without rewriting the plan, while any change to the core invalidates the
resolution even when catalog identifiers are unchanged. The satisfaction tri-state
maps onto the `unsupported` flow verdict in one direction only: an unsatisfied or
unverified requirement may render the affected flow `unsupported`, but an
`unsupported` flow never closes the requirement or reads as supported.

### D3. Preserve the repository lifecycle

| Stage | Responsibility |
|---|---|
| discover | Framework -> class -> object -> project manifest discovery |
| compile | Normalize refs/defaults, resolve bindings, authorize, construct complete candidate plan |
| validate | Check schemas, capability coverage, semantics, ordering and proof obligations |
| generate | Deterministic rendering from validated projections only, by the adapter resolved before validation, into explicitly owned resource sets grouped by apply unit without losing per-scope attribution |
| assemble | Cross-artifact consistency, manifest and provenance checks |
| build | Immutable offline candidate bundle; reject missing evidence required at this gate; activation additionally requires fresh live prerequisites |

All plugin exchanges use `depends_on`, `consumes`, `produces`; stage affinity
and ADR 0097 snapshot/envelope rules remain unchanged. Validation gates block
downstream artifacts for invalid candidates. Diagnostics may still be produced.
Deploy/reconcile is outside these six compiler stages and uses ADR 0090 runners
with immutable bundle input; it is not a seventh compiler stage. The number and
identity of plugins/processes and concrete API calls remain implementation choices.
Moving semantic authority into a platform object or changing Terraform/Ansible
resource ownership is an architectural change, not such a choice.

### D4. Deterministic order without semantic guessing

1. Normalize each context's predicates and effects with the backend's execution
   semantics, including NAT and jump/return behavior.
2. Resolve authoring conflicts before ordering. Overlapping permit/mandatory
   deny is an error; conflicting transformations are errors unless their domains
   are explicitly disjoint. Unknown overlap is not disjointness.
3. Build precedence edges from execution semantics: guards before permits,
   transformation dependencies, bounded state handling, dispatch/return and
   terminal default-deny coverage. Do not derive precedence from producer name.
4. Topologically sort with a canonical key among ready nodes. The key is the
   canonical serialized semantic tuple (including context, predicate, effect and
   stable source identity), not a truncated hash. Duplicates merge only when their
   full meaning matches, preserving all provenance.
5. Assign consecutive positions from that order; there are no fixed size slots.
   Validate every edge and the final executable control-flow graph.

Permutations of unordered inputs must produce identical semantic plans.
Semantically ordered input sequences are not arbitrarily shuffled. Keep timestamps
and live evidence outside the deterministic semantic digest, while including
snapshot content/version that affects authorization.

If backend anchors are used, they are an internal rendering detail with both
lower and upper ordering constraints. Anchor support itself must be verified.
Terraform dependency order is not a proof of the device's packet-processing
order. The final read-back must normalize to the intended plan.

On a default-allow backend the terminal deny is a backend obligation, not an
optional rule. ADR 0110's mandatory final drop-all and its check remain in
force for RouterOS, now carrying `E7082`; ADR 0110 assigned that check `E7854`,
a number storage media inventory had already held for three months, so the
erratum in `docs/diagnostics-catalog.md` moves it into the allocated range; in this contract that rule is the rendering of the reachable
terminal default deny required by the formal contract, it is emitted by the plan
compiler rather than by a template, and read-back must confirm that no executable rule
follows it within the corresponding managed sequence. This is not a global
last-resource position across the entire device. Earlier accepts, external
dispatch and adjacent contexts must not bypass the scope; they require separate
path evidence. The legacy final-drop requirement remains unchanged.

### D5. NAT, state and bypasses do not mint permissions

- Publication authorization binds original source, frontend, protocol, ports,
  direction and publication to the post-transform backend. Two frontends sharing
  a backend must not share permissions accidentally.
- Validate composed DNAT/SNAT/hairpin/nested transforms and reverse traffic.
  If original identity cannot be retained at the required enforcement point,
  block that backend plan or add an earlier identity-preserving gate.
- Validate the actual path: forward, local input/output, bridge, routing/tunnel
  and host paths need different obligations. Not every NAT rule requires a
  forward rule; every reachable path requires the right authorization gates.
- Established/related handling is bounded by current policy epoch and a declared
  revocation deadline. A backend may use verified session revalidation or scoped
  invalidation under quarantine; an unconditional established accept cannot
  precede mandatory revocation/quarantine controls.
- Related traffic needs bounded semantics and approved helpers. ICMP/ICMPv6,
  PMTU, neighbor discovery and fragments require typed control-traffic policies,
  not an unconditional early accept or indiscriminate protocol disablement.
- Disable acceleration/offload paths that bypass required enforcement unless
  their equivalence is tested. A router cannot prove same-bridge isolation alone.

The backend must declare how these requirements are met; describing a property
in this ADR does not make a RouterOS, Docker or Proxmox implementation support it.

### D6. Safe transition and observed-state contract

Deployment orchestration through the existing runner boundary must satisfy a
capability-qualified state machine; this does not prescribe a new runner,
controller or concrete backend commands. Preserve Terraform infrastructure
ownership and Ansible OS/service/runtime ownership; RouterOS post-bootstrap
desired configuration remains Terraform-owned under ADR 0057. Orchestration owns
sequencing, observation and evidence, not a second desired-state writer.
State/guard mutations must be delegated by the resource-domain owner with explicit
reconciliation. Transferring ownership away from Terraform requires a separate
architectural amendment to ADR 0057/0119; inability to meet transition guarantees
blocks qualification rather than authorizing an unreviewed workaround:

```text
candidate -> preflight -> staged/guarded -> activated
          -> observed and tested -> committed
                         \-> failed -> quarantined / authorized recovery
```

Preflight verifies bundle integrity, review authorization, expected current plan,
device/backend versions, exclusive writer/lease, clock/identity freshness, address
ownership and active lease conflicts. OOB management and a tested recovery plan
are required before any potentially locking change. L7 recovery intent identifies
the L1/L2 management path and independent failure domain; management-zone UI over
the same affected router is not evidence of OOB. Missing independent recovery
prerequisites block activation.

Stage atomically where supported. Otherwise install verified restrictive guards,
revoke stale sessions and change rules/addresses in a bounded sequence. Never
remove protection before its replacement is effective. Guard entry and removal
are themselves checked transitions; temporary outages require explicit approval.

During transition, admitted flows must be a subset of an explicitly approved
transition policy (see formal appendix). Removed grants must stop by the stated
deadline. Retries, reboot and partial apply preserve that condition or remain
quarantined. A backend that cannot achieve it is unsupported for strict deploy.

Read back effective ordering, dispatch, address ownership and active state;
compare semantic state, not just resource counts or comments. Exercise required
positive and negative paths. Only then record deployment success. A no-op apply
must still detect drift outside the managed chain that can bypass it.

Rollback is not permission to resurrect revoked grants. Restore only a plan
still authorized by the current security epoch, otherwise retain restrictive
guards and require operator recovery. Automatic rollback that reopens access
is forbidden. Unexpected writer/drift or evidence failure blocks completion. Each resource has
one writer; transferring ownership is an explicit guarded transition, never
concurrent competing management. Author, approver, scope owner and writer are
distinct responsibilities even if one operator holds several roles.

### D7. Human and AI feedback use the same evidence

Each diagnostic and change review carries:

```text
source reference + field -> requirement ID -> concrete flow/path witness
-> expected vs observed verdict -> minimal source fix -> reproducer/test
-> intent/plan digests + tool/backend versions + evidence scope
```

Reports distinguish `design`, `offline-validated`, `backend-tested` and
`live-observed`; missing evidence is `not run` or `unsupported`, never pass.
A test of a model is not evidence about installed devices.

AI may propose minimal source changes and new regressions; it cannot approve
its own permit expansion, relax guards merely to pass a test, or write secrets
to feedback. Human approval of critical policy/transition changes and secret
redaction follow ADR 0094 and existing deploy controls.

Semantic obligation IDs `SEC-AUTH`, `SEC-AVAIL`, `SEC-PATH`, `SEC-NAT`,
`SEC-ORDER`, `SEC-STATE`, `SEC-TRANSITION`, `SEC-CAP` are specified in the
[formal contract](0119-analysis/FORMAL-CONTRACT.md).

**Allocated 2026-09-11 at gate G1: `E7080..E7089`.** `E7080` and `E7081` carry
`SEC-ORDER` - a precedence cycle and an emitted order that breaks an edge it
claims to satisfy - `E7082` the terminal default deny, and `E7083..E7089` the
remaining obligations in the order they are listed above. The collision check
this required is recorded in `docs/diagnostics-catalog.md`: `E70xx` was the only
band inside `E7xxx` unclaimed by source, catalog, ADR or documentation, while
`E78xx`, where ADR 0110 and ADR 0111 live, stands at 93 of 100 with fourteen
collisions still inside it. The provisional prefixed form is retired.

## Consequences and acceptance

This replaces producer-owned priorities with one policy-preserving plan.
It adds proof/evidence and backend qualification work, but removes competing
ordering algorithms and prevents silent weakening for an unsupported platform.

A full solver for arbitrary platform code is not required: begin with a bounded,
typed subset and reject unsupported semantics. Small reference-model tests,
differential backend tests and live tests have distinct claims.

Acceptance of architecture requires the coherent threat model, formal contract
and decisions AD-01..AD-11 in the [final architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md).
Backend selection, plugin decomposition and implementation sequence are not part
of this approval.
Implementation readiness requires the
[shared acceptance gates](0118-analysis/MIGRATION-AND-ACCEPTANCE.md) and
[assurance profile](0119-analysis/ASSURANCE-PROFILE.md).
Neither ADR approval nor green documentation tests authorize production rollout.

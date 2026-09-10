# ADR 0119: Firewall Rule Ordering Contract

- Status: Proposed
- Date: 2026-09-09
- Revised: 2026-09-10 (authorization-preserving compilation and verified application)
- Related: ADR-0086, ADR-0090, ADR-0094, ADR-0110, ADR-0118
- Scope: Lowering network intent into deterministic, verified enforcement plans
- Implementation: Not implemented; no backend has qualified under this contract
- Analysis: [Formal obligations](0119-analysis/FORMAL-CONTRACT.md), [assurance profile](0119-analysis/ASSURANCE-PROFILE.md)

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

One security-plan compiler owns the canonical plan, including filter, NAT,
routing, state and dispatch dependencies. Source compilers may publish declared
intent fragments; generators render the validated plan and do not create
independent permits, reorder it, or rediscover topology. Device baseline and VPN
rules must participate too. Unknown pre-existing rules are not assumed harmless.

For every accepted flow there must be a current explicit permit and no applicable
mandatory deny. Required legitimate flows must also work: blocking everything is
not successful implementation. These are separate soundness and availability
obligations, not a claim to prevent information exfiltration in allowed traffic.

### D2. Versioned IR, explicit ownership

The proposed projection contract has three immutable records:

| Record | Required content |
|---|---|
| Security intent | Schema/profile version, canonical source refs, attachments, publications, policy bindings, selector/identity snapshot and validity |
| Enforcement plan | Intent digest, backend/version/capabilities, execution contexts, typed matches/effects, ordered rules, transforms, path coverage, state/revocation and transition requirements |
| Validation evidence | Plan digest, validator/tool versions, obligations checked, scope/assumptions, counterexamples and unsupported properties |

An execution context includes enforcer, routing domain, address family, hook
and chain. Rules carry stable semantic identity, source provenance and policy/
publication binding where applicable. A NAT action includes its target tuple,
not merely the string `dst-nat`. Original and transformed tuples are distinct.

Freshness expiry is part of the input contract. Unknown identities, stale dynamic
sets, unsupported predicates, unresolved paths and unbounded transformations
are blocking errors in strict mode. Empty selectors are never `any`.

The concrete manifest channel names and schemas must be registered in the
implementation PR; these conceptual record names are not existing runtime APIs.

### D3. Preserve the repository lifecycle

| Stage | Responsibility |
|---|---|
| discover | Framework -> class -> object -> project manifest discovery |
| compile | Normalize refs/defaults, resolve bindings, authorize, construct complete candidate plan |
| validate | Check schemas, capability coverage, semantics, ordering and proof obligations |
| generate | Deterministic backend rendering from validated projections only |
| assemble | Cross-artifact consistency, manifest and provenance checks |
| build | Immutable candidate bundle; reject incomplete evidence |

All plugin exchanges use `depends_on`, `consumes`, `produces`; stage affinity
and ADR 0097 snapshot/envelope rules remain unchanged. Validation gates block
downstream artifacts for invalid candidates. Diagnostics may still be produced.
Deploy/reconcile is outside these six compiler stages and uses ADR 0090 runners
with immutable bundle input; it is not a seventh compiler stage.

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

DeployRunner must implement a capability-qualified state machine:

```text
candidate -> preflight -> staged/guarded -> activated
          -> observed and tested -> committed
                         \-> failed -> quarantined / authorized recovery
```

Preflight verifies bundle integrity, review authorization, expected current plan,
device/backend versions, exclusive writer/lease, clock/identity freshness, address
ownership and active lease conflicts. OOB management and a tested recovery plan
are required before any potentially locking change.

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
is forbidden. Unexpected writer/drift or evidence failure blocks completion.

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
`SEC-ORDER`, `SEC-STATE`, `SEC-TRANSITION` are specified in the
[formal contract](0119-analysis/FORMAL-CONTRACT.md). Allocate numeric diagnostics
centrally with collision tests at implementation time, not in speculative tables.

## Consequences and acceptance

This replaces producer-owned priorities with one policy-preserving plan.
It adds proof/evidence and backend qualification work, but removes competing
ordering algorithms and prevents silent weakening for an unsupported platform.

A full solver for arbitrary platform code is not required: begin with a bounded,
typed subset and reject unsupported semantics. Small reference-model tests,
differential backend tests and live tests have distinct claims.

Acceptance of architecture requires a coherent threat model and formal contract.
Implementation readiness requires the
[shared acceptance gates](0118-analysis/MIGRATION-AND-ACCEPTANCE.md) and
[assurance profile](0119-analysis/ASSURANCE-PROFILE.md).
Neither ADR approval nor green documentation tests authorize production rollout.

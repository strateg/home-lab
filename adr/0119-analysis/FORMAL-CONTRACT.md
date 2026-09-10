# ADR 0119 — Formal contract and bounded proof obligations

Status: normative supporting contract of the **Proposed** ADR 0119.
No theorem below is a claim that the current runtime or live lab satisfies it.

## 1. Domain and assumptions

A flow event `f` contains original and current tuples, family, routing domain,
direction, ingress provenance, identity/snapshot reference, connection state,
publication ID (if any), policy epoch and time. A path is a sequence of actual
execution contexts and transformations, not just a list of matching rules.

For epoch `e`, define over an explicitly declared scope `U_e`:

- `P_e`: union of approved, explicitly bound permits.
- `D_e`: union of mandatory denies, including quarantine and expiry constraints.
- `C_e`: flows satisfying all applicable identity, direction, binding, validity
  and other declared restrictions.
- `A_e = (P_e intersect C_e) minus D_e`: authorized flow set.
- `Q_e subseteq A_e`: required legitimate flows, with stated environmental
  prerequisites and availability objectives.
- `Exec(R, f, path, state)`: backend-interpreter execution, including mutation,
  dispatch, tracking and acceleration, returning accept, deny or unsupported.

A submitted bound permit intersecting `D_e` is rejected in v1, with a witness.
Set subtraction defines authorization for reasoning and future normalization;
it does not authorize silently trimming a mistaken permit in v1.
Default deny is outside `P_e`, not an element of `D_e`.

Baseline policy activation is permit/binding_only or deny/scope_guard. Missing
binding is no grant. Publication disable/delete removes its bound permit from
the next desired epoch, not the reusable template or independent bindings.
Live revocation is a time-bounded transition, not a property of source editing.
Approval is tied to resolved semantics, not merely owner/rationale fields.
A scope guard uses concrete L2 selectors with an explicit original/current
tuple view and execution context. Evaluate all applicable views along the flow
path; a frontend restriction cannot silently become a backend-subnet restriction.

For a publication, its eligible flows are the intersection of its port/direction/
frontend mapping, referenced permit and service restrictions. A standalone L2
permit template is not automatically emitted as a second broad accept when
used through a publication binding. Policy ports are evaluated in original
client-facing coordinates; backend port mapping is a transformation. Empty
resolved intersections are rejected. Explicit independent network bindings are
reviewed separately; they must not unintentionally broaden a publication.

Threats include compromised endpoints, spoofing, lateral movement, identity
staleness, bypass paths, generator defects, stale conntrack, drift and partial
apply. Trusted assumptions (kernel, enforcer, compiler, identity authority,
cryptographic roots and physical control) are recorded with evidence.
L2 route constraints and interface-scoped NAT carry no grants. Feasible paths
include tunnel failure/fallback and proxy control-plane traffic, not just service
publications. Versioned legacy/strict scope labels do not prove independence of
shared execution contexts. Disabled/planned intent remains in requirement inventory,
but is not part of active permits or evidence of installed enforcement.
Compromise of that trusted base and covert channels need additional controls.

## 2. Obligations

| ID | Required property | Counterexample / evidence |
|---|---|---|
| SEC-AUTH | For every in-scope event/path/state, accepted delivery implies its original intent is in `A_e` | Unauthorized flow plus interpreter trace |
| SEC-AVAIL | Each `q in Q_e` succeeds under declared healthy prerequisites within its objective | Failed required DNS, PMTU, admin or application flow |
| SEC-PATH | Every feasible in-scope path crosses adequate verified gates or is demonstrably disabled | Same-bridge/direct/IPv6/offload bypass path |
| SEC-NAT | Authorization survives every composed transform without merging differently authorized originals | Approved frontend and unauthorized direct/backend flow collapse |
| SEC-ORDER | Canonical output is invariant to irrelevant input permutations and satisfies every required edge | Violating edge or different semantic plan |
| SEC-STATE | Forward and reverse admitted session traffic remains authorized under the active epoch; revocations meet the declared deadline | Old established or related flow survives beyond deadline |
| SEC-TRANSITION | Every intermediate state admits only the approved time-indexed transition set | Packet trace through partial apply, retry, reboot or rollback |

Termination is independent: every reachable execution must reach an allowed
terminal outcome in bounded steps, or fail validation. Unknown jump targets,
unbounded recursion and unresolved match semantics are errors. A reachable
default deny covers residual flows; an unreachable drop rule proves nothing.

`SEC-AUTH` means no unauthorized network delivery in the modeled scope.
It does not imply absence of application-layer data exfiltration, malware,
timing channels or cryptographic weaknesses. `SEC-AVAIL` prevents an acceptability
claim based solely on an all-drop configuration.

## 3. NAT and identity refinement

For transform `T`, preserve enough provenance to distinguish every pair of
original flows whose authorization differs. It is not enough to prove
`T(A_e)` has an accept rule: `T` may be many-to-one and admit unauthorized
preimages too.

If `T(f1) = T(f2)` at a gate but only `f1 in A_e`, that gate alone cannot
authorize correctly. Retain original metadata/connection identity, place a
discriminating earlier gate, or reject the plan. Include reverse mappings,
hairpin SNAT, nested NAT and protocol/port translation in this check.

NAT can legitimately have no accepted traffic while a candidate is staged.
For activated required publications, prove both correct authorization and
reachability. No universal NAT-resource-to-forward-resource count rule applies.

## 4. Ordering reference algorithm

```text
normalize typed predicates and effects per execution context
reject conflicting bindings and unknown predicate/effect relationships
construct finite semantic precedence graph G
ready := nodes with zero incoming edges
while ready is nonempty:
    n := minimum ready node by canonical full semantic key
    emit n; remove outgoing edges; update ready
if not all nodes emitted: reject cycle with witness
assign positions 0..n-1 within each executable sequence
verify all precedence edges and reachable control flow after rendering
```

A tie-break orders only semantically interchangeable ready nodes. If two nodes
could produce different authorization outcomes, their semantics require an edge,
normalization or a conflict error before sorting. Comparing scores is forbidden.
An anchor implementation needs `lower_boundary -> rule -> upper_boundary`.
No hash modulo or reserved position range is used.

Canonical encoding fixes map ordering, set ordering, address/prefix forms,
protocol/port intervals, null/empty distinctions and character encoding.
Content hashes identify artifacts, not order slots; verify full content when
resolving identity collisions. Backend-local positions do not imply that packets
globally traverse enforcers in that order; path semantics are checked separately.

## 5. Time and deployment

Before activation approve `T(t)`, the transition authorization envelope, tied
to old/new digests, an expiry and the new mandatory denies. Normally staged
grants do not take effect before activation; revoked grants stop by the specified
deadline. The envelope is no broader than the explicitly approved old/new grants
with current mandatory denies removed. Extra temporary grants require separate
review; no implicit union or wildcard exception is allowed.

For every intermediate ruleset/state `R_t`:
`Accept(R_t) subseteq T(t)`.
At completion: `Accept(R_final) subseteq A_new` and required-flow availability
holds under its prerequisites. Failure to prove a safe sequence blocks deploy.

Specify maximum transition duration, revocation deadline, identity/clock expiry,
failure action, operator recovery and evidence freshness per deployment profile.
Do not invent one universal timeout. Unsupported deadline guarantees block strict
qualification. Rollback is evaluated against the current envelope/epoch.

## 6. Required regression layers (future implementation)

1. Unit algebra: disjoint/overlapping/incomparable predicates; mandatory deny;
   explicit empty/false/zero; different targets for identical NAT actions.
2. Finite/property tests: accept-all mutant fails SEC-AUTH; all-drop mutant fails
   SEC-AVAIL; deleting a permit cannot enlarge `A_e`; adding a deny cannot enlarge it.
3. Ordering: 0, 1, 101, 1000 rules; shuffled unordered inputs; duplicate semantic
   nodes; cycles; missing lower anchor edge; stability across process/hash seeds.
4. Differential tests: intent interpreter vs normalized rendered backend rules,
   then actual backend behavior, including two frontends sharing one backend.
5. Stateful/path tests: positive and negative IPv4/IPv6, host/bridge/routed/tunnel,
   fragment/ICMP, offload and session-revocation cases.
6. Fault injection: apply interrupted at each mutation, retry, reboot, concurrent
   writer, stale identity/time, failed read-back and unauthorized rollback.

Store executable TUC evidence in acceptance-testing under the repository's
TUC protocol, not here. These are required tests, not results from this revision.

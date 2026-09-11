# ADR 0118: Universal Container Network Model

- Status: Accepted
- Revised: 2026-09-11 rev 3.2a (SPC supplement: offer digest split, anchored path inventory, vocabulary debt)
- Revised: 2026-09-11 rev 3.2 (capability requirements, scoped offers and satisfaction evidence)
- Revised: 2026-09-10 rev 3.1 (applicability review: ownership, routing/NAT, contexts and migration scope)
- Revised: 2026-09-10 rev 3 (final architecture proposal; implementation choices deferred)
- Date: 2026-09-09
- Revised: 2026-09-10 (single intent model; replaces all earlier D1-D21 text)
- Revised: 2026-09-10 rev 2 (SPC rebuild: legacy translation table, derived-field
  contract, authoring budget; adds D8, no earlier decision withdrawn)
- Related: ADR-0004, ADR-0041, ADR-0086, ADR-0088, ADR-0106, ADR-0107, ADR-0110, ADR-0111, ADR-0119
- Scope: Network intent for workloads and services; capability-qualified backends
- Implementation: Not implemented; approval of this proposal is not deployment approval
- Analysis: [Migration and acceptance](0118-analysis/MIGRATION-AND-ACCEPTANCE.md),
  [Authoring examples](0118-analysis/AUTHORING-EXAMPLES.md),
  [SPC rebuild record](0118-analysis/SPC-REBUILD-2026-09-10.md)

- Final design: [Architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
- Historical implementation exploration (not adopted): [Analysis](0118-analysis/FINAL-IMPLEMENTATION-PROPOSAL.md),
  [verification evidence](0118-analysis/FINAL-PROPOSAL-EVIDENCE-2026-09-10.md)

- Implementation planning: [Reviewed gate plan](0118-analysis/IMPLEMENTATION-PLAN.md),
  [review and corrections, 2026-09-11](0118-analysis/IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md)

## Context

The current AdGuard workload combines an inherited container bridge/gateway
(`172.18.0.0/24`) with a client-facing VLAN address
(`192.168.88.210/24`). These describe different interfaces but occupy one
`network` block. Fixing one gateway field does not resolve address ownership,
service permissions, or bypass paths.

Earlier revisions forced every platform into `primary/service`, then appended
a competing `attachments/publications/policies` model. This edition replaces
both descriptions with one contract. Historical text remains in Git, not as
alternative instructions. The joint review's findings remain evidence, not policy.

## Decision

### D1. Three questions, three concepts

| Question | Concept | Authoritative owner |
|---|---|---|
| Where is the workload connected? | Attachment | L4 workload; references L2 substrate |
| How can a client reach a service? | Publication | L5 service; references its runtime attachment |
| Who may initiate which traffic? | Policy | L2 network policy, explicitly bound by workloads/services |

An attachment exists without any publication. A directly connected LXC does not
need a second IP or NAT. A publication defines delivery, **never permission**.
A route or tunnel does not imply a publication or a permit.

All entities remain Class -> Object -> Instance. Embedded records have stable
local IDs defined by the owning class schema, not by ADR 0088 metadata aliasing.
Baseline local keys match `[A-Za-z_][A-Za-z0-9_]*`, case-sensitive, without dots,
hyphens or @; existing instance IDs are unaffected. References to them
use `workload_ref + attachment_id`, not ambiguous dotted concatenation. Class
schemas define fields, objects supply reusable defaults, project instances bind
real resources. `@group` remains a shard key; layers are derived under ADR 0102,
not selected by a directory or instance field. Generated outputs are never an
authoring or migration source: intent changes in sources, then regenerates.

### D2. Attachments own runtime addressing

A workload's proposed `network.schema_version: 2` contains the named mapping
`attachments.<local_id>`. Each attachment declares:

- stable local key, capability-qualified attachment requirements, L2 `network_ref`,
  and interface identity;
- allocation mode: static from a referenced prefix plus host offset, managed
  dynamic allocation, or shared host stack;
- optional explicit default-route selection, with at most one default per
  address family/routing domain unless an explicit multipath contract exists;
- network policy bindings for direct/egress traffic, when required.

L2 owns prefixes, gateways, zone membership and routing domains. A bridge is
not necessarily an IP network: use its declared prefix only when present,
otherwise reference a modeled address domain. Do not invent VLANs for bridges,
point-to-point links or overlays. Multiple attachments are valid.

**Address domain generalizes the VLAN case; it does not replace it.** A VLAN
instance remains an address domain, so `network_ref: inst.vlan.*` plus `host`
keeps the ADR 0111 intent of numeric prefix-plus-offset derivation, not any
last-octet limitation of its current helper. Bridges, point-to-point links
and overlays become addressable by declaring their own domain instead of a
synthetic VLAN. The ADR 0110 section 1.5 separation is unchanged: many VLANs may
belong to one trust zone, and policy selectors address zones, networks or address
domains, never L4/L5 instances.

Static addresses and gateways derive from the **same attachment's** address
domain (ADR 0111 generalized beyond VLANs). Explicit point-to-point addresses
are permitted with ownership and prefix checks. Off-link gateways require a
modeled route supported by the backend; no gateway is copied from a publication.
Host defaults follow ADR 0107; missing values never grant access or select a
different network. Dynamic allocation requires an authoritative, freshness-bound
binding before enforcement; unsupported dynamics fail rather than become `any`.

### D2.1 Routing/tunnel constraints and interface-scoped NAT

L2 owns route/tunnel intent: bounded selectors, routing domain, next-hop or L2
interface/tunnel endpoint and allowed fallback/failure behavior. L4 owns the
runtime realization binding pointing downward to that L2 endpoint and a concrete
attachment. Reverse joins are derived; strict L2 policies never gain container_ref.
Dedicated /30 networks remain modeled L2 address domains, not workload literals.

Interface-scoped SNAT/masquerade belongs to L2 egress transform intent, not a
service publication. It specifies source domain, egress endpoint and address
translation semantics; it grants nothing. Proxy control traffic and tunnel data
traffic require distinct explicit grants. Kill-switch is a mandatory path deny
against prohibited direct egress, including down/unknown tunnel states.

This closes conceptual ownership, not qualification: existing AWG/proxy chains
remain a declared versioned legacy routing/VPN scope until their extension is
qualified. Sharing a router chain requires proven composition, not just separate
scope labels. Legacy upward refs and raw priority/mark rules are not strict input;
their semantics must be mapped without losing constraints or widening grants.

### D3. Publications own delivery and bind authorization

A service's proposed `network.schema_version: 2` contains the named mapping
`publications.<local_id>`.
Each publication has:

- stable local key and backend attachment; the baseline profile derives the
  workload from `runtime.target_ref`, retaining the full composite ref in the plan;
- delivery mechanism: `direct`, `dnat`, or `host_publish` in v1;
- frontend address reference/allocation and address owner where distinct from
  the attachment; protocol and explicit frontend/backend port mappings;
- required `policy_ref` and intended enforcement binding(s).

`direct` references the attachment's existing address, without allocating a
second one. `host_publish` binds an address actually owned by the host.
`dnat` changes the destination but must preserve the original client/publication
identity for authorization. A proxy that loses client identity needs a separate,
verified application identity contract; a network allowlist is insufficient.

Publication ports and policy selectors are intersected in original client-facing
coordinates; backend port mapping is a transformation, not a competing port
selector. An empty resolved intersection is an error. Backend-only rules
must not accidentally permit unpublished ports, other publications, or direct
access to a backend. Direct backend access needs its own explicit binding.
Absence of publications means **no publication-generated permit**, not proof
that the workload is unreachable.

### D4. One policy algebra; explicit compatibility boundary

The proposed `strict` profile permits a flow only if it matches an approved
explicit permit, satisfies all applicable constraints, and matches no mandatory
deny. All other flows are denied, including intra-zone and outbound traffic.
A permit intersecting a mandatory deny is a blocking authoring conflict with a
counterexample; it is not resolved by position or specificity. Default deny is
the absence of permission, not a mandatory deny that prevents every exception.

Policies declare direction, bounded source/destination selectors, protocol/
ports or typed non-port protocol constraints, owner and rationale. Missing
selectors are invalid, not wildcards. Intentional broad selectors must be explicit
and reviewed; inherited `false`, empty values and zero are not replaced by truthy
defaults. Publication bindings restrict reusable L2 policies to the exact service
endpoint. Non-publication traffic uses explicit attachment/network bindings. The baseline
permits only permit/binding_only templates and deny/scope_guard policies. Scope
guards activate independently of publications, with concrete L2 selectors and
explicit original/current match coordinates for named execution contexts.
Unbound parameters are invalid in a scope guard. Typed binding parameters are not
wildcards; templates never emit independent grants. Endpoint selectors live in
L4/L5 bindings; L2 network bindings use L2 endpoints only.

L2 policies reference network/zone/address-domain selectors, not L4/L5 instances.
L4/L5 point downward to these policies; compilers perform reverse joins to
materialize endpoints. Do not add upward L2 -> service dependencies or a parallel
policy database. Application identity/access constraints stay at L5; their
declared restrictions must be preserved, not inferred from IP membership.
L7 owns approvals, operations and time-bounded exceptions, not duplicate rules.
Existing application clients.service_ref metadata is evidence for a candidate:
resolve its service runtime target to one explicit L4 attachment, preserve
provenance, then review. Ambiguity blocks conversion; source IP alone does not
prove application identity. No automatic L5 service grant is introduced.

ADR 0110's existing R1-R6 behavior remains the **legacy** profile. Its
`isolated` flag is not deny-all egress, and trust level is not authorization.
A future strict schema must explicitly select profile/version for the deployment
scope. Missing selection remains legacy only in the legacy parser; mixed profiles
on one managed boundary fail until an explicit, reviewed composition exists.
No silent conversion of R1/R2/R3 permits into strict permits or new defaults into
currently supported fields is allowed.

### D4.1 Legacy-to-strict translation table

The legacy evaluation order `R6 -> R1 -> R2 -> R3/R4/R5` (ADR 0110 section 2.2,
including the R1a perimeter and R1b internal variants) is unchanged inside the
legacy profile. This table states what each legacy rule becomes in the strict
profile, so no reader has to infer it.

| Legacy rule | Legacy meaning | Strict profile outcome |
|---|---|---|
| R6 explicit `policy_override` accept | Permit with named ports | **Candidate** for an explicit permit; carries source, destination, ports; still requires review, `owner` and `rationale` before it authorizes anything |
| R6 explicit `policy_override` drop | Deny for a zone pair | **Candidate** for a mandatory deny; retains its blocking effect only after review |
| R1a same zone (perimeter) | Implicit allow | **Nothing.** Same-zone traffic is denied unless an explicit permit exists |
| R1b same zone (internal plane) | Deny unless overridden | Aligned with strict default deny; the overrides become R6 candidates |
| R2 isolated source | Deny except to `untrusted` | **Nothing is granted.** The egress-to-untrusted allowance does not survive; required egress becomes an explicit bounded permit |
| R3 downhill | Implicit allow | **Nothing.** Trust level is not authorization |
| R4 uphill | Implicit deny | Consistent with default deny; produces no mandatory deny by itself |
| R5 same level | Implicit deny | Consistent with default deny; produces no mandatory deny by itself |
| Final drop-all (`E7854`) | Mandatory terminal rule on a default-allow backend | Retained as a backend obligation. In strict it is the rendering of a reachable terminal default deny, not a policy; ADR 0119 D4 owns its placement and read-back |

Rows that translate to "nothing" are the intended reduction in implicit grants;
they are also the reason a strict migration needs real flow data rather than a
mechanical rewrite. Candidate status never authorizes traffic and is never
rendered by a generator (ADR 0119 D1).

### D5. Address lifecycle is part of correctness

Address allocation belongs to one L2 domain and one owner. Multiple publications
may reference one allocation but may not allocate the same address independently.
Static attachment syntax is `address: {allocation: static, host: N}`; N is a
numeric network-address offset. The domain declares the gateway, not necessarily
offset 1. Literal addresses belong to L2 allocation inputs, not workload overrides.

Before a publication is deployable, prove:

1. Uniqueness in its routing domain, consistency with interface/prefix/gateway,
   and compatible ownership if sharing an IP across distinct listeners.
2. A real owner and announcement/routing mechanism (e.g. interface ownership,
   managed neighbor announcement, or routed prefix). NAT alone does not own a VIP.
3. No collision with DHCP pools, reservations, active leases or existing listeners.
   IP sharing requires identical owner semantics and disjoint listener matches.
4. Generated dependencies create ownership and safe policy before exposure;
   removal/reallocation revokes flows and stale state before address reuse.

DHCP exclusions are generated only from reviewed address intent. A static pool
check does not prove absence of an active lease: deploy preflight is required.
IPv4/IPv6 allocations, overlapping VRFs and nested workloads are checked in their
own domains; a global string comparison of IP addresses is insufficient.

### D6. Universal concepts, evidence-qualified capabilities

| Target | Representation | v1 qualification requirement |
|---|---|---|
| RouterOS container | Bridge/veth attachment + optional DNAT | Ownership, original-flow binding, routed and bridge paths |
| Proxmox LXC/VM | Direct attachment + optional direct publication | Working host/guest/bridge enforcement, not a router-only assumption |
| Linux Docker | Bridge or shared stack + optional host publication | Actual backend hooks, bind ownership, direct routing and host-local paths |
| Nested Docker/LXC | Multiple attachments and transformations | End-to-end composition; never assume one NAT layer |
| AWG/Tailscale routing workloads | Attachments + explicit route/tunnel policy | Allowed routes, peer/source validation and no forbidden WAN fallback |
| Kubernetes/ingress/other runtime | Same conceptual questions | Deferred until discovery, identity, path and backend conformance contracts exist |

These are modeling targets, **not a supported-platform certification matrix**.
The baseline strict profile is static IPv4 with one runtime backend per publication
and bounded typed flows. Dynamic identity/allocation, IPv6, shared-stack isolation,
HA ownership, multipath and nested transforms require separate qualification.
Unsupported alternate paths must be covered or verifiably disabled, never ignored.
Use ADR 0106 capability checks and versioned conformance evidence, never object
name matching. If a backend cannot enforce a required property, refuse the
candidate or propose a stronger topology boundary for review; do not approximate silently.
Host-network and same-kernel workloads are not independent security boundaries.

For every path (L2, routed, host INPUT/OUTPUT, tunnel, direct backend, IPv6,
offload/acceleration), a policy enforcement point or verified disablement must
be demonstrated. A flag such as `firewall: true` does not establish enforcement.

### D6.1 Capability requirements are derived, not a second intent model

Adopt the shared [capability satisfaction contract](0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md).
Attachments, publications, bindings, route constraints and the selected profile
derive typed requirements with source provenance and NET/SEC obligation IDs.
Authors do not maintain a second capability checklist per publication. Class
schemas define meaning; object/adapter contracts declare reusable offers; instance
placement/configuration determines applicability. Effective capability is a
derived join, not a new topology level or independent registry.

A declaration says what may be possible, not what is enabled, qualified or
authorized. DNAT requires preserved original-flow authorization; direct delivery
requires all-path gates; workload selectors require trustworthy provenance;
tunnel-only egress requires fail-closed route/fallback semantics. These needs
cannot be discharged by a flat union of capability names across devices.

Reuse ADR 0106 catalog/packs and derivation ownership. Device, policy, workload
and operations namespaces keep their existing meaning; neither cap.os.* nor
a capability named for access can mint a grant. Requirements may constrain
strategies, not silently select a wider topology, host-network mode or legacy
fallback. Unsupported realizations require a reviewed source/topology change.

Rev 3.2a adds three constraints without withdrawing any of the above. The D6 path
list is the lower bound of the inventory a capability claim must cover, so a
completeness claim is checked against this ADR rather than against the resolver's
own enumeration. The capability vocabulary is closed and reaches runtime as
identifiers only, so a path that no registered identifier can name is unverified,
not absent — several D6 paths are in that state today. And an offer's qualification
evidence must not participate in plan identity; see the shared contract §4.1.

### D7. Small authoring surface, complete diagnostics

Users author attachments, publications and policy bindings. They do not author
compiler order numbers, anchors, derived addresses or provider resource IDs.

**Derived-field contract.** The following are computed at workload/publication
consumers and must not be overridden there. L2 domain owners still author their
prefixes, gateway, family and routing domain as inputs; these are not forbidden
project-instance fields. A schema accepting consumer overrides fails G1.

| Field | Derived from |
|---|---|
| Effective address | `network_ref` address domain + `host` (ADR 0111) |
| Effective gateway | The same attachment's address domain |
| Routing domain, address family | The referenced network/address domain |
| Zone membership | `network_ref -> trust_zone_ref` (ADR 0110) |
| Rule positions, anchors, `place_before` targets | ADR 0119 D4 canonical order |
| Provider resource IDs and names | Backend rendering |
| Intent, plan and evidence digests | ADR 0119 D2 |

**Authoritative-field contract.** The derived-field contract above fixes one
direction: a consumer must not override what is computed for it. The other
direction needs the same discipline. An object supplies reusable shape and
defaults; it must not author a value that identifies or classifies one concrete
entity, because an object serves many instances and can hold only one such value.

| Value | Belongs to | Reason |
|---|---|---|
| Segment addressing: `vlan_id`, `cidr`, `gateway` | The domain instance | One object cannot give several segments their own addressing |
| Zone identity and classification: name, `security_level`, `isolated` | The zone instance | These are inputs to the policy algebra; a shared object makes them true for one zone and wrong for another |
| Any reference naming one device, enforcer or scope | The instance | A reference to a concrete resource is a binding, not a default |
| Shape, limits and policy defaults: MTU, DNS servers, allowed flow shape | The object | Genuinely repeated across instances |

Two findings in this repository established the rule rather than illustrating it.
`obj.network.vlan.vpn_tunnel` declared a VLAN id and prefix that all four of its
instances overrode, so the object's values were reachable by none of them and a
fifth VLAN would have inherited a colliding prefix. `obj.network.trust_zone.vpn_tunnel`
declared a security level and isolation flag correct for one of its two zones and
wrong for the other, and its zone name still renders on both.

A schema or a review that accepts an authoritative value on a shared object fails
G1 in the same way as a consumer-side derived override. Moving such a value is a
layering change and must be parity-preserving: the effective values, and therefore
the rendered artifacts, stay identical. A value that cannot be moved without
changing an artifact is not a layering defect but a behaviour change, and is
reviewed as one.

**Object-level reuse.** Repeating attachment and publication shape belongs on the
object level, exactly as it does today; project instances carry only what differs.
This is the existing Class -> Object -> Instance mechanism, not a new one, and it
is the reason the current typical workload declares two network keys. Object
defaults are explicit values, so they are not the "missing selectors" forbidden by
D4: an inherited selector is present, an absent one is an error.

An authoring budget for the resulting instance surface is an acceptance criterion,
not an aspiration; see the migration plan's authoring budget section.

All new fields above are a **proposed schema**, not valid current-project YAML.
The domain field `network.schema_version` has the distinct semantic identifier
`network_intent_version`, with explicit network-intent/network-policy contexts;
it is not the ADR 0088 manifest token resolving to @version. ADR 0088 is
context-scoped, not a global ban on nested data-key spelling. Register these
contexts at G1; do not claim they already exist. Typed mapping reference paths
must come from one declarative layer/schema contract with concrete local-key
diagnostics, not divergent validator-specific relation tables.

The implementation must register schemas, reference directions and capabilities
before instance migration. Legacy flat inputs are accepted only if conversion
is unambiguous; mixed/conflicting data blocks migration with an explanation.
No auto-generated permit may be accepted merely to make a migration pass.

Use stable semantic requirement IDs `NET-ATTACHMENT`, `NET-ADDRESS-OWNER`,
`NET-POLICY-BINDING`, `NET-PATH-COVERAGE`, `NET-PROFILE` in design/evidence.
Numeric diagnostic ranges previously suggested here are withdrawn pending a
registry collision check and allocation in the implementation change.

Until that allocation exists, diagnostics carry the semantic ID as their stable
identity and a provisional `NET-*`/`SEC-*` prefixed code, never a number that
could collide with the allocated `E78xx`/`W78xx` ranges of ADR 0110 and ADR 0111.
G1 allocates the numeric codes with a collision test and replaces the provisional
form in one change; the existing 15 network codes keep their meaning.

### D8. Authoring surface is a measured property

The claim in D7 is verifiable or it is not a requirement. For a representative
feature, the instance-level surface is counted as: distinct key paths authored,
instance files touched, and references to resolve. Both a budget and a comparison
against the current model apply, and an exceeding case needs a written reason
rather than silent acceptance. The migration plan holds the concrete budget,
the counting method and the exception procedure; ADR 0043 remains the source of
the underlying cognitive-load principle.

### D9. Identity, inheritance and authorization lifecycle

Attachments, publications and binding collections are named mappings; lists of
selector/port values replace as a whole. Mapping order is not execution order.
Local key plus project/owner/kind defines identity. Duplicate keys are errors.
Removing an override restores inheritance; `enabled: false` disables a record.
Null is neither deletion nor wildcard. Rename is delete/create, not implicit
state transfer. References to missing/disabled records block the candidate.

A publication owns its binding, not the reusable template. Disable/delete removes
that bound grant from desired intent; actual state revocation follows ADR 0119
deadlines. Other bindings remain independently visible. Removing a referenced
template/allocation/attachment requires a consistent dependent change. Removing
a guard is a potential permission expansion requiring review. Changes to inherited
intent invalidate affected semantic approval/evidence. Owner/rationale is not approval.

The [final architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
closes cardinalities, selectors, lifecycle, scope and design trade-offs. It does
not select implementation modules or backend order. Framework/core semantic
ownership and the existing Terraform/Ansible resource-domain boundary are
architectural constraints, as clarified by ADR 0119 D1/D6.

## Consequences and alternatives

- One address belongs to one attachment or explicit frontend owner, not a
  platform-dependent interpretation of a single field.
- Policy is independent of delivery, while backends remain free to lower it
  differently under ADR 0119.
- This requires coordinated schemas, consumers, migration and evidence. Adding
  YAML alone is not completion; no fixed hourly estimate is asserted.
- Rejected: universal dual IPs, NAT-as-permission, automatic trust-level permits
  in strict mode, per-platform duplicated intent models.
- Deferred: runtime-specific mechanisms without an executable conformance suite.

## Acceptance and references

Architecture review may accept this contract separately from implementation.
Strict readiness requires every gate in the
[migration and acceptance plan](0118-analysis/MIGRATION-AND-ACCEPTANCE.md).
The [assurance profile](0119-analysis/ASSURANCE-PROFILE.md) defines the bounded
DoD/NIST alignment claim; it is not ATO, STIG compliance or formal certification.

- [ADR 0119: verified lowering and application](0119-firewall-rule-ordering-contract.md)
- [ADR 0110: legacy matrix semantics](0110-universal-network-zone-vlan-mechanism.md)
- [ADR 0111: address derivation](0111-ip-address-derivation-from-vlan.md)
- [ADR 0107: host defaults](0107-host-placement-defaults-and-on-directive.md)
- [Joint review, 2026-09-09](../docs/reports/2026-09-09-adr0118-0119-joint-security-mathematics-review.md)

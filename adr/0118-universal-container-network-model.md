# ADR 0118: Universal Container Network Model

- Status: Proposed
- Date: 2026-09-09
- Revised: 2026-09-10 (single intent model; replaces all earlier D1-D21 text)
- Related: ADR-0004, ADR-0041, ADR-0086, ADR-0088, ADR-0106, ADR-0107, ADR-0110, ADR-0111, ADR-0119
- Scope: Network intent for workloads and services; capability-qualified backends
- Implementation: Not implemented; approval of this proposal is not deployment approval
- Analysis: [Migration and acceptance](0118-analysis/MIGRATION-AND-ACCEPTANCE.md)

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
local IDs; references to them use `workload_ref + attachment_id`, not ambiguous
dotted concatenation. Class schemas define fields, objects supply reusable
defaults, project instances bind real resources. `@group` remains a shard key;
layers are derived under ADR 0102, not selected by a directory or instance field.

### D2. Attachments own runtime addressing

A workload's proposed `network.schema_version: 2` contains `attachments[]`.
Each attachment declares:

- stable `id`, driver requirements, L2 `network_ref`, and interface identity;
- allocation mode: static from a referenced prefix plus host offset, managed
  dynamic allocation, or shared host stack;
- optional explicit default-route selection, with at most one default per
  address family/routing domain unless an explicit multipath contract exists;
- network policy bindings for direct/egress traffic, when required.

L2 owns prefixes, gateways, zone membership and routing domains. A bridge is
not necessarily an IP network: use its declared prefix only when present,
otherwise reference a modeled address domain. Do not invent VLANs for bridges,
point-to-point links or overlays. Multiple attachments are valid.

Static addresses and gateways derive from the **same attachment's** address
domain (ADR 0111 generalized beyond VLANs). Explicit point-to-point addresses
are permitted with ownership and prefix checks. Off-link gateways require a
modeled route supported by the backend; no gateway is copied from a publication.
Host defaults follow ADR 0107; missing values never grant access or select a
different network. Dynamic allocation requires an authoritative, freshness-bound
binding before enforcement; unsupported dynamics fail rather than become `any`.

### D3. Publications own delivery and bind authorization

A service's proposed `network.schema_version: 2` contains `publications[]`.
Each publication has:

- stable `id` and backend `workload_ref + attachment_id`, consistent with
  `runtime.target_ref`;
- delivery mechanism: `direct`, `dnat`, or `host_publish` in v1;
- frontend address reference/allocation and address owner where distinct from
  the attachment; protocol and explicit frontend/backend port mappings;
- required `policy_ref` and intended enforcement binding(s).

`direct` references the attachment's existing address, without allocating a
second one. `host_publish` binds an address actually owned by the host.
`dnat` changes the destination but must preserve the original client/publication
identity for authorization. A proxy that loses client identity needs a separate,
verified application identity contract; a network allowlist is insufficient.

Publication ports and policy selectors are intersected. Backend-only rules
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
endpoint. Non-publication traffic uses explicit attachment/network bindings.

L2 policies reference network/zone/address-domain selectors, not L4/L5 instances.
L4/L5 point downward to these policies; compilers perform reverse joins to
materialize endpoints. Do not add upward L2 -> service dependencies or a parallel
policy database. Application identity/access constraints stay at L5; their
declared restrictions must be preserved, not inferred from IP membership.
L7 owns approvals, operations and time-bounded exceptions, not duplicate rules.

ADR 0110's existing R1-R6 behavior remains the **legacy** profile. Its
`isolated` flag is not deny-all egress, and trust level is not authorization.
A future strict schema must explicitly select profile/version for the deployment
scope. Missing selection remains legacy only in the legacy parser; mixed profiles
on one managed boundary fail until an explicit, reviewed composition exists.
No silent conversion of R1/R2/R3 permits into strict permits or new defaults into
currently supported fields is allowed.

### D5. Address lifecycle is part of correctness

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
Use ADR 0106 capability checks and versioned conformance evidence, never object
name matching. If a backend cannot enforce a required property, refuse the
candidate or choose a stronger topology boundary; do not approximate silently.
Host-network and same-kernel workloads are not independent security boundaries.

For every path (L2, routed, host INPUT/OUTPUT, tunnel, direct backend, IPv6,
offload/acceleration), a policy enforcement point or verified disablement must
be demonstrated. A flag such as `firewall: true` does not establish enforcement.

### D7. Small authoring surface, complete diagnostics

Users author attachments, publications and policy bindings. They do not author
compiler order numbers, anchors, derived addresses or provider resource IDs.

All new fields above are a **proposed schema**, not valid current-project YAML.
The implementation must register schemas, reference directions and capabilities
before instance migration. Legacy flat inputs are accepted only if conversion
is unambiguous; mixed/conflicting data blocks migration with an explanation.
No auto-generated permit may be accepted merely to make a migration pass.

Use stable semantic requirement IDs `NET-ATTACHMENT`, `NET-ADDRESS-OWNER`,
`NET-POLICY-BINDING`, `NET-PATH-COVERAGE`, `NET-PROFILE` in design/evidence.
Numeric diagnostic ranges previously suggested here are withdrawn pending a
registry collision check and allocation in the implementation change.

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

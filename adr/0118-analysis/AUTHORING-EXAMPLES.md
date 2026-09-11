# ADR 0118/0119 — authoring examples

Status: illustrative companion to **Accepted rev 3.2** (base gate G0a,
2026-09-10; capability amendment 2026-09-11).
The [final architecture proposal](FINAL-ARCHITECTURE-PROPOSAL.md) defines meaning;
the ADRs remain authoritative. These fragments are not accepted by current
schemas and must not be copied into active topology before schema registration.
They illustrate design, not an implemented feature or a deployment-ready fixture.

## 1. Attachment without publication

Object defaults supply reusable shape; instance supplies placement.

```yaml
# Object fragment
defaults:
  network:
    schema_version: 2
    attachments:
      primary:
        enabled: true
        interface: eth0
        address: {allocation: static}
        default_route: true
```

```yaml
# L4 instance fragment
network:
  attachments:
    primary:
      network_ref: inst.vlan.servers
      address: {host: 60}
```

Mapping inheritance preserves interface/allocation/default_route. The address is
domain network address plus 60; gateway belongs to that domain. No publication,
second address, NAT or grant is implied. Other explicit bindings may still exist.
The key primary is a local identity, not a special mandatory interface role.

## 2. DNS publication with a bound policy

All refs below are **test-fixture identities**, not live home-lab allocations.
Premises: client domain 192.0.2.0/24, backend domain 198.51.100.0/24;
gateways are explicitly .1. Backend .20 and frontend .53 have single owners;
frontend is outside a fixture DHCP pool .100–.199. Both paths are modeled.
These premises do not establish real address readiness.

```yaml
# L2 policy fragment, identity inst.policy.dns_test
schema_version: 2
effect: permit
activation: binding_only
direction: ingress
source: {binding: source}
destination: {binding: destination}
flows:
  - {protocol: udp, destination_ports: [53]}
  - {protocol: tcp, destination_ports: [53]}
owner: test-network-owner
rationale: DNS for the client test network
```

```yaml
# L4 dns-test; object defaults refer to backend, not primary
network:
  schema_version: 2
  attachments:
    backend:
      enabled: true
      interface: eth0
      network_ref: inst.bridge.backend_test
      address: {allocation: static, host: 20}
      default_route: true
```

```yaml
# L5 service fragment; runtime supplies the backend workload identity
runtime:
  target_ref: dns-test
network:
  schema_version: 2
  publications:
    dns:
      enabled: true
      backend: {attachment_id: backend}
      mechanism: dnat
      frontend:
        network_ref: inst.vlan.client_test
        address: {allocation: static, host: 53}
        address_owner_ref: rtr-test
        announcement: interface_address
      ports:
        - {protocol: udp, frontend: 53, backend: 53}
        - {protocol: tcp, frontend: 53, backend: 53}
      source_refs:
        - {network_ref: inst.vlan.client_test}
      policy_ref: inst.policy.dns_test
      enforcer_ref: rtr-test
```

With no other grants/guards and all obligations satisfied:
- client -> frontend TCP/UDP 53 is authorized;
- guest -> frontend, client -> UI 3000 and direct backend are not authorized;
- reverse traffic is bounded by the same grant and current epoch;
- policy ports match the original frontend tuple, not an independently chosen
  backend port;
- the template alone grants nothing; owner/rationale are not approval.

Disabling dns removes its grant from desired intent. Actual sessions must be
revoked by the approved deadline; the reusable policy and unrelated bindings remain.
Direct attachment reachability is not removed by deleting publication metadata.

## 3. Two publications, one backend

DNS and admin UI use **two named publication records**, with distinct ports and
source bindings. They may be under one service with one runtime target, or under
two services with explicit runtime targets; they are not a malformed combined
list labeled as two services.

If both share a VIP, they reference one modeled allocation with one owner, rather
than declaring duplicate independent allocations. Sharing a backend, template or
address never merges permissions. Exact duplicate delivery may be normalized,
but all distinct bindings and their provenance remain visible.

## 4. Other architectural cases

| Case | Authoritative intent |
|---|---|
| Direct Grafana access | direct publication references attachment address, management binding |
| App -> database | Database publication binds source app attachment; no L2 upward service ref |
| Workload DNS/NTP egress | Explicit L4 access binding; not automatic outbound allow |
| Network transit | Explicit L2 network binding with bounded endpoints |
| Mandatory deny | L2 scope activates deny-only guard, independent of publications |
| Dynamic/shared identity | Separate qualification contract; never missing selector -> any |

## 5. Derived fields and deliberate negative cases

The workload/publication does not override effective address, gateway, family,
zone, rule positions, anchors, provider IDs or digests. L2 domain declarations
still author their own prefixes/gateway/family: these are domain inputs, not
workload-derived overrides.

Reject: attachment.host outside address; duplicate mapping key; reference to
disabled attachment; unresolved binding; conflicting owner; permit overlapping
mandatory deny; unavailable path semantics.

The earlier production example with LAN .210 remains blocked by its stated
DHCP/lease ownership problem. Changing this teaching fixture to .53 does not
resolve that real deployment issue. Equal host offsets in different domains are
allowed when their independent allocations are valid.

## 6. Route/tunnel and source-client design cases

A dedicated AWG /30 is an L2 address domain plus an L4 attachment. L2 owns the
tunnel endpoint and route/fallback constraint; L4 realization points downward
to it. Interface-scoped SNAT is separate L2 transform intent, never a publication
or a permission. Proxy-to-remote control traffic has its own bounded grant.
Kill-switch blocks prohibited direct-WAN fallback even if the tunnel is down.

These concepts model the existing VPN requirements but do not qualify the AWG
chain for baseline strict. Shared RouterOS chains require composition evidence.

A service client reference (for example a MQTT client service) can suggest a
source candidate by resolving its runtime target to a concrete L4 attachment.
Ambiguous attachments require explicit selection; common IP is not proof of
application identity. Existing clients metadata never activates a permit.

The nested schema_version above is domain data under the distinct proposed
network_intent_version contract, not an alias for manifest @version.
Local record keys use [A-Za-z_][A-Za-z0-9_]*; instance IDs such as dns-test
are a different namespace and are not renamed by that rule.

## 6A. Derived capability requirements, not extra YAML

These fragments gain no required_capabilities list. The compiler derives needs
from their meaning; the [capability contract](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md)
defines scoped offers and evidence:

| Example | Derived requirement, in addition to valid source semantics |
|---|---|
| Attachment without publication | Compatible substrate/domain/interface and independent guard/egress path coverage; no grant inferred |
| Direct publication | Authorized client delivery and adequate host/bridge/routed gates, not merely an IP |
| DNS DNAT publication | Transform support plus preserved original client/frontend identity; distinguish direct backend and other publications |
| Workload source binding | Trustworthy ingress provenance/anti-spoofing or qualified stronger identity |
| Tunnel-only route | Enforced no-direct-fallback behavior in healthy/down/unknown states; separate control-plane grants |

A DNAT capability flag alone does not prove DNS authorization. An adequate
earlier gate may satisfy the identity obligation without original-tuple matching
at the final gate, but only with complete path/state evidence. The compiler
cannot invent a grant or silently choose a different topology to obtain support.
Missing live evidence leaves activation unverified, not an otherwise valid
offline candidate forbidden. These are design examples, not backend test results.

## 7. Legacy and review

Legacy zone/trust rules remain ADR 0110 behavior. In strict, attachment and zone
membership grant nothing. Known ports/source metadata are candidates for review,
not inferred authorization. See [migration and acceptance](MIGRATION-AND-ACCEPTANCE.md)
and ADR 0118 D4.1. Authoring budgets must be measured against the new mapping
shape and include inherited-source navigation; old array counts are historical.

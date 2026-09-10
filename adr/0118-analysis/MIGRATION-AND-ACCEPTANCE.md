# ADR 0118/0119 — Migration and acceptance

Status: supporting plan for **Proposed** ADRs; no migration or live apply performed.
Baseline: WSL repository `/home/nixos/workspaces/home-lab`,
HEAD `ce8018754db0bd28d67568a8f7fb755236c9d8a9`.
Source checks refreshed 2026-09-10. Previous reports' test counts are historical.

## 1. Concrete topology mapping

| Source / situation | Required migration | Exit evidence |
|---|---|---|
| [AdGuard workload](../../projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-adguard.yaml): flat VLAN + inherited bridge | Separate bridge attachment from DNS publication; UI is a separate management grant | Correct backend gateway; approved TCP/UDP 53; denied UI 3000/direct bypass |
| [LAN](../../projects/home-lab/topology/instances/network/inst.vlan.lan.yaml): DHCP .10-.254 | Resolve frontend .210-.212 ownership and collisions before activation; reservation/lease-aware migration | Pool/reservation validation, active lease preflight, owner read-back |
| [Container bridge](../../projects/home-lab/topology/instances/network/inst.bridge.containers.yaml): 172.18.0.0/24 | Model address domain and explicit zone/policy; no synthetic VLAN required | Runtime IP/gateway and intra-bridge enforcement |
| [Mosquitto service](../../projects/home-lab/topology/instances/services/rtr-mikrotik-chateau/svc-mosquitto.yaml): 1883/8883/9001, source and TLS declarations | Preserve IoT/servers restrictions; publish only approved listeners with verified auth/TLS | Unauthorized source denied; plaintext/listener exceptions explicitly reviewed |
| [Servers VLAN](../../projects/home-lab/topology/instances/network/inst.vlan.servers.yaml): staged VLAN 100 | Preserve current canonical 10.0.100.0/24 intent, not old 10.0.30.0/24 examples | Compile-derived address evidence plus actual VLAN/path readiness |
| [Proxmox matrix](../../projects/home-lab/topology/instances/network/inst.security_matrix.proxmox.yaml): disabled/stub | Implement/qualify real internal enforcement before claiming lateral isolation | Same-L2 allowed and denied traffic observed; stale CIDR comment corrected with migration |
| Linux Docker/OrangePi | Confirm actual service bind ownership separately from host management IP | Correct host-local/forward/direct-route filtering with tested Docker backend |
| [AWG Russia](../../projects/home-lab/topology/instances/routeros_container/rtr-mikrotik-chateau/docker-amneziawg-russia.yaml) and Sweden | Preserve dedicated /30 attachments, routing policies and tunnel semantics; not generic service DNAT | Route/peer restrictions and no prohibited WAN fallback on tunnel loss |
| Tailscale exit/subnet router | Explicit permitted routes and identity/ACL integration | Identity expiry, direct paths and route withdrawal tests |

The table is a migration backlog, not authorization to choose new IPs, move
workloads, enable a stub or apply rules. A staged VLAN or feature declaration
is not live evidence. Full source/effective-state inventory must be regenerated
when implementation starts.

## 2. Proposed authoring sketch (not accepted by today's schemas)

The fragments below illustrate the new shape without defining a second complete
schema. All refs/IDs must be validated against registered class schemas in the
implementation. `policy.dns-approved` is a placeholder for a reviewed L2 policy,
not an existing project instance.

```yaml
# L4 docker-adguard — attachment only:
network:
  schema_version: 2
  attachments:
    - id: backend
      driver: veth
      network_ref: inst.bridge.containers
      interface: eth0
      address:
        allocation: static
        host: 210
      default_route: true

```

```yaml
# L5 svc-adguard — delivery plus mandatory policy binding:
network:
  schema_version: 2
  publications:
    - id: dns
      backend:
        workload_ref: docker-adguard
        attachment_id: backend
      mechanism: dnat
      frontend:
        network_ref: inst.vlan.lan
        host: 210
        address_owner_ref: rtr-mikrotik-chateau
        announcement: interface_address
      ports:
        - {protocol: udp, frontend: 53, backend: 53}
        - {protocol: tcp, frontend: 53, backend: 53}
      policy_ref: policy.dns-approved
      enforcer_ref: rtr-mikrotik-chateau
```

**This candidate must currently fail address-readiness validation** because
the LAN DHCP range includes .210. The example does not claim reservation,
active-lease clearance, owner setup or reviewed policy already exists.
Derived backend gateway comes from the container address domain, not the LAN.

For direct LXC, the publication references the existing attachment address:
no second allocation and no DNAT. A workload without a publication keeps its
attachment but gains no publication permit. Host publication uses an address
owned by the host. These distinctions are semantic tests, not template defaults.

## 3. Sequenced implementation gates

| Gate | Deliverable | Must block on | Current evidence |
|---|---|---|---|
| G0 Design | Coherent ADR pair, scope/assumptions, independent review | Contradictions or unassigned hard requirements | Rewritten; human review pending |
| G1 Schema | Registered versioned C->O->I fields, reference paths, profiles and diagnostics | Unknown/mixed versions; code collision; upward dependency | Not implemented |
| G2 Normalize | Legacy adapter, canonical intent and provenance; no permit expansion | Ambiguous flat data, lost false/zero, mismatched gateways/owners | Not implemented |
| G3 Semantics | Reference interpreter, complete plan, obligation checker | Unsupported predicates/path/capabilities; mandatory deny conflict | Not implemented |
| G4 Render | One backend pilot, manifests, deterministic artifacts and differential tests | Generator-created grants; lost original tuple; unstable order | Not implemented |
| G5 Topology | Reviewed service/egress/control-flow inventory and address migration | DHCP/lease collision, absent owner, broad unintended grants | Not implemented |
| G6 Transition | Bundle integrity, safe sequencing, revocation, read-back and recovery | Unproven intermediate state, drift or unsafe rollback | Not implemented |
| G7 Runtime | Positive/negative/failure tests on actual declared paths | Untested L2/IPv6/host/tunnel/offload path; unmet availability | Not run |
| G8 Qualification | Backend/version profile, evidence pack and human risk approval | Missing HA requirement/evidence or stale baseline | Not qualified |

G1-G4 precede migration of instances. All active consumers (IP derivation,
matrix projection, RouterOS/Docker/Proxmox generators, docs, deploy) must switch
together for a migrated scope; comparison mode does not authorize deployment.
Unknown backends fail the new profile without changing legacy scope behavior.

At implementation time update affected ADRs/rule packs, register, semantic
schema registry, layer/reference rules, manifests, tests and framework.lock.
Document an explicit deprecation window; eventually remove legacy adapters only
after source/consumer inventory shows no remaining use. Never edit generated
outputs as the migration source.

## 4. Minimum acceptance matrix

| ID | Scenario | Expected result |
|---|---|---|
| A01 | Approved client -> AdGuard DNS TCP/UDP 53 | Allow; source and publication binding retained |
| A02 | Guest/user -> AdGuard UI 3000 without admin grant | Deny, including direct backend |
| A03 | Two publications sharing backend, different sources | No permission transfer between frontends |
| A04 | Mandatory deny overlaps more specific permit | Compile error with intersecting-flow witness |
| A05 | VIP in DHCP pool/lease, duplicate owner or listener | Candidate/preflight blocked |
| A06 | Direct LXC with no publication | Address retained; no automatic service permit |
| A07 | Same-bridge lateral traffic and host-local access | Enforced declared policy, not router-only inference |
| A08 | Docker bind IP unowned; host network namespace | Block unsafe candidate; prove actual host enforcement |
| A09 | Multi-attachment, nested NAT, overlapping VRFs | Correct domain/route and composed authorization |
| A10 | Missing or stale dynamic identity/address data | Deny/refuse activation, never selector widening |
| A11 | IPv6, ICMP/PMTU/ND, fragments, offload | Explicit supported policy/path or verified disablement |
| A12 | AWG/Tailscale outage or route withdrawal | No prohibited fallback; authorized recovery only |
| A13 | Existing sessions after permit removal/quarantine | Revoked by declared deadline, including related traffic |
| A14 | Input permutations and >1000 independent rules | Same semantic plan; unique consecutive positions |
| A15 | accept-all and all-drop mutants | Fail SEC-AUTH and SEC-AVAIL respectively |
| A16 | Interrupted apply/retry/reboot/concurrent writer | SEC-TRANSITION maintained or restrictive quarantine |
| A17 | Unknown allow above managed dispatch; unsafe rollback | Drift/recovery blocked; no false success |
| A18 | Valid new plan repeated without changes | Idempotent apply and semantically equal observed state |
| A19 | Model-level egress/source restrictions changed | Removing grants cannot enlarge authorized set |
| A20 | Audit flood/lost telemetry and required infrastructure flows | Resource bounds/failure policy met; DNS/NTP/admin availability tested |

Implement as unit/property/differential tests plus separately numbered TUCs
following the acceptance-tuc pack. Keep runnable evidence/logs in each TUC folder.
Do not turn this design checklist into a fabricated passed test report.

## 5. Review finding traceability

"Addressed" below means the design requirement is captured; implementation
closure still needs G1-G8 evidence.

| Previous finding | New contract location |
|---|---|
| F01 publication != authorization | ADR 0118 D3-D4; ADR 0119 D5 |
| F02 misleading isolated defaults | ADR 0118 D4; ADR 0110 compatibility note |
| F03 VIP ownership/DHCP | ADR 0118 D5; A05 |
| F04 Docker ownership/hooks | ADR 0118 D3/D6; A08 |
| F05 none != unreachable | ADR 0118 D3; A06 |
| F06 bypass/L2 coverage | ADR 0118 D6; SEC-PATH |
| F07 forced symmetry | ADR 0118 D1-D3 |
| F08 unsupported Kubernetes | ADR 0118 D6 |
| F09 conflicting codes | ADR 0118 D7; G1 registry gate |
| F10 contradictory examples | One normative edition; explicit blocked candidate above |
| J01 competing normative models | Earlier D sections replaced, not appended |
| J02 priority != authorization | ADR 0118 D4; ADR 0119 D1 |
| J03 incomplete DAG bounds | ADR 0119 D4; formal ordering algorithm |
| J04 hash/range collisions | Consecutive positions and full canonical key |
| J05 specificity not subset | Typed predicates/effects; unknown/conflicting overlap blocks |
| J06 terminal coverage != safety | SEC-AUTH, SEC-AVAIL and separate termination |
| J07 NAT correspondence | SEC-NAT original-flow refinement |
| J08 unsafe/unchecked apply | ADR 0119 D6; SEC-TRANSITION |
| J09 legacy semantics and missing enforcers | ADR 0118 D4/D6; G4-G8 |
| J10 ownership/lifecycle/diagnostics | ADR 0119 D1-D3/D7 |

## 6. Documentation validation

See [revision evidence](REVISION-EVIDENCE-2026-09-10.md) for commands actually
run for this documentation change. Passing those checks does not close A01-A20,
G1-G8, backend support or compliance assessment.

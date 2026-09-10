# ADR 0118/0119 — Migration and acceptance

Status: supporting plan for **Accepted** ADRs 0118/0119 (gate G0a closed 2026-09-10);
no migration, backend qualification or live apply performed.
Baseline: WSL repository `/home/nixos/workspaces/home-lab`, branch `development`,
HEAD `c788237e379a32150ad328b2596cf86678981edc` (the revision-freeze commit).
The earlier pointer `ce8018754db0bd28d67568a8f7fb755236c9d8a9` was its parent and
is kept only as the base of the preceding revision.
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

## 2. Authoring contract

Rev 3 uses named mappings and a single address syntax. The canonical design
and current examples are in [final architecture proposal](FINAL-ARCHITECTURE-PROPOSAL.md)
and [authoring examples](AUTHORING-EXAMPLES.md). Earlier array sketches and the
internal_networks driver-enum assumption are superseded; they are not migration
inputs. Current runtime schemas still do not implement this proposal.

## 2A. Authoring budget

ADR 0118 D8 requires the authoring surface to be measured. This section holds the
criterion so it can be checked rather than asserted.

**Counting method.** For one representative feature, count on project instances
only, excluding class and object files: distinct authored key paths, instance
files touched, and references that a reader must resolve to answer "which address,
who may reach it, where is it enforced". Comments and `@`-meta fields are excluded.
Object-level defaults are not counted, because the author does not write them.

**Measured baseline at the current HEAD.** Twenty-five instance files declare a
network block; twenty-one of them declare exactly two keys. Across the whole
project nine policy override entries exist. For the AdGuard DNS feature the
current instance surface is nine key paths in two files with three references.

**Budget.**

| Feature class | Key paths | Instance files | References |
|---|---|---|---|
| Direct attachment, no publication | 6 | 1 | 1 |
| Single publication with one policy binding | 30 | 3 | 6 |
| Tunnel, multi-attachment or nested transform | no fixed budget; exception procedure applies | | |

The numeric budgets above remain design targets, not achieved measurements.
Rev 2 array-fragment counts are superseded; measure the rev 3 mapping examples
with the same method before schema acceptance. Also report inherited-source
navigation (files/references inspected), separately from files edited, so moving
fields into defaults does not hide cognitive cost.

**Comparison rule.** A migrated feature is also compared against its own current
surface. The recorded AdGuard baseline is 9 key paths in 2 files with 3 references;
remeasure both baseline and candidate consistently when migration begins. Growth is expected
where implicit grants become explicit; growth without a corresponding removal of
an implicit grant is a finding.

**Exception procedure.** Exceeding a budget is allowed and must be recorded with:
the measured numbers, which implicit grant or hidden ambiguity the extra surface
removes, whether object-level reuse was applied first, and an owner. An unexplained
exceeding case blocks G1 sign-off for that schema, not the whole migration.

**Not in scope of the budget.** Obligation counts, gate counts and evidence
requirements are implementer-facing; they are not authoring surface.

## 2B. Filling strict policies from existing data

Strict authorization requires explicit selectors, and the current sources do not
contain them for most services: five of twenty-nine services declare ports, three
declare a source restriction, and none declare a policy owner. A mechanical rewrite
is therefore impossible, and inventing selectors is forbidden. The permitted path
is derive, review, freeze:

```text
derive   compiler proposes candidates from existing ports, allowed_from,
         trust_zone_ref and observed intent; each candidate is marked
         unapproved and carries its source references
review   a human confirms, narrows or rejects each candidate and assigns
         owner and rationale
freeze   the approved result is written back to sources as an explicit
         policy instance; the candidate marking is removed
```

Rules that make this safe:

- a candidate never authorizes traffic, is never rendered by a generator, and is
  never counted as a permit in `A_e`;
- rejecting a candidate is a valid outcome and must not block the pipeline;
- a candidate whose selectors cannot be determined from sources is reported as
  missing data, not widened to `any`;
- freezing writes to project sources, never to generated outputs;
- the derived-from references stay in the frozen policy so the decision is
  auditable later.

Source-only recount on 2026-09-10: of 29 service files, 5 declare top-level ports,
3 declare security.allowed_from, and only 2 declare both. Thus 27 lack at least
one of those fields; 23 lack both. Other metadata can inform candidates but does
not prove flow completeness. Even the 2 with both are not automatically approved
or deployment-ready. Incomplete intent needs verified flow data before freeze. That data collection
is part of G5 and is not an ADR decision.

## 2C. Scope of a coordinated switch

Counted at the baseline HEAD, so the coordination cost in gate G1-G4 is a number
rather than an adjective. No hourly estimate is asserted.

Counting method, so the numbers are reproducible: instance files are `*.yaml`
under `projects/home-lab/topology/instances/`; a network block is a top-level
`network:` key and its keys are counted at one indent level below it; consumers
are repository files containing the token, excluding generated output; validator
plugins are manifest entries, not files in the validators directory.

| Surface | Count |
|---|---|
| Project instances of all kinds | 189 |
| Instance files declaring a network block | 25 |
| Instance files referencing `vlan_ref` | 38 |
| Repository files consuming `vlan_ref` | 28 |
| Plugins among those consumers | 8 |
| Validator plugins registered in manifests | 52 |
| Files consuming `network_binding_ref` | 4 |
| Instance files containing token `trust_zone_ref` | 43: includes 1 comment-only file |
| Instance files declaring a `trust_zone_ref:` key | 42: 10 network, 3 devices, 29 services |
| Routing policies / legacy upward `container_ref` files | 5 / 6 (4 in `inst.routing_policy.*`, 2 inside `inst.vlan.vpn_amnezia` and `inst.vlan.vpn_sweden`; review inventory, not migrated) |
| Instance files declaring an authored `routing_mark` | 9 (5 routing policies, 3 VPN VLANs, 1 tunnel); derived under D2.1, so each is an A23 case |
| Security matrix instances | 2, one of them disabled |

Zone migration must classify ownership, not reject 43 files blindly. Preserve
authoritative L2 declarations; inspect device declarations by their actual domain
role; reject conflicting workload/publication overrides only in the new strict
schema. A service may need a separately named application classification rather
than a replacement network zone. In multi-attachment cases zones belong to
endpoints, not one scalar service-wide zone.

Disabled Proxmox matrix and its overrides remain planned/unqualified inventory.
No intra-zone isolation is claimed until the relevant enforcement path is qualified.
Routing/VPN remains versioned legacy until extension qualification; a shared
forward/mangle/NAT context blocks strict activation without proven composition.
These are design boundaries, not an instruction to migrate or enable devices.

## 3. Sequenced implementation gates

| Gate | Deliverable | Must block on | Current evidence |
|---|---|---|---|
| G0a Architecture | Coherent ADR pair, route/NAT ownership, core authority, Terraform/Ansible boundary, scoped key semantics and independent review | Contradictions or unassigned hard requirements | **Closed 2026-09-10**: accepted after two applicability reviews; ADR 0118/0119 status Accepted |
| G0b Assurance | Named owners for HA-01..HA-10, tailoring record, approved threat model and availability objectives | Any unnamed accountable owner; absent tailoring record | Not started; owner assignment is a human decision |
| G1 Schema | Context-scoped network_intent_version, local-key grammar, typed collection relations, profiles, diagnostics and authoring budget check | Unknown/mixed versions; code collision; upward dependency; unexplained budget excess | Not implemented |
| G2 Normalize | Legacy adapter, canonical intent and provenance; derive-review-freeze for candidates; no permit expansion | Ambiguous flat data, lost false/zero, mismatched gateways/owners, candidate rendered as a permit | Not implemented |
| G3 Semantics | Reference interpreter, complete plan, obligation checker | Unsupported predicates/path/capabilities; mandatory deny conflict | Not implemented |
| G4 Render | One backend pilot, manifests, deterministic artifacts and differential tests | Generator-created grants; lost original tuple; unstable order | Not implemented |
| G5 Topology | Reviewed service/egress/control-flow inventory, flow-data collection for services lacking ports or source restrictions, and address migration | DHCP/lease collision, absent owner, broad unintended grants, frozen policy without source data | Not implemented |
| G6 Transition | Bundle integrity, single resource owner, shared-scope composition, modeled independent management/recovery, revocation and read-back | Missing OOB, unproven intermediate state/composition, drift or unsafe rollback | Not implemented |
| G7 Runtime | Positive/negative/failure tests on actual declared paths | Untested L2/IPv6/host/tunnel/offload path; unmet availability | Not run |
| G8 Qualification | Backend/version profile, evidence pack and human risk approval | Missing HA requirement/evidence or stale baseline | Not qualified |

The gate-by-gate implementation plan derived from these gates is in
[implementation plan](IMPLEMENTATION-PLAN.md).

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
| A21 | Migrated feature measured against the authoring budget | Within budget, or an exception recorded with numbers, removed implicit grant and owner |
| A22 | Unapproved candidate present in the model | No permit in `A_e`, no rendered rule, no accepted flow; rejecting it leaves the pipeline green |
| A23 | Instance declares a derived field (address, gateway, position, provider ID, routing mark) | Schema rejects the instance at G1 |
| A24 | Zone membership, `vlan_cidr_map` and grant derivation across the whole pipeline | Each is derived exactly once, by a core-level plugin; no backend or object module recomputes it. A second producer fails the check |

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

Findings from the SPC review of this revision, recorded in the
[rebuild record](SPC-REBUILD-2026-09-10.md):

| Finding | New contract location |
|---|---|
| S01 plan ownership vs M1-B enforcer ownership | ADR 0119 D1 ownership paragraph |
| S02 legacy R1-R6 outcome unstated | ADR 0118 D4.1 translation table |
| S03 legacy evaluation order unreferenced | ADR 0118 D4.1 header |
| S04 final drop-all and E7854 unreferenced | ADR 0118 D4.1 last row; ADR 0119 D4 |
| S05 ADR 0088 stable-ID basis unreferenced | ADR 0118 D1 |
| S06 zone/VLAN separation only implicit | ADR 0118 D2 address-domain paragraph |
| S07 generated outputs prohibition only in appendix | ADR 0118 D1 |
| S08 authoring surface claim unmeasurable | ADR 0118 D8; section 2A |
| S09 derived fields not enumerated | ADR 0118 D7 derived-field contract; A23 |
| S10 example used one literal for two address domains | Section 2.2 annotations |
| S11 only a deliberately failing example existed | Section 2.1 |
| S12 `driver: veth` outside the current enum | Section 2.2 note; G1 |
| S13 no diagnostic identity before numeric allocation | ADR 0118 D7; ADR 0119 D7 |
| S14 strict data unavailable for most services | Section 2B derive-review-freeze; G5 |
| S15 coordination scope not quantified | Section 2C |
| S16 assurance owners unnamed, tailoring record absent | Gate G0b |
| S17 baseline pointer stale | Header of this document |

## 6. Documentation validation

See [revision evidence](REVISION-EVIDENCE-2026-09-10.md) for the commands run for
the preceding revision, and the [rebuild record](SPC-REBUILD-2026-09-10.md) for
this one. Passing those checks does not close A01-A24, G1-G8, backend support or
compliance assessment.

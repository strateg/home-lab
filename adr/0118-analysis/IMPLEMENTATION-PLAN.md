# ADR 0118/0119 — implementation plan

Status: plan for the **Accepted** architecture (gate G0a closed 2026-09-10).
Nothing here is implemented. No topology, generator, deploy code, secret or device
configuration is changed by this document.

Reference state: commit `769457f5` on branch `development`, clean tree.
Method: Strict Process Compliance, `docs/ai/spc-contract.md`, steps 0-7.

## How this plan was derived

Four choices were required because the architecture deliberately leaves them to
the implementation phase (ADR 0119 D3: plugin count and identity, concrete API
calls, backend order and PR sequence are implementation choices). They were made
explicitly, not inherited:

| Decision | Chosen | Rejected alternatives |
|---|---|---|
| Source of the plan structure | Derived from AD-01..AD-10 and runtime constraints | Adopting the historical exploration wholesale; leaving structure undecided |
| Unit of planning | The gate G1..G8 | PR chain; artifact layer |
| Producer of network intent and security plan | New core compilers subscribing to `effective_model` | Extending `security_matrix_compiler` |
| Gate G0b | Runs in parallel; blocks assurance claims and G6-G8 only | Blocking all work until G0b closes |

`adr/0118-analysis/FINAL-IMPLEMENTATION-PROPOSAL.md` is marked *not adopted* in
both ADRs. Its findings R01-R08 are used here as a defect inventory, verified
independently. Its plugin decomposition, backend order and PR sequence are not
adopted by this plan.

Two things stay architectural and cannot be changed here: backend-neutral
semantics belong to framework/core (AD-07), and the Terraform/Ansible resource
boundary holds under ADR 0057 (AD-08). Moving either requires an ADR amendment.

## Verified baseline

Measured by running the commands, not quoted:

| Fact | Value |
|---|---|
| Targeted test baseline | 32 passed, 1 failed — `test_generator_uses_projection_contract_only`, `firewall.tf.j2:117`, missing `firewall_baseline_rules` |
| `_deep_merge` on named mappings | Preserves inherited `enabled`, `interface`, `address.allocation`, `default_route`; merges `address.host`; replaces value lists whole. **Matches AD-02 without change** |
| `_deep_merge` on lists | Replaces the record entirely, losing `driver`, `interface`, `address.allocation` |
| `_resolve_ip` | Matches numeric arithmetic on every current `/24` and on `/30`+2; returns `10.0.0.300` for `/23`+300 (an invalid address, no error) and `10.0.0.2` for `10.0.0.128/25`+2; gateway always `<base>.1` |
| Published channels `security_matrices`, `zone_vlans`, `matrix_by_enforcer`, `vlan_cidr_map` | Consumed by one validator; consumed by **zero** generators. `mikrotik/plugins/projections.py:590-651` rebuilds `vlan_cidr_map` and `zone_vlans` at generate |
| Validator checking `host` against `dhcp_range` | Does not exist; `dhcp_range` appears only in generators and projections |
| Acceptance coverage A01-A24 | 0 of 24 |
| Files to change, excluding new files and tests | 43 |

## Gate plan

Each gate lists what it delivers, what blocks it, and how it is declared closed.
Exit criteria are completed verifiable deliverables. No hourly estimate is given;
the architecture forbids asserting one.

### Pre-gate work (independent of every gate)

Twelve items depend on nothing and may proceed immediately.

| Item | Work | Exit criterion |
|---|---|---|
| I14 | Define the required/optional projection contract; fix projection, fixture and consumer together | Targeted baseline reaches 33/33. Updating the snapshot or disabling `StrictUndefined` does not count |
| I05 | Make the layer/schema contract the single source of reference rules; the validator reads it | No divergent relation table remains |
| I08, I40 | Restrict local keys to `[A-Za-z_][A-Za-z0-9_]*`; give the network strict profile a name distinguishable from the existing placeholder-contract meaning | Grammar test; no term collision in test names |
| I15 | Make the generator consume the published channels **without changing semantics first**: artifact diffs must be empty | Empty diff, then a separate change for semantics |
| I17 | Type the control-traffic policies that are currently unconditional accepts | ICMP and established handling declared, not blanket |
| I20 | Bring container rendering to the full inventory, or record the unrendered ones as planned | Inventory matches sources or explicitly marks the gap |
| I28, I31, I32 | Resolve the declared/derived zone conflict, declare the container bridge address domain and its zone, correct the stale CIDR comment | Sources agree with the canonical values |
| I37 | Name owners for HA-01..HA-10 and produce the tailoring record | Gate G0b closes. Human decision, not code |

I15 is split deliberately. Consuming the channel and changing what the channel
means are two different changes; combined, the artifact diff stops being evidence
for either.

### G1 — Schema

Delivers: `attachments` on L4 classes, `publications` on L5 classes, policy
`effect`/`activation`, route/tunnel constraint and interface-scoped NAT on L2
classes; typed collection relations; the `network-intent` and `network-policy`
contexts; provisional `NET-*`/`SEC-*` diagnostics.

| Aspect | Content |
|---|---|
| Addresses | I01, I02, I03, I04, I06, I07 |
| Approach | One shared collection definition on the base class, specialized in subclasses — 14 service classes must not carry 14 copies. `network.schema_version: 2` coexists with v1; mixed versions **inside one effective source** are rejected, not ignored |
| Blocks on | Unknown or mixed versions; a schema that accepts a derived field; an upward L2 reference; an unexplained authoring-budget excess |
| Exit | Positive and negative fixtures behave as specified; the authoring budget is measured on the rev 3.1 mapping examples with the section 2A method, including inherited-source navigation; provisional codes pass a collision test against the existing 15 network codes |
| Not in G1 | No instance migration. No numeric diagnostic range before the collision test |

### G2 — Normalize

Delivers: the network intent producer, the legacy adapter, and candidate state.

| Aspect | Content |
|---|---|
| Addresses | I09, I10, I12, I13 |
| Approach | A new core compiler subscribing to `effective_model` / `effective_model_candidate`, publishing intent and a source map. The existing `security_matrix_compiler` keeps owning legacy R1-R6 unchanged. A new resolver does numeric offset arithmetic from the network address and takes the gateway from the domain; `ip_derivation_compiler` remains the legacy adapter for v1 inputs, so the path with no current defect is not disturbed |
| Candidates | Derived from existing `ports`, `allowed_from`, `trust_zone_ref` and `clients.service_ref`; marked unapproved; never counted in `A_e`; never rendered. Rejecting a candidate must leave the pipeline green |
| Blocks on | Ambiguous flat data; lost `false`/zero; mismatched gateway or owner; a candidate reaching a generator |
| Exit | `/24`, `/23`+300, shifted `/25`, `/30` resolve to numeric arithmetic or fail explicitly; legacy conversion is one-directional with divergence diagnostics; A22 passes |
| Not in G2 | No permit expansion. No two canonical sources |

### G3 — Semantics

Delivers: the security plan producer, the reference interpreter and the
obligation checker.

| Aspect | Content |
|---|---|
| Addresses | I10 (plan half), I11 |
| Approach | A second core compiler produces one canonical plan and one projection per enforcer, keyed by that enforcer's `managed_by_ref`. Checking lives in a validate-stage plugin, not inside the compiler — stage affinity holds |
| Blocks on | Unsupported predicates, paths or capabilities; a permit intersecting a mandatory deny; a cycle or unknown match/effect relation |
| Exit | `SEC-AUTH`, `SEC-AVAIL`, `SEC-ORDER` and termination are checkable on a reference model; A04, A14, A15, A19 pass; input permutations produce identical semantic plans |
| Not in G3 | No backend rendering. No claim about installed devices |

### G4 — Render

Delivers: one qualified backend rendering path and deterministic artifacts.

| Aspect | Content |
|---|---|
| Addresses | I16, I18, I19, plus the semantics half of I15 |
| Approach | Object modules lower and render a validated plan only. The terminal deny is emitted by the plan and rendered by the template, and read-back must confirm no executable rule follows it inside the managed sequence; ADR 0110's `E7854` obligation stays in force. Backend selection is deliberately left open here — see open decisions |
| Blocks on | A generator creating a grant; a lost original tuple; unstable order; the pre-gate baseline still failing |
| Exit | Differential test: reference verdict against normalized rendered rules; A03, A24 pass; a second producer of zone membership or `vlan_cidr_map` fails the check |
| Not in G4 | No apply. Renaming a stub is not qualification |

### G5 — Topology

Delivers: reviewed flow inventory, address readiness and the frozen policies.

| Aspect | Content |
|---|---|
| Addresses | I25, I26, I27, I29, I30, I33 |
| Approach | Derive, review, freeze. Twenty-three of twenty-nine services declare neither ports nor a source restriction and none declares an owner, so real flow data must be collected in the running network first. Zone migration separates L2 authority from consumer override; mass deletion of `trust_zone_ref` is forbidden. Upward `container_ref` in six files and authored `routing_mark` in nine files are mapped to the target model, not legalized |
| Blocks on | A DHCP, reservation or active-lease collision; an absent address owner; a broad unintended grant; a policy frozen without source data |
| Exit | Address readiness validated on the model **and** verified against active leases at preflight — either alone is insufficient; A05, A06, A23 pass |
| Not in G5 | No inventing selectors. No deriving service intent from well-known product ports |

### G6 — Transition

Delivers: the safe application contract.

| Aspect | Content |
|---|---|
| Addresses | I21, I22, I23, I24, I39 |
| Approach | A transaction controller over the existing runner boundary, not a new transport. Terraform keeps RouterOS post-bootstrap desired configuration under ADR 0057; orchestration owns sequencing, observation and evidence. Ownership is explicit in data, with author, approver, scope owner and writer distinguished. OOB is an L7 recovery contract over an independent management path; the management UI reached through the same router is not evidence |
| Blocks on | Missing OOB; unproven intermediate state; unproven composition of a shared chain; drift; unsafe rollback |
| Exit | `SEC-STATE` and `SEC-TRANSITION` hold under interrupt, retry, reboot, concurrent writer and stale identity; A13, A16, A17, A18 pass; rollback cannot resurrect a revoked grant |
| Not in G6 | Transferring resource ownership away from Terraform, which needs an ADR amendment |

### G7 — Runtime

Delivers: positive, negative and failure evidence on actually declared paths.

| Aspect | Content |
|---|---|
| Addresses | I33, I34, I36 |
| Approach | The six regression layers built bottom-up: unit algebra, property, ordering, differential, stateful and path, fault injection. New scenarios become separately numbered TUCs with their evidence in the TUC folder |
| Blocks on | An untested L2, IPv6, host, tunnel or offload path; unmet availability |
| Exit | A01-A24 have executable coverage; reports distinguish design, offline-validated, backend-tested and live-observed; missing evidence reads `not run` or `unsupported`, never pass |
| Not in G7 | A green documentation run is not implementation evidence |

### G8 — Qualification

Delivers: the backend/version profile, the evidence pack and human risk approval.

| Aspect | Content |
|---|---|
| Blocks on | A missing HA requirement or its evidence; a stale baseline |
| Exit | Every applicable HA-01..HA-10 requirement holds at its necessary evidence level; a named person accepts the residual risk |

### G0b — Assurance, in parallel

Named owners for HA-01..HA-10, the tailoring record, the approved threat model
and availability objectives. It gates assurance claims and G6-G8; G1-G3 do not
depend on it and proceed alongside. Until it closes, reports say "proposed
high-assurance network contract", never "compliant".

## Dependency structure

```text
pre-gate (12 independent items, I14 first among them)
        |
        v
G1 schema ----> G2 normalize ----> G3 semantics ----> G4 render
                                                          |
G0b assurance (parallel, human)                           v
        \-------------------------------> G5 topology --> G6 transition --> G7 runtime --> G8 qualification
```

The longest chain is six links: schemas, intent, plan, bundle evidence,
transition, shared-chain composition. G5 needs G1-G4 for its schema and plan, and
independently needs flow data that only the running network can supply, so its
data collection starts as soon as G1 fixes what a policy must contain.

## Open decisions, deliberately not made here

Recording them is not deferral by omission; each has an owner and a gate.

| Decision | Options | Owner | Gate |
|---|---|---|---|
| First backend to qualify | The architecture explicitly does not pick RouterOS first and does not declare Proxmox or Docker ready | Implementation owner | Before G4 |
| Shared forward/mangle/NAT chain | Prove composition of all rules, dispatch and transforms under one writer, or separate the scope physically | Scope owner | G6 |
| Security digests in the bundle | Extend the existing bundle contract, or add a parallel manifest | Build/release owner | G6 |
| Unrendered RouterOS containers | Complete the rendering, or bound the scope and keep them visible as planned | Topology owner | G4 |

The shared-chain decision is the one that reaches furthest: there is one enforcer
and one forward chain, so until composition is proven or the scope is separated,
strict activation is blocked for the whole topology, not only for the VPN plane.
That constraint is correct and raises the entry threshold; it is not a defect.

## What this plan does not authorize

No deployment, no migration of instances, no device change, no enabling of a
disabled enforcer, no compliance claim. Gates G1-G8 remain open and acceptance
scenarios A01-A24 remain unclosed until their evidence exists. ADR 0110 keeps its
implemented R1-R6 behavior and the strict profile is active nowhere.

## Traceability

Problems I01-I41 and mechanisms are recorded in the SPC cycle that produced this
plan. Every gate above names the problems it closes; no problem was resolved by
rewording, and the items that cannot be closed by code — owner assignment, flow
data collection, the OOB decision — are listed as such rather than absorbed into
a gate.

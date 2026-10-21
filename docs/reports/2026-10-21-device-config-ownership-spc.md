# Device configuration ownership: knowing what Terraform changes, and leaving no garbage — SPC analysis

2026-10-21. Formal analysis under `docs/ai/spc-contract.md`, steps 0–5. Step 6
(model rebuild) is deliberately not entered: it requires a decision on *which*
admissible option to implement.

**Question posed:** what software mechanisms in the topology system can make it
visible what Terraform changes and what stays behind as garbage on a device,
given the requirement that **no garbage may exist on the device**.

Procedural `GO STEP X` gating is suspended by standing operator instruction;
the content obligations of the contract (document map, constraints register,
facts before conclusions, classification before solutions, no model changes
before approval) are kept.

---

## STEP 0 — READ FIRST

**ALL MATERIALS READ.**

Read in full before any analysis:

* `docs/ai/spc-contract.md`, `CLAUDE.md`, `docs/ai/AGENT-RULEBOOK.md`
* ADR 0103 (runtime reconciliation status — including its cancellation
  section), ADR 0105 (device state commit/rollback), ADR 0115 (hash-based
  deploy idempotency), ADR 0055 (manual Terraform extension layer), ADR 0083
  (unified node initialization), ADR 0119 (firewall rule ordering contract)
* `topology-tools/plugins/generators/artifact_contract.py`
  (`compute_obsolete_entries` and ownership proof), the builders manifest
  (`topology-tools/plugins/manifests/builders.yaml`), the discoverers manifest
  and `topology-tools/plugins/discoverers/`
* `topology-tools/plugins/builders/soho_readiness_builder.py` (the
  `drift-report.json` producer)
* `topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py`
  and the rendered roots under `generated/home-lab/terraform/mikrotik/`
* `projects/home-lab/topology/instances/network/` in full (routing policies,
  security matrices, tunnels, VLANs, trust zones)
* `topology-tools/data/error-catalog.yaml`
* this session's two prior reports:
  `docs/reports/2026-10-21-chateau-dead-rules.md`,
  `docs/reports/2026-10-21-rtr-slate-track-conservation.md`

Measured live (read-only REST GET against `rtr-mikrotik-chateau`, credentials
from `projects/home-lab/secrets/terraform/mikrotik.yaml` per CORE-010):
`/ip/firewall/filter`, `/ip/firewall/nat`, `/ip/firewall/mangle`,
`/ip/firewall/address-list`, `/interface/vlan`, `/interface/list/member`,
`/ip/dhcp-server`, `/ip/pool`, `/ip/dns/static`, `/interface/wireguard`,
`/interface/wireguard/peers`, `/routing/table`, `/ip/route`. State read from
`.work/native/home-lab/terraform/mikrotik/terraform.tfstate` (serial 912,
2026-10-02). Nothing on the device was modified.

---

## STEP 1 — DOCUMENT MAP

| Document | Owner / Stakeholder | Purpose | Binding Requirements | Data Used |
|---|---|---|---|---|
| `CLAUDE.md` + `docs/ai/AGENT-RULEBOOK.md` | project | operating rules for any change | CORE-001…010: edit sources not `generated/`; stage affinity; framework lock; secrets only via SOPS; ADR governance for architectural change; command evidence for validation | all of it |
| ADR 0080 | architecture | 6-stage pipeline `discover → compile → validate → generate → assemble → build`, plugin data bus | stage affinity; `consumes`/`produces` declared in manifests | stage/phase/order model |
| ADR 0063 / 0065 / 0106 | architecture | plugin microkernel, API contract, capability-driven resolution | no hidden coupling outside `depends_on`/`consumes`/`produces` | plugin families, contracts |
| ADR 0074 | architecture | v5 generator architecture | generator determinism; offline/CI-safe builds | determinism constraint |
| **ADR 0103** | architecture | runtime reconciliation status replaces static `status:` | D1 implemented (topology = intent only); **D2–D12 cancelled 2026-06-18** | the cancelled reconciler design, and its five rationale points |
| **ADR 0105** | architecture | device state commit and rollback | **Deferred** (C1–C3 unresolved); "use proven tool patterns, do not reinvent" | apply/rollback boundary |
| **ADR 0115** | architecture | incremental hash-based deploy idempotency | **Proposed**, prerequisite ADR 0105 | granular drift detection gap, stated by the architecture itself |
| ADR 0055 | architecture | manual Terraform extension layer | manual `.tf` additions are legitimate, tracked, and separate from generated roots | precedent for a sanctioned exception layer |
| ADR 0083 | deploy domain | unified node initialization | `--import-existing`, `--acknowledge-drift`, `--reset/--confirm-reset` semantics exist at node level | existing drift vocabulary |
| ADR 0091 | product | SOHO readiness evidence | `drift-report.json` is a required handover artifact | the artifact exists and is a stub |
| ADR 0119 | architecture | firewall rule ordering contract | **Accepted, not implemented**; no backend has qualified | ordering/verification obligations |
| ADR 0110 / 0118 | architecture | zone/VLAN mechanism, container network model | matrix → enforcement lowering; one matrix per enforcer | what the rendered rules mean |
| `artifact_contract.py` | framework | per-generator artifact plan, generation report, obsolete detection | `planned`/`generated`/`obsolete`/`skipped`; **delete requires ownership proof** | the GC pattern to transpose |
| `terraform.tfstate` (native workspace) | operator | Terraform's record of what it owns | only resources in state are seen by `plan` | 162 resource ids across 10 families |
| device REST API | operator | ground truth of what exists | the only authority on reality | 314 live objects across those families |
| `docs/reports/2026-10-21-chateau-dead-rules.md` | this session | audit of the unreachable rules | 63 dead forward rules, 0 owned; the ws-nixos gap | measurements reused here |

---

## STEP 2 — CONSTRAINTS REGISTER

| Stakeholder | Requirement | Criticality | Type | Verification Mechanism | Source |
|---|---|---|---|---|---|
| Operator | It must be visible, before applying, which device objects Terraform will create / change / destroy | **Critical** | Operational | a report artifact that enumerates the four classes and is diffable | this request |
| Operator | No garbage on the device | **Critical** | Operational | live inventory minus (planned ∪ sanctioned) = ∅, machine-checked | this request |
| Operator | Configuration must be repeatable from topology | **Critical** | Governance | regenerate → apply → inventory converges with no manual step | this request, CORE-003 |
| Project | Topology declares intent; reality is queried, never hand-maintained in instance YAML | **Critical** | Governance | no `status:`-like reality fields reintroduced | ADR 0103 D1 |
| Project | The compile/generate pipeline stays deterministic and offline/CI-safe | **Critical** | Governance | identical inputs → byte-identical artifacts; no network calls in `compile`/`generate` | ADR 0074, ADR 0103 D2.1 |
| Project | Stage affinity preserved; any new plugin declares `consumes`/`produces` | **Critical** | Governance | `task validate:plugin-manifests`, plugin contract tests | CORE-004, ADR 0063/0080 |
| Project | `generated/` is never hand-edited; sources are edited and regenerated | **Critical** | Governance | `task validate:default`, generator tests | CORE-002 |
| Project | Credentials only through SOPS/age; no secret reaches an artifact | **Critical** | Legal/Governance | `V5_SECRETS_MODE`, secrets tests | CORE-006, ADR 0072 |
| Project | Architectural change carries ADR governance | **Critical** | Governance | `task validate:adr-consistency` | CORE-007 |
| Project | A new diagnostic family is allocated against a measured free band and registered before it is raised | Important | Governance | diagnostic registry tests | error-catalog convention, ADR 0088 |
| Operator | Live changes to shared infrastructure are confirmed, performed in safe mode, and reversible | **Critical** | Operational | `/system safe-mode`, backup before the window | ADR 0105 intent, operator instruction |
| Operator | Deleting anything that currently carries traffic requires explicit per-object evidence | **Critical** | Operational | packet/byte counters read immediately before deletion | measured in STEP 3 (3 such objects) |
| Operator | Not-modelled-but-needed configuration must survive (defconf, vendor features, manual exceptions) | **Critical** | Operational | an explicit sanctioned-exception list; deletion refused without ownership proof | measured in STEP 3 (46 such objects) |
| Project | Effort proportional to a single-operator home lab | Important | Operational | staged options, each independently useful | ADR 0103 cancellation rationale |
| Project | Reuse mature tooling rather than reimplementing it | Important | Governance | reviewed against Terraform/RouterOS native capabilities | ADR 0105 "do not reinvent wheels" |

No Critical requirement is identified as impossible. Two are **currently
unmet** and that is the subject of this analysis.

---

## STEP 3 — DIAGNOSTIC ANALYSIS

Facts and measurements only. No classification, no proposals.

### 3.1 The three inputs, and what each one can and cannot see

| Input | Authority over | Objects observed | Blind to |
|---|---|---|---|
| rendered `generated/home-lab/terraform/mikrotik/*.tf` | intent (what should exist) | 262 resource declarations | anything on the device |
| `terraform.tfstate` (native, serial 912) | what Terraform believes it owns | 162 ids in the 10 families examined | every object it never created |
| device REST API | what exists | 314 objects in those families | intent and ownership |

`terraform plan` compares the first two only. **It is structurally incapable of
reporting an object that is not in state.**

### 3.2 Four-class decomposition of one family (firewall filter rules)

Computed from the three inputs above. Ownership marker = the substring
`managed by topology`, which the generator stamps into the `comment` field of
every filter rule it renders.

| Class | Count | What `terraform apply` does | What it is |
|---|---|---|---|
| rendered ∧ in state | 86 | keeps / updates in place | correctly owned |
| rendered ∧ ¬in state | 6 | **creates** | the two routing policies added earlier today (4 of the 6 already exist on the device as hand-made rules → an apply would produce a second copy) |
| ¬rendered ∧ in state | 1 | **destroys** | `zone_override_user_to_servers_http_tcp` (`*190`), withdrawn from the model today |
| ¬rendered ∧ ¬in state ∧ marked | **87** | **nothing — invisible to plan** | carries our own ownership marker; Terraform does not know it exists |
| ¬rendered ∧ ¬in state ∧ unmarked | 24 | nothing | `defconf:` rules, manual rules, hand-made rules |
| dynamic | 3 | nothing | RouterOS-managed (back-to-home-vpn, fasttrack counter) |
| **total live** | **201** | | |

86 + 1 = 87 = the state count. 87 + 87 + 24 + 3 = 201 = the live count. The
decomposition is complete and reconciles against both inputs.

### 3.3 The same decomposition across ten resource families

| Family | live | dynamic | in state | rendered | **marked, ¬in state** | unmarked, ¬in state |
|---|---|---|---|---|---|---|
| `ip_firewall_filter` | 201 | 3 | 87 | 92 | **87** | 24 |
| `ip_firewall_nat` | 19 | 1 | 10 | 10 | **4** | 4 |
| `ip_firewall_mangle` | 28 | 3 | 12 | 16 | **6** | 7 |
| `ip_firewall_addr_list` | 17 | 0 | 12 | 12 | 0 | 5 |
| `interface_vlan` | 9 | 0 | 9 | 9 | 0 | 0 |
| `ip_dhcp_server` | 7 | 0 | 7 | 7 | 0 | 0 |
| `ip_pool` | 10 | 0 | 7 | 7 | 0 | 3 |
| `ip_dns_record` | 14 | 0 | 10 | 10 | **1** | 3 |
| `interface_wireguard` | 4 | 0 | 4 | 4 | 0 | 0 |
| `interface_wireguard_peer` | 5 | 1 | 4 | 4 | 0 | 0 |
| **total** | **314** | **8** | **162** | 195 | **98** | **46** |

98 of 314 live objects (31%) carry our marker and are unknown to Terraform.
46 (15%) are unmarked and unknown. The pattern is not confined to firewall
filter rules; it is strongest there because that is the family with the most
objects and the only one with ordering semantics.

### 3.4 Composition of the 98 marked-but-unowned objects (filter family, 87)

| Property | Count |
|---|---|
| comment matches a comment the generator still plans → duplicate of an owned rule | 79 |
| comment matches nothing planned → leftover of a withdrawn rule | 8 |
| **currently passing traffic (packets > 0)** | **3** |
| in the unreachable tail (below the terminal drop) | 58 |

The three with traffic sit at forward indices 3, 4 and 11 — *above* their
Terraform-owned twins:

| id | comment | packets | bytes |
|---|---|---|---|
| `*BD` | VPN-Sweden tunnel ingress | 7 019 113 | 9.44 GB |
| `*BC` | VPN-Sweden tunnel egress | 3 369 393 | 499 MB |
| `*9A` | Allow LAN to WAN | 242 429 | 57 MB |

Their owned twins exist later in the chain. Deleting the unowned copy moves the
match to the twin; whether the result is identical depends on what lies between
the two positions.

### 3.5 Composition of the 46 unmarked objects

Includes 11 RouterOS `defconf:` rules (two of them carrying 7.8 M and 1.9 M
packets), three Transmission rules, two management-access rules, the four
hand-made ws-nixos rules (0 packets, superseded by today's topology change),
and `*BB` "AWG-Proxy Sweden Test WAN egress" at **3 386 244 packets** — a rule
that is live, load-bearing, unmarked and modelled nowhere.

### 3.6 Ownership-marker coverage on the rendered side

262 rendered resources; 190 carry the marker (72.5%). Families with no marker
at all: `container_envs` (40), `ip_pool` (7), `wifi` (5),
`interface_wireguard_peer` (4), `interface_veth` (2), `container` (2),
`wireguard_asymmetric_key` (2), `ip_dns` (1), `container_config` (1). Partial:
`ip_address` 13/17, `interface_wireguard` 2/4, `interface_list_member` 2/4.

### 3.7 Ordering facts (filter family)

The terminal drop is `*E0` = `zone_drop_all_forward`, Terraform-owned, at
forward index 119 of 183. 63 rules sit below it, all at 0 packets, none
Terraform-owned. Every filter resource the generator renders carries
`place_before = routeros_ip_firewall_filter.zone_drop_all_forward.id`, and all
82 owned forward rules are above the terminal drop. No rendered artifact and no
check records the device-side *position* of anything.

### 3.8 State of the mechanisms the architecture already defines

| Mechanism | Designed in | Status | Observed |
|---|---|---|---|
| `base.builder.terraform_state_reconciler` (build stage, phase verify, consumes normalized rows + tfstate, produces reconciliation report) | ADR 0103 D2.1 | **cancelled 2026-06-18** | not present in `builders.yaml` |
| `lane.py reconcile` CLI comparing topology vs state vs device over REST | ADR 0103 D2.2 | **cancelled** | no REST client exists anywhere in `scripts/` or `topology-tools/` |
| device state commit + rollback | ADR 0105 | **Deferred** (C1–C3) | — |
| granular/incremental drift detection | ADR 0115 | **Proposed**, blocked on 0105 | — |
| `drift-report.json` as a required handover artifact | ADR 0091 | implemented as a stub | `{"drift_state": "unknown"}`, a constant written by `soho_readiness_builder.py` |
| file-level obsolete detection with ownership proof and `retain\|warn\|delete` policy | `artifact_contract.py` | **implemented and in use** | per-generator `artifact-generation-report.json`, `obsolete_count: 0` |
| ordering contract for rendered rules | ADR 0119 | **Accepted, not implemented** | "no backend has qualified under this contract" |
| node-level drift vocabulary (`--acknowledge-drift`, `--import-existing`, `--reset`) | ADR 0083 | implemented | operates on node initialization status, not on individual device objects |
| `discover` stage | ADR 0080 | implemented | discovers plugin manifests only; **zero** object-module discoverers exist |

### 3.9 The five rationale points of the ADR 0103 cancellation, against measurement

| # | Stated rationale (2026-06-18) | Measurement (2026-10-21) |
|---|---|---|
| 1 | Core goal (removing static `status:`) achieved by Wave 3 | Confirmed; D1 holds and is not in question |
| 2 | "Terraform is the reconciliation engine; `terraform plan` already computes drift" | `plan` sees 162 of 314 objects. 98 marked-but-unowned objects are invisible to it, 58 of them in an unreachable tail. A "no changes" plan coexisted with all of it |
| 3 | "single operator who knows what is deployed because they deployed it" | The hand-made ws-nixos rules were neither remembered nor detected; they were found only by reading the device in this session |
| 4 | Dual-mode (plugin + CLI) overengineered for a home lab | Not contradicted by measurement; the cost argument stands on its own |
| 5 | "No risk from cancellation… no value that `terraform plan` does not already provide" | Two of ws-nixos' country exits could not pass a packet for an unknown period. `plan` reported nothing, because nothing it owned was wrong |

### 3.10 Diagnostic band availability

217 codes catalogued; 247 codes raised in code but absent from the catalog.
E81xx — the band ADR 0103 Phase 0.2 earmarked for reconciliation — has since
been consumed by `workspace_assembler.py` (E8101–E8105). Fully free bands
adjacent to the deploy/assembler family: **E84xx, E85xx, E86xx, E87xx**
(`W84xx…W87xx` likewise). E99xx is free on `development` but reserved by the
conserved rtr-slate track (`frozen/rtr-slate-terraform-2026-10-21`).

---

## STEP 4 — PROBLEM CLASSIFICATION

### P1 — Ownership is not represented as data. *Design gap.*

The system renders intent and Terraform records its own state, but **no
artifact states which device objects the project claims**. Ownership exists
only implicitly, in two places that were never meant to carry it: a free-text
`comment` substring on the device, and Terraform's private state file. There is
nothing to join them against. This is why the question "what is garbage" cannot
currently be answered by any tool in the repository.

### P2 — Reality is not an input to the pipeline. *Design gap, deliberately created.*

Six stages exist; none consumes device state. The plugin and the CLI that would
have done so were specified in ADR 0103 and cancelled. The cancellation's load-
bearing premise (`terraform plan` suffices) is falsified by §3.9/§3.2: `plan` is
a comparison of intent with Terraform's *memory*, not with the device. Reality
enters the repository today only through a human reading a router, or through
`observed_runtime` fields hand-copied into instance YAML.

### P3 — Garbage has no definition. *Governance gap.*

"No garbage on the device" is not yet a checkable predicate, because the
complement of "planned" is not "garbage": §3.5 shows 46 live objects that are
unmodelled and legitimate (vendor `defconf`, manual exceptions, one rule
carrying 3.4 M packets). Until a sanctioned-exception layer exists for device
objects — the analogue of ADR 0055's tracked manual `.tf` layer — any automated
deletion is unsafe, and any claim of "no garbage" is unfalsifiable.

### P4 — Ordering is rendered but never verified. *Implementation gap.*

The generator encodes the correct ordering obligation (`place_before` the
terminal drop) and ADR 0119 states the contract formally, but nothing checks
either side: not the rendered plan, and not the device. A permit rendered
correctly and *placed* below the terminal drop is indistinguishable, in every
artifact the pipeline produces, from one that works. This is the specific gap
that let two country exits be dead while every gate passed.

### P5 — A declaration can look like configuration and enforce nothing. *Design gap.*

`inst.tunnel.wg-exit.chateau_routing` declares mangle and firewall rules for
four addresses in the same vocabulary the generators use. No plugin consumes
it. The pipeline has no obligation that a configuration-shaped block be read by
someone, so authoring one is silent. Same shape as the five instances of
"declared, validated, not enforced" recorded on the conserved rtr-slate track.

### Classification summary

| Problem | Kind | Blocks which Critical requirement |
|---|---|---|
| P1 ownership not data | design gap | "visible what Terraform will change", "no garbage" |
| P2 reality not an input | design gap (cancelled by decision) | "no garbage", "repeatable" |
| P3 garbage undefined | governance gap | "no garbage" |
| P4 ordering unverified | implementation gap | "repeatable" (a correct model can be dead on the device) |
| P5 unread declarations | design gap | "repeatable" |

P1–P3 are a single causal chain: without ownership data (P1) and a reality
input (P2), garbage cannot be defined (P3). P4 and P5 are independent defect
generators that produce the same symptom class and are cheaper to close.

---

## STEP 5 — ADMISSIBLE SOLUTION SPACE

Mechanisms first, then the options assembled from them. Nothing here is
implemented; no model, number or artifact was changed in producing this step.

### 5.1 Candidate mechanisms

| # | Mechanism | Where it attaches | Constraints it must respect | Admissible? |
|---|---|---|---|---|
| **M1** | **Resource-level ownership ledger.** Each generator emits, beside its `.tf`, a machine-readable ledger of every resource it renders: type, logical name, identity keys (the match tuple that makes it findable on the device), and the marker it stamps. | `generate` stage, as a sibling of the existing `artifact-plan.json` | determinism (pure function of compiled model); no secrets | **Yes.** The data already exists inside the generators; `artifact_contract.py` already writes per-plugin contract artifacts |
| **M2** | **Universal marker discipline.** Extend `managed by topology` to every resource type whose RouterOS object has a comment field; record in the ledger, per resource, which proof channel applies (marker / state-only). A diagnostic refuses a rendered resource with no proof channel at all. | `generate` + `validate` | marker text is part of the device's observable config; changing it rewrites comments on apply (one-time churn, measurable in a plan) | **Yes**, with the caveat that 72 rendered resources today have no marker and some types cannot carry one |
| **M3** | **Device inventory snapshot as a file.** A standalone collector (REST, SOPS credentials) writes a timestamped inventory of a device's objects to a known path; the pipeline consumes the *file*, never the network. | collector = CLI (deploy domain); consumption = `build` stage | pipeline determinism and offline/CI-safety are preserved precisely because the live call is outside it; snapshot must carry no secrets (wireguard private keys, PSKs must be redacted) | **Yes.** This is ADR 0103 D2.2 reshaped so that D2.1's determinism argument no longer conflicts with it |
| **M4** | **Reconciliation / GC builder.** `build` stage, phase `verify`: inputs = ownership ledger (M1) + tfstate + inventory (M3); output = reconciliation report with the four classes of §3.2 plus the ordering facts of §3.7, and a remediation script (RouterOS `/remove [find .id=…]` for proven garbage, `terraform import` for objects that should be adopted). Reuses `compute_obsolete_entries` semantics verbatim: `ownership_proven` flag, proof method, and action policy `retain | warn | delete` where **delete without proof degrades to warn and records an error**. | `build`, order ≈ 530, after the existing verify builders | stage affinity; `consumes`/`produces` declared; must not perform the deletion itself | **Yes.** It is the cancelled ADR 0103 Wave 1 plus the device side, built on a GC pattern already proven in this repo at file level |
| **M5** | **Sanctioned device-exception layer.** A tracked topology-side declaration listing device objects that are legitimately not generated (vendor `defconf`, manual exceptions), each with an owner and a reason, so that *garbage* = live − planned − sanctioned − dynamic. | topology (project instances) + `validate` | must be explicit, reviewable and small; an entry is a claim that needs a reason | **Yes.** Direct analogue of ADR 0055, which already sanctions tracked manual `.tf` additions |
| **M6** | **Ordering verification.** Two checks: (a) `validate`/`generate` — every rendered permit in a chain that has a terminal drop declares `place_before` it; (b) `build` — for each owned permit in the inventory, its device position precedes the terminal drop and no earlier rule with a conflicting action shadows its match tuple. | `validate` + `build` | (b) needs M3; (a) is pure offline | **Yes**, and (a) alone would have caught the ws-nixos defect at compile time |
| **M7** | **Consumer obligation for configuration-shaped blocks.** Every instance block that speaks device configuration must name its consumer (an `@`-prefixed semantic key per ADR 0088), and a validator refuses a named consumer that does not exist or does not read it; blocks explicitly marked documentation are exempt and are rendered as such. | `validate` | ADR 0088 semantic-key registry; must not require the plugin bus to expose instance-data read sets | **Yes** |
| **M8** | **Golden-config application.** Stop relying on incremental convergence for the device: generate a complete configuration (RouterOS `.rsc`) and apply it to a reset device, so that anything not in the model ceases to exist by construction. | `generate` + deploy domain | requires ~100% model coverage of the device, a maintenance window, and a verified backup; §3.5 shows at least one live load-bearing rule modelled nowhere; `defconf` and vendor features must be modelled or deliberately dropped | **Conditionally.** Not admissible *now* (coverage gate fails); admissible as a target state once M1–M5 report full coverage |
| **M9** | **Terraform-only tightening** (`import` blocks for everything, `-refresh-only` plans, provider-level ownership). | deploy domain | no change to the topology system | **Partially.** It fixes the *adoption* half (bringing unowned objects into state) but cannot enumerate what to adopt: Terraform never sees an object it does not own. Necessary, not sufficient |
| **M10** | Hand-maintained inventory in instance YAML (`observed_runtime`-style reality fields). | topology | ADR 0103 D1 forbids reality in instance YAML; stale by construction | **No.** Explicitly inadmissible |
| **M11** | Do nothing; rely on `terraform plan` and operator memory. | — | — | **No.** §3.9 rows 2, 3 and 5 are falsified by measurement; the Critical requirements stay unmet |

### 5.2 Options assembled from the mechanisms

| Option | Mechanisms | Answers "what will Terraform change?" | Achieves "no garbage"? | New live risk | Rough effort |
|---|---|---|---|---|---|
| **A — Prevention only** | M6a, M7 | no | no | none (offline checks) | small |
| **B — Visibility** | M1, M2, M3, M4 in `warn` mode | **yes, mechanically** | no — it makes garbage measurable and named | none (reports only) | medium |
| **C — Visibility + governed GC** | B + M5, M6b, M9, M4 in `delete` mode emitting a remediation script | yes | **yes, for everything with proof of ownership**; the sanctioned list defines the rest | real but bounded: deletion is scripted, proof-gated, counter-gated, run in safe mode by the operator | medium-large |
| **D — Golden config** | C + M8 | yes (trivially: everything is replaced) | **yes, by construction** | highest: reset + window + total coverage required | large |

### 5.3 Why each option is admissible or not, against STEP 2

* **A** violates nothing and closes P4(a) and P5 — the two defect *generators* —
  but leaves both Critical requirements unmet. Admissible only as a first
  increment, not as the answer.
* **B** satisfies the first Critical requirement in full and converts the second
  from unfalsifiable to measured. It respects determinism because the live call
  lives outside the pipeline (M3) and the pipeline consumes a file. It does not
  satisfy "no garbage" on its own.
* **C** satisfies both Critical requirements. Its admissibility depends entirely
  on M5: without the sanctioned-exception layer, "delete what is not planned"
  would have deleted the 46 unmarked objects of §3.5, including a rule carrying
  3.4 M packets and the vendor `defconf` set. With M5 plus the ownership proof
  and counter gates, deletion is confined to objects that are provably ours and
  provably idle — and the three traffic-carrying duplicates of §3.4 are, by that
  rule, *not* auto-deletable; they need the twin-reachability check of M6b
  first.
* **D** is the only option that makes "no garbage" true by construction rather
  than by reconciliation, and it is the one the project's own principle
  ("repeatable configuration from topology") implies as an end state. It is
  inadmissible until B/C report 100% coverage, because today the model provably
  does not describe everything the device needs.

### 5.4 Standing decisions this would touch

| Decision | Current status | What the options require |
|---|---|---|
| ADR 0103 D2–D12 | cancelled 2026-06-18 | B and C are a partial un-cancellation. The cancellation rationale needs amending against §3.9 — honestly, as a revision with the measurements, not a silent reversal |
| ADR 0105 | Deferred | C's remediation step is state application; it either stays operator-driven (no 0105 dependency) or revives 0105 |
| ADR 0115 | Proposed, blocked on 0105 | M1's identity keys are the granular unit 0115 asks for; B would unblock part of it |
| ADR 0119 | Accepted, not implemented | M6 is a first qualifying backend check |
| ADR 0091 | `drift-report.json` is a stub | M4 gives it a real value, replacing `"drift_state": "unknown"` |
| ADR 0055 | Implemented | M5 extends its principle from `.tf` files to device objects |
| New diagnostics | — | allocate **E84xx/W84xx** (measured free, adjacent to the deploy bands); register before raising |

---

## STEP 6 — MODEL REBUILD

**Not entered.** Requires a decision on which option to implement. The
recommendation, for the record and not as an authorisation:

1. **A first** — small, offline, no live risk, and it stops the two defect
   generators from producing the next instance of this problem.
2. **Then B** — it is the mechanism that answers the question as asked, and it
   is a prerequisite for any safe cleanup. Its report is also the coverage
   measurement that D's admissibility depends on.
3. **Then C**, with M5 authored deliberately: each sanctioned exception named,
   owned and justified. The 46 unmarked objects of §3.5 are triaged in that
   step — model it, sanction it, or delete it — one at a time.
4. **D only after** C reports zero sanctioned exceptions of any consequence and
   full coverage, and in a planned window with a verified backup.

## STEP 7 — VALIDATION & COMPLIANCE

**Not entered.** The compliance matrix is produced against an implemented
option, not against a solution space.

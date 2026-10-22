# ADR 0120: Device Configuration Provenance and Ownership

- Status: Partially Implemented
- Scope note: D1-D9 implemented and enforced; D10 defers the remaining options behind measurable triggers
- Date: 2026-10-21
- Revised: 2026-10-22 rev 2 (SPC rebuild: three-signal model, generation re-baselining promoted to a decision, identity constraint recorded, the option ladder replaced by triggers)
- Related: ADR 0055 (manual Terraform extension layer), ADR 0074 (generator determinism),
  ADR 0080 (unified build pipeline), ADR 0083 (node initialization, drift vocabulary),
  ADR 0091 (readiness evidence, `drift-report.json`), ADR 0103 (runtime reconciliation status
  — D2–D12 cancelled), ADR 0105 (device state commit/rollback — Deferred),
  ADR 0110 (zone/VLAN mechanism), ADR 0114 (TAIGA identity),
  ADR 0115 (hash-based deploy idempotency — Proposed),
  ADR 0119 (firewall rule ordering contract — Accepted, not implemented)
- Analysis: [SPC analysis of this revision](0120-analysis/SPC-ANALYSIS.md);
  [the option-B wave plan](../docs/reports/2026-10-22-adr0120-option-b-implementation-spc.md),
  superseded in *sequencing* by D10 and kept because the plan itself stays valid
- Evidence: `docs/reports/2026-10-21-chateau-dead-rules.md` (§1–§6d, the live audit),
  `docs/reports/2026-10-21-device-config-ownership-spc.md` (the analysis behind rev 1)

---

## Context

The project's purpose is repeatable device configuration derived from topology.
Three things are needed for that and, when this ADR was first written, only two
existed: topology declared intent and Terraform applied it, but **nothing stated
which objects on a device the project claimed**. Ownership lived implicitly in a
free-text `comment` substring and in Terraform's private state file, with
nothing to join them against.

### The measurements that forced it

Read-only against `rtr-mikrotik-chateau`, 2026-10-21, state serial 912:

| | |
|---|---|
| live objects across ten resource families | 314 |
| tracked by Terraform state | 162 |
| **carrying a marker, unknown to Terraform** | **98** |
| unmarked and unknown (vendor `defconf`, manual, hand-made) | 46 |
| firewall rules below the chain's terminal drop | 63, all at 0 packets, **none** Terraform-owned |

`terraform plan` compares intent with Terraform's *memory*, never with the
device, so a plan reporting "no changes" coexisted with all of it. Two of
ws-nixos' WireGuard country exits could not pass a packet for an unknown period:
their Chateau-side rules existed only as hand-made rules placed below the
terminal drop, while the declaration that should have produced them sat in a
block no plugin reads.

### What changed on 2026-10-22, and why this ADR was rebuilt

Rev 1 was a four-rung ladder — prevention, then visibility, then governed
cleanup, then golden config — and it said in binding language that visibility
was the next increment. Implementing the prevention layer, and then revising the
marker twice, produced something rev 1 did not anticipate: **two signals the
device publishes for free that answer most of what the visibility layer was
for.**

A marker revision rewrites exactly the set the current state owns, so after one,
an older marker form *is* proof of non-ownership. And RouterOS already flags
`invalid: true` on any row it cannot apply. 108 unowned rows and 8 inapplicable
rows were named that way — with no ledger, no inventory artifact and no builder.

So the ladder's second rung is no longer the cheapest path to its own purpose.
The decisions below are restructured around the signals that exist, and the
remaining options are deferred behind triggers rather than scheduled.

### Why this is not simply ADR 0103 again

ADR 0103 designed a reconciler (D2.1) and a CLI (D2.2) and cancelled both,
stating that "`terraform plan` already solves drift detection for this
single-operator home-lab" and that there was "no risk from cancellation".
Measurement falsified three of its five grounds — all claims about *capability*.
Two survive, and they are claims about *proportion*: a dual-mode architecture is
overengineered here, and the economics must justify the cost. D10 keeps the
surviving half and discards the falsified half, which is the opposite of
repeating it.

---

## Decision

### D1. Provenance is three signals, not one

Every object on a managed device belongs to exactly one provenance class, and
the class must be readable **from the device itself**, not only from the
repository:

| Class | How the device says so |
|---|---|
| `taiga` | the canonical marker in its comment |
| `manual` | the manual marker, with owner and date (D8) |
| `vendor` | RouterOS `defconf:` prefix, or `dynamic=true` |
| `garbage` | none of the above |

Three distinct signals are available, and **each proves something different**.
Conflating them is how a clean-looking census hid eight inapplicable rows:

| Signal | Proves | Blind to | Cost to read |
|---|---|---|---|
| the canonical marker | **origin**: TAIGA rendered this row, in this marker generation | whether current state still owns it | free, on the device |
| Terraform state | **ownership**: this exact row is managed now | every row it never created — 108 today | a local file |
| `invalid: true` | **inapplicability**: the device cannot apply this row | rows that are wrong but applicable | free, on the device |

Measured consequence of the first row's blind spot: three rows carried a marker
and were in no state at all — an earlier apply created them, their interfaces
were later recreated with new ids, and state moved on. **A marked row can still
be garbage.** The marker narrows the question from "whose is this?" to "ours —
but is it owned?"; only state answers the second part, and only the device
answers whether the row works at all.

### D2. One canonical marker, no synonyms

The marker is the suffix **`-Managed by TAIGA-`**, declared in
`configs/quality/device-provenance-policy.yaml`. A comment reads
`VPN-Sweden tunnel ingress -Managed by TAIGA-`.

**It credits the system, not the data.** TAIGA is the system that renders and
applies: the compilers, validators, generators and the six-stage pipeline —
*Topology Artifacts for Infrastructure Governance and Automation*, framework id
`taiga` (ADR 0114). "Topology" is the set of YAML files it reads. An object
exists on a device because TAIGA put it there, so `managed by Topology` credited
the input rather than the agent — and an operator reading a comment on a live
router wants to know what will overwrite it.

A delimited token rather than a trailing phrase, so the owned part is
unmistakable at a glance in Winbox and in `/export`, and unambiguous to parse.
Dashes rather than brackets because `-` is literal in a RouterOS regex, so
`comment~"-Managed by TAIGA-"` is an exact search; `[` and `]` open a character
class, which made the obvious search match almost every comment.

Five forms are retired and refused at validation time (`E8401`): the bracketed
predecessor, `managed by topology`, `managed by terraform`,
`managed by Terraform`, and a bare default. They stay in the policy forever —
D3 is why they are evidence rather than history.

*Enforced by `scripts/validation/validate_device_provenance.py` in the
`validate-v5` lane, enforce mode.*

### D3. A marker revision re-baselines provenance, and that is a tool

Observed twice on 2026-10-22 and reproducible: an apply updates the rows the
current state owns and **cannot touch rows nothing owns**. So after a marker
revision,

> a row carrying an older marker form is a row the current state does not own —
> or a row whose pending change is more than a comment.

Measured on the plain → bracketed → TAIGA cutovers:

| Generation | Owned | Count |
|---|---|---|
| `-Managed by TAIGA-` (current) | yes | **198** |
| bracketed (lived ~2.5 hours) | — | **0** |
| plain (first generation) | **no** | **108** |
| plain (first generation) | yes | **7** |

The zero is the verification: the intermediate generation left no residue, so
both rewrites covered exactly the owned set and nothing else. The 7 are
resources whose pending plan carries more than a comment — two
`ip_dhcp_server_network` rows that also move `dns_server`/`netmask`, four
permits awaiting placement replacement, one inert override awaiting destruction.
That third class is itself a signal: *owned, and holding a change nobody has
decided to apply.*

Three decisions follow:

1. **Retired forms are never dropped from the policy.** They are the evidence
   that makes this comparison possible.
2. **The comparison is a named procedure**, not a trick someone rediscovers:
   render, plan, classify each change by the attributes it actually touches,
   apply the comment-only subset, then census the device by marker generation
   crossed with state membership. Commands recorded in
   `docs/reports/2026-10-21-chateau-dead-rules.md` §6c–§6d.
3. **A revision is a legitimate reason to rewrite comments on a device**, and
   the only one. It costs one apply of comment-only changes, verified by parsing
   `terraform show -json` rather than by reading a plan's prose.

### D4. Every rendered device object carries the marker, or its type is exempt for a stated reason

Exemption is per resource type, declared in data, with one of three reasons,
each verifiable:

| Reason | Meaning | Verified by |
|---|---|---|
| `no_comment_attribute` | the provider exposes no `comment` for this type | `terraform providers schema -json` |
| `singleton_settings` | a settings object, not a list item: it cannot be garbage, only drift in value | the resource's own semantics |
| `not_a_device_object` | creates no object on a device | the provider |

Measured on the `routeros` provider: 21 of 24 rendered types support `comment`.
The three that do not are `routeros_container_envs` (keyed by name+key),
`routeros_ip_dns` and `routeros_container_config` (settings singletons).

**For exempt types ownership is state-only** — the channel that is blind to
garbage (D1). 44 of 262 rendered resources sit in that gap. It is stated here so
it is known rather than discovered later.

*Enforced in the lane (`E8400`, `E8401`, `E8402`); result: 262 rendered
resources, 218 marked, 44 exempt, every one in exactly one verdict.*

### D5. "Garbage" has a definition, and part of it is evaluable today

```text
garbage = live - taiga - manual - vendor/dynamic
```

| Term | Status | Procedure |
|---|---|---|
| `live` | available on demand | REST read of the device's families |
| `taiga`, comment-bearing types | **evaluable** | generation comparison (D3) |
| `taiga`, exempt types | not device-readable | state only (D4) |
| `manual` | **not evaluable** | the registry does not exist (D8, deferred in D10) |
| `vendor/dynamic` | evaluable | `defconf:` prefix, `dynamic=true` |

So the predicate is evaluated far enough to name a concrete target set — 108
unowned rows and 7 inapplicable ones — and not far enough to assert emptiness.
The complement matters as much as the term: 46 live objects are unmodelled and
legitimate, including vendor rules carrying 7.8 M packets and one unmodelled
rule carrying 3.4 M. **Treating "not planned" as "garbage" would have deleted
them.**

### D6. A rendered permit must prove its placement

A chain that ends with a rule matching everything swallows whatever is created
after it. Every rendered permit in such a chain must prove placement by one of
exactly two means:

* **`place_before` the terminal rule** — a device-visible attribute; or
* **the terminal's own `depends_on` naming the permit** — Terraform metadata
  only, which fixes creation order and therefore device order while rendering no
  device change. This is the correct proof where `place_before` would create a
  dependency cycle.

Where the terminal is *conditional* (the input chain's drop matches only `!LAN`)
a later permit can still be effective, so the obligation is a warning: the order
is unspecified rather than wrong. Deny rules need no proof — only permits can be
stranded.

*Enforced in the lane (`E8410`, `W8410`); 28 permits proven, 5 that had none
fixed. Those five worked on the live router only because they were created
before the terminal drop existed; one stranded copy already sat in the dead
tail.*

### D7. A configuration-shaped declaration must name its consumer

A block named `firewall_rules`, `mangle_rules`, `nat_rules`, `policy_routes`,
`routing_rules` or `address_lists` speaks device configuration, and authoring one
is a claim that something enforces it. The instance must declare in data who
consumes each such block:

```yaml
config_block_provenance:
  mikrotik_config: object.mikrotik.generator.terraform
  chateau_routing: documentation
```

A named plugin must exist in some manifest. `documentation` is a legitimate
answer and the honest one for a block kept as description — but it must be said,
not assumed.

**What this proves and what it does not.** It proves a consumer is named and
exists. It does not prove the plugin reads that path, because no plugin declares
the instance-data paths it reads. The gap is real and stated; closing it is B4
in D10.

*Enforced by `base.validator.config_block_provenance` (`E8420`, `E8421`); 21
findings at introduction, all resolved.*

### D8. How a human records a hand-made change

A deliberate manual change is legitimate — ADR 0055 establishes that for
Terraform files and the same need exists on the device. It must be
*distinguishable*, which means marked on the device and registered in the
repository.

**On the device**, the comment begins with `manual:` and carries two required
tokens and one optional:

```text
manual: AWG proxy test egress owner=platform-owner since=2026-10-21 ref=docs/reports/2026-10-21-chateau-dead-rules.md
```

`owner=` — an exception without an owner is garbage with a comment. `since=` —
`YYYY-MM-DD`, so staleness is visible without asking anyone. `ref=` — optional,
strongly preferred.

A generated object must never carry this marker: it would read as a sanctioned
exception and be spared by the very reconciliation that owns it. *Enforced as
`E8402`.*

**In the repository**, a manual-exception registry carries one entry per such
object: device, family, identity, owner, reason, review date. Two consequences,
and both are the point: an object marked `manual:` on the device but absent from
the registry is **not** sanctioned, and an entry whose review date has passed is
reported. The intended lifecycle of every entry is removal — promoted into
topology, or deleted from the device. **The registry does not exist yet**
(deferred in D10); until it does, `manual` is an unevaluable term in D5 and
hand-made objects are tracked in the audit report instead.

### D9. Identity: the measured constraint on any matcher

Any mechanism, script or person that says *this live row belongs to that
rendered resource* must pick a key. Measured on the current artifacts and
device:

| Candidate key | Unique? | Evidence |
|---|---|---|
| Terraform `type` + resource name | **yes** | 262 rendered resources, **0** duplicate pairs |
| rendered comment text | **no** | **85 of 242** marked comments repeat — four address-list rows share `Zone: VPN Tunnel Zone (level=2)`, and the ADR-0110 R2 isolation rules repeat across zone pairs |
| live row `.id` | **unstable** | ids change on recreate; the orphans bound to the deleted interface `*36` are the proof |
| per-family match tuple | per-family | works for filter/mangle; address-list rows differ only by `address`; `ip_pool` by `name` |

So the only generic unique key lives on the rendered side and is **absent from
the device** unless written into the comment — the one free-text field a RouterOS
object has. Two usable strategies follow, complements rather than rivals:

* **identity in the marker** (`-Managed by TAIGA:zone_addr_vpn_tunnel_2-`): one
  generic rule for every comment-bearing type, turning live→rendered into a
  dictionary lookup with no state and no per-family code. Costs one more comment
  rewrite and ~20–30 characters per comment, against a RouterOS comment cap that
  is **not yet verified** (the longest live comment is 117 characters).
* **an identity function per family**: no device change, but one function per
  family, each needing its own evidence, and fragile exactly where rows are
  near-identical. Unavoidable anyway for the 44 exempt resources (D4).

Neither is adopted now (D10). This decision records the constraint so the next
attempt does not re-walk the two dead ends.

### D10. What is built, what is deferred, and what reverses the deferral

**Implemented and enforced** (2026-10-21/22): D1 as a model, D2, D3, D4, D6, D7,
D8's device half, D9 as a recorded constraint. Diagnostics E8400, E8401, E8402,
E8410, W8410, E8420, E8421 — registered before being raised, in the
measured-free E84xx/W84xx band, not the E81xx band ADR 0103 earmarked and the
workspace assembler has occupied since.

**Deferred**: the ownership ledger, the device-inventory artifact, the
reconciliation builder and the read-set declaration (B1–B5); the
manual-exception registry and governed deletion (C1–C4); golden configuration
(D). The plan for all of them is written and stays valid —
`docs/reports/2026-10-22-adr0120-option-b-implementation-spc.md`, ≈4–4½ days in
five waves.

**Why deferred, precisely.** Not because the need is gone — "no garbage" is
still unmet (D5) — but because the question that machinery existed to answer is
answerable today by D3 and `invalid`, the target set is already named, and the
hazards that make deletion dangerous are per-object facts a person checks
against stated gates rather than facts a builder discovers. Building it now
would put machinery ahead of a consumer, which is how ADR 0091's
`drift-report.json` came to report `"drift_state": "unknown"` for three years.

**The one piece worth building whenever convenient**: the inventory collector as
a plain script (B2 alone, ~½ day, deterministic, no device change, secrets
redacted at collection). It is the only part whose value does not depend on a
consumer, because it makes every future census reproducible by someone who was
not there.

**Triggers that reverse this deferral.** Each is measurable from data the
repository already produces; any one firing makes the plan the next increment:

| # | Trigger | Measured by |
|---|---|---|
| T1 | a second enforcer actually applies configuration | a second `security_matrix` scope with a resolving adapter and a non-empty rendered root |
| T2 | the unowned count grows again after a cleanup | the generation census, re-run: a rise proves a recurring flow rather than one-time residue |
| T3 | someone other than the operator must read device state — a CI gate, a second person, an audit | a consumer exists for the report, which is exactly what is missing today |
| T4 | golden configuration (D) becomes a goal | its gate needs a measured 100% coverage figure, which only the reconciliation produces |

Until one fires, the standing answer to "should we build the reconciliation
layer?" is **no**, and this decision is where that answer lives so it is not
re-litigated from scratch.

---

## Open work this ADR does not close

Named here because an unexamined open item is worse than a tracked one. None of
it is blocked on the deferred machinery.

| # | Item | Shape |
|---|---|---|
| 1 | Russia AWG tunnel: no handshake in 12 h+, `rx` frozen at 201780 while `tx` climbs, measured four times across 2026-10-21 | a service fault, and the only item here with user-visible impact |
| 2 | 7 rows RouterOS flags `invalid: true` | three guarded commands; the predicate is the device's own verdict, so none can match a row in force. The filter pair also unblocks the ws-nixos apply |
| 3 | 108 unowned rows, individually identified by marker generation | one-off cleanup under the D5 complement and the measured hazard gates |
| 4 | 7 held-back resources — two dhcp networks moving `dns_server`/`netmask`, four permits awaiting placement replacement, one inert override awaiting destruction | decisions, then an apply |
| 5 | ws-nixos routing policies rendered but unapplied | import the four out-of-band mangle rules or delete them first, then apply |
| 6 | `manual` is unevaluable until the registry exists (D8) | blocks asserting `garbage = ∅`, not finding garbage |

---

## Consequences

### Enforced today

* The lane fails on an unmarked or unplaced rendered object, on a retired marker
  form, on a generated object claiming the manual marker, and on a
  configuration-shaped block with no named consumer.
* `generated/` carries the marker on every comment-bearing device object; the
  device carries it on all 198 rows Terraform owns and can update comment-only.
* Comments were rewritten on the device twice. That is the cost of D3, and the
  reason D3 is a decision rather than an accident.

### Two limits found by applying D2 to a real device

**A provider defect blocked every `routeros_ip_address` update, and is now
patched locally.** RouterOS assigns VRF membership per interface (`/ip/vrf` holds
one builtin row, `main`, with `interfaces: all`), so `vrf` on an address row is
derived and its SET endpoint has no such parameter; the released provider
declares `vrf` Optional-not-Computed and sends it on every PATCH, so RouterOS
answers `400 unknown parameter vrf`. The effect was wider than markers: **no
attribute of any `routeros_ip_address` could be updated** on RouterOS ≥ 7.21.
Device: 7.24.5.

Upstream [issue #944](https://github.com/terraform-routeros/terraform-provider-routeros/issues/944)
is this symptom and is open;
[PR #984](https://github.com/terraform-routeros/terraform-provider-routeros/pull/984)
is the twelve-line fix and is open; the newest upstream tag is the pinned
v1.99.1, so no released fix exists. Resolved by building the pinned release with
that patch, with everything that decides the output tracked:
`configs/terraform/patches/`,
`scripts/terraform/build-patched-routeros-provider.sh` (which refuses a tag
resolving to an unexpected commit and asserts after patching that the fix
landed), and the binary in gitignored `.work/`. The script prints its own exit
condition: delete the patch when upstream releases above 1.99.1.

A second defect, recorded because any reconciliation inherits it: **the provider
persisted the intended comment into state even though the PATCH returned 400**,
so state claimed four addresses were updated while the device held the old text.
A plan reading state alone reported them as done. State is a record of what
Terraform believes, not of what is.

**A clamped-key phantom diff, now structurally impossible.** X25519 clamps three
bits of byte 0 and two of byte 31 before use, so a key and its clamped form are
the same key with the same public key; RouterOS stores the clamped form.
`amneziawg.sweden.client_private_key` was stored unclamped and differed from the
device in exactly bits 0, 1, 2 of byte 0, deriving the identical public key — so
every plan reported a `private_key` change on a live tunnel, and it could never
converge. A plan that always wants to rewrite a key teaches an operator to skip
past key changes, which is the one line that must stay readable. The stored
secret is normalised (same key, no rotation, verified by deriving the public key
both ways) and `scripts/terraform/generate-tfvars.py` normalises on the way out,
pinned by `tests/test_tfvars_wireguard_key_canonicalisation.py`.

### Deliberately not addressed

* No mechanism deletes anything. The gates for deletion are stated — ownership
  proof, packet counters, twin reachability, vendor markers — and are checked by
  a person.
* ADR 0103's cancellation of a *dual-mode* architecture is not reversed. The
  deferred plan builds one path.
* ADR 0105 stays Deferred: nothing here applies state, so no commit/rollback
  contract is required.

### Rejected alternatives

| Alternative | Why not |
|---|---|
| Keep the four-rung ladder and build visibility next | 4–4½ days and a third rewrite of 199 live comments for a question D3 already answers, with no consumer for the output |
| Cancel the remaining options outright, as ADR 0103 cancelled D2–D12 | three of 0103's five grounds were later falsified by measurement; a cancellation asserts a permanent claim, and the hazard numbers say the need returns with the next enforcer. D10 defers with triggers instead |
| Leave the sequencing decision in a session report | reports do not bind; this document does |
| Hand-maintained reality fields in instance YAML | ADR 0103 D1 forbids it, and it is stale by construction |
| Rely on `terraform plan` alone | measured blind to 98 of 314 live objects; the premise that failed |
| Live device reads inside `compile`/`generate` | breaks determinism and CI-safety (ADR 0074); the collector writes a file the pipeline would read |
| Delete everything not planned | would have deleted 46 legitimate objects, including vendor defaults and a rule carrying 3.4 M packets |
| A marker on every type without checking the provider | three types have no `comment` attribute; an unverified assumption fails at apply, not at validate |
| Match live rows by comment text | measured non-unique for 85 of 242 (D9) |

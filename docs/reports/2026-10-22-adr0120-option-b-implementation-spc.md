# Implementing ADR 0120 — SPC analysis and implementation plan

2026-10-22. Formal analysis under `docs/ai/spc-contract.md`, steps 0–5, followed
by an implementation plan. What this settles is **how** option B would be built,
in what order, and what each piece must prove.

> **Sequencing superseded the same day.** ADR 0120 rev 2 (D10) defers option B
> behind four measurable triggers: the two free oracles this analysis itself
> surfaced - marker generation comparison and `invalid: true` - answer the
> question B existed to answer, so building B now would put machinery ahead of a
> consumer. **The plan below stays valid and is the plan to execute when a
> trigger fires**; only "do it next" was withdrawn. The identity finding in §3.4
> and §5.1 became ADR 0120 D9 and binds regardless.

Procedural `GO STEP X` gating is suspended by standing operator instruction; the
content obligations are kept.

---

## STEP 0 — READ FIRST

**ALL MATERIALS READ.**

* ADR 0120 in full, including the four-option plan and the two limits recorded
  while applying option A to a live device
* ADR 0103 (the cancelled reconciler and CLI, with its five rationale points),
  ADR 0105 (Deferred), ADR 0115 (Proposed), ADR 0091 (`drift-report.json` as a
  required handover artifact), ADR 0114 (TAIGA identity), ADR 0119 (ordering),
  ADR 0080/0063/0065 (pipeline, microkernel, plugin API), ADR 0074
  (determinism), ADR 0055 (manual extension layer)
* `topology-tools/plugins/generators/artifact_contract.py` — the artifact plan,
  the generation report, and `compute_obsolete_entries` with its ownership proof
* `topology-tools/plugins/manifests/builders.yaml`, `validators.yaml`,
  `discoverers.yaml`; `topology-tools/plugins/builders/soho_readiness_builder.py`
* `schemas/` (14 schemas, including `artifact-plan.schema.json`; **no**
  `drift-report.schema.json`)
* `scripts/validation/validate_device_provenance.py`,
  `configs/quality/device-provenance-policy.yaml`,
  `topology-tools/plugins/validators/config_block_provenance_validator.py`
* this session's three reports:
  `2026-10-21-chateau-dead-rules.md` (§1–§6d),
  `2026-10-21-device-config-ownership-spc.md`,
  `2026-10-21-rtr-slate-track-conservation.md`

Measured live for this analysis (read-only REST, 20 resource families, plus
`terraform show -json` over two plans): the four marker/ownership censuses, the
identity-uniqueness measurement in §3.4, comment lengths, and the eight
`invalid: true` rows.

---

## STEP 1 — DOCUMENT MAP

| Document | Owner | Purpose | Binding requirement | Data used |
|---|---|---|---|---|
| ADR 0120 | architecture | provenance and ownership contract | D1–D8; option B is the next increment, gate: none | the whole plan |
| ADR 0103 | architecture | reconciliation status | D1 holds (topology = intent); D2–D12 cancelled, premise now falsified | the cancelled plugin/CLI design, its effort figures |
| ADR 0091 | product | readiness evidence | `drift-report.json` is required; today a constant | the stub to replace |
| ADR 0074 | architecture | generator determinism | identical inputs → identical artifacts; offline/CI-safe | the constraint that forces B2's file boundary |
| ADR 0080 / 0063 / 0065 | architecture | 6-stage pipeline, microkernel, plugin API | stage affinity; `consumes`/`produces` declared | where B1/B3/B4 attach |
| ADR 0119 | architecture | rule ordering | Accepted, unimplemented; D5 is its first qualifying check | device-side ordering (C4) |
| ADR 0055 | architecture | manual extension layer | a tracked exception layer is legitimate | the model for C1 |
| `artifact_contract.py` | framework | plan / report / obsolete detection | `planned`/`generated`/`obsolete`; delete needs ownership proof | the pattern B1 and B3 reuse |
| `builders.yaml` | framework | build-stage plugins | phase `verify`, orders 520–529; `finalize` at 530 | where B3 sits |
| `schemas/` | framework | artifact schemas | new machine-readable artifacts get a schema | B1/B3 outputs |
| device REST + tfstate | operator | reality and ownership | only state proves ownership; only the device proves existence | every census in §3 |

---

## STEP 2 — CONSTRAINTS REGISTER

| Stakeholder | Requirement | Criticality | Type | Verification | Source |
|---|---|---|---|---|---|
| Operator | Before an apply, see what TAIGA will create/change/destroy **and** what on the device nothing owns | **Critical** | Operational | a report artifact enumerating the classes, diffable | ADR 0120 D4, this request |
| Operator | No garbage on the device | **Critical** | Operational | live − planned − manual − vendor = ∅, machine-checked | ADR 0120 D4 |
| Operator | Nothing in force is ever deleted by a mechanism | **Critical** | Operational | ownership proof + counters + ordering checked per object before any removal | §3.5; three traffic-carrying duplicates measured |
| Project | `compile`/`generate` stay deterministic and offline | **Critical** | Governance | no network in the pipeline; identical inputs → identical bytes | ADR 0074; ADR 0103 D2.1 |
| Project | Stage affinity; `consumes`/`produces` declared | **Critical** | Governance | `task validate:plugin-manifests`, contract tests | CORE-004 |
| Project | No secret reaches an artifact | **Critical** | Legal | the inventory is redacted at collection; schema forbids key fields | CORE-006 |
| Project | New diagnostics registered before raised | Important | Governance | `test_diagnostic_code_registry` | error-catalog convention |
| Project | New machine-readable artifact carries a schema | Important | Governance | `schemas/`, validated in the builder | 14 existing schemas |
| Operator | Effort proportional to a single-operator lab | Important | Operational | each wave independently useful, each ≤ ~1 day | ADR 0103's cancellation reasoning |
| Operator | Live writes confirmed, reversible, one channel at a time | **Critical** | Operational | backup + safe mode; the classifier has been blocking batches all session | measured today |
| Project | The marker is the device-readable channel; state is the ownership channel | **Critical** | Governance | neither alone is sufficient — proven today | ADR 0120 D1 revision |

No Critical requirement is impossible. Two are unmet and are the subject of the
plan.

---

## STEP 3 — DIAGNOSTIC ANALYSIS

Facts and measurements only.

### 3.1 What option A left behind, exactly

| | |
|---|---|
| rendered resources under the policed root | 262 — 218 marked, 44 exempt |
| live rows carrying the current marker, owned | **198** |
| live rows carrying an older marker, **not owned** | **108** |
| live rows carrying an older marker, owned | **7** |
| live rows RouterOS flags `invalid: true` | **8** (1 removed, 7 remain) |
| live rows with no marker at all (vendor/manual/third-party) | ~46 (measured 2026-10-21) |

### 3.2 The three signals now available, and what each can prove

| Signal | Proves | Blind to | Cost to read |
|---|---|---|---|
| marker (`-Managed by TAIGA-`) | *origin*: TAIGA rendered this row, in this generation | whether the current state still owns it | free, on the device |
| Terraform state | *ownership*: this exact row is managed | anything it never created — 108 rows today | a file |
| `invalid: true` | the device *cannot apply* this row | rows that are wrong but applicable | free, on the device |

No single signal answers "is this garbage". The marker plus state does, for
comment-bearing types; `invalid` is a cheap true-positive on top.

### 3.3 What a marker revision proved about generations

Two rewrites on 2026-10-22 (bracketed, then TAIGA) each updated exactly the
owned set and nothing else: the intermediate generation left **0** residue.
A revision therefore re-baselines provenance — after it, an older form means
"not owned by current state" or "owned, but its pending plan is more than a
comment". That is a working oracle built from data already on the device.

### 3.4 The identity problem, measured

For a reconciliation to say *this live row is the one that resource owns*, both
sides need a shared key. Measured on the current artifacts and device:

| Candidate key | Unique? | Evidence |
|---|---|---|
| Terraform resource name (`type` + `name`) | **yes** | 262 rendered resources, **0** duplicate `(type, name)` pairs |
| rendered comment text | **no** | **85 of 242** marked comments are non-unique; 4 address-list rows share `Zone: VPN Tunnel Zone (level=2)`, and the ADR-0110 R2 isolation rules repeat across zone pairs |
| live row `.id` | unstable | ids change on recreate; `*36`-bound orphans are the proof |
| match tuple (chain + action + matchers) | per-type | works for filter/mangle; address-list rows differ only by `address`; `ip_pool` by `name`; needs a function per family |

So the only *generic* unique key exists on the rendered side and is absent from
the device — unless it is written into the one free-text field the device has.

### 3.5 What makes deletion dangerous, in numbers

| Hazard | Measurement |
|---|---|
| unowned rows that are **passing traffic** | 3 of 87 filter duplicates: 7.0 M, 3.4 M, 242 k packets, each sitting *above* its owned twin |
| unowned rows that are load-bearing and modelled nowhere | `AWG-Proxy Sweden Test WAN egress`, 3.4 M packets, no marker, no state |
| vendor rows that must never be touched | 11 `defconf:` rules, two carrying 7.8 M and 1.9 M packets |
| rows whose removal is provably inert | the 8 `invalid: true` rows, all 0 packets, each superseded |

### 3.6 Mechanisms already in the repository that B would reuse

| Mechanism | State | Reuse |
|---|---|---|
| `compute_obsolete_entries` (stale = existing − planned, ownership proof, `retain\|warn\|delete`, delete degrades to warn without proof) | implemented, in use at file level | the exact semantics B3 needs at object level |
| per-generator `artifact-plan.json` + `artifact-generation-report.json` + `schemas/artifact-plan.schema.json` | implemented | the shape and the schema convention for the ledger |
| build stage, phase `verify`, orders 520–529, `finalize` 530 | implemented | B3 attaches at 530-ish in `verify` |
| `soho_readiness_builder` writing `drift-report.json` with `"drift_state": "unknown"` and `jsonschema` validation available | implemented stub | B3 supplies the real value; a schema is missing and would be added |
| REST reads with SOPS credentials, 20 families | written ad hoc in this session | B2 formalises what already works |
| `validate_device_provenance.py` + policy data | implemented | B3 shares the policy file; no second vocabulary |

### 3.7 What blocks adoption of unowned rows (needed by C2)

`terraform import` is the sanctioned way to take an unowned row into state. Two
measured obstacles:

1. **The `vrf` provider defect** made every `routeros_ip_address` update fail
   until the patched build (ADR 0120). Import itself was unaffected, but the
   same class of schema-vs-device mismatch is what breaks adoption.
2. **The provider writes state on a failed apply.** After a 400, state claimed
   four comments were updated while the device held the old text. Any
   reconciliation that trusts state without reading the device inherits that
   lie — which is the argument for B2 existing at all.

### 3.8 Prior estimate, and what has changed since

ADR 0103 costed the reconciler plugin at 17 h and the CLI at 17 h, and
cancelled both. Since then: the GC semantics exist (§3.6), the REST reads exist
(§3.6), the policy vocabulary exists, the marker is a working generation oracle
(§3.3), and the premise behind the cancellation is falsified by 108 rows that
`terraform plan` cannot see.

---

## STEP 4 — PROBLEM CLASSIFICATION

### P1 — Identity is not expressible on the device. *Design gap.*

The only generic unique key (`type` + resource name) lives on the rendered side.
Comments — the device's only free-text channel — are **not** unique (§3.4). So a
reconciliation can today compute *how many* rows are unowned but cannot say,
for each one, *which rendered resource it corresponds to* without per-family
matching logic. Every other gap below inherits this one.

### P2 — Reality is still not an input. *Design gap, now the only blocker to B3.*

Nothing in the six stages reads the device. The collector exists only as ad-hoc
commands in a session transcript.

### P3 — "Garbage" is defined but not evaluable. *Governance gap.*

D4 states `live − taiga − manual − vendor`. `manual` has no registry (C1) and
`live` has no artifact (B2), so the predicate is well-formed and unevaluated.

### P4 — Ownership proof is per-type, not uniform. *Implementation gap.*

44 of 262 rendered resources are exempt from the marker (no `comment`
attribute, singleton settings, non-device). For those, ownership can only come
from state — which is exactly the channel that is blind to garbage.

### P5 — The deletion gates are known but unmechanised. *Implementation gap.*

§3.5 names four hazard classes with numbers. Each has a checkable rule
(ownership proof, packet counters, twin reachability, vendor markers) and none
is implemented.

| Problem | Kind | Blocks |
|---|---|---|
| P1 identity on the device | design | per-object reconciliation (B3), adoption (C2) |
| P2 reality not an input | design | everything in B |
| P3 garbage not evaluable | governance | "no garbage" (C) |
| P4 proof not uniform | implementation | completeness of any census |
| P5 gates unmechanised | implementation | safe deletion (C) |

---

## STEP 5 — ADMISSIBLE SOLUTION SPACE

### 5.1 The identity fork (P1), which the rest depends on

| # | Mechanism | How it works | Admissible? |
|---|---|---|---|
| **I-1** | **Identity in the marker.** The generator stamps the logical name into the comment: `Zone: VPN Tunnel Zone (level=2) -Managed by TAIGA:zone_addr_vpn_tunnel_2-` | one generic rule for every comment-bearing type; live↔rendered becomes a dictionary lookup, no state, no per-family code | **Yes.** Costs a third comment rewrite (199 rows, procedure proven twice today) and ~20–30 chars per comment. Longest live comment is 117 chars; the RouterOS cap is **not verified** and must be measured with one probe write before committing |
| **I-2** | **Identity function per family** in the ledger (match tuple, or `name`, or `(list,address)`) | no device change; but a function per family, each needing its own evidence, and fragile exactly where rows are near-identical — the 4 identical address-list comments differ only by `address` | **Yes**, and unavoidable anyway for the 44 exempt resources |
| **I-3** | Match by comment text alone | measured non-unique for 85 of 242 | **No** |
| **I-4** | Match by live `.id` | unstable across recreate; the `*36` orphans are the counter-example | **No** |

I-1 and I-2 are complements, not rivals: I-1 covers the 218 marked resources
generically, I-2 covers the 44 exempt ones. Taking only I-2 is possible and
avoids a device rewrite; taking only I-1 leaves the exempt types unmatched.

### 5.2 Mechanisms for B

| # | Mechanism | Attaches | Notes |
|---|---|---|---|
| **B1** | Ownership ledger per generator: type, logical name, identity (I-1 token and/or I-2 keys), proof channel, declared placement | `generate`, beside `artifact-plan.json`, with a schema in `schemas/` | pure function of the compiled model; determinism preserved |
| **B2** | Device inventory collector → timestamped, redacted JSON at a known path | deploy domain script; **not** a pipeline plugin | the pipeline consumes a file, so ADR 0074 holds; redaction asserted by schema and test |
| **B3** | Reconciliation builder: ledger + tfstate + inventory → classes of D1, ordering facts of D5, `invalid` rows, and a real `drift-report.json` | `build`, phase `verify`, order ~530 | reuses `compute_obsolete_entries` semantics verbatim; `retain\|warn\|delete`; delete without proof degrades to warn |
| **B4** | Read-set declaration: plugins declare the instance-data paths they consume | manifests + `validate` | upgrades D6 from "a consumer is named" to "a consumer reads it" |
| **B5** | `invalid`-row class as a first-class finding in B3 | B3 | cheapest true positive; found 8 rows the marker census called clean |

### 5.3 Why each is admissible against STEP 2

* B1 touches no device and no network; it is the compiled model written down.
* B2 is the only network component and it sits outside the pipeline by design —
  that is precisely what reconciles ADR 0103 D2.1's determinism argument with
  D2.2's need for reality.
* B3 performs no writes. It emits a report and, in C2, a script.
* B4 is offline and closes an honest gap the validator's own docstring admits.
* B5 is free.

### 5.4 What stays out of B, deliberately

* No deletion (C).
* No `terraform import` automation (C2) — §3.7 shows adoption has its own
  failure modes and needs the inventory first.
* No golden config (D) — its coverage gate still fails.

---

## IMPLEMENTATION PLAN

Five waves. Each ends with something an operator can read, and each is
independently revertible. Effort is in half-days of focused work, not hours of
typing.

### Wave 0 — settle identity (prerequisite, ½ day)

| # | Task | Done when |
|---|---|---|
| 0.1 | Measure the RouterOS comment cap with one probe write on a scratch object, in safe mode | the cap is a recorded number, not an assumption |
| 0.2 | Decide I-1 (identity in the marker) vs I-2-only, in ADR 0120 as a D2 revision | the ADR states the identity contract and its cost |
| 0.3 | If I-1: extend the policy with the identity token's grammar and the regex-safe form | `validate_device_provenance.py` enforces the token's presence |

**This is the one gate that needs the operator**, because I-1 implies a third
rewrite of 199 live comments. Everything after Wave 0 is independent of the
answer except the matcher's input.

### Wave 1 — ownership ledger (1 day)

| # | Task | Done when |
|---|---|---|
| 1.1 | `schemas/ownership-ledger.schema.json` | schema committed, validated in tests |
| 1.2 | Emit the ledger from `artifact_contract.py` helpers so **every** generator gets it, not just MikroTik | `generated/artifact-contracts/<plugin>/ownership-ledger.json` exists for each |
| 1.3 | Per-family identity keys (I-2) for the exempt 44 and as a cross-check for the rest | each family either has keys or is recorded as unmatchable, with a reason |
| 1.4 | Declared placement per rendered rule (reuse the D5 logic already in the validator) | the ledger carries what the validator proves |
| 1.5 | Contract tests incl. determinism (two runs, identical bytes) | tests pass |

### Wave 2 — device inventory (1 day)

| # | Task | Done when |
|---|---|---|
| 2.1 | `scripts/deploy/collect_device_inventory.py` — REST, SOPS creds, 20 families, `--out` | one command produces the file |
| 2.2 | Redaction: private keys, preshared keys, passwords, container envs holding secrets | a test asserts no value matching the secret patterns survives |
| 2.3 | `schemas/device-inventory.schema.json` + `collected_at`, device identity, RouterOS version, per-row `invalid`/`dynamic`/counters | schema validated by the collector and in tests |
| 2.4 | A committed **fixture** inventory for tests, redacted and small | B3 is testable offline with no device |

### Wave 3 — reconciliation builder (1–1½ days)

| # | Task | Done when |
|---|---|---|
| 3.1 | `base.builder.device_reconciliation`, `build`/`verify`, consumes the ledger + state paths + inventory path from config | manifest entry, contract test |
| 3.2 | Classifier: owned-and-present, owned-and-missing, **marked-but-unowned**, unmarked-foreign, vendor/dynamic, `invalid` | the six counts reproduce today's hand-measured numbers on the fixture |
| 3.3 | Ordering facts per chain, device-side (D5/C4 groundwork) | the terminal-drop position and anything below it are in the report |
| 3.4 | `drift-report.json` gets a real `drift_state` + a schema; ADR 0091's artifact stops lying | `"unknown"` is gone |
| 3.5 | Diagnostics `E843x`/`W843x` registered **before** raising; mode `warn` first | registry test passes; lane green in warn |
| 3.6 | Report artifact + a one-screen text summary for an operator | both emitted |

### Wave 4 — read-set declaration (½ day)

| # | Task | Done when |
|---|---|---|
| 4.1 | `reads` key in plugin manifests: instance-data paths a plugin consumes | manifests updated for the plugins that read config blocks |
| 4.2 | `config_block_provenance` upgraded: the named consumer must declare the path | D6's stated gap closed; the validator's docstring updated to match |

### Wave 5 — enforcement and hand-off to C (½ day)

| # | Task | Done when |
|---|---|---|
| 5.1 | Flip the reconciliation gate to `enforce` for the classes that are provably empty (owned-and-missing, `invalid`) | lane fails if they reappear |
| 5.2 | Record the measured garbage inventory as C's triage backlog, per object | C1 starts from data, not from a scan |

### Sequencing, gates and risk

```
Wave 0 (identity)  ──┬── Wave 1 (ledger) ──┐
                     │                      ├── Wave 3 (reconciliation) ── Wave 5 (enforce)
                     └── Wave 2 (inventory) ┘
                         Wave 4 (read-sets) — independent, any time
```

* Wave 0 blocks only the *matcher input*; Waves 1 and 2 can start immediately on
  the I-2 path.
* Nothing before Wave 5 changes a device; Wave 5 changes only CI strictness.
* Total ≈ 4–4½ days, against ADR 0103's 34 h estimate for less scope — the
  difference is the mechanisms that now exist (§3.6, §3.8).

### What this plan deliberately does not do

It does not delete anything, does not import anything, and does not touch the
seven held-back resources, the 108 unowned rows or the seven remaining
`invalid` rows. Those are C, and C starts when B can name every one of them.

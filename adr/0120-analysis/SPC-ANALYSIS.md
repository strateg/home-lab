# ADR 0120 — SPC analysis of the revision

2026-10-22. Formal re-examination of ADR 0120 after option A was implemented and
applied to a live device, under `docs/ai/spc-contract.md`. Steps 0–7. The
operator authorised STEP 6 (rewrite the ADR), so this analysis runs to
completion rather than stopping at the solution space.

Procedural `GO STEP X` gating is suspended by standing operator instruction; the
content obligations are kept.

The question this settles: **ADR 0120 was written when ownership was unreadable
from a device. It is readable now. What does the ADR say, and what does it stop
saying?**

---

## STEP 0 — READ FIRST

**ALL MATERIALS READ.**

* ADR 0120 as it stood (497 lines: context, D1–D8, the four-option plan,
  consequences, two recorded limits)
* ADR 0103 in full, including the cancellation of D2–D12 and its five rationale
  points — the precedent for deferring work in this repository, and for getting
  a deferral's premise wrong
* ADR 0091 (`drift-report.json` required, implemented as a constant),
  ADR 0105 (Deferred), ADR 0115 (Proposed, blocked on 0105), ADR 0114 (TAIGA),
  ADR 0119 (Accepted, unimplemented), ADR 0074, ADR 0055
* the implemented artefacts of option A: `configs/quality/device-provenance-policy.yaml`,
  `scripts/validation/validate_device_provenance.py`,
  `topology-tools/plugins/validators/config_block_provenance_validator.py`,
  the E84xx catalog entries, their tests
* the four device censuses of 2026-10-21/22, the identity measurement, the eight
  `invalid: true` rows, and both plan classifications via `terraform show -json`
* `docs/reports/2026-10-22-adr0120-option-b-implementation-spc.md` — the wave
  plan whose premise this analysis re-examines

---

## STEP 1 — DOCUMENT MAP

| Document | Owner | Purpose | Binding requirement | Data used |
|---|---|---|---|---|
| ADR 0120 (as written) | architecture | provenance contract + four-option ladder | D1–D8 binding; "Gate to B: none. B is the next increment" | the whole text, and that sentence in particular |
| ADR 0103 | architecture | reconciliation status | D1 holds; D2–D12 cancelled on a premise later falsified | the shape of an honest deferral, and the shape of a dishonest one |
| ADR 0091 | product | readiness evidence | `drift-report.json` is required | a three-year-old stub nobody consumed |
| ADR 0074 | architecture | determinism | offline, CI-safe pipeline | the constraint on any reality input |
| option A artefacts | framework | marker, placement, consumer obligations | enforced in the lane | the measured result: 262 resources, 218 marked, 44 exempt |
| device censuses | operator | reality | — | 198 / 108 / 7 / 8 (§3.2) |
| identity measurement | this analysis | can a live row be matched to a rendered one? | — | 0 duplicate `(type,name)`, 85 of 242 comments non-unique |
| the wave plan | this session | how to build option B | ≈4–4½ days, one gate | its own premise |

---

## STEP 2 — CONSTRAINTS REGISTER

| Stakeholder | Requirement | Criticality | Type | Verification | Source |
|---|---|---|---|---|---|
| Operator | Know what TAIGA will change and what on the device nothing owns | **Critical** | Operational | answerable today, by a documented procedure | original request |
| Operator | No garbage on the device | **Critical** | Operational | `live − taiga − manual − vendor = ∅` | ADR 0120 D4 |
| Operator | Nothing in force is deleted by a mechanism or a person acting on one | **Critical** | Operational | ownership proof + counters + ordering, per object | measured hazards (§3.5) |
| Operator | Effort proportional to a single-operator lab | **Critical** | Operational | each increment independently useful; no machinery ahead of a consumer | ADR 0103's surviving argument |
| Project | An ADR states decisions that bind, not intentions that decay | **Critical** | Governance | every decision either enforced by a gate or explicitly marked unenforced | ADR policy, CORE-007 |
| Project | A deferral names a falsifiable trigger | **Critical** | Governance | the trigger is measurable from data the repo already produces | ADR 0103's cancellation is the counter-example |
| Project | Determinism and offline CI | **Critical** | Governance | no network in `compile`/`generate` | ADR 0074 |
| Project | Diagnostics registered before raised | Important | Governance | registry test | error-catalog convention |
| Project | No secret in an artifact | **Critical** | Legal | secrets only via SOPS | CORE-006 |

**Critical requirement in tension:** "no machinery ahead of a consumer" against
"no garbage on the device". The resolution is the subject of STEP 5.

---

## STEP 3 — DIAGNOSTIC ANALYSIS

Facts only.

### 3.1 What option A actually delivered

| Obligation | Enforced by | Measured result |
|---|---|---|
| D2/D3 marker on every rendered device object | `validate_device_provenance.py`, lane, enforce | 262 resources: 218 marked, 44 exempt, every one in exactly one verdict |
| D5 placement proof for permits | same | 28 permits proven; 5 that had none were fixed; input chain made deterministic with no device change |
| D6 configuration-shaped block names its consumer | `base.validator.config_block_provenance` | 21 findings at introduction, all resolved; 10 instances annotated |
| D8 diagnostics registered before raised | catalog + registry test | E8400/E8401/E8402/E8410/W8410/E8420/E8421 |

### 3.2 What the device looks like now

| Class | Count | How it is identified |
|---|---|---|
| current marker, owned by state | **198** | `-Managed by TAIGA-` + present in tfstate |
| older marker, **not** owned | **108** | an older marker form is now proof of non-ownership |
| older marker, owned | **7** | owned, but pending plan is more than a comment |
| `invalid: true` | **7** (of 8; one removed) | the device's own verdict |
| no marker at all | ~46 | vendor `defconf`, manual, third-party |

### 3.3 The discovery that changes the ADR

A marker revision rewrites exactly the set the current state owns. Measured
twice on 2026-10-22 (plain → bracketed → TAIGA): the intermediate generation
left **zero** residue. Therefore, after a revision:

> an object carrying an older marker form is an object the current state does
> not own — or one whose pending change is more than a comment.

That was not designed. It was observed, and it is reproducible: it follows from
the fact that an apply updates owned rows and cannot touch unowned ones.

**Consequence.** The central question option B existed to answer — *what on this
device does nothing own?* — is answerable today, from the device alone, with no
ledger, no inventory artifact and no builder. 108 rows were named that way.

### 3.4 The second free oracle

`invalid: true` is the device's own statement that a row cannot be applied —
typically because it references an interface that no longer exists. Eight such
rows existed; the marker census called all eight clean. It needs no state, no
ledger and no interpretation.

### 3.5 What still makes any cleanup dangerous

| Hazard | Measurement |
|---|---|
| unowned rows **passing traffic** from above their owned twins | 3 rows: 7.0 M, 3.4 M, 242 k packets |
| live load-bearing rules modelled nowhere | `AWG-Proxy Sweden Test WAN egress`, 3.4 M packets, no marker, no state |
| vendor rows that must never be touched | 11 `defconf:`, two at 7.8 M and 1.9 M packets |
| provably inert rows | the `invalid` set: 0 packets each, each superseded |

### 3.6 The identity constraint on any future matcher

| Candidate key | Unique? | Evidence |
|---|---|---|
| Terraform `type` + resource name | **yes** | 262 rendered, **0** duplicate pairs |
| rendered comment text | **no** | **85 of 242** marked comments repeat |
| live row `.id` | unstable | the `*36`-bound orphans |
| per-family match tuple | per-family | works for filter/mangle; address-list rows differ only by `address` |

The only generic unique key lives on the rendered side and is absent from the
device unless written into the comment.

### 3.7 Cost and consumer of the planned machinery

| | |
|---|---|
| wave plan effort | ≈4–4½ days |
| device churn demanded by its first gate | a third rewrite of 199 live comments |
| consumers of its output today | none; the operator reads answers, not artifacts |
| precedent for an unconsumed report artifact | ADR 0091's `drift-report.json`, `"drift_state": "unknown"` since 2026 |

### 3.8 What the open work actually consists of

| Item | Nature | Would option B fix it? |
|---|---|---|
| Russia AWG tunnel: no handshake 12 h+, `rx` frozen | service fault | no — it would report it; already reported by hand |
| 7 `invalid` rows | one-off removal, 3 guarded commands | no |
| 7 held-back resources (2 dhcp networks, 4 replacements, 1 destroy) | decisions, then an apply | no |
| 108 unowned rows | one-off cleanup, target set already named | no |
| ws-nixos routing policies unapplied | import/delete prep, then apply | no |

### 3.9 The precedent, read carefully

ADR 0103 cancelled its reconciler on five grounds. Three were falsified by
measurement (`terraform plan` suffices; no risk from cancellation; the operator
knows what is deployed). Two were not: the dual-mode architecture was
overengineered for this lab, and the economics did not justify the cost. The
falsified grounds were all *claims about capability*; the surviving ones are
*claims about proportion*.

---

## STEP 4 — PROBLEM CLASSIFICATION

### P1 — The ADR's structure encodes a premise that no longer holds. *Design gap in the document.*

ADR 0120 is built as a four-rung ladder in which visibility (B) is the
prerequisite for everything, and it says so in binding language: "Gate to B:
none. B is the next increment." That was true when written. Since then two
oracles appeared that deliver the ladder's second rung's *purpose* without its
machinery. An ADR that keeps directing work toward B is directing it past a
cheaper answer the same ADR's own mechanism produced.

### P2 — The signal model in D1 is incomplete. *Design gap.*

D1 names four provenance classes and one channel (the marker). Reality has
three channels with different powers: marker = origin, state = ownership,
`invalid` = inapplicability. The ADR records the first and, since the
2026-10-21 revision, a note about the limit. It does not state the model.

### P3 — D4's definition is correct and partly evaluable, and the ADR does not say which part. *Governance gap.*

`garbage = live − taiga − manual − vendor` is well formed. Today, generation
comparison evaluates it for comment-bearing families; the `manual` term has no
registry; exempt types have no device-readable channel at all. The ADR presents
the definition as uniformly unevaluated, which understates what is available.

### P4 — The deferral risk is the mirror of ADR 0103's. *Governance risk.*

Deferring B without a falsifiable trigger would repeat 0103's error in the
opposite direction: there, the premise was a capability claim that measurement
later destroyed; here, the premise would be a proportion claim ("no consumer
yet") that circumstances can change silently. A deferral is only honest if the
condition that reverses it is measurable from data the repository already
produces.

### P5 — Identity is a standing constraint, not an implementation detail. *Design gap.*

§3.6 is a property of the system, true whether or not B is ever built: any
future matcher, script or cleanup must pick a key, and two of the four obvious
candidates are measurably unusable. This belongs among the decisions, where
someone will find it before re-deriving it.

| Problem | Kind | Effect if unaddressed |
|---|---|---|
| P1 ladder premise | design (document) | work directed at machinery past a cheaper answer |
| P2 signal model unstated | design | each reader re-derives which signal proves what |
| P3 evaluability unstated | governance | available capability looks unavailable |
| P4 deferral without a trigger | governance | ADR 0103's failure mode, mirrored |
| P5 identity not recorded | design | re-derived per attempt; two dead ends re-walked |

---

## STEP 5 — ADMISSIBLE SOLUTION SPACE

| # | Mechanism | Constraints | Admissible? |
|---|---|---|---|
| **M1** | **State the three-signal model as a decision**, with what each proves and what it is blind to | must match measurement exactly | **Yes.** Costs nothing; P2 and P5 close |
| **M2** | **Promote generation comparison to a named, documented procedure** — the marker revision as a deliberate re-baselining tool | needs the retired-form list kept forever (already in the policy) | **Yes.** It is the mechanism that exists; naming it makes it repeatable by someone else |
| **M3** | **Restructure the options: A implemented; the collector split out as the one cheap piece; B/C/D deferred with triggers** | each trigger measurable from existing data | **Yes** |
| **M4** | **Record the identity constraint as a decision** | — | **Yes** |
| **M5** | Keep the ladder as written and build B next | 4–4½ days, 199 more comment rewrites, no consumer | **No.** Violates "no machinery ahead of a consumer" while the Critical requirement it serves is already answerable |
| **M6** | Cancel B/C/D outright, as 0103 cancelled D2–D12 | — | **No.** Three of 0103's five grounds were later falsified by measurement; a cancellation asserts a permanent claim, and the hazard numbers in §3.5 say the need returns with the next enforcer |
| **M7** | Leave the ADR unchanged and keep the decision in a session report | reports are not binding; the ADR is | **No.** P1 is a defect in the binding document |
| **M8** | Build only the collector (inventory as a script, no ledger, no builder) | ½ day, deterministic, no device change | **Yes**, and it is the only part of B whose value does not depend on a consumer: it makes every future census reproducible without the operator |

### Why the resolution of the STEP 2 tension is M1–M4 + M8

"No garbage" stays Critical and stays unmet. What changed is that the *path* to
it no longer runs through machinery: the target set is already named, and the
hazards that make deletion dangerous (§3.5) are per-object facts a person checks
with the gates D7/C3 describe — not facts a builder discovers. So the ADR should
carry the signals, the procedure, the identity constraint and the triggers, and
should stop asserting that B is the next step.

---

## STEP 6 — MODEL REBUILD

Authorised by the operator. ADR 0120 is rewritten:

| Change | From | To |
|---|---|---|
| Signal model | marker only, plus a note on its limit | **D1**: three signals with a truth table (origin / ownership / inapplicability) |
| Generation property | an "unplanned benefit" in a consequences subsection | **D3**: a named decision — a marker revision re-baselines provenance, and retired forms are kept forever because they are the evidence |
| Garbage definition | uniformly unevaluated | **D5**: the definition, plus exactly which term is evaluable today and by what procedure |
| Identity | absent (lived in a session report) | **D9**: measured constraint, two usable keys, two dead ends |
| Option ladder | "Gate to B: none. B is the next increment" | **D10**: A implemented; collector optional and cheap; B/C/D deferred behind four measurable triggers |
| Operational backlog | scattered across three reports | a named section, because it is what is actually open |
| The two provider defects and the clamping finding | consequences | kept, unchanged in substance |

Decisions D2 (canonical marker), D4 (coverage or stated exemption), D6
(placement proof), D7 (consumer obligation), D8 (human marking) carry over with
their measurements intact. Nothing enforced today becomes unenforced.

## STEP 7 — VALIDATION & COMPLIANCE

| Requirement | Source | Met | How verified | If No |
|---|---|---|---|---|
| Know what TAIGA changes and what nothing owns | request | **Yes** | generation comparison, documented as a procedure in D3; four censuses reproduce it | — |
| No garbage on the device | D5 | **No** | 108 unowned + 7 invalid rows remain; the ADR states this as open, with the target set named | the operational backlog; C when a trigger fires |
| Nothing in force deleted by a mechanism | §3.5 | **Yes** | no mechanism deletes anything; the gates are stated and the hazards measured per object | — |
| Effort proportional | ADR 0103's surviving argument | **Yes** | the rewrite costs documentation; the only build left optional is ½ day | — |
| An ADR states binding decisions | CORE-007 | **Yes** | each decision marked enforced-by-gate or explicitly unenforced | — |
| A deferral names a falsifiable trigger | P4 | **Yes** | D10 lists four, each measurable from existing data | — |
| Determinism / offline CI | ADR 0074 | **Yes** | no new pipeline component; the collector, if built, writes a file the pipeline would read | — |
| Diagnostics registered before raised | convention | **Yes** | unchanged; no new codes in this revision | — |
| No secret in an artifact | CORE-006 | **Yes** | unchanged; the collector's redaction requirement is stated in D10 | — |

**No Critical requirement is unmet by this revision.** "No garbage" remains
unmet by the *system* and is now stated as such, with the work it needs named
and the target set enumerated — which is the difference between an open item and
an unexamined one.

# SPC review of ADR 0118/0119: acceptability, topology fit and cognitive load

Method: Strict Process Compliance, `docs/ai/spc-contract.md`, steps 0-7.
Baseline: branch `development`, HEAD `c788237e379a32150ad328b2596cf86678981edc`,
clean tree at the start of the review.
Subject: the architecture documents. No implementation exists, and none was
created. No topology, generator, deploy code, secret or device configuration was
touched at any step.

Question asked: is the proposal acceptable, does it fit the main characteristics
of the topology, and what cognitive load does it place on a human developer.

---

## 1. Answers first

**Acceptability.** The document is acceptable as an architectural contract, subject
to two acts only a person can perform: architecture acceptance (gate G0a) and
assurance owner assignment plus a tailoring record (gate G0b). Every in-document
constraint that can be satisfied by the document is satisfied after the rebuild
described in section 5. Strict-profile readiness is a separate question and the
answer there is no, unchanged and self-declared: gates G1-G8 are open, acceptance
scenarios A01-A23 are unclosed, and no backend is qualified.

**Fit with the topology.** Nine of the model's core characteristics are preserved
explicitly, six were preserved but left unstated and are now stated, and three
constitute real semantic change that the project must decide to accept. The three:
zone membership stops granting access, plan ordering moves from per-matrix to one
compiler, and address derivation generalizes from VLAN to address domain. None of
them contradicts an implemented ADR; all of them change what existing YAML means.

**Cognitive load.** Measured, not estimated. For a directly attached workload the
new shape is smaller than today: 6 authored key paths against 9. For a published
service with an explicit policy it is roughly three times larger: about 30 against
9, in three files instead of two, with six references instead of three. The
concept vocabulary grows from 15 to 62. Roughly half of the measured growth is
intrinsic to the problem and cannot be written away; the rest was presentation and
has been reduced.

---

## 2. Scope and evidence boundary

| Established | Not established |
|---|---|
| Document-level consistency, reference integrity, governance validation | Any runtime behavior, compiler, generator or backend property |
| Measurements of the current sources at the baseline commit | Live device state; no device was queried |
| That every recorded constraint has at least one admissible mechanism | That any mechanism has been implemented or tested |

All counts below come from direct inspection of the repository at the baseline
commit. Commands are listed in section 6.

---

## 3. Compliance matrix A: the document as an architectural contract

Scope: what the document itself can satisfy. 68 constraints were registered before
analysis; they are grouped here, with every Critical item that changed state listed
individually.

### 3.1 Constraints met by the document

| Requirement | Source | Met | How verified | If No, what must change |
|---|---|---|---|---|
| Class to Object to Instance preserved | CORE-003, ADR 0062/0071/0088 | Yes | ADR 0118 D1 states it; `validate:layers` PASS, 62/140/189 unchanged | — |
| Derived layers, not directory-selected | ADR 0102 | Yes | ADR 0118 D1 | — |
| Downward references only, no upward L2 to L5 | ADR 0088/0102 practice | Yes | ADR 0118 D4 | — |
| Six lifecycle stages and stage affinity | CORE-004, ADR 0063/0080/0086 | Yes | ADR 0119 D3; deploy explicitly outside the six | — |
| Generators render, never invent grants | CORE-002 | Yes | ADR 0119 D1 | — |
| Capability checks, never name matching | ADR 0106 | Yes | ADR 0118 D6 | — |
| Host defaults via the `@on` directive | ADR 0107 | Yes | ADR 0118 D2 | — |
| Secrets only through SOPS/age | CORE-006 | Yes | HA-09; ADR 0119 D7 forbids secrets in feedback | — |
| ADR governance updated with the change | CORE-007 | Yes | Register note added; `validate:adr-consistency` PASS | — |
| Validation claimed only with command evidence | CORE-008 | Yes | Section 6 | — |
| Generated outputs never edited | CORE-002, CLAUDE.md | Yes | `git status` shows no path under `generated/` | — |
| **R1-R6 behavior unchanged** | ADR 0110, Implemented | Yes | ADR 0110 body untouched; translation table asserts legacy semantics rather than altering them | — |
| **Legacy evaluation order preserved** | ADR 0110 section 2.2 | Yes | Now referenced in ADR 0118 D4.1; was unstated before | — |
| **M1-B, one matrix per enforcer** | ADR 0110 section 1.3 | Yes | Now stated in ADR 0119 D1; was unstated before | — |
| **Trust zone and VLAN separation** | ADR 0110 section 1.5 | Yes | Now stated in ADR 0118 D2; was implicit before | — |
| **Final drop-all and `E7854`** | ADR 0110 section 4.4 | Yes | Now stated in ADR 0118 D4.1 and ADR 0119 D4; was unstated before. *Erratum 2026-09-11: the number was wrong. `E7854` had belonged to storage media inventory since three months before ADR 0110 claimed it; the drop-all is `E7082`.* | — |
| **IP derivation `vlan_ref` plus `host`** | ADR 0111 | Yes | ADR 0118 D2 keeps the arithmetic; VLAN remains an address domain | — |
| **Canonical semantic keys** | ADR 0088 | Yes | Now referenced in ADR 0118 D1; was unstated before | — |
| **Cognitive load is a project criterion** | ADR 0043 | Yes | ADR 0118 D8 plus the migration plan's authoring budget make it measurable; it was an unverifiable claim before | — |
| Publication is delivery, never permission | ADR 0118 D1/D3 | Yes | Contract text and acceptance scenario A03 | — |
| Absence of publication is not proof of unreachability | ADR 0118 D3 | Yes | A06; authoring example 1 | — |
| Missing selectors are invalid, not wildcards | ADR 0118 D4 | Yes | Contract text; example 2.1 | — |
| Permit intersecting a mandatory deny blocks compilation | ADR 0118 D4 | Yes | A04; formal contract section 1 | — |
| No silent legacy-to-strict conversion | ADR 0118 D4 | Yes | Translation table; candidates never authorize, A22 | — |
| Authors do not write derived values | ADR 0118 D7 | Yes | Derived-field contract; A23; example 4 | — |
| One plan compiler owns ordering | ADR 0119 D1 | Yes | Contract text, now reconciled with M1-B | — |
| Precedence from execution semantics, not producer name | ADR 0119 D4 | Yes | Contract text; the joint review's counterexample stands unrefuted | — |
| Terraform order is not device order | ADR 0119 D4 | Yes | Contract text; read-back required | — |
| NAT and state do not mint permissions | ADR 0119 D5 | Yes | `SEC-NAT`; example 3 | — |
| Rollback never resurrects revoked grants | ADR 0119 D6 | Yes | Contract text; A17 | — |
| Blocking everything is not success | ADR 0119 D1 | Yes | `SEC-AVAIL` separate from `SEC-AUTH`; A15 | — |
| No DoD or STIG claim without a tailoring record | Assurance profile | Yes | Claim explicitly bounded; the profile says so itself | — |
| Gates precede instance migration | Migration plan | Yes | G1-G4 ordering restated; scope quantified | — |
| A working example exists for the reader | User requirement | Yes | Authoring examples document; migration plan section 2.1 | — |
| Coordination scope stated numerically | T-01, T-04 | Yes | Migration plan section 2C | — |
| Baseline pointer correct | U-06 | Yes | Updated to the freeze commit | — |

### 3.2 Constraints not met, with what must change

| Requirement | Source | Met | How verified | What must change |
|---|---|---|---|---|
| Accountable human authority approves boundary, baseline, applicability and residual risk | HA tailoring record, Critical | **No** | No tailoring record exists in the repository | A named person must produce it. Gate G0b. Not a document edit |
| Independent human acceptance of the architecture | ADR 0118 acceptance section, Critical | **No** | Recorded as "human review pending" | A named reviewer must accept or reject. Gate G0a |
| Named owners for HA-01 to HA-10 | Assurance profile, Critical | **No** | Roles are named, persons are not | Assignment by a person. Gate G0b |
| AI commit metadata on the resulting commit | CORE-009, Important | **No** | No commit created for this rebuild | Include `AI-Agent` and `AI-Tokens` when committing |

**Result of matrix A.** Every Critical constraint that the document can satisfy is
satisfied. The three unmet Critical constraints are external human acts, not
properties of the text, and each has an assigned gate. The Important one is a
commit-time formality.

---

## 4. Compliance matrix B: readiness of the strict profile

Scope: the system, not the document. This matrix is included because acceptability
of the contract is routinely confused with readiness to deploy it.

| Requirement | Met | Evidence |
|---|---|---|
| HA-01 deny by default with bounded grants | No | Not implemented |
| HA-02 coverage of east-west, host, tunnel, IPv6, accelerated paths | No | Proxmox generator is a stub, its matrix is disabled, all nine LXC resolve to `firewall: false` |
| HA-03 to HA-10 | No | Not implemented; owners unnamed |
| Any backend qualified | No | Self-declared: no backend has qualified |
| Gates G1-G8 | No | All open |
| Acceptance scenarios A01-A23 | No | Zero closed |
| Data available to author strict policies | No | 5 of 29 services declare ports, 3 declare a source restriction, 0 declare an owner |

**Result of matrix B: NO VALID SOLUTION for deployment.** This is not a criticism
of the proposal; it is what the proposal itself states. Approving the architecture
is not approving a rollout, and no green documentation check changes that.

---

## 5. What the review changed in the document

Seventeen findings were carried into the text. The full change record with the
preserved reference commit is in `adr/0118-analysis/SPC-REBUILD-2026-09-10.md`.
Summary by kind:

| Kind | Count | Examples |
|---|---|---|
| Unstated link to an implemented ADR | 6 | R1-R6 outcomes, evaluation order, M1-B, zone/VLAN separation, final drop-all, semantic keys |
| Unverifiable claim made measurable | 2 | Authoring surface budget; derived-field contract |
| Example defects | 3 | One literal used for two address domains, only a deliberately failing example existed, `driver` value outside the current enum |
| Missing mechanism | 3 | Derive-review-freeze for candidates, provisional diagnostic identity, quantified coordination scope |
| Governance | 3 | Gate G0 split into architecture and assurance, stale baseline pointer, rule pack synchronization |

Mechanisms requiring topology data, a backend property or a human decision were
deliberately not executed and are listed as open in the rebuild record. Nothing
was resolved by rewording.

---

## 6. Verification commands

| Command | Result |
|---|---|
| `check_adr_consistency.py --strict-titles` | PASS, 0 errors, 0 warnings |
| `validate_agent_rules.py --fail-on-warnings` | PASS, 20 rules, 12 packs |
| `generate_ai_layer_table.py --check` | PASS, layer table matches canonical source |
| `pytest tests/test_validate_agent_rules.py tests/test_agent_instruction_sync.py tests/test_agent_rule_map_schema_policy.py` | PASS, 9 tests |
| `task validate:layers` | PASS, 62 classes, 140 objects, 189 instances, 29 runtime edges |
| `validate_repo_hygiene.py` | PASS |
| `git diff --check` | PASS |

Not run, and therefore not claimed: full `task ci`, topology compile, plugin
suites, any backend or live test. This change is documentation-only.

---

## 7. Measurements

Counting method: instance files are `*.yaml` under
`projects/home-lab/topology/instances/`; a network block is a top-level `network:`
key, and its keys are counted one indent level below it; consumers are repository
files containing the token, excluding generated output; validator plugins are
manifest entries, not files in the validators directory.

Two values in an earlier draft of this report were file counts rather than the
quantity named: "declaring exactly two network keys" was 22 and is 21, and
"registered validators" was 55, the number of files in the validators directory,
against 52 manifest entries. Both are corrected here and in the supporting
documents.

| Measurement | Value |
|---|---|
| Project instances | 189 |
| Instance files with a network block | 25 |
| Of those, declaring exactly two network keys | 21 |
| Distinct network key names in instances | 12 |
| Services declaring ports | 5 of 29 |
| Services declaring a source restriction | 3 of 29 |
| Services with both | 2 of 29 (svc-mikrotik-ui, svc-mosquitto) |
| Services in the servers trust zone | 20 of 29, against 13 of 19 recorded in ADR 0043 |
| Authored policy override entries, whole project | 9 |
| Repository files consuming `vlan_ref` | 28, of which 8 are plugins |
| Validator plugins registered in manifests | 52 |
| AdGuard feature surface today | 9 key paths, 2 files, 3 references |
| Same feature, budgeted proposed shape | about 30 key paths, 3 files, 6 references |
| Same feature, fragments written inline without object reuse | about 38 key paths |
| Concept vocabulary, current versus strict | 15 versus 62 |
| Normative identifiers for an implementer | 51 |
| Numeric diagnostic codes, current versus proposed | 15 versus 0, provisional identity now defined |

---

## 8. Open items for a person

| Item | Gate | Owner needed |
|---|---|---|
| Accept or reject the architecture | G0a | Architecture reviewer |
| Name owners for HA-01 to HA-10, produce the tailoring record | G0b | Accountable authority |
| Decide whether the three semantic changes are accepted | G0a | Architecture reviewer |
| Collect flow data for the 26 services lacking ports or source restrictions | G5 | Service owners |
| Resolve the staged servers VLAN, the VIP inside the DHCP pool, the disabled Proxmox enforcer, the LXC firewall flag, the stale CIDR comment | G5 | Topology owner |
| Decide whether to split the overloaded servers zone | G5 | Topology owner |

None of these is blocked on further analysis.

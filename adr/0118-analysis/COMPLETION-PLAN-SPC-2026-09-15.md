# ADR 0118/0119 — Completion plan (SPC report)

Status: **analysis artifact**. Not an ADR, not an amendment, and not an
authorization to change anything.

Amended 2026-09-15 after review. The execution sequencing is superseded by
[implementation roadmap](IMPLEMENTATION-ROADMAP-2026-09-15.md), which carries the
path to G8; what stands here is the measurement record, the classification and the
NO VALID SOLUTION finding. Five factual defects found by that review are corrected
in place and listed in section 10. Produced under `docs/ai/spc-contract.md`
(Strict Process Compliance), steps 0-7, each gated on explicit approval.

Subject as stated by the requester: *"составить план для скорейшего завершения,
проанализировав ADR и код, дав оценку; сначала реализовать основные пункты,
потом частные случаи."*

Baseline: WSL repository `/home/nixos/workspaces/home-lab`, branch `development`,
HEAD `97f06ffde71ef46c0ac6bd3e72a504e8e6771a60`, working tree clean.
All figures below were measured on 2026-09-15 in the session that produced this
report. Nothing in the repository was changed to produce it.

Reference model preserved unchanged: [implementation plan](IMPLEMENTATION-PLAN.md)
rev 4a, its W01-W13 register, the G0a-G8 gates and the A01-A32 matrix of
[migration and acceptance](MIGRATION-AND-ACCEPTANCE.md). This report introduces no
new work identifiers; it assigns admissible mechanisms onto the existing ones.

---

## 1. Measurement record

Every number carries the command that produced it and the boundary it covers.

| # | Command | Boundary | Result | Time |
|---|---|---|---|---|
| R1 | `.venv/bin/python topology-tools/compile-topology.py` | whole `home-lab` project | `total=152 errors=0 warnings=2 infos=150` | - |
| R2 | `.venv/bin/python -m pytest tests -q` | the **whole** `tests` tree | **1 failed, 2551 passed, 17 skipped** | 977.53 s |
| R2a | `.venv/bin/python -m pytest tests/test_backend_specialization_boundary.py -q` | one file; independently reproduced by review | **1 failed, 6 passed** | 0.71 s |
| R3 | `task test:plugin-contract` | `tests/plugin_contract tests/plugin_api tests/kernel tests/test_plugin_registry.py`, `-n auto`, `--cov-fail-under=75` | 483 passed | 55.28 s |
| R4 | `.venv/bin/python -m pytest tests/netmodel -q` | 17 files, 301 `def test_` | 373 passed | 2.05 s |
| R5 | `.venv/bin/python -m pytest tests/plugin_integration/test_strict_admission_pipeline.py -q` | one file | 33 passed | 75.57 s |
| R6 | `task framework:verify-lock` | `verify-framework-lock.py --strict` | `Framework lock verification: OK` | - |
| R7 | `task netmodel:inventory` | real topology snapshot | attachments 24, publication candidates 0, blocked 29 | - |
| R8 | `task validate:error-catalog-sync` | `topology-tools` + `scripts` | **FAILED** (exit 1) | - |
| R9 | `task validate:artifact-parity` | - | **not run in this session** | - |

### 1.1 The one failure in R2

```
FAILED tests/test_backend_specialization_boundary.py::
       test_the_generator_side_specialization_debt_does_not_grow
```

The W07 budget is 17 top-level functions and 1565 lines in
`topology/object-modules/mikrotik/plugins/projections.py`. Traced by `ast` across
this cycle's own commits:

| Commit | Functions | Lines | Against 17 / 1565 |
|---|---|---|---|
| `3312ca0b` (the measurement the budget was set from) | 17 | 1565 | at the line |
| `e95f88fc` | 17 | 1565 | ok |
| `6d6ff63e` — W05 cutover | 17 | **1614** | lines breached |
| `b326cd19` — W05 oracle-side class selection | **18** | **1626** | both breached |
| `97f06ffd` — HEAD | **18** | **1626** | both breached |

The check is a deterministic static count, not a flake. It was in no selection run
after `6d6ff63e`, which is why the previously reported "2012 passed" and
"481/483 passed" did not include it.

### 1.2 R8 detail

| Figure | Value |
|---|---|
| Defined in catalog | 232 |
| Used in source | 467 |
| Synchronized | 193 (coverage 83.2 %) |
| UNDEFINED (used, not in catalog) | **274** |
| UNUSED (in catalog, not used) | 39, including `E7042`, `E7062`, `E7085`, `E7087`, `E7088`, `E7089` |
| CODE COLLISIONS | 25 |

No ADR 0118/0119 code is among the 274. `validate:error-catalog-sync` appears
nowhere in `taskfiles/ci.yml`, so it blocks no gate of this subject.

### 1.3 Structural facts

| Fact | Value |
|---|---|
| `netmodel/` | 16 modules, 3951 lines |
| `netmodel` tests | 301 `def test_`, 5368 lines |
| Core network/security plugins | 4 validators + 3 compilers, 4638 lines |
| MikroTik projection | 18 functions, 1626 lines |
| Plugins in the `mikrotik` object module | 2, both `kind: generator` |
| Path classes in `netmodel/path.py` | 7 |
| Path classes required by ADR 0118 D6 | 7 (IPv6 carried as a family) |
| Capability catalog entries | 303 |
| Fields on a catalog entry | 9: `title, summary, domain, layer, stability, adr_refs, alias_for, derived, vendor` |
| Typed records for requirement, offer semantic core, evidence annex, resolution/witness | **0** |

The catalog is an identifier-only registry and is not the place offers belong.
The gap is not a missing field on a catalog entry: it is that requirement, offer
semantic core, evidence annex and resolution/witness do not exist as separate typed
records anywhere. Registering the six missing identifiers in the catalog and
defining those record types are two different pieces of work.
| Instances in `projects/home-lab/topology/instances` | 189 |
| Service files | 29 |
| Files with a `network:` block | 27 (docker 9, lxc 9, routeros_container 6, devices 3) |
| Sources with `network_intent_version: 2` | **0** |
| `availability_requirements` declared anywhere | **0** |
| Security matrices | 2, with 4 + 4 override entries |
| Attachments / publication candidates / blocked | 24 / 0 / **29 of 29** |

Reasons the 29 publications are blocked, by frequency: no policy owner 29,
no source restriction declared 26, no ports declared 25, runtime target has no
attachment 7.

### 1.4 Where the strict chain is open, in code

| Link | State | Reference |
|---|---|---|
| Plan provenance | literal `"provenance": "legacy_shadow"` | `security_plan_compiler.py:162` |
| Strict-eligible scopes | literal `strict_eligible: list[str] = []` | `security_plan_compiler.py:154` |
| Stated reason | no approved bound permits; nothing in the topology declares an approver | `security_plan_compiler.py:166` |
| Approval producer | `Proposed; not accepted or implemented` | [proposal](../0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md) |
| Verified intent | digest computed; no strict-intent source exists (0 v2 sources) | section 1.3 |

### 1.5 Obligation coverage

| Obligation | Core plugin | Decides today | Missing input |
|---|---|---|---|
| SEC-AUTH | `security_plan` | yes | - |
| SEC-AVAIL | `security_plan` | yes; `unverified` on the real topology (`W7002`) | 0 declared `availability_requirements` |
| SEC-ORDER | `security_plan` | yes | - |
| Termination (independent) | `security_plan` (`E7096`) | yes | - |
| SEC-NAT | `security_obligations` (`E7086`) | failure only | the positive half is missing code |
| SEC-STATE | `security_obligations` | reports absent evidence | session inventory, active epoch |
| SEC-TRANSITION | `security_obligations` | reports absent evidence | previously applied plan, authorization envelope |
| SEC-PATH | `security_obligations` | reports absent evidence | path inventory and per-case demonstration |
| SEC-CAP | `security_obligations` | reports absent evidence | versioned offers; the catalog has none |

### 1.6 Acceptance coverage and evidence freshness

Acceptance cases named in tests (`grep` over `tests/**/*.py`): A14 once, A22 five
times, A24 four times, A26 once, A29 once.

**This is a citation count, not a coverage measure, and it is not used as one.**
A test that does not cite an identifier is not counted, so the figure is a lower
bound on citation and says nothing about whether the behaviour is tested. What the
matrix actually needs is the per-case record of section 8 of the roadmap -
applicability, scope, runnable test, required evidence level, result, digest,
freshness, reviewer - and no such record exists for any case today.
The TUC catalog holds `TUC-0001`..`TUC-0004`; none belongs to 0118/0119.

Of the seven regression layers required by [formal contract](../0119-analysis/FORMAL-CONTRACT.md)
section 6: layers 1-3 exist over the model, layer 4 exists in its first half only
(no real backend), layer 5 is model-level, layer 6 (fault injection) is absent,
layer 7 is blocked by the missing offer vocabulary.

| Claim | Measured | Repeated at `97f06ffd` |
|---|---|---|
| Artifact parity, 163 files identical | 2026-09-14 | **no** |
| Live addresses reproduced by the strict resolver, 23 of 23 | 2026-09-11 | no |
| Address domains 11, all unshifted /24 | 2026-09-11 | no |
| Scopes admissible under the strict boundary, 0 of 2 | 2026-09-14 | no |
| W07 budget 17 / 1565 | 2026-09-14 | **yes - breached** |
| Full `pytest tests` | **2026-09-15** | 1 failed, 2551 passed, 17 skipped |

Six commits lie between HEAD and the last parity measurement: `b510035a`,
`bdc1374b`, `678d0463`, `b0a9d964`, `be81d696`, `97f06ffd`.

---

## 2. Classification

Eighteen findings were recorded and classified by nature, by blocking character
and by who can close them. The grouping is a classification of what was measured,
not a canonical decomposition of the remaining work; the roadmap's stage structure
is the one that governs execution.

| Nature | Items | Count |
|---|---|---|
| Governance | approval authority, assurance owners, trust contract, external review | 4 |
| Evidence | SEC-PATH demonstration, acceptance cases, regression layers, freshness | 4 |
| Implementation | SEC-STATE/TRANSITION channels, SEC-NAT positive half, W07, W05 divergence 3 | 4 |
| Data | v2 sources, availability objectives, 29 service authorings | 3 |
| Design | offer shape | 1 |
| Tooling | 274 unregistered codes | 1 |
| Regression | W07 budget breach | 1 |

| Who can close it | Count |
|---|---|
| Machine, inside this repository | 5 |
| Machine plus a human decision | 3 |
| Human only | 5 |
| Requires a real backend or device | 4 |

**This is not a capacity problem.** Five of eighteen close with code. The other
thirteen wait on a human decision, on absent source data, or on evidence that the
model cannot produce about itself by construction.

Two chains are open at their first link:

* strict: `approver -> approval -> intent -> strict provenance -> strict_eligible`
  is open at the approver, and the code says so rather than hiding it;
* capability: `offer shape -> catalog identifiers -> requirement/offer/resolution
  -> SEC-CAP -> A25-A32` is open at the offer shape.

---

## 3. NO VALID SOLUTION - recorded

For the scope **"complete the implementation of ADR 0118 and 0119"** there is
**no valid solution** under the constraints in force. The blocking constraints are:

* no self-declared closure of PR2, the strict boundary or G3 without outside review;
* no approval producer before the trust contract is agreed;
* evidence levels are kinds, not a ladder - an offline pass never closes a case
  whose terminal level is backend-tested or live-observed;
* no assurance claim without named HA owners and a tailoring record;
* G1-G4 precede any migration of instances.

The five goals with no admissible mechanism here are: strict closure of G2/G3;
G0b and G8; acceptance cases A26, A27, A28, A29, A31; regression layer 6 and the
second half of layer 4; and complete SEC-STATE, SEC-TRANSITION, SEC-PATH, SEC-CAP.

This is not a consequence of the chosen scope. It is a property of the constraints.

For the admissible subspace, a valid solution does exist, and it is section 4.

---

## 4. The plan

Main items are what closes without an external dependency *and* lies inside the
AD-09 base profile. Special cases are profile extensions and everything waiting on
a person or a device.

### T1 - Return measurement to truth (W05/W07, W13)

**T1.1 Bring the projection back inside the W07 budget.**
Removing `_row_class` alone gives 17 / 1614 - the function budget closes, the line
budget still misses by 49. The move that closes both:

| Function | Lines | Why this one |
|---|---|---|
| `_row_class` | 12 | class selection is core semantics |
| `_build_vlan_cidr_index` | 37 | a second derivation of `vlan_cidr_map`; the generator already consumes that channel from `base.compiler.security_matrix` |
| `_resolve_vlan_refs_to_cidrs` | 21 | same |
| **total** | **70** | result: **15 functions / 1556 lines**, both inside budget |

It also removes an A24 candidate violation: `vlan_cidr_map` is derived today both
in the compiler and in the projection.

Exit: `tests/test_backend_specialization_boundary.py` green, artifacts byte-identical.

**T1.2 Re-run artifact parity at the final HEAD.** Compile in a clean worktree
under `COMPILE_DETERMINISTIC_TIMESTAMP`, compare with
`scripts/validation/compare_artifacts.py`; the only declared exclusion is
`artifact-manifest.json`.

**T1.3 Refresh the measured figures** in [model operation](MODEL-OPERATION.md)
section 8, and record the diagnostic-code debt as external: 274 undefined,
39 unused, 25 collisions, the gate absent from `task ci`, no code of this subject
among the 274.

### T2 - The one obligation that lacks only code (W06)

**T2.1 SEC-NAT, positive decision.** Full parse of `nat` declarations under a
closed form; original identity keyed on effect, sources, destinations and
transport kind/protocol/ports; a mutant on each arm - two frontends collapsing
onto one backend rule must break the check, and a correct transform must pass it.
The algebra exists twice, so a differential against `netmodel/transform.py` is
required.

### T3 - Offline halves of the deferred obligations (W06)

**T3.1 A channel carrying the previously applied plan and the authorization
envelope.** SEC-TRANSITION keeps answering `unverified`, but for the reason
"no observed state" rather than "no input at all".

**T3.2 Derive the path inventory from the model.** Lower bound is the 7 D6 path
classes crossed with the families and epochs in scope. Ranges are computed
arithmetically; no set is materialized. `coverage_gaps` keeps taking
`demonstrated` as an argument - an inventory is not a coverage claim.

### T4 - W07, specialization onto the compile stage (predecessor of G4)

**T4.1 One function at a time, with artifact parity at every step,** in the order
the W07 decision declares. After T1.1 there remain 15 functions / 1556 lines; the
largest are `build_mikrotik_projection` 303, `_extract_security_matrix` 268,
`_extract_wireguard_tunnels` 191, `_extract_containers` 191, `_extract_wifi_config`
138, `_build_routing_policy_entry` 110, `_extract_mac_vlan_assignments` 104,
`_extract_bridge_vlans` 99. The target is a compile-stage compiler plugin in the
object module, which today has two plugins, both generators.

Moving everything in one step is not admissible: 1556 lines pinned only by parity
would be traded for an unmeasured baseline.

### T5 - Vocabulary (W03)

**T5.1 Register catalog identifiers for the six known enforcement gaps** in the
vocabulary-debt table. The full offer shape is not a main item: it is G1 design
work, and SEC-CAP stays `unverified` until it lands. Until an identifier is
registered the requirement is unverified by construction - a missing-vocabulary
condition, reported separately from an absent path.

### T6 - Evidence whose terminal level is offline (W11)

**T6.1 A25, A30 (digest behaviour) and A32, plus completion of regression
layers 1-3.** These are the only cases whose terminal level is offline-validated.
A26, A27, A28, A29 and A31 are not included: a model result never closes a case
whose terminal level is backend-tested or live-observed.

### Special cases, deliberately excluded

| Item | Why deferred |
|---|---|
| Full offer shape in the catalog | G1 design work; unlocks SEC-CAP and A25-A32 |
| Migration of sources to v2, one scope with all its consumers | G1-G4 must precede it |
| Policy owners, ports and source restrictions for 29 services | 29 security decisions, one per service |
| `availability_requirements` | needs an owner of the availability objectives (G0b) |
| Complete SEC-STATE, SEC-TRANSITION, SEC-PATH, SEC-CAP | missing inputs and live observation, not missing code |
| AD-09 extensions: IPv6, dynamic identity, nested transforms, HA, multipath | AD-09 itself puts them in separate qualification |
| Regression layer 6 and the second half of layer 4 | require a device |
| Authoring-budget remeasurement | only meaningful once migration actually runs |

---

## 5. Handed to a person - this work does not produce these

| # | Decision required | Unblocks |
|---|---|---|
| H1 | The trust contract: source of authority, approver identification, prohibition of self-approval, pinning of the authority context, signed-decision format | the approval producer, then strict G2/G3 |
| H2 | Named owners for HA-01..HA-10 and a tailoring record | G0b, then G8 |
| H3 | An owner for the availability objectives, and the objectives | SEC-AVAIL |
| H4 | A scope decision for A26, A27, A28, A29, A31 and regression layer 6 - with an owner and a reason, and without marking them closed | an honest acceptance matrix |
| H5 | Outside review of the final HEAD; PR2, the strict boundary and G3 are not self-declared closed | acceptance of what was done |
| H6 | A scope decision if W07 is taken out of the first completion | an explicit deferral of G4 |

---

## 6. Estimate

The unit is an **iteration**: one focused change plus its verification. Each
figure carries its basis; none is a feeling.

| Track | Iterations | Basis |
|---|---|---|
| T1.1 | 1 | 3 functions / 70 lines; the receiving channel already exists and is consumed |
| T1.2 | 1 | two compiles plus a comparison; the instrument is closed (W13) |
| T1.3 | 1 | documentation; the figures are already measured |
| T2.1 | 2 | one arm of the decision, mutants, differential against `transform.py` (132 lines) |
| T3.1 | 2 | published record, `consumes`, channel tests |
| T3.2 | 2 | 7 classes x families x epochs, arithmetic, nothing materialized |
| T4.1 | **8** | 15 functions / 1556 lines at roughly 2 functions per iteration with parity each time |
| T5.1 | 2 | 6 identifiers plus wiring into the contract validator |
| T6.1 | 3 | 3 acceptance cases plus completion of layers 1-3 |
| **Total** | **22** | |

Wall-clock cost of the gates, measured in this session: `pytest tests`
16 min 17 s; `task test:plugin-contract` 55 s; `tests/netmodel` 2 s;
`test_strict_admission_pipeline.py` 76 s; one project compile per parity run and
two per comparison.

Verification regime: a narrow selection on every iteration; a full `pytest tests`
at track boundaries (after T1, after T4, on the final HEAD) - about five full runs,
roughly 80 minutes in that alone. Artifact parity after T1.1, after each T4.1
iteration, and on the final HEAD.

**This is not an estimate of completion.** Twenty-two iterations cover the
admissible offline subspace of section 4 and nothing else: not the special cases,
not H1-H6, and not the path to G8 that the roadmap lays out. A total figure cannot
be produced yet - there is no accepted target and version, no owners, no trust
bootstrap and no breakdown of the missing semantic checks. It is recomputed after
the baseline and G1/feasibility, per W-item, with human and device waiting counted
separately.

---

## 7. What will and will not be closed

| Gate | After this plan | What still holds it |
|---|---|---|
| G0b | not closed | H2 |
| G1 | still partial | offer shape; typed requirement/offer/resolution contracts |
| G2 | not closed | H1 - provenance stays `legacy_shadow` |
| G3 | closer, not closed | four obligations answer `unverified` honestly; SEC-NAT becomes two-sided |
| G4 | **not closed even with all of T4** | needs versioned offers and an integrated strict backend |
| G5 | not closed | 29 of 29 publications blocked; H3 and the per-service authoring |
| G6-G8 | not closed | require a device and H2 |

No plan closes these gates under the constraints in force. That is the record in
section 3, not a consequence of the scope chosen here.

---

## 8. Compliance

Forty-one Critical requirements were checked against this plan; none is unmet. The
full matrix is in the session record. Three Important requirements are not fully met:

| Requirement | State | What must change |
|---|---|---|
| Finish the reviews of `bdc1374b` / `d48543fd` and repeat the full gate on the final HEAD | **No** - the full run in this session is 1 failed, 2551 passed, 17 skipped | execute T1.1, re-run; the reviews are H5 |
| The authoring surface is measured | **No** | only meaningful once migration runs, i.e. after G1-G4 |
| Minimise the remaining volume | **Partial** - 22 iterations, 8 of them in T4.1 | reducible only by H6, which defers G4 explicitly |

---

## 9. Disposition of every finding

Nothing was dropped.

| Finding | Disposition |
|---|---|
| W07 budget regression | T1.1 |
| 274 unregistered codes, 25 collisions | T1.3, recorded as external debt |
| Provenance hardcoded `legacy_shadow` | H1 |
| 0 v2 sources | special cases, after G1-G4 |
| 0 availability requirements | H3 |
| No offer fields in the catalog | partly T5.1; fully a special case |
| SEC-STATE / SEC-TRANSITION inputs | offline half T3.1; the rest a special case |
| SEC-PATH inventory and evidence | inventory T3.2; evidence a special case |
| SEC-NAT one-sided | T2.1 |
| W07 not started | T4.1 |
| W05 divergence 3 (overlay as address domain) | special case - a source change, hence a scope decision |
| 27 of 32 acceptance cases untested | offline cases T6.1; backend/live H4 |
| Regression layers 4 (second half) and 6 | H4 |
| No HA owners, no tailoring record | H2 |
| Approval producer proposal unaccepted | H1 |
| Stale evidence at HEAD | T1.2 and T1.3 |
| 29 of 29 publications blocked | special cases - 29 decisions |
| PR2 / strict boundary / G3 not externally accepted | H5 |

---

## 10. Corrections after review, 2026-09-15

Five defects were found in the first version of this report and are corrected
in place above.

| # | Defect | Correction |
|---|---|---|
| 1 | The capability catalog was treated as an offer store, so "0 offer fields" was reported as the gap | The catalog is identifier-only by design. The gap is that requirement, offer semantic core, evidence annex and resolution/witness do not exist as separate typed records - section 1.3 |
| 2 | Acceptance-case identifiers found by `grep` were carried into the classification as a coverage measure | It is a citation count and is no longer used as coverage. What the matrix needs is a per-case record; none exists - section 1.6 |
| 3 | The decomposition into eighteen gaps was presented as the structure of the remaining work | It is a classification of what was measured. The roadmap's stages govern execution - section 2 |
| 4 | The boundary of `task test:plugin-contract` was given as "plugin_contract + kernel" | The gate is `tests/plugin_contract tests/plugin_api tests/kernel tests/test_plugin_registry.py` with `-n auto` and `--cov-fail-under=75` - section 1 |
| 5 | Twenty-two iterations read as an estimate of completion | It covers the admissible offline subspace only. No total figure exists yet - section 6 |

Attribution of the measurements: R2 (`1 failed, 2551 passed, 17 skipped`) is this
report's own run and has not been independently repeated. R2a
(`1 failed, 6 passed` on the boundary file) was independently reproduced by review.

The architectural answers recorded by the roadmap - accept the signed L7 decision
contract with separately pinned authority; keep the self-approval prohibition;
identifiers in the catalog with offers and evidence as separate typed records;
W07 not excluded, the generator only renders; Q approved separately from permits,
observed traffic is review material and never a grant; one isolated RouterOS profile
as the first completion - are answers to H1, H3, H4 and H6 of section 5. H2 (named
owners) and the operator decisions on scope, on accepting the approval contract and
on an available lab with independent recovery remain open.

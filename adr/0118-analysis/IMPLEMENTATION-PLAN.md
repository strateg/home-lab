# ADR 0118/0119 — implementation plan

Status: reviewed implementation plan for the **Accepted** architecture, G0a closed
2026-09-10. Revision 4, 2026-09-11 (capability satisfaction amendment). **No implementation gate is closed by this plan.**
No topology migration, code change, secret access, live inspection or deployment
is authorized by editing this document.

Authority: [ADR 0118](../0118-universal-container-network-model.md),
[ADR 0119](../0119-firewall-rule-ordering-contract.md) and
[architecture rev 3.2](FINAL-ARCHITECTURE-PROPOSAL.md).
[Migration/acceptance](MIGRATION-AND-ACCEPTANCE.md) owns G0..G8 and A01..A32;
this plan assigns implementation work and evidence to those gates.
[Review findings](IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md) explain the corrections.

Capability amendment baseline: commit `493867d5`, branch development; revision 3
was clean before this documentation change. The earlier review baseline was
`966971f6`; the following runtime test results belong to that earlier review,
not a new execution for revision 4. Prior plans remain retrievable in Git.
The earlier `769457f5` reference is historical, not the current review baseline.
The previous plan cited an SPC cycle, but its I01..I41 issue register is not
present in the searched ADR-analysis/report files. This revision uses the complete
W01..W12 work register below; it does not invent meanings for the missing IDs.

## 1. Recommendations and fixed boundaries

| Decision | Recommendation / constraint |
|---|---|
| Planning unit | Keep gates, but distinguish prerequisites, concurrent preparation, gate closure and live authorization |
| Intent/plan production | Two core compiler responsibilities after effective_model; explicit backend specialization before validate, not hidden lowering at generate |
| First target | Recommend isolated RouterOS static-IPv4 qualification fixture; select exact version/provider/capabilities before G3 backend specialization. Not the production management router |
| Legacy behavior | Keep R1-R6 and current input semantics unchanged in a separate compatibility path; baseline defects get separate scoped fixes |
| Resource ownership | Preserve ADR 0057 Terraform ownership of RouterOS desired configuration and Ansible OS/service/runtime domain; orchestration is not a second writer |
| Bundle | Extend the existing versioned bundle manifest with a security section or a hash-bound referenced artifact; no independent parallel source of authority |
| G0b | Prepare in parallel; blocks assurance claims and closure/live execution of G6-G8. Pure schema/model and isolated controller simulation can proceed without claiming those gates closed |
| Capabilities | Derive requirements; resolve scoped versioned offers and evidence per ADR 0119 SEC-CAP. Reuse ADR 0106, no parallel registry or flag-as-proof |
| Estimates | No hours or fixed critical-path duration asserted without scoped deliverables and qualification results |

Historical [implementation exploration](FINAL-IMPLEMENTATION-PROPOSAL.md) is
not adopted wholesale. Its defect observations are review inputs, not an approved
backend/controller design. Choosing RouterOS here is an implementation
recommendation within the accepted architecture, not evidence it already qualifies.

## 2. Evidence baseline and limits

Historical targeted command at the earlier review baseline `966971f6`
(not rerun for this architecture amendment):

```bash
.venv/bin/python -m pytest \
  tests/plugin_integration/test_security_matrix_compiler.py \
  tests/plugin_integration/test_ip_derivation_compiler.py \
  tests/plugin_integration/test_generator_projection_contract.py -q
```

Result: **32 passed, 1 failed**, 3.62 s. The MikroTik projection-only test fails at
`topology/object-modules/mikrotik/templates/terraform/firewall.tf.j2:117`:
missing `runtime_baseline.firewall_baseline_rules`.
This is an existing baseline failure, not a new strict-profile test failure.

Source inspection confirms:
- effective_model is compile/finalize and the sole compiled_json owner, publishing
  `effective_model_candidate`;
- instance_data/resolved lineage do not establish complete field-level provenance
  for every object default and @on expansion; provenance is an explicit W04 deliverable;
- current bundle manifest has version, source hashes and nodes, not the proposed
  security intent/plan/evidence closure.

The prior probes of list replacement, numeric IP limitations and mapping merge
remain [recorded evidence](FINAL-PROPOSAL-EVIDENCE-2026-09-10.md), not new runtime
results of this review. Existing /24 compatibility must be demonstrated in W01/W03,
not assumed from a helper's happy path.

A01..A32 are **unclosed**, not proven to have zero related test coverage.
No live backend is qualified. The former “43 files to change” estimate is removed:
there was no accompanying reproducible file list. Each W item must enumerate its
actual touched files before implementation; counts are not acceptance criteria.

## 3. Complete work register

Paths identify current seams or proposed locations, not permission to edit now.
Owners are roles; a human assignee must be recorded before execution.

| Work | Scope / source seams | Depends on | Gate / responsible role |
|---|---|---|---|
| W01 Baseline | MikroTik projection/consumer/template contract; targeted tests | None; isolated defect fix | Prerequisite, generator maintainer |
| W02 Contract unification | layer-contract + reference validator; remove duplicate relation semantics | Existing relation behavior captured; may prepare alongside W01 | G1, schema/runtime maintainer |
| W03 Schema and IP domains | L2/L4/L5 definitions, contexts, local keys, typed flows/diagnostics; requirement/offer/resolution contracts and ownership; catalog vocabulary and diagnostic-range registration | W02 canonical relation contract | G1 schema; G2 address semantics, schema owner |
| W04 Intent and provenance | Core compiler, source/default/@on provenance, domain resolution, candidate adapter; derive complete capability requirements | W03; effective-model and provenance channel contracts | G2, compiler maintainer |
| W05 Legacy projection parity | security_matrix channels and MikroTik projection integration | W01; characterize both existing derivations first | Prerequisite to backend cutover, generator maintainer. **Characterization done 2026-09-11: derivations diverge, cutover blocked** — see [W05 characterization](W05-ZONE-DERIVATION-CHARACTERIZATION.md) |
| W06 Plan and checker | Core plan, predicates/path/state algebra, capability composition/strategies, independent oracle and SEC-CAP validation | W04 and bounded capability requirements | G3, security/compiler owner |
| W07 Backend specialization/render | Versioned adapter offers, effective applicability, complete execution contexts and deterministic rendering; no negotiation in generate | W05/W06; target feasibility record | G4, backend owner |
| W08 Artifact/bundle closure | Existing bundle schema/manifest; security/offer/strategy/evidence digest closure and invalidation tests | Contract designed with W06; integrated with W07 | G4 offline closure, build/release owner |
| W09 Topology/flow inventory | Services, domains, leases, planned intents, zone conflicts, legacy VPN mapping | Inventory now; freeze only after W03/W04; migration requires G1-G4 | G5, topology/flow owner |
| W10 Transaction/recovery | Existing runner, owner-delegated operations, fresh effective-capability checks, journal, revocation, OOB/recovery evidence | W08; topology/ownership input and feasibility findings | G6, deploy/scope owner |
| W11 Conformance/TUCs | Unit/property/differential/negative/fault/live evidence; A25-A32 capability regressions and applicability matrix | Developed with W01-W10, not deferred until G7 | G7, test/qualification owner |
| W12 Assurance/qualification | HA owners, tailoring, threat model, Q objectives, risk review | Preparation now; G8 needs applicable completed evidence | G0b/G8, human risk owner |
| W13 Artifact determinism | Generator ordering and manifest/plan digest inputs; declared non-semantic fields | None; isolated defect characterization, then fix | Prerequisite to G4 closure, generator/build owner |

This is the complete local work-ID register. W13 was added on 2026-09-11 when
generation was found to be non-deterministic; it is a baseline defect like W01,
not a new capability. W items can span two gates when
schema and executable semantics have different closure evidence. No “twelve
independent items” claim remains.

### Work that is not an independent cleanup

- Typing/restricting control traffic depends on explicit flow requirements and
  W03/W06; do not alter legacy ICMP/established acceptance as a preparatory refactor.
- Changing a zone/domain, enabling missing containers or fixing a DHCP conflict
  can change exposure. Keep as reviewed W09 migration, not unconditional pre-gate work.
- Restrict new embedded local keys in the new schema only; do not rename existing
  instance IDs or change the global @on syntax as a shortcut.
- W05 must compare existing compiler and generator outputs. If they disagree,
  stop and classify a separate behavior change; do not force empty diffs by
  copying generator semantics blindly into the core.
- Capturing source inventory, test baselines and human owner assignments can start
  now; applying any of their proposed topology fixes cannot.

## 4. Runtime and dataflow contract

All new plugin inputs/outputs use depends_on/consumes/produces. Use the registered
snapshot/outbox/execution-envelope boundary, no global ctx mutation or hidden
filesystem reads, registry access or dynamic loading in new workers.
Default new execution mode is subinterpreter; use the existing framework result
adapter rather than inventing a competing envelope API. Discovery order remains
framework -> class -> object -> project.

```text
discover: backend capability/version descriptors + source metadata contracts
compile:
  existing capability catalog/packs + object-derived OS/firmware/capability inputs
  existing C->O->I / @on / effective_model (sole compiled_json_owner)
    -> core network_intent + derived capability requirements + source_map + candidate report
    -> core security plan authority
    -> backend-specialized complete candidate plan + scoped capability witnesses
validate:
  schema + semantic + capability + ordering/path/state obligations
generate:
  deterministic rendering of the validated backend plan
assemble:
  cross-artifact validation, plan/resource inventory, digest closure
build:
  immutable versioned bundle with validation/evidence references
deploy (outside compiler lifecycle):
  approved bundle -> guarded execution -> observed evidence
```

Exact proposed responsibilities/channels:

| Producer | Required input | Published output / timing |
|---|---|---|
| Core network intent compiler | base.compiler.effective_model / effective_model_candidate plus declared provenance/profile inputs | network_intent with capability requirements, source_map, candidate_report; compile/finalize after effective_model |
| Core security plan compiler | network_intent + capability/profile constraints | semantic_plan, obligation_inventory; compile/finalize after intent |
| Backend specialization responsibility | semantic_plan + versioned offers + declared effective context/owner inputs | complete backend_plan, guards/transforms/contexts, selected strategy and candidate capability witnesses; compile before validation |
| Validator | intent/requirements, complete plan/offers/witnesses, source map, profile | validation_evidence with SEC-CAP results per claim, bound to exact semantic/plan digest |
| Generator | backend_plan + successful matching validation evidence | artifacts + semantic/resource manifest, no new grant/order decision |
| Assembler/builder | artifact manifest, plan/evidence digests | validated security section of existing immutable bundle |

These names are proposed contracts, not registered APIs. Outputs consumed across
stages must use the declared pipeline_shared lifetime; stage_local data must not
be assumed available to later stages. Add serialization/lifetime/DAG contract tests. Backend specialization
may be an internal bounded core operation using declared backend semantics or a
separate compiler plugin; that decomposition is fixed when W06/W07 contracts are
written. It cannot occur only in a generator after the relevant validator ran.

Do not rely on ctx.compiled_json being assigned midway through compile: subscribe
to effective_model_candidate. Do not create an effective_model -> security plan ->
effective_model dependency cycle. Use the matrix's managed_by_ref to resolve its
enforcer; it is **not a field looked up on the enforcer itself**. The plan key
includes project, enforcer and execution context (routing domain, family, hook,
chain/scope); duplicate/conflicting ownership is an error.

Compilers may reject impossible normalization early. Validate independently checks
the emitted candidate; stage affinity does not prohibit compiler diagnostics.
Only successful validation releases runnable strict artifacts. Diagnostic and
unapproved-candidate reports may still be produced without becoming executable.

Field-level provenance must survive inheritance and @on: origin file/field,
effective owner/local key, applied defaults and host reference. If effective_model
alone lacks it, preserve it at the owning normalization stage and declare an
additional channel. Never fabricate a source_map by reverse-reading YAML in generate.

### Capability contracts and stage boundary

The [shared contract](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md) governs
the proposed channels above. Reuse capability_contract_loader and capability_compiler
ownership; extend their declared outputs as needed, not hidden catalog rereads or
a second OS/capability derivation. Discovery finds manifests/descriptors; typed
loading/resolution remains in the owning compile contracts. Concrete channel names
and payload schemas are a W03 deliverable, not APIs already present.

W04 derives core requirements from intent/profile; W06/W07 add strategy-specific
prerequisites without weakening them. Check bounded prerequisite DAGs and complete
path/state inventory independently from satisfaction. Never union all device flags.
Effective capability is a join of offers with placement/configuration and owner
operations, not a new independently authored source.

Two seams that revision 4 left unnamed (revision 4a). First, `discover_capability_preflight`
is the existing discover-stage plugin (it checks catalog/packs presence, publishes
`capability_preflight_ok`, raises `E7107`); offer and descriptor discovery extends
that declared plugin rather than adding a sixth capability plugin. Second,
`capability_derivation.py` holds the derivation helpers shared by the compiler and
the validator; a network path reuses them and must not fork a parallel copy.
`topology-tools/check-capability-contract.py` is a standalone ADR 0062 checker
whose default catalog path does not exist in the tree; it is not a seam here.

Vocabulary is a W03 deliverable with a hard ordering constraint. The catalog
reaches runtime as identifiers only — the loader publishes `catalog_ids` and
`packs_map` and reads no other catalog field — and the contract validator rejects
any class or object capability outside that set. So an offer cannot be modelled by
enriching `capability-catalog.yaml`, and every identifier that a requirement, offer
or A25-A32 test names must be registered in the catalog before it is referenced.
The [vocabulary debt table](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md)
lists which identifiers the known enforcement gaps still lack. Registration is
declaration only: it qualifies nothing and authorizes no generator or template change.

Separate expected configuration at each transition phase from observed current
state. An authorized planned enablement may be modeled offline; live preconditions
must be observed before the step relying on them. This does not permit assuming
that a currently disabled feature is already effective.

## 4A. Diagnostic and feedback contract

ADR 0119 D7 is normative and had no owner in revision 2. Every blocking
diagnostic and change review emitted by the new path carries:

```text
source reference + field -> requirement ID -> concrete flow/path witness
-> expected vs observed verdict -> minimal source fix -> reproducer/test
-> intent/plan digests + tool/backend versions + evidence scope
```

| Element | Owning work | First gate that must produce it |
|---|---|---|
| Source reference and field, resolved through provenance | W04 | G2 |
| Requirement ID, semantic and allocated numeric | W03 | G1 |
| Flow or path witness for an authorization verdict | W06 | G3 |
| Expected versus observed, with evidence level named | W06/W11 | G3 |
| Minimal source fix and runnable reproducer | W06/W11 | G3 |
| Intent, plan and evidence digests plus tool/backend versions | W08 | G4 |

Capability diagnostics additionally name requirement/offer/strategy, exact context,
failed or unknown condition, required evidence level and invalidation reason.
A message that only names a rule, a resource or a template line does not satisfy
D7. Reports label evidence as design, offline-validated, backend-tested or
live-observed; missing evidence reads not run or unsupported, never pass. Secrets
never appear in diagnostics, feedback or public manifests, and that redaction is
tested rather than assumed: it is an explicit W04/W08 regression, not a review habit.

An operator-facing explain path is a recommended convenience, not a gate
requirement. If one is added it consumes the same records; it must not become a
second derivation of authorization.

## 5. Gate deliverables and exit criteria

### Baseline prerequisite — W01/W05/W13

W01: decide which projection keys are required and which have defined empty
values; make producer/fixture/consumer agree. Required missing data fails clearly.
Exit: 33/33 targeted tests, including missing-key behavior; no StrictUndefined
disablement, weakened assertion or snapshot-only suppression.
**Done 2026-09-11** (`c26232d2`): contract declared on the consumer boundary,
optional keys given defined empty values, dhcp required once enabled and failing
with a named diagnostic; baseline reached 33/33.

W05: characterize compiler-versus-generator legacy projection differences, then
switch consumers to the canonical channel with **identical managed artifacts**
for the fixed source/versions. Compare normalized semantics and rendered content;
exclude only documented nonsemantic timestamps from hashes. If there is a real
behavior difference, separate and review it before advancing.
No strict semantics, source migration or producer ownership handoff is mixed into
this parity step. W01 is not a prerequisite for reading/designing W02-W04.

W13: two generations of identical sources differ in 4 of 147 emitted files.
Two causes, and only the first is benign.

`artifact-manifest.json` carries a `generated_at` timestamp and the SHA-256 of
`build/effective-topology.json` and `.yaml`, which embed timestamps of their own.
That is expected, but it means an artifact comparison is meaningless until the
declared non-semantic fields are excluded, and today no such list exists.

The three `.state/artifact-plans/*.json` files vary between runs, listing
different paths as obsolete. **Root cause found 2026-09-11.**
`topology-tools/plugins/generators/artifact_contract.py:324` computes the obsolete
set from a live scan of the output root, while sibling generators are writing into
that same root. Under parallel plugin execution what counts as already-present
therefore depends on scheduling. Measured over five runs of identical sources:
`object.orangepi.generator.bootstrap.json` took four distinct values, the mikrotik
and proxmox plans two each. With `--no-parallel-plugins` the three become stable
and only the timestamped manifest varies, which isolates the cause to the race
rather than to the generators' own logic.

The classification is also wrong, not merely unstable: a file another generator
has just written in this run is not an obsolete leftover of a previous one.

Candidate fixes, for the owner to choose:
snapshot the output root once before the generate stage and have generators
consume it, which fixes the race and makes "obsolete" mean what it says;
or derive the obsolete set from the declared artifact plans instead of the
filesystem, which is stronger and larger. Serialising the stage hides the race at
the cost of parallelism and is not a fix.

G4 exits on deterministic artifacts and differential tests. Neither is checkable
while the same input can produce two outputs, so this is a prerequisite to G4
closure rather than work inside it.

Exit: a declared list of non-semantic fields excluded from artifact comparison,
with the exclusion applied by the comparison itself rather than by reviewer
judgement; repeated generation of one source producing byte-identical output
outside that list, demonstrated over enough runs to catch an intermittent case;
the ordering dependence identified and removed at its source rather than papered
over by sorting the comparison.

**Closed 2026-09-11.** `scripts/validation/compare_artifacts.py` and
`task validate:artifact-parity` provide the comparison, applying the exclusion by
name and printing the justification with it. The artifact plans are deliberately
not excluded, so the symptom stays visible if the cause returns.

The race is fixed at its source. The orchestrator takes the artifacts inventory
when it builds the plugin context, before any stage runs, and generators consume
it instead of scanning the live output root. Five generations of identical
sources under the default parallel execution now differ in one file of 147, the
timestamped manifest, which is the declared exclusion.

The fix also corrected the classification, which is a content change and not
parity: the orangepi bootstrap plan listed 4 obsolete candidates in one run and 8
in another, all of them the mikrotik and proxmox generators' fresh output, and now
lists none. Those entries carried `action: warn` under the default; with
`artifact_obsolete_action` set to `delete` one generator would have deleted
another's output.

Not in W13: changing what any artifact contains. This is about the same input
yielding the same output.

### Known-broken baseline beyond W01

W01 measured one narrow suite and brought it to 33/33. The wider baseline is
worse, and recording it here keeps a later green run from being read as progress
it did not make. All of the following reproduce at `c788237e`, before any
implementation work in this cycle. All three are now closed; the section stays as
the record of what the baseline actually was.

| Symptom | Status |
|---|---|
| `tests/plugin_contract/test_plugin_level_boundaries.py`: hardcoded product name and private address in the mikrotik projection, 2 failures. Both were inside a docstring illustrating a return shape, not in logic | **Fixed 2026-09-11** by moving the example to documentation-reserved values. Artifacts verified unchanged |
| `tests/plugin_integration/test_session_compile_fixture.py`: 4 errors, the session fixture compiled without `--diagnostics`, so the effective-json owner resolved to disabled and the file it then read was never written | **Fixed 2026-09-11**; same trap as the netmodel snapshot task hit |
| `tests/plugin_integration/test_tuc0003_mikrotik_v2.py::test_generator_contains_topology_and_runtime_markers`: the test's own fixture declared VLANs without a `vlan_id`, and the payload carries no objects map to default it from, so the template correctly skipped them and the test then demanded them | **Fixed 2026-09-11** by declaring segment addressing on the fixture's instances. Generation was never at fault: the real artifact emits nine `routeros_interface_vlan` resources, one per non-native VLAN |

A suite selected narrowly enough will pass over any of these. Claims about test
state name the suites they ran.

The TUC entry was first written here as "no VLAN interfaces are emitted", read
from the assertion message rather than from the artifact. The artifact had all
nine. A failing assertion names what a test expected, not what the system does;
the artifact is the evidence.

### A second known-broken set, measured 2026-09-11 on the full suite

The three items above were found by running narrow suites. The first full run of
`tests` in this cycle - 1944 collected, 14:57 - found more, and none of it is in
the work register. It is recorded here for the same reason: so a later green run
is not read as progress it did not make.

**1918 passed, 4 failed, 9 errors, 14 skipped.** Each failure was checked against
a detached worktree at `93c0c2f7` without this cycle's declarations, and the two
sides are identical - `4 failed, 9 passed, 9 errors` on both. The declarations
introduce none of it.

| Symptom | Evidence |
|---|---|
| `tests/plugin_regression/conftest.py`: 9 errors. The session fixture runs the compiler, asserts `returncode == 0`, then reads `effective.json` - which was never written | Reproduced by hand: the identical command exits 0 with a clean compile (150 infos, 0 errors) and produces neither `effective.json` nor `diagnostics.json`, despite `--output-json` and `--diagnostics-json` being passed. **The third occurrence of the `--diagnostics` trap**, after the netmodel snapshot task and `test_session_compile_fixture.py`. A flag that silently disables two explicitly requested outputs is the defect; the fixtures are its victims. **Fixed 2026-09-11 at the source**: all 9 errors gone, `tests/plugin_regression` is 10 passed / 3 skipped |
| `test_compile_external_project_repo_root.py` (2), `test_init_project_repo.py` (1): a scaffolded external project compiles but emits no `generated/effective-topology.json` | Same at HEAD |
| `test_generate_tfvars_script.py`: rendered tfvars carry `wireguard_wg1_peers` but not the `wireguard_peers` the test demands | Same at HEAD. Whether the test or the generator is wrong is undetermined; naming it here is not a diagnosis |

The `--diagnostics` trap has now cost three separate debugging sessions. It is
worth fixing at the source - an explicit `--output-json` should either produce
the file or fail - rather than adding the flag to a fourth caller.

**Fixed 2026-09-11, as preparation for W06.** `--diagnostics` remains the master
switch, which is a defensible design; the indefensible part was the silence. An
explicitly given `--output-json`, `--diagnostics-json` or `--diagnostics-txt` now
enables writing on its own, detected by comparing against the parser's default so
the always-present defaults do not make the flag meaningless.

This was selected into the W06 preparation because it is the instrument that
verification uses: a plan compiler is checked by reading the diagnostics and the
effective model it produces, and a tool that accepts a path, writes nothing and
exits 0 makes every such check unfalsifiable. It also closed the nine
`tests/plugin_regression` errors outright - that suite is now 10 passed, 3
skipped - which is the second time this cycle that a tooling defect turned out to
be the cause of what looked like nine independent test failures.

Six tests pin both halves: an explicit path enables writing, the defaults do not.

### W02, re-measured 2026-09-11 — the duplication is not duplication

Selected into the W06 preparation because a plan built on two answers about one
relation is ambiguous before it is ordered. The measurement contradicted the
premise.

`declarative_reference_validator` was listed here as duplicating several
per-domain validators code for code. It does not. All seven domain registrations
- power source, network core, service dependency, dns, certificate, backup -
point at **one** entry, `declarative_reference_validator.py`, each configured with
its own `enabled_rules`. That is consolidation, and W02's "remove duplicate
relation semantics" was done before this cycle began.

The per-domain modules still on disk are **not** registered by any manifest and
never execute. They are retained deliberately as parity oracles: twelve tests in
`test_declarative_reference_validator_parity.py` run the legacy implementation
beside the consolidated one and require the same diagnostics - the same
arrangement this cycle used for `find_conflicts` and `_order_by_edges`. Deleting
them would delete the evidence that the consolidation preserved behaviour.

**What that exposed was a defect in this cycle's own instrument.** The collision
checker counted those oracles as second owners, so five collisions it reported
could not occur at runtime. It now excludes modules under `plugins/` that no
manifest registers; non-plugin modules stay in, because a library is live by
being imported. Collisions fall 30 to 25, with nothing added. Reporting a defect
that is not there is worse than not checking: it spends attention and hides the
real ones among it.

**What is genuinely open, and now decided.** A v2 attachment's reference lives at
`network.attachments.<key>.network_ref` - inside a collection. `reference_validator`'s
rule table is declarative, `namespace` plus `field` read as `row[namespace][field]`,
and cannot express that without traversal it does not have and a rule per record
key that does not exist until the source is read. It also splits VLAN and bridge
into separate rules with separate `target_classes`, while a v2 `network_ref` names
an *address domain* generalizing both (AD-04), so the split is the wrong shape.

The authority is therefore `base.validator.network_intent_schema`, through
`E7020`. Teaching the relation table collection traversal is a larger change that
buys nothing the model needs today, and running both would hand the plan compiler
two answers about one reference. A test fails if a second owner appears.

### SEC-CAP reference model, 2026-09-11: `netmodel/capability.py`

Selected into the W06 preparation because `SEC-CAP` (`E7089`) is one of G3's own
obligations and `E7042` was the last allocated code with no mechanism behind it.

The capability satisfaction contract's central claim is a chain of inequalities -
**declared support is not effective support is not evidence is not permission** -
and four refusals are structural rather than checked:

* **There is no fourth status.** `satisfied`, `unsatisfied`, `unverified`.
  "Not applicable" is a scope decision with its own type, so it cannot be returned
  where a status is expected and read as a pass.
* **Unknown is not unlimited.** An unstated bound is `Unknown`, a distinct value
  that raises on `bool()`. A `None` meaning "no limit" at every call site that
  forgets to check is how an unstated capacity becomes an infinite one.
* **An empty loop is not proof.** No applicable offer resolves to `unverified`,
  never `satisfied` - "no applicable offer" and "no incompatibility found" are the
  same silence and only one means anything.
* **A version label is not trust.** Offers carry a content digest, witnesses
  record the digest relied on, and two bodies for one identity and version is an
  error rather than a discovery-order preference.

`unsatisfied` and `unverified` both block, and stay distinguishable: one is a
demonstrated incompatibility with a source-level remedy, the other means nobody
knows. A test asserts a resolution can never be `satisfied` with no witness, which
is flag-as-proof written out. Another asserts the module has no vocabulary for
permit, grant, authorize, allow or accept: SEC-CAP is necessary and never
sufficient, and it cannot discharge SEC-AUTH, AVAIL, PATH, NAT, STATE or
TRANSITION on its own.

**`E7042` stays unimplemented, and now with a measurement rather than a shrug.**
The capability catalog holds 303 entries carrying `@capability`, `title`,
`summary`, `domain`, `layer` and `stability` - and no version, context selector,
limit, condition, evidence reference or content digest. They are dispatch flags.
Checking a publication mechanism against them would compare it to a membership
set, which is exactly the flag-as-proof that A26-A29 block and that the contract
rules out in one sentence: set membership alone cannot prove network semantics.

What has to exist first is the offer shape, and the contract puts that in G1:
schemas, metadata contexts and manifest channels registered before use. A test
pins the catalog's current fields and names what to do the day offer fields
appear in it.

27 tests; 232 in netmodel.

### W06 / G3 begins, 2026-09-11 — lowering, an independent oracle, and mutants

G3's own instruction shaped the decomposition: *"Use an independent reference
interpreter; do not make the generator and oracle share the same decision code
and call agreement proof."* So three modules, and the third does not know the
first exists.

`netmodel.policy` decides what the intent authorizes. `netmodel.lower` translates
grants and guards into ordered rules and decides nothing - re-deciding
authorization there would put one question in two places that could answer
differently. `netmodel.interpret` reads a plan and returns accept, deny or
unsupported, importing neither of the others, which a test asserts.

With them apart, the obligations become properties over a bounded enumerated flow
space rather than arguments: `Accept(R) ⊆ A_e` (SEC-AUTH), `Q_e ⊆ Accept(R)`
(SEC-AVAIL), and the two monotonicity claims - deleting a permit cannot enlarge
the accepted set, adding a deny cannot either.

**The mutants carry the weight.** The contract's §6.2 names them and they are
implemented: an accept-all plan must fail SEC-AUTH, an all-drop plan must fail
SEC-AVAIL while still satisfying SEC-AUTH. A checker that cannot fail a plan that
is definitely wrong says nothing about one that looks right. A separate test
refuses the vacuous case directly, because both obligations are subset claims and
the cheapest way for a subset claim to pass is for one side to be empty - the same
failure the address differential had when it read one field name wrong and
compared nothing.

**Three verdicts, not two.** `unsupported` is a real outcome, not a soft deny. A
plan with no terminal rule that matches nothing leaves the result to a backend
default the interpreter does not know; saying so is honest, and silently
returning deny would report a safe result for a rule set nobody understood.
Default-deny is a property of a backend, not of a rule list.

**The terminal deny is the plan's.** ADR 0119 D4 says so and the reason is
checkable: a terminal rule a template adds is one the plan cannot reason about,
while "is anything executable after the drop-all" is precisely what the plan has
to answer. It matches on endpoints alone, ignoring protocol and port, because a
terminal matching like an ordinary rule would leave the scope open on every port
the author did not list.

15 tests; 247 in netmodel.

**SEC-NAT, 2026-09-11: `netmodel/transform.py`.** A flow event now carries both
tuples the formal contract requires. The fields are the *current* coordinates -
what a rule matches at this point in the path - and `original` holds the
client-facing tuple, `None` when nothing has transformed it.

That split is the obligation: a rule matches current coordinates because that is
what a device does; authorization is decided on the original, because a
destination NAT changes where a packet goes and never who was allowed to send it.
A transform records the original rather than replacing it, and composing two
transforms keeps the first, since the client-facing tuple is a property of the
flow and not of the last hop that touched it.

**Two formulations were wrong and the tests said so, which is worth recording.**

The collapse detector first compared *current tuples for equality*. A destination
NAT preserves the source, so two flows from different zones to one backend never
become the same tuple - the comparison found nothing, and the scenario it was
written for was not the one the contract names. The real collapse is that **one
rule written in backend coordinates decides both flows and cannot see which
frontend authorized which**, so the grouping is by decision, not by tuple. The
function takes a `decided_by` callable and stays ignorant of how the decision was
reached, which keeps it from importing the algebra it is checked against.

The mutant was also overclaimed. It asserted that discarding the original hides
the collapse; it does not - the sources still differ, so the collapse is still
found, and what is lost is the client-facing tuple in the report, the thing an
author needs to know which publication to narrow. The real damage is a different
substitution, and that is now the mutant: decide authorization on where the packet
ended up rather than where it came from, and a flow the intent refused is
permitted by the rule that exists for a different one.

The end-to-end case is demonstrated rather than described: a rule emitted for a
published path but written in backend coordinates without the frontend's source
restriction accepts a direct flow, the interpreter accepts it correctly because
that is what the device would do, and the intent asked in its own coordinates
never permitted it. Reading only the interpreter calls this fine; reading only the
intent calls it impossible. The obligation is the comparison.

15 tests; 262 in netmodel. Still to come in W06: path and state algebra,
transition envelopes, and the capability composition `netmodel.capability` now has
a shape for.

**A framework lock is not reproducible from a commit alone.** A detached worktree
at `93c0c2f7` computes `sha256-f43ba202...` where the committed lock says
`sha256-baee680d...`, while the same revision in the main working tree matches.
Something inside `distribution.include` is therefore not tracked by git, so the
integrity hash depends on files a fresh clone does not have. This was found while
building the control run above and is unrelated to the declarations; it matters
because a lock that cannot be recomputed from source cannot serve as an integrity
check for anyone but the machine that generated it.

### G1 — Registered schema and reference contracts

W02/W03 deliver:
- versioned L4 attachments/access bindings, L5 publications, L2 policy/guard,
  route/tunnel/interface-transform schema and downward realization bindings;
- shared definitions without 14 independently maintained service-schema copies;
- versioned requirement/offer/resolution contracts: applicability, typed conditions,
  units/limits, evidence levels, ownership, provenance and unknown values; reuse
  catalog/packs and namespace ownership, no per-publication duplicate checklist;
- network_intent_version in explicit domain contexts, distinct from manifest @version;
- typed collection traversal, concrete-key error paths, one relation authority;
- local keys, disable/delete/rename semantics, inherited false/zero/empty cases;
- typed protocol/port/control-flow shape, explicit original/current match views;
- central **numeric diagnostic allocation with collision tests**, replacing the
  design-only NET-*/SEC-* provisional codes while retaining semantic requirement IDs,
  as required by ADR 0118 D7.

**Measured 2026-09-11: a declaration alone cannot close G1.** Thirty classes
declare `property_schemas`, and nothing in `topology-tools/` or `scripts/` reads
them; validators read object `properties`, which is data, not the class schema.
Registering a shape therefore constrains no instance: it neither breaks the
existing flat inputs nor enables the new ones. The enforcing consumer is the part
that makes G1 real, and it is missing rather than assumed. Declaring the shape
first is still worth doing, so that consumer has one definition to enforce rather
than one invented alongside it.

**Declared 2026-09-11, all three v2 shapes, one per owning layer.** Attachments on
`class.compute.workload` (L4); publications on `class.service` (L5); policies and
bindings on `class.network.firewall_policy` (L2). Each is tied by test to what the
reference model enforces: the local-key grammar to `netmodel.identity.LOCAL_KEY_RE`,
and the declared effect/activation pairings to `netmodel.policy._ALLOWED_MODES`
compared as sets, so a fourth mode cannot be added on one side alone. Artifact
parity was measured across all 147 emitted files before and after: identical,
which is the evidence that the declarations are inert rather than the assumption.

*L5 had no shared base.* The fourteen service classes used no `@extends` at all, so
there was nowhere to declare publications once. `class.service` was added as an
abstract base and the fourteen now extend it, following the pattern L1
(`class.peripheral`) and L4 (`class.compute.workload`) already use. This is what
the bullet above means by "shared definitions without 14 independently maintained
service-schema copies"; without it the requirement could not be met at all.

*A publication carries no source selector.* Not an omission to fill in later: a
publication is a delivery fact, contributing to C in `A = (P n C) \ D` and never
to P, and the guarantee is structural - there is no field in which to author who
may connect. Today's `security.allowed_from` on a service instance is precisely
that conflation, and migrating it to a policy binding is W09 source-migration work,
not a schema default.

**Measured 2026-09-11: class inheritance records lineage but does not merge.** The
compiler emits `lineage` (root-first) and `parent_class` on every class, and leaves
the parent's payload on the parent: `class.compute.workload.lxc` does not carry the
base's `network_intent_schema`, nor `class.service.proxy` the base's
`service_publication_schema`. A consumer that reads only the class an instance
names would therefore find no schema on any concrete workload or service. The
enforcing validator must resolve declarations along `lineage`. This is checked by
test against the compiled snapshot, so if the merge behaviour ever changes the
consumer is told rather than silently reading a stale assumption.

G1 exits on full positive/negative C->O->I fixtures and A21/A23/A25 schema portions.
Allocate SEC-CAP diagnostics centrally; E8020/E8021 keep their platform/bootstrap
meaning and must not be reused for network satisfaction failures.

**Numeric allocation done, 2026-09-11: `E70xx`/`W70xx`/`I70xx`.** 28 codes, each
tied to a rule the reference model enforces or an obligation the ADR 0119 formal
contract states; no reserved-for-later entries, which D7 rejects. `E70xx` was the
only hundred inside `E7xxx` unclaimed by source, catalog, ADR or documentation.

The collision check D7 required found more than the allocation needed:

| Finding | Measure |
|---|---|
| Codes emitted with no catalog entry | 274, against a governance rule requiring registration before implementation |
| Codes emitted with unrelated meanings by different modules | 30, of which 14 are inside `E78xx` |
| `E78xx` occupancy | 93 of 100. Nothing new goes there |
| The checker's own blind spot | `SCAN_DIRS` omitted the top level of `topology-tools/`, hiding every code the compiler itself emits - 4 unregistered and 11 collisions, including the `E7821..E7827` framework-lock family |
| `E7854` | Claimed by ADR 0110 for the final drop-all on 2026-06-22; held by `storage_media_inventory_validator` since 2026-03-24. The drop-all is now `E7082` |
| ADR 0110's validator table | Names five modules that do not exist; the checks live in `network_security_validator`, `security_matrix_compiler` and `ip_derivation_compiler`, two of which are compilers |

Two squatters were moved off eight codes the registry documents as belonging to
other owners: the manifest governance checks and the framework layout checks, now
`E3301..E3312` and `E3320..E3323`. Collisions fell 38 to 30 and unregistered codes
280 to 274, with none added. Two test suites had been asserting `E7801` for two
unrelated things.

Both ledgers are frozen in `tests/test_diagnostic_code_registry.py`: they may
shrink, they may not grow. Paying the remaining 274 by machine would fill the
catalog with titles nobody chose, so the debt is recorded rather than invented
away. Artifact parity across all 147 files was measured before and after: identical.

Still open in this area: `storage_l3_refs_validator` squats on `E7861..E7863`,
`E7865` and `E7866`, which ADR 0111 documents for IP derivation, and
`declarative_reference_validator` duplicates several per-domain validators code
for code. Neither is fixed here; both are named so the next change has a target
rather than a rediscovery.

**The enforcing consumer exists, 2026-09-11: `base.validator.network_intent_schema`.**
This is the part that makes G1 real; the plan's own measurement said a declaration
alone could not close it. One validator reads all three declarations - which is
why they were declared together first - and resolves each along class `lineage`,
because the compiler records lineage and merges nothing.

Authored shape per declaration: `network` for attachments, `publication` for
publications, `policy` for policies and bindings, each carrying `schema_version: 2`.
A block without that version but with a v2 collection is refused rather than
guessed at.

Enforced today: `E7001` undeclared key or property, `E7002` record key outside the
local-key grammar, `E7003` derived or forbidden field authored, `E7004` v1 keys
beside v2, `E7005` missing required field or malformed record, `E7006` absent or
unsupported version, `E7007` the validator's own prerequisite. `E7007` is separate
from `E7005` deliberately: "the check did not run" and "a field is missing" are
different facts, and a check that cannot run must not report as a pass.

Three copies of the local-key grammar now exist - `netmodel.identity.LOCAL_KEY_RE`,
the `key_pattern` in each class file, and the validator - and a test asserts all
three are the same string, so they cannot drift.

Evidence: 38 plugin tests executing through the registry, which is also the only
proof the plugin loads at all - a validator that emits nothing because it never
ran is indistinguishable from one that emits nothing because the sources are
clean. The tests build their context from the real class files rather than a
fixture copy, so the validator and the declaration cannot drift while the tests
keep passing. Artifact parity across all 147 files: identical. Every source in the
tree is v1, so the validator is correctly silent on it.

Two tests in `tests/netmodel/test_schema_declaration.py` were inverted rather than
deleted: they asserted nothing read the declarations, and now assert that something
does. "The consumer disappeared" is a failure worth being told about.

Method note. The artifact-parity compile ran without `--strict-model-lock` and so
passed while `tests/plugin_regression/test_plugin_output_determinism.py` failed on
a stale `framework.lock` - the class comments had been edited after the last lock
refresh. Parity and lock integrity are different claims; a green parity run says
nothing about the lock.

**Second pass: meaning across records, 2026-09-11.** Shape checking says a record
is well formed; it says nothing about whether it refers to anything real. The
validator now runs a second pass, and only when the first found nothing - one
mistake should produce one message, and cross-record checks over malformed
records report the first mistake again in a less useful form.

| Code | Rule | Exactness |
|---|---|---|
| `E7020` | An attachment names a modeled address domain | Exact |
| `E7022` | No two enabled attachments claim one host offset in one domain | Exact; a disabled record claims nothing |
| `E7023` | A static address needs a domain that declares a prefix | Narrow form only: the domain declares no prefix at all |
| `E7040` | A publication endpoint names an attachment on the workload its service runs on | Exact; the message lists what is declared there |
| `E7041` | No two publications claim one endpoint, protocol and port | Exact |
| `E7060` | Only permit/binding_only and deny/scope_guard | Exact |
| `E7061` | A binding names an existing permit; a guard cannot be bound | Exact |
| `E7063` | A permit does not overlap a mandatory deny, reported with a concrete witness | Exact |
| `E7064` | No unbound parameter on a guard; no empty resolved selector | Exact |

**Not implemented, and absence is the honest form.** `E7021` (one default route
per address family and routing domain) needs the family, which an attachment must
not author and which nothing yet derives; a per-workload "at most one" check would
be stricter than the rule and would reject a legitimate dual-stack source. `E7042`
needs capability resolution. `E7062` and `E7080`..`E7089` are plan-time
obligations belonging to a plan compiler that does not exist. A check that cannot
be right yet emits nothing, because a check that is silently wrong is worse than a
missing one - it is believed.

**The algebra exists twice, with a forcing function.** The plugin cannot import
`netmodel`: that package sits outside framework distribution deliberately, so an
external project would not have it. `E7063` is therefore implemented again inside
the plugin, and a differential test runs both it and `netmodel.policy.authorize`
over the same cases and requires the same verdict. Without that test the two
copies would drift and both would keep passing their own tests.

58 plugin tests. Artifact parity: identical across all 147 files. Determinism and
strict-lock compiles pass. The first run of the new pass failed five existing
tests whose fixtures were only shape-valid - they named a network no row declared -
which is the pass doing its job; the fixtures were completed rather than the check
weakened.

**Address domain resolution, 2026-09-11.** `E7021` and `E7024` are now
implemented, and `E7024` was registered before the code that raises it, as the
governance rule requires.

`E7021` is scoped by address family derived from the referenced domain's prefix,
and by a single implicit routing domain - nothing in the sources declares one,
measured: `routing_domain` appears nowhere except in this cycle's own
`derived_and_forbidden_here` list, and all eleven modeled domains are IPv4. That
makes the check exact now and exact when IPv6 arrives; it becomes too permissive
only if routing domains are introduced, which is the safe direction. The rejected
alternative - counting default routes per workload - would have been stricter
than the rule and would reject a correct dual-stack source. A family that cannot
be read is not a match for anything.

`E7024` refuses a host offset the prefix does not admit. **Building it found a
defect in the reference model**: `netmodel.domains.resolve_host` accepted any
offset inside the prefix, so offset 0 resolved to the network address and the top
offset to the IPv4 broadcast address, and it presented both as host addresses.
Neither is assignable; a model that derives an unusable address is worse than one
that refuses, because the error then surfaces on the device instead of in review.

The corrected range has four cases, all checked against the standard library's
own `hosts()`: a single-address prefix (/32, /128) admits offset 0 only; a
two-address prefix (/31 per RFC 3021, /127 per RFC 6164) admits both, because a
point-to-point link has no network or broadcast address to set aside; IPv4
otherwise gives 1..size-2; IPv6 otherwise gives 1..size-1.

The offset-versus-last-octet distinction is now covered by a test that only
passes if the difference is real: offset 300 is refused in a /24 and accepted in
a /16. A validator reading host as a last octet would treat both the same way.

**Method rule, learned expensively.** The range is computed, never enumerated.
`list(ip_network("2001:db8::/64").hosts())` asks for 2**64 addresses; running it
to compare implementations exhausted memory and took the machine down. Both the
helper and the differential test now say so in place, and the differential
compares chosen offsets arithmetically.

The address algebra exists twice for the same reason the policy algebra does -
`netmodel` is outside framework distribution - and has its own differential test
requiring both to give the same answer, including the same refusals.

69 plugin tests, 152 netmodel tests. Artifact parity identical across 147 files
(both sides counted, not assumed). Determinism and strict-lock compiles pass.

**Complexity, measured 2026-09-11.** The same mistake that exhausted memory on an
IPv6 prefix - materializing a structure that has a closed form - was present in
two hot paths. Both were measured before and after; neither changes any output.

*Plan ordering.* `precedence_edges` built the full edge set: inside one context
that is a complete bipartite graph (every mandatory deny before every permit)
plus a sink (everything before the terminal). 1,600 rules produced 230,400 edges
and took 2.18s. Two counters say the same thing - a permit waits on its context's
remaining denies, a terminal on its context's remaining non-terminals - so the
counters are kept and the edges are not built. 0.027s, **81x**, and memory falls
from an edge set to 0.3 MB. 3,200 rules now order in 0.05s, where the old path
would have built roughly a million edges.

Kahn's tie-breaking is preserved exactly, including across contexts, because
changing the emitted order would silently change plan identity. That equivalence
is a test, not an argument: 300 random inputs with mixed contexts, effects and
terminals are ordered both ways and the sequences compared. The general path
remains for caller-supplied edges, which have no closed form to exploit.
`verify_edges` has a counterpart, `verify_structure`, that re-derives each rule's
role and checks the same property in one pass rather than against a materialized
set.

*Conflict search.* `find_conflicts` compared every grant against every guard -
320,000 comparisons for 800 grants against 400 guards, most decided by the first
field. Guards are now indexed by protocol and by each source endpoint they name.
This is exact rather than heuristic because endpoints are opaque atoms: two
endpoint sets intersect only if they share a literal member, so a lookup by
member misses nothing, and the algebra still never infers containment between
endpoints. The index narrows what is examined; `intersect` still decides.

The gain scales with how well sources discriminate, and this is stated rather
than rounded up to an asymptotic claim. Measured at 800 grants: one shared source
0.60s (the full scan, and correct - those pairs genuinely must be checked), seven
sources 0.085s, a hundred 0.0066s, all distinct 0.0014s. Equivalence is again a
test: 400 random inputs, compared against the previous every-pair scan kept as
the oracle, conflict order included.

A guard on scaling accompanies each, asserting the shape of the growth rather
than a wall-clock number, which would only detect how fast the machine is.

### W04 / G2 — the legacy IP derivation, characterized 2026-09-11

G2 says to keep the old `ip_derivation` path and not to describe its known /23 and
shifted-/25 defects as an absence of defects. Measured rather than restated, in
`W04-IP-DERIVATION-CHARACTERIZATION.md`.

`_resolve_ip` does not compute an address. It splits the last octet off the CIDR
and appends the host number to what remains; the prefix length is carried into the
output and never used in the arithmetic, and the gateway is unconditionally `.1`
of the printed base.

Three failure modes, measured:

| Mode | Example | Result |
|---|---|---|
| Syntactically invalid output | `10.0.30.0/23` host 300 | `10.0.30.300` - not an address. The compiler's own range check uses `num_addresses - 2`, so 300 is legal in a /23 and the string is built |
| Address outside its own network | `10.0.30.128/25` host 10 | `10.0.30.10`. Valid IPv4, wrong subnet, no diagnostic, interface does not come up |
| Gateway outside its own network | any shifted subnet | `10.0.30.1` for a `10.0.30.128/25` network |

And one case that is **not** a defect: on a shifted subnet the legacy answer can
land inside the network and still mean something else, because legacy reads
`host` as a last octet and the target model reads it as an offset. Both are
coherent readings of a v1 source, which is why ADR 0118 states the offset meaning
explicitly rather than leaving it implied - and why migrating a shifted subnet is
a per-source decision, not a mechanical rewrite.

**The defect is latent, not absent.** All eleven address domains are unshifted
/24s, where last-octet and offset arithmetic agree exactly. The legacy path is not
working; it is indistinguishable from working on the only shape present.

So: nothing in `ip_derivation_compiler` was changed. There are no output deltas to
review while every domain is an unshifted /24, and the plan requires legacy repair
to be its own reviewed change. Added instead are a characterization test pinning
every measured row, and a guard that fails the moment a source introduces a
non-/24 or shifted network, naming the document rather than leaving the next
reader to rediscover it. A latent silent failure becomes a loud one at the moment
it stops being hypothetical.

*Correction worth keeping.* The first draft of the characterization table listed
`10.0.30.64/26` host 70 as an out-of-network defect. `.70` is inside that network;
it belongs in the semantic-difference row. The error was caught by the test
asserting it, not by rereading the table - which is the argument for pinning a
characterization in tests rather than in prose.

**Strict resolution with provenance, 2026-09-11: `netmodel/resolve.py`.** G2 asks
for a source map - not only what an address resolved to, but which authored field,
inherited default or derived rule produced it. Without that, reviewing a generated
address has nothing to check it against.

Precedence is explicit and recorded: authored beats object default beats host
default (`@on:host.X`), and the losers are kept on the resolved value so a
reviewer sees what was overridden rather than inferring it from absence. Layer
order in the call does not affect the result - precedence is a property of the
origin - and that is asserted rather than assumed. A key a layer does not mention
leaves the layer below in place; `None` is not a value, because a source that
means "remove this" says `enabled: false`.

Derived values carry `DERIVED` provenance naming the domain and the rule, never
an authored origin - a source map that sent a reviewer looking for a field the
schema forbids would be worse than none. The authored request is kept as what the
derivation replaced, so the intent sits beside the result.

Refusal, never fallback, and each is a test: an unmodeled network, a missing
`network_ref`, a static request against a prefixless domain, a static request
with no offset, an address that is not an object. A dynamic allocation resolves to
no address rather than an invented one, and a domain with no gateway yields none
rather than the first usable address - which is precisely what the legacy path
defaulted to, unconditionally, producing gateways outside their own network on
every shifted subnet.

G2's listed cases are covered: /24, /23 in both halves, shifted /25, /30, the
network and broadcast offsets, an offset past the end, and one that does not exist
in a shifted subnet.

**The differential says the replacement changes nothing live.** All 23 addresses
the pipeline currently renders were resolved through the strict resolver and
compared: identical, every one inside its own network, gateways included. That is
the evidence that mounting this does not move a deployed address - not an argument
that it should not.

*Method note.* The first version of that differential read `resolved_ip`; the
field is `_resolved_ip`, so it compared nothing and would have passed vacuously.
It was caught by the guard asserting a minimum comparison count, which is now the
rule for any differential here: assert that it examined something, or it is not
evidence.

**Mounted in the compiler, 2026-09-11: `base.compiler.network_intent_resolver`.**
Resolution now publishes a channel, `resolved_network_intent`, carrying each
effective address, gateway and family together with its source map. A later stage
consumes one authority instead of deriving addresses again with arithmetic of its
own, which is how the legacy compiler and the MikroTik generator came to disagree
about zones (W05) and would have happened again here.

Three deliberate limits, each a test:

* It does not touch a v1 source. The flat block is still `ip_derivation_compiler`'s;
  replacing that would change rendered addresses nobody has reviewed.
* It does not fail the stage. It runs before validate, so an unresolvable record
  is published as unresolved with its reason and
  `base.validator.network_intent_schema` reports it with the right code. Erroring
  here too would report one fault twice, with worse paths.
* It does not guess. A dynamic allocation yields no address, a domain without a
  gateway yields none rather than the first usable address, an offset the prefix
  rejects yields nothing. Each is a fallback the legacy path took.

Precedence between authored, object-default and `@on:host.X` values is not
re-implemented here: `instance_rows` publishes merged rows, so the merge already
happened upstream. A second precedence table would be a second authority for one
rule, which is what W02 exists to remove.

One resolver, asserted: a test checks that the compiler and the validator hold the
same `resolve_offset` object, not merely equivalent code.

16 plugin tests executing through the registry - again the only proof the plugin
loads, since an empty channel from a plugin that never ran looks exactly like an
empty channel from v1-only sources. Artifact parity identical across 147 files;
determinism and strict-lock compiles pass.

*Method note.* The first version of those tests read the channel with
`ctx.subscribe` after execution and failed on all fourteen: `subscribe` needs an
active execution scope, and the plugin's is torn down by the time an assertion
runs. `get_published_data()` reads the bus directly.

**Migrating one real source, 2026-09-11.** `docker-grafana` was converted to v2,
compiled, and reverted. Two things came out of it that no amount of fixture
testing would have produced.

*A bug the tests could not see.* The validator resolved class declarations by
reading `lineage` from `ctx.classes`. That field does not exist there: `ctx.classes`
holds raw class-module payloads, and `lineage` is added when the effective model
is assembled, after the validate stage. The chain therefore collapsed to one
element and no declaration on a base class was ever found - every v2 block would
have been rejected as undeclared.

The tests passed throughout, because the fixture supplied `lineage`, copied from
the compiled model. **A fixture built from the wrong stage's shape is not a
fixture, it is a second implementation of the bug.** The fixture now carries
`@extends` as the files on disk do, the chain is followed through the payloads,
and two tests pin it: one resolving a declaration two levels up, one asserting a
looping parent link does not hang the compile.

*The migration unit is the host, not the workload.* `srv-orangepi5` declares
`workload_defaults.network` with v1 keys, and 19 workloads inherit from it.
Migrating one produces an effective block holding both the instance's v2
attachments and the host's inherited v1 keys - the mixture `E7004` forbids. That
is the rule working: an instance inheriting a v1 host default is a v1-flavoured
source, and allowing it would mean two readings of `host` in one block. W09 should
plan migration per host, moving the defaults and every workload under them
together.

Addresses are not what makes that expensive: nothing renders the derived
addresses, so a migration cannot change one. The whole cost is in the inheritance
graph.

*Method rule.* An empirical migration of one real source belongs in every gate
that introduces a new authoring shape. Two defects surfaced in one compile that
71 passing plugin tests did not contain.

**The migration path is mechanically available, 2026-09-11.** Having established
that migration is per host, the next question is whether the v2 shape can travel
the inheritance chain at all - and the chain turned out to have three links, not
two: the object module pulls `network.network_ref` and `network.gateway` from the
host with `@on` directives, so `obj.docker.container.generic` moves with the host
and its instances.

`_get_nested_value` walks a dotted path of arbitrary depth, so
`@on:host.network.attachments.primary.network_ref` resolves with no change to the
resolver. Three tests assert it rather than leaving it as a reading of the code:
a v2 attachment inheriting `network_ref` and `driver` from the host while the
instance keeps only its own address; the inherited block carrying no v1 key, which
is what makes it acceptable to `E7004`; and a required host path the host does not
declare being reported as `E6810` rather than silently dropped - silence there
would leave an attachment without a `network_ref` and the validator would then
point the author at the instance file, which is the wrong one.

The gateway leaves the chain entirely. In v2 it is a property of the address
domain, derived, not authorable on an attachment - one fewer value to keep in
agreement across three files.

So W09 has a recipe rather than an open question, and it needs no framework
change: object module, host `workload_defaults`, instances, together, per host.
The migrated shape is written out in `MODEL-OPERATION.md` section 7a.

**A22 candidate isolation, 2026-09-11: `netmodel/candidates.py`.** The separation
between what is proposed and what is authorized is a type boundary rather than a
remembered check.

A `Candidate` is not a `Binding` and has no approval field to flip. `promote` is
the only crossing; it takes a keyword-only approver with no default, so no call
approves implicitly — G2 names `metadata-as-approval` as a fallback that must not
exist, and the check is over the signature rather than the prose. It refuses an
approver who is the proposer, because self-approval turns review into a formality
that leaves a full audit trail of nobody having looked. Approval activates a
template and never widens one: promoting a candidate whose selectors miss the
template is refused rather than resolved permissively.

An unapproved `Binding` is reported as a candidate rather than dropped. A binding
somebody wrote and nobody approved is exactly what a reviewer needs to see, and
A22 is about candidates being *present* and inert — refusing to represent them
would satisfy the letter and defeat the point.

The A22 property itself is asserted directly: the authorized set computed with
candidates in the model is identical to the set computed without them.

**What this does not close.** Rejecting a proposal is green; a missing mandatory
intent must still block, and that is `SEC-AVAIL` (`E7084`), which belongs to the
plan compiler. The plan is explicit that "candidate rejected" cannot hide missing
Q, so the module is given no vocabulary for requirement or availability at all,
and a test asserts neither `Review` nor `Candidate` gains such a field. A green
review is evidence about proposals only, and saying so is the difference between
A22 satisfied and A22 assumed.

15 tests. Remaining for G2: none of the framework work; what is left is source
migration, which is W09 and gated on G1-G4.

**Correction to that instruction (revision 4a).** It presumed those codes are
registered. At baseline `493867d5` they are not. The canonical registry is
`topology-tools/data/error-catalog.yaml`, indexed by `docs/diagnostics-catalog.md`,
whose governance rule states that new ranges are registered *before*
implementation. Checking every code raised by the five capability plugins against
that registry shows three unregistered ad-hoc codes: `E8020` and `E8021`
(`capability_helpers`) and `E3202` (`capability_contract_validator`). `E8020`/
`E8021` also sit inside the `E80xx` band already occupied by registered
`E8001..E8007`, and the `E8xxx` family has no entry in the core-ranges list at all.

W03 therefore owns, before any SEC-CAP code is raised:

- registering `E8020`, `E8021` and `E3202` with their current platform/bootstrap
  and contract meanings, so that the "keep their meaning" instruction has a subject;
- reserving a distinct family range for network capability satisfaction and
  recording it in both the registry and its index, with a collision test;
- registering the `E8xxx` family in the core-ranges section so the band is owned.

Codes are immutable once released and retired codes may not be reused, so this
registration is a prerequisite of G1 closure, not clean-up afterwards. It touches
framework registries rather than the ADR package and is not performed by this plan.
L2 authoritative prefix/gateway/zone declarations remain valid; only derived
consumer overrides are rejected. Registering extension schema does not qualify
dynamic/nested capabilities. Mixed source versions are rejected only in an
ambiguous single effective network contract; separately scoped legacy and strict
sources may coexist without gaining unproven shared-boundary compatibility.

No active instance migration. Unknown keys, unresolved typed refs and unexplained
authoring-budget excess block closure. Numeric code allocation is not deferred
past G1 or replaced by a meaningless test that strings do not collide with numbers.

### G2 — Normalized intent, provenance and candidate isolation

W04 resolves addresses numerically, gateways from domains, bindings and identity.
Keep the old ip_derivation input path for legacy compatibility; do not describe its
known /23 or shifted-/25 defects as an absence of defects. Any legacy repair is
separate from the new strict resolver with explicitly reviewed output changes.

Derive capability requirements with source/obligation provenance and planned/active
status; preserve attachment/guard/egress requirements when no publication exists.
A25 tests requirement completeness and no increase in authoring keys.

Candidate proposals remain outside approved grants and runnable artifact inputs.
Rejecting an **optional unapproved suggestion** may leave the pipeline green.
Missing mandatory intent, a conflicting active binding or unready required service
must still block strict activation: “candidate rejected” cannot hide missing Q.

Exit: boundary/invalid-type/reservation/collision tests; /24,/23,/25,/30 cases;
mapping inheritance; disabled refs; original/backend endpoint resolution; source
map; snapshots/envelopes and A22 isolation. No fallback to any, first attachment,
product-default ports or metadata-as-approval.

### G3 — Semantic model, backend prerequisites and independent checks

W06 produces complete bounded authorization/path/state semantics and a validator.
Test SEC-AUTH, AVAIL, PATH, NAT, ORDER, STATE, CAP and transition-model prerequisites,
not merely the sort order. Use an independent reference interpreter; do not make
the generator and oracle share the same decision code and call agreement proof.

Resolve scoped offers with device/runtime, adapter and owner-operation witnesses;
check coverage independently, evaluate typed conditions and aggregate resource
bounds, ensure jointly compatible strategies/modes/owners, reject unknown
relationships/cycles and choose only proven-equivalent strategies canonically.
A26-A29/A31/A32 model portions block flag-as-proof, grant expansion and self-attested
qualification. Missing live evidence remains an activation prerequisite, not an
excuse to claim unsatisfied offline semantics or to waive later checks.

Before backend specialization, record target version/provider/capability envelope,
scope, trust assumptions, transform/state semantics and expected fail-closed cases.
Recommend a physically/logically isolated RouterOS fixture, not an existing
production service as an automatically safe pilot. Availability of a test target
and provider support are prerequisites to actual backend tests, not assumptions.

Investigate ordering/read-back/guard/revocation feasibility **before** freezing G4
artifact contracts. Record unresolved feasibility as a block to deployment
qualification, not permission to bypass Terraform ownership.
Exit: A03/A04/A09-A15/A19 model portions, termination, original/current tuple
distinction, path witnesses, scope composition counterexamples and deterministic
canonical keys. Unsupported extensions fail explicitly; no installed-device claim.

### G4 — Offline backend artifacts and immutable bundle closure

W07 renders the already validated specialized plan. Terminal deny is a plan
obligation; the template only renders it. Include legacy/unowned context inventory
in shared-scope validation; generating a correct managed subchain alone is insufficient.

W08 extends the **existing** bundle contract. Security content includes profile,
intent/plan digests, exact artifact/resource inventory and hashes, validation
evidence, selected offer/contract/backend versions, strategy and conditions,
ownership and transition requirements. W07 supplies versioned offers; W08 tests
A27/A30 offline-vs-live status, offer/evidence tampering and invalidation.
Expected post-transition configuration is explicit, never confused with observation.

A30 needs a decidable boundary to test against, so W08 implements the offer split
of [contract §4.1](../0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md): the offer
semantic core enters the plan digest, the evidence annex is hashed separately and
bound to the manifest only. The regression is bidirectional and both directions are
required: mutating the core must change the plan digest and invalidate resolution,
and re-recording identical semantics with a newer observation must leave the plan
digest byte-identical. Testing only the first direction proves invalidation while
leaving the freshness-determinism claim unevidenced.
A referenced security artifact is permissible only when its hash and schema are
bound by the root manifest. Missing/tampered/stale evidence required at the current
gate blocks that gate. Offline build does not require future live observations;
activation and completion require their respective fresh evidence.
No free-standing parallel “security manifest” can independently authorize execution.

Assemble validates cross-artifact consistency; build creates immutable input.
Live observations and execution journal remain outside the bundle, bound to its
digest/epoch. Keep secrets out of diagnostics and deterministic public manifests.

Exit: independent reference vs normalized rendered-rule differential tests;
A03/A24, artifact syntax, digest closure, tamper/omission/stale-evidence negatives,
no backend rediscovery or independent grant producer, no generated edits.
Call this **offline validation**, not backend qualification. G4 does not close
live read-back, state revocation, device ordering or G8.

### G5 — Reviewed scope inventory and activation readiness

W09 may inventory sources and prepare flow questions before G1. Freeze normalized
intent after G1/G2; source migration follows G1-G4 per the acceptance contract.
Use approved configuration/requirements, observed evidence and explicit review.
Live traffic alone neither identifies every required flow nor authorizes it.

Current source inventory: 23/29 service files have neither ports nor allowed_from;
27/29 lack at least one; only 2 have both, and that is not proof of completeness.
Retain the accepted inventory of 6 legacy upward container_ref files and 9 authored
routing_mark files; resolve them by provenance and role, not blind text replacement.
Keep legacy VPN and disabled/planned Proxmox intents visible; no enablement by default.

Model readiness: allocations, domain ownership, declared pools/listeners, explicit
grants/guards/Q, runtime targets and zone consistency.
Live readiness: fresh authoritative leases/address/listener/identity observations
at **G6 preflight**. G5 does not require a nonexistent G6 execution result to close
its model/review portion; deployment remains blocked until the fresh preflight passes.

Exit: approved per-scope inventory, A05 model/A06/A21/A23 mapping portions,
no lost restrictions, all pending live checks explicit. Do not migrate all services
or qualify every extension merely to complete a bounded first scope.

### G6 — Transaction implementation and safe laboratory execution

W10 defines controller behavior over the existing runner, not a new transport.
Start pure state-machine/fault simulation alongside W08; closure requires G0b,
G4 bundle closure, scoped G5 readiness, target feasibility and independent recovery.

Specify the writer for each desired resource, temporary guard and state operation.
Terraform remains RouterOS post-bootstrap owner. Read-only probes do not change
ownership. A mutation must have owner delegation and reconciliation with desired
state; no hidden imperative side writer under a controller or wrapper.
If supported owner operations cannot meet the invariant, stop qualification and
request the architectural amendment — do not smuggle it into implementation.

Preflight re-evaluates effective-capability conditions and evidence freshness for
exact subjects/versions/modes/contexts; changed dependencies invalidate resolution.
A27/A29/A30 verify phase-specific conditions, owner-delegated operations and that
safe_mode/state_restore cannot restore revoked grants. Missing post-apply evidence
blocks completion, not construction of a qualified guarded transition.

Journal step preconditions/postconditions, idempotency keys, approved old/new epochs,
transition envelope, deadlines, stale-session invalidation, retry/reboot recovery,
audit/resource-failure behavior and current-authority rollback.
Negative-test partial application at every mutation, including installing/removing
guards. A06 source attachment correctness is not OOB; management UI on the affected
router is not independent recovery.

Exit: A13/A16-A18/A20 transition/fault portions at the declared evidence levels,
fresh A05 preflight, no unauthorized intermediate flows, required availability
within the approved transition envelope. Passing simulation alone is not G6 closure.
Production application remains a separate operator authorization after qualification.

### G7 — Scoped executable and observed conformance

W11 is continuous; tests start with the producing gate. At G7 consolidate the
matrix below, run positive/negative/fault paths on the actual isolated target,
and distinguish model, rendered, backend-tested and live-observed evidence.

Each A01..A32 has a test or an explicit scope decision. Unsupported extension cases
must prove refusal/verified disablement for the baseline, not be marked passed
without evidence. Keep unqualified requirements open for their extension profile.
No need to claim Docker, Proxmox, IPv6 or AWG success to qualify a bounded RouterOS
profile; no right to ignore their paths if present in that profile's real scope.

Exit: versioned per-scope matrix with evidence locations, actual-path coverage,
fresh observations and failure/recovery results. A01 named production AdGuard
remains open until that actual scope is exercised; a synthetic DNS fixture is
evidence for the same semantic obligation, not an invented production test result.
New execution scenarios use TUC folders and the repository TUC numbering process.

### G8 — Qualification and human risk approval

W12 closes only the selected backend/version/capability/scope profile.
All applicable HA obligations and required A-case evidence must be current; human
assignees and residual-risk acceptance must be recorded. Explicit exclusions need
enforced boundaries, not merely a “not applicable” label.
The wider project and other platform profiles remain unqualified.

G8 authorizes a qualification statement, not an automatic production apply.
A production deployment additionally needs the exact approved bundle, current
preflight/ownership/identity evidence, OOB and transition approval.

## 6. Acceptance coverage ownership

Coverage is assigned now; tests are implemented with their owning gate.
For combined cases, an early pass never substitutes for the later evidence level.

| Cases | First owner | Later required evidence |
|---|---|---|
| A01-A02 | G3 authorized DNS/UI model | G4 rendered; G7 observed on the named qualified scope |
| A03 | G3 original/frontend identity | G4 differential; G7 backend behavior |
| A04 | G1 schema + G3 overlap oracle | Blocking witness, not sorting precedence |
| A05 | G2 allocation/model + G5 reviewed inventory | G6 fresh ownership/lease/listener preflight |
| A06 | G1/G2 direct attachment | G4 artifact; G7 path behavior where applicable |
| A07-A08 | G3 host/bridge capability/path model | G7 applicable backend path or explicit unsupported/refusal |
| A09-A12 | G2/G3 domain/transform/identity/fallback semantics | G7 supported extension evidence or tested baseline refusal/disablement |
| A13 | G3 epoch/state semantics | G6 revocation faults + G7 observed deadlines |
| A14-A15 | G3 canonical/order and independent mutants | G4 rendered differential regressions |
| A16-A18 | W10 simulation, G4 immutable contracts | G6/G7 actual interruption, drift, recovery and idempotence |
| A19 | G3 monotonicity | G4 lowering preservation |
| A20 | G3 resource/audit failure model + Q | G6/G7 bounded failure and required-flow availability |
| A21 | G1 budget method | G5 actual migrated feature and inheritance navigation |
| A22 | G2 candidate isolation | G4 no artifact grant + G7 no accepted flow |
| A23 | G1 consumer-derived override rejection | G5 migration roles and provenance; valid L2 declarations preserved |
| A24 | W05 parity + G2/G3 producer ownership | G4 whole-pipeline integration proving no semantic recomputation |
| A25 | W03/W04 G1/G2 typed requirements and provenance | Full intent inventory, no second author checklist |
| A26 | W06/W07 G3 scoped composition | G7 effective device/adapter/path coverage, disabled/wrong-scope negatives |
| A27 | W06 G3 evidence-relative status | W08 G4 offline bundle allowed; W10 G6 activation/completion preconditions enforced |
| A28 | W06 G3 strategy alternatives/determinism | W07 G4 independent rendered equivalence; G7 applicable backend paths |
| A29 | W06 G3 owner/recovery model | W10 G6/G7 no side writer or revoked-grant restoration |
| A30 | W08 G4 digest/dependency invalidation | W10 G6/G7 version/mode/drift/expiry observations |
| A31 | W06/W11 G3 inventory/evidence trust negatives | G7 complete scope inventory and independently checked qualification |
| A32 | W06 G3 non-authorizing capability changes | G4/G5 no auto topology/selector/profile/owner fallback |

W08 additionally tests bundle integrity, version compatibility, missing artifact/
evidence, stale plan hashes and unapproved candidate input. These are supporting
regressions, not replacements for A01..A32.

## 7. Dependency and execution policy

```text
W01 baseline -------- W05 legacy parity -----------------------+
W02/W03 G1 -> W04 G2 -> W06 G3 -> W07/W08 G4 offline closure ----+--> G6
                   |              ^                              ^
source inventory --+--> G5 model/review readiness ---------------|
target feasibility/capability record -> G3 specialization -------|
G0b owners/tailoring + independent recovery ----------------------+
G6 observed transition -> G7 scoped conformance -> G8 qualification
```

Read the diagram as closure dependencies, not a prohibition on drafting tests or
collecting requirements early. G5 model review can be prepared alongside G3/G4;
active source migration still requires G1-G4. Shared-chain composition is designed
and modeled in G3/G4, then verified at G6/G7, not discovered for the first time at G6.
There is no unsupported “six-link longest chain” estimate.

A blocked production router does not imply the entire repository or an isolated
laboratory is blocked. Only scopes sharing unproven execution paths/resources are
blocked from strict activation. Separate scopes require evidence of isolation,
not a change of labels.

## 8. Remaining approvals and bounded implementation choices

| Item | Required record / owner | Deadline |
|---|---|---|
| Human work assignees and G0b tailoring | Names, authority, threat assumptions and Q objectives / risk owner | Before claiming G0b or G6-G8 closed |
| Recommended RouterOS target | Exact version/provider/profile, isolated topology and availability / backend owner | Before G3 backend specialization and G4 fixtures |
| Shared-chain composition or real separation | All dispatch/rules/transforms/owners and path proof / scope owner | Design by G3; model checked G4; live preflight G6 |
| Owner-controlled transition feasibility | Allowed operations, guard/state reconciliation and recovery / deploy owner | Before G4 artifact contract freeze; qualification blocks if unresolved |
| Unrendered containers | Actual source/artifact inventory with planned/unqualified labels / topology owner | Scope selection and G5; no forced enablement |
| Production activation | Exact scope/bundle/epoch, fresh observations, recovery and approval / operator | After applicable qualification; not authorized by this plan |

Bundle authority and core ownership are resolved constraints, not open alternatives.
Implementation may choose API calls, helper structure and tests within them.

## 9. Validation policy for implementation changes

For each work item: targeted tests plus the narrow relevant Task gate, manifest/
snapshot tests where applicable, and strict lock verification. Refresh framework.lock
only alongside actual framework changes. Before integration closure run task ci
and the applicable TUC quality gates; document unavailable checks as not run.

Compare source -> normalized intent -> plan -> rendered artifacts -> immutable
bundle -> observed state using exact revision/digest links. Neither a passing
documentation gate nor this plan's work assignment closes G1-G8 or A01-A32.

**Artifact comparison has a method, and one obvious method is invalid.** Generated
output is gitignored and untracked, so `git status` reports nothing about it
whatever the artifacts do; a clean status is not evidence of an unchanged
artifact. Comparison means generating both sides and comparing content hashes of
every emitted file, with the declared non-semantic fields of W13 excluded and the
exclusion list stated in the claim. Where the two sides are different revisions,
generate each in its own checkout so that neither run inherits the other's output.
A parity claim without that procedure is not a weak claim, it is an empty one.

### Governance deliverables per gate

The acceptance contract requires governance artifacts to move with the code, not
after it. Each gate that changes a contract also updates, in the same change:
affected ADRs and their register entry, the scoped rule packs, the semantic
schema and diagnostic registries, layer/reference rules, plugin manifests and
tests. A gate whose code landed without its governance update is not closed.
Documentation-only revisions never refresh framework.lock.

### Stop conditions and reversibility

A gate that cannot meet its exit criteria has three admissible outcomes, and
silently proceeding is not among them: reduce the scope and record what moved out,
record the blocker as a qualification block and stop, or raise an architectural
amendment when the obstacle is an accepted decision rather than an implementation
difficulty. The third applies in particular to resource ownership: an unmet
transition guarantee is a reason to stop, never a reason to add a second writer.

The effort is reversible up to G6 by construction. Version 2 schemas coexist with
version 1, so schema and compiler work that stops after G1-G4 leaves registered
but inert definitions: no instance uses them, no artifact changes, the legacy path
keeps its behavior. That property must be preserved deliberately, and it is a
regression: at every landed change the managed artifacts of the legacy scope stay
identical unless the change is an explicitly reviewed behavior change. From G6
onward the work touches live state and reversibility becomes the transition
envelope's problem, not the repository's.

### Entry conditions

Gates declare exits; parallel preparation needs entries too. Reading sources,
characterizing current behavior, drafting schemas and tests, collecting
requirements and recording human assignees may start at any time. Landing a
contract change requires its predecessor contract to be registered; freezing an
artifact contract requires the feasibility record; claiming closure requires the
gate's own evidence. Preparation is never converted into closure by being finished
early.

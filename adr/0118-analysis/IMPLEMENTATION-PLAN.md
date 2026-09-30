# ADR 0118/0119 — implementation plan

Status: reviewed implementation plan for the **Accepted** architecture, G0a closed
2026-09-10. Revision 4, 2026-09-11 (capability satisfaction amendment); revision 5,
2026-09-30 (W07 migration order completion recorded; no gate closes). **No implementation gate is closed by this plan.**
No topology migration, code change, secret access, live inspection or deployment
is authorized by editing this document.

Authority: [ADR 0118](../0118-universal-container-network-model.md),
[ADR 0119](../0119-firewall-rule-ordering-contract.md) and
[current architecture proposal, rev 3.4](FINAL-ARCHITECTURE-PROPOSAL.md).
[Migration/acceptance](MIGRATION-AND-ACCEPTANCE.md) owns G0..G8 and A01..A32;
this plan assigns implementation work and evidence to those gates.
[Review findings](IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md) explain the corrections.

Current enforcer/scope contract: ADR 0119 D1-D1.1 rev 3.4. The
[conformance record](ENFORCER-AXIS-CONFORMANCE.md) owned ten open implementation
rows at its 2026-09-15 baseline; **reconciled 2026-09-30** against real commits
that predate this plan's own W07 entry, five are now closed (V-04, V-05, V-09,
V-13, V-15), one is split (V-14: closed for Proxmox, worse for MikroTik - the W07
migration multiplied its substring selectors from 9 to 18), and four remain open
unchanged (V-07, V-10, V-11, V-12). [W07](W07-BACKEND-SPECIALIZATION-DECISION.md)
records the selected layout. **Its migration order (items 1, 4a-4i) completed
2026-09-30** - see the dated entry below and `adr/REGISTER.md` - moving every
function that made a backend decision in the MikroTik generate-stage projection
into a compile-stage plugin. This closes no gate: the migration touches none of
the conformance record's remaining open rows, and it made V-14 measurably worse
by copying the row-kind and router-filter selectors verbatim into ten new files
instead of replacing them with declared-class/capability selection - a direct
cost of migrating per function with parity evidence rather than fixing what each
function assumed. The single-router assumption V-10 names is now replicated
across four of those plugins instead of living in one function. First test
multi-instance, multi-scope, adapter ambiguity and shared-target cases; then fix
the complete enforcer-to-scope index contract (`scopes_by_enforcer`, already
published) before adding further consumers. Historical measurements below retain
their original revision and do not establish current gate closure.

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
| W07 Backend specialization/render | Versioned adapter offers, effective applicability, complete execution contexts and deterministic rendering; no negotiation in generate | W05/W06; target feasibility record | G4, backend owner. **Migration order complete 2026-09-30**: every function that made a backend decision in the MikroTik generate-stage projection moved to a compile-stage plugin — see [W07 decision](W07-BACKEND-SPECIALIZATION-DECISION.md). This satisfies "no negotiation in generate" for those functions only; versioned adapter offers, effective applicability and complete execution contexts remain undesigned, and G4 stays open — see [conformance record](ENFORCER-AXIS-CONFORMANCE.md) |
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

15 tests; 262 in netmodel.

### Four blockers from external analysis, 2026-09-14

**1. Layer validation was broken.** `class.service`, added with the L5 base, was
never entered in `topology/layer-contract.yaml`, and
`validate_v5_layer_contract.py` reported FAIL. Fixed by listing it at L5 beside
the concrete roles. A class the contract does not list fails validation whether or
not any instance names it directly - the abstract base needs an entry exactly as
`class.compute.workload` has one.

*Correction to my own report of it.* I said the validator printed FAIL while
exiting 0. It does not: the `rc=0` I read was `tail`'s exit code, because I had
piped the output. The script returns 1 correctly and there is no second defect.

**2. Evidence was modelled as a numeric scale, and that is wrong.** `satisfies`
compared level values, so `live_observed` discharged a requirement for
`offline_validated`. The contract forbids it in one sentence - *a live packet
sample does not replace independent model checks or all-path coverage* - and its
section 4 table gives each claim its own required evidence rather than a
threshold: offline validation wants compatible versioned offers and independent
model checks, live observation wants a fresh preflight and a post-apply read-back.
Neither answers the other's question.

Evidence is now a **set of kinds** an offer holds, and satisfaction is membership.
Both directions are tested: live does not discharge offline, offline does not
discharge live, an offer may hold several kinds at once, and an offer holding none
satisfies nothing.

*Joint satisfiability, freshness and ownership, named as missing above, are now
implemented.* The contract's section 3 is the reason they cannot be folded into
per-offer resolution: effective support is **not the union of capabilities on all
devices**, so two offers can each be adequate and be unusable together.

| Checked in combination | Refused because |
|---|---|
| Mutually exclusive modes | Hardware offload and software conntrack cannot both hold in one plan |
| Ownership across witnesses | One plan needs one operator, not each offer owned by someone |
| Delegation | A mutating operation without a delegated owner is a hidden imperative writer |
| Evidence freshness | Stale is `unverified`, and an offer with no expiry does not expire - that is a statement it makes, not an omission the checker fills in |
| Prerequisite graph | Bounded and acyclic; a cycle is refused rather than broken at an arbitrary edge, since which offer came first would then depend on iteration order |
| Aggregate capacity | The tightest witness bounds the plan, not the roomiest |

`as_of` is a required argument with no default, and a test asserts the module
imports nothing that can tell the time: a clock inside the decision would make the
same inputs answer differently on different days, and the contract both wants
timestamps out of semantic identity and forbids one universal timeout.

`self_proving` catches the circularity the contract names directly - a strategy
whose only prerequisite is the property it is meant to prove. Neither end shows
it: the offer looks like it has a dependency, and the dependency looks like it has
a witness.

**3. W05 stays a blocker for the generator cutover**, unchanged, and the
characterization says so: the two overlay CIDRs are still declared on trust zones
and consumed only by the generator, so removing the duplicate derivation would
change output. The selector work under it is done; the source change is not.

**4. The transition module was an unfinished draft, and the diagnosis was exact.**
Three tests failed because reordering finished `Step` objects does not recompute
their stored states - an alternative strategy shuffled labels over states the safe
order had already built, so the dangerous sequence it claimed to model never
existed and the test correctly found no violation.

Restructured: a strategy returns **mutations**, and `simulate` is the only place a
state is built, so every strategy is played out the way its own order would
actually run and a strategy can be wrong. With that, the unsafe sequence - tear the
denies down first - produces the violation the obligation predicts, while both
endpoints remain inside the envelope. That case is now asserted directly: both ends
safe, a state between them not, which is the entire reason to check states rather
than endpoints.

12 transition tests, 47 capability tests, 294 in netmodel. Layer contract PASS.
Artifact parity identical across 147 files.

**SEC-STATE, 2026-09-14: `netmodel/state.py`.** The obligation's failure is an old
established or related flow surviving past its deadline, and the reason it is easy
to miss is mechanical: a stateful enforcer admits the first packet by matching a
rule and every packet after it by matching the **session**. Removing the rule stops
nothing already running. The contract says it directly - *live revocation is a
time-bounded transition, not a property of source editing* - and a test asserts
exactly that: the new epoch authorizes nothing, the session established under the
old one is still there, and editing the source stopped no traffic.

A revocation without a positive deadline is refused. It is not a lenient
revocation; it is an unbounded permit, and there is no default because the
contract forbids inventing one universal timeout. A session inside its deadline is
not a violation - transitions take time - and one past it is.

*Reverse traffic belongs to the authorization that admitted the session.* The
reverse tuple mirrors the endpoints and keeps the service port, since swapping the
port too would describe a different connection. An epoch that authorizes the
forward direction but not the return one is describing half of a working
connection as unauthorized, which is a modelling defect; it is reported rather
than repaired, because hiding it behind a permissive reverse rule is how a broad
accept nobody meant enters a plan.

Related flows inherit the parent's fate: a child connection has no rule of its
own and lives because the parent did, so it is reported with it.

Time is a supplied tick, and a test asserts the module imports nothing that can
read a clock - the same rule the capability freshness check follows.

14 tests; 308 in netmodel.

**SEC-PATH, 2026-09-14: `netmodel/path.py`.** It looked blocked on W09 and was
not: the lower bound on `Omega_g` is stated normatively in the contract, so
enumerating it is not self-declaration. Every path class ADR 0118 D6 requires -
L2 same-bridge, routed, host input and output, tunnel, direct backend, offload -
crossed with the families and epochs in scope.

*What is genuinely external is the evidence*, and the module has no function that
could produce it: `required_cases` enumerates what must be covered, `coverage_gaps`
takes `demonstrated` as an argument, and a test asserts no evidence-producing
function exists. `complete(R_g, Omega_g)` is unfalsifiable when one component
supplies both halves - a resolver that forgets a class reports full coverage of the
classes it remembered.

Absence is `unverified` by construction, an evidence entry citing nothing is a
claim rather than evidence, and an exclusion requires both an owner and a reason,
because the contract says a scope decision naming neither closes nothing. Evidence
for a case the scope never required is reported too: otherwise an inventory could
shrink while the coverage percentage rose.

*One deliberate departure from the literal text, recorded rather than silently
made.* The contract lists IPv6 among the path classes and also crosses the classes
with the address families. Literally that yields "the IPv6 path class under the
IPv4 family", which means nothing. IPv6 is carried by the family axis, where it
produces a real case for every class; a test asserts that.

Until W09 and W11 supply evidence every case reads `unverified`, which is the
correct answer rather than a placeholder.

14 tests; 322 in netmodel.

### W06 obligations: all eight now have a checker

`SEC-AUTH` and `SEC-AVAIL` in the interpreter-versus-algebra comparison, `SEC-ORDER`
in `plan`, `SEC-NAT` in `transform`, `SEC-STATE` in `state`, `SEC-TRANSITION` in
`transition`, `SEC-PATH` in `path`, `SEC-CAP` in `capability`. Three habits run
through all of them and are what make them checks rather than descriptions:
silence never means yes; nothing marks its own homework; and every checker is
shown failing on a plan that is definitely wrong before it is trusted about one
that looks right. `MODEL-OPERATION.md` section 7d has the table.

### The obligations against the real topology, 2026-09-14

Everything above was checked on fixtures, and a fixture agrees with whatever its
author believed. The eight zone-to-zone overrides that two security matrices
actually declare are now read from the compiled model, lowered, interpreted and
compared with the algebra. Reading them needed one addition to `snapshot.py`,
selecting matrices by declared class rather than identifier prefix, for the reason
W05 records.

SEC-AUTH and SEC-AVAIL hold on the real intent, and the terminal deny closes the
declared scope with no flow left unmatched. Neither result is the valuable part.

**The valuable part: the model cannot express the only mandatory deny the sources
contain.** Three of the eight overrides carry no ports - `management-to-servers-full`,
`lan-to-management-admin`, and `servers-to-management-deny`, which is the single
`drop` in the whole topology. The model refuses an unbounded port set deliberately:
an empty selector is an error rather than "any", and a constraint that is not about
ports is a separate shape. So the strongest guard in the sources is currently
inexpressible.

That is a migration finding, not a model defect - the source says "deny everything
from servers to management" and the target wants it said as a bounded set or as a
typed non-port constraint. It is recorded as a test rather than a note, because a
model that expressed five permits and silently dropped the one deny would look
like progress. The test passes while the gap exists and fails when the deny
becomes expressible, at which point it must be re-derived and SEC-AUTH re-measured
with it present.

The guard-precedence test skips rather than asserting guards exist: asserting
would fail for a reason that test is not about, and an empty loop passing quietly
would be worse than either.

8 tests, one skipped for the reason above; 329 in netmodel.

### The join: `base.compiler.security_plan`, 2026-09-14

The plan every obligation is checked against is now produced by the pipeline
rather than derived in a test. It reads the security matrices by declared class,
lowers their zone-to-zone overrides into rules, orders them by execution
precedence, closes each scope with a terminal deny and publishes the result with a
digest over meaning alone.

On the real topology: 2 scopes, 7 rules, 3 overrides it cannot lower - the same
three the reference model blocked, for the same reason. What cannot be lowered is
published with its reason rather than dropped, because a plan that silently
omitted the sources' only mandatory deny would look complete.

`E7082` is the terminal's code. `E7854`, which ADR 0110 named for it, belongs to
storage media inventory and has since three months before that ADR claimed it.

**A defect found by reading real output, not a fixture.** Positions were numbered
globally across scopes, so a two-matrix topology produced a terminal at position 1
with five rules after it. Correct per scope, and a list that drops everything
after position 1 the moment a consumer flattens it. Positions are now per scope and
consecutive from zero, with a test asserting both that and the terminal being last
in its own scope.

The lowering now exists twice - the framework cannot import `netmodel`, which sits
outside distribution - so a differential runs both over the same overrides and
requires the same emitted sequence. That is the third such pair, after the policy
algebra and the address arithmetic.

18 tests. Artifact parity identical across 147 files; `tests/plugin_regression`
10 passed, 3 skipped.

### The independent check: `base.validator.security_plan`, 2026-09-14

G3 says validation independently checks the complete plan, and *independently* is
the requirement rather than a description: a validator that called the compiler's
sort would compare the sort with itself and report agreement. So this one
re-derives the required precedence from the rules and checks the emitted positions
against it. **It never sorts anything** - a test asserts it produces no `position`,
only reads them - so the two can disagree, which is the only condition under which
their agreement means something.

`E7080`, `E7081` and `E7082` are emitted for the first time: a precedence cycle, an
emitted order violating an edge it must satisfy, and a scope with no terminal deny.
Each has a failure that looks fine from the other side - a permit before the deny
that constrains it reads correctly in a rule list, and an unterminated scope reads
correctly in one too, while being open on a default-allow backend.

The terminal is a role and not an effect here as well. Counting it among the denies
would require it to precede every permit and follow every rule at once, so the
validator would report a cycle it had invented; a test asserts a correct plan stays
clean. Cycle detection is iterative, because a 400-rule chain exhausts a recursive
one - also tested.

*Two corrections in the making.* My own independence test first searched the source
for `sorted(` and flagged `sorted(by_scope)`, which iterates scope names
deterministically and orders no rules; a substring test cannot tell an ordering
from a stable iteration, so it now asserts over the AST that no `position` is ever
produced. And the validator initially reused `E7007`, registered for a different
validator's missing rows. Both say a check did not run, but they name different
missing producers and a reader needs to know which, so `E7008` was registered -
the same split, for the same reason, as `E7007` from `E7005`.

12 tests. Artifact parity identical across 147 files; `tests/plugin_regression`
10 passed, 3 skipped.

### W07 decision, 2026-09-14: specialization is a compile-stage object-module plugin

The plan left the decomposition open and this fixes it, in
`W07-BACKEND-SPECIALIZATION-DECISION.md`. The constraint it had to satisfy - *it
cannot occur only in a generator after the relevant validator ran* - **is currently
violated**, and that measurement is what decided it.

`object.mikrotik.generator.terraform` runs at generate, order 220, and calls a
projection of 1,565 lines across 17 functions, every one of which makes a backend
decision: zone membership and matrix rules (246 lines), tunnel termination (191),
container attachment and publication shape (191), routing policy and `*_vlan_ref`
resolution (110), capability flags driving conditional generation (21). Every
validator has finished before any of it runs, and nothing checks its output except
artifact parity, which compares it with itself from the previous run.

Two consequences were already observed rather than predicted. **W05** is the
generator recomputing zone membership and reaching a different answer, because
both derive it and only one is checked. And `_derive_mikrotik_capability_flags`
drives conditional generation from capability set membership - the flag-as-proof
the capability contract rules out - two stages after the SEC-CAP resolution could
have seen it.

**Decided: a compile-stage compiler plugin in the object module.** Validation must
be able to see the specialized plan, and anything produced at generate is
unverifiable by construction. Backend semantics belong to the backend's module
rather than an internal core operation, which would make the core know about one
product. And the seam exists: `base.compiler.security_plan` already publishes a
backend-neutral plan at compile, so a specializer consuming it and publishing
`backend_plan` needs no new mechanism. The generator's remaining job is rendering
- which ADR 0119 D4 already says for the terminal deny, and the same rule covers
everything else the projection decides.

**No code was moved.** The projection's output is pinned only by artifact parity,
and moving 1,565 lines in one step would replace a measured baseline with an
unmeasured one. Migration is per function with parity evidence, ordered by what is
checkable: capability flags first, then the reference resolution the compiler
already performs, then `_extract_security_matrix` - which is blocked on the W05
divergence and is exactly the step anyone would reach for first.

Seven tests hold the line: the debt may shrink and must not grow, the budget must
not go stale, the compile-before-validate seam must stay, and the blocked step must
keep being named. The decision records its own falsifier - a specialization needing
information that exists only after generation would put the seam in the wrong place
- because a decision with no stated falsifier is a preference.

### W07 migration order complete, 2026-09-29/2026-09-30

The migration order this section named ("No code was moved" above; capability
flags first, then the reference resolution, then the W05-blocked matrix step) ran
to completion across ten items - `W07-BACKEND-SPECIALIZATION-DECISION.md`'s table,
items 1 and 4a-4i - each with real-topology parity evidence (`generated/`
byte-identical, `errors=0 warnings=3` unchanged) and its own dated entry in
`adr/REGISTER.md`. The MikroTik generate-stage projection this section measured
at 17 functions / 1,565 lines is now 2 functions / 518 lines:
`_extract_security_matrix` (its own multi-*scope*-per-enforcer defect closed by
separate, earlier work in this program - `e868abbe`, `168b4f27`, see below - but
still limited to one *enforcer*, the still-open V-11/V-12 layout question) and
`build_mikrotik_projection` itself, the orchestrator this section predicted would
be what remained. Ten new compile-stage compiler plugins were registered, one per
migrated function, each consumed by `object.mikrotik.generator.terraform` as a
required channel.

Two real defects surfaced during migration, not before it: item 4b found a local
variable shadowing a new required parameter, which would have silently corrupted
rendered container output; item 4g found a test building a `PluginInputSnapshot`
directly, bypassing the projection's own auto-deriving wrapper, whose fixture's
real VLAN was silently discarded by an all-empty channel stand-in rather than
rendered. Both are fixed; both are recorded in `REGISTER.md`'s item 4b/4g entries.

**What this does and does not establish.** It satisfies the constraint this
decision opened with - specialization not occurring only in a generator after
validation ran - for the ten functions named. It does not close G4: the exit
criteria two sections below (independent differential tests, digest closure,
tamper/omission/stale-evidence negatives) are untouched.

`ENFORCER-AXIS-CONFORMANCE.md`'s ten rows were reconciled the same day (2026-09-30)
against real commits, five of them (V-04, V-05, V-09, V-13, V-15) already closed by
work earlier in this program, before this migration started - the conformance
record's own table had simply never been updated to say so. The migration itself
touches none of the remaining open rows except by making one worse: V-10's
single-router assumption (`default_router_id = next(iter(sorted(router_ids)), "")`
feeding a `len(router_ids) == 1` branch) was carried verbatim into four of the ten
new plugins rather than fixed - replicated four times instead of living in one
function, and dead code in `projections.py` itself now that nothing there reads
it - and V-14's substring-selector count rose from 9 (one file) to 18 (across
eleven files), since each new plugin re-implements its own router-filter and
row-kind selection rather than sharing one. Migration relocates where
specialization runs; it does not audit what each relocated function assumes, and
moving one function into ten files multiplies whatever that function assumed by
ten.

### PR1 from the post-fix review, 2026-09-14 — gates restored

`docs/reports/2026-09-14-adr0118-0119-post-fix-review.md` measured two red gates,
and both were mine.

**Three fixtures in `test_security_matrix_compiler.py`.** The class-based selector
(`e0d39f6a`) reads `class_ref`, and those fixtures carry only an instance id. I ran
the W05 parity test and the netmodel suite after that change and **not the test
file of the module I had changed** - the parity evidence I did collect said
nothing about the compiler's own contract tests. Fixed by giving the fixture rows
the `class_ref` that `normalized_rows` carries, not by restoring prefix selection.

**Two banned registry accesses.** `test_integration_tests_no_legacy_publish_registry`
forbids `get_published_data(` in the integration suite, and I introduced it in two
files while working around `subscribe` needing an execution scope that is gone by
assertion time. The correct shape was already there: every other plugin returns
what it produced in `output_data`, and a test reads that. Both compilers now do,
and the tests read the result rather than reaching into a private structure the
envelope contract exists to replace.

A third failure surfaced while verifying: two of my own `--diagnostics` tests
failed on a stale `framework.lock` after the compiler edits. Refreshed.

The review's own selection - 163 passed, 3 failed - is now **166 passed**.
`tests/plugin_contract` is 281 passed, 0 failed. `tests/netmodel` 329 passed, 1
skipped. Artifact parity identical across 147 files.

**Status correction the review asked for.** The eight obligations have checkers;
they do not yet all check one complete pipeline-produced plan. G3 is not closed,
and the phrase in this plan that its remaining work is "a widening one" was
premature - the review is right that intent, approved plan and independent
obligations are not yet joined. The findings F1-F5 name real counterexamples that
green tests did not catch, and they are the next work rather than more migration.

*Evidence correction.* PR1 was first recorded as "`tests/plugin_contract` 281
passed". That is not `task test:plugin-contract`, which runs
`tests/plugin_contract tests/plugin_api tests/kernel tests/test_plugin_registry.py`
with coverage. Re-measured on that exact scope: **405 passed, 0 failed**. Each
run's command and boundary is now recorded with its number.

### PR2, part one, 2026-09-14 — the lowering stops losing meaning

Against the five completion criteria set for PR2.

**1. Every protocol survives.** `_lower_one` took `sorted(ports.items())[0]` and
emitted one rule; on `{tcp: [53], udp: [53]}` it kept TCP and dropped UDP with an
empty `unlowerable` - a lost service for a permit, a lost restriction for a deny,
and no diagnostic either way. One source selector is now one rule per protocol,
tested for permit and for deny separately.

**2. No partial success.** A scope with even one unlowerable override is now in
`blocked_scopes` and absent from `strict_eligible`: the remaining rules are a
subset of the intent, and a subset of a restriction is a weaker restriction. The
shadow plan is still published, because it is worth analysing - it is labelled,
not suppressed.

**3. Any-transport is its own kind.** `transport: {kind: "any"}` versus
`{kind: "ports", protocol, ports}`. Not an empty port list, which reads as
"nothing", and not an enumeration of well-known service ports, which would narrow
a deny to the ones somebody thought of. The digest and the ordering key read the
typed field.

**The consequence, measured on the real topology: all eight overrides now lower,
including `servers-to-management-deny`.** The only mandatory deny in the sources
was inexpressible an hour ago and is now an any-transport guard at position 0 of
its scope. Nothing unlowerable, no blocked scopes.

**A vanishing scope, fixed with it.** Scopes were derived from successfully
lowered rules, so a wholly unrepresentable matrix disappeared from the plan - and
a scope that is absent cannot be reported as unterminated, so the omission hid
itself. Scopes now come from the matrices.

**The validator gaps F1.3 named are closed.** A declared scope with no rules is
checked rather than skipped past an early return; a terminal whose effect is
`permit` is refused, because it closes nothing and shadows everything after it;
two terminals in one scope are refused; and positions must be unique and
consecutive from zero, which the edge check cannot see - rules with no precedence
relation between them are compared with nothing.

Three tests failed on this change and all three encoded the old behaviour the
review called defective. They now assert the new.

40 tests across the two plugins; 359 in the netmodel and matrix suites. Artifact
parity identical across 147 files.

### PR2, part two, 2026-09-14 — the divergence with the reference model, closed

The framework could express an any-transport rule and `netmodel` could not, which
made the differentials meaningless for exactly the rule that matters most.

`ANY_TRANSPORT` is now a shape in the reference algebra: `protocol="any"` with
`ports=None`, and a template carrying both is refused - listing some ports would
narrow it to the ones somebody thought of. `Flow.admits` decides transport
coverage, `intersect` lets an any-transport side absorb the other's shape so a
conflict witness is still a flow an author can look at, and the guard index
gained a lookup under `ANY_TRANSPORT`, without which the index would have
silently narrowed the search past the one guard that covers everything.

**The independent interpreter reads it too, not by importing the lowering.** A
rule may constrain every transport without being terminal; reading that as a
ports rule with no ports would have matched nothing at all.

**Checked where the permits are silent**, which is the point: an any-transport
deny is asserted over protocols and ports no permit mentions. A deny narrowed to
somebody's port list is the failure nobody notices, because the restriction that
was never written leaves no trace.

*A defect this surfaced.* `terminal_rule` built its flow from `protocols[0]` and
port 0 - arbitrary, and broken the moment an any-transport permit put `"any"`
first in that list. A terminal assembled from whichever protocol sorted first was
never closing its scope, only appearing to. It is an any-transport rule now.

**On the real topology the reference model now derives all eight overrides**,
including the mandatory deny. The guard-precedence test no longer skips: 334
netmodel tests, **zero skipped**, down from one. The test that recorded the gap
now records its closure.

*The name was wrong, as the review said.* Lowering every legacy override of a
scope says the compiler represented what was written; it says nothing about
approval or independent validation. `lowering_complete` and `strict_eligible` are
now separate, and the second is **empty** with a stated reason rather than
inheriting a completeness result.

375 tests across the two plugins and the netmodel suite. Artifact parity identical
across 147 files.

**Still open, and the next criterion.** Independent completeness: the validator
does not yet compare the plan against source requirements. `expected_overrides` is
published by the compiler and is *not* an adequate source for that check - the
compiler can lose a rule and its own record of it in the same edit, which is
precisely the case the check has to catch. The validator needs the normalized
intent through its own manifest contract, and must compare semantic coverage
rather than counts. The completion criterion is stated: remove UDP, a guard, or a
whole scope from the plan **and** from the compiler's metadata together, and the
independent check must still find the loss.

### PR2, part three, 2026-09-14 — the validator reads the source, not the plan

Against the four conditions set for this change.

**1. Independent input.** The validator consumes `normalized_rows` in its own
right and derives what the sources require by lowering them again. Not from the
plan, and not from `expected_overrides`: a compiler can lose a rule and its own
record of that rule in one edit, which is exactly the case the check exists to
catch. The consume is `required: false` at the registry level on purpose - a
missing source must be a visible `E7008` saying the completeness check did not
run, not a plugin the registry quietly declined to execute.

**2. Two-way semantic comparison.** `E7083` for anything accepted outside the
source's authorization, `E7084` for a required flow the plan does not carry. Both
directions, because one-way inclusion is satisfied perfectly by an empty plan -
which accepts nothing unauthorized and carries nothing at all. A test asserts
exactly that case reports both `E7084` and `E7090`.

**3. Traceable coverage, separate from behaviour.** `E7090` when a mandatory deny
the source states has no rule in the plan, `E7091` when a declared scope is
missing. Both registered before use. The guard case is the one behavioural
equivalence cannot reach: deleting a guard leaves every verdict identical,
because the terminal denies what the guard denied - the outcome matches and the
obligation is gone.

**4. An independent flow space.** Built from the source obligations, so a deleted
UDP rule still has its flows probed and cannot vanish along with itself. The
plan's own coordinates are unioned on top, and that turned out to be necessary: a
smuggled permit on a port the sources never mention was invisible until the union
was added. Deriving the space from the plan hides losses; deriving it only from
the intent hides additions.

**The mutant the review named passes.** Removing a rule together with the
compiler's metadata about it - the UDP permit, the mandatory guard, and a whole
scope, each with `expected_overrides` adjusted to match - is detected in all three
cases.

*A false positive the check found in itself.* On first run against the real
topology it reported six accepted flows as unauthorized. The cause was mine: I had
written one function to answer two questions. An any-transport permit authorizes
every transport between its endpoints and belongs in the authorized set in full;
it contributes **no** finite required flows, because "every port" is not an
availability objective anyone stated. `_authorized` and `_required` are now
separate, and enumerating a requirement nobody made is the mirror of dropping a
restriction - equally wrong, and easier to miss.

26 validator tests; 366 across the netmodel, compiler and registry suites.
Artifact parity identical across 147 files.

### PR2, part four, 2026-09-14 — A, Q and the difference between them

Two corrections from review, both to work finished an hour earlier.

**A permit is not an availability obligation.** `_required` derived Q from the
permits, which invents a claim nobody made and then reports it as met. It had
already excluded any-transport permits for exactly that reason without noticing
the reason applied to finite ones too. Q now comes only from a declared
`availability_requirements` list, and where none is declared `W7002` says
SEC-AVAIL is **unverified rather than satisfied**.

The contract as stated: A is what is allowed with guards applied; Q is what must
work under declared prerequisites; `Q subseteq A`; SEC-AUTH is `Accept subseteq A`;
SEC-AVAIL is that applicable requirements in Q are carried.

`Q subseteq A` is enforced as a **contradiction**, `E7092`. A requirement a
mandatory deny forbids is two source statements disagreeing, and it blocks the
model - it is never settled by weakening the guard or by dropping the
requirement. A test asserts it does not also report as the plan's own failure.

The four regressions now exist:

| Case | Reported as |
|---|---|
| An undeclared permit missing from the plan | `E7093`, lowering incompleteness - **not** `E7084` |
| A declared required flow not carried | `E7084` |
| A required flow a guard forbids | `E7092`, a contradiction |
| No requirements declared | `W7002`, unverified |

An explicitly empty `availability_requirements: []` is distinguished from absent
data: the first is a decision - nothing here has to keep working - and the second
is not, so only absence warns.

The earlier "an empty plan must give `E7084`" test was wrong and is qualified: an
empty plan fails availability only when an applicable non-empty Q exists.
Otherwise its emptiness is caught by coverage, as `E7090` and `E7093`.

**Probes now reach outside every enumeration.** Union of intent and plan
coordinates is necessary and not sufficient: a wildcard permit agrees with the
authorization on every value anyone listed and permits more beyond them, so
"matches on all probes" would be a property of the probe set. A port and a
protocol from outside every list are added, and a test asserts they really are
outside rather than trusting the constants. Endpoints get no representative -
they are opaque atoms from a closed enumerated set, and inventing one would probe
a zone that does not exist.

On the real topology: no errors, two `W7002`. 33 validator tests, 399 across the
suites, artifact parity identical across 147 files.

### PR2, part five, 2026-09-14 — three limits made checkable

Fixed before the strict boundary, because each is a way the checks above could
have reported a plan clean while missing something.

**Unsupported semantics are refused rather than approximated.** Measured first:
a port range `"1000-2000"` raised a `TypeError` the registry turned into a plugin
with no output, and `{"!tcp": [22]}` was accepted as a protocol literally named
`"!tcp"` - two rules emitted, nothing in `unlowerable`. The second is the worse
one: a shape lowered as if understood produces a plan the semantic checks cannot
see past, and they then call it clean.

`E7094` now refuses a protocol outside the implemented set, a non-integer port
selector, and a port outside 1-65535, and the affected scope is blocked entirely.
The reason is not fastidiousness: the probe classes that make the semantic check
meaningful are derived from the shapes the algebra supports, so an unsupported one
is invisible to them by construction. Ranges, CIDR conditions and negations need
their own equivalence classes before they can be lowered, and until then the
refusal is the honest answer.

**The endpoint set is closed by contract, not by convention.** `E7095` refuses a
rule naming an endpoint no source declares. The probe space enumerates endpoints,
so an unknown one is not merely undeclared - it sits outside every check the space
can perform, and its rule would be examined by nothing. The terminal is exempt: it
names the whole scope, which is a different kind of statement.

**An empty Q is a value; a decision is a claim.** `availability_requirements: []`
is more than absence and still not evidence that anyone decided anything. An
attested empty set needs `availability_waiver` with an owner and a rationale -
both, because one without the other is a label. Unattested emptiness keeps
reporting `W7002`, and the test that previously accepted a bare empty list is
corrected.

43 validator tests, 366 across the other suites, artifact parity identical across
147 files. On the real topology: no errors, the same two `W7002`.

### The strict admission boundary, 2026-09-14

Nothing renders the security plan yet, which prevents application and does not
constitute a boundary - one written after the first consumer arrives is written
around it. `plugins/validators/strict_admission.py` is the contract every strict
backend consumer must use.

| Condition | How it is refused |
|---|---|
| `legacy_shadow` regardless of lowering | Provenance must be `strict`; completeness of lowering never substitutes |
| A provenance swap alone | Approved intent **and** a passing independent check, both required |
| A plan changed after checking | Admission computes the digest itself and compares with the one the verifier recorded |
| Missing inputs, blocked scopes, incomplete checks | Each refuses on its own |
| A refusal enabling legacy | `legacy_fallback_permitted` is `init=False` and always false |

**Two test-design points that changed the shape of this.**

*A positive control comes first.* An implementation that refuses everything
passes every negative test ever written, so a prepared strict fixture must be
admitted - and a second test removes one condition at a time from that control to
show each is load-bearing.

*The digest is computed, never accepted.* A mutated plan that also recomputes its
own `digest` field is self-consistent, and trusting the presented hash would let a
changed plan certify itself. `content_digest` excludes any `digest` the payload
carries, and a test asserts editing that field alone does not change the plan's
identity.

**Checked on disk, not from a return value.** The pipeline test asserts no strict
artifact exists after a real run while admission is refused, because a function
that says no while something else writes the file is exactly what this guards and
is invisible to a test that reads an answer. The artifact paths are declared
explicitly so their absence is checkable rather than incidental; when the first
renderer lands, its output path joins the list and the guard starts biting.

**On the real topology the plan lowers completely, verifies with no errors, and
is still refused** - because `provenance` is `legacy_shadow`. That is the main
negative test, and it passes while shadow analysis stays available.

*What the waiver is and is not.* `availability_waiver` with an owner and a
rationale makes a statement traceable. Whether that person may waive it, and
whether the waiver was agreed, belong to admission and are not properties of two
filled-in strings.

16 contract tests, 8 pipeline tests, 421 across `plugin_contract`, `plugin_api`,
`kernel` and `test_plugin_registry`. Artifact parity identical across 147 files.

### Code review of `12f4e836` — six findings, all reproduced and fixed

`docs/reports/2026-09-14-adr0118-0119-code-review-12f4e836.md`. Every one was real
and every one was mine.

**Q was checked against half of its own definition.** `Q subseteq A` verified only
that no guard forbade a requirement, never that a permit covered it - so UDP/53
required with TCP/443 permitted passed silently. And `_flow_space` omitted the
availability coordinates, so a source allowing any transport and requiring TCP/53
had **no probe for TCP/53 at all**: replacing that permit with a deny returned
SUCCESS with no diagnostics. Both halves are now checked and the requirement's own
coordinates are probed.

**Guard coverage used an incomplete key** - scope, origin and transport, without
endpoints or effect. Moving a mandatory deny's destination left the key unchanged
and the loss invisible, because the terminal denied the flow either way: identical
behaviour, restriction gone. That is precisely the case traceable coverage exists
for, and it was the case it missed.

**The representatives "outside every enumeration" were constants.** A source
listing 64999 or `sctp` put them back inside, and the wildcard permit passed
again; the test asserting their independence proved it for one fixture. They are
derived from what is present now, and the property is tested over enumerations
that deliberately contain the old constants.

**An undeclared scope was never checked.** The semantic loop iterated the source's
scopes, so a scope the plan invented - with an any-transport permit and a correct
terminal - was asked nothing. An undeclared scope is exactly where an unauthorized
permit would hide. The loop now covers the union.

**Unsupported semantics were refused in one place and not the other.** The
compiler blocked a port range and the validator then crashed on it with `E4102`
instead of reporting; `!tcp` was still read as a protocol token there; and
`ports: "tcp:443"` became an any-transport permit in **both**, turning a typo into
the broadest rule the model can express. A malformed selector is not a missing
one, and both now say so. A test asserts the two supported-protocol sets agree,
since they are written twice on purpose.

**The committed lock did not describe the committed content.** At `12f4e836` an
isolated worktree fails `E7824`, while the working tree passed. *Corrected
2026-09-14:* I attributed that to a lock regenerated before the last edit. It was
not - the external review of `5e02bf70` established the real cause, five
gitignored `*.egg-info` files inside the integrity hash, and reproduced the
committed hashes of older revisions by adding exactly those rows. The guard below
is still worth having, and it was guarding the wrong thing on its own. `tests/test_framework_lock_matches_content.py`
now runs the strict verifier, so a divergent lock fails here rather than in
someone else's checkout.

*The pattern worth keeping.* Four of the six were checks that returned SUCCESS on
a plan with something removed. A check whose failure mode is silence needs a
counterexample per claim, not per function - and the review produced them by
mutating the source rather than by reading the code.

53 validator tests, 210 across the targeted integration selection, 421 on the full
`plugin-contract` gate, 334 netmodel. Artifact parity identical across 147 files;
the real topology reports no errors and the same two `W7002`.

### Self-review, 2026-09-14 — by mutation, not by reading

A self-review looks for defects with the assumptions that produced them, so this
did not read the code. It did what actually found things last time: mutate the
source and the plan, and require each claim's checker to fire.

**Fourteen mutations, thirteen caught, one apparent miss that was my harness.**
The wildcard-permit case inherited `effect: deny` from the rule it was copied
from, so it inserted a wildcard *deny* - and `E7084` was the correct answer. With
the mutation written properly, all three smuggling shapes - any-transport, an
unlisted port, an unlisted protocol - report `E7083`. No false positives: the
unmutated plan and a reordered rule list are both clean.

**A real hole, found by a different axis.** Enumerating the allocated `E70xx`
codes against the code that raises them showed seven with no raiser at all. Four
- `E7085`-`E7088` - are the obligations implemented in `netmodel` and not yet
mounted in the framework, which is expected and now stated. `I7001` and `W7001`
were registered speculatively and raise nothing, which is the thing D7 warns
against and they are mine.

And `E7094` was registered for unsupported predicate semantics and **raised by
nobody**. The compiler refused the selector and recorded a reason in a channel;
the validator's source reader returned `None` silently. So the scope was blocked
and the operator running the compile saw nothing. A code with no raiser is a claim
nobody checks. `_obligation` now returns its refusal reason, the validator reports
`E7094`, and six tests cover every refused shape.

*Two instrument errors on the way, both mine.* The first scan looked only for
`code=` keyword arguments and reported `E7090` and `E7093` as unraised - while
the mutation tests had just shown them firing. The second fix missed the
availability call site of `_obligation` and crashed the plugin with `E4102`; the
test suite caught it immediately, which is what it is for.

59 validator tests, 335 netmodel, artifact parity identical across 147 files, the
real topology unchanged at two `W7002`.

#### Acting on it, same day

`W7001` and `I7001` are withdrawn. Neither number is reused - governance rule 2 -
and the catalog carries the reason so a reader meeting one in an older report can
still find out what it meant. `W7001` was the wrong severity as well as unused:
`class.compute.workload.yaml` says an explicit `enabled: false` disables an
inherited record *without deleting it*, "so a reference to it is an error rather
than a silent miss". A warning cannot say that. The rule is now `E7025`, and it
is raised in the two places a reference can land on a disabled record:

* a publication whose `endpoint_ref` names a disabled attachment. This used to
  report `E7040` "not an attachment on lxc-host", which sends the author looking
  for a typo in a name that is spelled correctly. The disabled record is also no
  longer offered in the `Declared there:` list, since it is not a candidate.
* a binding whose `policy_ref` names a disabled policy. This was worse than a
  misleading message: the binding was validated *against the disabled template
  and passed*, recording an approval against a policy that grants nothing.

**The measurement instrument was the second finding.** Enumerating allocated
codes against their raisers is the check that caught `E7094`, and it existed only
as something I typed once. It is now `test_every_allocated_code_is_raised_or_recorded_as_waiting`,
and running it properly found more than the self-review had: not four unraised
codes but **seven**. `E7042` (publication mechanism against enforcer capability)
and `E7062` (an unapproved binding used as authorization) are also registered
with nothing to raise them - `E7062` because the framework still compiles legacy
matrices, so no binding becomes a grant anywhere it could fire. All seven are now
a ledger that names the mount point each is waiting for; it may shrink and cannot
grow. A control run registering a fake `E7099` makes the test fail, so it has
teeth.

The scan uses its own AST walk rather than `scan_emissions`, which counts a
`code=` keyword or a CODE-named constant and therefore cannot see
`self._diag("E7025", ...)`. That blind spot is what produced the false
`E7090`/`E7093` report during the review.

**Not concluded, and a self-review does not change that.** It found one real
defect, acting on it found two more, and none of that speaks to what nobody
thought to mutate. PR2 and the strict boundary still need an outside review
against this code and the exact gate commands. F3 through F5 remain open, and so
does G3.

### External review of `5e02bf70`, and what it closed

`docs/reports/2026-09-14-adr0118-0119-strict-review-5e02bf70.md`. It confirmed the
earlier fixes and produced six counterexamples against the admission boundary,
each of them an *admitted* plan that should not have been.

**The chain was open at both ends.** `approved=True` was read for its truthiness
alone - so an approval issued for a different scope and a different binding
admitted this plan - and `complete` meant only that the source input had been
readable, so a genuine record reporting `W7002` was a pass. Admission now binds

    approval -> the exact intent that was checked -> the verification -> the plan

by digest. The validator computes an `intent_digest` over the obligations it
lowered for itself, the approval names that same digest and the scopes it covers,
and a missing field is refused rather than defaulted: an absent `errors` is not
zero errors. `complete` is gone. In its place the record carries a status per
obligation per scope - `pass`, `fail`, `unverified` - because there are three
answers and one boolean could only carry two.

That last distinction is what the real topology now shows. Both matrices come
back `SEC-AVAIL: unverified`, errors 0, and nothing is admissible - not because
anything is broken, but because nobody has said what has to keep working.

**Three scope lists that contradicted each other went unread.** A plan whose
`strict_eligible` named a scope its `lowering_complete` did not, with non-empty
`unlowerable` and empty `blocked_scopes`, was admitted on the strength of
eligibility being non-empty. Each list is now checked against the others, and
requesting a scope outside the eligible set is refused - admission is per scope,
so a renderer receives the projection that was admitted.

**A scope stating only `Q` was skipped twice over.** `_source_obligations` moved
to the next row when a scope declared no `policy_overrides`, so its requirements
were never read; and `_check_semantics` returned before the loop when the whole
source had no permits and no guards. A scope saying only "TCP/53 must work", with
a plan carrying nothing but a terminal, came out at errors 0 and complete. Both
early exits are gone, and `Q ⊄ A` is now reported where `A` is empty.

**The write boundary was never exercised.** The pipeline test ran a compiler and
a validator and then asserted that two directories did not exist. No generator
ran, so it passed whether or not any control over writing existed. There is now a
test-only generator in `tests/fixtures/strict_writer/` that runs in the generate
stage, consumes the plan and the record through the same contract a renderer will
use, and writes one marker only when admission says yes. The positive control is
a real check of the exact plan - the validator examines it and publishes its own
record, and nothing is edited afterwards. A bypass mutant that replaces
`evaluate` with one that always admits *does* write the marker, which is what
makes the negative cases' silence mean something.

**A legal source crashed the probe builder.** A permit naming all 65535 ports is
inside the finite-port contract; `_port_outside` raised `AssertionError` on an
empty complement, and after that was fixed the 524288-probe cartesian product hit
the 30s plugin budget - which reads as a crash either way. The probe set is now
one representative per equivalence class: two ports belonging to exactly the same
listed sets are indistinguishable to every rule and every obligation here, so
probing both proves nothing the first did not. The class outside every set is
kept, because that is where a wildcard permit hides; when the sets already cover
1-65535 that class is empty, which is an ordinary source.

**Identity excluded too much.** `content_digest` stripped every field named
`digest` at any depth, so changing a nested `evidence_ref.digest` left the plan's
identity unchanged and kept its admission. Only the payload's own top-level
identity is excluded now, and a nested digest is refused as an unsupported shape
rather than digested around.

**`E7824` had a different cause than I recorded.** I wrote that the lock had been
refreshed before the last edit. The review established what it actually was: the
integrity hash covered five gitignored `*.egg-info` files written by
`pip install -e`, so a clean checkout and an installed working tree computed
different hashes. Adding exactly those five rows to the computation reproduces
the committed hashes of older revisions. Installation and build metadata is now
excluded from the distribution, and a second test walks the distribution and
fails on any file `git ls-files` does not list - the class, not that instance. A
tree built from tracked files alone now verifies.

**The raiser scan was wrong a third time.** Requiring the code literal to be a
call argument refused the lookup-table mutant the review asked for and missed
`E7090`, which reaches `emit_diagnostic` through a loop variable. The question it
asks now is narrower than "is this emitted" and wider than one call shape: is the
code named inside a function that emits diagnostics at all. A module-level table
does not satisfy it. It is still a necessary condition rather than proof, and it
says so.

*Not closed.* PR2 and the strict boundary still need a review against this code.
No producer of approvals exists, so in the real pipeline every plan is refused
twice over - at provenance and at approval - and the positive control is a fixture.
F3 through F5 remain open, and so does G3.

### External review of `c5a5addc`, and what it closed

`docs/reports/2026-09-14-adr0118-0119-review-c5a5addc.md`. Two blocking defects and
three contract gaps, all reproduced with the real compiler and validator rather
than hand-written records.

**R2 - a requirement was accepted and then discharged by nobody.** Availability
requirements shared `_obligation` with policy overrides, and a portless override
means *every transport* - a real and checkable restriction, and the only mandatory
deny in this topology. The same default on a requirement means "every port must
keep working", which this implementation cannot check: `_required` skipped
any-transport entries and `_check_requirements_are_permitted` iterated an empty
port tuple. Two skips, and between them the requirement was never examined -
errors 0, warnings 0, SEC-AVAIL **pass**, and the plan admitted. `W7002` did not
fire either, because the list was not empty.

The two grammars are now separate, and only in that one place. An unbounded
requirement is refused at the parser with `E7094`, which leaves SEC-AVAIL
unverified for its scope and blocks admission. The portless *override* still
means every transport.

**R1 - the consumer API reopened the gap `evaluate` closes.** `admitted_projection`
filtered scope names and never checked that the plan it was handed was the plan
that had been admitted, so a caller could evaluate one plan, change a rule, and
take a projection of the changed rules stamped with the admitted digest. It also
returned the plan's own rule mappings, so editing the projection edited the plan.
Identity is re-established against a snapshot taken first - hashing the caller's
object and copying afterwards leaves the same window open, only narrower - and a
mismatch raises rather than returning empty, because an empty ruleset handed to a
firewall renderer is not a safe way to report a programming error.

**R3 - the fail-closed guard was spelling-sensitive.** Applicability was inferred
by searching the serialized plan for quoted words. `path` made SEC-PATH applicable
and refused the plan; `paths` with identical content was admitted. The comment
claiming a future construct would necessarily be refused was therefore stronger
than the code. The plan shape is closed now: known fields, reserved
obligation-name fields, and everything else refused.

**R4 - approval was not bound to the attestation it rests on.** The intent digest
carried `availability_attested` as a set of scope names, so replacing a waiver's
owner and rationale left it unmoved and the previous approval discharged a claim
somebody else now signs. The permission set genuinely is unchanged - that is why
this did not belong in semantic identity. It has its own `evidence_digest` now,
and the approval names both.

**R5 - the epoch was a label.** The approval had to carry a non-empty epoch
string, but equality was conditional on the plan having one, and the strict
fixture has none - so the same plan was admitted under `old-epoch` and
`new-epoch`. `evaluate` takes `expected_epoch` from the caller's deployment
context and refuses to decide without it. Freshness and revocation remain F4; what
this closes is the pretence that a filled-in string implemented them.

*Not closed.* PR2 and the strict boundary still need a review against this code.
G3 is not closed by a bounded fixture. F3 through F5 and W05 remain separate work.

### Follow-up review, same day: the grammar and the input types

The reviewer confirmed the six earlier counterexamples are refused and found
three more, all of the same shape - a check that reads a value without deciding
whether it can.

**Closing the field names closed half the shape.** `transport.kind:
not_implemented`, a transport with no `kind`, and `schema_version: 999` all spell
their keys correctly, so the closed key set admitted every one. A consumer
reading any of them would have to guess what they mean, and every guess is a rule
nobody authorized. `malformed_constructs` states the grammar: the transport kinds
this contract acts on, a non-empty port list inside 1-65535, `effect` in
`{permit, deny}`, a boolean `terminal`, an integer `position`, a named scope. A
test asserts it accepts what the compiler emits - a grammar stricter than the
producer refuses every real plan and would look like a working boundary.

**`approved: "false"` was consent.** A truthy string read as a boolean is this
whole boundary failing on a type it never asked for. `is not True` now, and the
same for `source_available`. Checked through the writer as well as in the verdict,
because a return value nobody acts on proves nothing.

**An empty `evidence_digest` disabled its own comparison.** `elif evidence_digest
and ...` meant a record naming no evidence matched every approval. An absent
digest is refused; it compares equal to nothing, which is not the same as matching
everything. The intent digest had the explicit check and the evidence digest did
not - the asymmetry was the defect.

### F3, F4, F5 — the three obligation checkers the post-fix review left open

All three were measuring something adjacent to what they claimed.

**F4, SEC-STATE: the deadline was measured from the session.** `now -
established_at` compared against a revocation deadline answers "how old is this
connection", not "has the agreed grace period run out". The review's probe -
`established_at=0, now=100, deadline=10` - reported two survivors at the instant
of the epoch change, before any grace had begun. The model also could not express
*when* revocation started. `Revocation` now carries `effective_at` and
`superseded_by`, the deadline is absolute, and the epoch link is checked: a
revocation from another transition raises rather than being applied to this one.

Two failures that were one: a session opened at or after `effective_at` gets no
grace, because nothing is winding it down. It is a new connection under a policy
that does not authorize it, which says the new policy is not in force - a
different thing to do about it, so a different kind in the report. And a related
session is now judged by its **parent's** authorization, following the chain to
its root; judging it on its own tuple, typically a port no rule mentions, answered
a different question. A parent nobody listed is an orphan rather than an
assumption.

**F3, SEC-CAP: one level deep and one mode for the whole plan.** Freshness and
delegation were checked over the chosen offers, so the review's three-level probe
- a selected offer whose prerequisite depended on an expired, undelegated one -
came back with no conflicts. Expansion is transitive now, and every node in the
closure is checked; a conflict says whether the offender was chosen or required.

Mode, ownership and capacity are `resource`-scoped. Requiring one mode across the
whole selection refused perfectly good independent components - two firewalls on
different devices may legitimately differ - and an offer stating a mode without
naming what it acts on is `unverified`, because "which interface?" is a question
somebody has to answer.

`content_digest` was accepted from the caller as any non-empty string, so the
duplicate-body check compared labels: two offers with different limits could
carry one digest and look like one body. It is computed from the offer's semantic
core now, separated from an evidence annex - re-validating an attestation does not
change what an offer promises, and changing its limits does.

And the return type changed, which is the part that matters most: an empty
conflict list was read as "these work together" when it meant "nothing I could
check disagreed". `Feasibility` carries conflicts, unknowns and a status, and an
unstated capacity makes it `unverified` rather than satisfied.

**F5, SEC-TRANSITION: a sequence proved by never being attempted.** A strategy
returning no mutations was simulated into zero states, and zero states have no
state outside the envelope. The review's probe - empty flow space, expired
envelope, arbitrary digests - returned `[]`, and `[]` read as proof. Five things
are checked around the replay now: the envelope's digests must be the digests of
these plans and it must not have expired as of a moment the caller supplies; the
flow space must cover every flow the envelope admits or the new plan must carry;
the mutations must be exactly the diff, so nothing is skipped, invented or applied
twice; the final state must *be* the new plan rather than merely a safe one; and
at the end `Accept(R_final) ⊆ A_new` with every required flow still carried.

`UNSUPPORTED` was skipped alongside `DENY`, and they are opposites: a deny is a
rule saying no, an unmatched flow is no rule at all. On a default-allow backend
that is an open flow, and the window between removing a terminal and adding the
next one is exactly where it appears.

*What none of this proves.* The simulator re-derives canonical order at every
step, so it reasons about rule sets rather than about the RouterOS or Terraform
operations that realise them. That remains a backend-level test contract, and the
review said so first.

### W05 / A24 — zone membership is derived once

The characterization left an open decision and two options. The parity-preserving
one was taken: **the core learned `additional_networks`**, so the rendered address
lists are unchanged and the cutover is a refactor rather than an exposure change.
The other option - deciding the overlay CIDRs belong to a different construct -
moves the rendered lists and stays open as a source change for a policy owner.

Three things changed, and the second one is the reason the first one worked.

`security_matrix_compiler` reads `additional_networks` from the trust zone and
appends its CIDRs after the domain CIDRs, deduplicated, in authored order. That
field was authored L2 intent the core could not see, so the generator was
compensating for a gap rather than disagreeing.

Zones are resolved in **sorted** order. An intermediate measurement is what
justifies it: with the field read but the zones unsorted, the rendered address
entries were an identical multiset - none added, none lost - in a different order,
because the compiler iterated `zone_refs` and the generator had iterated rows.
That is divergence 2, and closing it made the cutover byte-identical instead of
merely equivalent.

`object.mikrotik.generator.terraform` declares `security_matrices` and
`vlan_cidr_map` as optional consumes and hands both to the projection, which then
derives no zones at all. The projection's local derivation is kept as a **parity
oracle**: a differential runs it against the rendered artifact, which the pipeline
produced from the channel. Deleting it would remove the only thing that could
notice the two disagreeing, and a negative control - stripping
`additional_networks` from the oracle - fails that differential.

*Measured.* One compile before and one after, fixed timestamp, compared with
`compare_artifacts.py`: **163 files, identical outside the declared exclusions.**

*Divergence 3, closed the same day.* The projection selected address domains by a
substring of the object ref, so five routing policies passed the filter, harmless
only because they declare neither `trust_zone_ref` nor `cidr`. Both sides select by
declared class now, with separate copies of the class list and a test asserting
they agree - the oracle has to be able to disagree with the core, which is the
point of keeping it. Artifacts byte-identical again.

*Still open, and now the only W05 item.* Making the overlay networks address
domains in their own right. `netmodel` derives zone prefixes from domains alone and
still shows the delta; a computed check says modelling each overlay as a domain in
the same zone yields exactly the rendered set. That proves parity **for the address
lists**, not for every artifact a new network class touches - and the class would
have to carry a prefix and a zone ref without rendering a VLAN interface, which
`class.network.vlan` does. A source change for a policy owner, with its own
artifact comparison.

### External review of `b326cd19` — the terminal that closed part of its scope

`docs/reports/2026-09-15-adr0118-0119-review-b326cd19.md`. One P1, reproduced
through the real validator and the generate-stage writer, with the earlier
counterexamples confirmed closed.

**Presence and effect were checked; the predicate was not.** A terminal narrowed
to `sources: [z.a]` left `z.b -> z.a UDP/9999` reaching no rule at all - inside
the closed endpoint set - and the run came back errors 0, four obligations
`pass`, admission granted, marker written. A terminal narrowed to `tcp/53` was
worse than incomplete: the interpreter ignored a terminal's transport, so the
verifier proved an unconditional deny while the projection handed the consumer
the finite predicate. One plan, two meanings.

The invariant is stated and checked now: `deny`, last, no named endpoints,
`transport: {kind: any}`. Anything narrower is refused rather than interpreted,
because the residue cannot be proved empty - the endpoint set is closed by
enumeration and the transport space is not.

**Termination is its own obligation.** `unsupported` was skipped unless the flow
happened to be in `Q`, so whether an execution had to terminate depended on
somebody declaring an availability objective. `E7096` reports any in-scope flow
that reaches no rule, regardless. It is deliberately *not* repaired by reading an
unmatched flow as a deny: that credits the plan with a rule it does not carry, and
on a default-allow backend the true outcome is the opposite of a deny.

**One meaning, enforced in three places.** The interpreter honours a terminal's
transport; the validator refuses the narrow shape; and `strict_admission` forbids
it in the plan grammar, so a record that somehow reported `pass` still does not
admit the plan. Either of the last two alone would close the finding - both means
neither can be edited out quietly.

**The reference model had the same shape.** `netmodel.interpret` special-cased
terminals to ignore protocol and port. It does not now, and `unterminated()` names
the residue the way `E7096` does. The two implementations were wrong in the same
way, which is worth recording: a differential only catches what the two do
differently.

*Tests.* Three narrowed-terminal refusals at writer level with the counterexample
flow deliberately **outside** `Q` - inside it the test would prove availability
and leave termination unguarded, which is how this went unnoticed - plus the
full-scope positive control that still writes, a rule-after-the-terminal refusal,
and the reference-model mutants.

### Review of `b0a9d964` — four unproven passes, and the merge that carried one

`docs/reports/2026-09-15-adr0118-0119-obligations-review-b0a9d964.md`. Three P1
and one P2, all reproduced through the real validators and the generate-stage
writer. The finding is the one this work has been refusing everywhere else, made
by me in a new place.

**R1 - presence became proof.** SEC-STATE passed on a non-empty sessions list and
an epoch; SEC-TRANSITION on a non-empty previous plan and envelope, with a message
claiming the sequence was *replayed* while nothing replayed anything; SEC-PATH on
the plan's own `demonstrated` list matching its own `cases`; SEC-CAP on a
capability name appearing as a key. A session carrying a revoked epoch, a previous
plan with no rules, a self-asserted demonstration and a disabled offer with no
evidence were all admitted, marker written.

The four pass branches are gone, and so are the failure branches that rested on
the same non-check. Each returns `unverified` with the missing input named, and
does so *even when fields that look like the input are present* - which is the
part that matters, because the counterexamples all had the fields.

`E7085`, `E7087`, `E7088` and `E7089` went back on the awaiting-a-mount ledger and
are no longer named in the module: a number sitting in a table inside an emitting
module reads as raised to the registry scan while no branch can reach it.

**R2 - partial success in SEC-NAT.** Only the mapping-shaped declarations were
selected, so a readable transform beside an unsupported string gave the scope an
overall pass; a subset of the transforms checked, reported as all of them. And the
original identity was `sources -> destinations`, so a permit on TCP/53 and a deny
on TCP/443 between one pair of endpoints looked like one original and their
collapse went unseen.

Every declaration is parsed under a closed form now, one unreadable declaration
decides the scope, and the identity carries transport and effect. SEC-NAT still
reports a collision - that is a demonstration - and no longer reports a pass:
collision freedom over this identity is necessary, and the composition proof ADR
0119 asks for is over original and current tuples with their context.

**R3 - a stale verdict under a fresh digest.** The partial record carried no
identity, so a `pass` produced for one plan, with the plan changing before the
merge, was stamped with the new plan's digest while a fresh run said `fail`. The
record names the plan it examined; `E7097` refuses a mismatch; the merge takes
only the five obligations that producer owns, never overwrites the four decided
beside them, and validates the counter types it adds.

**R4 - two answers to one question.** The producer decided applicability per
scope and admission gathered rule fields across the whole plan, so a transform in
one scope refused a second scope where the producer had correctly said
`not_applicable`. `applicable_obligations` takes a scope; plan-level fields still
apply everywhere.

*What this leaves.* A mounted channel, a stage graph, a record with identity - and
exactly one obligation that can demonstrate anything. That is the honest state,
and it is less than the previous commit message claimed.

### Approval producer — a proposed contract, not an accepted one

`adr/0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md`, 2026-09-15. Status:
**Proposed; not accepted or implemented.** Recorded here so the plan references
it; referencing a proposal is not adopting it, and nothing in this repository
implements it.

What it asks for, in one line: a signed, source-controlled L7 review decision
authenticated against an operator-pinned authority context, verified by a
validate-stage producer that publishes a typed `network_approval` on a declared
channel. The producer *verifies* an existing decision; it never concludes that a
human approved because compilation succeeded.

Three things in it are worth carrying into any implementation, because each is a
mistake this work has already made once in a different place:

* **An approver is an authenticated principal, not a string.** Not a commit
  author, a CODEOWNERS entry, an OS user or an `approved_by` field. Self-approval
  is not a single-operator convenience, and a different spelling of one identity
  is not a second person.
* **Four facts with four authorities**, and none substitutes for another: a
  proposal names useful traffic, a principal approves resolved intent, a verifier
  says the plan preserves it, admission permits a write. The approval record
  carries references and review claims - never a second copy of the rules.
* **The plan digest is not the approval subject.** Approval binds intent and
  evidence; the verifier binds the plan to that intent; admission binds its
  verdict to the exact plan. Signing the plan would make re-approval a
  consequence of recompiling.

**What it does not do, stated by the document and worth repeating.** An approval
producer removes the absence of an authenticated decision. It does not turn
`legacy_shadow` into strict intent and it does not close G2 or G3. A real signed
decision cannot relabel a legacy plan - the document's own M1/M2 split says so:
M1 proves the producer is authentic on real sources while a legacy plan is still
refused; M2 needs a strict candidate produced and independently verified from
real typed sources, which does not exist yet. A positive path needs both.

*Not started.* The trust contract comes first - source of authority, approver
identification, the self-approval prohibition, how the authority context is
pinned, and the signed-decision format - and that is a decision to agree, not one
to infer from this document.

### The five remaining obligations, mounted

`base.validator.security_obligations` mounts the channel for SEC-NAT, SEC-STATE,
SEC-TRANSITION, SEC-PATH and SEC-CAP. They had existed only in `netmodel`, which
the framework cannot import, and mounting them had been refused for a good
reason: none of the five has its inputs in the pipeline, and a checker with no
input finds nothing. Reporting that as a pass is the empty-loop mistake.

**What is actually decided, stated precisely.** One of the five - SEC-NAT -
reaches a verdict, because its input is on the rule. The other four correctly
report the absence of evidence. That is a channel and one implemented decision,
not five completed checks, and the difference matters: an obligation that
abstains is not one that holds.

**Three answers, and the middle one is why this is now possible.** *Not
applicable* when the plan declares no field the obligation governs - nothing here
could violate it, and that is not a pass. *Unverified* when it applies and the
input is absent, with the missing input named in a `W7003`; this blocks strict
admission exactly as a failure does. *Pass* or *fail* when the check can run, with
`E7085`-`E7089` reporting the failures.

Applicability is read from declared fields, not from a word search - the mistake
`strict_admission` made and had corrected. The two vocabularies are the same list,
and a test asserts it.

SEC-NAT is the one whose input is already on the rule, so it decides today: two
transforms collapsing onto one translated target is `E7086`, and that path is
exercised end to end, through the writer. The other four abstain and say what they
are waiting for, which is a statement the record can carry and admission can act
on. On the real topology all five report *not applicable*, so nothing changed:
compile is unchanged at errors 0 / warnings 2, artifacts byte-identical.

**Two records, one merge.** The obligations validator publishes its own statuses
and error count; the plan validator merges both into the single verification
record admission reads, and adds the other plugin's errors to its own - a record
reporting zero while a sibling found one would read as a clean check. If that
plugin does not run, the five simply have no status, and an applicable obligation
with no status is a refusal rather than an assumption.

`E7085`-`E7089` left the "awaiting a mount" ledger. `E7042` and `E7062` remain on
it, and the raiser scan was widened from function scope to module scope to see a
code table an emitting loop indexes - with the mutant a review asked for still
refused, because a module that names codes and emits nothing is not a raiser.

**A framework lock is not reproducible from a commit alone.** A detached worktree
at `93c0c2f7` computes `sha256-f43ba202...` where the committed lock says
`sha256-baee680d...`, while the same revision in the main working tree matches.
Something inside `distribution.include` is therefore not tracked by git, so the
integrity hash depends on files a fresh clone does not have. This was found while
building the control run above and is unrelated to the declarations; it matters
because a lock that cannot be recomputed from source cannot serve as an integrity
check for anyone but the machine that generated it.

*Closed 2026-09-14.* The external review named the five files: the `*.egg-info`
directory `pip install -e` writes beside the package. `distribution.exclude_globs`
now excludes installation and build metadata, and
`tests/test_framework_lock_matches_content.py` fails on any distributed file that
`git ls-files` does not list. A tree built from tracked files alone verifies.

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

**Next bounded proposal, 2026-09-15:** [approval producer contract](../0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md)
(Proposed, not implemented). Defines L7 signed review, separately pinned approver
authority, declared validate-stage publication and the real-source positive path.
An authenticated approval does not change `legacy_shadow`; typed strict-source
lowering/verification remain prerequisites. Acceptance of this proposal and its
M1/M2 evidence do not by themselves close G3.


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

## 5A. ADR 0118/0119 dated implementation narrative (moved from `adr/REGISTER.md`, 2026-09-30)

`adr/REGISTER.md` is the ADR index; this narrative accumulated there from the first ADR 0118/0119 revision (2026-09-10) through the W07 migration order's completion and initial conformance-counterexample work (2026-09-30) and does not belong in an index table. Moved here verbatim, in its original order, with no content changed.

### ADR 0118/0119 revision — 2026-09-10

- ADR 0118 remains **Proposed**: one attachment/publication/policy model replaces
  the contradictory earlier D1-D21; capability-qualified scope and explicit legacy boundary.
- ADR 0119 remains **Proposed**: one authorization-preserving plan replaces
  producer priorities; formal obligations, safe transition and observed-state contract.
- ADR 0110 remains **Implemented** for its existing R1-R6 behavior; added an
  explicit cross-reference to the unimplemented strict-profile proposal.
- Supporting contracts: [migration and acceptance](0118-analysis/MIGRATION-AND-ACCEPTANCE.md),
  [formal obligations](0119-analysis/FORMAL-CONTRACT.md),
  [assurance profile](0119-analysis/ASSURANCE-PROFILE.md).
- No topology migration, backend qualification or compliance approval is implied.

### ADR 0118/0119 revision 2 — 2026-09-10 (SPC rebuild)

- ADR 0118 stays **Proposed**: adds D4.1 legacy-to-strict translation, a
  derived-field contract and D8 making the authoring surface a measured property.
- ADR 0119 stays **Proposed**: states plan ownership against ADR 0110's M1-B
  enforcer ownership and restores the explicit terminal-deny obligation.
- ADR 0110 stays **Implemented**; its R1-R6 behavior and `managed_by_ref`
  semantics are unchanged and now referenced explicitly by the proposal.
- Change record: [SPC rebuild](0118-analysis/SPC-REBUILD-2026-09-10.md).
- Still no migration, backend qualification, deployment or compliance approval.

### ADR 0118/0119 implementation analysis — 2026-09-10

- [Final implementation proposal](0118-analysis/FINAL-IMPLEMENTATION-PROPOSAL.md)
  and [reproducible evidence](0118-analysis/FINAL-PROPOSAL-EVIDENCE-2026-09-10.md).
- Recommends named source mappings, explicit binding lifecycle, two compiler
  plugins and a qualified transaction-based pilot; records baseline failures.
- Analysis only: these refinements are not adopted into normative rev 2 yet.
  Both ADRs remain **Proposed**; no runtime change, migration or deployment.

### ADR 0118/0119 revision 3 — final architecture proposal, 2026-09-10

- Both ADRs remain **Proposed**; [final architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
  is the current design review target, with synchronized examples/formal contract.
- Resolves named identity/inheritance, allocation ownership, binding lifecycle,
  original/frontend coordinate semantics, bounded profile and writer responsibilities.
- Supersedes rev 2 array authoring sketches and blanket consumer/domain input
  confusion. Earlier implementation exploration is historical and not adopted.
- No plugin count, backend priority, execution tool, code change or deployment
  is approved by this design revision. Human architectural acceptance is pending.

### ADR 0118/0119 revision 3.1 — applicability corrections, 2026-09-10

- [Final proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md) updated from the
  [rev 3 applicability review](../docs/reports/2026-09-10-adr0118-0119-rev3-applicability-review.md).
- [Review response and evidence](0118-analysis/REV3-APPLICABILITY-RESPONSE.md)
  records accepted conditions, qualified claims and fresh static counts.
- Adds route/tunnel/interface-NAT ownership, downward runtime realization,
  framework/core semantic authority and the existing Terraform/Ansible boundary.
- Clarifies scoped network version keys, local-key grammar, zone migration,
  planned-intent visibility, shared-chain composition and OOB prerequisites.
- Runtime, topology and generated artifacts are unchanged by the revision itself.

### ADR 0118/0119 architecture acceptance — 2026-09-10 (gate G0a)

- Both ADRs move from **Proposed** to **Accepted**: the architecture contract
  AD-01..AD-10 is adopted as the project's target network model.
- Basis: [rev 3.1 applicability review](../docs/reports/2026-09-10-adr0118-0119-rev31-applicability-review.md),
  which found all five rev 3 conditions closed, plus the
  [SPC acceptability review](../docs/reports/2026-09-10-adr0118-0119-spc-acceptability-review.md).
- Two remaining documentation defects were corrected before acceptance: the legacy
  upward `container_ref` inventory is 6 files, not 4, and authored `routing_mark`
  appears in 9 files, both now in the migration plan section 2C; acceptance scenario
  A24 makes single-source derivation of zone membership and `vlan_cidr_map` checkable.
- **What acceptance does not mean.** Gate G0b (named owners for HA-01..HA-10 and the
  tailoring record) is **not** closed. Gates G1-G8 are open, A01-A24 are unclosed, no
  backend is qualified, and no deployment, migration or device change is authorized.
  Compliance claims remain bounded by the assurance profile.
- ADR 0110 stays **Implemented**; its R1-R6 legacy behavior is unchanged, and the
  strict profile is not active anywhere.
- Implementation planning followed in the same SPC cycle: the gate-by-gate
  [implementation plan](0118-analysis/IMPLEMENTATION-PLAN.md) derives structure
  from AD-01..AD-10, uses the gate as its unit, and records four open decisions
  with owners. It authorizes no code, migration or deployment.

### ADR 0118/0119 implementation-plan review — 2026-09-11

- [Plan revision 2](0118-analysis/IMPLEMENTATION-PLAN.md) replaces the unsupported
  independent-prework claim and missing I01-I41 registry with W01-W12 dependencies.
- [Review](0118-analysis/IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md) records findings,
  baseline evidence and corrections: numeric diagnostics at G1, pre-validation
  specialization, immutable bundle closure at G4, scoped conformance and safe ownership.
- ADRs remain **Accepted**, implementation unimplemented; G0b/G1-G8 and A01-A24
  are not closed by this documentation review. No source migration or deployment.

### ADR 0118/0119 revision 3.2 — capability satisfaction, 2026-09-11

- Both ADRs remain **Accepted**, implementation **not implemented**. At the user's
  direction the [architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md)
  adds AD-11: derived requirements, scoped offers and evidence-relative resolution.
- [Shared capability contract](0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md)
  reuses ADR 0106 catalog/packs/derivation. No second intent database, runtime stage,
  automatic topology fallback, grant or transfer of resource ownership is introduced.
- [Formal contract](0119-analysis/FORMAL-CONTRACT.md) adds SEC-CAP; selected
  versions/strategies/conditions and evidence bind to intent/plan/bundle digests.
  Offline candidate readiness remains distinct from fresh live activation evidence.
- [Plan revision 4](0118-analysis/IMPLEMENTATION-PLAN.md) extends W03/W04/W06/W07/
  W08/W10/W11 without discarding revision 3 diagnostic, governance, stop/reversibility
  or entry-condition provisions. [Acceptance](0118-analysis/MIGRATION-AND-ACCEPTANCE.md)
  adds A25-A32; existing A01-A24 remain unchanged.
- G0a base acceptance and its historical reviews are retained; those reviews are
  not independent review evidence for rev 3.2. G0b/G1-G8 and A01-A32 remain open.
  No catalog/runtime/schema implementation, device change, qualification or deploy.

### ADR 0118/0119 rev 3.2a — capability amendment supplement, 2026-09-11

- SPC review of rev 3.2. Both ADRs remain **Accepted**, implementation **not
  implemented**. No decision is withdrawn; three under-specified points in AD-11
  are corrected and the amendment's repository-level premises are re-grounded.
- **Determinism:** rev 3.2 required offer content to be hash-bound while listing
  qualification evidence references as offer content, which contradicts its own
  claim that a fresh identical observation leaves the semantic plan unchanged.
  [Contract §4.1](0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md) now splits the
  offer into a digest-bearing semantic core and a separately hashed evidence annex;
  [formal contract](0119-analysis/FORMAL-CONTRACT.md) binds the split to `W_g`.
- **Inventory:** `complete(R_g, Omega_g)` was self-referential. Omega_g now has an
  external lower bound anchored to the ADR 0118 D6 path list, shared with SEC-PATH.
- **Status vocabulary:** the tri-state is mapped one-directionally onto the
  pre-existing `unsupported` flow verdict, so neither collapses into the other.
- **Corrected premises:** `E8020`/`E8021`/`E3202` are raised in code but are not
  registered in `topology-tools/data/error-catalog.yaml`, so rev 3.2's instruction
  to preserve their meaning had no registered subject; the capability catalog
  reaches runtime as identifiers only and is a closed vocabulary, so offers cannot
  live in it; the acceptance baseline pointer was five commits stale.
- **Vocabulary debt:** six recorded enforcement gaps (acceleration/FastTrack, the
  Docker `DOCKER-USER` versus nftables hook, IPv6 family, the Proxmox generator
  STUB, the nine unrendered LXC attachments, `untracked` admission) are mapped onto
  existing A-cases; four still lack any catalog identifier and are therefore
  unverified by construction until W03 registers one.
- A25-A32 gain terminal evidence levels. Registers are unchanged: A01-A32 for
  acceptance, W01-W12 for work. No new ADR, gate, plugin, catalog entry, runtime
  change, test result, qualification or deployment authorization.

### ADR 0118 D7 amendment — authoritative-field contract, 2026-09-11

- Adds the inverse of the derived-field contract: an object supplies reusable
  shape and defaults and must not author a value that identifies or classifies
  one concrete entity.
- Established by two findings, not by argument. `obj.network.vlan.vpn_tunnel`
  declared a VLAN id and prefix that all four instances overrode; the values were
  reachable by none of them and a fifth VLAN would have inherited a collision.
  `obj.network.trust_zone.vpn_tunnel` declared a security level and isolation
  flag correct for one of its two zones and wrong for the other.
- Both were corrected as parity-preserving layering moves: effective values and
  rendered artifacts unchanged, verified byte-for-byte.
- Open and deliberately not folded in: `inst.trust_zone.vpn_exit` still renders
  as "VPN Tunnel Zone" because it inherited that name. Correcting it changes
  rendered comments and is a separate reviewed change.
- No gate closed, nothing qualified, no deployment implied.

### ADR0118/0119 — approval producer implementation proposal, 2026-09-15

- Adds [proposed approval producer contract](0119-analysis/APPROVAL-PRODUCER-CONTRACT-PROPOSAL.md): L7 signed review, separately pinned authority/context, exact validate-stage manifest channel and admission binding.
- Keeps approval separate from semantic verification, source promotion and activation. A real signed decision cannot relabel a legacy plan.
- Status: Proposed implementation contract, not accepted or implemented; parent ADR statuses unchanged. No G3 closure, backend qualification, actual approver assignment or deployment authorization.

### ADR 0118/0119 rev 3.3 — enforcer type and enforcer instance, 2026-09-15

- ADR 0119 stays **Accepted**; adds **D1.1**. An enforcer has a type, resolved
  from the device's declared enforcement capability under ADR 0106, never from an
  identifier and never from which object module owns a generator. One type, one
  renderer. Artifacts are produced per enforcer instance: two enforcers of one
  type are two scopes, two projections and two independent artifact sets with
  their own connection identity and applied state. Enforcement plane stays a
  third, orthogonal axis. D2 adds enforcer type to the execution context; D3
  states the generate stage renders one artifact set per instance.
- ADR 0118 stays **Accepted**; D6 now says its table lists runtime targets, not
  enforcers - a workload's runtime does not select the enforcer covering its
  paths, and one runtime may be covered by several enforcers of different types.
- ADR 0110 stays **Implemented**. An erratum corrects the §1.1 transcription
  against the implemented class schema: `enforcement_plane` is required,
  `address_space` exists, `device_assignments` does not, and `managed_by_ref`
  carries no `target_class` - `class.router` was dropped because an enforcer need
  not be a router. R1-R6 behaviour and M1-B are unchanged.
- [W07 decision](0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md) is amended:
  the seam is parameterised by enforcer type rather than by backend, and a second
  time by enforcer instance. Records the chosen Terraform layout
  `terraform/<backend>/<enforcer instance id>/` as an implementation choice, and
  states that adopting it is a reviewed behaviour change affecting 24 of 163
  emitted paths, not a refactor.
- Basis: SPC analysis of 2026-09-15 in this session. Measured: four devices with
  four distinct OS declared in the topology; `cap.firewall.security_matrix`,
  `.routeros` and `.pve` registered in the catalogue with zero consumers; a
  published `matrix_by_enforcer` index with zero subscribers; and a single
  unaliased `provider "routeros"` in one Terraform root.
- No code, schema or artifact changed. No gate closed, nothing qualified, no
  deployment implied.

### ADR 0118/0119 rev 3.4 — enforcer axes corrected after review, 2026-09-15

- Corrects rev 3.3 against the [rev 3.3 review](../docs/reports/2026-09-15-adr0118-0119-rev33-review-0202f253.md).
  Both ADRs stay **Accepted**; ADR 0110 stays **Implemented**. No gate closed.
- **Cardinality (R1).** ADR 0119 D1 now states the direction: one scope names
  exactly one enforcer, one enforcer may hold several scopes on several planes. A
  scope carries its own identity and is never keyed by its `managed_by_ref`. An
  enforcer-to-scope index must carry every scope in a deterministic order or refuse
  the multiplicity with a diagnostic. Plane separation is semantic and is not
  evidence that shared chains or resources are isolated.
- **Separation (R2).** D1.1 no longer demands one address, credential set and state
  per enforcer. It states six distinctions - enforcer identity, scope/context,
  connection binding, resource identity and writer, state namespace, apply unit -
  and requires unambiguous target selection with a single writer per resource.
  Several targets may share a management endpoint; sharing a binding, state
  namespace or apply unit is allowed where the coupling is declared and its
  reconciliation and recovery validated. Scope attribution is not a failure domain.
- **Dispatch (R3).** "One type, one renderer" is replaced. A type names a family of
  enforcement semantics; for each target context exactly one compatible versioned
  adapter is resolved, zero is unsupported, more than one blocks with no priority or
  first-match fallback. Resolution carries provenance, and the adapter's identity
  and version are pinned before validation and enter the plan's verifiable identity.
- **Layout justification (R4).** The W07 claim that a Terraform root holds one
  unaliased provider configuration is withdrawn: Terraform supports several
  configurations of one provider through `alias`. Root-per-instance is justified
  instead by state, writer and transaction boundaries, the aliased alternative is
  named and its rejection reasoned, each adapter's selected layout is tabulated, and
  moving roots now requires a resource/state/consumer inventory and a
  no-unintended-recreation plan rather than a path rename.
- **Erratum authority (R5).** ADR 0110's erratum separates the stale transcription
  from the normative amendment that dropped `target_class: class.router`, states the
  reason, requires the replacement to check an enforcement-capable target rather
  than accept any `instance_ref`, and no longer says the implemented file is the
  authority over an accepted contract.
- **Harmonization and evidence (R6).** AD-01 and AD-08 in the
  [architecture proposal](0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md) carry the
  cardinality and the ownership distinctions. The findings matrix is published as
  [enforcer axis conformance](0118-analysis/ENFORCER-AXIS-CONFORMANCE.md) instead of
  living only in a commit message.
- The index defect is reproduced in that record: two matrices on one enforcer
  compile SUCCESS with no diagnostics and `matrix_by_enforcer` keeps whichever came
  last, which is also a D4 permutation violation.
- No code, schema or artifact changed. Ten implementation gaps remain open and
  are listed in section 2 of the conformance record.

### Rev 3.4 editorial consolidation

- Removes remaining enforcer=scope and per-instance-artifact wording from D1.1
  and the W07 stage diagram; scope attribution and declared apply units are retained.
- Synchronizes the design annex header, enforcement-plane terminology, current
  implementation-plan entrypoint, capability supplement and scoped AI rule packs/map.
- Separates W07 layout goals from proven state/resource/failure isolation; the root
  migration remains a future reviewed change, not an authorization or completed work.
- Corrects the conformance count to ten open implementation rows; distinguishes
  corpus coverage, feasibility observations and planned regression tests.
- Corrects rev 3.4 document dates to 2026-09-15, matching both author and committer
  timestamps of `48a7ac3f`. No new revision, implementation gate or qualification
  status is introduced by this consolidation.

### ADR 0118/0119 — enforcer/scope implementation readiness, 2026-09-28

- Adds [readiness record](0118-analysis/ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md):
  a re-measured baseline, an independent reproduction of the V-13 index defect, and
  a bounded specification for the next code change. Both ADRs stay **Accepted**;
  ADR 0110 stays **Implemented**. No gate closed, nothing qualified.
- Corrects two conformance rows from measurement rather than from restatement:
  `security_matrices` is complete in membership but permutation-sensitive in order,
  and V-09 is a singular return type across projection, generator and template
  rather than one dropped row.
- Records five new findings, `N-01`..`N-05`. The load-bearing one is that V-04/V-05
  is blocked on a namespace decision, not on adding a declaration: the three
  `cap.firewall.security_matrix*` identifiers are registered at L2 with device
  summaries while the catalogue reserves that namespace for policy objects and
  already carries an L1 device slot, `cap.net.l3.security.firewall.zone_policy`.
  The enforcer of record declares neither, `enabled_packs` never reach the
  effective capability set, and an unattributed scope compiles clean and is
  enforced by nobody.
- Sequences the ten open rows into implementable-now, blocked-on-V-13 and
  blocked-on-a-decision. The capability-axis decision is raised as a proposal
  requiring review; it is not taken there.
- Proposes `E7010`, `E7011` and `W7012` inside the existing ADR 0118/0119
  allocation, with the collision check recorded. No code, schema, manifest or
  artifact changed; no code has been written against this specification.

### ADR 0118/0119 — enforcer/scope readiness record updated after implementation, 2026-09-28

- Marks readiness record section 5 (`matrix_by_enforcer` → `scopes_by_enforcer`,
  `E7010`/`E7011`/`W7012`) as done, referencing commit `c5f66c10` on branch
  `adr-0118-0119`, with its actual validation evidence replacing the earlier plan.
- Updates the section 4 sequencing table: V-13/N-05/plane-default done; V-09,
  V-10, V-14 (the projection/generator/template consumer chain) move from
  blocked-on-V-13 to the next implementable-now candidate.
- Adds section 5b: a sketch, not a specification, of the consumer chain's touch
  points and open questions (two-scope fixture, rendered shape, parity
  evidence) - explicitly not authorization to begin that change.
- Records an open, separately tracked finding: `pytest tests` shows 125 failures
  confined to `tests/plugin_integration/test_security_plan_validator.py`, which
  passes 77/77 in isolation. Bisected to somewhere among the ~100
  `plugin_integration` files collected before it; five other directories and the
  immediately adjacent file are individually cleared. Reasoned as unlikely to be
  caused by `c5f66c10` (disjoint files) but not yet confirmed by a rerun. Not
  part of the ADR 0118/0119 scope.
- No code, schema or artifact changed by this entry.

### ADR 0118/0119 — consumer-chain finding N-06, pollution investigation closed, 2026-09-28

- Corrects the readiness record's section 5b: "one rendered block per scope"
  was wrong. `zone_firewall.tf.j2` emits exactly one terminal-deny resource and
  `vpn.tf.j2` hardcodes two more references to it by name; RouterOS has one
  `forward` chain per device regardless of how many scopes it holds. New
  finding N-06 records this and redirects V-09/V-10/V-14 from a generate-stage
  rendering change to a compile-stage composition step: zones union safely
  (shared origin data), matrix cells and policy-override names do not and need
  explicit conflict diagnostics rather than a silent last-write-wins merge -
  the same defect class V-13 fixed for the enforcer index, one level deeper.
  Not started; this is corrected design work, not code.
- Closes the test-pollution investigation opened while validating `c5f66c10`.
  The original 125 failures in `test_security_plan_validator.py` were not
  reproduced: every preceding directory and both halves of the preceding
  `plugin_integration` files were cleared individually, and the decisive
  check - the exact natural collection order `pytest tests` itself uses,
  reconstructed and run through the target file inclusive - passed the target
  clean (1981 passed, 1 skipped, 1 unrelated failure explained by process
  timing relative to `1336c12f`). Closed as an investigated, not reproduced,
  anomaly, most likely resource exhaustion specific to the original
  2573-test run, not a code defect requiring a fix.
- No code, schema or artifact changed by this entry.

### ADR 0118/0119 — composition contract decided (D-COMP-1..4), 2026-09-28

- Resolves the two design questions N-06 left open, narrower in scope than
  N-02: how the MikroTik adapter composes several scopes on one enforcer, a
  case unexercised anywhere in the real topology today. Fulfils ADR 0119 D1's
  existing requirement that composition across scopes sharing an enforcer be
  validated rather than assumed; does not amend the ADR.
- D-COMP-1: scopes composed for one enforcer must have pairwise-disjoint
  `zone_refs`, refused on overlap. Deliberately stricter than an
  equal-cells-are-safe merge - it makes a matrix-cell collision between scopes
  structurally impossible rather than something to adjudicate, at the cost of
  refusing a legitimate future case (two scopes sharing a zone for different
  concerns) until that is its own reviewed decision.
- D-COMP-2: `policy_overrides` names must be unique per enforcer (not
  globally), refused on collision rather than silently disambiguated - the
  same reasoning D1.1 already applies to adapter resolution.
- D-COMP-3/D-COMP-4: the composed shape (zones/matrix union, overrides
  concatenated) and its determinism (scopes processed in
  `scopes_by_enforcer`'s existing sorted order).
- New diagnostics `E7013`/`E7014`, collision-checked clean in the 7009-7019
  sub-band of the existing ADR 0118/0119 allocation.
- Not implemented: `security_matrix_compiler.py` does not yet compose, no test
  exercises D-COMP-1..4. Removes the design blockers section 5b listed for
  V-09/V-10/V-14; a two-scope fixture and parity evidence remain open before
  that chain can be specified the way section 5 was for V-13.

### ADR 0118/0119 — V-09/V-10/V-14 landed, readiness record closed out, 2026-09-29

- `e868abbe`: `_extract_security_matrix` in the MikroTik projection reads the
  compiler's `composed_matrices_by_enforcer` instead of re-deriving zone
  membership and R1-R6 itself. Finding N-07 (recorded first, before coding)
  characterized that local computation as a third independent derivation of
  the same fact, diverged from the compiler in three ways found by reading
  both implementations side by side - none active on the real topology's data.
  `security_matrices` retired entirely as a MikroTik consume (manifest,
  generator, projection signature) rather than left accepted-but-unread.
  `tests/test_backend_specialization_boundary.py`'s line budget lowered
  1518 -> 1399, matching the function's 209 -> 94 line shrink; the W07
  decision document's migration-order step 3 marked Done.
- `168b4f27`: the two-scope composed-plan fixture section 5b/5d called for,
  in `test_projection_helpers.py` - exercises `build_mikrotik_projection`
  with a genuinely multi-scope composed plan, which the real topology (one
  enabled scope) cannot exercise on its own.
- Real-topology parity verified: `generated/` byte-identical after a clean
  recompile, `errors=0 warnings=2` matching the recorded baseline.
- Readiness record reconciled: V-09/V-10/V-14 marked Done in section 4;
  sections 5b/5d's now-resolved open items struck through; evidence for both
  commits added to section 7; the status banner lists all five landed changes
  (`c5f66c10`, `1336c12f`, `e72d0099`, `e868abbe`, `168b4f27`).
- No design decision changes in this entry - implementation and bookkeeping
  only, against the design section 5c already decided.

### ADR 0118/0119 — enforcer type/adapter resolution designed (D-TYPE-1..3), 2026-09-29

- Resolves the capability-axis question section 4 named as the single
  highest-value blocked item, larger than first framed. Before designing a
  replacement, checked whether either capability engine could express
  "enforced by RouterOS OR Proxmox" as written: `capability_contract_validator.py`
  and `netmodel/capability.py`'s `Offer.applies_to` both match capability
  identifiers exactly, with no prefix/hierarchy semantics and no `any_of`/`one_of`
  construct anywhere in the schemas. `required_capabilities` on a class is a
  conjunction; it cannot express dispatch among mutually exclusive adapters.
  The earlier "recommended framing" (device axis = `cap.net.l3.security.
  firewall.*`) is retired along with the namespace question it was answering -
  a namespace choice does not fix a conjunction-only engine being asked to do
  selection.
- D-TYPE-1: enforcer type (perimeter/internal/none) is derived from exactly one
  of two mutually exclusive device-kind capabilities:
  `cap.net.l3.security.firewall.zone_policy` (existing, router-side) or a new
  registration, `cap.compute.security.firewall.zone_policy` (hypervisor-side;
  no such L1 capability existed for Proxmox before this, which is a second,
  independent reason the router-only framing could not have worked).
- D-TYPE-2: adapter is derived from type × the already-derived `cap.os.*`
  family (`cap.os.routeros` -> `.routeros` adapter, `cap.os.proxmox` -> `.pve`),
  not a third declared capability. Zero matching OS families refuses as
  unsupported; more than one refuses as ambiguous with no priority order -
  matching ADR 0119 D1.1's explicit dispatch contract. This makes
  `cap.firewall.security_matrix.routeros`/`.pve` derived outputs, like
  `cap.role.*` already are, closing N-03 without a redundant declaration.
- D-TYPE-3: the generic `cap.firewall.security_matrix` (zero declarers, zero
  consumers) is retired rather than repurposed as a `required_capabilities`
  entry - resolution answers "is this a valid enforcer" directly, which is
  N-01's `managed_by_ref` target-check replacement.
- `E7015`-`E7018` allocated in the existing 7009-7019 sub-band, collision
  check clean. Placement: an extension of `capability_compiler.py`'s existing
  per-object derivation pass, not a new plugin family.
- N-04 (`enabled_packs`) stays deferred, confirmed independently: only two
  objects declare non-empty packs (Chateau, GL.iNet), and the real enforcer
  does not need pack expansion to gain `.zone_policy` - a direct declaration
  is narrower and sufficient. Fixing pack expansion has a wider blast radius
  (Chateau's enabled `pack.router.enterprise` also lists BGP/OSPF/VRF
  capabilities) and is not required for this decision.
- Not implemented: no code, schema or catalogue entry changed. `enforcer_resolution`
  does not exist yet.

### ADR 0118/0119 — enforcer type/adapter resolution, SPC MODE review (two passes), 2026-09-29

- The design entered at commit `8dd9a3a3` (previous entry) went through the
  formal `docs/ai/spc-contract.md` 7-step protocol rather than being accepted
  as written. **Correction to the previous entry:** its D-TYPE-3 bullet
  ("the generic `cap.firewall.security_matrix` ... is retired") is
  superseded by this entry - the SPC review's first pass found that
  `CAPABILITY-SATISFACTION-CONTRACT.md` §5 forbids exactly that action
  ("Legacy catalog entries are not reclassified by this amendment"), and its
  §7 already treats `.pve` as the correct identifier with an unimplemented
  generator as the actual gap. All three pre-registered identifiers
  (`cap.firewall.security_matrix`, `.routeros`, `.pve`) are kept.
- First pass, second finding: D-TYPE-2 had no rule for a device already
  carrying a direct `.routeros`/`.pve` declaration alongside the
  newly-resolved one - ADR 0119 D1.1's "generic capability alongside a
  specific one... inputs to the resolution, not answers" case. Fixed with an
  explicit reconciliation rule: agreement confirms, disagreement is a
  distinct refusal (`E7019`), no priority order between the two inputs.
- Second pass (STEP 7 compliance matrix run to completion) found two further
  Critical gaps the first pass missed: (1) ADR 0119 D1.1 requires adapter
  identity *and* version; only identity had been resolved. (2) The chosen
  type values (`perimeter`/`internal`) are the exact strings
  `class.network.security_matrix.yaml`'s `enforcement_plane` field already
  uses for an axis ADR 0119 D1.1 states is independent of enforcer type.
- Resolution, both user-confirmed: (1) the resolving generator plugin's
  existing `api_version` manifest field (already `1.x` on both MikroTik and
  Proxmox generators) is bound to the resolved adapter identity as a partial
  version signal; full D2 execution-context binding remains this record's
  pre-existing V-07 row, not newly closed. (2) type values renamed to
  `network`/`compute` (naming the producing capability namespace), with
  `perimeter`/`internal` reserved exclusively for `enforcement_plane`.
- `E7015`-`E7019` (5, not 4) in the same sub-band, collision check re-run
  clean. Still design-only: not registered in `error-catalog.yaml` or
  `docs/diagnostics-catalog.md`, `enforcer_resolution` does not exist.
- Verification: `check_adr_consistency.py --strict-titles` clean; diagnostic
  sub-band grep shows the five codes referenced only in this design record.

### ADR 0118/0119 — enforcer type/adapter resolution, implemented, 2026-09-29

- Implemented the design from the previous two entries. Building it against
  the real topology found three things the SPC review itself had not:
  1. The real enforcer of record, `rtr-mikrotik-chateau`, declared no
     `cap.net.l3.security.firewall.zone_policy` at all, despite its
     security-matrix instance being explicitly zone-based. Fixed as a
     topology-data correction (`obj.mikrotik.chateau_lte7_ax.yaml`), not by
     weakening the D-TYPE-1 gate.
  2. The approved `adapter_version` mechanism (binding the resolving
     generator's `api_version`) was wrong: `api_version: 1.x` is identical
     across every plugin in the entire framework (the kernel-API
     compatibility marker, not an adapter revision) - a repo-wide grep during
     implementation found this, not the review. `adapter_version` ships as
     `None`, honestly, rather than a misleading constant.
  3. Device-kind capabilities live on the hardware object;
     `cap.os.*` capabilities live on a *different* object under ADR 0064's
     embedded-OS model, joined only at the instance level via `os_refs`.
     `capability_compiler.py` (the design's chosen home) iterates objects and
     can never see both facts for one entity. Moved to
     `effective_model_compiler.py`, which already performs this exact join
     for OS/firmware capabilities; `enforcer_resolution` is published keyed
     by **instance id**, not object id.
- Severity corrected during implementation: an eager `error` severity on
  every resolution (not only referenced ones) broke the real compile for
  `rtr-slate` (GL.iNet, OpenWrt - type resolves, no adapter exists, and
  nothing points `managed_by_ref` at it). Renamed and downgraded four of the
  five codes to warnings (`W7015`, `W7016`, `W7017`, `W7019`); `E7018` stays
  the one hard error, since it only fires for an instance an actual
  security_matrix scope depends on.
- New capability registered: `cap.compute.security.firewall.zone_policy`
  (`capability-catalog.yaml`). N-01 replaced in both
  `declarative_reference_validator.py` and `network_core_refs_validator.py`
  (kept in parity per `test_declarative_reference_validator_parity.py`).
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, the third
  warning being the expected `W7016` for `rtr-slate`; `git status` shows no
  diff under `generated/` (purely additive); manifests
  (`compilers.yaml`/`validators.yaml`) and `framework.lock.yaml` updated for
  the new `enforcer_resolution` produces/consumes wiring.
- Tests: 13 new cases in `test_effective_model_compiler.py` (object-level and
  cross-object/os_refs resolution, contradiction, unsupported, reconciliation
  disagreement, non-enforcer omission) and 3 new cases in
  `test_network_core_refs_validator.py` (E7018 accept/reject paths), all
  passing, plus the targeted suites (`test_security_matrix_compiler.py`,
  `test_declarative_reference_validator_parity.py`,
  `test_backend_specialization_boundary.py`, `test_data_bus_contracts.py`,
  `test_manifest.py`, `test_capability_contract_validator.py`,
  `test_capability_contract_loader_compiler.py`), all clean.

### W07 migration order item 1 — capability-flag derivation moved to compile stage, 2026-09-29

- `_derive_mikrotik_capability_flags` and `_extract_capabilities` moved verbatim
  from `topology/object-modules/mikrotik/plugins/projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.capability_flags`
  (`topology/object-modules/mikrotik/plugins/compilers/
  capability_flags_compiler.py`, compile stage) - the first compile-stage
  compiler plugin an object module has registered in this framework,
  establishing the `object.<module>.compiler.plan -> backend_plan` seam
  `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s Shape section
  already specified.
- Root cause found during implementation, not anticipated by the decision
  document: `phase: finalize` plugins are dispatched through an `on_finalize`
  hook, not `execute()` directly - `effective_model_compiler.py` already does
  this via a one-line delegation, which the new plugin now mirrors. Diagnosed
  by direct-execute vs full-stage-execute comparison after the plugin was
  silently skipped (`skip_reason: "phase 'finalize' not implemented"`) despite
  correct manifest registration and scheduling order.
- `build_mikrotik_projection` gains `capability_flags` as a required argument
  (the same "required, refuse `None`" contract `composed_matrices_by_enforcer`/
  `vlan_cidr_map` already use); the generator's manifest `depends_on`/`consumes`
  updated to match. `I4210` registered for the new plugin's per-run info
  diagnostic.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from the pre-existing baseline; `git status` shows no diff under
  `generated/` (purely additive).
- Tests: 9 files updated for the new required parameter and consumer wiring
  (`test_mikrotik_capability_driven.py` - unit tests for the derivation logic
  itself now import from the new module;
  `tests/helpers/mikrotik_security_channels.py` - the shared fixture helper
  now derives real `capability_flags` from `ctx.compiled_json` rather than
  publishing empty, since capability-driven template-selection tests depend
  on real content; `test_projection_helpers.py`, `test_projection_snapshots.py`,
  `test_terraform_mikrotik_generator.py`, `test_generator_template_and_
  publish_contract.py`, `test_tuc0002_terraform_v2.py`,
  `test_tuc0003_mikrotik_v2.py`, `test_backend_specialization_boundary.py` -
  the last one's function/line budget lowered to 13/1361 and its migration
  parametrize lists updated). Full `tests/plugin_integration` +
  `tests/plugin_contract` + `tests/kernel` run confirmed clean.

### W07 migration order item 4a — WireGuard tunnel derivation moved to compile stage, 2026-09-29

- `_extract_wireguard_tunnels` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.wireguard_tunnels`
  (`topology/object-modules/mikrotik/plugins/compilers/
  wireguard_tunnels_compiler.py`, compile stage) - the second compile-stage
  compiler plugin an object module has registered, after item 1's
  `capability_flags`. Uses the `on_finalize` delegation pattern from the
  start (item 1's root-cause finding applied directly, no rediscovery
  needed).
- Consumes `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows) and `base.compiler.security_matrix`'s
  `vlan_cidr_map`. `build_mikrotik_projection` gains `wireguard_tunnels` as a
  required argument, the same "required, refuse `None`" contract the other
  three channels already use.
- Characterization (required before migrating, per the W05/N-07 lesson)
  found no divergence to fix first: the function reads only topology
  instance data plus the already-compiler-sourced `vlan_cidr_index`, not a
  second derivation of a compiler-owned fact - lower risk than items 1-3.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`.
- `projections.py` now 12 functions / 1179 lines (down from 13/1361);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_wireguard_tunnels` added to the "migrated, gone rather than
  dormant" list.
- Same nine-file test-wiring pattern as item 1 applied again: the shared
  helper `tests/helpers/mikrotik_security_channels.py` now derives
  `wireguard_tunnels` from `ctx.compiled_json` the same way it already does
  `capability_flags`; all `consumes_keys`/`allowed_dependencies` sets
  extended to the new plugin id. Full targeted mikrotik/projection/
  terraform/tuc slice (120 tests) and the boundary suite confirmed passing.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4a marked done, with a note that this confirms the "dedicated
  plugin per specialization" choice item 1 first established, rather than
  one plugin accreting every concern.

### W07 migration order item 4b — container derivation moved to compile stage, 2026-09-29

- `_extract_containers` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.containers`
  (`topology/object-modules/mikrotik/plugins/compilers/containers_compiler.py`,
  compile stage) - the third dedicated compile-stage compiler plugin an
  object module has registered, after item 1's `capability_flags` and item
  4a's `wireguard_tunnels`.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, `routeros_container`-group rows) - no dependency on
  `base.compiler.security_matrix`, since container derivation touches no
  zone/CIDR fact. `build_mikrotik_projection` gains `containers` as a
  required argument (a plain list; `[]` is already the correct empty shape,
  unlike the dict-shaped channels).
- Characterization found no divergence to fix first, same as item 4a - but
  also caught a real hazard: the projection already had an unrelated local
  variable also named `containers` (observed-runtime bridge-interface
  config, a different meaning entirely), which would have silently shadowed
  the new parameter for the rest of the function and corrupted rendered
  output if migrated without reading the whole function body first. Found
  by grepping the function for the parameter name before finalizing, not by
  a test; renamed to `observed_containers`.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 6 containers derived correctly with the rename in place.
- `projections.py` now 11 functions / 1000 lines (down from 12/1179);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_containers` added to the "migrated, gone rather than dormant"
  list.
- Same nine-file test-wiring pattern as items 1/4a applied again. Targeted
  mikrotik/projection/terraform/tuc slice: 118 passed (2 unrelated errors in
  `test_tuc0001_router_data_link.py`, root-caused to CPU contention from a
  concurrently-running full-suite background job - every one of the ~30
  underlying timeouts hit completely unrelated validators, dns_refs through
  vm_refs, none touching MikroTik/containers/wireguard; a clean non-strict
  compile immediately prior showed zero errors).
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4b marked done, naming the naming-collision finding explicitly
  since it is the kind of thing the characterization step exists to catch.

### W07 migration order item 4c — WiFi config derivation moved to compile stage, 2026-09-29

- `_extract_wifi_config` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.wifi_config`
  (`topology/object-modules/mikrotik/plugins/compilers/wifi_config_compiler.py`,
  compile stage) - the fourth dedicated compile-stage compiler plugin an
  object module has registered.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router rows) - no dependency on `base.compiler.security_matrix`, same as
  item 4b. `build_mikrotik_projection` gains `wifi_config` as a required
  argument. `_extract_bridge_vlans` (item 4f, still in the projection) takes
  this function's output as its own argument; the projection now threads
  the `wifi_config` parameter into it locally, so 4f's eventual migration
  will need `wifi_config` already in scope.
- Characterization found no divergence and, checked explicitly this time
  given item 4b's finding, no naming collision either: grepped the whole
  function body for every generic-sounding name (`interfaces`, `datapaths`,
  `configurations`, `securities`) before concluding it was safe.
- Surfaced a test-infrastructure gap instead: `test_projection_helpers.py`'s
  `build_mikrotik_projection` wrapper always defaulted the new required
  channels to empty, silently breaking
  `test_mikrotik_projection_extracts_wifi_interfaces` (a test that builds
  real WiFi `instance_data` and expects it derived). Fixed by making that
  wrapper auto-derive all four channels from the fixture's own rows, the
  same way `test_mikrotik_capability_driven.py`'s wrapper already did.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 5 WiFi interface bindings derived correctly.
- `projections.py` now 10 functions / 877 lines (down from 11/1000);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_wifi_config` added to the "migrated, gone rather than dormant"
  list.
- Same test-wiring pattern as items 1/4a/4b applied again, plus the
  `test_projection_helpers.py` wrapper fix above. Targeted mikrotik/
  projection/terraform/tuc slice: 120 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4c marked done, naming both findings (no collision this time,
  found by checking; the test-wrapper gap, found by a real content test
  failing) and noting the forward dependency onto item 4f.

### W07 migration order item 4d — routing-policy derivation moved to compile stage, 2026-09-29

- `_build_routing_policy_entry` moved verbatim from `projections.py`
  (generate stage) to a new plugin, `object.mikrotik.compiler.
  routing_policies` (`topology/object-modules/mikrotik/plugins/compilers/
  routing_policies_compiler.py`, compile stage) - the fifth dedicated
  compile-stage compiler plugin an object module has registered.
- Unlike items 4a-4c, the source function was a per-row builder called from
  inside a larger shared loop (over `network` rows) that also builds vlans
  and bridges in the same iteration, not an independent top-level extractor.
  Migrating it required replicating the loop's row-selection and
  `managed_by_ref`-resolution logic for `routing_policy` rows specifically -
  checked against the original by reading the surrounding loop in full, not
  just the builder function - while leaving the vlan/bridge branches of that
  same loop untouched in the projection.
- Consumes `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows) and `base.compiler.security_matrix`'s
  `vlan_cidr_map`, same as item 4a. `build_mikrotik_projection` gains
  `routing_policies` as a required argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 5 routing policies derived correctly.
- `projections.py` now 9 functions / 774 lines (down from 10/877);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_build_routing_policy_entry` added to the "migrated, gone rather than
  dormant" list.
- Same test-wiring pattern as items 1/4a/4b/4c applied again, including
  extending both `test_projection_helpers.py`'s auto-deriving wrapper and
  `test_mikrotik_capability_driven.py`'s wrapper with a routing-policy
  derivation helper that replicates the plugin's row-selection loop.
  Targeted mikrotik/projection/terraform/tuc slice: 120 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4d marked done, naming the new kind of migration this item
  represents (extracting a slice of a shared loop, not an independent
  function) for the benefit of items 4e-4i.

### W07 migration order item 4e — MAC-to-VLAN assignment derivation moved to compile stage, 2026-09-29

- `_extract_mac_vlan_assignments` moved verbatim from `projections.py`
  (generate stage) to a new plugin, `object.mikrotik.compiler.
  mac_vlan_assignments` (`topology/object-modules/mikrotik/plugins/
  compilers/mac_vlan_assignments_compiler.py`, compile stage) - the sixth
  dedicated compile-stage compiler plugin an object module has registered.
- It needed a VLAN `instance_id -> vlan_id` index the projection used to
  build from its own already-filtered `vlans` list - itself a slice of the
  same shared per-`network`-row loop item 4d's migration already drew from,
  the same "per-row builder/index fed by a shared loop" shape 4d named.
  Rather than replicate the whole VLAN branch (still generate-stage, item
  4g), the plugin replicates only the row-selection, `managed_by_ref`-
  resolution and `vlan_id`-fallback logic needed to build the index itself -
  checked against the full network-row loop in `build_mikrotik_projection`,
  not only the removed function.
- This is also the first migration whose derivation needs object-level
  properties (`_get_object_properties`'s `objects_map` fallback for
  `vlan_id`), which `base.compiler.effective_model` already publishes under
  `effective_model_candidate["objects"]` - confirmed by reading the
  compiler's own `objects_index` construction, not assumed present.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows, objects) - no `base.compiler.security_matrix`
  dependency, same as items 4b/4c. `build_mikrotik_projection` gains
  `mac_vlan_assignments` as a required argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Verified against the real topology: full compile is `errors=0 warnings=3`,
  unchanged from baseline; `git status` shows no diff under `generated/`;
  the real topology's 3 MAC-to-VLAN assignments derived correctly (I4215).
- `projections.py` now 8 functions / 720 lines (down from 9/774);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_mac_vlan_assignments` added to the "migrated, gone rather than
  dormant" list.
- Same test-wiring pattern as items 1/4a/4b/4c/4d applied again, including
  extending `mikrotik_security_channels.py`, `test_projection_helpers.py`
  and `test_mikrotik_capability_driven.py` with a MAC-VLAN derivation helper
  that replicates the plugin's own vlan_id_index-building loop slice.
  Targeted mikrotik/projection/terraform/tuc slice plus the full boundary
  test file: 121 + 15 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4e marked done, naming the two new lessons this item adds
  (an index fed by a shared-loop slice, and a migrated function's data need
  satisfied by a channel another compiler already publishes rather than a
  new one) for the benefit of items 4f-4i.

### W07 migration order item 4f — bridge-VLAN derivation moved to compile stage, 2026-09-29

- `_extract_bridge_vlans` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.bridge_vlans`
  (`topology/object-modules/mikrotik/plugins/compilers/
  bridge_vlans_compiler.py`, compile stage) - the seventh dedicated
  compile-stage compiler plugin an object module has registered.
- Confirms the forward dependency item 4c's entry recorded: this plugin
  subscribes to `wifi_config` (item 4c) from `object.mikrotik.compiler.
  wifi_config` as a published channel, rather than the local variable the
  projection used to thread into it. It also consumes
  `base.compiler.effective_model`'s `effective_model_candidate` for the
  router-row side of the derivation. No shared-loop slice or extra channel
  was needed this time - both inputs were already either a top-level router
  list or another compiler's published output.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 1 bridge VLAN entry derived correctly (I4216).
- `projections.py` now 7 functions / 632 lines (down from 8/720);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_extract_bridge_vlans` added to the "migrated, gone rather than dormant"
  list.
- Same test-wiring pattern as items 1/4a/4b/4c/4d/4e applied again,
  including extending `mikrotik_security_channels.py`,
  `test_projection_helpers.py` and `test_mikrotik_capability_driven.py`
  with a bridge-VLAN derivation helper that depends on the wifi_config
  derivation helper, the same forward dependency the real plugin has.
  Targeted mikrotik/projection/terraform/tuc slice plus the full boundary
  test file: 121 + 16 passed, clean.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4f marked done, updating the guidance for items 4g-4i to
  describe subscribing to an earlier item's channel once it migrates,
  rather than threading a still-local variable into a not-yet-migrated
  function.

### W07 migration order item 4g — VLAN-entry derivation moved to compile stage, 2026-09-29

- `_build_vlan_entry` moved verbatim from `projections.py` (generate stage)
  to a new plugin, `object.mikrotik.compiler.vlan_entries`
  (`topology/object-modules/mikrotik/plugins/compilers/
  vlan_entries_compiler.py`, compile stage) - the eighth dedicated
  compile-stage compiler plugin an object module has registered.
- Like items 4d/4e, the source function was a per-row builder inside the
  same shared `network`-row loop that also builds bridges. Migrating it
  required replicating the VLAN branch's row-selection and
  `managed_by_ref`-resolution logic (including an `ip_allocations` fallback
  the bridge branch does not have) - checked against the full network-row
  loop, not just the builder - while leaving the bridge branch of that same
  loop untouched in the projection.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows, objects) - no `base.compiler.security_matrix`
  dependency, same as items 4b/4c/4e. `build_mikrotik_projection` gains
  `vlans` as a required argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- It did surface a test-infrastructure gap, the same kind item 4c found but
  in a different helper: `tests/plugin_integration/test_tuc0003_mikrotik_v2.py`
  builds a `PluginInputSnapshot` directly (no `ctx` to publish through) via
  `empty_channel_subscriptions()`, and one of its three tests asserts on a
  real VLAN (`inst.vlan.guest`) its fixture actually carries - the all-empty
  stand-in silently rendered "no VLANs configured" instead of failing
  loudly. `vlans` is the first of the eight non-matrix channels this
  fixture's assertions depend on with real content, which is why the gap
  surfaced only now. Fixed by adding `derived_channel_subscriptions
  (compiled_json)` to `tests/helpers/mikrotik_security_channels.py` - the
  `PluginInputSnapshot` counterpart to `publish_empty_channels`, deriving
  all eight channels from a given semantic payload - and switching that one
  file's `_build_snapshot` to use it; `empty_channel_subscriptions()`
  itself is untouched, since other callers genuinely want the all-empty
  stand-in.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 10 VLAN entries derived correctly (I4217).
- `projections.py` now 6 functions / 583 lines (down from 7/632);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_build_vlan_entry` added to the "migrated, gone rather than dormant"
  list.
- Same test-wiring pattern as items 1/4a/4b/4c/4d/4e/4f applied again,
  including extending `mikrotik_security_channels.py`,
  `test_projection_helpers.py` and `test_mikrotik_capability_driven.py`
  with a VLAN-entry derivation helper that replicates the plugin's
  row-selection loop, plus the new `derived_channel_subscriptions` helper
  and its one call site. Targeted mikrotik/projection/terraform/tuc slice
  plus the full boundary test file: 121 + 17 passed, clean (after fixing
  the test_tuc0003 gap - the first isolated run surfaced 1 failure, real
  and reproducible, not a stale-read or contention false alarm).
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4g marked done, naming the new lesson (a `PluginInputSnapshot`
  built directly, bypassing any projection wrapper, needs its own
  per-fixture channel derivation too) for the benefit of items 4h-4i.

### W07 migration order item 4h — bridge-entry derivation moved to compile stage, 2026-09-30

- `_build_bridge_entry` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.bridge_entries`
  (`topology/object-modules/mikrotik/plugins/compilers/
  bridge_entries_compiler.py`, compile stage) - the ninth dedicated
  compile-stage compiler plugin an object module has registered, and the
  bridge branch of the same shared `network`-row loop item 4g's VLAN branch
  came from. With both branches now migrated, that loop keeps only
  `networks.append` and the required-object-ref/instance-id validation
  calls.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, network rows, objects) - no `base.compiler.security_matrix`
  dependency, same as items 4b/4c/4e/4g. `build_mikrotik_projection` gains
  `bridges` as a required argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- Applied 4g's lesson directly this time: before finalizing, every test
  whose fixture carries a real bridge row was checked for a
  rendered-bridge assertion, not only the ones already using a derivation
  helper. `test_tuc0003_mikrotik_v2.py`'s `MIKROTIK_COMPILED_PAYLOAD`
  carries a `br-lan` bridge and one of its tests asserts
  `resource "routeros_interface_bridge"` in the rendered output, so
  `derived_channel_subscriptions` (added in item 4g) gained a `bridges`
  derivation in the same change that added the `bridges` channel, rather
  than waiting for that test to fail first the way item 4g's gap was found.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology derives 0 bridges, matching the pre-migration baseline (this
  topology's LAN uses the native bridge interface directly rather than a
  separate `obj.network.bridge` row) (I4218).
- `projections.py` now 5 functions / 564 lines (down from 6/583);
  `test_backend_specialization_boundary.py` budget lowered to match,
  `_build_bridge_entry` added to the "migrated, gone rather than dormant"
  list.
- Same test-wiring pattern as items 1/4a-4g applied again, including
  extending `mikrotik_security_channels.py`, `test_projection_helpers.py`
  and `test_mikrotik_capability_driven.py` with a bridge-entry derivation
  helper that replicates the plugin's row-selection loop, plus extending
  `derived_channel_subscriptions` with the new channel proactively.
  Targeted mikrotik/projection/terraform/tuc slice plus the full boundary
  test file: 121 + 18 passed, clean on the first isolated run (no gap this
  time, unlike item 4g).
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4h marked done. Only item 4i (`_build_firewall_entry`, 16
  lines) remains in the migration order.

### W07 migration order item 4i — firewall-entry derivation moved to compile stage, completing the migration order, 2026-09-30

- `_build_firewall_entry` moved verbatim from `projections.py` (generate
  stage) to a new plugin, `object.mikrotik.compiler.firewall_entries`
  (`topology/object-modules/mikrotik/plugins/compilers/
  firewall_entries_compiler.py`, compile stage) - the tenth and final
  dedicated compile-stage compiler plugin the W07 migration order calls
  for. Unlike items 4d/4e/4g/4h, the source function's loop was never
  shared with any other row kind - its own dedicated loop over the
  `firewall` instance group, the same independent-extractor shape items
  4a-4c had.
- Consumes only `base.compiler.effective_model`'s `effective_model_candidate`
  (router ids, `firewall`-group rows, objects) - no `base.compiler.
  security_matrix` dependency, same as items 4b/4c/4e/4g/4h.
  `build_mikrotik_projection` gains `firewall_policies` as a required
  argument.
- Characterization found no divergence and, checked given 4b's and 4c's
  findings, no naming collision.
- With this function's departure, `_get_object_properties` and
  `_is_staged_row` lost their last caller in the projection. Per the W07
  decision document's own reasoning, neither makes a backend decision, so
  neither was an independent migration candidate - but leaving them in
  place once nothing called them would be exactly the dormant-helper risk
  A24 exists to prevent. Removed as dead code in the same change.
- The zone/CIDR resolution `build_mikrotik_projection` still applies to
  this channel's output (trust-zone-to-CIDR matching, `src_zone_ref`/
  `dst_zone_ref` normalization) is not part of `_build_firewall_entry` and
  stays in the projection, the same way policy-based routing's
  `src_vlan_ref` resolution stays local to the routing_policies plugin.
- Applied item 4h's discipline again: every test whose fixture carries a
  real firewall-policy row was checked before finalizing, not only after a
  failure. `test_terraform_mikrotik_generator.py`'s
  `test_terraform_mikrotik_generator_reflects_full_network_topology`
  asserts on real firewall-filter output (`guest_isolated_default`,
  `iot_isolated_default`) and passed on the first isolated run, because
  `publish_empty_channels`/`derived_channel_subscriptions` already derive
  `firewall_policies` from the fixture the same way every other channel
  does - no test-infrastructure gap this time.
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline; `git status` shows no diff under `generated/`; the real
  topology's 4 firewall-policy entries derived correctly (I4219).
- `projections.py` is now 2 functions / 518 lines (down from 5/564 at item
  4h, and from 17/1,565 at the W07 baseline) - `_extract_security_matrix`
  and `build_mikrotik_projection` itself, exactly the scope the decision
  document named in advance as what a final step would actually be.
  `test_backend_specialization_boundary.py` budget lowered to match, and
  `_build_firewall_entry`, `_get_object_properties`, `_is_staged_row`
  added to the "migrated, gone rather than dormant" list.
- Same test-wiring pattern as items 1/4a-4h applied again, including
  extending `mikrotik_security_channels.py`, `test_projection_helpers.py`
  and `test_mikrotik_capability_driven.py` with a firewall-entry derivation
  helper that replicates the plugin's own dedicated loop. Targeted
  mikrotik/projection/terraform/tuc slice plus the full boundary test file:
  121 + 21 passed, clean on the first isolated run.
- `adr/0118-analysis/W07-BACKEND-SPECIALIZATION-DECISION.md`'s migration
  order item 4i marked done, completing the migration order (items 1,
  4a-4i). The document's "What this decision does not do" section's stale
  function/line count updated to match, and a closing note added
  clarifying that completing the migration order does not by itself close
  W07/G4 - that gate also depends on the conformance record in
  `ENFORCER-AXIS-CONFORMANCE.md`.

### ENFORCER-AXIS-CONFORMANCE.md reconciliation and first counterexample, 2026-09-30

- Reconciled `ENFORCER-AXIS-CONFORMANCE.md`'s ten open rows against
  `ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md`'s own sequencing record and
  the real commits it cites, none of which the conformance table had been
  updated to reflect. Five rows closed (V-04, V-05, V-09, V-13, V-15), one
  split (V-14: Proxmox closed, MikroTik worse - the W07 migration order
  raised its substring-selector count from 9 to 18), four unchanged (V-07,
  V-10, V-11, V-12). Found and corrected a misattribution in the readiness
  record's own sequencing table: it credited V-10 as closed alongside V-09,
  but V-10's own wording and evidence (the single-router assumption) were
  never what that commit fixed, per the commit's own message. Both
  documents corrected; `IMPLEMENTATION-PLAN.md`'s W07-completion entry
  (added the same day) updated to match rather than repeat the same error.
- Implemented and pinned the conformance record's first counterexample
  (section 4, "Two devices of one type"): `test_effective_model_resolves_
  two_instances_of_one_type_independently` in
  `tests/plugin_integration/test_effective_model_compiler.py` confirms two
  enforcer instances of one type resolve independently at the D-TYPE
  layer, with divergent outcomes (one resolves, one hits W7016) - passed on
  the first run, confirming already-correct behavior rather than finding a
  defect there.
- Implemented the second counterexample's accepted fallback outcome ("or
  explicit unsupported-multiplicity diagnostic"): `_extract_security_matrix`
  in `topology/object-modules/mikrotik/plugins/projections.py` used to
  silently pick the sorted-first enforcer when `composed_matrices_by_
  enforcer` held a composed plan for more than one - V-10's defect, latent
  because the real topology has exactly one router. It now raises
  `ProjectionError` naming every enforcer it found, citing the V-11/V-12
  Terraform state-layout question this does not decide. Pinned by
  `test_mikrotik_projection_refuses_more_than_one_enforced_router` in
  `tests/plugin_integration/test_projection_helpers.py`. This is real
  progress on V-10 (silent to explicit) but not the closure V-10's title
  asks for (multi-enforcer rendering itself stays blocked on V-11/V-12).
- Verified against the real topology: `check_adr_consistency.py
  --strict-titles` clean; full compile is `errors=0 warnings=3`, unchanged
  from baseline (the refusal never fires there - one router, one composed
  plan); `git status` shows no diff under `generated/`. Targeted mikrotik/
  projection/effective-model test slice: 99 passed, 1 skipped.
- `adr/0118-analysis/ENFORCER-AXIS-CONFORMANCE.md`'s section 4
  counterexamples table gained a Status column recording both results.

### Counterexample 4 characterized: enforcer_resolution has zero consumers, 2026-09-30

- Investigating counterexample 3 ("Generic + specific capabilities...
  Provenance retained") found it has no implemented mechanism to test
  against - `provenance` does not appear anywhere in `capability_compiler.py`
  - and overlaps V-07, already blocked on G1/W03. Assessed and deferred
  rather than guessed at; `ENFORCER-AXIS-CONFORMANCE.md` section 4 records
  why.
- That investigation surfaced a larger, concrete finding: `enforcer_resolution`
  (D-TYPE-1..3, `7d6a2072`) has **zero consumers anywhere** in the MikroTik or
  Proxmox plugin trees. Every plugin that builds `router_ids` still decides
  "is this an enforcer" by `object_ref.startswith("obj.mikrotik.")`, a
  name-prefix check with no relationship to whether the compiler's own
  resolver would recognize the instance as a valid enforcer at all. This is
  exactly counterexample 4: "Reference names a target with no enforcement
  capability | Visible refusal; a valid instance_ref alone is insufficient" -
  currently the opposite is true.
- Characterized, not fixed, per explicit direction: added
  `test_mikrotik_projection_accepts_a_router_ref_the_type_resolver_would_
  refuse` in `tests/plugin_integration/test_projection_helpers.py`, running
  the same instance shape through both real compilers - `effective_model_
  compiler` correctly omits an instance with no declared device-kind
  capability from `enforcer_resolution`, and `build_mikrotik_projection`
  still accepts the same instance as a router. Wiring `enforcer_resolution`
  into the ~10 files across MikroTik and Proxmox that build `router_ids` is
  deferred as its own, larger change - not attempted here.
- Also added a caveat to V-04's closed row (section 2a): V-04's *type
  resolution* half is genuinely closed against its original zero-consumer
  evidence, but its *target validation* half is not - `enforcer_resolution`
  existing and being computed is not the same as anything downstream
  validating against it, which this counterexample now demonstrates
  concretely rather than by inference.
- Verified: `check_adr_consistency.py --strict-titles` clean; targeted
  mikrotik/projection/effective-model test slice: 34 passed (test_projection_
  helpers.py + test_effective_model_compiler.py in full).

### VLAN managed_by_ref gains a network-enforcer-type check (E7019), 2026-09-30

- The "zero consumers anywhere" framing above was overclaimed: it was scoped
  to the MikroTik/Proxmox object-module plugin trees and missed the
  framework-level VALIDATE stage. `declarative_reference_validator.py`
  (registered as `base.validator.network_core_refs`; `network_core_refs_
  validator.py` is the same logic kept only as the parity test's legacy
  baseline, not itself registered in any manifest) already subscribes to
  `enforcer_resolution` and raises `E7018` for `class.network.security_matrix`
  rows' `managed_by_ref` - just not for VLAN, bridge, firewall-policy,
  routing-policy or MAC-VLAN-assignment rows, each validated by separate,
  purely structural logic in the same file. Corrected in
  `ENFORCER-AXIS-CONFORMANCE.md` (commit `6e254609`) before this entry.
- Given three scoping options, chose the minimal one: fix VLAN's
  `managed_by_ref` only, leaving firewall_policy/routing_policy's (already
  broader, pre-existing) gap untouched as separate future work.
- `_rule_network_core` in `declarative_reference_validator.py` gains a new
  `class.network.vlan`-only branch alongside the existing generic
  `class.router`/L1 structural check (`E7835`): a new helper,
  `_validate_vlan_managed_by_enforcer_type`, runs only when that structural
  check already passed (avoiding a duplicate diagnostic for the same root
  cause) and requires the resolved `enforcer_resolution` type to be exactly
  `"network"`, not merely non-`None` - a hypervisor resolved as `"compute"`
  is valid for a security matrix (ADR-0110) but not for a VLAN. New code
  `E7019` allocated in `error-catalog.yaml` (`E7018`'s empty adjacent slot in
  the same 7009-7019 sub-band), `severity: error`, `stage: validate`
  (`E7018`'s own catalog entry says `stage: compile`, a pre-existing
  mismatch against where it actually runs - not touched here).
- Scoped strictly per instruction: `class.network.firewall_policy` and
  `class.network.routing_policy` still have no enforcer-type check on their
  own `managed_by_ref`, and the COMPILE-stage object-module compilers that
  build `router_ids` (the ~10-file gap counterexample 4 characterizes) are
  unchanged - this only adds a VALIDATE-stage guard for the case where a
  VLAN's `managed_by_ref` is explicitly set.
- Tests: two new regression tests in `test_declarative_reference_validator.py`
  (missing enforcer type; wrong/`"compute"` type). Three "accepts valid"
  tests in the same file and in `test_network_core_refs_validator.py` needed
  an added `enforcer_resolution` publish to stay green (E7019 now fires for
  them otherwise); the parity test (`test_declarative_reference_validator_
  parity.py`) needed the same, plus widening its `_run` helper's
  `consumes_keys` to include `base.compiler.effective_model` - the legacy
  reference file never reads that channel, so parity is preserved by making
  the new check pass silently on that fixture, not by touching the legacy
  file. 42 tests passed across the three files.
- `topology-tools/data/error-catalog.yaml` is inside the framework integrity
  boundary: regenerated `projects/home-lab/framework.lock.yaml` (`generate-
  framework-lock.py --force`) after adding `E7019`, per `docs/framework/
  FRAMEWORK-V5.md`'s documented recovery for `E7824`.
- Verified against the real topology: `errors=0 warnings=3`, unchanged from
  baseline (the one real router resolves `"network"`, so `E7019` never fires
  there); `git status` shows no diff under `generated/`;
  `check_adr_consistency.py --strict-titles` clean.
- `ENFORCER-AXIS-CONFORMANCE.md` updated: V-04's row (section 2a) and
  counterexample 4's row (section 4) now describe the VALIDATE-stage E7019
  guard precisely, while keeping the COMPILE-stage/projection gap that
  counterexample 4's own test targets marked as still violated and
  unaffected by this change.

### routing_policy and firewall_policy's managed_by_ref join the check, 2026-09-30

- Given three remaining open items (V-07 and V-11/V-12 both blocked on
  architectural decisions not for an agent to make; V-14's MikroTik-side
  `router_ids`-by-capability refactor, ~10-11 files, COMPILE stage; or this
  smaller extension), chose the smaller extension: the same E7019/E7018
  pattern, applied to the two remaining `managed_by_ref`-bearing network-core
  row kinds that had no check at all.
- `class.network.routing_policy` was not excluded from `_is_network_row`
  and already got the generic structural `class.router`/L1 check (E7835);
  it now also gets E7019's strict "network"-type check, alongside
  `class.network.vlan` - a router's own routing table is not something a
  hypervisor can take over, the same reasoning VLAN's check already used.
  Renamed the helper from `_validate_vlan_managed_by_enforcer_type` to
  `_validate_network_type_managed_by_ref` to reflect the broader scope.
- `class.network.firewall_policy` was fully excluded from `_is_network_row`
  (grouped with bridge/trust_zone/firewall_rule/data_link/physical_link/qos,
  none of which carry `managed_by_ref`) with no explanation in the exclusion
  set's own comments or git history for why it specifically had no check at
  all, despite real topology instances (`inst.fw.*`) setting `managed_by_ref`
  in practice - neither class schema (`class.network.firewall_policy.yaml`,
  `class.network.routing_policy.yaml`) declares the field at all, since it is
  a cross-cutting instance field, not a class-specific schema property.
  Given firewall_policy is conceptually closer to security_matrix (a
  named security/firewall scope that could plausibly be enforced by a
  router's zone policy or a hypervisor's own firewall stack, ADR-0110) than
  to VLAN (an L2 network-topology construct that only a router administers),
  gave it `E7018`'s permissive (network-or-compute) check instead of E7019's
  strict one, under a new code `E7026` (no structural class.router/L1 check
  to layer onto, since none existed before). `_validate_enforcer_type_ref`
  gained `code`/`context_label` parameters (defaulting to `E7018`/"security
  matrix", so the existing security_matrix call site is unchanged) so E7018
  and E7026 share one implementation.
- New code `E7026` allocated in `error-catalog.yaml`; `E7019`'s catalog
  entry and hint text updated to describe both classes it now covers rather
  than "VLAN only".
- Tests: four new regression tests in `test_declarative_reference_validator.py`
  (routing_policy: wrong/`"compute"` type, accepts `"network"`; firewall_policy:
  missing type, accepts `"compute"`) - 11 tests, all passing. No existing test
  in this file, the parity test, or `test_network_core_refs_validator.py` uses
  a `routing_policy`/`firewall_policy` row, so none needed updating.
- `error-catalog.yaml` is inside the framework integrity boundary again:
  regenerated `framework.lock.yaml` (`generate-framework-lock.py --force`).
- Verified against the real topology: `errors=0 warnings=3`, unchanged (the
  real topology's `inst.routing_policy.*` and `inst.fw.*` instances are all
  managed by the one real router, which resolves `"network"`); no diff under
  `generated/`; `check_adr_consistency.py --strict-titles` clean.
- Checked whether bridge or "MAC-VLAN-assignment" rows are also
  `managed_by_ref`-bearing gaps at this VALIDATE-stage level, since earlier
  text in this record grouped them with VLAN/firewall-policy/routing-policy:
  they are not. `class.network.bridge`'s schema has no `managed_by_ref` field
  at all (only `host_ref`, already checked as `E7836`), and "MAC-VLAN
  assignment" is not a distinct instance class - `mac_vlan_assignments_
  compiler.py` derives it from VLAN rows' own data, which `E7019` already
  covers. All four `managed_by_ref`-bearing `_rule_network_core` row kinds
  (security_matrix, vlan, routing_policy, firewall_policy) now have a
  capability check. `ENFORCER-AXIS-CONFORMANCE.md`'s V-04 row and
  counterexample 4's row updated again to name `E7026`, the newly-covered
  classes, and this correction - the remaining gap those rows measure is
  purely the COMPILE-stage `router_ids` builders (V-14/the ~10-file wiring),
  a different mechanism from this VALIDATE-stage class-row check entirely.

### V-14 MikroTik-side closed: router_ids by declared capability, 2026-09-30

- With the VALIDATE-stage `managed_by_ref` checks (E7018/E7019/E7026) done,
  the two remaining implementable-by-agent priorities were this (V-14's
  MikroTik-side refactor) or stopping; V-07/V-11/V-12 stay blocked on
  architectural decisions not for an agent to make. Chose this: it is the
  last open piece of counterexample 4 ("Reference names a target with no
  enforcement capability"), already characterized by
  `test_mikrotik_projection_accepts_a_router_ref_the_type_resolver_would_
  refuse`, and closes V-14's own finding (`grep -rn 'in object_ref\|in
  instance_id\|startswith("obj\.' topology/object-modules/mikrotik/plugins/`
  = 18 lines across 11 files, 2026-09-30 baseline).
- Characterized the exact selection criterion needed before writing any fix
  code, since the naive replacement is a real regression risk: `rtr-slate`
  (a real device, GL.iNet Slate AX1800, `obj/glinet/obj.glinet.slate_
  ax1800.yaml`) declares `cap.net.l3.security.firewall.zone_policy` and so
  resolves `enforcer_resolution` type `"network"` (D-TYPE-1), but its OS
  family is OpenWrt, not RouterOS, so D-TYPE-2 resolves no adapter - `type
  == "network"` alone would have wrongly admitted it into every MikroTik-
  specific `router_ids` set. The real topology's one MikroTik router (`rtr-
  mikrotik-chateau`) resolves `adapter == "cap.firewall.security_matrix.
  routeros"`; `rtr-slate` does not. Selection criterion: `enforcer_
  resolution[instance_id].get("adapter") == "cap.firewall.security_matrix.
  routeros"`, replacing `object_ref.startswith("obj.mikrotik.")` - true
  declared-capability selection (D-TYPE-1..3), not a name-prefix
  convention, and provably not a same-topology no-op the way E7019's real-
  topology parity check often is.
- Applied uniformly across all ten compile-stage compilers found by that
  grep (`bridge_entries`, `firewall_entries`, `vlan_entries`, `routing_
  policies`, `mac_vlan_assignments`, `containers`, `wireguard_tunnels`,
  `wifi_config`, `bridge_vlans`, `capability_flags`): each gained a local
  `_is_mikrotik_enforcer(instance_id, enforcer_resolution)` helper
  (duplicated per file, matching this family's established "small helpers
  duplicated, not cross-imported" convention already set by `_resolved_
  object_ref`/`_get_object_properties`) and an `enforcer_resolution`
  subscribe from `base.compiler.effective_model` alongside the existing
  `effective_model_candidate` one. `plugins.yaml` gained a matching
  `enforcer_resolution` consumes entry for each (`allowed_dependencies` is
  keyed by producer plugin id, not key, so this was for documentation/
  auditability parity with the existing `consumes` declarations, not a
  runtime necessity - confirmed by reading `kernel/plugin_base.py`'s
  `subscribe` and `specs.py`'s `declared_dependency_ids` before assuming
  either way).
- `projections.py`'s own `build_mikrotik_projection` (GENERATE stage, called
  by `terraform_mikrotik_generator.py`) had the same pattern at its own
  `router_ids` build - not dead code, unlike the different single-pick
  pattern V-10 found dead at a different line in the same file. Gave it the
  same fix: a new required `enforcer_resolution` parameter (same "required,
  refuse None" `ProjectionError` contract the other nine channel parameters
  already have), the same local `_is_mikrotik_enforcer` helper, and a new
  `enforcer_resolution` consumes entry + `depends_on: base.compiler.
  effective_model` on `object.mikrotik.generator.terraform`'s manifest
  entry. This closes `test_mikrotik_projection_accepts_a_router_ref_the_
  type_resolver_would_refuse` for real: converted from a characterization
  test (asserted the bug) to a regression test (asserts the fix), renamed
  to `test_mikrotik_projection_refuses_a_router_ref_the_type_resolver_
  refuses`.
- Test fixture fallout, all traced to the same root cause (fixtures that
  identify "the router(s)" by name prefix, same as the code used to): four
  files' local `build_mikrotik_projection` wrapper functions (`test_
  projection_helpers.py`, `test_projection_snapshots.py`, `test_mikrotik_
  capability_driven.py`) and one direct-generator-execution fixture (`test_
  mikrotik_capability_driven.py`'s `_ctx`) needed a synthesized `enforcer_
  resolution` default (or explicit publish), deriving it from the same
  name-prefix router set the fixture already computes, so every test not
  specifically exercising the new capability check keeps picking the same
  routers as before. `test_mikrotik_vlan_entries_silently_drops_an_
  ambiguous_target` (a different, still-open counterexample - "Shared
  management endpoint, distinct target selectors") needed the same
  treatment for its two-router premise to still hold; it is unaffected by
  and does not test the V-14 fix itself. `test_the_manifest_declares_all_
  twelve_channels_required` renamed to ...`_thirteen_...` with a new
  assertion for the `enforcer_resolution` consumes entry.
- `error-catalog.yaml` was not touched this time - no new diagnostic code,
  since router selection is an internal compiler decision, not something
  that emits a diagnostic of its own (an excluded router silently produces
  fewer entries, the same as before; a VLAN/routing_policy/firewall_policy
  row naming it as `managed_by_ref` is what `E7018`/`E7019`/`E7026` already
  catch). `topology/object-modules/mikrotik/` is inside the framework
  integrity boundary (`topology/framework.yaml`'s `include`): regenerated
  `framework.lock.yaml` regardless, since these files changed.
- Verified against the real topology: `errors=0 warnings=3`, unchanged; no
  diff under `generated/` (the real router resolves the RouterOS adapter,
  so nothing it manages was excluded); `check_adr_consistency.py --strict-
  titles` clean.
- Mid-verification process hygiene: a background full-suite run was
  accidentally left running from an earlier step while a second one was
  launched for this step, producing two concurrent processes reading/
  writing overlapping `/tmp` state and two spurious failures neither
  reproduced alone. Killed both, ran one clean instance instead of trusting
  the noisy result - the same "characterize before concluding" discipline
  this whole session has used for topology defects, applied to a tooling
  anomaly instead.

### V-14 fully closed: row-kind selection by declared class, 2026-09-30

- The user confirmed V-14 as the next priority after the router-selection
  half landed. The remaining row-kind-selection half (7 lines across 6
  files: `bridge_entries`, `firewall_entries`, `vlan_entries`, `mac_vlan_
  assignments`, `routing_policies`, `wireguard_tunnels`) decides "is this
  network row a VLAN/bridge/routing-policy/firewall-policy row" by matching
  a substring against `object_ref` - a name convention, not the declared
  class V-14 asks for, even though `effective_model_candidate`'s rows
  already carry `instance.extends_class`/`materializes_class` (populated
  by `effective_model_compiler.py` the same way `extends_object`/
  `materializes_object` are) - confirmed by reading the compiler's own
  normalization code before assuming the field existed.
- Added a `_resolved_class_ref(row)` helper to each of the six files,
  mirroring the existing `_resolved_object_ref`'s exact resolution order
  (`extends_class` then `materializes_class`), and replaced each substring
  check with a declared-class comparison: `class.network.bridge`,
  `.firewall_policy`, `.vlan` (both `vlan_entries` and `mac_vlan_
  assignments`, since MAC-VLAN assignment is derived from VLAN row data),
  `.routing_policy`, and `.tunnel_link` for WireGuard. Verified each class
  name against the real class-module `@extends` chain and a real instance
  file before using it, not assumed from the object's name.
- This also fixed a live aliasing bug the substring approach was working
  around, not just a style issue: `obj.network.routing_policy.vpn_vlan`
  contains the substring `"vlan"`, so `vlan_entries_compiler.py` and
  `mac_vlan_assignments_compiler.py` both needed an explicit `or
  "routing_policy" in object_ref` exclusion to avoid misclassifying it as a
  VLAN row. The class-based check has no such aliasing risk - a genuine
  correctness improvement, not only a V-14-compliance one.
- `wireguard_tunnels_compiler.py`'s case needed a documented boundary
  rather than a deeper fix: `class.network.tunnel_link` has exactly one
  extending object today (`obj.network.wireguard_tunnel`), so the class
  check alone is sufficient for the current corpus, but the compiler's own
  extracted shape (`endpoint_a`/`endpoint_b`, listen port, peers) is
  WireGuard-specific - a future non-WireGuard `tunnel_link` object would
  additionally need a `tunnel_type` property check (threading `objects_map`
  into `_extract_wireguard_tunnels`'s signature, a broader change than the
  other five files needed). Noted in the code rather than solved
  speculatively for a class that has no second member yet.
- Caught one test-fixture risk before it became a silent false pass: `test_
  mikrotik_vlan_entries_silently_drops_an_ambiguous_target`'s `inst.vlan.
  ambiguous` fixture row set `extends_object`/`materializes_object` but not
  `extends_class`/`materializes_class` - with the new class-based filter,
  this row would have been excluded for lacking a class match instead of
  reaching the `managed_by_ref` ambiguity logic the test exists to
  characterize, and the test's `vlans == []` assertion would have kept
  passing for the wrong reason. Added the missing `materializes_class:
  class.network.vlan` field so the test still exercises the gap it names.
  Checked the other MikroTik-adjacent test files for the same risk
  (`test_mikrotik_capability_driven.py`, `test_terraform_mikrotik_
  generator.py`, `test_tuc0002_terraform_v2.py`, `test_tuc0003_mikrotik_
  v2.py`) - none construct raw VLAN/bridge/routing-policy/firewall-policy/
  wireguard-tunnel network rows without a class field already set, so none
  needed the same fix.
- `grep -rn 'in object_ref\|in instance_id\|startswith("obj\.'
  topology/object-modules/mikrotik/plugins/` now returns zero real code
  matches (one harmless comment line remains, an unrelated ADR-0117 note).
  V-14 is fully closed, not split, for the first time since the W07
  migration order copied the pattern into ten new files.
- Verified against the real topology: `errors=0 warnings=3`, unchanged; no
  diff under `generated/`; targeted mikrotik/terraform/tuc00/bridge/vlan/
  routing_policy/wireguard/firewall test slice (150 passed);
  `check_adr_consistency.py --strict-titles` clean; `plugin_contract`/
  `kernel` (408 passed, the same pre-existing unrelated `projections.py`
  "chateau" hardcode failure confirmed again).
- `ENFORCER-AXIS-CONFORMANCE.md`'s V-14 row updated to "fully closed," and
  the section 2 "Net" summary corrected from "closed or majority-closed" to
  plain "closed."

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

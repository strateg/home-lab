# ADR 0118/0119 — implementation plan

Status: reviewed implementation plan for the **Accepted** architecture, G0a closed
2026-09-10. Revision 3, 2026-09-11. **No implementation gate is closed by this plan.**
No topology migration, code change, secret access, live inspection or deployment
is authorized by editing this document.

Authority: [ADR 0118](../0118-universal-container-network-model.md),
[ADR 0119](../0119-firewall-rule-ordering-contract.md) and
[architecture rev 3.1](FINAL-ARCHITECTURE-PROPOSAL.md).
[Migration/acceptance](MIGRATION-AND-ACCEPTANCE.md) owns G0..G8 and A01..A24;
this plan assigns implementation work and evidence to those gates.
[Review findings](IMPLEMENTATION-PLAN-REVIEW-2026-09-11.md) explain the corrections.

Review baseline: commit `966971f6`, branch development; tree was clean before
this documentation review. The prior plan is retrievable at that commit.
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
| Estimates | No hours or fixed critical-path duration asserted without scoped deliverables and qualification results |

Historical [implementation exploration](FINAL-IMPLEMENTATION-PROPOSAL.md) is
not adopted wholesale. Its defect observations are review inputs, not an approved
backend/controller design. Choosing RouterOS here is an implementation
recommendation within the accepted architecture, not evidence it already qualifies.

## 2. Evidence baseline and limits

Fresh targeted command, run at the review baseline:

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

A01..A24 are **unclosed**, not proven to have zero related test coverage.
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
| W03 Schema and IP domains | L2/L4/L5 class definitions, semantic contexts, shared network definitions, local-key grammar, typed flows, diagnostics | W02 canonical relation contract | G1 schema; G2 address semantics, schema owner |
| W04 Intent and provenance | Core compiler, source/default/@on provenance, domain resolution, candidate adapter | W03; effective-model and provenance channel contracts | G2, compiler maintainer |
| W05 Legacy projection parity | security_matrix channels and MikroTik projection integration | W01; characterize both existing derivations first | Prerequisite to backend cutover, generator maintainer |
| W06 Plan and checker | Core security plan, predicates/path/state algebra, independent reference oracle, validate-stage obligations | W04 and bounded capability requirements | G3, security/compiler owner |
| W07 Backend specialization/render | Versioned RouterOS adapter, complete execution contexts and deterministic rendering; no semantic discovery in generate | W05/W06; target feasibility record | G4, backend owner |
| W08 Artifact/bundle closure | Assemblers/builders, existing bundle schema/manifest, security artifact digest closure | Contract designed with W06; integrated with W07 | G4 offline closure, build/release owner |
| W09 Topology/flow inventory | Services, domains, leases, planned intents, zone conflicts, legacy VPN mapping | Inventory now; freeze only after W03/W04; migration requires G1-G4 | G5, topology/flow owner |
| W10 Transaction/recovery | Existing runner boundary, owner-delegated operations, journal, revocation, OOB/recovery evidence | W08; topology/ownership input and feasibility findings | G6, deploy/scope owner |
| W11 Conformance/TUCs | Unit/property/differential/negative/fault/live evidence, applicability matrix | Developed with W01-W10, not deferred until G7 | G7, test/qualification owner |
| W12 Assurance/qualification | HA owners, tailoring, threat model, Q objectives, risk review | Preparation now; G8 needs applicable completed evidence | G0b/G8, human risk owner |

This is the complete local work-ID register. W items can span two gates when
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
  existing C->O->I / @on / effective_model (sole compiled_json_owner)
    -> core network_intent + source_map + candidate report
    -> core security plan authority
    -> backend-specialized complete candidate plan
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
| Core network intent compiler | base.compiler.effective_model / effective_model_candidate plus declared provenance inputs | network_intent, source_map, candidate_report; compile/finalize after effective_model |
| Core security plan compiler | network_intent + capability/profile constraints | semantic_plan, obligation_inventory; compile/finalize after intent |
| Backend specialization responsibility | semantic_plan + backend capability semantics | complete backend_plan, including guards/transforms/contexts; compile before validation |
| Validator | intent, complete plan, source map, profile | validation_evidence, bound to exact semantic/plan digest |
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

A message that only names a rule, a resource or a template line does not satisfy
D7. Reports label evidence as design, offline-validated, backend-tested or
live-observed; missing evidence reads not run or unsupported, never pass. Secrets
never appear in diagnostics, feedback or public manifests, and that redaction is
tested rather than assumed: it is an explicit W04/W08 regression, not a review habit.

An operator-facing explain path is a recommended convenience, not a gate
requirement. If one is added it consumes the same records; it must not become a
second derivation of authorization.

## 5. Gate deliverables and exit criteria

### Baseline prerequisite — W01/W05

W01: decide which projection keys are required and which have defined empty
values; make producer/fixture/consumer agree. Required missing data fails clearly.
Exit: 33/33 targeted tests, including missing-key behavior; no StrictUndefined
disablement, weakened assertion or snapshot-only suppression.

W05: characterize compiler-versus-generator legacy projection differences, then
switch consumers to the canonical channel with **identical managed artifacts**
for the fixed source/versions. Compare normalized semantics and rendered content;
exclude only documented nonsemantic timestamps from hashes. If there is a real
behavior difference, separate and review it before advancing.
No strict semantics, source migration or producer ownership handoff is mixed into
this parity step. W01 is not a prerequisite for reading/designing W02-W04.

### G1 — Registered schema and reference contracts

W02/W03 deliver:
- versioned L4 attachments/access bindings, L5 publications, L2 policy/guard,
  route/tunnel/interface-transform schema and downward realization bindings;
- shared definitions without 14 independently maintained service-schema copies;
- network_intent_version in explicit domain contexts, distinct from manifest @version;
- typed collection traversal, concrete-key error paths, one relation authority;
- local keys, disable/delete/rename semantics, inherited false/zero/empty cases;
- typed protocol/port/control-flow shape, explicit original/current match views;
- central **numeric diagnostic allocation with collision tests**, replacing the
  design-only NET-*/SEC-* provisional codes while retaining semantic requirement IDs,
  as required by ADR 0118 D7.

G1 exits on full positive/negative C->O->I fixtures and A21/A23 schema portions.
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
Test SEC-AUTH, AVAIL, PATH, NAT, ORDER, STATE and transition-model prerequisites,
not merely the sort order. Use an independent reference interpreter; do not make
the generator and oracle share the same decision code and call agreement proof.

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
evidence, capability/backend versions, ownership and transition requirements.
A referenced security artifact is permissible only when its hash and schema are
bound by the root manifest. Missing/tampered/stale evidence blocks build/deploy.
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

Each A01..A24 has a test or an explicit scope decision. Unsupported extension cases
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

W08 additionally tests bundle integrity, version compatibility, missing artifact/
evidence, stale plan hashes and unapproved candidate input. These are supporting
regressions, not invented replacements for A01..A24.

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
documentation gate nor this plan's work assignment closes G1-G8 or A01-A24.

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

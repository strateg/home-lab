# Enforcer axes — what the corpus requires and what the code does

Status: measurement record for the ADR 0118/0119 rev 3.3/3.4 amendment.
Not a plan, not an authorization, and not evidence that anything is qualified.

This is the artifact the rev 3.3 commit message described and did not publish; the
[rev 3.3 review](../../docs/reports/2026-09-15-adr0118-0119-rev33-review-0202f253.md)
was right that a summary in a commit body is not a referenced matrix. Identifiers
`V-01`..`V-18` label the session inventory published here; the review itself uses
`R1`..`R6`. They are distinct identifier sets, not interchangeable finding numbers.

Baseline: branch `development`, measured 2026-09-15 at `0202f253` unless a row says
otherwise. Historical rationale is distinguished below from implementation
evidence. Static searches are indicators, not proof that every dynamic consumer
or enforcement path has been examined. No measurement was repeated by this
editorial consolidation.

## 1. Corpus coverage and supporting observations

These eight rows preserve the design inventory. V-16 and V-18 are feasibility/layout
observations, not closed implementation requirements. Stating a requirement or
finding a provider resource does not establish rendering or backend conformance.

| ID | Gap / observation | Corpus treatment | Evidence boundary |
|---|---|---|---|
| V-01 | Enforcer type was not separated explicitly from instance/module | ADR 0119 D1.1 | Historical design finding; word counts do not prove conceptual absence |
| V-02 | Artifact grouping and target/scope attribution were conflated | ADR 0119 D1.1, D3 | Rev 3.4 requires attribution and explicit apply-unit grouping, not a universal root-per-instance rule |
| V-03 | W07 parameterised by `<backend>`, using backend and object module as synonyms | W07 amendment | Text of the Shape section at `3312ca0b` |
| V-06 | `enforcement_plane` carried role and type on one axis | ADR 0119 D1.1; ADR 0110 erratum | Class schema enum `[perimeter, internal]` with platform names in its prose |
| V-16 | Proxmox adapter feasibility needs explicit investigation | W07 target-layout choice | Provider resource availability is a feasibility input, not evidence of G4/G7 conformance for a pinned version |
| V-17 | ADR 0110 §1.1 transcription behind the implemented schema | ADR 0110 erratum | Diff of the ADR excerpt against `class.network.security_matrix.yaml` |
| V-18 | `bootstrap/` renders per device, `terraform/` per module | Cited as precedent in W07 | `find generated -maxdepth 3 -type d` |
| V-08 | `managed_by_ref` lost `target_class` with no recorded reason | ADR 0110 erratum, as a normative amendment | Class file carries no `target_class`; ADR excerpt carries `class.router` |

## 2. Open — the implementation does not meet what the corpus now requires

**Reconciled 2026-09-30** against `ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md`'s
own sequencing record (2026-09-28) and the real commits it cites, none of which
this table had been updated to reflect. Five of the original ten rows are closed;
one is closed on one side and worse on the other; four are unchanged. This
reconciliation is itself a static/code re-read, the same evidence class the
original measurement used - not a live/dynamic re-verification.

### 2a. Closed since the 2026-09-15 baseline

| ID | Requirement | Closed by | Evidence |
|---|---|---|---|
| V-04 | Type resolution and target validation use declared enforcement capability | `7d6a2072` (D-TYPE-1..3) | `cap.firewall.security_matrix.routeros`/`.pve` are no longer zero-consumer: `effective_model_compiler.py:296-303` uses them as D-TYPE-2's adapter-identifier vocabulary, and `test_effective_model_compiler.py:515,599,729` assert them as resolved values. **Caveat, 2026-09-30:** this closes the row's *type resolution* half, measured against the original zero-consumer evidence. The *target validation* half is narrower than it looks - `enforcer_resolution` is computed and published, but has zero consumers of its own anywhere in the MikroTik or Proxmox plugin trees, so nothing downstream actually validates a reference against it yet; see the "Reference names a target with no enforcement capability" counterexample in section 4, characterized the same day |
| V-05 | Devices declare what they enforce | `7d6a2072` | `obj.mikrotik.chateau_lte7_ax.yaml:262` declares `cap.net.l3.security.firewall.zone_policy`, exactly the device-kind capability `effective_model_compiler.py`'s `_ENFORCER_TYPE_CAPS["network"]` gates D-TYPE-1 on |
| V-09 | Every scope of an enforcer is projected | `e868abbe`, `168b4f27` | `_extract_security_matrix` now reads `composed_matrices_by_enforcer[router_id]`, which `security_matrix_compiler.py` already composes from the complete `scopes_by_enforcer` index (all scope_ids for that one enforcer merged, not the first match). The two-scope fixture in `test_projection_helpers.py` and the real one-scope topology (`generated/` byte-identical) both cover it. **Scoped to one enforcer**, per the commit's own text - see V-10 |
| V-13 | Enforcer-to-scope index is complete and deterministic | `c5f66c10` | `matrix_by_enforcer` no longer exists (`test_security_matrix_compiler.py:608` asserts it `not in` published keys); `scopes_by_enforcer` replaces it as `dict[str, list[str]]`, and `composed_matrices_by_enforcer` (the real consumer's channel) is built from it, not from a one-entry-per-enforcer dict; `E7010`/`E7011` registered |
| V-15 | One derivation per fact, pipeline-wide (Proxmox side) | `1336c12f` | `_extract_security_matrix_proxmox` is deleted; `proxmox/plugins/projections.py:115-124` records why (dead, zero consumers, confirmed by grep) and that a real consumer subscribes to `scopes_by_enforcer` directly when Proxmox firewall rendering stops being a stub |

### 2b. Still open, unchanged since the 2026-09-15 baseline

| ID | Requirement | State | Evidence |
|---|---|---|---|
| V-07 | Resolved type and adapter identity available in the derived scope/context contract | `enforcer_resolution` now exists and is wired as a plugin data-flow channel (`compilers.yaml:601`, `validators.yaml:483`), but that is not the G1/W03-registered scope/context **contract** this row asks for - a produces/consumes wire-up is not a schema registration | `topology-tools/plugins/manifests/compilers.yaml:601`; no `enforcer_resolution` entry in `topology-tools/schemas/` |
| V-10 | No single-instance assumption | `e868abbe`'s own commit message states this explicitly: *"Multiple enforcers in router_ids are not handled - the render context still carries one security_matrix value for the whole root, the still-blocked V-11/V-12 layout question, explicitly out of this step's scope"* - its new code chose the sorted-first router id "matching the single-router assumption already made elsewhere in this module," not removing it. The readiness record's own sequencing table (`ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md` section 4) groups V-10 into the same "Done" row as V-09 with the gloss "closed for multi-scope; multi-enforcer stays with V-11/V-12" - but V-10's own wording and original evidence were always about multi-*enforcer*, not multi-scope; that gloss appears to attribute V-09's closure to V-10 as well. The W07 migration order (2026-09-29/30) replicated the pattern verbatim into four new plugins rather than fixing it, and it is now dead code in `projections.py` itself | `default_router_id = next(iter(sorted(router_ids)), "")` and `len(router_ids) == 1`, replicated in `routing_policies_compiler.py:173,200`, `vlan_entries_compiler.py:125,138`, `mac_vlan_assignments_compiler.py:76,236`, `firewall_entries_compiler.py:103,114`; dead (no reader) at `projections.py:310` |
| V-11 | Explicit apply-unit/state/resource mapping; selected adapter layout implements it | One Terraform root per module; one unaliased `provider "routeros"` bound to one `var.mikrotik_host`; one state | `generated/home-lab/terraform/mikrotik/provider.tf` |
| V-12 | Connection binding per target | `mikrotik_host`, `mikrotik_api_host` and one `terraform_remote_state` are single-valued in plugin config | `topology/object-modules/mikrotik/plugins.yaml` |
| V-14 | Selection by declared class or capability | **Proxmox side closed** (`1336c12f`, 2 → 0, the deleted stub). **MikroTik side not closed, and worse**: the W07 migration order (2026-09-29/30) copied the router-filter and row-kind selectors verbatim into each of the ten new plugins rather than replacing them with declared-class/capability selection, so the count rose from 9 (one file) to 18 (across eleven files). The readiness record's section 4 groups V-14 into the same "Done" row as V-09/V-10 for `e868abbe`; that commit only removed the one substring selector inside `_extract_security_matrix` itself (replaced by a direct `composed_matrices_by_enforcer[router_id]` lookup) - a real, local fix, but not the corpus-wide finding this row measures | `grep -rn 'in object_ref\|in instance_id\|startswith("obj\.' topology/object-modules/mikrotik/plugins/` = 18 lines across 11 files (2026-09-30); `topology/object-modules/proxmox/plugins/` = 0 |

**Net: five of the original ten rows are closed (V-04, V-05, V-09, V-13, V-15); one
is split (V-14: Proxmox closed, MikroTik worse); four are unchanged (V-07, V-10,
V-11, V-12).** Where the readiness record's own sequencing table groups a row
under a "Done" commit alongside others, this section verifies each row
individually against current code rather than inheriting the grouping - two of
those groupings (V-10, V-14) turned out narrower than the row they were filed
under.

## 3. The index defect, reproduced

`matrix_by_enforcer` keys scopes by the enforcer they name. Because one enforcer may
hold several scopes, the last row processed wins and the result depends on input
order. Reproduced on the real compiler at `0202f253` with two matrices, distinct
ids and planes, one `managed_by_ref`:

| Input order | `matrix_by_enforcer['rtr.shared']` | Result |
|---|---|---|
| perimeter, internal | `inst.security_matrix.b` (internal) | SUCCESS, no diagnostics |
| internal, perimeter | `inst.security_matrix.a` (perimeter) | SUCCESS, no diagnostics |

`security_matrices` keeps both matrices in both runs. Two consequences, and the
second is the one that makes this more than an incomplete index: a scope is lost
without a diagnostic, and the surviving entry depends on the order of unordered
inputs, which ADR 0119 D4 forbids outright.

Subscribing a consumer to this channel and removing the projection's early return
would therefore not establish completeness or determinism. The channel contract is
fixed first - a complete collection in a deterministic order, or an explicit refusal
of multiplicity it cannot represent - and tested, before any consumer reads it.

**Closed by `c5f66c10` (V-13, section 2a).** `matrix_by_enforcer` no longer exists;
`scopes_by_enforcer` is the complete, deterministic `dict[str, list[str]]` this
section called for, and the real consumer (`_extract_security_matrix`) reads
`composed_matrices_by_enforcer`, built from it, not a one-entry-per-enforcer dict.
The reproduction above is retained as the record of what the defect was, not as
a description of current behavior.

## 4. Next implementation checks (planned, not executed here)

These refine existing W03/W06/W07 and A24/A26/A30 obligations, not new acceptance IDs.

| Counterexample / positive control | Required result | Status |
|---|---|---|
| Two devices of one type | Both projections retained, no target/resource leakage | **Independence pinned 2026-09-30** at the enforcer-resolution layer (`test_effective_model_resolves_two_instances_of_one_type_independently`, passed on first run - already-correct, `_resolve_enforcer` takes only per-call arguments and `enforcer_resolution` is keyed by instance_id). "Both projections retained" through to rendering is not implemented - blocked on V-11/V-12 - see the next row's fallback |
| Two scopes/planes on one device; reverse input order | Both scopes retained deterministically, or explicit unsupported-multiplicity diagnostic | **Split.** One-enforcer/two-scope retention was already covered (`test_mikrotik_projection_reads_a_two_scope_composed_plan`, predates this reconciliation) - that is V-09's closed concern. The **second outcome implemented 2026-09-30**: `_extract_security_matrix` now raises `ProjectionError` instead of silently picking the sorted-first enforcer when `composed_matrices_by_enforcer` holds a plan for more than one (`test_mikrotik_projection_refuses_more_than_one_enforced_router`). This is V-10's territory more than this row's title, given the V-10/V-14 misattribution section 2b already found - the row groupings in this table predate that finding and were not re-drawn |
| Generic + specific capabilities; multiple enforcement mechanisms | Provenance retained; no first-match type/adapter selection | **Assessed 2026-09-30, not attempted**: "provenance" here has no implemented mechanism to test against - `grep -rn provenance` in `capability_compiler.py` returns nothing, and this overlaps V-07 (already blocked on G1/W03 registering the derived scope/context contract). Writing a test would mean designing new infrastructure, not characterizing existing behavior; deferred rather than guessed at |
| Reference names a target with no enforcement capability | Visible refusal; a valid instance_ref alone is insufficient | **Characterized 2026-09-30, currently violated**: `test_mikrotik_projection_accepts_a_router_ref_the_type_resolver_would_refuse` runs the same instance shape through both compilers - `effective_model_compiler` correctly omits it from `enforcer_resolution` (no device-kind capability, D-TYPE-1 finds no candidate), but `build_mikrotik_projection` still accepts it as a router, since it decides router membership by `object_ref.startswith("obj.mikrotik.")` and never reads `enforcer_resolution` at all - which has **zero consumers** anywhere in the MikroTik or Proxmox plugin trees. Not fixed: wiring `enforcer_resolution` into router_ids across ~10 files is deferred as its own change |
| Zero or multiple compatible adapters | Visible unsupported/ambiguous result; no approximate rendering | **Both halves covered at the resolution layer.** Zero: `test_effective_model_warns_when_resolved_type_has_no_compatible_adapter` (W7016, pre-existing). Multiple: `test_effective_model_warns_when_resolved_type_has_ambiguous_adapters`, added 2026-09-30 - `_ENFORCER_ADAPTER_BY_TYPE` has exactly one OS-family entry per type today, so W7017 is structurally unreachable via any real capability declaration; unit-tests `_resolve_enforcer` directly with the class table monkeypatched to two entries, confirming the branch itself refuses rather than approximates. Neither half re-verified at rendering - no rendering path can reach either state while `_ENFORCER_ADAPTER_BY_TYPE` has one entry per type |
| Shared management endpoint, distinct target selectors | Valid explicit binding accepted; ambiguous target refused | **Characterized 2026-09-30, currently violated**: `test_mikrotik_vlan_entries_silently_drops_an_ambiguous_target` gives `object.mikrotik.compiler.vlan_entries` two routers and a VLAN row with no `managed_by_ref` and no matching `ip_allocations` entry - genuinely ambiguous, since the single-router default only applies with exactly one router. The row is silently excluded (`vlans == []`) with no diagnostic naming it at all, not the required visible refusal. `bridge_entries_compiler.py`, `firewall_entries_compiler.py`, `mac_vlan_assignments_compiler.py` and `routing_policies_compiler.py` share this exact pattern verbatim (migrated from the same source loop); not tested five times. Not fixed - same deferred-wiring reasoning as counterexample 4 |
| Adapter identity/version changed after checking | Affected plan/evidence binding invalidated | **Assessed 2026-09-30, not attempted**: `adapter_version` is `None` everywhere it is produced (`effective_model_compiler.py`, six call sites) - there is no populated version to change, and no plan/evidence digest-invalidation mechanism exists yet to test against (a search for `plan_digest`, `evidence_digest` and `invalidat` under `topology-tools/plugins/` finds only the unrelated security-plan validators). This is W08/G4 territory (offline artifact digest closure), not yet built; deferred rather than guessed at, same reasoning as counterexample 3 |
| Shared resource/state/apply unit | One writer and declared coupling; no isolation claim from directory layout | **Assessed 2026-09-30, blocked**: this is V-11/V-12's own territory (Terraform state/resource layout), already recorded in section 2b as blocked on a reviewed Terraform state-layout change that design preparation alone does not authorize. Not attempted for the same reason V-11/V-12 remain open |

Implement counterexamples and the complete index contract before adding its first
consumer. Preserve the positive controls: rejecting all targets is not a correct
implementation of deterministic dispatch.

The [readiness record](ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md), 2026-09-28,
sequenced these rows and specified that first channel change ahead of any
consumer: `scopes_by_enforcer` (`c5f66c10`, 2026-09-28) replaced `matrix_by_enforcer`
before `_extract_security_matrix` was wired to the composed result it feeds
(`e868abbe`, 2026-09-29) - the ordering this section asked for, followed. It also
extended two rows from repeated measurement: `security_matrices` is complete in
membership but permutation-sensitive in order, and V-09 is a singular return type
across projection, generator and template rather than one dropped row. All eight
counterexample rows above carry real 2026-09-30 evidence now (Status column):
two closed (1, 5), two split with one half fixed (2, 6 - both the same class of
silent-drop gap V-10 already named, now demonstrated in `vlan_entries_compiler.py`
alongside `_extract_security_matrix`), two characterized as currently violated
without a fix attempted (4, and 6's still-open half), and two assessed and
deferred because the infrastructure they would test does not exist yet (3, 7) or
because fixing them is blocked on the same reviewed layout change as V-11/V-12
(8). None of the eight map to V-04/V-05/V-09/V-13/V-15 (section 2a, closed); most
map to V-10/V-11/V-12, still open (section 2b) - V-10's own gap is now an
explicit refusal in one place (`_extract_security_matrix`) and a demonstrated,
unfixed silent drop in five more (`vlan_entries_compiler.py` and the four other
verbatim-migrated plugins), which is real progress but not the closure V-10's
title asks for (multi-enforcer rendering stays blocked on V-11/V-12). The
readiness record closes no gate, and neither does this reconciliation or the
2026-09-30 work above - see section 5.

## 5. What this record does not claim

No gate is closed by anything here. Nothing is qualified. The rows in section 1 are
statements the corpus now makes, not behaviour that was verified on a device; the
open rows in section 2b describe source/output gaps rather than an installed
system; and the 2026-09-30 reconciliation that closed five section 2a rows is a
static/code re-read, the same evidence class as the original measurement, not a
live or dynamic re-verification, and not a gate closure - see section 2's own
opening note. The section 4 tests remain implementation work, not evidence
produced by this record.

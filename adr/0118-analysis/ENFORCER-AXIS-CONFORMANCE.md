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

There are **ten** open implementation rows: V-04, V-05, V-07 and V-09..V-15.
Their status is not changed by the documentation amendment.

| ID | Requirement | State | Evidence |
|---|---|---|---|
| V-04 | Type resolution and target validation use declared enforcement capability | `cap.firewall.security_matrix`, `.routeros` and `.pve` are registered in the catalogue and have **zero** consumers | `grep -rn cap.firewall.security_matrix` outside the catalogue returns nothing across `*.py`, `*.yaml`, `*.j2` |
| V-05 | Devices declare what they enforce | **No** device object declares any `cap.firewall.*` enforcement capability | Only `obj.network.firewall_policy.established_related.yaml` declares `cap.firewall.*`, and only `stateful` / `connection_tracking` |
| V-07 | Resolved type and adapter identity available in the derived scope/context contract | Derivation/consumer contract remains open; do not add a duplicate authored type field | G1/W03 must register the derived contract; absence from authored class properties alone is not proof about compiled output |
| V-09 | Every scope of an enforcer is projected | `_extract_security_matrix` returns inside its loop; the first matching matrix wins, the rest are dropped silently | `projections.py:105` (line renumbered by the W07 migration order, 2026-09-30; the defect itself is unchanged - this function was not a migration candidate) |
| V-10 | No single-instance assumption | The pattern - `default_router_id = next(iter(sorted(router_ids)), "")` feeding a branch guarded by `len(router_ids) == 1`, commented "single-router topology" - was replicated verbatim into four new compile-stage plugins by the W07 migration order (2026-09-30), which moved the functions that used it rather than fixing it: `routing_policies_compiler.py:173,200`, `vlan_entries_compiler.py:125,138`, `mac_vlan_assignments_compiler.py:76,236`, `firewall_entries_compiler.py:103,114`. In `projections.py` itself the assumption is now dead code: `default_router_id` (line 310) has no remaining reader, since every branch that used it moved out with the functions it fed. |
| V-11 | Explicit apply-unit/state/resource mapping; selected adapter layout implements it | One Terraform root per module; one unaliased `provider "routeros"` bound to one `var.mikrotik_host`; one state | `generated/home-lab/terraform/mikrotik/provider.tf` |
| V-12 | Connection binding per target | `mikrotik_host`, `mikrotik_api_host` and one `terraform_remote_state` are single-valued in plugin config | `topology/object-modules/mikrotik/plugins.yaml` |
| V-13 | Enforcer-to-scope index is complete and deterministic | `matrix_by_enforcer` is published with **zero** subscribers, and it is a one-entry-per-enforcer dict; see section 3 | `security_matrix_compiler.py:118,146`; `grep` for `subscribe(... "matrix_by_enforcer")` returns nothing |
| V-14 | Selection by declared class or capability | 9 substring selectors remain in the MikroTik projection, 2 in the Proxmox projection | `grep -n 'in object_ref\|in instance_id\|startswith("obj\.'` |
| V-15 | One derivation per fact, pipeline-wide | `_extract_security_matrix_proxmox` is a second derivation: `STUB`, selects on two substrings of `instance_id`, consumes no channel, and its module declares `depends_on: []` with no `consumes` | `proxmox/plugins/projections.py:52`; `proxmox/plugins.yaml` |

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

## 4. Next implementation checks (planned, not executed here)

These refine existing W03/W06/W07 and A24/A26/A30 obligations, not new acceptance IDs.

| Counterexample / positive control | Required result |
|---|---|
| Two devices of one type | Both projections retained, no target/resource leakage |
| Two scopes/planes on one device; reverse input order | Both scopes retained deterministically, or explicit unsupported-multiplicity diagnostic |
| Generic + specific capabilities; multiple enforcement mechanisms | Provenance retained; no first-match type/adapter selection |
| Reference names a target with no enforcement capability | Visible refusal; a valid instance_ref alone is insufficient |
| Zero or multiple compatible adapters | Visible unsupported/ambiguous result; no approximate rendering |
| Shared management endpoint, distinct target selectors | Valid explicit binding accepted; ambiguous target refused |
| Adapter identity/version changed after checking | Affected plan/evidence binding invalidated |
| Shared resource/state/apply unit | One writer and declared coupling; no isolation claim from directory layout |

Implement counterexamples and the complete `matrix_by_enforcer` contract before
adding its first consumer. Preserve the positive controls: rejecting all targets
is not a correct implementation of deterministic dispatch.

The [readiness record](ENFORCER-SCOPE-IMPLEMENTATION-READINESS.md), 2026-09-28,
sequences these rows, specifies that first channel change, and extends two rows
here from repeated measurement: `security_matrices` is complete in membership but
permutation-sensitive in order, and V-09 is a singular return type across
projection, generator and template rather than one dropped row. It closes no gate.

## 5. What this record does not claim

No gate is closed by anything here. Nothing is qualified. The rows in section 1 are
statements the corpus now makes, not behaviour that was verified on a device, and
the rows in section 2 describe source/output gaps rather than an installed system.
The section 4 tests remain implementation work, not evidence produced by this record.

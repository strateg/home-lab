# Enforcer axes — what the corpus requires and what the code does

Status: measurement record for the ADR 0118/0119 rev 3.3/3.4 amendment.
Not a plan, not an authorization, and not evidence that anything is qualified.

This is the artifact the rev 3.3 commit message described and did not publish; the
[rev 3.3 review](../../docs/reports/2026-09-15-adr0118-0119-rev33-review-0202f253.md)
was right that a summary in a commit body is not a referenced matrix. Identifiers
`V-01`..`V-18` are used by that review and by the session record; they are fixed
here so they can be cited.

Baseline: branch `development`, measured 2026-09-15 at `0202f253` unless a row says
otherwise. Every row names how it was measured.

## 1. Closed by the amendment

These were gaps in the normative corpus. The text now states the requirement; the
code does not yet meet it, which is section 2.

| ID | Gap | Closed by | Measured as |
|---|---|---|---|
| V-01 | No notion of enforcer type anywhere in the corpus | ADR 0119 D1.1 | `grep -c enforcer` gave 1 in ADR 0118 (incidental) and 8 in ADR 0119, all in D1/D2 |
| V-02 | Nothing required artifacts per enforcer instance | ADR 0119 D1.1, D3 | Absent from both ADRs and all annexes |
| V-03 | W07 parameterised by `<backend>`, using backend and object module as synonyms | W07 amendment | Text of the Shape section at `3312ca0b` |
| V-06 | `enforcement_plane` carried role and type on one axis | ADR 0119 D1.1; ADR 0110 erratum | Class schema enum `[perimeter, internal]` with platform names in its prose |
| V-16 | Whether pve-firewall is Terraform-expressible was unestablished | W07 amendment | `bpg/proxmox` publishes 8 firewall resource docs; `proxmox_virtual_environment_firewall_rules` scopes by `node_name`, `vm_id`, `container_id` |
| V-17 | ADR 0110 §1.1 transcription behind the implemented schema | ADR 0110 erratum | Diff of the ADR excerpt against `class.network.security_matrix.yaml` |
| V-18 | `bootstrap/` renders per device, `terraform/` per module | Cited as precedent in W07 | `find generated -maxdepth 3 -type d` |
| V-08 | `managed_by_ref` lost `target_class` with no recorded reason | ADR 0110 erratum, as a normative amendment | Class file carries no `target_class`; ADR excerpt carries `class.router` |

## 2. Open — the implementation does not meet what the corpus now requires

None of these is a defect of the amendment. Each is the system as measured.

| ID | Requirement | State | Evidence |
|---|---|---|---|
| V-04 | Type resolves from declared enforcement capability | `cap.firewall.security_matrix`, `.routeros` and `.pve` are registered in the catalogue and have **zero** consumers | `grep -rn cap.firewall.security_matrix` outside the catalogue returns nothing across `*.py`, `*.yaml`, `*.j2` |
| V-05 | Devices declare what they enforce | **No** device object declares any `cap.firewall.*` enforcement capability | Only `obj.network.firewall_policy.established_related.yaml` declares `cap.firewall.*`, and only `stateful` / `connection_tracking` |
| V-07 | Enforcer type available as a derived field of the scope | Field absent; deliberately not added before its derivation exists | `class.network.security_matrix.yaml` property list |
| V-09 | Every scope of an enforcer is projected | `_extract_security_matrix` returns inside its loop; the first matching matrix wins, the rest are dropped silently | `projections.py:750` |
| V-10 | No single-instance assumption | `default_router_id = next(iter(sorted(router_ids)), "")` and a branch guarded by `len(router_ids) == 1`, commented "single-router topology" | `projections.py:1327`, `:1355` |
| V-11 | One apply unit per enforcer instance | One Terraform root per module; one unaliased `provider "routeros"` bound to one `var.mikrotik_host`; one state | `generated/home-lab/terraform/mikrotik/provider.tf` |
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

## 4. What this record does not claim

No gate is closed by anything here. Nothing is qualified. The rows in section 1 are
statements the corpus now makes, not behaviour that was verified on a device, and
the rows in section 2 are measurements of source and output rather than of an
installed system.

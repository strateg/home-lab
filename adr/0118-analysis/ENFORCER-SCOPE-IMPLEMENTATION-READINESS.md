# Enforcer/scope implementation readiness

Status: measurement record and bounded implementation specification for the next
code change under W07 / gate G4. Not an authorization, no gate closed, nothing
qualified, no deployment implied. No code, schema, manifest or artifact is changed
by this document.

Date: 2026-09-28. Baseline: branch `development`, working tree at `48a7ac3f` plus
the uncommitted rev 3.4 editorial consolidation of the ADR corpus. Every row below
names the command or file it was measured from; measurements were taken on this
working tree, not copied from earlier records.

Authority: [ADR 0118](../0118-universal-container-network-model.md),
[ADR 0119 D1-D1.1 rev 3.4](../0119-firewall-rule-ordering-contract.md),
[architecture rev 3.4](FINAL-ARCHITECTURE-PROPOSAL.md).
Owns the ten open implementation rows: [conformance record](ENFORCER-AXIS-CONFORMANCE.md).
Owns the layout decision: [W07](W07-BACKEND-SPECIALIZATION-DECISION.md).
Owns gate sequencing: [roadmap](IMPLEMENTATION-ROADMAP-2026-09-15.md).

## 1. What this record adds

The conformance record lists ten open implementation rows and eight planned
counterexamples. It does not say which of them is implementable next, which is
blocked on a decision rather than on code, and what the first change's contract
actually is. This record answers those three questions and corrects or extends
five rows from measurements repeated here.

It does not re-open any accepted decision and it allocates no authority.

## 2. Baseline, re-measured

| What | Measured value | How |
|---|---|---|
| W07 boundary budget | **9 passed**, 0 failed | `pytest tests/test_backend_specialization_boundary.py -q` |
| Projection size | 1,518 lines, 15 functions | as recorded at `ed15dfbf`; the boundary test asserts it |
| Enabled scopes in topology | **one** | `inst.security_matrix.mikrotik`; `inst.security_matrix.proxmox` carries `status: disabled` and no `managed_by_ref` |
| Rendered scopes | **one** | `generated/home-lab/terraform/mikrotik/zone_firewall.tf:2` names `inst.security_matrix.mikrotik` |
| Proxmox firewall artifacts | none | `ls generated/home-lab/terraform/proxmox/` - no firewall file |
| `E7009`, `E7010`-`E7019` (all of E/W/I) | **unclaimed** | `grep -rEon '[EWI]70(09\|1[0-9])'` over `*.py *.yaml *.md *.j2 *.json`, excluding `build/` and `.venv/`, returns nothing |

The roadmap's recorded boundary baseline - "1 failed, 6 passed" - was measured at
`97f06ffd`, before `ed15dfbf` landed W07 step 2. It is stale, not wrong for its
own revision. The full-suite figure is recorded in section 7.

## 3. Reproduced, and where the conformance record needs extending

### 3.1 V-13 reproduced independently

Two matrices, distinct ids and planes, one `managed_by_ref`, run through the real
compiler on this tree:

| Input order | `matrix_by_enforcer['rtr.shared']` | `security_matrices` iteration order | Status / diagnostics |
|---|---|---|---|
| perimeter, internal | `inst.security_matrix.b` | `a`, `b` | SUCCESS, none |
| internal, perimeter | `inst.security_matrix.a` | `b`, `a` | SUCCESS, none |

The record's finding stands. Two extensions:

**(a) The complete channel is permutation-sensitive too.** The record says
`security_matrices` keeps both matrices in both runs. That is true of *membership*
and not of *order*: the dict is insertion-ordered over `matrix_instances`, which
follows row order. Its one real consumer merges zone payloads across matrices with
`dict.update` (`projections.py:1519`). Today that merge is order-insensitive,
because every matrix's `zones` payload for a given `zone_ref` is copied from the
one shared `zone_index`, so the values collide identically. The artifact therefore
does not move. The published channel is nonetheless order-dependent, which ADR 0119
D4 forbids of a published channel whether or not a consumer currently notices.
Stating it the other way round - "no consumer notices, so it is deterministic" - is
the reasoning D4 exists to refuse.

**(b) V-09 is a type, not a lost row.** The record reads as though an early
`return` drops the remaining matrices. The stronger fact is that the whole chain is
singular and cannot represent a second scope at all:

```
_extract_security_matrix(...) -> dict          one scope   projections.py:552
generator: projection["security_matrix"]       one scope   terraform_mikrotik_generator.py:193
render context: "security_matrix": ...         one scope   terraform_mikrotik_generator.py:278
zone_firewall.tf.j2: security_matrix.get(...)  one scope   templates/terraform/zone_firewall.tf.j2:13
```

So removing the `return` is not the fix and would not even compile into a correct
result: the change is a return-type and render-grouping change across four
artifacts. This is why the record's instruction - fix the channel contract before
adding a consumer - is the right order, and why V-09 is not a small follow-up.

### 3.2 New findings

Identifiers `N-01`..`N-05`, distinct from `V-*` and from the review's `R1`..`R6`.

| ID | Finding | Evidence |
|---|---|---|
| N-01 | The replacement target check V-08 calls for has an identified mount point, and that point is today an **explicit exclusion**. `class.network.security_matrix` is in `_NETWORK_CLASS_EXCLUSIONS` in two validators, both carrying the comment "ADR-0110: managed_by_ref may be router OR hypervisor". The `target_class: class.router` check was not generalised to "enforcement-capable target"; it was switched off. | `network_core_refs_validator.py:30`, `declarative_reference_validator.py:58`; the live `managed_by_ref` check for other classes is `E7835` at `:106` and `:393` |
| N-02 | V-04/V-05 is blocked on a **namespace decision**, not on adding a declaration. The catalogue documents two boundaries: `cap.net.l3.security.firewall.*` = "Router firewall (device feature)", layer L1; `cap.firewall.*` = "Firewall policy object capabilities (L2)", layer L2. But `cap.firewall.security_matrix`, `.routeros` and `.pve` are registered at L2 with **device** summaries ("Device can enforce...", "Enforces security matrix via RouterOS firewall"). The L1 device slot that already exists for this is `cap.net.l3.security.firewall.zone_policy`. | `capability-catalog.yaml:41-42` (boundaries), `:265-292` (the three), `:1880` (zone_policy) |
| N-03 | The enforcer of record declares **neither** enforcement capability, and a non-enforcer declares one. `obj.mikrotik.chateau_lte7_ax` declares `cap.net.l3.security.firewall.stateful` and `.l7_filtering`, not `.zone_policy` and no `cap.firewall.*`. `obj.glinet.slate_ax1800` declares `.zone_policy` and enforces no matrix. | `obj.mikrotik.chateau_lte7_ax.yaml:237-262`, `obj.glinet.slate_ax1800.yaml:232` |
| N-04 | `enabled_packs` never reach the effective capability set, so a pack cannot satisfy any future capability check. The Chateau enables `pack.router.enterprise`, which lists `.zone_policy`; the capability compiler derives only `cap.os.*`, `cap.bootstrap.*`, `cap.vendor.*`, `cap.role.*`, `cap.arch.*`, `cap.firmware.*`, and the projection's reader takes `capabilities`, `derived_capabilities`, `enabled_capabilities`, `vendor_capabilities` - never `enabled_packs`. The packs are validated for consistency and then dropped. | `capability_compiler.py:9-15`, `projections.py:23-48`, `capability-packs.yaml:161,188` |
| N-05 | A scope with **no** `managed_by_ref` compiles clean and is enforced by nobody, silently. The compiler publishes it into `security_matrices` with `managed_by_ref: None` and emits no diagnostic, although the class schema lists `managed_by_ref` as required. The MikroTik projection skips it (`managed_by not in router_ids`). The Proxmox stub generator's active-matrix test requires `managed_by_ref` to be set *and* Proxmox-owned, so it reports `I9302` "No active security matrix found - skipping". This is the present state of `inst.security_matrix.proxmox`. | reproduced on the real compiler; `class.network.security_matrix.yaml:12-16`; `projections.py:593`; `firewall_proxmox_generator.py:133-190` |

Two smaller observations, recorded so they are not rediscovered:

* The Proxmox firewall **generator** is a *third* derivation of the
  enforcer->scope relation, after the compiler and the MikroTik projection. It reads
  `compiled_json` directly with `depends_on: []`, selects Proxmox hosts by the
  substring `"proxmox"` in `extends_object`, and `break`s at the first match, so
  with two Proxmox scopes its `E9303` would name one. It does fail closed on an
  active matrix, which is the right behaviour for a stub; the defect is the
  derivation, not the refusal. (`firewall_proxmox_generator.py:118-157`, `:154`,
  `proxmox/plugins.yaml:188`.)
* The compiler defaults `enforcement_plane` to `"perimeter"` when neither instance
  nor object declares it, although the class schema makes it required
  (`security_matrix_compiler.py:148-154`). On the real topology both objects
  declare it, so the default is **latent, not active** - a silent default for a
  required property, of the same family as the fallbacks W07 removed.

## 4. Sequencing: what is implementable now, and what is not

| Row | State | What it waits on |
|---|---|---|
| V-13, N-05, plane default | **Implementable now** | nothing; zero subscribers on `matrix_by_enforcer`, so no consumer migration is entangled |
| V-15 (Proxmox second/third derivation) | Implementable now | the channel contract below, so the stub has something to consume |
| V-09, V-10, V-14 | Blocked on V-13 landing | the consumer chain is a return-type change across projection, generator and template; it needs the channel to be able to express multiplicity first |
| V-04, V-05, V-08, N-01-N-04 | **Blocked on a decision, not on code** | which registered namespace is the enforcement-capability axis (N-02), what becomes of the other three identifiers, and whether `enabled_packs` contribute to the effective set (N-04). Adding a declaration before that decision picks the axis by accident - the failure mode ADR 0119 D1.1 names |
| V-07 | Blocked on G1/W03 | the derived scope/context contract must be registered before a field claims to carry resolved type and adapter identity |
| V-11, V-12 | Blocked on a reviewed behaviour change | the W07 root/state migration relocates Terraform state; W07 records it as design preparation and explicitly not authorization to migrate state |

The decision in row four is the single highest-value item this record surfaces,
because it is cheap to get wrong silently. It belongs in the ADR corpus, not in a
commit: it changes what "resolved from the device's declared enforcement
capability" denotes. Recommended framing for that decision, not adopted here:
the device axis is `cap.net.l3.security.firewall.*` (already L1, already declared
by devices, already in `class.router`'s supported list), the three
`cap.firewall.security_matrix*` identifiers are the *adapter/mechanism* axis rather
than the device axis, and `enabled_packs` either expand into the effective set or
stop being written as if they grant capabilities. That is a proposal requiring
review, and section 5 does not depend on it.

## 5. The first change, specified

Scope: the compiler's published enforcer->scope contract and its diagnostics.
Nothing else. No consumer is migrated, no artifact path moves, no capability check
is added, no state is relocated.

### 5.1 Channel contract

`matrix_by_enforcer: dict[str, str]` cannot represent the one-to-many relation ADR
0119 D1.1 states, so it is replaced rather than repaired. Proposed shape:

```python
scopes_by_enforcer: dict[str, list[str]]   # enforcer id -> sorted scope ids, complete
```

with both levels deterministic: keys in sorted order, each value sorted, built by
sorting the collected pairs rather than by relying on input order. `security_matrices`
is published in sorted key order for the same reason.

The rename is part of the change and not cosmetic: the key's present name says
*matrix*, singular, keyed by enforcer, which is the defect written into the
identifier. Renaming is safe here precisely because the channel has zero
subscribers - verified by `grep` for `subscribe(... "matrix_by_enforcer")`
returning nothing outside the compiler and its own test.

The alternative - keep one entry per enforcer and refuse multiplicity with a
diagnostic - is rejected, because the model states the relation is one-to-many, so
refusing it would encode the defect as a rule. A refusal is still required for the
cases the *backends* cannot render (section 5.2), which is a different statement:
the model represents several scopes; a given adapter may decline to render them.

### 5.2 Diagnostics

Inside the ADR 0118/0119 allocation `E70xx`/`W70xx`/`I70xx`, in the unclaimed
contiguous sub-band `7009`-`7019`. The collision check the allocation requires is
in section 2 and returned nothing. Proposed entries, each raised by the same change
that registers it so nothing lands on the awaiting-a-mount ledger:

| Code | Severity / stage | Condition |
|---|---|---|
| `E7010` | error / compile | A scope declares no enforcer. Attribution is required; an unattributed scope is enforced by nobody and today says nothing. Closes N-05. |
| `E7011` | error / compile | A scope declares no enforcement plane and neither instance nor object supplies one. Replaces the silent `"perimeter"` default. |
| `W7012` | warning / compile | An enforcer holds several scopes. Not an error - the model permits it - but it is the case no current adapter renders, so it is reported rather than discovered later as a missing artifact. Downgraded or removed when the consumer chain lands. |

`E7010` and `E7011` are behaviour changes on inputs the class schema already calls
required, so they are reviewed as such: on the real topology `E7010` fires for
`inst.security_matrix.proxmox`, which is `status: disabled` and therefore must be
handled explicitly - either by the compiler skipping disabled instances (a separate
contract, since `status` is currently pure passthrough) or by the instance
declaring its enforcer. Choosing that is part of the change and must not be settled
by whichever makes the suite green.

### 5.3 Manifest

`topology-tools/plugins/manifests/compilers.yaml:545` replaces the
`matrix_by_enforcer` `produces` entry with `scopes_by_enforcer`. No `consumes`
entry anywhere changes, since there is no subscriber.

### 5.4 Tests

Against `tests/plugin_integration/test_security_matrix_compiler.py`, whose present
`test_matrix_by_enforcer_published` asserts only that the key exists - a presence
check, which is what let the defect live under a passing test. Counterexamples,
from the conformance record's section 4, narrowed to this change's scope:

| Case | Required result |
|---|---|
| Two scopes on one enforcer | both scope ids present under that enforcer |
| The same two, input order reversed | byte-identical published channel |
| Two enforcers, one scope each | both keys present, no cross-attribution |
| Scope with no `managed_by_ref` | `E7010`, and the scope does not appear under any enforcer |
| Scope with no plane anywhere | `E7011` |
| Permutation of the whole row list | `security_matrices` and `scopes_by_enforcer` both byte-identical |

Positive controls, kept explicitly, because refusing everything would pass every
counterexample above: the single-scope single-enforcer topology still compiles
SUCCESS with no diagnostics and the same published content as today; the real
project topology still produces the same `security_matrices` payload.

### 5.5 Parity

Expected artifact parity: **unchanged output**. One enabled scope, one rendered
scope, no consumer of the renamed channel. Any artifact diff is a defect in the
change, not an accepted consequence, with the single exception of whatever is
decided for `inst.security_matrix.proxmox` under `E7010` - which, if it results in
a compile error, is a blocked pipeline rather than a changed artifact and must be
resolved before the change lands. Evidence: two compilations under symmetric
conditions with the declared W13 exclusions, plus the full suite and the narrowest
relevant Task gate.

## 6. What this record does not do

No gate advances. `W07`/`G4` are not closed by section 5: it repairs one published
channel and adds three diagnostics, and the layout migration, the consumer chain,
the capability axis and the apply-unit contract all remain open. The section 4
sequencing is a reading of existing obligations, not new acceptance IDs. The
namespace framing in section 4 is a proposal awaiting review, and no part of this
record authorizes a state migration, a device operation or a deployment.

## 7. Command evidence

```
pytest tests/test_backend_specialization_boundary.py -q     9 passed
grep -rEon '[EWI]70(09|1[0-9])' ... (excl. build/, .venv/)  no matches
grep -rn 'subscribe(.*matrix_by_enforcer'                   no matches
pytest tests -q -p no:randomly                              see below
```

Full-suite result at this tree: PENDING at the time of writing; it is a measurement
of the unchanged baseline, and no claim in this record depends on it.

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

**Implementation status, 2026-09-28 (updated).** Three changes have landed on
branch `adr-0118-0119`, in order:

1. `c5f66c10` - section 5: `matrix_by_enforcer` replaced by `scopes_by_enforcer`,
   `E7010`/`E7011`/`W7012` added, section 5.4 counterexamples as `TestScopesByEnforcer`.
2. `1336c12f` - V-15: the Proxmox projection's dead second derivation deleted.
3. `e72d0099` - section 5c: `composed_matrices_by_enforcer` published, `E7013`/`E7014`
   added, `TestComposedMatricesByEnforcer`.

Evidence for each is in section 7. None closes W07/G4 - see section 6, unchanged.
Sections 1-3 are not revised: the measurements they record predate all three
changes and are still accurate as a baseline for this tree. Section 4's
sequencing reflects the current state after all three.

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
| V-13, N-05, plane default | **Done** - `c5f66c10` | `scopes_by_enforcer` published, complete and deterministic; `E7010`/`E7011` refuse the two silent gaps |
| V-15 (Proxmox second/third derivation) | **Done** - `1336c12f` | dead second derivation deleted (zero consumers, confirmed by grep); golden snapshot updated; `depends_on: []` left as is, since no real consumer exists yet to justify wiring `scopes_by_enforcer` there |
| V-09, V-10, V-14 | Composition landed (5c); consumer chain still unstarted | `composed_matrices_by_enforcer` published, zero subscribers; `_extract_security_matrix` in `projections.py` still first-matches directly. Wiring the projection and a two-scope fixture remain |
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

## 5b. Next candidate: corrected, and larger than first sketched

V-09/V-10/V-14 - the consumer chain - is the next implementable-now row per
section 4. The first version of this section proposed "one rendered block per
scope." That is wrong, for a reason found by reading the templates rather than
guessing the shape, and the correction changes where the work belongs.

### N-06: RouterOS has one forward chain, not one per scope

`zone_firewall.tf.j2` emits exactly one terminal-deny resource,
`routeros_ip_firewall_filter.zone_drop_all_forward`, and every deny and
policy-override rule in the same file places itself before it by that literal
Terraform address. `vpn.tf.j2` references the same address by name at two more
call sites, to place tunnel-egress and container firewall rules ahead of it.
Five hardcoded references across two files, confirmed by grep, all assuming
there is exactly one.

This is not a template limitation to lift. RouterOS has one `forward` chain per
device; a device with two scopes still has one chain, and a chain can only
have one meaningful final deny - whichever renders last is the one that acts,
and every earlier rule's `place_before` target has to be it. "One block per
scope" would either collide two resources both named
`zone_drop_all_forward`, or rename them per scope and leave `vpn.tf.j2`
pointing at an arbitrary one of several. Rendering-multiple-blocks is not a
looser version of the correct fix; it does not compile into a correct result
at all, the same character of mistake section 3.1(b) found in the original
V-09 read of `_extract_security_matrix`.

**What follows: composition, not iteration.** Two scopes on one enforcer must
become one validated, composed plan before anything renders - matching ADR
0119 D1's own language, "one logical plan authority producing one projection
per scope" feeding "one owned resource set per apply unit," and D1's explicit
warning that composition across scopes sharing an enforcer is checked, not
assumed. Concretely, for the MikroTik adapter's existing single-chain,
single-root shape:

- **Zones union safely.** A zone's data (`name`, `security_level`, `isolated`,
  `cidrs`) is read from one shared `zone_index` in the compiler regardless of
  which scope references it (`security_matrix_compiler.py`), so two scopes
  naming the same `zone_ref` carry identical data. A dict union across scopes
  - what `projections.py:1519` already does for the single scope it reads
    today - produces no duplicate address-list resource and needs no conflict
    check.
- **Matrix cells do not.** `matrix` is `{from_zone: {to_zone: cell}}`, authored
  per scope. Two scopes disagreeing on the same `(from_zone, to_zone)` pair is
  a real contradiction, not a naming collision, and silently keeping whichever
  scope's cell a dict-update processed last would be the *same defect class*
  V-13 fixed for the enforcer index - a silent, input-order-dependent
  overwrite - reintroduced one level deeper. It needs an explicit check and a
  diagnostic, not a merge.
- **Policy overrides do not either.** They are an authored list, not a dict, so
  concatenating two scopes' lists loses nothing by itself - but
  `zone_override_{{ override_name }}` derives the Terraform resource name from
  the override's own `name` field alone, which nothing enforces as unique
  across separate `security_matrix` instances. Two scopes each authoring an
  override called e.g. `admin-access` collide at the same
  `routeros_ip_firewall_filter.zone_override_admin_access` address.
- **Render order is a plan property, not a template one.** ADR 0119 D4 already
  requires deterministic order without semantic guessing; the composed cell/
  override sequence needs its own fixed order (scope-id sorted, matching
  `scopes_by_enforcer`'s own determinism) fed to the template, not left to
  however Jinja happens to iterate a merged structure.

**Where it belongs.** ADR 0119 D4 already draws this line for the terminal
deny - "the plan compiler emits it and the template only renders it" - and the
same rule applies to composition: it is compile-stage work, most naturally an
extension of `security_matrix_compiler.py` (which already owns one derivation
of this fact) consuming its own `security_matrices` and `scopes_by_enforcer`
output to build one validated composed plan per enforcer with an *unchanged*
shape - the same `{zones, matrix, policy_overrides}` dict `zone_firewall.tf.j2`
already consumes. Read this way, the generate-stage touch points from the
first sketch shrink to almost nothing: the projection and template keep
consuming one flat structure per enforcer; only what feeds it changes, from
first-match to composed-and-checked. What grows is a new compile-stage
composition step with real conflict semantics to design - closer in size to a
second D1.1-style contract than to section 5's channel rename.

**Touch points, corrected:**

```
security_matrix_compiler.py   DONE (e72d0099, section 5c): composes
                               scopes_by_enforcer[e] into one validated
                               per-enforcer plan, diagnoses matrix-cell and
                               override-name conflicts instead of merging them
projections.py  _extract_security_matrix(...)   OPEN: still first-matches
                matrix_instances directly; needs to read the composed plan
                for this router instead
templates/terraform/zone_firewall.tf.j2   unchanged in shape; will consume
                                           composed input once wired
templates/terraform/vpn.tf.j2             unchanged; the single zone_drop_all_forward
                                           reference stays valid because there is still one
```

**What it needed before it could be specified like section 5 was.** Two of
the three items below are now resolved in section 5c; only the fixture and
parity work remain open.

- ~~Conflict semantics for matrix cells~~ - resolved, section 5c D-COMP-1:
  disjoint zones make the conflict structurally impossible rather than
  something to adjudicate.
- ~~A decided uniqueness rule for policy-override names~~ - resolved, section
  5c D-COMP-2: unique per enforcer, refused on collision.
- A two-scope MikroTik fixture (real or synthetic) to serve as the positive
  control and the D-COMP-1/D-COMP-2 counterexamples; the live topology has
  exactly one enabled scope today. Still open.
- Parity evidence against the real topology's one-scope case, the same way
  section 5.5 required it, plus the conformance record's remaining
  counterexamples this record has not yet exercised: two devices of one type
  (no target/resource leakage), and the zero/multiple-adapter cases, which
  belong to V-04/V-05 and stay blocked on the capability-axis decision even
  once this chain lands. Still open.

## 5c. Composition contract, decided 2026-09-28

The two open questions above are resolved here, narrower in scope than N-02:
this governs only how the MikroTik adapter composes several scopes on one
enforcer, a case unexercised anywhere in the real topology today. It fulfils
ADR 0119 D1's existing requirement - "composition across scopes sharing an
enforcer... validated rather than assumed" - rather than amending the ADR.

**D-COMP-1, zones: pairwise disjoint, refused on overlap.** Scopes composed
for one enforcer must not share a `zone_ref`. This is deliberately stricter
than "merge if identical": a cell for `(from_zone, to_zone)` can only exist in
a scope whose `zone_refs` contains both, so disjoint zones make a matrix-cell
collision between scopes structurally impossible - there is no equal-cells
comparison to design, implement or get subtly wrong. The cost is real: a
future need for two scopes to legitimately share a zone (e.g. one scope for
base connectivity, another for audit logging over the same zone) is refused
today, not accommodated. That is the intended direction - starting strict and
loosening later is a reviewed amendment; starting permissive and restricting
later breaks whatever already relied on the permissive behaviour. If that need
arises, it is a new decision, not a bug in this one.

**D-COMP-2, policy overrides: unique names, refused on collision.** Every
`policy_overrides` entry's `name` must be unique across every scope one
enforcer composes - not globally, since the Terraform root is per enforcer
today and only names rendered into one root can collide at
`routeros_ip_firewall_filter.zone_override_<name>`. Two different enforcers
may reuse a name freely. This is a refusal, not a rename-to-disambiguate:
silently qualifying a collided name would hide the authoring problem inside
generated output instead of surfacing it to the author, the same reasoning
D1.1 already applies to adapter resolution - ambiguity is reported, not
guessed past.

**D-COMP-3, composed shape.** For enforcer `e` with scopes `scopes_by_enforcer[e]`
in their existing sorted order: `zones = union` of each scope's zones (safe
under D-COMP-1: disjoint keys, no collision possible), `matrix = union` of
each scope's matrix (safe for the same reason - a shared key is exactly what
D-COMP-1 refuses upstream), `policy_overrides = concatenation` in scope order,
each entry already name-unique under D-COMP-2. The composed dict has the same
`{zones, matrix, policy_overrides}` shape `zone_firewall.tf.j2` already
consumes; nothing downstream of composition needs to change shape.

**D-COMP-4, determinism.** Scopes are processed in the sorted order
`scopes_by_enforcer` already establishes, so the composed plan does not depend
on `normalized_rows` input order - the same guarantee V-13 established for the
index one level up, extended through composition rather than left to stop at
the index.

**Diagnostics.** `E7013` (zone_refs overlap between scopes sharing an
enforcer) and `E7014` (policy_override name collision across scopes sharing
an enforcer), both error/compile, in the same 7009-7019 sub-band; collision
check re-run and clean (`grep -rEon '[EWI]70(1[3-9])'`, excl. `build/`,
`.venv/` - only this record's own prose mentions the numbers).

**Implemented, separate commit.** D-COMP-1..4 are coded in
`security_matrix_compiler.py`, publishing a new `composed_matrices_by_enforcer`
channel (zero subscribers so far - the same safe, testable-in-isolation shape
V-13's channel had before anything read it). `E7013`/`E7014` fire on the
counterexamples in `TestComposedMatricesByEnforcer`: overlapping zones,
colliding override names, order-independence, two-enforcer independence, and a
single-scope positive control confirming composition of one scope is a no-op.
Real topology: `errors=0 warnings=2` (matches baseline), `generated/`
byte-unchanged, since the one enabled scope composes trivially with itself.

**Still open before V-09/V-10/V-14 can render anything.** The composed
channel has no reader yet. `_extract_security_matrix` in `projections.py`
still first-matches `security_matrices` directly, so the real generator output
is unaffected by this step - by design, matching how V-13 landed its channel
before anything consumed it. Wiring the MikroTik projection to read
`composed_matrices_by_enforcer` instead, and the two-scope fixture to prove
parity when it does, remain open.

## 6. What this record does not do

No gate advances. `W07`/`G4` are not closed by section 5: it repairs one published
channel and adds three diagnostics, and the layout migration, the consumer chain,
the capability axis and the apply-unit contract all remain open. The section 4
sequencing is a reading of existing obligations, not new acceptance IDs. The
namespace framing in section 4 is a proposal awaiting review, and no part of this
record authorizes a state migration, a device operation or a deployment.

## 7. Command evidence

Evidence for sections 1-3 (unchanged baseline, before `c5f66c10`):

```
pytest tests/test_backend_specialization_boundary.py -q     9 passed
grep -rEon '[EWI]70(09|1[0-9])' ... (excl. build/, .venv/)  no matches
grep -rn 'subscribe(.*matrix_by_enforcer'                   no matches
```

Evidence for section 5, at `c5f66c10`:

```
ad hoc counterexample script, mirroring 5.4 exactly     6/6 + positive control pass
pytest tests/plugin_integration/test_security_matrix_compiler.py -q      31 passed
pytest tests/plugin_contract/test_integration_tests_no_legacy_publish_registry.py -q
                                                                            1 passed
pytest tests/test_diagnostic_code_registry.py tests/test_plugin_registry.py -q
                                                                           17 passed
generate-framework-lock.py --force && verify-framework-lock.py --strict   OK
compile-topology.py (canonical invocation)                errors=0 warnings=2
                                              (matches the last recorded baseline)
git status after compile                          generated/ unchanged, byte-identical
```

Evidence for V-15, at `1336c12f`:

```
pytest tests/plugin_integration/test_projection_snapshots.py
      tests/plugin_integration/test_projection_helpers.py
      tests/plugin_integration/test_terraform_proxmox_generator.py
      tests/plugin_integration/test_generator_projection_contract.py
      tests/plugin_contract/test_object_generator_ownership.py
      tests/plugin_contract/test_projection_ownership_boundaries.py -q    49 passed
pytest tests/plugin_regression/test_terraform_proxmox_parity.py
      tests/plugin_integration/test_bootstrap_generators.py -q  13 passed, 1 skipped
pytest tests/test_diagnostic_code_registry.py
      tests/test_backend_specialization_boundary.py -q                   20 passed
generate-framework-lock.py --force && verify-framework-lock.py --strict   OK
compile-topology.py (canonical invocation)                errors=0 warnings=2
git status after compile                          generated/ unchanged, byte-identical
```

Evidence for section 5c (D-COMP-1..4), at `e72d0099`:

```
pytest tests/plugin_integration/test_security_matrix_compiler.py -q      36 passed
pytest tests/plugin_contract/test_integration_tests_no_legacy_publish_registry.py
      tests/test_diagnostic_code_registry.py tests/test_plugin_registry.py
      tests/test_backend_specialization_boundary.py -q                   27 passed
pytest tests/plugin_contract/test_manifest.py
      tests/plugin_contract/test_validate_plugin_manifests.py -q         40 passed
pytest tests/plugin_integration/test_mikrotik_capability_driven.py
      tests/plugin_integration/test_generator_projection_contract.py
      tests/plugin_integration/test_zone_derivation_parity_w05.py
      tests/plugin_regression/test_terraform_mikrotik_parity.py -q
                                                       34 passed, 1 skipped
generate-framework-lock.py --force && verify-framework-lock.py --strict   OK
compile-topology.py (canonical invocation)                errors=0 warnings=2
git status after compile                          generated/ unchanged, byte-identical
```

A full `pytest tests -q -p no:randomly` was run once on this tree, before
`c5f66c10`: 125 failed, all in `tests/plugin_integration/test_security_plan_validator.py`,
which passes 77/77 in isolation. That result was investigated rather than
accepted at face value. Bisection cleared every directory collected before the
target - `ai_rules`, `kernel`, `netmodel`, `orchestration`, `plugin_api`,
`plugin_contract` - both individually and combined, and cleared both halves of
the ~100 `plugin_integration` files collected before the target within that
directory. The decisive check was the exact natural collection order `pytest
tests` itself uses, reconstructed file-by-file and run as one invocation
through the target inclusive (291-file collection order captured once, first
201 files, exit code 0): **1981 passed, 1 skipped, 1 failed - and the failure
was not the target file.** `test_security_plan_validator.py` passed clean, all
77 of its tests, under the exact conditions that had produced 125 failures.
The one failure that did occur (`test_projection_matches_golden_snapshot
[proxmox-...]`) is explained: that pytest process started before `1336c12f`
landed the golden-snapshot update V-15 required, so it ran against
already-superseded source.

No reproducible order-dependent pollution was found. The original 125 failures
are best explained as a one-off condition specific to that one 52-minute,
2573-test run - resource exhaustion (disk, file descriptors) from the many
subprocess-heavy bootstrap/compile tests plugin_integration and plugin_contract
both carry is the leading candidate, given the failure did not survive an exact
structural reproduction. This is closed as an investigated, not reproduced,
anomaly - not as a fixed bug, since nothing was found to fix. A fresh full
`pytest tests` run remains the only way to see whether it recurs; it has not
been re-run in full since this tree's V-13/V-15 changes landed. No claim in
this record or in sections 5/5b depends on that outcome.

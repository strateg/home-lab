# W07 — where backend specialization lives

Status: contract decision for work item W07 / gate G4 of the ADR 0118/0119
implementation plan. Date: 2026-09-14. Baseline: commit `3312ca0b`.
The initial decision moved no code or topology/artifact/device state. Subsequent
implementation evidence is recorded in the migration order below.

## Why this document exists

The implementation plan leaves the decomposition open and fixes it here:

> Backend specialization may be an internal bounded core operation using declared
> backend semantics or a separate compiler plugin; that decomposition is fixed
> when W06/W07 contracts are written. **It cannot occur only in a generator after
> the relevant validator ran.**

The last sentence is a constraint, and it is currently violated. That is the
measurement this decision rests on, so it is stated first.

## Measurement: specialization happens entirely after validation

`object.mikrotik.generator.terraform` is registered at stage **generate**, order
220. It calls `build_mikrotik_projection`, which was 1,565 lines across 17
functions when this was measured, all of which make backend decisions. Step 2 of
the migration order below has since landed, leaving 15 functions and 1,518 lines;
the table records the measurement the decision was taken on:

| Function | Lines | Decides |
|---|---|---|
| `build_mikrotik_projection` | 276 | The whole projected view the templates render |
| `_extract_security_matrix` | 246 | Zone membership, address lists, matrix rules |
| `_extract_wireguard_tunnels` | 191 | Which tunnels this router terminates |
| `_extract_containers` | 191 | Container attachment and publication shape |
| `_extract_wifi_config` | 138 | Interface and VLAN membership |
| `_build_routing_policy_entry` | 110 | Policy-based routing, `*_vlan_ref` resolution |
| `_extract_mac_vlan_assignments` | 104 | MAC-to-VLAN binding |
| `_extract_bridge_vlans` | 99 | Bridge VLAN membership |
| `_derive_mikrotik_capability_flags` | 21 | Conditional generation from capability sets |

Every validator has finished before any of this runs. Nothing checks its output
except artifact parity, which compares it with itself from the previous run.

Two issues recorded at the original baseline (before the later W05 cutover):

* **W05.** The generator recomputes zone membership and reaches a different answer
  from the compiler, because both derive it and only one is checked.
* **`_derive_mikrotik_capability_flags`.** Capability classification is valid
  dispatch, not SEC-CAP proof. Any resulting realization/applicability decisions
  must be visible in the specialized plan before validation; template selection
  at generate cannot independently establish that a required property is supported.

## Decision

**Backend specialization is a compile-stage compiler plugin in the object module.**
Not an internal core operation, and not the generator.

Three reasons, in the order they decided it.

**Validation must be able to see the specialized plan.** The capability contract
says specialization *"evaluates declared offers and finite strategies, adding
their prerequisites"* and validation *"independently checks the complete
specialized plan and witness coverage"*. A validator cannot check what does not
exist yet. Anything produced at generate is unverifiable by construction, which is
the constraint the plan states.

**Backend semantics belong to the backend's module.** Putting RouterOS knowledge
into an internal core operation makes the core know about one product, which ADR
0063's microkernel boundary exists to prevent. The object module already owns the
templates and the capability declarations; the specialization belongs beside them.

**The seam already exists.** `base.compiler.security_plan` publishes a
backend-neutral plan at compile. A specialization plugin consuming that and
publishing `backend_plan` fits the existing channel contract with no new
mechanism, and `base.validator.security_plan` gains a specialized counterpart the
same way.

### Shape

```text
compile   base.compiler.security_plan       -> security_plan (all scopes)
compile   object.<module>.compiler.plan     -> backend_plan (scope/context projections,
                                              resolved adapter identity/version,
                                              owned resources and apply-unit mapping)
validate  base.validator.security_plan      -> checks common semantics
validate  object.<module>.validator.plan    -> checks specialized plan and composition
generate  object.<module>.generator.*       -> renders checked projections,
                                              artifacts grouped by declared apply unit
```

`<module>` identifies plugin placement, not the type authority or a dispatch rule.
These are schematic roles, not permission to select a publisher dynamically or
bypass declared `depends_on`, `consumes` and `produces`. One module may host several
adapter contracts. Enforcer type comes from topology classification; the compatible
versioned adapter is resolved and pinned before validation under ADR 0119 D1.1.

The seam retains scope identity and target enforcer; one enforcer may own several
scopes. The artifact grouping is by the declared apply unit, which may cover
several scopes under the validated coupling/ownership contract. Neither type,
module nor directory name substitutes for these identities.

The generator's remaining job is rendering. ADR 0119 D4 already says this for the
terminal deny — the plan compiler emits it and the template only renders it.
No adapter negotiation or semantic rediscovery is deferred to generate.

### The layout, and the reason it is not the one first given

The proposed layout is unchanged:

```
<artifacts root>/terraform/<backend>/<enforcer instance id>/
```

So `terraform/mikrotik/rtr-mikrotik-chateau/` and `terraform/proxmox/srv-gamayun/`.
The first segment stays the existing directory name; it is a path, not the type
authority - dispatch is by resolved adapter, and letting a directory name decide
would reintroduce exactly what the amendment removes. The layout follows
`bootstrap/<device>/`, which already renders per device here.

**The justification given on 2026-09-15 was wrong and is withdrawn.** It said a
root per instance follows because "a Terraform root holds one unaliased provider
configuration and one state". The first half describes the file this repository
happens to emit, not a property of Terraform: several configurations of one
provider are supported through
[`alias`](https://developer.hashicorp.com/terraform/language/block/provider#alias),
so one root can address several RouterOS devices. Deriving an architectural rule
from the shape of current output is the same mistake as deriving enforcer types
from which module owns a generator.

The selected layout binds each root execution to an explicit state namespace,
locking policy, resource inventory and apply unit. It is intended to reduce
cross-enforcer state/apply coupling; a directory or root alone does not establish
that boundary. In particular it does not prove atomic apply, unique resource
ownership or isolation of failures on shared paths.

For the RouterOS and Proxmox choices below, implementation must demonstrate:

* every managed resource has one writer and an unambiguous target;
* separate roots do not accidentally share a state namespace or manage the same
  resource; any intentional sharing has a declared reconciliation contract;
* all scopes sharing chains, hooks, address sets or other resources are composed
  before rendering, even if their artifacts are stored separately;
* partial apply and recovery obey the approved transition envelope, including
  effects on other scopes. Root separation is not SEC-TRANSITION evidence;
* connection bindings explicitly select targets. Endpoints and credential
  references need not be unique across roots.

An aliased single root is a valid alternative. For this bounded implementation it
is not selected because it would group several enforcers into the same declared
state/apply unit. This is a layout choice, not a prohibition in ADR 0119 and not
a limitation of Terraform. Its benefits depend on proving the boundaries above.

### Selected target layout per adapter (not implemented)

Per-scope attribution, unambiguous targets and single-writer resource ownership
are the obligations. This table selects per-enforcer roots for two adapters; it
does not equate enforcer, scope and apply unit in the universal model.

| Adapter | Selected layout | Why |
|---|---|---|
| RouterOS via `terraform-routeros/routeros` | one root per enforcer instance | provider is configured per device; state boundary per enforcer |
| Proxmox VE via `bpg/proxmox` | one root per enforcer instance, scopes carried inside it | `proxmox_virtual_environment_firewall_rules` scopes itself with `node_name`, `vm_id` and `container_id`, so one node's several scopes render as explicit arguments in that node's root |
| Oracle Cloud via `oci` | unchanged | a tenancy is not an enforcer; the rule does not reach it. If OCI is later modelled as carrying one, it is decided then |

The previous version gave Proxmox a per-instance root in one paragraph and a
shared-root exception in the next. The table is the selected implementation layout;
ADR 0119 still permits other declared, validated apply-unit arrangements.

### What a move requires, beyond renaming

**This requires a separately reviewed behaviour change; path parity is only one part.**
Moving the roots changes 24 of the 163 emitted paths, and byte content may be
identical while byte parity still fails, because the comparison is by path. A
declared rename handles that much. It does not handle the rest, and the rest is
where the risk is:

* an old-to-new inventory of every resource address, state entry, provider
  configuration and consumer, with no address owned twice across the transition;
* a reviewed state migration - `terraform state mv` or equivalent - against the
  **existing** state, not against a fresh plan;
* evidence that nothing is destroyed and recreated unintentionally: a plan against
  migrated state showing no replacements for resources that did not change;
* every consumer of the moved paths switched together, per the migration plan.

Recording this is design preparation. It is not authorization to migrate state.

## What this decision does not do

The decision itself changes no runtime. Its original measurement at `3312ca0b`
was 17 functions / 1,565 lines. Step 2 landed in `ed15dfbf`; the current recorded
projection is 15 functions / 1,518 lines. Historical W05 derivation findings do not
mean its removed fallback still runs. Remaining per-scope extraction/index defects
are listed in [the conformance record](ENFORCER-AXIS-CONFORMANCE.md).

Migration remains bounded and evidence-driven: legacy parity for unchanged
behaviour, explicit review for semantic changes and artifact/state relocation.
Neither the completed helper removal nor this amendment closes W07/G4.

## Migration order

Derived from what is checkable, not from what is easy.

1. `_derive_mikrotik_capability_flags` - smallest, and the one whose current
   placement contradicts the capability contract most directly.
   **Done 2026-09-29.** Moved verbatim, along with `_extract_capabilities`, to
   `object.mikrotik.compiler.capability_flags` - the first compile-stage
   compiler plugin an object module has registered, establishing the `object.
   <module>.compiler.plan -> backend_plan` seam this document's Shape section
   already specified. The projection now takes `capability_flags` as a
   required argument (the same "required, refuse `None`" contract
   `composed_matrices_by_enforcer`/`vlan_cidr_map` already use) instead of
   deriving it at generate stage. Real-topology parity: `generated/`
   byte-identical (`git status` after a clean recompile shows no diff);
   `errors=0 warnings=3`, matching the pre-existing baseline (the third
   warning, `W7016` for `rtr-slate`, predates this change).
2. `_build_vlan_cidr_index` and `_resolve_vlan_refs_to_cidrs` - pure reference
   resolution the compiler already performs; a duplicate authority to remove.
   **Done 2026-09-15** (`ed15dfbf`). Both are gone, along with `_row_class` and the zone
   oracle that used them. The projection reads `vlan_cidr_map` and
   `security_matrices` from `base.compiler.security_matrix` and derives no
   substitute for either: both consumes are `required: true`, so a missing
   channel blocks generation (E8003) instead of rendering empty address lists and
   empty tunnel routes under a SUCCESS status. The parity oracle moved to
   `tests/plugin_integration/test_zone_derivation_parity_w05.py`, where it is
   re-derived independently and checked against the rendered artifact - a second
   implementation belongs to the test that runs it, not to the code path a
   generator can still fall back into. Artifacts: 163 files compared against a
   clean worktree at `e8bc55e4` with symmetric output history, identical outside
   the declared W13 exclusion. The projection is 15 functions and 1,518 lines;
   `tests/test_backend_specialization_boundary.py` lowers the budget to match and
   asserts the three helpers are absent rather than merely small.
3. `_extract_security_matrix` - preserve the W05 parity baseline, but first fix
   the complete deterministic enforcer-to-scope contract and its counterexamples
   (V-09/V-13). Do not subscribe a consumer to the current lossy index. Removing
   the first-match return alone does not establish correct multi-scope rendering.
   **Done 2026-09-29.** The enforcer-to-scope contract was fixed first, in order:
   `scopes_by_enforcer` (complete, deterministic) replaced the lossy
   `matrix_by_enforcer` index; `composed_matrices_by_enforcer` composes every
   scope one enforcer holds under an explicit conflict contract (D-COMP-1..4,
   `E7013`/`E7014`) rather than first-matching one. Only then did
   `_extract_security_matrix` move: it no longer re-derives R1-R6 from raw
   `network_rows` - a third derivation of the same fact the W05 baseline never
   named, found by reading the function in full before migrating it (N-07) - it
   reads the compiler's already-composed plan and resolves only
   `src_vlan_ref`/`dst_vlan_ref` addressing, which the compiler does not own.
   Real-topology parity: `generated/` byte-identical (`git status` after a clean
   recompile shows no diff under `generated/`); `errors=0 warnings=2`, matching
   the baseline. The function is 94 lines, down from 209;
   `tests/test_backend_specialization_boundary.py`'s line budget is lowered to
   match, and the manifest's `security_matrices` consume is replaced by
   `composed_matrices_by_enforcer` (the projection derives no substitute for
   either).
4. Everything else, in descending size, each with parity evidence. Made
   concrete on 2026-09-29 against the post-item-3 measurement (13 functions,
   1,361 lines; `_derive_mikrotik_capability_flags`, `_extract_capabilities`,
   `_build_vlan_cidr_index`, `_resolve_vlan_refs_to_cidrs` and `_row_class` are
   already gone, so this list is what remains):

   | Order | Function | Lines | Decides |
   |---|---|---|---|
   | 4a | `_extract_wireguard_tunnels` | 196 | Which tunnels this router terminates |
   | 4b | `_extract_containers` | 191 | Container attachment and publication shape |
   | 4c | `_extract_wifi_config` | 138 | Interface and VLAN membership |
   | 4d | `_build_routing_policy_entry` | 110 | Policy-based routing, `*_vlan_ref` resolution |
   | 4e | `_extract_mac_vlan_assignments` | 104 | MAC-to-VLAN binding |
   | 4f | `_extract_bridge_vlans` | 99 | Bridge VLAN membership |
   | 4g | `_build_vlan_entry` | 41 | VLAN row -> rendered shape |
   | 4h | `_build_bridge_entry` | 21 | Bridge row -> rendered shape |
   | 4i | `_build_firewall_entry` | 16 | Firewall-policy row -> rendered shape |

   `_get_object_properties` (20 lines) and `_is_staged_row` (3 lines) are not
   listed: neither makes a backend decision - the first is a compiled-object
   property lookup, the second a status/notes predicate - so migrating them
   independently would not pay down the debt this table measures; they move
   with whichever caller needs them, if any survives the migration.

   `build_mikrotik_projection` itself (329 lines) is deliberately last and
   unordered here: it is the orchestrator that calls every function above, so
   its own size is a consequence of theirs, not an independent candidate. As
   4a-4i land it should shrink toward assembly and rendering-input shaping;
   whatever remains once none of 4a-4i are called from it is the actual
   scope of a final step, not assumed now.

   **4a done 2026-09-29.** `_extract_wireguard_tunnels` moved verbatim to
   `object.mikrotik.compiler.wireguard_tunnels`, the second compile-stage
   compiler plugin an object module has registered (after item 1's
   `capability_flags`). It consumes `effective_model_candidate` (for router
   ids and network rows) and `base.compiler.security_matrix`'s
   `vlan_cidr_map`. The projection now takes `wireguard_tunnels` as a
   required argument, the same "required, refuse `None`" contract the other
   three channels already use. Characterization found no divergence to fix
   first, unlike items the W05/N-07 pattern warned about: the function reads
   only topology instance data (`endpoint_a`/`endpoint_b`/`tunnel_name`) plus
   the already-compiler-sourced `vlan_cidr_index`, never re-deriving a fact
   the compiler itself publishes. Real-topology parity: `generated/`
   byte-identical (`git status` shows no diff); `errors=0 warnings=3`,
   unchanged from the pre-existing baseline. Confirms the choice named in
   (ii) below: a second, dedicated plugin per specialization, not one plugin
   accreting every concern.

   **4b done 2026-09-29.** `_extract_containers` moved verbatim to
   `object.mikrotik.compiler.containers`, the third dedicated compile-stage
   compiler plugin. It consumes only `effective_model_candidate` (router ids
   and `routeros_container`-group rows) - no `base.compiler.security_matrix`
   dependency, since container derivation touches no zone/CIDR fact. The
   projection now takes `containers` as a required argument. Characterization
   found no divergence to fix first, the same as item 4a: the function reads
   only topology instance data, no compiler-owned fact re-derived.
   Migrating it surfaced a real hazard the characterization step exists to
   catch: the projection already had an unrelated local variable also named
   `containers` (observed-runtime bridge-interface config, a completely
   different meaning), which would have silently shadowed the new parameter
   for the rest of the function and corrupted the rendered output - found by
   grepping the full function body for the parameter name before finalizing
   the change, not discovered by a test. Renamed to `observed_containers`.
   Real-topology parity: `generated/` byte-identical; `errors=0 warnings=3`,
   unchanged; the real topology's 6 containers derived correctly with the
   rename in place, confirming the fix.

   **4c done 2026-09-29.** `_extract_wifi_config` moved verbatim to
   `object.mikrotik.compiler.wifi_config`, the fourth dedicated compile-stage
   compiler plugin. It consumes only `effective_model_candidate` (router
   rows) - no dependency on `base.compiler.security_matrix`, same as item
   4b. `_extract_bridge_vlans` (item 4f, still in the projection) takes this
   function's output as an argument; the projection now threads the
   `wifi_config` parameter into it locally instead of calling the removed
   function, so 4f's migration will need `wifi_config` in scope when its
   turn comes. Characterization found no divergence and no naming collision
   this time (checked directly, given 4b's finding, by grepping the whole
   function body for every generic-sounding name - `interfaces`,
   `datapaths`, `configurations`, `securities` - before assuming it was
   safe). It did surface a test-infrastructure gap instead of a production
   one: `tests/plugin_integration/test_projection_helpers.py`'s
   `build_mikrotik_projection` wrapper always defaulted the new required
   channels to empty, which silently broke
   `test_mikrotik_projection_extracts_wifi_interfaces` - a test that builds
   real WiFi `instance_data` and expects it derived, not discarded. Fixed by
   making the wrapper auto-derive all four channels from the fixture's own
   rows, the same way `test_mikrotik_capability_driven.py`'s wrapper already
   did, rather than hard-defaulting empty. Real-topology parity: `generated/`
   byte-identical; `errors=0 warnings=3`, unchanged; the real topology's 5
   WiFi interface bindings derived correctly.

   **4d done 2026-09-29.** `_build_routing_policy_entry` moved verbatim to
   `object.mikrotik.compiler.routing_policies`, the fifth dedicated
   compile-stage compiler plugin. Unlike items 4a-4c, the source function was
   a per-row builder called from inside a larger shared loop (over `network`
   rows) that also builds vlans and bridges in the same iteration - not an
   independent top-level extractor. Migrating it required replicating the
   loop's row-selection and `managed_by_ref`-resolution logic for
   `routing_policy` rows specifically (checked against the original by
   reading the surrounding loop in full, not just the builder function),
   while leaving the vlan/bridge branches of that same loop untouched in the
   projection. The plugin consumes `effective_model_candidate` (router ids,
   network rows) and `base.compiler.security_matrix`'s `vlan_cidr_map`, same
   as item 4a. Characterization found no divergence and, checked given 4b's
   and 4c's findings, no naming collision. Real-topology parity: `generated/`
   byte-identical; `errors=0 warnings=3`, unchanged; the real topology's 5
   routing policies derived correctly.

   Each of 4e-4i needs the same three-part evidence 1-3 above recorded, sized
   to what the function actually risks: (i) a characterization step - does the
   projection already diverge from any compiler-published fact for this data,
   the way W05 did for zones and N-07 did for R1-R6 - checked by reading the
   function in full, not assumed absent because no defect is currently named;
   (ii) the compile-stage channel it moves to, and the object-module plugin
   that owns it - items 1, 4a, 4b, 4c and 4d each got their own dedicated
   plugin rather than accreting into one, which later items should default
   to unless a specific reason favors sharing, and a later item may need to
   thread an earlier item's channel into whatever of its own logic still
   lives in the projection, the way 4c's `wifi_config` now threads into
   4f's still-local `_extract_bridge_vlans`. 4d additionally found that the
   source function is not always an independent top-level extractor: a
   per-row builder called from inside a larger shared loop needs the loop's
   own row-selection/defaulting logic replicated for the rows it cares
   about, checked against the surrounding loop in full, not only the
   builder; and (i) is not a formality - 4b's characterization caught a
   naming collision that would have silently corrupted rendered output if
   migrated without reading the whole function first, and 4c's caught that
   the test suite, not only the projection, can silently default a required
   channel empty and discard real fixture content;
   (iii) real-topology parity (`generated/` byte-identical, matching or lower
   `errors=`/`warnings=`) plus updated `test_backend_specialization_boundary.py`
   budgets and migration-list entries, the same pattern items 1-3 established.

## What would falsify this decision

If a specialization turns out to need information that only exists after
generation - a rendered artifact's own content, for instance - then the seam is in
the wrong place and this document is wrong rather than the code. No such case is
known; recording the falsifier is the point.

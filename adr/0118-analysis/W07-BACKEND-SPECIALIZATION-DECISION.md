# W07 — where backend specialization lives

Status: contract decision for work item W07 / gate G4 of the ADR 0118/0119
implementation plan. Date: 2026-09-14. Baseline: commit `3312ca0b`.
No code was moved. No topology, artifact or device state changed.

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

Two consequences already observed rather than predicted:

* **W05.** The generator recomputes zone membership and reaches a different answer
  from the compiler, because both derive it and only one is checked.
* **`_derive_mikrotik_capability_flags`.** Conditional generation from capability
  set membership is the flag-as-proof the capability contract rules out, and it
  is unreachable by the SEC-CAP resolution because it happens two stages later.

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

```
compile   base.compiler.security_plan     -> security_plan   (backend-neutral, all scopes)
compile   object.<type>.compiler.plan     -> backend_plan    (specialized, per enforcer)
validate  base.validator.security_plan    -> checks security_plan
validate  object.<type>.validator.plan    -> checks backend_plan
generate  object.<type>.generator.*       -> renders backend_plan, decides nothing,
                                             one artifact set per enforcer instance
```

The generator's remaining job is rendering. ADR 0119 D4 already says this for the
terminal deny - *the plan compiler emits it and the template only renders it* -
and the same rule applies to everything else the projection currently decides.

**Amended 2026-09-15: `<type>`, not `<backend>`.** The first version of this shape
was parameterised by backend, and used "backend" and "object module" as synonyms.
That reads the model off the code: it makes the set of enforcer types equal to the
set of modules that happen to own a generator, which is the assumption
[ADR 0119 D1.1](../0119-firewall-rule-ordering-contract.md) now forbids. The
parameter is the enforcer type, resolved from the device's declared enforcement
capability. A module may host more than one type, and a type is not created by
adding a module.

The shape is also parameterised a second time, by **apply unit**, which the first
version did not express at all and the version after that got wrong.

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

The real justification is the second half, stated properly. A Terraform root is a
**state and transaction boundary**: one state file, one plan, one apply, one
locking domain, one blast radius on failure. Choosing a root per enforcer instance
therefore buys, and only buys, these:

* every resource in the root has one writer, and that writer's scope attribution is
  structural rather than conventional;
* a failed or partial apply is bounded to one enforcer, which matters because a
  partially applied firewall is the transition case SEC-TRANSITION exists for;
* state can be moved, locked, restored or quarantined per enforcer;
* credentials and endpoints are chosen per root, without that being *required* -
  ADR 0119 D1.1 requires unambiguous target selection and a single writer, not
  unique endpoints, and several roots may legitimately point at one management
  endpoint.

An aliased single root is the alternative, and it is not absurd: it keeps paths
stable and renders every enforcer in one plan. It is rejected here because it puts
every enforcer in one state and one apply, which is the coupling the third and
fourth bullets exist to avoid - not because Terraform cannot express it.

### Which layout each adapter actually uses

Per-instance **separation** is the obligation; a root per instance is one way to
meet it, and it is not the only one.

| Adapter | Selected layout | Why |
|---|---|---|
| RouterOS via `terraform-routeros/routeros` | one root per enforcer instance | provider is configured per device; state boundary per enforcer |
| Proxmox VE via `bpg/proxmox` | one root per enforcer instance, scopes carried inside it | `proxmox_virtual_environment_firewall_rules` scopes itself with `node_name`, `vm_id` and `container_id`, so one node's several scopes render as explicit arguments in that node's root |
| Oracle Cloud via `oci` | unchanged | a tenancy is not an enforcer; the rule does not reach it. If OCI is later modelled as carrying one, it is decided then |

That is one rule with one exception stated as a table entry rather than as prose
contradicting itself: the previous version gave Proxmox a per-instance root in one
paragraph and made it a shared-root exception in the next.

### What a move requires, beyond renaming

**This is a reviewed behaviour change, and path parity is the smallest part of it.**
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

It moves no code. The projection is 1,565 lines whose output is currently pinned
only by artifact parity, and moving it in one step would replace a measured
baseline with an unmeasured one. The migration is per function, each with parity
evidence, and W05 shows why: the first function anyone tries to move is
`_extract_security_matrix`, and it **diverges from the compiler today**, so moving
it is a behaviour change requiring review rather than a refactor.

## Migration order

Derived from what is checkable, not from what is easy.

1. `_derive_mikrotik_capability_flags` - smallest, and the one whose current
   placement contradicts the capability contract most directly.
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
3. `_extract_security_matrix` - blocked on the W05 divergence, which must be
   resolved as its own reviewed change first.
4. Everything else, in descending size, each with parity evidence.

## What would falsify this decision

If a specialization turns out to need information that only exists after
generation - a rendered artifact's own content, for instance - then the seam is in
the wrong place and this document is wrong rather than the code. No such case is
known; recording the falsifier is the point.

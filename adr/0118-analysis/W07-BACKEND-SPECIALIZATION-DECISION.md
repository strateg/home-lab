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
compile   base.compiler.security_plan        -> security_plan     (backend-neutral)
compile   object.<backend>.compiler.plan     -> backend_plan      (specialized)
validate  base.validator.security_plan       -> checks security_plan
validate  object.<backend>.validator.plan    -> checks backend_plan
generate  object.<backend>.generator.*       -> renders backend_plan, decides nothing
```

The generator's remaining job is rendering. ADR 0119 D4 already says this for the
terminal deny - *the plan compiler emits it and the template only renders it* -
and the same rule applies to everything else the projection currently decides.

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

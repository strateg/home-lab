# ADR 0086 — Reference Validator Rule Catalog (Wave 2 / W2-01)

## Purpose

This catalog maps current `*_refs_validator.py` behavior to a declarative rule model.
It is the source input for implementing `DeclarativeReferenceValidator` in Wave 2.

## Shared runtime preconditions

All reference validators in this catalog share these preconditions:

- Subscribe source: `base.compiler.instance_rows.normalized_rows`
- Build row index: `row_by_id[instance]`
- Validate typed refs against:
  - class constraints,
  - layer constraints,
  - shape constraints (string/list/object)
- Emit diagnostics with stable code/severity/path contracts.

---

## Rule Family A — Direct typed reference checks

These validators follow the same structural pattern and are first-priority for
full declarative consolidation.

| Source plugin | Primary code(s) | Rule targets |
|---|---|---|
| `dns_refs_validator.py` | `E7856` | `records[*].device_ref -> L1`, `lxc_ref -> class.compute.workload.container`, `service_ref -> class.service.*` |
| `certificate_refs_validator.py` | `E7857` | `service_ref` and `used_by[*].service_ref` -> class prefix `class.service.` |
| `backup_refs_validator.py` | `E7858` | `destination_ref -> class.storage.pool`, `targets[*].device_ref/lxc_ref/data_asset_ref` |
| `service_dependency_refs_validator.py` | `E7849`, `E7850` | `data_asset_refs[*] -> class.storage.data_asset`, `dependencies[*].service_ref -> class.service.*` |
| `network_core_refs_validator.py` | `E7833`..`E7836` | VLAN/bridge core refs: `bridge_ref`, `trust_zone_ref`, `managed_by_ref`, `host_ref` |
| `power_source_refs_validator.py` | `E7801`..`E7805` | `extensions.power.source_ref`, optional `outlet_ref`, plus cycle/occupancy constraints |

### Declarative model mapping (A-family)

Use a common `ReferenceRule` shape:

```python
ReferenceRule(
    name="dns_device_ref",
    applies_when=ClassIs("class.service.dns") | GroupIn({"dns", "dns_zones"}),
    field="extensions.records[].device_ref",
    expected=LayerIs("L1"),
    code="E7856",
    severity="error",
)
```

For list/object paths, support selectors:
- `[]` for list iteration,
- nested object path resolution,
- optional/nullable field policy.

---

## Rule Family B — Storage chain (medium complexity)

| Source plugin | Primary code(s) | Notes |
|---|---|---|
| `storage_l3_refs_validator.py` | `E7830`..`E7832`, `E7860`..`E7869`, `W7866`..`W7869` | Multi-entity chain + infer logic + warning/error blend |

### Consolidation strategy

- **Phase B1 (declarative core):** move plain typed refs and list refs.
- **Phase B2 (semantic rules):** keep procedural handlers for infer/policy coupling,
  then gradually convert to declarative predicates once stable.

---

## Rule Family C — Compute workload refs (high complexity)

| Source plugin | Primary code(s) | Notes |
|---|---|---|
| `lxc_refs_validator.py` | `E7880`..`E7888`, `W7888` | Typed refs + capability checks + architecture compatibility + legacy deprecation checks |
| `vm_refs_validator.py` | `E7870`..`E7877`, `W7877` | Similar to LXC with VM-specific storage/runtime assumptions |
| `host_os_refs_validator.py` | `E7890`..`E7896`, `E7892`..`E7895` | Host inventory contracts, architecture normalization, installation requirements |

### Consolidation strategy

- Keep these plugins procedural in early Wave 2.
- Extract reusable primitives first:
  - `validate_ref_string()`
  - `validate_target_class_layer()`
  - `normalize_arch()`
  - `active_os_binding()`
- Consolidate into declarative form only after parity harness covers edge cases.

---

## Rule Family D — Service runtime refs (high complexity)

| Source plugin | Primary code(s) | Notes |
|---|---|---|
| `service_runtime_refs_validator.py` | `E7841`, `W7842`, `W7845` | Runtime type matrix, legacy field deprecation, host capability checks |

### Consolidation strategy

- Split validator internally into sections:
  1. typed runtime ref checks,
  2. legacy compatibility warnings,
  3. device runtime capability checks.
- Only section (1) is immediate declarative candidate.

---

## Declarative engine requirements (minimum)

To represent A-family rules safely, engine must support:

1. `applies_when` selector by `class_ref`/`group`.
2. Field path extraction with list traversal.
3. Target predicate composition:
   - class equals/prefix,
   - layer equals,
   - existence in `row_by_id`.
4. Type/shape policies:
   - `string_non_empty`,
   - `list_of_objects`,
   - `list_of_strings`.
5. Stable path rendering for diagnostics.
6. Deterministic rule order.

---

## Proposed Wave 2 execution split

### Immediate (W2 baseline)

- Consolidate fully (A-family):
  - DNS, certificate, backup, service dependency, network core, power source.

### Deferred in Wave 2 (procedural keep, helper extraction)

- Storage L3 semantic infer rules,
- LXC/VM/Host OS architecture/capability contracts,
- Service runtime capability/deprecation matrix.

---

## Diagnostic parity matrix seed

Use this matrix as test design baseline for `test_declarative_reference_validator_parity.py`:

| Rule bucket | Must preserve |
|---|---|
| Missing subscribe payload | same error code and `pipeline:validate` path style |
| Invalid scalar ref type | same error code and field path |
| Unknown target id | same error code and field path |
| Wrong class/layer target | same error code and field path |
| Invalid list item type | same error code and indexed path |

---

## Notes

- This catalog is intentionally split by complexity to avoid risky big-bang rewrites.
- Wave 2 implementation should start with A-family declarative migration and parity gates.

# ADR 0083: Plugin Boundary Analysis (C/O/I Levels)

## Purpose

Prove that all plugins introduced by ADR 0083 respect the 4-level plugin boundary model:
**Global → Class → Object → Instance**. No level may reference identifiers from a lower level.

---

## Plugin Inventory

| Plugin ID | Level | Stage | Phase | Order |
|-----------|-------|-------|-------|-------|
| `base.validator.initialization_contract` | Global | validate | post | 180 |
| `base.generator.initialization_manifest` | Global | generate | post | 395 |
| `base.assembler.bootstrap_secrets` | Global | assemble | run | 420 |
| `object.mikrotik.generator.bootstrap` | Object | generate | run | 320 |
| `object.proxmox.generator.bootstrap` | Object | generate | run | 310 |
| `object.orangepi.generator.bootstrap` | Object | generate | run | 320 |

---

## Level Boundary Analysis

### 1. `base.validator.initialization_contract` (Global Level)

**Claim:** This validator operates at global level and does NOT reference object-specific or instance-specific identifiers.

**Evidence:**

- **Input:** Reads `compiled_json` containing all object modules.
- **Logic:** Iterates over objects that have `class_ref` matching `class.compute.*` or `class.router`, checks for presence and schema compliance of `initialization_contract`.
- **Schema reference:** Uses `schemas/initialization-contract.schema.json` — a generic schema, not object-specific.
- **Output:** Diagnostics with `E97xx` codes.

**Boundary check:**

| Rule | Status | Notes |
|------|--------|-------|
| Must NOT reference `obj.*` identifiers | ✅ PASS | Iterates generically over all objects with compute/router class_ref |
| Must NOT reference `inst.*` identifiers | ✅ PASS | Does not access instance data |
| May call interfaces from own level or higher | ✅ PASS | Uses only `ctx.compiled_json` (global context) |

**Verdict:** ✅ Valid global-level plugin.

### 2. `base.generator.initialization_manifest` (Global Level)

**Claim:** This generator aggregates data from all object modules into a single manifest. It operates at global level.

**Evidence:**

- **Input:** Reads `compiled_json` to find all objects with `initialization_contract`. Resolves per-instance data from compiled model.
- **Logic:** For each object with a contract, iterates instances and builds manifest entries. Uses generic field access (`obj.initialization_contract.mechanism`, etc.).
- **Output:** `generated/<project>/bootstrap/INITIALIZATION-MANIFEST.yaml`.
- **Data bus:** Publishes `initialization_manifest_path` and `initialization_manifest_data` as `pipeline_shared`.

**Boundary check:**

| Rule | Status | Notes |
|------|--------|-------|
| Must NOT reference `obj.*` identifiers | ⚠️ REVIEW | Accesses `obj.initialization_contract` but via generic iteration, not hardcoded object IDs |
| Must NOT reference `inst.*` identifiers | ⚠️ REVIEW | Accesses instance IDs for manifest entries but via generic iteration |
| May call interfaces from own level or higher | ✅ PASS | Uses only `ctx.compiled_json` and `ctx.publish()` |

**Analysis of ⚠️ items:**

The plugin accesses `obj.*` and `inst.*` **data** through generic compiled model traversal, not through hardcoded references to specific objects or instances. This is the same pattern used by `base.generator.ansible_inventory` and `base.generator.effective_json`, which are accepted global-level plugins.

**Key distinction:** Referencing `obj.*` **identifiers** (hardcoded strings like `obj.mikrotik.chateau_lte7_ax`) violates boundaries. Iterating over all objects generically (`for obj in compiled_objects if obj.has('initialization_contract')`) does NOT violate boundaries.

**Verdict:** ✅ Valid global-level plugin. No hardcoded object/instance identifiers.

### 3. `base.assembler.bootstrap_secrets` (Global Level)

**Claim:** This assembler renders secret-bearing artifacts for all nodes generically.

**Evidence:**

- **Input:** Consumes `initialization_manifest_data` from manifest generator. Reads SOPS-encrypted secrets from `projects/<project>/secrets/`.
- **Logic:** For each node in manifest, combines generated secret-free template with decrypted secrets into `.work/native/bootstrap/<instance_id>/`.
- **Output:** Secret-bearing bootstrap artifacts in `.work/native/`.

**Boundary check:**

| Rule | Status | Notes |
|------|--------|-------|
| Must NOT reference `obj.*` identifiers | ✅ PASS | Iterates manifest nodes generically |
| Must NOT reference `inst.*` identifiers | ✅ PASS | Uses instance IDs from manifest data, not hardcoded |
| May call interfaces from own level or higher | ✅ PASS | Uses `ctx.subscribe()` and file I/O |

**Verdict:** ✅ Valid global-level plugin.

### 4. `object.mikrotik.generator.bootstrap` (Object Level)

**Claim:** This generator is object-level and accesses only object-level and higher data.

**Evidence (from existing `plugins.yaml`):**

- **Input:** Reads compiled model for MikroTik objects. Uses projection `build_mikrotik_projection()`.
- **Logic:** Renders bootstrap templates with MikroTik-specific context.
- **Output:** `generated/<project>/bootstrap/<instance_id>/init-terraform.rsc`.
- **Template paths:** Relative to `topology/object-modules/mikrotik/templates/`.

**Boundary check:**

| Rule | Status | Notes |
|------|--------|-------|
| Object-level plugin may reference `obj.*` | ✅ PASS | References own object module data |
| Must NOT reference `inst.*` directly | ⚠️ REVIEW | Iterates instances of own object for per-instance rendering |
| May call interfaces from own level or higher | ✅ PASS | Uses projections and global context |

**Analysis of ⚠️ item:**

Object-level generators produce per-instance artifacts as part of normal operation. The key rule is that the generator reads instance **data** through the compiled model (which is assembled by the compiler from class → object → instance inheritance), not by directly importing or referencing instance module files or instance-specific plugin logic.

**Existing precedent:** `object.mikrotik.generator.terraform` and `object.proxmox.generator.terraform` already iterate instances of their object to produce per-instance Terraform files. This is the accepted pattern per ADR 0078.

**Verdict:** ✅ Valid object-level plugin.

### 5. `object.proxmox.generator.bootstrap` (Object Level)

Same analysis as MikroTik above. Existing plugin at order 310.

**Current concern:** The existing plugin config contains 6 `post_install_scripts` entries (storage, network, git, zswap) that are **day-1 configuration**, violating the D7 bootstrap boundary rule. ADR 0083 Phase 3 must refactor these to day-1 Terraform/Ansible tasks.

**Boundary verdict:** ✅ Valid object-level plugin (structure). ⚠️ Content violates day-0/day-1 boundary (requires refactoring per D7).

### 6. `object.orangepi.generator.bootstrap` (Object Level)

Not yet implemented. Will follow the same pattern as MikroTik and Proxmox.

**Verdict:** ✅ Will be valid object-level plugin when implemented.

---

## Cross-Cutting Concerns

### Initialization Contract Field Ownership

The `initialization_contract` field is declared on the **object module**. This is correct because:

1. **Class level** defines capability taxonomy (e.g., `class.router` says "routers exist").
2. **Object level** defines how specific device types are bootstrapped (e.g., MikroTik uses netinstall).
3. **Instance level** provides deployment-specific values (IP, hostname, secrets refs).

The field MUST NOT be placed at class level (too generic) or instance level (would duplicate contract across instances of the same object).

### Data Flow Direction

```
Class (defines capabilities)
  ↓
Object (declares initialization_contract with templates)
  ↓
Instance (provides instance-specific values: IP, hostname)
  ↓
Global generator (aggregates all into INITIALIZATION-MANIFEST.yaml)
  ↓
Global assembler (injects secrets into .work/native/)
```

This flow respects the class → object → instance → global aggregation pattern used throughout the v5 architecture.

---

## Summary

| Plugin | Level | Boundary Valid | Notes |
|--------|-------|---------------|-------|
| `base.validator.initialization_contract` | Global | ✅ | Generic schema validation |
| `base.generator.initialization_manifest` | Global | ✅ | Generic aggregation, no hardcoded IDs |
| `base.assembler.bootstrap_secrets` | Global | ✅ | Consumes manifest data generically |
| `object.mikrotik.generator.bootstrap` | Object | ✅ | Existing pattern, ADR 0078 compliant |
| `object.proxmox.generator.bootstrap` | Object | ✅ / ⚠️ | Structure OK; content needs D7 refactoring |
| `object.orangepi.generator.bootstrap` | Object | ✅ | Future implementation |

**Conclusion:** All proposed plugins respect the 4-level boundary model. No class-level plugin references object data; no object-level plugin references instance-specific logic. Global plugins iterate generically without hardcoded identifiers.

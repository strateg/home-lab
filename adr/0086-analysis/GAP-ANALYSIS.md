# ADR 0086 — Current State vs Target State Gap Analysis

## Scope Clarification

This gap analysis follows the revised ADR 0086 scope:

- Keep runtime/schema contracts unchanged in this ADR.
- Preserve discovery chain and project extensibility.
- Focus on validator consolidation, standalone plugin layout simplification,
  and ID policy normalization.
- Defer new runtime protocol work (host/strategy contribution fields) to a separate ADR.

---

## AS-IS Snapshot

### Runtime and Contracts

1. `PluginContext` exposes broad shared data (`raw_yaml`, `compiled_json`, `classes`, `objects`),
   so level-isolation is not runtime-enforced.
2. `PluginRegistry` enforces stage/phase/dependency contracts, not level ACLs.
3. Manifest schema does not support additional contribution fields beyond current contract.

### Discovery and Extensibility

1. Discovery chain is deterministic and multi-root:
   framework -> class -> object -> project.
2. `project_plugins_root` loading path is active and tested.
3. Class/object module manifests are still used in runtime.

### Plugin Inventory Hotspots

1. High duplication in reference validators (`*_refs_validator.py`).
2. Thin vendor-specific router port validators with minimal unique logic.
3. ID naming inconsistency across manifests (`object.*` vs `object_*` style mixing).

---

## TO-BE (ADR 0086 Target within current runtime)

### 1. Boundary Model

- Replace level-visibility assumptions with contract-based architecture checks.
- Keep OOP-consistent cross-level validation where needed.

### 2. Validator Consolidation

- Consolidate duplicated reference checks into declarative validator.
- Consolidate router-port validators into one rule-driven validator.

### 3. Layout Simplification

- Move standalone class/object plugins into `topology-tools/plugins/<family>/`.
- Keep module manifests only as needed extension points.

### 4. ID Policy

- Define and enforce one plugin ID style across all manifests.
- Apply migration via mapping table + compatibility test updates.

### 5. Discovery Safety

- Preserve multi-slot manifest discovery behavior unchanged.
- Keep project plugin slot as mandatory contract.

---

## Gap Table

| Area | AS-IS | TO-BE | Gap Type |
|------|-------|-------|----------|
| Boundary semantics | Naming-level policy not runtime-enforced | Contract-based architecture checks | Policy/Tests |
| OOP alignment | Level rules conflict with practical validation | Cross-level reads allowed by contract | Policy/Docs |
| Reference validators | Many near-duplicate plugins | One declarative validator + rules | Code consolidation |
| Router port validators | Thin vendor split | Unified rule-driven validator | Code consolidation |
| Plugin placement | Standalone plugins split across roots | Standalone plugins centralized in framework dirs | Layout |
| ID naming | Mixed namespace styles | Single enforced naming convention | Naming/CI |
| Project extensibility | Works via project discovery slot | Must remain unchanged | Regression safety |

---

## File Impact Summary

### Likely Create

- `topology-tools/plugins/validators/declarative_reference_validator.py`
- `topology-tools/plugins/validators/router_port_validator.py`
- Optional CI helper for manifest ID/style checks

### Likely Edit

- `topology-tools/plugins/plugins.yaml` (new consolidated validator entries + ID rewires)
- `topology/class-modules/L1-foundation/router/plugins.yaml` (remove/migrate standalone entries)
- `topology/object-modules/*/plugins.yaml` (remove/migrate standalone entries)
- Plugin contract/architecture tests in `tests/plugin_contract/` and `tests/plugin_integration/`
- Docs and agent guidance files referencing level-boundary rules

### Likely Remove

- Duplicated reference validator files replaced by declarative rules
- Thin router-port validator split files replaced by unified validator
- Empty legacy plugin manifests after migration

---

## Main Risks

1. Diagnostic regressions during validator consolidation.
2. Dependency rewiring errors in manifests after ID updates.
3. Accidental breakage of project plugin discovery slot.

---

## Mitigations

1. Golden diagnostics parity tests for validator migration.
2. Pre-merge manifest lint + dependency consistency checks.
3. Mandatory regression tests for project manifest discovery and boundary checks.

---

## Exit Criteria

- Consolidated validator plugins are in place and parity-verified.
- Standalone plugin layout simplified as defined by ADR 0086.
- ID policy unified and CI-enforced.
- Project discovery slot remains functional.
- Full test suite passes with deterministic outputs.

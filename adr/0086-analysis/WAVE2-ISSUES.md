# ADR 0086 — Wave 2 Issues Backlog

This file contains ready-to-copy issue templates for Wave 2 execution
(validator consolidation with diagnostic parity guarantees).

---

## W2-01 — Build Reference Validator Rule Catalog

**Title**
`W2-01: Build rule catalog for duplicated reference validators`

**Description**
Create canonical mapping from existing `*_refs_validator.py` plugins to a single
rule table format for declarative validation.

**Scope (files)**
- New: `adr/0086-analysis/REFERENCE-RULE-CATALOG.md`
- Inputs:
  - `topology-tools/plugins/validators/backup_refs_validator.py`
  - `topology-tools/plugins/validators/certificate_refs_validator.py`
  - `topology-tools/plugins/validators/dns_refs_validator.py`
  - `topology-tools/plugins/validators/host_os_refs_validator.py`
  - `topology-tools/plugins/validators/lxc_refs_validator.py`
  - `topology-tools/plugins/validators/network_core_refs_validator.py`
  - `topology-tools/plugins/validators/power_source_refs_validator.py`
  - `topology-tools/plugins/validators/service_dependency_refs_validator.py`
  - `topology-tools/plugins/validators/service_runtime_refs_validator.py`
  - `topology-tools/plugins/validators/storage_l3_refs_validator.py`
  - `topology-tools/plugins/validators/vm_refs_validator.py`

**Expected diff**
- Rule catalog with fields: source plugin, field paths, predicates, diagnostic code,
  severity, path template, message template.

**Validation**
```bat
python -m pytest tests\plugin_integration -k "refs" -q
```

**Definition of Done**
- Every existing refs validator has explicit rule mapping.

---

## W2-02 — Introduce Declarative Reference Validator

**Title**
`W2-02: Add declarative reference validator implementation`

**Description**
Implement consolidated validator that executes rules from an in-code table
(or static rule config) while preserving diagnostics contract.

**Scope (files)**
- New: `topology-tools/plugins/validators/declarative_reference_validator.py`
- Optional helper module for rule predicates if needed.

**Expected diff**
- New plugin class with deterministic rule execution order.
- `ctx.subscribe("base.compiler.instance_rows", "normalized_rows")` compatibility.
- Stable diagnostic emission API.

**Validation**
```bat
python -m pytest tests\plugin_integration -k "reference or refs" -q
```

**Definition of Done**
- New validator runs and emits diagnostics in expected format.

**Depends on**
- W2-01

---

## W2-03 — Wire Manifest to Consolidated Reference Validator

**Title**
`W2-03: Update plugins manifests to use declarative reference validator`

**Description**
Switch manifest entries from duplicated refs validators to consolidated plugin.

**Scope (files)**
- `topology-tools/plugins/plugins.yaml`

**Expected diff**
- Add consolidated validator entry.
- Remove duplicated refs validator entries.
- Update `depends_on`/`consumes` references as needed.

**Validation**
```bat
python -m pytest tests\plugin_contract\test_manifest_discovery.py tests\plugin_contract\test_plugin_schema_contract.py -q
```

**Definition of Done**
- Manifests load without dependency/schema errors.

**Depends on**
- W2-02

---

## W2-04 — Diagnostic Parity Harness for Ref Validators

**Title**
`W2-04: Add diagnostic parity tests for refs validator consolidation`

**Description**
Create parity tests comparing old and new diagnostics for representative fixtures.
If old validators are removed in same branch, preserve baseline fixtures as expected snapshots.

**Scope (files)**
- New: `tests/plugin_integration/test_declarative_reference_validator_parity.py`
- Optional fixtures under `tests/fixtures/`.

**Expected diff**
- Assertions on diagnostic `code`, `severity`, and `path` parity.

**Validation**
```bat
python -m pytest tests\plugin_integration\test_declarative_reference_validator_parity.py -q
```

**Definition of Done**
- Parity test suite green and protects against silent drift.

**Depends on**
- W2-02
- W2-03

---

## W2-05 — Consolidate Router Port Validators

**Title**
`W2-05: Consolidate router port validators into single rule-driven plugin`

**Description**
Replace thin vendor-specific router port validators with one consolidated plugin
using vendor rule variants.

**Scope (files)**
- New: `topology-tools/plugins/validators/router_port_validator.py`
- Existing candidate files:
  - `topology/class-modules/L1-foundation/router/plugins/validators/router_data_channel_interface_validator.py`
  - `topology/object-modules/mikrotik/plugins/validators/mikrotik_router_ports_validator.py`
  - `topology/object-modules/glinet/plugins/validators/glinet_router_ports_validator.py`

**Expected diff**
- One validator with per-vendor rule table.
- Deterministic diagnostics contract retained.

**Validation**
```bat
python -m pytest tests\plugin_integration -k "router and port" -q
```

**Definition of Done**
- Old thin port validators are functionally replaced.

---

## W2-06 — Manifest Rewire for Router Port Consolidation

**Title**
`W2-06: Rewire manifests and dependencies for router port consolidation`

**Description**
Update manifests after introducing unified router port validator.

**Scope (files)**
- `topology-tools/plugins/plugins.yaml`
- `topology/class-modules/L1-foundation/router/plugins.yaml`
- `topology/object-modules/mikrotik/plugins.yaml`
- `topology/object-modules/glinet/plugins.yaml`

**Expected diff**
- Add consolidated validator entry in framework manifest.
- Remove obsolete class/object thin entries.
- Update all `depends_on` references.

**Validation**
```bat
python -m pytest tests\plugin_contract tests\plugin_integration\test_module_manifest_discovery.py -q
```

**Definition of Done**
- Manifest graph valid and tests green.

**Depends on**
- W2-05

---

## W2-07 — Update ID Mapping and Migration Notes

**Title**
`W2-07: Publish Wave 2 plugin ID mapping and migration notes`

**Description**
Track old -> new IDs and dependency rewires for validator consolidation.

**Scope (files)**
- New: `adr/0086-analysis/WAVE2-ID-MAPPING.md`
- Optional updates: `adr/0086-analysis/CUTOVER-CHECKLIST.md`

**Expected diff**
- Explicit mapping table and impacted manifests/tests list.

**Validation**
```bat
python -m pytest tests\plugin_contract -q
```

**Definition of Done**
- Mapping doc is complete and reviewed before final cleanup.

**Depends on**
- W2-03
- W2-06

---

## W2-08 — Wave 2 Final Gate (Tests + Validate Lane)

**Title**
`W2-08: Execute Wave 2 final validation gates`

**Description**
Run full Wave 2 verification gates and record outputs.

**Scope**
- Gate task (no mandatory code changes)

**Validation**
```bat
python -m pytest tests\plugin_contract -q
python -m pytest tests\plugin_integration -k "refs or router or port" -q
set V5_SECRETS_MODE=passthrough
python scripts\orchestration\lane.py validate-v5
```

**Definition of Done**
- All gate commands pass.
- Results attached to PR/issues.

**Depends on**
- W2-04
- W2-06
- W2-07

---

## Recommended Execution Order

1. W2-01
2. W2-02
3. W2-03
4. W2-04
5. W2-05
6. W2-06
7. W2-07
8. W2-08

---

## Rollback Boundaries

Create one rollback commit boundary after each block:
- Block A: W2-01..W2-03
- Block B: W2-04
- Block C: W2-05..W2-06
- Block D: W2-07..W2-08

Suggested tag pattern:
- `adr0086-wave2-block-a`
- `adr0086-wave2-block-b`
- `adr0086-wave2-block-c`
- `adr0086-wave2-done`

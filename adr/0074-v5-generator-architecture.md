# ADR 0074: V5 Generator Architecture (Contract-First)

**Date:** 2026-03-19  
**Status:** Accepted (implementation in progress)  
**Depends on:** ADR 0050, ADR 0051, ADR 0055, ADR 0056, ADR 0063, ADR 0065, ADR 0066, ADR 0069

---

## Context

v5 already has a working plugin microkernel, projection helpers, baseline deployment generators, regression tests, and CI syntax gates.

The remaining problem is architectural clarity:

1. Keep generator behavior deterministic and testable while implementation evolves.
2. Avoid drift between projection contracts, templates, and CI gates.
3. Define extension points without allowing hidden divergence from baseline artifacts.

This ADR defines the normative generator contract for v5.

---

## Goals

1. Deterministic, git-friendly generated artifacts.
2. Projection-first generation (no direct dependency on raw topology internals).
3. Clear validation gates for correctness and parity.
4. Safe extension model for operators.

## Non-Goals

1. Defining runtime secrets distribution flow (covered by ADR 0072 and related docs).
2. Replacing plugin microkernel contracts (covered by ADR 0063/0065).
3. Changing output ownership/layering from ADR 0050/0055/0056.

---

## Decision

### D1. Projection-First Generator Contract

Generators MUST read model data through projection builders, not through ad-hoc traversal of `ctx.compiled_json`.

Required pattern:

1. Build projection (`build_*_projection(...)`).
2. Validate/transform projection (optional typed dataclass helpers).
3. Render artifacts from projection payload only.

Rationale:

- isolates templates from compiled model schema drift;
- enables snapshot contracts for projection stability;
- allows generator tests to stub projections directly.

### D2. Determinism Is Mandatory

Generators MUST produce stable outputs for identical semantic input.

Required mechanisms:

1. Stable sort in projection layer.
2. Deterministic file naming and file set.
3. Atomic writes (`write_text_atomic`).
4. No non-deterministic timestamps/random values in generated files.

`terraform fmt` MUST NOT run inside generator execution. Formatting and syntax checks are CI/runtime gates, not generation side effects.

### D3. Artifact Contract and Output Ownership

Output roots are fixed:

- `v5-generated/terraform/proxmox/`
- `v5-generated/terraform/mikrotik/`
- `v5-generated/ansible/inventory/production/`
- `v5-generated/bootstrap/<device-id>/`

Generated root is baseline-only:

1. no state files;
2. no execution logs;
3. no environment-specific secrets.

This preserves ADR 0050/0055/0056 layering.

### D4. Plugin Registration and Ordering Contract

Generate-stage order policy:

- `190-199`: core generator artifacts
- `200-239`: infrastructure generators (Terraform + Ansible)
- `240-299`: reserved for future generate hooks/extensions
- `300-399`: bootstrap generators

Current canonical IDs:

- `base.generator.effective_json` (190)
- `base.generator.effective_yaml` (200)
- `base.generator.terraform_proxmox` (210)
- `base.generator.terraform_mikrotik` (220)
- `base.generator.ansible_inventory` (230)
- `base.generator.bootstrap_proxmox` (310)
- `base.generator.bootstrap_mikrotik` (320)
- `base.generator.bootstrap_orangepi` (330)

Generators SHOULD be dependency-light (`depends_on: []`) unless they explicitly consume published data from another generator.

### D5. Rendering Strategy (Jinja2-Only)

All deployment artifact files MUST be rendered from external Jinja2 templates under `v5/topology-tools/templates/`.

Rules:

1. Inline string rendering in generator code is not allowed for artifact bodies.
2. Generator code is responsible for context assembly only.
3. Template extraction is mandatory for all new and existing deployment generators.

The canonical Terraform output remains multi-file (`provider.tf`, `variables.tf`, `outputs.tf`, etc.).
This ADR does not require consolidation into single `main.tf`.

### D6. Validation Gates Are Part of Architecture

Four gate levels:

1. Projection contract tests: required fields, negative paths, snapshot stability.
2. Generator integration tests: expected files and deterministic content ordering.
3. CI syntax gates:
   - `terraform fmt -check`
   - `terraform validate`
   - `ansible-inventory --list`
4. Regression parity gates against v4 baselines (with explicit allowlist for intentional diffs).

Secret-safety scanning of generated artifacts is REQUIRED before production cutover (Phase 8), even if implementation is staged.

### D7. Extension Model (Safe by Construction)

Three tiers are allowed:

1. Tier 1: configuration injection (`ctx.config`) for version pins, toggles, output variants.
2. Tier 2: post-generation hooks as separate generator plugins.
3. Tier 3: compile-stage augmentation plugins before projection build.

Constraints:

1. Extensions MUST NOT bypass CI validation gates.
2. Extensions MUST be explicit in plugin manifest and execution order.
3. Editing generated files manually is not a supported workflow.

For Tier 2 subscribe-based hooks, data exchange MUST use `ctx.publish/ctx.subscribe` contract.
Returning only `output_data` is not sufficient for inter-plugin subscription.

### D8. Diagnostics Contract

Generator diagnostics MUST use stable code ranges:

- `E91xx`: Terraform Proxmox generator
- `E92xx`: Terraform MikroTik generator
- `E93xx`: Ansible generator
- `E94xx`: Bootstrap Proxmox generator
- `E95xx`: Bootstrap MikroTik generator
- `E96xx`: Bootstrap Orange Pi generator

New generator families must reserve non-overlapping ranges before implementation.

---

## Consequences

### Positive

1. Strong boundary between compiled model and rendering.
2. Deterministic outputs with better code review quality.
3. Better failure locality through gate layering.
4. Safer operator customization without baseline forking.

### Trade-offs

1. Extra projection/snapshot maintenance cost.
2. More explicit plugin ordering and diagnostics governance.
3. Extension hooks require disciplined manifest management.

---

## Implementation Status (as of 2026-03-19)

Implemented:

1. Projection helpers and negative tests.
2. Projection golden snapshots and input-order stability tests.
3. Baseline generators for Terraform, Ansible inventory, and bootstrap artifacts.
4. External Jinja2 templates for all current generator outputs.
5. CI syntax gates for generated Terraform and Ansible inventory.
6. Regression parity test suites for Proxmox, MikroTik, and Ansible outputs.

Open items (from production readiness plan):

1. Capability-driven behavior in MikroTik generator (Phase 4.2).
2. Runtime inventory assembly flow (Phase 5.2).
3. Hardware identity capture utility and strict placeholder closure (Phase 7).
4. End-to-end deployment dry-run and cutover runbook completion (Phase 8).
5. Secret-safety scan gate for generated artifacts (Phase 8).

---

## Compliance Mapping

1. Projection contract + snapshots:
   - `v5/tests/plugin_integration/test_projection_helpers.py`
   - `v5/tests/plugin_integration/test_projection_snapshots.py`
   - `v5/tests/plugin_integration/test_generator_projection_contract.py`

2. Generator integration tests:
   - `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`
   - `v5/tests/plugin_integration/test_terraform_mikrotik_generator.py`
   - `v5/tests/plugin_integration/test_ansible_inventory_generator.py`
   - `v5/tests/plugin_integration/test_bootstrap_generators.py`

3. Regression parity tests:
   - `v5/tests/plugin_regression/test_terraform_proxmox_parity.py`
   - `v5/tests/plugin_regression/test_terraform_mikrotik_parity.py`
   - `v5/tests/plugin_regression/test_ansible_inventory_parity.py`

4. CI gates:
   - `.github/workflows/plugin-validation.yml`

---

## References

- `adr/plan/v5-production-readiness.md`
- `v5/topology-tools/plugins/plugins.yaml`
- `v5/topology-tools/plugins/generators/base_generator.py`
- `v5/topology-tools/plugins/generators/projections.py`
- `v5/topology-tools/kernel/plugin_base.py`
- ADR 0050, ADR 0051, ADR 0055, ADR 0056, ADR 0063, ADR 0065, ADR 0066, ADR 0069

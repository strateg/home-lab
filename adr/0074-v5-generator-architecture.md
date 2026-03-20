# ADR 0074: V5 Generator Architecture (Contract-First)

**Date:** 2026-03-19
**Status:** Final
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

- `v5-generated/<project>/terraform/proxmox/`
- `v5-generated/<project>/terraform/mikrotik/`
- `v5-generated/<project>/ansible/inventory/production/`
- `v5-generated/<project>/bootstrap/<device-id>/`

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

All generator config keys consumed by code MUST be declared in `plugins.yaml` `config_schema`.
Undeclared ad-hoc config keys are not allowed.

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
4. Regression parity gates with explicit levels:
   - L1: artifact file-set parity (required)
   - L2: semantic content contract checks (required)
   - L3: full-content parity/allowlist (optional, phase-scoped)

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

Base generators publish the following metadata keys when executed via registry context:

1. `generated_dir`: output root directory for the generator invocation.
2. `generated_files`: full list of written files.
3. Family-specific file key:
   - `terraform_proxmox_files`
   - `terraform_mikrotik_files`
   - `ansible_inventory_files`
   - `bootstrap_proxmox_files`
   - `bootstrap_mikrotik_files`
   - `bootstrap_orangepi_files`

### D8. Diagnostics Contract

Generator diagnostics MUST use stable code ranges:

- `E91xx`: Terraform Proxmox generator
- `E92xx`: Terraform MikroTik generator
- `E93xx`: Ansible generator
- `E94xx`: Bootstrap Proxmox generator
- `E95xx`: Bootstrap MikroTik generator
- `E96xx`: Bootstrap Orange Pi generator

New generator families must reserve non-overlapping ranges before implementation.
Shared precondition code `E3001` is reserved for common "compiled_json missing/empty" failure and is allowed across generator families.

Cross-ADR code alignment:

- `E780x`: framework/project contract failures (ADR 0075)
- `E782x`: framework distribution/lock integrity failures (ADR 0076)

## Diagnostic Governance (Normative)

To keep diagnostics stable across framework/project boundaries and distribution stages, diagnostic codes are a versioned contract.

Rules:

1. Code identifiers (`E####`, `W####`) are immutable once released.
2. Message text may be clarified, but semantic meaning MUST remain backward-compatible.
3. New codes MUST be registered in a central catalog before release.
4. Reuse of retired codes is forbidden.
5. CI MUST fail on unknown or duplicate code registrations.

Severity policy:

1. Local development: `E####` blocks generation completion; warnings are allowed.
2. CI mainline: any `E####` fails pipeline.
3. Release CI: any `E####` fails pipeline; policy-selected warnings MAY be promoted to failure.

### D9. Generator Configuration Contract

Generator plugins consume two global configuration keys:

1. `generator_artifacts_root`: Output directory for generated artifacts. Defaults to `ctx.output_dir` if unset.
2. `generator_templates_root`: Root directory for Jinja2 template lookup. Defaults to `v5/topology-tools/templates`.

Per-generator configuration keys are declared in `plugins.yaml` under `config` and `config_schema`. Common patterns:

| Key Pattern | Used By | Purpose |
|-------------|---------|---------|
| `terraform_version` | terraform_* generators | Version constraint for versions.tf |
| `*_provider_source` | terraform_* generators | Provider source address |
| `*_provider_version` | terraform_* generators | Provider version constraint |
| `inventory_profile` | ansible_inventory | Profile folder name |
| `topology_lane` | ansible_inventory | Logical lane tag |

Undeclared config keys consumed by generator code are prohibited.

### D10. Template Directory Structure

All Jinja2 templates reside under `v5/topology-tools/templates/`:

```
templates/
  terraform/
    proxmox/
      provider.tf.j2, versions.tf.j2, bridges.tf.j2,
      lxc.tf.j2, vms.tf.j2, variables.tf.j2,
      outputs.tf.j2, terraform.tfvars.example.j2
    mikrotik/
      provider.tf.j2, interfaces.tf.j2, firewall.tf.j2,
      dhcp.tf.j2, dns.tf.j2, addresses.tf.j2, qos.tf.j2,
      vpn.tf.j2, containers.tf.j2, variables.tf.j2,
      outputs.tf.j2, terraform.tfvars.example.j2
  ansible/
    inventory/
      hosts.yml.j2, group_vars_all.yml.j2, host_vars.yml.j2
  bootstrap/
    proxmox/
      answer.toml.example.j2, readme.md.j2, script.sh.j2
    mikrotik/
      init-terraform.rsc.j2, backup-restore-overrides.rsc.j2,
      terraform.tfvars.example.j2, readme.md.j2
    orangepi/
      user-data.example.j2, meta-data.j2, readme.md.j2
```

Templates use Jinja2 with `StrictUndefined` mode - missing variables raise errors.

Inventory of all templates is tracked in `templates/TEMPLATE-INVENTORY.md`.

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

1. Projection helpers with negative tests and typed dataclasses.
2. Projection golden snapshots and input-order stability tests.
3. Baseline generators for Terraform, Ansible inventory, and bootstrap artifacts.
4. External Jinja2 templates for all deployment generators.
5. CI syntax gates: `terraform fmt -check`, `terraform validate`, `ansible-inventory --list`.
6. Regression parity test suites for Proxmox, MikroTik, and Ansible outputs.
7. Generator metadata publishing contract (`generated_dir`, `generated_files`, family-specific keys).
8. Secret-safety scan gate in CI for generated artifacts (regex-based leak detection).
9. Generator projection-only contract tests (verifies generators don't access raw compiled_json internals).

Open items (from production readiness plan):

1. ~~Capability-driven behavior in MikroTik generator (Phase 4.2).~~ **DONE**
2. ~~Runtime inventory assembly flow (Phase 5.2).~~ **DONE**
3. Hardware identity capture utility and strict placeholder closure (Phase 7).
4. End-to-end deployment dry-run and cutover runbook completion (Phase 8).

---

## Compliance Mapping

| ADR Decision | Verification | Test/Gate |
|--------------|--------------|-----------|
| D1 (Projection-first) | Unit + Contract | `test_projection_helpers.py`, `test_generator_projection_contract.py` |
| D2 (Determinism) | Snapshot stability | `test_projection_snapshots.py` |
| D3 (Output ownership) | Integration | `test_terraform_*_generator.py` |
| D4 (Plugin ordering) | Manifest schema | `test_manifest.py` |
| D5 (Jinja2 templates) | Template contract | `test_generator_template_and_publish_contract.py` |
| D6 (Validation gates) | CI pipeline | `plugin-validation.yml` |
| D7 (Extension model) | Publish contract | `test_generator_template_and_publish_contract.py` |
| D8 (Diagnostics) | Code ranges | Generator implementation |
| D9 (Config contract) | Schema validation | `plugins.yaml` config_schema |
| D10 (Template structure) | File existence | CI compile step |

Test files:

1. Projection contract:
   - `v5/tests/plugin_integration/test_projection_helpers.py`
   - `v5/tests/plugin_integration/test_projection_snapshots.py`
   - `v5/tests/plugin_integration/test_generator_projection_contract.py`

2. Generator integration:
   - `v5/tests/plugin_integration/test_terraform_proxmox_generator.py`
   - `v5/tests/plugin_integration/test_terraform_mikrotik_generator.py`
   - `v5/tests/plugin_integration/test_ansible_inventory_generator.py`
   - `v5/tests/plugin_integration/test_bootstrap_generators.py`
   - `v5/tests/plugin_integration/test_generator_template_and_publish_contract.py`

3. Regression parity:
   - `v5/tests/plugin_regression/test_terraform_proxmox_parity.py`
   - `v5/tests/plugin_regression/test_terraform_mikrotik_parity.py`
   - `v5/tests/plugin_regression/test_ansible_inventory_parity.py`

4. CI gates:
   - `.github/workflows/plugin-validation.yml` (terraform fmt/validate, ansible-inventory, secret-safety scan)

---

## Next Steps for Implementation

Based on open items:

1. **Phase 4.2 - Capability-driven MikroTik generation**:
   - Update `build_mikrotik_projection()` to include capability flags
   - Add conditional logic in templates for optional resources (WireGuard, containers)
   - Add tests for capability-gated output variations

2. **Phase 5.2 - Runtime inventory assembly**:
   - Keep `assemble-ansible-runtime.py` project-aware (`v5/projects/<project>/ansible/inventory-overrides/<env>`)
   - Keep generated/runtime inventory under `v5-generated/<project>/ansible/...`
   - Keep secrets externalized per ADR 0051

3. **Phase 7 - Hardware identity capture**:
   - Use `discover-hardware-identity.py` utility for annotation-driven patch generation
   - Generate YAML patches for encrypted side-car updates (`v5-build/hardware-identity-patches/<project>/`)
   - Keep strict placeholder enforcement scoped to secret-annotated paths

4. **Phase 8 - E2E validation**:
   - Execute `terraform plan` with generated artifacts
   - Execute `ansible-playbook --check` validation
   - Complete deployment runbook documentation (`docs/runbooks/V5-E2E-DRY-RUN.md`)
   - Runtime status: runbook is published; environment execution remains rollout-gated

---

## References

Implementation:

- `v5/topology-tools/plugins/generators/base_generator.py` - BaseGenerator with template/atomic write helpers
- `v5/topology-tools/plugins/generators/projections.py` - Projection builders and typed dataclasses
- `v5/topology-tools/plugins/plugins.yaml` - Plugin manifest with ordering and config_schema
- `v5/topology-tools/templates/` - Jinja2 template files
- `v5/topology-tools/kernel/plugin_base.py` - Plugin base classes
- `docs/diagnostics-catalog.md` - diagnostic ownership and non-overlap index
- `docs/runbooks/V5-E2E-DRY-RUN.md` - end-to-end dry-run procedure and acceptance gates

Planning:

- `adr/plan/v5-production-readiness.md` - Phase tracking

Related ADRs:

- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime Inventory Ownership
- ADR 0055: Manual Terraform Extension Layer
- ADR 0056: Native Execution Workspace
- ADR 0063: Plugin Microkernel Architecture
- ADR 0065: Staged Plugin Implementation
- ADR 0066: Instance Shard Validation
- ADR 0069: Plugin-First Compiler Pipeline

---

## Sequencing Note (2026-03-20)

Execution sequencing is constrained by ADR 0075:

1. Complete ADR 0075 Stage 1 (monorepo framework/project boundary and project-aware path resolution).
2. Then finalize ADR 0074 remaining rollout items in project-aware mode:
   - runtime inventory assembly path ownership,
   - generator output root qualification by project context,
   - final cutover runbooks and E2E deployment gates.

Reason: completing these items before ADR 0075 creates guaranteed rework of generator/runtime path contracts.

Execution plan reference: `adr/plan/0075-0074-master-migration-plan.md`.

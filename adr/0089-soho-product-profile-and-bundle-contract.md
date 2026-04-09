# ADR 0089: SOHO Product Profile and Bundle Contract

- Status: Implemented (complete)
- Date: 2026-04-05
- Depends on: ADR 0063, ADR 0070, ADR 0072, ADR 0074, ADR 0075, ADR 0077, ADR 0080, ADR 0085
- Analysis: `adr/0089-analysis/` (GAP-ANALYSIS.md, IMPLEMENTATION-PLAN.md, E2E-SCENARIO.md, SWOT-ANALYSIS.md)

---

## Context

Framework-level contracts are already mature:
- plugin-first runtime;
- deterministic generation;
- stage-based validation;
- secrets discipline;
- project/runtime separation.

But SOHO scope is still implicit.

The system currently lacks one canonical contract that declares:
- what is supported for a SOHO deployment,
- which capability bundles are mandatory,
- which deployment classes are valid,
- how product-level support boundaries are validated.

Without such a contract, there is drift between:
- what the framework can technically generate,
- what the project explicitly supports and will maintain.

---

## Problem

There is no mandatory project-level product profile and no deterministic mechanism to resolve:
- SOHO deployment class,
- required bundle set,
- profile/class/hardware compatibility,
- legacy-vs-migrated validation behavior.

As a result, support scope is under-specified and machine validation is weaker than it should be.

---

## Decision

Introduce canonical SOHO product-profile contract `soho.standard.v1` as the project-level source of truth.

### D1. `product_profile` is mandatory for migrated SOHO projects

`project.yaml` must contain:

```yaml
product_profile:
  profile_id: soho.standard.v1
  deployment_class: managed-soho
  site_class: single-site
  user_band: 1-25
  operator_mode: single-operator
  release_channel: stable
```

### D2. The profile is the source of truth for SOHO support scope

For migrated SOHO projects, `product_profile` is normative for:
- support boundary;
- required bundle set;
- deployment class selection;
- release/readiness gating scope.

Project-local overrides may refine implementation details, but must not weaken required profile guarantees.

### D3. Supported deployment classes are explicit and finite

Allowed values:

- `starter`
- `managed-soho`
- `advanced-soho`

Unsupported combinations of:
- profile,
- deployment class,
- hardware class,
- bundle graph

are validation failures.

### D4. SOHO bundle resolution is profile-driven

`soho.standard.v1` defines deterministic bundle resolution as **additive composition** of core bundles + deployment-class-specific bundles.

#### Core bundles (required for all deployment classes):

- `bundle.edge-routing`
- `bundle.network-segmentation`
- `bundle.secrets-governance`

#### Deployment-class-specific bundles:

**starter:**
- `bundle.remote-access`
- `bundle.operator-workflows`

**managed-soho:**
- `bundle.remote-access`
- `bundle.backup-restore`
- `bundle.observability`
- `bundle.operator-workflows`
- `bundle.update-management`

**advanced-soho:**
- `bundle.remote-access`
- `bundle.backup-restore`
- `bundle.observability`
- `bundle.operator-workflows`
- `bundle.update-management`
- `bundle.incident-response`
- `bundle.multi-uplink-resilience`

#### Effective bundle resolution (deterministic):

The effective bundle set for a given deployment class is computed as:

```
effective_bundles = core_bundles ∪ class_specific_bundles
```

**Examples:**

For `deployment_class: managed-soho`, the effective bundle set is:

```yaml
effective_bundles:
  - bundle.edge-routing              # core
  - bundle.network-segmentation      # core
  - bundle.secrets-governance        # core
  - bundle.remote-access             # class-specific
  - bundle.backup-restore            # class-specific
  - bundle.observability             # class-specific
  - bundle.operator-workflows        # class-specific
  - bundle.update-management         # class-specific
```

Total: **8 required bundles** for managed-soho.

For `deployment_class: starter`, the effective bundle set is:

```yaml
effective_bundles:
  - bundle.edge-routing              # core
  - bundle.network-segmentation      # core
  - bundle.secrets-governance        # core
  - bundle.remote-access             # class-specific
  - bundle.operator-workflows        # class-specific
```

Total: **5 required bundles** for starter.

Bundle resolution must be deterministic and derived mechanically from the profile and deployment_class, not manually assembled ad hoc per project.

### D5. New canonical contracts

The following contracts are introduced:

- `topology/product-profiles/soho.standard.v1.yaml`
- `topology/product-bundles/*.yaml`
- `schemas/product-profile.schema.json`

### D6. Pipeline binding

- **discover**  
  resolve profile, deployment class, hardware matrix compatibility
- **compile**  
  materialize effective SOHO bundle graph
- **validate**  
  enforce required bundles, profile/class compatibility, hardware support matrix

### D7. Validation behavior and migration states

Projects are classified as:

- `legacy` — no `product_profile`
- `migrated-soft` — `product_profile` present, warnings may still be tolerated during cutover
- `migrated-hard` — `product_profile` present and all profile requirements are blocking

#### Migration state pipeline enforcement

Pipeline stage behavior is conditional on migration state:

| Migration State | Discover Stage | Compile Stage | Validate Stage |
|---|---|---|
| **legacy** | Profile resolution **advisory only**<br/>Diagnostic: INFO | Bundle resolution **advisory only**<br/>Diagnostic: INFO | Compatibility checks **advisory only**<br/>Diagnostic: WARN |
| **migrated-soft** | Profile resolution **required**<br/>Missing profile → ERROR | Bundle resolution **required**<br/>Missing bundles → ERROR | **Warnings allowed**, only critical blocking<br/>Example: backup policy missing → WARN |
| **migrated-hard** | Profile resolution **required**<br/>Missing profile → ERROR, pipeline halt | Bundle resolution **required**<br/>Missing bundles → ERROR, pipeline halt | **All profile requirements blocking**<br/>Any WARN → ERROR, pipeline halt |

**Enforcement mechanism:**

Pipeline stages must:

1. Read `project.yaml → product_profile.migration_state`
2. Adjust diagnostic severity based on state
3. Block or allow pipeline continuation per table above

**State transition rules:**

- `legacy → migrated-soft`: Manual opt-in via `project.yaml` update + validation passes with warnings
- `migrated-soft → migrated-hard`: All warnings resolved + validation passes clean
- Downgrades (e.g., `migrated-hard → legacy`) are **invalid** and rejected by validation

**Sunset enforcement:**

After `sunset_policy.legacy_end_date` (defined in profile contract), `legacy` projects are automatically treated as `migrated-hard` for blocking purposes.

Cutover policy must define when a project moves from `legacy` to `migrated-soft` to `migrated-hard`.

### D8. Invariants

For migrated SOHO projects:

- profile resolution must be deterministic;
- required bundles must be resolvable without manual operator interpretation;
- unsupported profile/class/hardware combinations must fail validation;
- bundle resolution must not depend on local workstation state;
- profile contract must remain machine-validatable.

### D9. Migration-state contract is explicit

Migration state storage:
- `project.yaml` field: `product_profile.migration_state`
- allowed values: `legacy`, `migrated-soft`, `migrated-hard`

Transition authority:
- only validation/compile governance workflow may advance state; manual downgrade is invalid.

Blocking policy:
- `legacy`: advisory-only diagnostics for profile contract
- `migrated-soft`: warnings allowed, but release blocked on critical profile incompatibility
- `migrated-hard`: full blocking enforcement for all D1-D8 requirements

Sunset:
- `legacy` support must have explicit end date in project governance config; after sunset date `legacy` becomes blocking.

---

## Related ADRs

This ADR establishes the foundational product profile contract. Implementation details are specified in:

- ADR 0090: Operator lifecycle command surface (`product:*` tasks)
- ADR 0091: Handover/evidence artifact contract and readiness diagnostics

These ADRs depend on this one (ADR 0089) and extend the product profile contract with operational semantics.

---

## Consequences

### Positive
- SOHO support boundary becomes explicit and machine-validatable.
- Project portability improves via profile-driven resolution.
- Deployment class support becomes finite and testable.
- Product-level claims become enforceable.

### Trade-offs
- Additional schema and validator maintenance.
- Bundle compatibility becomes a first-class governance concern.
- Migration state management adds rollout complexity.

### Risks
- Overly broad profile semantics can blur the support boundary.
- Weak cutover policy can leave projects indefinitely half-migrated.
- Hardware matrix drift can produce false support claims.

### Mitigations
- Keep deployment classes finite and explicit.
- Enforce migrated-hard mode with blocking validation.
- Version product-profile schemas and bundle contracts.
- Tie support claims to acceptance and readiness evidence.

---

## Migration notes

Existing projects without `product_profile` remain `legacy` until migrated.

Implementation artifacts must define:
- warning vs blocking behavior for each migration state,
- sunset timeline for `legacy`,
- required acceptance checks before `migrated-hard`.

---

## Decision summary

Adopt a mandatory SOHO product-profile contract as the project-level source of truth for support scope, bundle resolution, and deployment-class validation.

# ADR 0089: SOHO Product Profile and Bundle Contract

- Status: Proposed
- Date: 2026-04-05
- Depends on: ADR 0063, ADR 0070, ADR 0072, ADR 0074, ADR 0075, ADR 0077, ADR 0080, ADR 0085

---

## Context

Framework contracts are mature, but SOHO scope is still implicit.  
Project-level product behavior (supported footprint, required capabilities, gating baseline) is not formalized in one canonical contract.

This causes drift between what is technically possible and what is explicitly supported for a SOHO deployment.

---

## Problem

There is no mandatory product profile in project data and no deterministic way to resolve required SOHO bundles and supported deployment classes.

---

## Decision

Introduce canonical SOHO product-profile contract `soho.standard.v1` as project-level source of truth.

### 1. Mandatory `product_profile` block in `project.yaml`

```yaml
product_profile:
  profile_id: soho.standard.v1
  deployment_class: managed-soho
  site_class: single-site
  user_band: 1-25
  operator_mode: single-operator
  release_channel: stable
```

### 2. Supported deployment classes are explicit and finite

- `starter`
- `managed-soho`
- `advanced-soho`

Unsupported combinations (profile/class/hardware) are validation errors.

### 3. SOHO bundle set is profile-resolved, not manual

Required bundle IDs for `soho.standard.v1`:

- `bundle.edge-routing`
- `bundle.network-segmentation`
- `bundle.remote-access`
- `bundle.backup-restore`
- `bundle.observability`
- `bundle.operator-workflows`
- `bundle.secrets-governance`
- `bundle.update-management`

### 4. New contracts

- `topology/product-profiles/soho.standard.v1.yaml`
- `topology/product-bundles/*.yaml`
- `schemas/product-profile.schema.json`

### 5. Pipeline binding

- **discover**: resolve profile, class, hardware matrix compatibility
- **compile**: materialize effective SOHO bundle graph
- **validate**: enforce required bundles and class/profile compatibility

---

## Out of scope

This ADR does not define:

- operator lifecycle command surface (`product:*`) — see ADR 0090
- handover/evidence artifact contract and readiness diagnostics — see ADR 0091

---

## Consequences

### Positive

- SOHO support boundary becomes explicit and machine-validatable.
- Project portability improves via profile-driven contract resolution.
- Product claims become testable against declared classes/bundles.

### Trade-offs

- Additional schema and validator maintenance.
- Bundle/version compatibility management becomes a first-class responsibility.

---

## Migration notes

Existing projects without `product_profile` remain legacy until migrated.  
Cutover policy (warning vs blocking) is defined in implementation plan artifacts.


# ADR 0078: Object-Module Local Template Layout

**Date:** 2026-03-21
**Status:** Accepted
**Depends on:** ADR 0062, ADR 0074, ADR 0076, ADR 0077

---

## Context

In v5, object behavior is defined in `topology/object-modules/*`, but some generator templates were still stored in `topology-tools/templates/*`.

This caused practical issues:

1. object implementation and its generator templates were split across different roots;
2. framework distribution/build flow had to preserve extra template paths from tools domain;
3. module portability to external projects was weaker because object assets were not self-contained.

For object-scoped generators (for example MikroTik Terraform), templates are part of object module implementation, not global tooling infrastructure.

---

## Decision

Move object-specific templates from `topology-tools/templates` into corresponding object modules.

### Normative layout

1. Object templates MUST be stored under:
   - `v5/topology/object-modules/<object-id>/templates/<generator-id>/`
2. Shared, cross-object templates MAY remain under:
   - `v5/topology-tools/templates/`
3. For MikroTik Terraform:
   - old: `v5/topology-tools/templates/terraform/mikrotik/*`
   - new: `v5/topology/object-modules/mikrotik/templates/terraform/*`

### Generator template resolution policy

Generators MUST resolve templates in this order:

1. explicit override via `generator_templates_root` (if provided);
2. object-local templates (`object-modules/<object-id>/templates`);
3. legacy/shared tool templates (`topology-tools/templates`) as fallback for shared assets.

### Distribution contract

Framework distribution packaging MUST include object-local templates together with object modules, so generated projects can run without hidden dependencies on tool-internal template paths.

---

## Non-Goals

1. Changing generator business logic or output format.
2. Moving cross-object/shared templates that are intentionally framework-global.
3. Revising plugin API contracts from ADR 0065/0074.

---

## Consequences

### Positive

1. Object modules become more self-contained and portable.
2. Framework distribution structure aligns with implementation ownership.
3. Lower risk of path drift between local repo and extracted/project consumption.

### Trade-offs

1. Need to maintain template resolution compatibility during migration.
2. Some generators require explicit path-resolution updates.

---

## Migration Notes

1. Move template files physically to object module `templates/` subtree.
2. Update generator template names/roots to object-local paths.
3. Rebuild framework lock and run strict compile/validation gates.
4. Keep fallback path temporarily for compatibility until all object templates are migrated.

---

## Acceptance Criteria

1. Object-specific templates are no longer required from `topology-tools/templates` for migrated objects.
2. Strict compile and plugin integration tests pass with object-local template roots.
3. Framework distribution includes migrated templates under object module paths.

---

## References

- `v5/topology/object-modules/mikrotik/templates/terraform/`
- `v5/topology-tools/plugins/generators/terraform_mikrotik_generator.py`
- `v5/topology-tools/templates/TEMPLATE-INVENTORY.md`
- `v5/projects/home-lab/framework.lock.yaml`

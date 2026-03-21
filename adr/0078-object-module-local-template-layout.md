# ADR 0078: Object-Module Local Templates and Generator Plugins Layout

**Date:** 2026-03-21
**Status:** Accepted
**Depends on:** ADR 0062, ADR 0074, ADR 0076, ADR 0077

---

## Context

In v5, object behavior is defined in `topology/object-modules/*`, but object-scoped generation implementation was split across `topology-tools`:

1. templates in `topology-tools/templates/*`;
2. generator plugin code in `topology-tools/plugins/generators/*`.

This caused practical issues:

1. object implementation, templates, and generator code were split across different roots;
2. framework distribution/build flow had to preserve extra object-specific paths from tools domain;
3. module portability to external projects was weaker because object assets were not self-contained.

For object-scoped generators (for example MikroTik/Proxmox/OrangePi), templates and plugin implementation are part of object module implementation, not global tooling infrastructure.

---

## Decision

Move object-specific templates and generator plugin code into corresponding object modules.

### Normative layout

1. Object templates MUST be stored under:
   - `v5/topology/object-modules/<object-id>/templates/<generator-id>/`
2. Object-scoped generator plugins MUST be stored under:
   - `v5/topology/object-modules/<object-id>/plugins/`
3. Plugin manifest entrypoints for object-scoped generators MUST point to object-module plugin paths.
4. Shared, cross-object templates MAY remain under:
   - `v5/topology-tools/templates/`
5. Shared, cross-object generator plugins MAY remain under:
   - `v5/topology-tools/plugins/generators/`

### Object migrations in scope

1. MikroTik Terraform templates:
   - old: `v5/topology-tools/templates/terraform/mikrotik/*`
   - new: `v5/topology/object-modules/mikrotik/templates/terraform/*`
2. Generator plugins:
   - `terraform_mikrotik_generator.py` -> `object-modules/mikrotik/plugins/`
   - `bootstrap_mikrotik_generator.py` -> `object-modules/mikrotik/plugins/`
   - `terraform_proxmox_generator.py` -> `object-modules/proxmox/plugins/`
   - `bootstrap_proxmox_generator.py` -> `object-modules/proxmox/plugins/`
   - `bootstrap_orangepi_generator.py` -> `object-modules/orangepi/plugins/`

### Generator template resolution policy

Generators MUST resolve templates in this order:

1. explicit override via `generator_templates_root` (if provided);
2. object-local templates (`object-modules/<object-id>/templates`);
3. legacy/shared tool templates (`topology-tools/templates`) as fallback for shared assets.

### Distribution contract

Framework distribution packaging MUST include object-local templates and object-local generator plugins together with object modules, so generated projects can run without hidden dependencies on tool-internal paths.

---

## Non-Goals

1. Changing generator business logic or output format.
2. Moving cross-object/shared templates that are intentionally framework-global.
3. Moving cross-object/shared generator plugins that are intentionally framework-global.
4. Revising plugin API contracts from ADR 0065/0074.

---

## Consequences

### Positive

1. Object modules become more self-contained and portable.
2. Framework distribution structure aligns with implementation ownership.
3. Lower risk of path drift between local repo and extracted/project consumption.
4. Plugin entrypoints are aligned with module ownership boundaries.

### Trade-offs

1. Need to maintain template resolution compatibility during migration.
2. Some generators require explicit import path handling for shared runtime helpers.
3. Transitional compatibility shims may be needed for legacy imports/tests.

---

## Migration Notes

1. Move template files physically to object module `templates/` subtree.
2. Move object-scoped generator plugin files to object module `plugins/` subtree.
3. Update generator template names/roots to object-local paths.
4. Update plugin manifest entrypoints to object-module plugin files.
5. Rebuild framework lock and run strict compile/validation gates.
6. Keep compatibility shims only as temporary layer for legacy imports/tests.

---

## Acceptance Criteria

1. Object-specific templates are no longer required from `topology-tools/templates` for migrated objects.
2. Object-specific generator plugin entrypoints resolve from `object-modules/<object-id>/plugins`.
3. Strict compile and plugin integration tests pass with object-local templates/plugins.
4. Framework distribution includes migrated templates/plugins under object module paths.

---

## References

- `v5/topology/object-modules/mikrotik/templates/terraform/`
- `v5/topology/object-modules/mikrotik/plugins/terraform_mikrotik_generator.py`
- `v5/topology/object-modules/mikrotik/plugins/bootstrap_mikrotik_generator.py`
- `v5/topology/object-modules/proxmox/plugins/terraform_proxmox_generator.py`
- `v5/topology/object-modules/proxmox/plugins/bootstrap_proxmox_generator.py`
- `v5/topology/object-modules/orangepi/plugins/bootstrap_orangepi_generator.py`
- `v5/topology-tools/plugins/plugins.yaml`
- `v5/topology-tools/templates/TEMPLATE-INVENTORY.md`
- `v5/projects/home-lab/framework.lock.yaml`

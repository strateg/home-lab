# Plugin Namespace Conventions

**Date:** 2026-05-29
**Source:** ADR 0063, ADR 0086
**Purpose:** Define plugin ID naming conventions to prevent cross-project collisions

---

## Overview

Plugin IDs must follow a structured namespace format to ensure:
- Global uniqueness across framework, class modules, object modules, and projects
- Clear ownership and provenance of each plugin
- Predictable discovery and resolution order

---

## Plugin ID Format

```
<scope>.<family>.<name>
```

### Components

| Component | Description | Example |
|-----------|-------------|---------|
| `scope` | Ownership namespace (see below) | `base`, `object.proxmox`, `project.homelab` |
| `family` | Plugin kind/stage affinity | `discoverer`, `compiler`, `validator`, `generator`, `assembler`, `builder` |
| `name` | Descriptive identifier | `instance_rows`, `terraform`, `references` |

---

## Scope Prefixes

### Framework Scope (`base.*`)

Framework base plugins live in `topology-tools/plugins/` and use the `base.*` prefix.

```
base.<family>.<name>

Examples:
  base.discover.manifest_loader
  base.compiler.instance_rows
  base.validator.references
  base.generator.effective_json
  base.assembler.workspace
  base.builder.release_manifest
```

**Ownership:** Framework maintainers only.

### Class Module Scope (`class.<module>.*`)

Class module plugins live in `topology/class-modules/<module>/plugins/` and use the `class.<module>.*` prefix.

```
class.<module>.<family>.<name>

Examples:
  class.compute.validator.cpu_architecture
  class.network.compiler.vlan_defaults
  class.storage.generator.zfs_pools
```

**Ownership:** Class module maintainers.

### Object Module Scope (`object.<module>.*`)

Object module plugins live in `topology/object-modules/<module>/plugins/` and use the `object.<module>.*` prefix.

```
object.<module>.<family>.<name>

Examples:
  object.proxmox.generator.terraform
  object.proxmox.generator.bootstrap
  object.mikrotik.generator.terraform
  object.mikrotik.validator.port_contract
  object.orangepi.generator.bootstrap
```

**Ownership:** Object module maintainers.

### Project Scope (`project.<name>.*`)

Project-specific plugins live in `projects/<name>/plugins/` and use the `project.<name>.*` prefix.

```
project.<project_id>.<family>.<name>

Examples:
  project.homelab.generator.custom_docs
  project.homelab.validator.local_policy
  project.production.assembler.deploy_hooks
```

**Ownership:** Project maintainers.

---

## Current Plugin Distribution

| Scope | Count | Location |
|-------|-------|----------|
| `base.*` | 85 | `topology-tools/plugins/` |
| `object.proxmox.*` | 2 | `topology/object-modules/proxmox/plugins/` |
| `object.mikrotik.*` | 2 | `topology/object-modules/mikrotik/plugins/` |
| `object.orangepi.*` | 1 | `topology/object-modules/orangepi/plugins/` |

---

## Naming Guidelines

### DO

- Use lowercase with underscores for multi-word names
- Use descriptive, domain-specific names
- Match family name to plugin kind
- Include module name in scope for class/object plugins

```yaml
# Good examples
- id: base.validator.network_ip_overlap
- id: object.proxmox.generator.terraform
- id: project.homelab.validator.dns_policy
```

### DON'T

- Use generic names without scope context
- Use camelCase or PascalCase
- Omit the scope prefix
- Use abbreviations unless widely understood

```yaml
# Bad examples
- id: validator.overlap           # Missing scope
- id: base.NetworkIpOverlap       # Wrong case
- id: terraform_generator         # Missing scope and family
- id: base.validator.v             # Too abbreviated
```

---

## Discovery Order

Plugins are discovered in a deterministic order per ADR 0086:

1. **Framework manifest** (`topology-tools/plugins/plugins.yaml`)
2. **Class module manifests** (`topology/class-modules/*/plugins.yaml`) - sorted alphabetically
3. **Object module manifests** (`topology/object-modules/*/plugins.yaml`) - sorted alphabetically
4. **Project manifests** (`projects/*/plugins.yaml`) - sorted alphabetically

Later-discovered plugins with the same ID will shadow earlier ones (not recommended).

---

## Collision Prevention

### Enforcement

The CI pipeline validates:
1. All plugin IDs match the namespace pattern for their manifest location
2. No duplicate IDs within the same manifest
3. Pre-commit hooks detect cycles in dependencies

### Cross-Project Isolation

Projects using the same framework should use unique `project.<name>.*` prefixes to prevent collisions when sharing plugins or merging configurations.

---

## Migration Notes

### Existing Plugins

All current plugins (85 base + 5 object module) follow these conventions. No migration is required.

### Adding New Plugins

When creating a new plugin:

1. Determine the correct scope based on plugin location
2. Choose the appropriate family based on plugin kind
3. Select a descriptive name
4. Verify ID uniqueness with: `grep -r "id: <proposed_id>" topology-tools/ topology/`

---

## Related Documents

- [ADR 0063: Plugin Microkernel](../../adr/0063-plugin-microkernel-for-compiler-validators-generators.md)
- [ADR 0086: Flatten Plugin Hierarchy](../../adr/0086-flatten-plugin-hierarchy-and-reduce-granularity.md)
- [PLUGIN-EXECUTION-MODES.md](./PLUGIN-EXECUTION-MODES.md)
- [PLUGIN-ENVELOPE-MODEL.md](./PLUGIN-ENVELOPE-MODEL.md)

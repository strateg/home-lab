# ADR 0086 — Current State vs Target State Gap Analysis

## Plugin Inventory (AS-IS → TO-BE)

### Validators (40 → ~28)

| # | Current Plugin | Action | Target |
|---|---------------|--------|--------|
| 1 | `reference_validator` | Keep | `validator.references` |
| 2 | `backup_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 3 | `certificate_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 4 | `dns_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 5 | `host_os_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 6 | `lxc_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 7 | `network_core_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 8 | `power_source_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 9 | `service_dependency_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 10 | `service_runtime_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 11 | `storage_l3_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 12 | `vm_refs_validator` | **Merge → DeclarativeRef** | Rule in `validator.declarative_refs` |
| 13 | `mikrotik_router_ports_validator` | **Merge → RouterPort** | Rules in `validator.router_ports` |
| 14 | `glinet_router_ports_validator` | **Merge → RouterPort** | Rules in `validator.router_ports` |
| 15 | `router_data_channel_interface_validator` | **Move** | `validator.router_data_channel` |
| 16 | `ethernet_cable_endpoint_validator` | **Move** | `validator.ethernet_cable_endpoints` |
| 17–40 | 24 remaining validators | Keep (rename ID) | `validator.<domain>` |

**Net change:** 40 → ~28 plugins (−12)

### Generators (11 → ~8 standalone + 5 strategy entries)

| # | Current Plugin | Action | Target |
|---|---------------|--------|--------|
| 1 | `terraform_proxmox_generator` | **Convert → strategy** | `strategy.proxmox.terraform` (`contributes_to: generator.terraform`) |
| 2 | `terraform_mikrotik_generator` | **Convert → strategy** | `strategy.mikrotik.terraform` (`contributes_to: generator.terraform`) |
| 3 | `bootstrap_proxmox_generator` | **Convert → strategy** | `strategy.proxmox.bootstrap` (`contributes_to: generator.bootstrap`) |
| 4 | `bootstrap_mikrotik_generator` | **Convert → strategy** | `strategy.mikrotik.bootstrap` (`contributes_to: generator.bootstrap`) |
| 5 | `bootstrap_orangepi_generator` | **Convert → strategy** | `strategy.orangepi.bootstrap` (`contributes_to: generator.bootstrap`) |
| — | *(new)* | **Create host** | `generator.terraform` (host generator) |
| — | *(new)* | **Create host** | `generator.bootstrap` (host generator) |
| 6–11 | 6 remaining generators | Keep (rename ID) | `generator.<domain>` |

**Net change:** 11 standalone → 8 standalone + 5 strategy entries
(5 vendor generators become strategy entries dispatched by 2 host generators)

### Compilers, Discoverers, Assemblers, Builders (9 → 9)

No consolidation needed. Only ID rename.

### Total: 67 → ~37 standalone plugins + 5 strategy entries

---

## File Operations Summary

### Files to CREATE (~6)
- `topology-tools/plugins/validators/declarative_reference_validator.py`
- `topology-tools/plugins/validators/router_port_validator.py`
- `topology-tools/plugins/generators/terraform_generator.py` (host generator)
- `topology-tools/plugins/generators/bootstrap_generator.py` (host generator)
- Projection helpers (if not already in `lib/`):
  - `topology/object-modules/proxmox/lib/projection.py`
  - `topology/object-modules/mikrotik/lib/projection.py`

### Files to REFACTOR (~5)
Existing vendor generator plugins become strategy plugins (same directory,
new `contributes_to` field in manifest, simplified class interface):
- `topology/object-modules/proxmox/plugins/generators/terraform_proxmox_generator.py`
  → refactor to `TerraformStrategy` conforming to host generator protocol
- `topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py`
  → refactor to `TerraformStrategy`
- `topology/object-modules/proxmox/plugins/generators/bootstrap_proxmox_generator.py`
  → refactor to `BootstrapStrategy`
- `topology/object-modules/mikrotik/plugins/generators/bootstrap_mikrotik_generator.py`
  → refactor to `BootstrapStrategy`
- `topology/object-modules/orangepi/plugins/generators/bootstrap_orangepi_generator.py`
  → refactor to `BootstrapStrategy`

### Files to MOVE (~2)
- `router_data_channel_interface_validator.py` → global validators
- `ethernet_cable_endpoint_validator.py` → global validators

### Files to DELETE (~14)
- 11 reference validator files
- 2 port validator files (mikrotik, glinet) + 1 base

### Manifests to UPDATE
- `topology-tools/plugins/plugins.yaml` — add host generators, consolidate standalone entries, rename IDs
- `topology/object-modules/proxmox/plugins.yaml` — replace standalone entries with `contributes_to` strategy entries
- `topology/object-modules/mikrotik/plugins.yaml` — replace standalone entries with `contributes_to` strategy entries
- `topology/object-modules/orangepi/plugins.yaml` — replace standalone entry with `contributes_to` strategy entry
- `topology/object-modules/glinet/plugins.yaml` — remove (standalone validator moved to global)
- `topology/object-modules/network/plugins.yaml` — remove (standalone validator moved to global)
- `topology/class-modules/router/plugins.yaml` — remove (standalone validator moved to global)

### Files to EDIT (kernel + tests + docs)
- `topology-tools/kernel/plugin_registry.py` — add `contributes_to` to PluginSpec, add `get_contributors()` method
- `topology-tools/kernel/plugin_base.py` — no changes needed (PluginContext/PluginResult unchanged)
- `plugin_manifest_discovery.py` — **no simplification** (multi-slot discovery preserved)
- `test_plugin_level_boundaries.py` — replace with architectural test
- `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md` — update rules
- ADR 0063 — add superseded note
- `schemas/plugin-manifest.schema.json` — add `contributes_to` optional field

---

## Dependency Graph Impact

### Plugins that depend on reference validators
Any plugin with `depends_on: [base.validator.dns_refs]` etc. must be checked.
Expected: reference validators are **leaf nodes** — nothing depends on them.

### Plugins that depend on vendor generators
Expected: assembler/builder may depend on generators.
Must update: `base.assembler.workspace` if it depends on specific generator IDs.
After D4: assemblers depend on host generators (`generator.terraform`,
`generator.bootstrap`), not on individual vendor strategies.

### Inter-plugin data exchange (produces/consumes)
Reference validators only **consume** from `base.compiler.instance_rows`.
They do not **produce** data consumed by other plugins.
Safe to consolidate without cascade.

Vendor generators **produce** `generated_files` and vendor-specific file lists.
After D4: host generators produce these keys. Strategy entries contribute through
host generator dispatch, not through their own produces/consumes declarations.

### `contributes_to` interaction with DAG
Strategy entries with `contributes_to` are NOT independently scheduled by the DAG.
They are loaded and dispatched by the host generator. The host generator is the
DAG node that other plugins depend on.

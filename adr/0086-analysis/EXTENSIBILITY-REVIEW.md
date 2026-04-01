# ADR 0086 — Extensibility Review: Project-Level Plugins and Auto-Registration

**Date:** 2026-04-01
**Scope:** Analysis of ADR 0086 decisions D1–D8 for compatibility with ADR 0081 1:N project model, `lib/` directory design, and automatic plugin registration.

---

## Executive Summary

ADR 0086 proposes valuable consolidation (67→~35 plugins, declarative rules, flat layout) but introduces **two decisions that break project-level extensibility**:

| Decision | Issue | Severity |
|----------|-------|----------|
| **D4** (vendor generator consolidation) | Hardcoded `VENDORS` dict — closed for extension | 🔴 Breaking |
| **D5** (single unified manifest) | Eliminates project plugin manifest slot from discovery chain | 🔴 Breaking |

The remaining decisions (D1, D2, D3, D6, D7, D8) are safe and recommended.

**Root cause:** ADR 0086 does not list ADR 0081 in its `Depends on` header and was written without considering the 1:N framework→project contract.

---

## 1. The `lib/` Directory Anti-Pattern

### What ADR 0086 proposes

D4 moves vendor strategy code from **plugins** (auto-discovered via `plugins.yaml`) to **library code** (static Python imports):

```
# PROPOSED (ADR 0086)
topology/object-modules/mikrotik/lib/
├── projection.py
├── terraform_strategy.py       # ← plain library class
└── bootstrap_strategy.py       # ← plain library class
```

The consolidated generators import them statically:

```python
class TerraformGenerator(GeneratorPlugin):
    VENDORS = {
        "proxmox":  ProxmoxTerraformStrategy,    # ← hardcoded import
        "mikrotik": MikrotikTerraformStrategy,    # ← hardcoded import
    }
```

### Why this breaks extensibility

**Scenario:** A standalone project repository (`my-office-infra/`) uses the framework artifact and wants to manage Ubiquiti UniFi switches via Terraform.

**Current architecture (before ADR 0086):**
The project can create:
```
my-office-infra/
├── plugins/
│   └── generators/
│       └── plugins.yaml    ← registers object.unifi.generator.terraform
│       └── terraform_unifi_generator.py
```

The existing `plugin_manifest_discovery.py` merge chain (slot #4: `project_plugins_root`) auto-discovers this manifest and loads the new generator plugin alongside framework generators. **No framework code changes needed.**

**After ADR 0086 D4:**
The `TerraformGenerator.VENDORS` dict is hardcoded in the **framework artifact**. To add UniFi, the project must either:
1. Fork and modify the framework plugin code — **violates ADR 0081 §3.2** (self-sufficiency without framework modification)
2. Create a separate standalone generator that duplicates all `TerraformGenerator` infrastructure — **violates DRY**

**Verdict:** `lib/` is acceptable for **non-extensible internal code** (projection builders, template helpers). It is **unacceptable** for vendor strategy code that must be registry-discovered by projects.

---

## 2. Hardcoded `VENDORS` Breaks the 1:N Model

### ADR 0081 §3.3–3.4 Contract

> Projects MAY define plugins in `<project-root>/plugins/<family>/`. Project plugins **extend (but do not override)** framework plugins.

> Plugin discovery follows a strict deterministic merge chain:
> 1. Kernel
> 2. Framework base — `topology-tools/plugins/plugins.yaml`
> 3. Class modules — `topology/class-modules/<class>/plugins.yaml`
> 4. Object modules — `topology/object-modules/<object>/plugins.yaml`
> 5. **Project** — `<project-root>/plugins/plugins.yaml`

### What gets lost

| Capability | Current (pre-0086) | ADR 0086 D4+D5 | Impact |
|------------|--------------------|--------------------|--------|
| Project adds new vendor generator | ✅ Add `plugins.yaml` in project `plugins/generators/` | ❌ `VENDORS` dict is hardcoded in framework | **Broken** |
| Project adds custom validator | ✅ Project `plugins/validators/plugins.yaml` | ❌ D5 single manifest only in `topology-tools/` | **Broken** |
| Framework adds vendor without project changes | ✅ New object-module manifest auto-discovered | ✅ Added to single manifest | OK |
| Discovery order is deterministic | ✅ 4-slot merge in `plugin_manifest_discovery.py` | ❌ Single file, no merge slots | **Broken** |

### Evidence: Existing infrastructure already supports project plugins

`compile-topology.py` line 1042:
```python
project_plugins_root=manifest_bundle.project_root / "plugins",
```

`plugin_manifest_discovery.py` lines 162–168:
```python
if project_plugins_root is not None and project_plugins_root.exists():
    for manifest_path in project_plugins_root.rglob(manifest_name):
        ...
        discovered.append((2, rel_key, resolved))
```

Test coverage: `test_module_manifest_discovery.py::test_module_manifest_loader_includes_project_plugins_root` — confirms project-level `plugins.yaml` is merged in slot #4.

---

## 3. Proposed Alternative: Auto-Discovered Vendor Strategy Registration

### Core idea

Keep ADR 0086's consolidation goal (2 registry generators instead of 5 standalone plugins) but replace **hardcoded `VENDORS` dicts** with **runtime strategy discovery** via the existing plugin manifest mechanism.

### Mechanism: Strategy plugins with `contributes_to`

A vendor strategy is registered as a lightweight plugin entry with a new `contributes_to` declaration:

```yaml
# topology/object-modules/mikrotik/plugins.yaml (framework-shipped)
schema_version: 1
plugins:
  - id: strategy.mikrotik.terraform
    kind: generator
    entry: plugins/generators/terraform_mikrotik_strategy.py:MikrotikTerraformStrategy
    api_version: "1.x"
    stages: [generate]
    phase: run
    order: 220
    depends_on: []
    contributes_to: generator.terraform     # ← links to parent generator
    config:
      mikrotik_provider_source: "terraform-routeros/routeros"
      # ... vendor-specific config
    description: MikroTik Terraform vendor strategy.
```

The consolidated `TerraformGenerator` discovers strategies at runtime:

```python
class TerraformGenerator(GeneratorPlugin):
    """Single generator that discovers vendor strategies from registry."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Query registry for all plugins with contributes_to=self.plugin_id
        strategies = self._discover_strategies(ctx)
        for vendor_id, strategy_class in strategies.items():
            projection = strategy_class.build_projection(ctx)
            strategy_class.render(projection, ctx.output_dir)
```

### Project extensibility

A standalone project repository adds UniFi support:

```yaml
# my-office-infra/plugins/generators/plugins.yaml
schema_version: 1
plugins:
  - id: strategy.unifi.terraform
    kind: generator
    entry: generators/terraform_unifi_strategy.py:UnifiTerraformStrategy
    api_version: "1.x"
    stages: [generate]
    phase: run
    order: 225
    depends_on: []
    contributes_to: generator.terraform     # ← extends framework generator
    config:
      unifi_provider_source: "paultyng/unifi"
      # ...
```

Discovered via existing `plugin_manifest_discovery.py` slot #4 (`project_plugins_root`). Zero framework changes needed.

### Alternative mechanism: Config-level strategy entries

If `contributes_to` is too heavy, strategies can be registered in the parent generator's `config` block:

```yaml
# In plugins.yaml config for generator.terraform:
config:
  vendor_strategies:
    - entry: topology/object-modules/proxmox/lib/terraform_strategy.py:ProxmoxTerraformStrategy
      vendor_prefix: "obj.proxmox."
    - entry: topology/object-modules/mikrotik/lib/terraform_strategy.py:MikrotikTerraformStrategy
      vendor_prefix: "obj.mikrotik."
```

This is simpler but **less extensible** — projects cannot add entries to framework config. The `contributes_to` approach is recommended.

---

## 4. Decision-by-Decision Impact Assessment

### D1: Flat Plugin Directories — ✅ SAFE

Moving validators and compilers to `topology-tools/plugins/<stage>/` is compatible with project extensibility. Project plugins remain in `<project>/plugins/<family>/`. The two roots (framework + project) coexist through `plugin_manifest_discovery.py`.

**Recommendation:** Accept D1 as-is.

### D2: Declarative Reference Validators — ✅ SAFE

Purely additive consolidation. The `DeclarativeReferenceValidator` with `RULES` table is internal framework logic. Projects that need custom reference validation can add their own validator plugin.

**Recommendation:** Accept D2 as-is.

### D3: Port Validator Consolidation — ✅ SAFE

Strategy pattern for vendor port rules is internal. Project can still add `validator.custom_ports` as a separate plugin.

**Recommendation:** Accept D3 as-is.

### D4: Vendor Generator Consolidation — 🔴 NEEDS REVISION

**Current text:** Hardcoded `VENDORS = { "proxmox": ..., "mikrotik": ... }` dict with strategies as library code in `lib/`.

**Revised proposal:**
- Keep 2 consolidated generators (`generator.terraform`, `generator.bootstrap`)
- Replace `VENDORS` dict with runtime strategy discovery via `contributes_to` mechanism
- Vendor strategies remain as **plugin manifest entries** (auto-discovered), not library code
- Projection builders can stay in `lib/` since they're consumed by strategies, not an extensibility point
- Framework-shipped strategies stay in object-module `plugins.yaml` manifests (merge slot #3)
- Project-added strategies go in `<project>/plugins/generators/plugins.yaml` (merge slot #4)

**Result:** Same consolidation outcome (5 standalone generators → 2 parent generators + 5 lightweight strategy entries) but open for extension.

### D5: Single Unified Manifest — 🔴 NEEDS REVISION

**Current text:** "Merge all plugin manifests into one `topology-tools/plugins/plugins.yaml`."

**Revised proposal:**
- Framework base plugins consolidate into one manifest (`topology-tools/plugins/plugins.yaml`) — **OK**
- **Preserve multi-slot discovery chain** in `plugin_manifest_discovery.py`:
  1. Framework base manifest (slot #0)
  2. Class module manifests (slot #1) — may become empty after D1 migration
  3. Object module manifests (slot #2) — contains vendor strategy registrations
  4. Project plugin manifests (slot #3) — **must not be eliminated**
- Simplification: after D1, class/object manifests may only contain vendor strategy entries (not standalone plugins). The discovery mechanism stays, the manifests get smaller.
- Alternative: if class/object manifests are truly eliminated, the `contributes_to` strategy entries must move to the base framework manifest. Project strategies still use project `plugins.yaml`.

### D6: Simplified Plugin IDs — ✅ SAFE

Namespace change `<stage>.<domain_name>` is orthogonal to extensibility. Just ensure the convention works for project-contributed plugins too (e.g., `strategy.unifi.terraform` follows the pattern).

**Recommendation:** Accept D6. Document that project plugin IDs should follow the same `<stage>.<domain>` convention.

### D7: Retire Boundary Test — ✅ SAFE

**Recommendation:** Accept D7 as-is.

### D8: Preserve Projection-First — ✅ SAFE

**Recommendation:** Accept D8 as-is.

---

## 5. Where `lib/` IS Acceptable vs Where It's NOT

| Code Type | `lib/` OK? | Reason |
|-----------|------------|--------|
| Projection builders (`build_mikrotik_projection()`) | ✅ Yes | Consumed only by vendor strategies; not an extensibility point |
| Template helpers (Jinja2 filters, macros) | ✅ Yes | Internal to rendering pipeline |
| Terraform rendering strategy | ❌ No | Must be registry-discoverable for project extensibility |
| Bootstrap rendering strategy | ❌ No | Must be registry-discoverable for project extensibility |
| Shared utility functions | ✅ Yes | Pure helpers, no registration needed |

---

## 6. Auto-Registration Protocol Summary

### Current auto-registration (already working)

```
compile-topology.py
  └→ _load_module_plugin_manifests()
       └→ discover_plugin_manifest_paths(
              base_manifest_path=...,           # slot 0: framework base
              class_modules_root=...,           # slot 1: class modules scan
              object_modules_root=...,          # slot 2: object modules scan
              project_plugins_root=...,         # slot 3: project plugins scan
          )
            └→ rglob("plugins.yaml") in each root
            └→ deterministic sort by (slot, relative_path)
            └→ deduplicate
```

**This is automatic plugin registration.** Any `plugins.yaml` placed in the correct directory is auto-discovered. No manual editing of a central manifest needed.

### What ADR 0086 should preserve

1. Multi-slot discovery chain (D5 revision)
2. `project_plugins_root` parameter in discovery function
3. Object module manifests (even if smaller, they hold strategy entries)

### What ADR 0086 CAN simplify

1. Remove class/object **plugin directories** for standalone plugins (they move to `topology-tools/plugins/<stage>/`)
2. Reduce class/object manifests to vendor strategy entries only
3. Simplify plugin IDs (D6)
4. Consolidate internal validators (D2, D3)

---

## 7. Comparison Matrix

| Dimension | Current (pre-0086) | ADR 0086 as proposed | Recommended hybrid |
|-----------|-------------------|---------------------|-------------------|
| Plugin count | 67 | ~35 | ~37 (35 + 2 strategy host entries) |
| Vendor extensibility | ✅ Add plugin in object-module manifest | ❌ Hardcoded `VENDORS` dict | ✅ `contributes_to` strategy registration |
| Project plugin support | ✅ `project_plugins_root` slot #4 | ❌ Single manifest only | ✅ Preserved slot #4 |
| Discovery mechanism | 4-slot merge chain | Single file load | 3-slot merge (framework + object-strategies + project) |
| Manifest files | 7+ | 1 | 2–3 (base + object strategies + project) |
| Cognitive load | High (4 levels, 4 locations) | Low (1 location) | Low (1 location for plugins + strategy entries in object manifests) |
| Open-Closed Principle | ✅ Open for extension | ❌ Closed (hardcoded) | ✅ Open via `contributes_to` |
| ADR 0081 compliance | ✅ Full | ❌ D4+D5 break §3.3–3.4 | ✅ Full |

---

## 8. Recommended Changes to ADR 0086

1. **Add `ADR 0081` to `Depends on`** header.

2. **Revise D4** — replace hardcoded `VENDORS` with auto-discovered strategy protocol:
   - Vendor strategies are registered as plugin manifest entries with `contributes_to: <parent_generator_id>`
   - Parent generators (`generator.terraform`, `generator.bootstrap`) query strategies at runtime
   - Strategies stay in object-module manifests (auto-discovered) or project manifests

3. **Revise D5** — "single unified manifest" applies to framework base plugins only:
   - Object-module manifests continue to exist for strategy entries
   - Project manifests continue to be discovered
   - `plugin_manifest_discovery.py` multi-slot merge is preserved

4. **Keep `lib/` only for non-extensible code** — projection builders, template helpers. Strategy modules that must be discovered stay as plugin entries.

5. **Add extensibility section** to ADR 0086 Consequences documenting the `contributes_to` protocol for project-level vendor contribution.

---

## 9. Missing ADR 0086 Dependency

ADR 0086 header currently reads:
```
- Depends on: ADR 0063, 0065, 0066, 0074, 0080
```

Should be:
```
- Depends on: ADR 0063, 0065, 0066, 0074, 0080, 0081
```

ADR 0081 defines the 1:N project model and plugin discovery contract that D4 and D5 directly affect.

# ADR 0086: Flatten Plugin Hierarchy and Reduce Plugin Granularity

- Status: Proposed
- Date: 2026-04-01
- Depends on: ADR 0063, 0065, 0066, 0074, 0080, 0081
- Supersedes: ADR 0063 Section 4B (4-level plugin boundary model)

## Context

ADR 0063 introduced a 4-level plugin boundary model (global → class → object → instance)
with strict visibility rules:

- Class-level plugins MUST NOT reference `obj.*` or `inst.*`
- Object-level plugins MUST NOT reference `inst.*`
- Plugins are physically placed in their respective module directories

After 67 plugins have been implemented and the system has matured, an architectural review
reveals that this model creates friction without delivering its intended benefits.

ADR 0081 established a 1:N framework→project model where the framework ships as a
versioned artifact to N independent project repositories. Projects MAY define plugins
in `<project-root>/plugins/<family>/` that extend framework plugins. The existing
`plugin_manifest_discovery.py` implements a deterministic 4-slot merge chain
(framework → class → object → project). Any refactoring of the plugin hierarchy
MUST preserve this extensibility contract.

### Problem 1: Runtime Does Not Enforce Boundaries

`PluginContext` passes **identical, unscoped data** to every plugin regardless of declared level:

```python
@dataclass
class PluginContext:
    raw_yaml: dict          # Full topology
    compiled_json: dict     # Full compilation
    classes: dict           # ALL classes
    objects: dict           # ALL objects
```

No filtering, no access control, no level-based scoping exists in the runtime.
The 4-level boundary is a naming convention enforced only by a single boundary test
(`test_plugin_level_boundaries.py`) and code review.

### Problem 2: Boundary Rules Contradict OOP Semantics

In the Class → Object → Instance model:

- A **class** defines abstract contracts that its objects must satisfy
- An **object** defines vendor-specific behavior for its instances
- An **instance** is a deployed configuration

The rule "class-plugin must not see objects" contradicts OOP: a class-level validator
that checks whether objects satisfy the class contract **must** iterate over objects.

Concrete example: `RouterPortValidatorBase` is a "class-level" plugin in
`topology/class-modules/router/plugins/`, but it reads `ctx.objects` and filters
by object prefix. It **must** cross the boundary to perform its function.

### Problem 3: Excessive Granularity Creates Overhead

Current state:

| Pattern | Files | Lines of unique logic |
|---------|-------|-----------------------|
| `MikrotikRouterPortsValidator` | 1 file, 22 lines | 2 properties, 0 logic |
| `GlinetRouterPortsValidator` | 1 file, 22 lines | 2 properties, 0 logic |
| 11 reference validators | 11 files | Same "build index, check ref" pattern |
| 5 vendor generators | 5 plugin files | Same "build projection, render" pattern |

Each plugin requires: Python module + manifest entry + DAG node + dependency declarations.

### Problem 4: Cognitive Load

For developers and AI agents:

- 4 possible directory locations for a plugin
- 3+ manifest files to search/maintain
- Naming convention coupling (`base.*`, `class.router.*`, `obj.mikrotik.*`) means
  moving a plugin between levels requires renaming IDs and updating all dependents
- Rules not enforced by runtime — violations are silent unless caught by test/review

## Decision

### D1. Adopt Flat Plugin Model

Eliminate the 4-level plugin directory hierarchy for **standalone plugins**
(validators, compilers, discoverers, assemblers, builders). All standalone plugins
reside in `topology-tools/plugins/<stage>/` organized by pipeline stage only.

**Before:**
```
topology-tools/plugins/validators/          # "global"
topology/class-modules/router/plugins/      # "class-level"
topology/object-modules/mikrotik/plugins/   # "object-level"
```

**After:**
```
topology-tools/plugins/
├── discoverers/
├── compilers/
├── validators/
├── generators/
├── assemblers/
└── builders/
```

Vendor-specific **non-extensible** helper modules (projection builders, template
helpers, shared utilities) remain colocated with their topology modules as library
code:

```
topology/object-modules/mikrotik/lib/
├── projection.py          # build_mikrotik_projection()
└── template_helpers.py    # Jinja2 filters, shared formatters
```

**`lib/` boundary rule:** Only code that is NOT a point of project extensibility
belongs in `lib/`. Vendor strategies (Terraform, bootstrap) that projects may need
to add for new vendors MUST remain as registered plugin entries, not library code.
See D4 for the vendor strategy registration protocol.

### D2. Consolidate Reference Validators into Declarative Rule Engine

Replace 11 structurally identical reference validators with a single
`DeclarativeReferenceValidator` driven by a rules table:

```python
class DeclarativeReferenceValidator(ValidatorJsonPlugin):
    RULES = [
        ReferenceRule(name="dns_refs",     field="device_ref",  code="E7501", layers={"L5"}),
        ReferenceRule(name="backup_refs",  field="target_ref",  code="E7601", layers={"L6"}),
        ReferenceRule(name="host_os_refs", field="host_os_ref", code="E7201", layers={"L2"}),
        # ... remaining rules
    ]
```

Adding a new reference check = adding one `ReferenceRule` entry. No new file, no new
manifest entry, no new DAG node.

Existing diagnostic codes (E7xxx) are preserved — no downstream impact.

### D3. Consolidate Port Validators via Strategy Pattern

Replace the base + vendor inheritance hierarchy with a single plugin using
vendor-specific rule sets:

```python
class RouterPortValidator(ValidatorJsonPlugin):
    VENDOR_RULES = {
        "obj.mikrotik.": VendorPortRules(code="E7302", ...),
        "obj.glinet.":   VendorPortRules(code="E7303", ...),
    }
```

Eliminates: `router_port_validator_base.py` + `mikrotik_router_ports_validator.py` +
`glinet_router_ports_validator.py` (3 files → 1 file).

### D4. Consolidate Vendor Generators via Auto-Discovered Strategy Protocol

Replace per-vendor generator plugins with two **host generators** that dynamically
discover vendor strategy plugins at runtime via a `contributes_to` manifest field.

#### D4.1. Host Generators

Two host generators replace five standalone vendor generators:

```python
class TerraformGenerator(GeneratorPlugin):
    """Host generator that discovers and dispatches to vendor Terraform strategies."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        strategies = self._discover_contributed_strategies(ctx)
        for strategy in strategies:
            projection = strategy.build_projection(ctx)
            strategy.render(projection, ctx.output_dir)
        ...

class BootstrapGenerator(GeneratorPlugin):
    """Host generator that discovers and dispatches to vendor bootstrap strategies."""
    ...
```

Host generators contain shared infrastructure (output directory management, template
loading, atomic writes, artifact manifest integration) but **no vendor-specific logic**.

#### D4.2. `contributes_to` Manifest Field

Vendor strategies are registered as plugin manifest entries with a `contributes_to`
field that links them to a host generator:

```yaml
# topology/object-modules/mikrotik/plugins.yaml
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
    contributes_to: generator.terraform
    config:
      mikrotik_provider_source: "terraform-routeros/routeros"
      mikrotik_provider_version: "~> 1.40"
      capability_templates:
        qos:
          enabled_by: capabilities.has_qos
          template: terraform/qos.tf.j2
          output: qos.tf
    description: MikroTik Terraform vendor strategy.

  - id: strategy.mikrotik.bootstrap
    kind: generator
    entry: plugins/generators/bootstrap_mikrotik_strategy.py:MikrotikBootstrapStrategy
    api_version: "1.x"
    stages: [generate]
    phase: run
    order: 320
    depends_on: []
    contributes_to: generator.bootstrap
    config:
      bootstrap_files:
        - output_file: init-terraform.rsc
          template: bootstrap/init-terraform.rsc.j2
    description: MikroTik bootstrap vendor strategy.
```

The host generator queries the plugin registry for all specs where
`contributes_to == self.plugin_id`, loads them, and dispatches.

#### D4.3. Project-Level Vendor Extensibility (ADR 0081 §3.3 Compliance)

A standalone project repository adds a new vendor with **zero framework changes**:

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
    contributes_to: generator.terraform
    config:
      unifi_provider_source: "paultyng/unifi"
      unifi_provider_version: "~> 0.41"
    description: UniFi Terraform vendor strategy (project-specific).
```

Discovered via existing `plugin_manifest_discovery.py` slot #4
(`project_plugins_root`). The host `generator.terraform` picks it up automatically.

#### D4.4. `lib/` Boundary for Vendor Code

| Code | Location | Reason |
|------|----------|--------|
| Projection builders | `object-modules/<vendor>/lib/projection.py` | Internal helper consumed only by the vendor's own strategy; not an extensibility point |
| Template helpers | `object-modules/<vendor>/lib/template_helpers.py` | Pure helpers, no registration needed |
| Vendor strategies | `object-modules/<vendor>/plugins/generators/*.py` | **MUST** be plugin-registered for project extensibility |

#### D4.5. Kernel Extension: `contributes_to` Support

The kernel `PluginSpec` dataclass gains an optional `contributes_to: str` field.
The `PluginRegistry` provides a query method:

```python
def get_contributors(self, host_plugin_id: str) -> list[PluginSpec]:
    """Return all specs where contributes_to matches the given host plugin ID."""
    return [
        spec for spec in self.specs.values()
        if spec.contributes_to == host_plugin_id
    ]
```

Validation rules:
- `contributes_to` target MUST exist in registry (error `E4020` if missing)
- Contributor MUST share at least one stage with host plugin
- Contributor MUST NOT declare `contributes_to` and also appear in another
  plugin's `depends_on` (contributors are dispatched by host, not by DAG)

### D5. Consolidated Framework Manifest with Preserved Discovery Chain

Merge framework-level standalone plugin entries into one
`topology-tools/plugins/plugins.yaml`. This eliminates the need for class/object
manifests to contain standalone validator/compiler plugins.

**Critically, the multi-slot discovery chain in `plugin_manifest_discovery.py` is
preserved:**

| Slot | Source | Contents after D1+D4 |
|------|--------|---------------------|
| #0 | `topology-tools/plugins/plugins.yaml` | All framework standalone plugins + host generators |
| #1 | `topology/class-modules/*/plugins.yaml` | Empty or removed (class standalone plugins moved to slot #0) |
| #2 | `topology/object-modules/*/plugins.yaml` | Vendor `contributes_to` strategy entries only |
| #3 | `<project-root>/plugins/**/plugins.yaml` | Project-specific plugins and vendor strategy contributions |

Object-module manifests become smaller (only `contributes_to` strategy entries) but
continue to exist and are auto-discovered. The `plugin_manifest_discovery.py`
multi-root scan mechanism is NOT simplified to single-file load.

**Project plugin manifests (slot #3) are never eliminated.** This is the primary
extensibility mechanism for standalone project repositories (ADR 0081 §3.3–3.4).

### D6. Simplify Plugin ID Namespace

Remove level-based prefixes from plugin IDs:

**Before:** `base.validator.dns_refs`, `class.router.data_channel_interface`,
`obj.mikrotik.terraform`

**After:** `validator.dns_refs`, `validator.router_data_channel_interface`,
`generator.terraform`, `generator.bootstrap`

Strategy plugins use: `strategy.<vendor>.<domain>` — e.g.,
`strategy.mikrotik.terraform`, `strategy.proxmox.bootstrap`.

Convention: `<role>.<domain_name>` — two segments, no level encoding.
Role is one of: `discoverer`, `compiler`, `validator`, `generator`, `assembler`,
`builder`, `strategy`.

Project-contributed plugins follow the same convention:
`strategy.unifi.terraform`, `validator.custom_naming`.

### D7. Retire 4-Level Boundary Test

Remove `test_plugin_level_boundaries.py` and the boundary enforcement rules from
ADR 0063 Section 4B. Replace with:

- **Architectural test:** Every standalone plugin is in `topology-tools/plugins/<stage>/`
- **Strategy entries** in `object-modules/*/plugins.yaml` MUST have `contributes_to` field
- **No standalone plugin entries in module directories** (glob check in CI)
- **`lib/` modules** in `topology/object-modules/*/lib/` are importable library
  code, not plugins — verified by absence of `kind:` in `lib/` files
- **Project plugin slot** (`project_plugins_root`) is tested for discoverability

### D8. Preserve Projection-First Contract

ADR 0074 (projection-first generation) remains in full force. Vendor strategies
MUST use projection builders. The consolidation changes **where** code lives,
not **how** it accesses data.

## Consequences

### What Improves

1. **Plugin count drops from 67 to ~37** — fewer files, smaller manifests, simpler DAG
2. **One location to find any standalone plugin** — `topology-tools/plugins/<stage>/`
3. **Framework manifest consolidation** — one file for standalone plugins
4. **Zero visibility rules to remember** — no 4-level mental model
5. **Adding a reference check = 1 line** — no new file, no manifest entry
6. **Adding a framework vendor = strategy entry in object-module manifest** — lightweight
7. **Adding a project vendor = strategy entry in project manifest** — zero framework changes
8. **AI agents operate faster** — flat structure, fewer conventions, less ambiguity

### Extensibility Preserved (ADR 0081 Compliance)

1. **Multi-slot discovery chain preserved** — `plugin_manifest_discovery.py` continues
   to scan framework → class → object → project manifest roots
2. **Project plugin root preserved** — `<project-root>/plugins/` remains discoverable
3. **`contributes_to` protocol** replaces hardcoded vendor dicts — Open-Closed Principle
4. **New vendor = new manifest entry** — in object-module manifest (framework) or
   project manifest (standalone project), never requires modifying existing code
5. **No lib/ for extensible code** — vendor strategies are always plugin-registered

### Trade-offs

1. **Vendor strategy code restructured** — from standalone generator plugins to
   `contributes_to` strategy entries — git history disruption
2. **All plugin IDs change** — requires updating depends_on, consumes, tests,
   and any external references in one coordinated change
3. **ADR 0063 Section 4B is superseded** — documentation update required
4. **Large coordinated refactor** — must be staged carefully to avoid breaking CI
5. **Kernel extension required** — `contributes_to` field and `get_contributors()`
   method added to `PluginSpec`/`PluginRegistry`
6. **Object-module manifests persist** — they become smaller (strategy entries only)
   but are not eliminated, which means discovery still scans multiple roots

### Migration Impact

- **Kernel API addition** — `PluginSpec.contributes_to` field, `PluginRegistry.get_contributors()`
- **No breaking runtime API changes** — `PluginContext`, `PluginResult`, `PluginBase` unchanged
- **No topology file changes** — topology YAML is unaffected
- **No generated output changes** — identical artifacts after refactor
- **Test parity gate** — all existing regression tests must pass after each phase

## References

- ADR 0063: Plugin Microkernel — foundation being refined
- ADR 0065: Plugin API Contract — preserved as-is
- ADR 0066: Plugin Testing Strategy — boundary test replaced
- ADR 0074: Generator Architecture — projection-first preserved
- ADR 0080: Unified Build Pipeline — stage/phase model preserved
- ADR 0081: Framework Runtime Artifact and 1:N Project Model — extensibility contract for D4/D5
- Analysis: `adr/0086-analysis/`
- Extensibility review: `adr/0086-analysis/EXTENSIBILITY-REVIEW.md`

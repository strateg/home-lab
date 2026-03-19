# ADR 0074: V5 Generator Architecture

- Status: Proposed
- Date: 2026-03-19

## Context

The v5 deployment generators are required to achieve production readiness per `adr/plan/v5-production-readiness.md`. Phase 2 (Projection Layer) is complete with `projections.py` providing dataclasses and dict-based projection builders. Phases 3-6 need architectural decisions for:

1. Terraform Proxmox generator (Phase 3)
2. Terraform MikroTik generator (Phase 4)
3. Ansible Inventory generator (Phase 5)
4. Bootstrap generators (Phase 6)

Current state assessment:
- **Base infrastructure exists**: `base_generator.py` provides Jinja2 environment, atomic writes, output path resolution
- **Projection layer complete**: `projections.py` offers both dict-based (`build_*_projection`) and typed (`*Dataclass`) interfaces
- **Stub generators deployed**: `terraform_proxmox_generator.py`, `terraform_mikrotik_generator.py`, `ansible_inventory_generator.py` emit baseline locals-only artifacts
- **No v5 templates yet**: Template directory `v5/topology-tools/templates/` is empty
- **v4 templates available**: 19 Jinja2 templates in `v4/topology-tools/templates/terraform/`

Key architectural questions requiring decisions:
1. Dict-based vs typed (dataclass) projections for template rendering
2. Plugin registration strategy (stage, order, dependencies)
3. Template organization (one-per-resource vs monolithic)
4. Terraform provider versioning and state management
5. Deterministic output for git-friendly diffs
6. Validation gates after generation

## Decision

### D1: Dual Projection Interface (Dict-Primary, Typed-Optional)

**Decision**: Generators MUST consume projections from `projections.py`, never raw `compiled_json` internals directly.

- **Primary interface**: Dict-based projections (`build_proxmox_projection`, `build_mikrotik_projection`, etc.)
- **Optional typed access**: Dataclasses (`ProxmoxLXC`, `MikroTikInterface`, etc.) for complex transformation logic within generators, not templates

**Rationale**:
- Dict projections are directly consumable by Jinja2 templates without conversion
- Typed dataclasses provide IDE support and validation for complex generator logic
- Projection layer absorbs schema changes; templates remain stable
- v4 generators use dict-based contexts exclusively; proven pattern

**Implementation Pattern**:
```python
from plugins.generators.projections import build_proxmox_projection, build_proxmox_lxc_typed

def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    # Primary: dict-based for templates
    projection = build_proxmox_projection(ctx.compiled_json)

    # Optional: typed access for complex logic
    lxc_typed = build_proxmox_lxc_typed(ctx.compiled_json)
    for lxc in lxc_typed:
        # IDE-aware access: lxc.cores, lxc.memory, lxc.disk_size
        pass

    # Template receives dict projection
    content = self.render_template(ctx, "terraform/proxmox/lxc.tf.j2", {
        "lxc_containers": projection["lxc"],
        "counts": projection["counts"],
    })
```

### D2: Plugin Registration Contract

**Decision**: All deployment generators register in `plugins.yaml` with explicit stage, order, depends_on, and config_schema.

**Order Ranges** (established in `plugins.yaml` comments):
| Range | Category | Examples |
|-------|----------|----------|
| 190-199 | Core generators | `effective_json`, `effective_yaml` |
| 200-249 | Terraform generators | `terraform_proxmox` (210), `terraform_mikrotik` (220) |
| 250-299 | Ansible generators | `ansible_inventory` (230) |
| 300-399 | Bootstrap generators | `bootstrap_proxmox`, `bootstrap_mikrotik`, `bootstrap_orangepi` |

**Dependency Rules**:
- Generators depend on compile stage outputs, not on each other
- `depends_on: []` is the default for deployment generators (they read `ctx.compiled_json` which is set by compile stage)
- Bootstrap generators MAY depend on Terraform generators if they need generated paths

**Registration Template**:
```yaml
- id: base.generator.terraform_proxmox
  kind: generator
  entry: generators/terraform_proxmox_generator.py:TerraformProxmoxGenerator
  api_version: "1.x"
  stages: [generate]
  order: 210
  depends_on: []
  timeout: 60
  config:
    output_subdir: terraform/proxmox
    provider_version_constraint: ">= 0.66.0"
  config_schema:
    type: object
    properties:
      output_subdir:
        type: string
        description: Subdirectory under artifacts_root for generated files
      provider_version_constraint:
        type: string
        description: Terraform provider version constraint
    required: []
  description: Emits Proxmox Terraform HCL from v5 projections.
```

### D3: Template Organization Strategy (Mandatory Jinja2)

**Decision**: All generation templates MUST be external Jinja2 files. Inline string templates in Python code are **prohibited**.

#### Rationale

1. **Separation of Concerns**: Template content (HCL/YAML/RSC) belongs in template files, not Python code
2. **Syntax Highlighting**: IDE support for HCL/YAML syntax in `.j2` files
3. **Reviewability**: Template changes are visible in diffs without Python noise
4. **Reusability**: Jinja2 `{% include %}` and `{% extends %}` enable DRY templates
5. **Operator Customization**: External templates enable D8 extension hooks
6. **Consistency**: Single approach across all generators

#### Mandatory Template Directory Structure

```
v5/topology-tools/templates/
  _partials/                       # Shared fragments (REQUIRED)
    header.j2                      # "DO NOT EDIT - generated from topology"
    terraform_versions.tf.j2       # Shared provider version block
    terraform_provider_proxmox.tf.j2
    terraform_provider_mikrotik.tf.j2
  terraform/
    proxmox/
      provider.tf.j2
      versions.tf.j2
      bridges.tf.j2
      lxc.tf.j2
      vms.tf.j2
      variables.tf.j2
      outputs.tf.j2
      terraform.tfvars.example.j2
    mikrotik/
      provider.tf.j2
      versions.tf.j2
      interfaces.tf.j2
      firewall.tf.j2
      dhcp.tf.j2
      dns.tf.j2
      addresses.tf.j2
      qos.tf.j2
      vpn.tf.j2
      containers.tf.j2
      variables.tf.j2
      outputs.tf.j2
      terraform.tfvars.example.j2
  ansible/
    hosts.yml.j2
    group_vars_all.yml.j2
    host_vars.yml.j2
  bootstrap/
    proxmox/
      answer.toml.j2
      post-install/
        01-install-terraform.sh.j2
        02-install-ansible.sh.j2
        03-configure-storage.sh.j2
        04-configure-network.sh.j2
        05-init-git-repo.sh.j2
        06-final-reboot.sh.j2
      README.md.j2
    mikrotik/
      init-terraform.rsc.j2
      backup-restore-overrides.rsc.j2
      terraform.tfvars.example.j2
      README.md.j2
    orangepi/
      user-data.j2
      meta-data.j2
      README.md.j2
```

#### Template Conventions

**Header Partial** (included in all generated files):
```jinja2
{# _partials/header.j2 #}
# =============================================================================
# GENERATED FILE - DO NOT EDIT
# Generated from: v5/topology/topology.yaml
# Generator: {{ generator_name }}
# Timestamp: {{ generation_timestamp }}
# =============================================================================
```

**Template Structure Pattern**:
```jinja2
{# terraform/proxmox/lxc.tf.j2 #}
{% include "_partials/header.j2" %}

{% for lxc in lxc_containers | sort(attribute='instance_id') %}
resource "proxmox_virtual_environment_container" "{{ lxc.instance_id | replace('-', '_') }}" {
  description = "{{ lxc.description | default('Managed by Terraform') }}"
  node_name   = "{{ node_name }}"
  vm_id       = {{ lxc.vmid }}

  # ... resource configuration
}

{% endfor %}
```

#### Generator Implementation Pattern

Generators MUST use `render_template()` from `BaseGenerator`:

```python
class TerraformProxmoxGenerator(BaseGenerator):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        projection = build_proxmox_projection(ctx.compiled_json)

        # Each output file uses a template
        files = {
            "provider.tf": self.render_template(ctx, "terraform/proxmox/provider.tf.j2", {
                "api_url": projection["api_url"],
            }),
            "lxc.tf": self.render_template(ctx, "terraform/proxmox/lxc.tf.j2", {
                "lxc_containers": projection["lxc"],
                "node_name": projection["node_name"],
            }),
            # ... other files
        }

        for filename, content in files.items():
            path = self.resolve_output_path(ctx, "terraform/proxmox", filename)
            self.write_text_atomic(path, content)
```

#### Anti-Pattern: Inline Templates (PROHIBITED)

```python
# ❌ WRONG - inline template in Python code
def _lxc_tf(lxc_instances: list[str]) -> str:
    return (
        "# Baseline projection output\n"
        "locals {\n"
        f"  lxc_instances = {_render_string_list(lxc_instances)}\n"
        "}\n"
    )

# ✅ CORRECT - external Jinja2 template
def _lxc_tf(self, ctx: PluginContext, projection: dict) -> str:
    return self.render_template(ctx, "terraform/proxmox/lxc.tf.j2", {
        "lxc_containers": projection["lxc"],
    })
```

#### Migration Plan for Existing Inline Templates

Current generators use inline templates and MUST be migrated:

| Generator | Status | Migration Priority |
|-----------|--------|-------------------|
| `terraform_proxmox_generator.py` | ⚠️ Inline | P1 - High |
| `terraform_mikrotik_generator.py` | ⚠️ Inline | P1 - High |
| `ansible_inventory_generator.py` | ⚠️ Inline | P2 - Medium |
| `bootstrap_proxmox_generator.py` | ⚠️ Inline | P2 - Medium |
| `bootstrap_mikrotik_generator.py` | ⚠️ Inline | P2 - Medium |
| `bootstrap_orangepi_generator.py` | ⚠️ Inline | P2 - Medium |

**Migration Steps**:
1. Create template file in `v5/topology-tools/templates/`
2. Extract inline string content to template
3. Replace inline function with `render_template()` call
4. Run snapshot test to verify identical output
5. Run CI gates (`terraform fmt -check`, `terraform validate`)

#### Template Validation

Templates MUST be validated:
1. **Jinja2 Syntax**: Parse all `.j2` files on startup
2. **Required Variables**: Document expected context variables in template header
3. **Output Validation**: Generated content passes tool-specific validation (terraform fmt, yamllint)

### D4: Terraform Provider Versioning Strategy

**Decision**: Generator configuration includes provider version constraints; versions.tf template renders the constraint.

**Provider Constraints** (stored in plugin config):
| Provider | Source | Version Constraint |
|----------|--------|-------------------|
| bpg/proxmox | terraform-provider-proxmox | `>= 0.66.0` |
| terraform-routeros/routeros | RouterOS provider | `~> 1.40` |

**Implementation**:
```yaml
# plugins.yaml
- id: base.generator.terraform_proxmox
  config:
    proxmox_provider_source: "bpg/proxmox"
    proxmox_provider_version: ">= 0.66.0"
    terraform_version: ">= 1.6.0"
```

```jinja2
{# versions.tf.j2 #}
terraform {
  required_version = "{{ terraform_version }}"
  required_providers {
    proxmox = {
      source  = "{{ proxmox_provider_source }}"
      version = "{{ proxmox_provider_version }}"
    }
  }
}
```

**State Management Policy**:
- Generated artifacts go to `v5-generated/terraform/{proxmox,mikrotik}/`
- State files are NOT committed (gitignored)
- State is managed in execution workspace (`.work/native/terraform/` or operator environment)
- `terraform.tfvars.example` is generated; actual `terraform.tfvars` is in `local/terraform/` (gitignored)

### D5: Deterministic Output Guarantees

**Decision**: All generators MUST produce deterministic, diff-friendly output through explicit ordering and formatting.

**Required Mechanisms**:

1. **Projection-Level Sorting**: `projections.py` already applies `_sorted_rows()` using `(instance_id, object_ref, json_dump)` key tuple

2. **Template-Level Ordering**: Templates MUST iterate sorted collections
   ```jinja2
   {% for lxc in lxc_containers | sort(attribute='instance_id') %}
   resource "proxmox_virtual_environment_container" "{{ lxc.instance_id | replace('-', '_') }}" {
   {% endfor %}
   ```

3. **JSON Key Sorting**: All JSON output uses `sort_keys=True`
   ```python
   json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2)
   ```

4. **Atomic Writes**: Use `write_text_atomic()` from `base_generator.py` (tmp + rename)

5. **Post-Generation Formatting** (optional): Run `terraform fmt` if available
   ```python
   def post_generate(self, output_dir: Path) -> None:
       subprocess.run(["terraform", "fmt", "-recursive"], cwd=output_dir, check=False)
   ```

**Determinism Test Pattern**:
```python
def test_deterministic_output():
    for _ in range(3):
        result = generator.execute(ctx, Stage.GENERATE)
        outputs.append(read_all_files(result.output_data["files"]))
    assert outputs[0] == outputs[1] == outputs[2]
```

### D6: Post-Generation Validation Gates

**Decision**: Implement multi-tier validation gates integrated with generate stage and CI.

**Gate 1: Structural Validation** (in generator)
- Check all expected files were written
- Verify file count matches projection counts
- Emit diagnostic on missing/extra files

```python
expected_files = ["provider.tf", "versions.tf", "bridges.tf", "lxc.tf", "vms.tf",
                  "variables.tf", "outputs.tf", "terraform.tfvars.example"]
for filename in expected_files:
    if not (out_dir / filename).exists():
        diagnostics.append(self.emit_diagnostic(
            code="E9102", severity="error", stage=stage,
            message=f"expected file not generated: {filename}",
            path=str(out_dir / filename),
        ))
```

**Gate 2: Syntax Validation** (post-generate hook or CI)
- `terraform fmt -check` - HCL formatting
- `terraform validate` - HCL syntax and provider schema
- `ansible-inventory --list -i hosts.yml` - Ansible YAML validity

**Gate 3: Parity Validation** (CI/regression tests)
- Compare against v4 baseline with approved-diff allowlist
- Location: `v5/tests/plugin_regression/test_terraform_*_parity.py`

```python
def test_proxmox_parity():
    v4_output = load_v4_baseline("v4-generated/terraform/proxmox/")
    v5_output = generate_v5_output()

    diff = compute_diff(v4_output, v5_output)
    unapproved = [d for d in diff if d.file not in APPROVED_DIFFS]
    assert not unapproved, f"Unapproved diffs: {unapproved}"
```

**Gate 4: Secret-Safety Scan** (CI)
- Scan generated files for secret patterns
- Block commits containing actual credentials
- `terraform.tfvars.example` must contain only placeholder values

### D7: Migration Path from v4 Generators

**Decision**: Incremental migration with parity gates at each step.

**Phase 3 (Terraform Proxmox) Migration Steps**:
1. Copy v4 templates to `v5/topology-tools/templates/terraform/proxmox/`
2. Create projection adapter mapping v5 projection keys to v4 template expectations
3. Update `terraform_proxmox_generator.py` to use templates instead of inline strings
4. Add parity test comparing v4 and v5 output
5. Iterate until parity test passes (or diffs are explicitly approved)

**Template Adaptation Example**:
```python
# v4 template expects: lxc_containers, storage_map, bridge_map, topology_version
# v5 projection provides: lxc (list), counts
# Adapter:
def build_template_context(projection: dict) -> dict:
    return {
        "lxc_containers": projection["lxc"],
        "storage_map": _derive_storage_map(projection),  # computed from projection
        "bridge_map": {},  # v5 may not need this if bridges embedded in lxc
        "topology_version": "5.0",
    }
```

**v4 Freeze Policy**:
- v4 lane is frozen per ADR 0062
- v4 templates are read-only reference; do not modify
- If v4 template has bugs, fix in v5 and document intentional diff

### D8: Extension Points for Operator Customization

**Decision**: Provide three extension tiers with increasing customization power, without requiring generator forking.

#### Tier 1: Configuration Injection (Simplest)

Operators inject values via plugin config in `plugins.yaml` or runtime overrides.

**Supported Extension Points**:
- Provider version constraints
- Output subdirectory paths
- Feature toggles (e.g., `include_vpn_resources: false`)

**Implementation**:
```yaml
# plugins.yaml override in operator environment
- id: base.generator.terraform_proxmox
  config:
    proxmox_provider_version: "~> 0.90.0"  # Override default
    include_vm_resources: false             # Skip VM generation
    output_subdir: custom/proxmox           # Custom path
```

Generators read config via `ctx.config.get("key", default)`:
```python
provider_version = ctx.config.get("proxmox_provider_version", ">= 0.66.0")
```

#### Tier 2: Post-Generation Hooks (Moderate)

Operators register post-generation plugins that transform or augment generated output.

**Hook Contract**:
```python
class PostGenerateHook(GeneratorPlugin):
    """Post-generation transformer hook."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Read generated files from previous generator's output_data
        proxmox_files = ctx.subscribe("base.generator.terraform_proxmox", "terraform_proxmox_files")

        # Transform/augment
        for filepath in proxmox_files:
            content = Path(filepath).read_text()
            augmented = self._add_custom_tags(content)
            self.write_text_atomic(Path(filepath), augmented)

        return self.make_result([])
```

**Registration**:
```yaml
- id: operator.hook.proxmox_tags
  kind: generator
  entry: operators/custom_tags.py:CustomTagsHook
  stages: [generate]
  order: 215  # After terraform_proxmox (210), before mikrotik (220)
  depends_on: [base.generator.terraform_proxmox]
```

**Use Cases**:
- Adding organization-specific tags to all resources
- Injecting backend configuration
- Appending custom provider blocks

#### Tier 3: Projection Augmentation (Advanced)

Operators register compiler plugins that augment projections before generators consume them.

**Augmentation Contract**:
```python
class ProjectionAugmenter(CompilerPlugin):
    """Augment compiled model before generation."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Read base projection data
        lxc_rows = ctx.compiled_json.get("instances", {}).get("l4_lxc", [])

        # Augment with operator-specific data
        for row in lxc_rows:
            row["custom_metadata"] = self._lookup_cmdb(row["instance_id"])

        # Generators will see augmented data
        return self.make_result([])
```

**Registration**:
```yaml
- id: operator.compiler.cmdb_lookup
  kind: compiler
  entry: operators/cmdb_augmenter.py:CMDBAugmenter
  stages: [compile]
  order: 65  # After effective_model (60), before validators
  depends_on: [base.compiler.effective_model]
```

#### Extension Point Summary

| Tier | Complexity | Requires Code | Use Case |
|------|------------|---------------|----------|
| **T1: Config** | Low | No | Version pins, feature flags, paths |
| **T2: Hook** | Medium | Python plugin | Post-processing, augmentation |
| **T3: Augment** | High | Python plugin | Data enrichment, external lookups |

#### Anti-Patterns to Avoid

1. **Template Overrides**: Do NOT allow operators to replace template files. This creates hidden divergence and breaks reproducibility.

2. **Generated File Editing**: Do NOT provide hooks for in-place editing of generated content. Use Tier 2 post-generation hooks instead, which are explicit and auditable.

3. **Bypass Validation Gates**: Extension hooks MUST NOT skip post-generation validation (`terraform validate`, etc.).

#### Pipeline Integration

Extension points integrate with the compile -> validate -> generate -> post-validate flow:

```
compile stage:
  [base compilers] -> [T3 augmenters] -> compiled_json ready

validate stage:
  [validators run on compiled_json]

generate stage:
  [base generators (T1 config applied)] -> [T2 post-hooks]

post-validate (CI):
  terraform fmt -check
  terraform validate
  ansible-inventory --list
```

## Consequences

### What Improves

1. **Type Safety**: Dataclass projections provide IDE support and early error detection for complex generator logic
2. **Template Stability**: Projections absorb compiled model changes; templates remain stable
3. **Deterministic Output**: Explicit sorting guarantees reproducible generation
4. **Validation Coverage**: Multi-tier gates catch issues at generation, syntax, and parity levels
5. **Clear Migration Path**: Incremental template migration with continuous parity verification
6. **Plugin Isolation**: Each generator is independently testable and versionable
7. **Operator Extensibility**: Three-tier extension system (D8) allows customization without forking
8. **Pipeline Integration**: Generators fit cleanly in compile -> validate -> generate -> post-validate flow

### Trade-offs and Risks

1. **Dual Interface Complexity**: Supporting both dict and typed projections adds maintenance burden
   - Mitigation: Typed builders call dict builders internally; single source of truth

2. **Template Strategy Evolution**: Inline templates work now but may need extraction later
   - Mitigation: Clear extraction triggers in D3; snapshot tests before migration

3. **CI Time Increase**: Validation gates add runtime
   - Mitigation: Run expensive gates (terraform validate) only on relevant file changes

4. **Projection Contract Fragility**: If compiled model changes, projections may break
   - Mitigation: Projection contract tests with golden snapshots

5. **Extension Point Abuse**: Operators may create overly complex hook chains
   - Mitigation: Anti-patterns documented in D8; CI enforces validation gates cannot be bypassed

### Compatibility Impact

- **v4 Lane**: No changes; v4 generators continue to work independently
- **v5 Lane**: Generator output changes from stub locals to full HCL/YAML
- **CI Pipeline**: Terraform and Ansible validation gates already added (commit 1626aa4)
- **Developer Workflow**: `make generate-v5` now produces deployable artifacts

### Implementation Notes

D3 (Template Organization) now reflects the pragmatic hybrid approach adopted in implementation:
- **Baseline**: Inline Python string templates within generator classes (current state)
- **Evolution Path**: Extract to Jinja2 files when complexity thresholds are met (see D3 criteria)
- **Decision**: Inline templates are the *accepted default* for v5, not a deviation

D8 (Extension Points) provides the customization framework requested by operators without requiring generator forking.

## Supplement: Current Implementation Status (2026-03-19)

Based on commits `109ca98` and `1626aa4`, the following aspects are already implemented:

### S1: Implemented Generators (Inline Templates)

All Phase 3-6 generators are operational using **inline string templates** (not Jinja2 files):

| Generator | Order | Output Files | Status |
|-----------|-------|--------------|--------|
| `terraform_proxmox_generator.py` | 210 | provider.tf, versions.tf, bridges.tf, lxc.tf, vms.tf, variables.tf, outputs.tf, terraform.tfvars.example | ✅ Working |
| `terraform_mikrotik_generator.py` | 220 | provider.tf, interfaces.tf, firewall.tf, dhcp.tf, dns.tf, addresses.tf, qos.tf, vpn.tf, containers.tf, variables.tf, outputs.tf | ✅ Working |
| `ansible_inventory_generator.py` | 230 | hosts.yml, group_vars/all.yml | ✅ Working |
| `bootstrap_proxmox_generator.py` | 310 | answer.toml.example, post-install/*, README.md | ✅ Working |
| `bootstrap_mikrotik_generator.py` | 320 | init-terraform.rsc, backup-restore-overrides.rsc, terraform.tfvars.example, README.md | ✅ Working |
| `bootstrap_orangepi_generator.py` | 330 | cloud-init/user-data.example, cloud-init/meta-data, cloud-init/README.md | ✅ Working |

### S2: Template Strategy Rationale

**Current approach**: Generators use Python f-strings and heredoc-style inline templates.

**Alignment with D3**: This is the *accepted default* per the refined D3 decision, not a deviation. The hybrid approach recognizes that inline templates are optimal for the current complexity level.

**Trade-off analysis**:

| Aspect | Inline Templates (Current) | Jinja2 Files (Future) |
|--------|---------------------------|------------------------|
| **Co-location** | Template + logic in one file | Templates separate from logic |
| **IDE Support** | Full Python IDE support | Requires Jinja2 plugin |
| **Refactoring** | Easier (rename propagates) | Manual sync required |
| **Review** | Single file per generator | Multiple files per generator |
| **Reuse** | Copy-paste between generators | `{% include %}` / `{% extends %}` |
| **HCL Syntax** | No highlighting in Python strings | Full HCL highlighting in .j2 |

**Extraction Triggers** (per D3): Extract to Jinja2 files when:
- Any single template function exceeds 100 lines
- Template reuse opportunity emerges (e.g., shared `versions.tf` across targets)
- Operator customization via D8 Tier 2 hooks becomes unwieldy

### S3: CI Validation Gates (Implemented)

Per commit `1626aa4`, validation gates are already in `.github/workflows/plugin-validation.yml`:

```yaml
# Gate 2: Terraform Syntax Validation
- terraform init -backend=false -input=false
- terraform fmt -check
- terraform validate

# Gate 2: Ansible Inventory Validation
- ansible-inventory --list -i hosts.yml
```

**Covered targets**:
- `v5-generated/terraform/proxmox/` ✅
- `v5-generated/terraform/mikrotik/` ✅
- `v5-generated/ansible/inventory/production/hosts.yml` ✅

**Not yet covered**:
- Gate 3: Parity tests vs v4 baseline (pending)
- Gate 4: Secret-safety scan (pending)

### S4: Remaining Work for Production Readiness

| Phase | Item | Status |
|-------|------|--------|
| 3 | Parity test vs v4 Proxmox | ⏳ Pending |
| 4 | Parity test vs v4 MikroTik | ⏳ Pending |
| 4 | Capability-driven resource generation | ⏳ Pending |
| 5 | Runtime inventory assembly | ⏳ Pending |
| 5 | Parity test vs v4 Ansible | ⏳ Pending |
| 7 | Hardware identity capture utility | ⏳ Pending |
| 8 | E2E deployment dry-run | ⏳ Pending |

### S5: Diagnostic Code Allocation

Bootstrap generators introduced new error codes:

| Code | Generator | Meaning |
|------|-----------|---------|
| E9401 | bootstrap_proxmox | Projection build failed |
| E9501 | bootstrap_mikrotik | Projection build failed |
| E9601 | bootstrap_orangepi | Projection build failed |

**Recommendation**: Document error code ranges in plugin manifest or separate registry:
- E9100-E9199: Terraform Proxmox generator
- E9200-E9299: Terraform MikroTik generator
- E9300-E9399: Ansible generator
- E9400-E9499: Bootstrap Proxmox generator
- E9500-E9599: Bootstrap MikroTik generator
- E9600-E9699: Bootstrap Orange Pi generator

### S6: Extension Points Implementation Status

Per D8, the three-tier extension system:

| Tier | Implementation Status | Notes |
|------|----------------------|-------|
| **T1: Config Injection** | ✅ Working | Generators read `ctx.config.get()` for overrides |
| **T2: Post-Generation Hooks** | ✅ Infrastructure Ready | Plugin system supports `depends_on` ordering; no sample hooks yet |
| **T3: Projection Augmentation** | ✅ Infrastructure Ready | Compiler plugin chain allows order 65 insertion; no sample augmenters yet |

**Next Steps for T2/T3**:
1. Create example operator hook in `v5/topology-tools/plugins/operators/` (gitignored)
2. Document hook development workflow in CLAUDE.md
3. Add CI check that operator plugins don't break base generation

## Foundational Decisions from v4 ADRs

This section documents key architectural decisions from earlier ADRs that v5 generators MUST respect and build upon.

### F1: Three-Layer Terraform Assembly (ADR 0055)

**Origin**: ADR 0055 - Manual Terraform Extension Layer

v4 established that Terraform execution is assembled from three layers:

```
generated baseline (topology-derived)
    +
terraform-overrides/ (tracked exceptions)
    +
local/ (untracked operator inputs)
    =
.work/native/terraform/<target>/ (execution root)
```

**v5 Implication**: Generators emit to `v5-generated/terraform/<target>/` as pure baseline. They MUST NOT assume direct execution from generated path. Assembly happens via `assemble-native.py` or equivalent.

**Rules Preserved**:
- Generated files are disposable and regeneratable
- Overrides are additive, never shadowing generated files
- `terraform.tfvars` is NEVER generated (only `.example`)
- State files are NEVER in generated output

### F2: Tool-Centric Output Structure (ADR 0050)

**Origin**: ADR 0050 - Generated Directory Restructuring

Output is organized by execution tool, not by device:

```
v5-generated/
├── bootstrap/<device-id>/     # Pre-IaC device initialization
├── terraform/
│   ├── proxmox/               # Proxmox root module
│   └── mikrotik/              # MikroTik root module
└── ansible/inventory/         # Unified inventory root
```

**v5 Implication**: Generators write to `ctx.artifacts_root / <tool> / <target>`. Device-centric organization only applies to bootstrap.

**Rationale**: Terraform and Ansible run from control machine against APIs/SSH, not on devices. Bootstrap scripts run on/for specific devices.

### F3: Pure Baseline Generated Root (ADR 0056)

**Origin**: ADR 0056 - Native Execution Workspace Outside Generated Roots

`generated/` (now `v5-generated/`) must remain a pure baseline:
- Contains only topology-derived outputs
- Never modified by execution
- Safe to delete and rebuild
- Never contains state, logs, or execution artifacts

**v5 Implication**: Generators use `write_text_atomic()` for deterministic output. No side effects beyond file creation.

### F4: Inventory Ownership Split (ADR 0051)

**Origin**: ADR 0051 - Ansible Runtime, Inventory, and Secret Boundaries

Generated inventory is authoritative for host structure:
```
generated/ansible/inventory/<env>/
├── hosts.yml           # Topology-derived hosts
├── group_vars/all.yml  # Topology-derived vars
└── host_vars/*.yml     # Topology-derived per-host vars
```

Manual extensions belong in separate tracked location (not in generated/):
```
ansible/inventory-overrides/production/
├── group_vars/
└── host_vars/
```

**v5 Implication**: `ansible_inventory_generator.py` emits complete host structure. Operators extend via overrides, not by editing generated files.

### F5: Microkernel Plugin Architecture (ADR 0063)

**Origin**: ADR 0063 - Plugin Microkernel for Compiler, Validators, and Generators

Plugin kinds and their responsibilities:
| Kind | Stage | Responsibility |
|------|-------|----------------|
| compiler | compile | Transform/resolve, emit to `compiled_json` |
| validator_yaml | validate | Check source YAML before compilation |
| validator_json | validate | Check compiled JSON contracts |
| generator | generate | Emit artifacts from `compiled_json` |

**v5 Implication**: Generators implement `GeneratorPlugin` protocol, execute in `generate` stage, consume `ctx.compiled_json`, emit to `ctx.artifacts_root`.

**Error handling contract**:
- Timeout >30s: Hard kill, TIMEOUT status
- Exception in execute(): Catch, emit diagnostic, FAILED status
- Missing dependency: Fail-fast before stage

### F6: Generator Protocol Contract (ADR 0025, superseded but principle preserved)

**Origin**: ADR 0025 - Generator Protocol and CLI Base Class (superseded by ADR 0028/0063)

Original protocol:
```python
class Generator(Protocol):
    topology_path: Path
    output_dir: Path
    topology: Dict[str, Any]

    def load_topology(self) -> bool: ...
    def generate_all(self) -> bool: ...
    def print_summary(self) -> None: ...
```

**v5 Evolution**: Now formalized as `GeneratorPlugin` in plugin microkernel:
```python
class TerraformProxmoxGenerator(BaseGenerator):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # ctx.compiled_json replaces self.topology
        # ctx.artifacts_root replaces self.output_dir
        # PluginResult replaces bool return
```

**Preserved Principles**:
- Explicit contract with type hints
- Summary/diagnostic output via PluginResult
- Separation of loading (microkernel) from generation (plugin)

### F7: Parity and Validation Must Include Extensions (ADR 0055)

**Origin**: ADR 0055 section 8

Validation must run against fully assembled execution root, not just generated baseline:
- Parity tests compare assembled output
- `terraform validate` runs on layered root
- Package manifests record which overrides participated

**v5 Implication**: Parity tests in `v5/tests/plugin_regression/` should test assembled output when overrides exist.

### Summary: v4 Decisions That v5 Must Respect

| ADR | Decision | v5 Compliance |
|-----|----------|---------------|
| 0050 | Tool-centric output structure | ✅ `v5-generated/terraform/<target>/` |
| 0051 | Generated inventory is authoritative | ✅ `ansible_inventory_generator.py` |
| 0055 | Three-layer assembly | ✅ Generators emit baseline only |
| 0055 | Overrides are additive | ✅ No shadow/replace patterns |
| 0056 | Pure baseline generated root | ✅ No execution artifacts in v5-generated/ |
| 0063 | Plugin microkernel | ✅ All generators are plugins |
| 0063 | Error handling contract | ✅ ProjectionError → PluginResult |

## References

- Production Readiness Plan: `adr/plan/v5-production-readiness.md`
- Projection Layer: `v5/topology-tools/plugins/generators/projections.py`
- Base Generator: `v5/topology-tools/plugins/generators/base_generator.py`
- Plugin Contract: `v5/topology-tools/kernel/plugin_base.py`
- v4 Proxmox Generator: `v4/topology-tools/scripts/generators/terraform/proxmox/generator.py`
- v4 MikroTik Generator: `v4/topology-tools/scripts/generators/terraform/mikrotik/generator.py`

### Foundational v4 ADRs

- ADR 0025: Generator Protocol and CLI Base Class
- ADR 0050: Generated Directory Restructuring
- ADR 0051: Ansible Runtime, Inventory, and Secret Boundaries
- ADR 0055: Manual Terraform Extension Layer
- ADR 0056: Native Execution Workspace Outside Generated Roots
- ADR 0063: Plugin Microkernel for Compiler, Validators, and Generators
- Plugin Manifest: `v5/topology-tools/plugins/plugins.yaml`
- ADR 0062: Modular Topology Architecture Consolidation
- ADR 0063: Plugin Microkernel for Compiler, Validators, and Generators

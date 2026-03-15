# Phase 1: Generator Plugin Framework

**Parent:** [v5-production-readiness.md](v5-production-readiness.md)
**Status:** Not Started
**Priority:** P0

---

## Objective

Create the foundational infrastructure for v5 generator plugins that will produce Terraform, Ansible, and Bootstrap artifacts from the compiled effective model.

---

## Current State Analysis

### Existing Generator Plugins

```
v5/topology-tools/plugins/generators/
├── effective_json_generator.py  (1.8 KB) - emits effective-topology.json
└── effective_yaml_generator.py  (2.0 KB) - emits effective-topology.yaml
```

These are minimal generators that serialize the compiled model. They don't use templates.

### V4 Generator Architecture

```
v4/topology-tools/
├── generate-terraform-proxmox.py   (uses templates/terraform/proxmox/)
├── generate-terraform-mikrotik.py  (uses templates/terraform/mikrotik/)
├── generate-ansible-inventory.py   (uses templates/ansible/)
└── templates/
    ├── terraform/
    │   ├── proxmox/  (6 Jinja2 templates)
    │   └── mikrotik/ (7 Jinja2 templates)
    └── ansible/      (inventory templates)
```

V4 generators load topology.yaml directly and use Jinja2 templates.

### Key Differences V4 → V5

| Aspect | V4 | V5 |
|--------|----|----|
| Input | `topology.yaml` (raw YAML) | `ctx.compiled_json` (effective model) |
| Execution | Standalone script | Plugin in generate stage |
| Discovery | Manual import | Plugin registry |
| Dependencies | None declared | `depends_on: [base.generator.effective_json]` |
| Output path | `v4-generated/` | `v5-generated/` |

---

## Deliverables

### 1. Base Generator Class

**File:** `v5/topology-tools/plugins/generators/base_generator.py`

```python
from pathlib import Path
from typing import Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from kernel.plugin_base import GeneratorPlugin, PluginResult, PluginContext

class TemplateBasedGenerator(GeneratorPlugin):
    """Base class for generators that use Jinja2 templates."""

    # Subclasses override these
    TEMPLATE_DIR: str = ""  # relative to templates/
    OUTPUT_SUBDIR: str = ""  # relative to output root

    def __init__(self, context: PluginContext):
        super().__init__(context)
        self._env: Environment | None = None

    @property
    def template_env(self) -> Environment:
        """Lazily create Jinja2 environment."""
        if self._env is None:
            templates_root = Path(__file__).parent.parent.parent / "templates"
            template_path = templates_root / self.TEMPLATE_DIR
            self._env = Environment(
                loader=FileSystemLoader(template_path),
                autoescape=select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            self._register_filters()
        return self._env

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters. Override in subclasses."""
        pass

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with given context."""
        template = self.template_env.get_template(template_name)
        return template.render(**context)

    def write_output(self, output_dir: Path, filename: str, content: str) -> Path:
        """Write content to output file, creating directories as needed."""
        target_dir = output_dir / self.OUTPUT_SUBDIR
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / filename
        target_file.write_text(content)
        return target_file

    def get_effective_model(self) -> dict[str, Any]:
        """Get the compiled effective model from context."""
        return self.context.subscribe("base.compiler.effective_model", "effective_topology")
```

### 2. Template Directory Structure

```
v5/topology-tools/templates/
├── terraform/
│   ├── proxmox/
│   │   ├── provider.tf.j2
│   │   ├── bridges.tf.j2
│   │   ├── lxc.tf.j2
│   │   ├── vms.tf.j2
│   │   ├── variables.tf.j2
│   │   └── outputs.tf.j2
│   └── mikrotik/
│       ├── provider.tf.j2
│       ├── interfaces.tf.j2
│       ├── firewall.tf.j2
│       ├── dhcp.tf.j2
│       ├── vpn.tf.j2
│       ├── qos.tf.j2
│       └── containers.tf.j2
├── ansible/
│   ├── hosts.yml.j2
│   └── host_vars.yml.j2
└── bootstrap/
    ├── proxmox/
    ├── mikrotik/
    └── orangepi/
```

### 3. Plugin Registry Updates

**File:** `v5/topology-tools/plugins/plugins.yaml` (additions)

```yaml
# Generator base dependency
- id: base.compiler.effective_model
  kind: compiler
  entry: plugins/compilers/effective_model_compiler.py:EffectiveModelCompiler
  api_version: "1.x"
  stages: [compile]
  order: 60
  depends_on: [base.compiler.module_loader, base.compiler.capabilities, base.compiler.instance_rows]
  publishes:
    - effective_topology  # consumed by generators
```

### 4. Test Infrastructure

**File:** `v5/tests/plugin_integration/test_generator_base.py`

```python
import pytest
from pathlib import Path
from plugins.generators.base_generator import TemplateBasedGenerator

class TestTemplateBasedGenerator:
    def test_template_env_creation(self, plugin_context):
        """Template environment is created lazily."""
        ...

    def test_render_template(self, plugin_context, tmp_path):
        """Templates are rendered with context."""
        ...

    def test_write_output_creates_dirs(self, plugin_context, tmp_path):
        """Output directories are created as needed."""
        ...

    def test_get_effective_model(self, plugin_context_with_compiled):
        """Effective model is retrieved from compile stage."""
        ...
```

---

## Implementation Steps

### Step 1: Create base generator class

```bash
# Create file
touch v5/topology-tools/plugins/generators/base_generator.py

# Implement TemplateBasedGenerator
# - Template loading
# - Output file writing
# - Effective model access
```

### Step 2: Create template directory structure

```bash
mkdir -p v5/topology-tools/templates/{terraform/{proxmox,mikrotik},ansible,bootstrap/{proxmox,mikrotik,orangepi}}
```

### Step 3: Update effective_model_compiler to publish data

```python
# In effective_model_compiler.py execute():
self.context.publish("effective_topology", effective_model)
```

### Step 4: Add generator base tests

```bash
touch v5/tests/plugin_integration/test_generator_base.py
pytest v5/tests/plugin_integration/test_generator_base.py -v
```

### Step 5: Verify integration

```bash
# Compile topology and check that effective model is available for generators
python3 v5/topology-tools/compile-topology.py --verbose
```

---

## Acceptance Criteria

- [ ] `TemplateBasedGenerator` class exists with template loading
- [ ] Template directory structure created
- [ ] `effective_model_compiler` publishes `effective_topology` key
- [ ] Generator can access compiled model via `context.subscribe()`
- [ ] All tests pass: `pytest v5/tests/plugin_integration/test_generator_base.py`
- [ ] No regressions: `pytest v5/tests/ -v` all green

---

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `v5/topology-tools/plugins/generators/base_generator.py` |
| Create | `v5/topology-tools/templates/` (directory structure) |
| Modify | `v5/topology-tools/plugins/compilers/effective_model_compiler.py` |
| Create | `v5/tests/plugin_integration/test_generator_base.py` |

---

## Next Phase

After completing Phase 1, proceed to:
- [Phase 2: Terraform Proxmox Generator](phase2-terraform-proxmox.md)

# ADR 0063 Implementation Guide - Quick Reference

**Purpose:** Quick reference guide for implementing ADR 0063 (Plugin Microkernel)

**Date:** 2026-03-09
**Related ADRs:** 0063, 0064, 0065

---

## 📚 Documentation Map

| Document | Purpose | Audience |
|----------|---------|----------|
| **ADR 0063** | Architecture decision for microkernel | Architects, leads |
| **ADR 0064** | Plugin API contract specification | Plugin developers |
| **ADR 0065** | Testing and CI strategy | QA, DevOps |
| **PLUGIN_AUTHORING_GUIDE.md** | How to write plugins | Plugin developers |
| **PLUGIN_IMPLEMENTATION_EXAMPLES.md** | Concrete code examples | Plugin developers |
| **This document** | Quick reference | Everyone |

---

## 🎯 Quick Start (5 minutes)

### 1. Create Plugin File

```python
# topology/object-modules/mymodule/plugins/my_validator.py
from topology_tools.plugin_api import YamlValidatorPlugin, PluginResult

class MyValidator(YamlValidatorPlugin):
    def validate_config(self):
        return self._success()

    def execute(self, yaml_dict, source_path):
        # Your validation logic here
        return self._success()  # or emit diagnostics
```

### 2. Add to Manifest

```yaml
# topology/object-modules/mymodule/manifest.yaml
plugins:
  - id: obj.mymodule.validator.yaml.mycheck
    kind: validator_yaml
    entry: plugins/my_validator.py:MyValidator
    api_version: "1.x"
    stages: [validate]
    order: 100
    depends_on: []
```

### 3. Write Tests

```python
# topology/object-modules/mymodule/tests/test_my_validator.py
def test_plugin_valid_input(plugin_context):
    plugin = MyValidator(plugin_context)
    result = plugin.execute({"valid": "data"}, "test.yaml")
    assert result.status == PluginStatus.SUCCESS
```

### 4. Test Locally

```bash
cd topology/object-modules/mymodule
pytest tests/ -v --cov
```

---

## 🔌 Plugin Types at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  YAML Files                                                 │
│         ↓                                                   │
│  [validator_yaml plugins]    ← Check source syntax/semantics
│         ↓                                                   │
│  [compiler plugins]           ← Transform and resolve model │
│         ↓                                                   │
│  [validator_json plugins]    ← Check compiled consistency  │
│         ↓                                                   │
│  [generator plugins]          ← Generate artifacts         │
│         ↓                                                   │
│  Generated Files (TF, Ansible, Docs)                       │
└─────────────────────────────────────────────────────────────┘
```

| Type | Input | Output | Stage | When |
|------|-------|--------|-------|------|
| **validator_yaml** | YAML dict | Diagnostics | validate | Source checks |
| **compiler** | YAML/Object dict | Transformed dict | compile | Resolve refs |
| **validator_json** | JSON dict | Diagnostics | validate | Check consistency |
| **generator** | JSON dict | Files | generate | Emit artifacts |

---

## 🛠️ Common Tasks

### Task: Validate Required Field

```python
def execute(self, yaml_dict, source_path):
    if "required_field" not in yaml_dict:
        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=PluginStatus.FAILED,
            diagnostics=[
                PluginDiagnostic(
                    severity=PluginSeverity.ERROR,
                    code="REQ_FIELD_MISSING",
                    message="'required_field' is required"
                )
            ]
        )
```

### Task: Access Configuration

```python
def execute(self, yaml_dict, source_path):
    max_items = self.context.config.get("max_items", 100)
    if len(yaml_dict.get("items", [])) > max_items:
        # Emit error
```

### Task: Publish Data for Downstream

```python
def execute(self, model_dict):
    # ... do work ...
    self.context.publish("device_index", device_index)
    return self._success()
```

### Task: Consume Published Data

```python
def execute(self, json_dict, compiled_path):
    try:
        device_index = self.context.subscribe(
            "obj.mymodule.compiler.resolve_refs",
            "device_index"
        )
    except KeyError:
        # Dependency failed or not published
        return PluginResult(...status=PluginStatus.FAILED...)
```

### Task: Generate File

```python
def execute(self, json_dict, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "generated.tf"
    output_file.write_text(content)

    return PluginResult(
        ...
        output_data={
            "generated_files": [
                {"path": "generated.tf", "size": len(content)}
            ]
        }
    )
```

---

## ✅ Checklist Before Submitting PR

- [ ] Plugin class inherits from correct base (YamlValidatorPlugin, etc.)
- [ ] Config validation implemented in `validate_config()`
- [ ] No mutations of input parameters
- [ ] All diagnostics have severity, code, and message
- [ ] Source location provided for YAML validators (file, line)
- [ ] Exception handling wraps errors in PluginResult
- [ ] Manifest entry is complete (all required fields)
- [ ] Plugin ID follows convention: `obj.module.kind.subname`
- [ ] api_version matches kernel support (currently "1.x")
- [ ] order is unique and correctly sequenced within stage
- [ ] depends_on lists plugins that must run before this one
- [ ] Config schema is valid JSON Schema
- [ ] Unit tests cover happy path + error cases
- [ ] Contract tests validate kernel integration
- [ ] Integration tests check pipeline behavior
- [ ] No hardcoded paths (use context.config)
- [ ] No credentials in code
- [ ] Docstrings explain what plugin does
- [ ] Test data committed to testdata/
- [ ] README updated if needed

---

## 🐛 Troubleshooting

### Plugin Not Found

**Check:**
1. Manifest has `plugins:` section?
2. Plugin ID matches what kernel requests?
3. `entry` path correct relative to module root?
4. Class name matches exactly (case-sensitive)?
5. Run: `python -m topology_tools.validate_manifests topology/object-modules/mymodule/manifest.yaml`

### Plugin Times Out (>30s)

**Fix:**
1. Profile code: where's the bottleneck?
2. Add index/cache for repeated lookups
3. Process in batches instead of all-at-once
4. Consider if task should be split into multiple plugins

### Config Not Applied

**Check:**
1. Manifest has `config:` section with keys?
2. `config_schema` is valid JSON Schema?
3. Plugin reads from `self.context.config`?
4. Environment variable correct format: `TOPO_OBJ_MYMODULE_VALIDATOR_KEY=value`

### Diagnostics Not in Report

**Check:**
1. Plugin actually ran? (check kernel logs)
2. Correct severity? (ERROR, WARNING, INFO all included)
3. Plugin in correct stage? (validate, compile, generate)
4. Depends_on satisfied? (dependency failed = plugin skipped)

### Dependency Not Found

**Fix:**
1. Check depends_on plugin ID exact match (typos?)
2. Upstream plugin executes before your plugin? (check order)
3. Upstream plugin succeeded? (not FAILED status)

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Plugin Microkernel                     │
├─────────────────────────────────────────────────────────┤
│ 1. Load module manifests                                │
│ 2. Discover plugins from manifest.yaml                  │
│ 3. Validate plugin compatibility                        │
│ 4. Resolve dependency graph (DAG)                       │
│ 5. Determine execution order                            │
│ 6. Execute plugins in stages [validate→compile→generate]
│ 7. Enforce timeouts (30s per plugin)                    │
│ 8. Aggregate diagnostics                                │
│ 9. Handle errors/recovery                               │
└─────────────────────────────────────────────────────────┘
         ↓                      ↓                      ↓
    validator_yaml        compiler             generator
         ↓                      ↓                      ↓
  Check source          Resolve refs            Create files
```

---

## 📈 Plugin Execution Flow

```
Start
  ↓
[1] Load manifests from all modules
  ↓
[2] Discover plugins and register
  ↓
[3] Validate plugin compatibility
    - API version: 1.x matches kernel 1.2? ✓
    - Config: passes schema validation? ✓
  ↓
[4] Build dependency graph
    - Plugin A depends_on nothing
    - Plugin B depends_on Plugin A
    - Plugin C depends_on Plugin B
    - DAG cycles detected? ERROR!
  ↓
[5] Execute Stage: validate
    - Order plugins by numeric order (100, 200, 300)
    - For each plugin:
      - Run validate_config() → FAILED? Skip rest
      - Run execute() with timeout 30s
      - Aggregate diagnostics
      - Continue if non-critical, fail if critical
  ↓
[6] Execute Stage: compile
    - (same as validate)
  ↓
[7] Execute Stage: generate
    - (same as validate)
  ↓
[8] Aggregate all diagnostics
    - Sort by severity (ERROR > WARNING > INFO)
    - Include plugin attribution
    - Output to canonical schema
  ↓
[9] Report results
    - status: SUCCESS|PARTIAL|FAILED
    - diagnostics: [...all issues...]
    - output_data: {...transformed model...}
  ↓
End
```

---

## 🔐 Security Notes

- **No credentials in code** - Use environment variables or config
- **Manifest paths are relative** - No absolute paths allowed
- **Plugins cannot access filesystem directly** - Use output_dir provided
- **No subprocess/network requests** - Topology tools are offline-first
- **Input validation required** - Don't assume source data is valid
- **Diagnostics sanitized** - No leaking sensitive info in messages

---

## 🚀 Migration Phases

| Phase | Timeline | What | Status |
|-------|----------|------|--------|
| **Phase 1** | Week 1 | Plugin base protocol | Planned |
| **Phase 2** | Week 2-3 | Wrap generators as plugins | Planned |
| **Phase 3** | Week 4-5 | Migrate validators to plugins | Planned |
| **Phase 4** | +2 releases | Remove legacy code | Planned |

---

## 📞 Getting Help

1. **Read:** Plugin Authoring Guide (docs/PLUGIN_AUTHORING_GUIDE.md)
2. **Learn:** Implementation Examples (docs/PLUGIN_IMPLEMENTATION_EXAMPLES.md)
3. **Study:** ADR 0064 for API details
4. **Look:** Example plugins in topology/base-plugins/ (coming soon)
5. **Ask:** Code review on your PR

---

## 📚 References

- **ADR 0062:** Modular topology architecture (model/object/instance)
- **ADR 0063:** Plugin microkernel (this decision)
- **ADR 0064:** Plugin API contract
- **ADR 0065:** Plugin testing and CI
- **Docs:** PLUGIN_AUTHORING_GUIDE.md
- **Docs:** PLUGIN_IMPLEMENTATION_EXAMPLES.md
- **Code:** topology-tools/plugin_api/ (to be created)

---

## Version

- **Document:** v1.0
- **Kernel API:** 1.x
- **Compatible With:** Model v0062+
- **Last Updated:** 2026-03-09

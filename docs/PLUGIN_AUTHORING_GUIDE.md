# Plugin Authoring Guide

**Last Updated:** 2026-03-09
**Related:** ADR 0063, ADR 0064

This guide helps topology module developers create plugins that integrate with the plugin microkernel.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Plugin Types](#plugin-types)
3. [Project Structure](#project-structure)
4. [Writing Your First Plugin](#writing-your-first-plugin)
5. [Configuration](#configuration)
6. [Error Handling](#error-handling)
7. [Testing](#testing)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Create Plugin File

```python
# topology/object-modules/mikrotik/plugins/yaml_validators/device.py

from topology_tools.plugin_api import YamlValidatorPlugin, PluginResult, PluginStatus
from topology_tools.plugin_api import PluginSeverity, PluginDiagnostic

class MikrotikDeviceYamlValidator(YamlValidatorPlugin):
    """Validate Mikrotik device YAML structure and semantics"""

    def validate_config(self) -> PluginResult:
        """Validate plugin config before execution"""
        if "max_name_length" in self.context.config:
            if not isinstance(self.context.config["max_name_length"], int):
                return PluginResult(
                    plugin_id=self.context.plugin_id,
                    api_version=self.api_version,
                    status=PluginStatus.FAILED,
                    duration_ms=0,
                    diagnostics=[
                        PluginDiagnostic(
                            severity=PluginSeverity.ERROR,
                            code="CFG001",
                            message="max_name_length must be integer"
                        )
                    ]
                )
        return self._success()

    def execute(self, yaml_dict, source_path) -> PluginResult:
        """Validate device YAML"""
        diagnostics = []

        # Example validation
        if "devices" not in yaml_dict:
            diagnostics.append(
                self._diagnostic(
                    PluginSeverity.ERROR,
                    "DEV001",
                    "Missing required 'devices' section",
                    location={"file": source_path, "line": 1}
                )
            )

        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=PluginStatus.SUCCESS if not diagnostics else PluginStatus.PARTIAL,
            duration_ms=0,
            diagnostics=diagnostics,
            output_data={}
        )
```

### 2. Add to Module Manifest

```yaml
# topology/object-modules/mikrotik/manifest.yaml

module_id: obj.mikrotik
module_version: "0.5.0"

plugins:
  - id: obj.mikrotik.validator.yaml.device
    kind: validator_yaml
    entry: plugins/yaml_validators/device.py:MikrotikDeviceYamlValidator
    api_version: "1.x"
    stages: [validate]
    order: 100
    depends_on: []
    config:
      max_name_length: 63
      allow_deprecated: false
    config_schema:
      type: object
      properties:
        max_name_length:
          type: integer
          minimum: 1
          maximum: 255
          default: 63
        allow_deprecated:
          type: boolean
          default: false
```

### 3. Test Plugin

```python
# topology/object-modules/mikrotik/tests/test_device_validator.py

import pytest
from plugins.yaml_validators.device import MikrotikDeviceYamlValidator
from topology_tools.plugin_api import PluginContext

@pytest.fixture
def plugin_context():
    class MockKernel:
        def log(self, plugin_id, message, level):
            print(f"[{level}] {plugin_id}: {message}")

    return PluginContext(
        kernel=MockKernel(),
        plugin_id="obj.mikrotik.validator.yaml.device",
        config={"max_name_length": 63}
    )

def test_missing_devices_section(plugin_context):
    plugin = MikrotikDeviceYamlValidator(plugin_context)
    result = plugin.execute({"metadata": {}}, "test.yaml")

    assert result.status == PluginStatus.PARTIAL
    assert len(result.diagnostics) > 0
    assert result.diagnostics[0].code == "DEV001"

def test_valid_structure(plugin_context):
    plugin = MikrotikDeviceYamlValidator(plugin_context)
    result = plugin.execute({
        "devices": [
            {"name": "r1", "model": "RB4011"}
        ]
    }, "test.yaml")

    assert result.status == PluginStatus.SUCCESS
    assert len(result.diagnostics) == 0
```

---

## Plugin Types

### Validator YAML Plugins

**When to use:** Validate source YAML before compilation

**Input:** Raw YAML dict, source file path
**Output:** List of validation diagnostics
**Stage:** `validate`

```python
from topology_tools.plugin_api import YamlValidatorPlugin

class MyYamlValidator(YamlValidatorPlugin):
    def execute(self, yaml_dict, source_path) -> PluginResult:
        # Check syntax, required fields, semantic constraints
        # Emit diagnostics with source location
        pass
```

**Common checks:**
- Required fields presence
- Field type validation
- Enum value checks
- Reference resolution (device X exists?)
- Cardinality constraints (min/max items)

### Validator JSON Plugins

**When to use:** Validate compiled Object Model logical consistency

**Input:** Compiled JSON dict, compiled file path
**Output:** List of validation diagnostics
**Stage:** `validate`

```python
from topology_tools.plugin_api import JsonValidatorPlugin

class MyJsonValidator(JsonValidatorPlugin):
    def execute(self, json_dict, compiled_path) -> PluginResult:
        # Check cross-references, constraints on compiled model
        # May reference other plugin outputs
        pass
```

**Common checks:**
- Reference integrity (dangling references?)
- Cardinality across objects
- Constraint violations
- Inconsistent state

### Compiler Plugins

**When to use:** Transform/resolve model during compilation

**Input:** Object Model dict, returns transformed dict
**Output:** Transformed model + diagnostics
**Stage:** `compile`

```python
from topology_tools.plugin_api import CompilerPlugin

class MyCompiler(CompilerPlugin):
    def execute(self, model_dict) -> PluginResult:
        # Transform model, resolve references
        # Return modified model in output_data
        pass
```

**Common transformations:**
- Flattening nested structures
- Resolving template variables
- Building cross-reference indexes
- Normalizing data formats

### Generator Plugins

**When to use:** Generate artifacts (code, configs, docs)

**Input:** Compiled JSON, output directory
**Output:** File listing + diagnostics
**Stage:** `generate`

```python
from topology_tools.plugin_api import GeneratorPlugin

class MyGenerator(GeneratorPlugin):
    def execute(self, json_dict, output_dir) -> PluginResult:
        # Create files in output_dir
        # Emit diagnostics for each file created
        pass
```

**Common outputs:**
- Terraform .tf files
- Ansible playbooks
- Network config files
- Markdown documentation

---

## Project Structure

```
topology/object-modules/mikrotik/
├── manifest.yaml                    # Module manifest with plugin declarations
├── README.md
├── plugins/
│   ├── __init__.py
│   ├── yaml_validators/
│   │   ├── __init__.py
│   │   ├── device.py               # YamlValidatorPlugin
│   │   └── interface.py            # YamlValidatorPlugin
│   ├── json_validators/
│   │   ├── __init__.py
│   │   ├── references.py           # JsonValidatorPlugin
│   │   └── constraints.py          # JsonValidatorPlugin
│   ├── compilers/
│   │   ├── __init__.py
│   │   └── resolve_references.py  # CompilerPlugin
│   └── generators/
│       ├── __init__.py
│       ├── terraform.py            # GeneratorPlugin
│       └── ansible.py              # GeneratorPlugin
├── schema/
│   ├── class-contract.schema.json
│   └── object-contract.schema.json
├── tests/
│   ├── conftest.py
│   ├── test_yaml_validators.py
│   ├── test_json_validators.py
│   ├── test_compilers.py
│   └── test_generators.py
└── testdata/
    ├── valid_device.yaml
    ├── invalid_device.yaml
    └── expected_compiled.json
```

---

## Writing Your First Plugin

### Step 1: Understand the Contract

- What's the input? (YAML dict? JSON dict? Both?)
- What's the output? (Diagnostics? Modified data?)
- When does it run? (Which stage?)
- What depends on you? (Plugins with depends_on pointing to your ID)

### Step 2: Create Plugin Class

```python
from topology_tools.plugin_api import BasePlugin, PluginResult, PluginStatus, PluginSeverity

class MyPlugin(YamlValidatorPlugin):  # or other plugin type

    def validate_config(self) -> PluginResult:
        """Always implement this to catch config errors early"""
        # Verify self.context.config contains valid settings
        required_keys = ["key1", "key2"]
        for key in required_keys:
            if key not in self.context.config:
                return PluginResult(
                    plugin_id=self.context.plugin_id,
                    api_version=self.api_version,
                    status=PluginStatus.FAILED,
                    duration_ms=0,
                    diagnostics=[
                        PluginDiagnostic(
                            severity=PluginSeverity.ERROR,
                            code="CFG_MISSING",
                            message=f"Required config key '{key}' missing"
                        )
                    ]
                )
        return self._success()

    def execute(self, ...) -> PluginResult:
        """Implement the main logic"""
        diagnostics = []

        try:
            # Your business logic here
            result_data = self._do_work(...)

        except Exception as e:
            self.context.log(f"Error: {str(e)}", "error")
            return PluginResult(
                plugin_id=self.context.plugin_id,
                api_version=self.api_version,
                status=PluginStatus.FAILED,
                duration_ms=0,
                diagnostics=[
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="EXE_EXCEPTION",
                        message=str(e)
                    )
                ],
                error_traceback=traceback.format_exc()
            )

        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=PluginStatus.SUCCESS if not diagnostics else PluginStatus.PARTIAL,
            duration_ms=0,
            diagnostics=diagnostics,
            output_data=result_data
        )
```

### Step 3: Add to Manifest

```yaml
plugins:
  - id: obj.mymodule.validator.yaml.mycheck
    kind: validator_yaml
    entry: plugins/yaml_validators/mycheck.py:MyValidator
    api_version: "1.x"
    stages: [validate]
    order: 150
    depends_on: []  # or list plugin IDs you depend on
    config: {}      # or fill with defaults
    config_schema:
      type: object
      properties: {}
```

### Step 4: Add Tests

```python
def test_my_plugin_happy_path(plugin_context):
    plugin = MyPlugin(plugin_context)
    result = plugin.execute(valid_input)

    assert result.status == PluginStatus.SUCCESS
    assert len(result.diagnostics) == 0

def test_my_plugin_error_case(plugin_context):
    plugin = MyPlugin(plugin_context)
    result = plugin.execute(invalid_input)

    assert result.status == PluginStatus.PARTIAL
    assert len(result.diagnostics) > 0
    assert result.diagnostics[0].severity == PluginSeverity.ERROR
```

---

## Configuration

### Config in Manifest

```yaml
plugins:
  - id: obj.mikrotik.validator
    config:
      max_device_count: 1000
      enable_strict_mode: true
    config_schema:
      type: object
      properties:
        max_device_count:
          type: integer
          minimum: 1
          default: 1000
        enable_strict_mode:
          type: boolean
          default: false
      required: []
```

### Access Config in Plugin

```python
class MyPlugin(YamlValidatorPlugin):
    def execute(self, yaml_dict, source_path) -> PluginResult:
        max_count = self.context.config.get("max_device_count", 1000)
        strict = self.context.config.get("enable_strict_mode", False)

        # Use config values
```

### Override via Environment

```bash
# Environment variable format: TOPO_{PLUGIN_ID}_KEY=value
# Replace dots and dashes with underscores

export TOPO_OBJ_MIKROTIK_VALIDATOR_MAX_DEVICE_COUNT=500
export TOPO_OBJ_MIKROTIK_VALIDATOR_ENABLE_STRICT_MODE=true
```

---

## Error Handling

### Plugin Exceptions

```python
def execute(self, ...) -> PluginResult:
    try:
        result = self._validate()
    except ValueError as e:
        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=PluginStatus.FAILED,
            duration_ms=0,
            diagnostics=[
                PluginDiagnostic(
                    severity=PluginSeverity.ERROR,
                    code="VAL_ERROR",
                    message=str(e)
                )
            ],
            error_traceback=traceback.format_exc()
        )
```

### Publishing Errors

```python
def execute(self, yaml_dict, source_path) -> PluginResult:
    diagnostics = []

    for device in yaml_dict.get("devices", []):
        if not self._is_valid(device):
            diagnostics.append(
                PluginDiagnostic(
                    severity=PluginSeverity.ERROR,
                    code="DEV_INVALID",
                    message=f"Device {device.get('name')} is invalid",
                    location={
                        "file": source_path,
                        "line": self._find_line(device),
                        "column": 1
                    }
                )
            )

    return PluginResult(
        plugin_id=self.context.plugin_id,
        api_version=self.api_version,
        status=PluginStatus.PARTIAL if diagnostics else PluginStatus.SUCCESS,
        duration_ms=0,
        diagnostics=diagnostics,
        output_data={}
    )
```

---

## Testing

### Unit Tests (Plugin Isolation)

```python
# Test plugin in isolation with mock kernel

@pytest.fixture
def mock_context():
    class MockKernel:
        def log(self, plugin_id, msg, level):
            pass

    return PluginContext(
        kernel=MockKernel(),
        plugin_id="obj.test.validator",
        config={"key": "value"}
    )

def test_valid_input(mock_context):
    plugin = MyPlugin(mock_context)
    result = plugin.execute({"valid": "data"})
    assert result.status == PluginStatus.SUCCESS
```

### Contract Tests (Plugin vs Kernel)

```python
# Test plugin integration with kernel loader

def test_plugin_loads_from_manifest(kernel):
    """Test plugin can be discovered and instantiated by kernel"""
    plugin = kernel.load_plugin("obj.test.validator")
    assert plugin is not None
    assert plugin.api_version == "1.x"

def test_plugin_config_injected(kernel):
    """Test kernel passes config correctly"""
    plugin = kernel.load_plugin("obj.test.validator")
    assert plugin.context.config["expected_key"] == "expected_value"
```

### Integration Tests (Full Pipeline)

```python
# Test plugin within full compilation pipeline

def test_plugin_in_pipeline(kernel, test_yaml_file):
    """Test plugin runs in correct stage with correct data"""
    result = kernel.compile(test_yaml_file)

    # Find plugin result in aggregated diagnostics
    plugin_diags = [d for d in result.diagnostics
                    if d.plugin_id == "obj.test.validator"]
    assert len(plugin_diags) > 0
```

---

## Best Practices

### ✅ DO

1. **Validate config early** - Implement `validate_config()` thoroughly
2. **Emit diagnostics for everything** - Warnings, info, errors all matter
3. **Provide source location** - Help users find issues in YAML
4. **Document with docstrings** - Future developers need context
5. **Write contracts, not implementations** - Think about your plugin's interface
6. **Handle missing dependencies gracefully** - Don't assume other plugins succeeded
7. **Test error paths** - Most bugs hide in error handling
8. **Use semantic error codes** - `DEV001` is better than `ERROR1`
9. **Publish useful data** - If other plugins need your output, use context.publish()
10. **Keep plugins small** - One responsibility per plugin

### ❌ DON'T

1. **Mutate input data** - Always return new dicts, don't modify what you receive
2. **Hardcode paths** - Use manifest paths and context.config
3. **Suppress exceptions** - Always emit diagnostics
4. **Share state between plugins** - Use context.subscribe() for inter-plugin communication
5. **Assume plugins ran before you** - Check depends_on, use context.subscribe() safely
6. **Log directly to files** - Use context.log()
7. **Create threads/subprocesses** - Kernel controls concurrency
8. **Make network requests** - Topology tools are offline-first
9. **Store credentials in code** - Use environment variables or context.config
10. **Return different output_data types** - Be consistent with contract

---

## Troubleshooting

### Plugin Not Loaded

**Problem:** Kernel says plugin not found

**Solutions:**
1. Check plugin `id` in manifest matches what you're requesting
2. Check `entry` path is correct relative to module root
3. Check Python class name matches `entry` (case-sensitive)
4. Run `kernel.validate_manifest()` to catch manifest errors

```python
result = kernel.validate_manifest("path/to/manifest.yaml")
if not result.is_valid:
    print(result.errors)
```

### Plugin Timeouts

**Problem:** Plugin runs longer than 30 seconds

**Solutions:**
1. Optimize algorithm (use indices, avoid nested loops)
2. Cache expensive computations
3. Implement incremental processing (process in chunks)
4. Consider if this should be split into multiple plugins

### Plugin Config Not Working

**Problem:** context.config is empty or missing keys

**Solutions:**
1. Check manifest has `config:` section with keys
2. Check `config_schema` is valid JSON Schema
3. Check environment variable format: `TOPO_PLUGIN_ID_KEY=value`
4. Call `validate_config()` to catch config errors

### Plugin Results Aggregation

**Problem:** Diagnostics not appearing in final report

**Solutions:**
1. Check plugin `stages` matches pipeline execution
2. Check plugin `order` - maybe it runs too late?
3. Check plugin `depends_on` - maybe dependency failed?
4. Check diagnostics severity - some levels may be filtered
5. Look at kernel logs to see if plugin ran

---

## Next Steps

1. Read ADR 0063 for architecture overview
2. Read ADR 0064 for API contract details
3. Look at examples in `topology/base-plugins/` for reference implementations
4. Create your first plugin using this guide
5. Run tests: `pytest topology/object-modules/[your-module]/tests/`
6. Submit for code review focusing on:
   - Config validation completeness
   - Diagnostic quality and location info
   - Test coverage of error cases
   - Documentation clarity

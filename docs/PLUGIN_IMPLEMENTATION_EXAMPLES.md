# Plugin Implementation Examples

**Purpose:** Reference implementations showing best practices for plugin development

**Related:** ADR 0063, ADR 0064, Plugin Authoring Guide

---

## Example 1: Simple YAML Validator Plugin

**Use case:** Validate device name constraints in Mikrotik module

**File:** `topology/object-modules/mikrotik/plugins/yaml_validators/device_names.py`

```python
"""
Validate device name constraints in YAML.
- Max length: 63 characters (configurable)
- No spaces or special characters
- Must be unique within module
"""

import re
from typing import Dict, Any
from topology_tools.plugin_api import (
    YamlValidatorPlugin,
    PluginResult,
    PluginStatus,
    PluginSeverity,
    PluginDiagnostic
)

class MikrotikDeviceNamesValidator(YamlValidatorPlugin):
    """Validate device naming conventions in Mikrotik topology"""

    NAME_PATTERN = re.compile(r'^[a-z0-9_-]+$')

    def validate_config(self) -> PluginResult:
        """Validate plugin configuration"""
        try:
            max_length = self.context.config.get("max_name_length", 63)
            if not isinstance(max_length, int) or max_length < 1:
                raise ValueError("max_name_length must be positive integer")

            return self._success()

        except ValueError as e:
            return PluginResult(
                plugin_id=self.context.plugin_id,
                api_version=self.api_version,
                status=PluginStatus.FAILED,
                duration_ms=0,
                diagnostics=[
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="CFG_INVALID",
                        message=f"Config validation failed: {str(e)}"
                    )
                ]
            )

    def execute(self, yaml_dict: Dict[str, Any], source_path: str) -> PluginResult:
        """
        Validate device names in YAML.

        Checks:
        1. Device name exists
        2. Device name length <= max_name_length
        3. Device name matches pattern [a-z0-9_-]+
        4. Device names are unique
        """
        diagnostics = []
        max_length = self.context.config.get("max_name_length", 63)
        seen_names = set()

        devices = yaml_dict.get("devices", [])

        if not isinstance(devices, list):
            return PluginResult(
                plugin_id=self.context.plugin_id,
                api_version=self.api_version,
                status=PluginStatus.FAILED,
                duration_ms=0,
                diagnostics=[
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_INVALID_TYPE",
                        message="'devices' must be a list",
                        location={"file": source_path, "line": 1}
                    )
                ]
            )

        for idx, device in enumerate(devices):
            if not isinstance(device, dict):
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NOT_DICT",
                        message=f"Device at index {idx} must be dict, got {type(device).__name__}",
                        location={"file": source_path, "line": idx + 2}
                    )
                )
                continue

            device_name = device.get("name")

            # Check presence
            if device_name is None:
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NO_NAME",
                        message=f"Device at index {idx} has no 'name' field",
                        location={"file": source_path, "line": idx + 2}
                    )
                )
                continue

            # Check type
            if not isinstance(device_name, str):
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NAME_TYPE",
                        message=f"Device name must be string, got {type(device_name).__name__}",
                        location={"file": source_path, "line": idx + 2}
                    )
                )
                continue

            # Check length
            if len(device_name) > max_length:
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NAME_TOO_LONG",
                        message=f"Device name '{device_name}' exceeds {max_length} chars (got {len(device_name)})",
                        location={"file": source_path, "line": idx + 2}
                    )
                )
                continue

            # Check pattern
            if not self.NAME_PATTERN.match(device_name):
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NAME_INVALID_CHARS",
                        message=f"Device name '{device_name}' contains invalid characters. "
                                f"Allowed: a-z, 0-9, _, -",
                        location={"file": source_path, "line": idx + 2}
                    )
                )
                continue

            # Check uniqueness
            if device_name in seen_names:
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NAME_DUPLICATE",
                        message=f"Device name '{device_name}' appears more than once",
                        location={"file": source_path, "line": idx + 2}
                    )
                )
                continue

            seen_names.add(device_name)

        status = PluginStatus.SUCCESS if not diagnostics else (
            PluginStatus.PARTIAL if len(diagnostics) < len(devices)
            else PluginStatus.FAILED
        )

        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=status,
            duration_ms=0,
            diagnostics=diagnostics,
            output_data={"total_devices_checked": len(devices)}
        )
```

**Manifest entry:**

```yaml
plugins:
  - id: obj.mikrotik.validator.yaml.device_names
    kind: validator_yaml
    entry: plugins/yaml_validators/device_names.py:MikrotikDeviceNamesValidator
    api_version: "1.x"
    stages: [validate]
    order: 100
    depends_on: []
    config:
      max_name_length: 63
    config_schema:
      type: object
      properties:
        max_name_length:
          type: integer
          minimum: 1
          maximum: 255
          default: 63
      required: []
```

**Tests:**

```python
# topology/object-modules/mikrotik/tests/test_device_names_validator.py

import pytest
from plugins.yaml_validators.device_names import MikrotikDeviceNamesValidator
from topology_tools.plugin_api import PluginContext, PluginStatus, PluginSeverity

@pytest.fixture
def mock_kernel():
    class MockKernel:
        def log(self, plugin_id, message, level):
            pass
    return MockKernel()

@pytest.fixture
def plugin_context(mock_kernel):
    return PluginContext(
        kernel=mock_kernel,
        plugin_id="obj.mikrotik.validator.yaml.device_names",
        config={"max_name_length": 63}
    )

def test_valid_device_names(plugin_context):
    """Valid device names pass validation"""
    plugin = MikrotikDeviceNamesValidator(plugin_context)
    yaml_input = {
        "devices": [
            {"name": "router1"},
            {"name": "device-a"},
            {"name": "r1_backup"}
        ]
    }

    result = plugin.execute(yaml_input, "test.yaml")

    assert result.status == PluginStatus.SUCCESS
    assert len(result.diagnostics) == 0

def test_device_name_too_long(plugin_context):
    """Device name exceeding max length fails"""
    plugin = MikrotikDeviceNamesValidator(plugin_context)
    yaml_input = {
        "devices": [
            {"name": "a" * 64}  # 64 chars, exceeds default 63
        ]
    }

    result = plugin.execute(yaml_input, "test.yaml")

    assert result.status == PluginStatus.PARTIAL
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "DEV_NAME_TOO_LONG"
    assert result.diagnostics[0].severity == PluginSeverity.ERROR

def test_device_name_invalid_characters(plugin_context):
    """Device name with invalid chars fails"""
    plugin = MikrotikDeviceNamesValidator(plugin_context)
    yaml_input = {
        "devices": [
            {"name": "Router@1"},  # @ not allowed
            {"name": "device name"}  # space not allowed
        ]
    }

    result = plugin.execute(yaml_input, "test.yaml")

    assert result.status == PluginStatus.FAILED
    assert len(result.diagnostics) == 2
    assert all(d.code == "DEV_NAME_INVALID_CHARS" for d in result.diagnostics)

def test_duplicate_device_names(plugin_context):
    """Duplicate names detected"""
    plugin = MikrotikDeviceNamesValidator(plugin_context)
    yaml_input = {
        "devices": [
            {"name": "router1"},
            {"name": "router2"},
            {"name": "router1"}  # duplicate
        ]
    }

    result = plugin.execute(yaml_input, "test.yaml")

    assert result.status == PluginStatus.PARTIAL
    assert any(d.code == "DEV_NAME_DUPLICATE" for d in result.diagnostics)

def test_missing_device_name(plugin_context):
    """Missing device name fails"""
    plugin = MikrotikDeviceNamesValidator(plugin_context)
    yaml_input = {
        "devices": [
            {"name": "router1"},
            {"model": "RB4011"}  # no name field
        ]
    }

    result = plugin.execute(yaml_input, "test.yaml")

    assert result.status == PluginStatus.PARTIAL
    assert any(d.code == "DEV_NO_NAME" for d in result.diagnostics)

def test_config_validation_fails_on_invalid_max_length(mock_kernel):
    """Config validation rejects invalid max_name_length"""
    context = PluginContext(
        kernel=mock_kernel,
        plugin_id="obj.mikrotik.validator.yaml.device_names",
        config={"max_name_length": "invalid"}  # should be int
    )

    plugin = MikrotikDeviceNamesValidator(context)
    result = plugin.validate_config()

    assert result.status == PluginStatus.FAILED
    assert result.diagnostics[0].code == "CFG_INVALID"

def test_location_context_provided(plugin_context):
    """Diagnostics include source location"""
    plugin = MikrotikDeviceNamesValidator(plugin_context)
    yaml_input = {
        "devices": [
            {"name": "invalid@"}
        ]
    }

    result = plugin.execute(yaml_input, "topology.yaml")

    assert len(result.diagnostics) == 1
    diag = result.diagnostics[0]
    assert diag.location is not None
    assert diag.location["file"] == "topology.yaml"
    assert diag.location["line"] == 2  # After 'devices:' header
```

---

## Example 2: Compiler Plugin with Inter-Plugin Communication

**Use case:** Resolve device references, publish resolution map for other plugins

**File:** `topology/object-modules/mikrotik/plugins/compilers/resolve_device_refs.py`

```python
"""
Compiler plugin that:
1. Creates device index during compilation
2. Publishes device reference map
3. Resolves symbolic references to device IDs
"""

from typing import Dict, Any, List
from topology_tools.plugin_api import (
    CompilerPlugin,
    PluginResult,
    PluginStatus,
    PluginSeverity
)

class MikrotikDeviceRefResolver(CompilerPlugin):
    """
    Resolve device references in interfaces and links.

    Transforms:
    Input:  interfaces: [{device: "router1", name: "ether1"}]
    Output: interfaces: [{device_id: "dev_abc123", name: "ether1"}]

    Also publishes device map for downstream validators.
    """

    def validate_config(self) -> PluginResult:
        """No config needed for this plugin"""
        return self._success()

    def execute(self, model_dict: Dict[str, Any]) -> PluginResult:
        """
        Resolve device references.

        1. Build device index: name -> device_id
        2. Resolve interface references
        3. Resolve link endpoints
        4. Publish index for other plugins
        """
        diagnostics = []
        transformed = self._deep_copy(model_dict)  # Don't mutate input

        # Step 1: Build device index
        device_index = self._build_device_index(
            transformed.get("devices", []),
            diagnostics
        )

        if device_index is None:
            # Fatal error in indexing
            return PluginResult(
                plugin_id=self.context.plugin_id,
                api_version=self.api_version,
                status=PluginStatus.FAILED,
                duration_ms=0,
                diagnostics=diagnostics
            )

        # Step 2: Resolve interface device references
        for interface in transformed.get("interfaces", []):
            if "device" in interface and "device_id" not in interface:
                device_name = interface["device"]
                if device_name in device_index:
                    interface["device_id"] = device_index[device_name]
                else:
                    diagnostics.append(
                        PluginDiagnostic(
                            severity=PluginSeverity.ERROR,
                            code="REF_UNKNOWN_DEVICE",
                            message=f"Interface references unknown device: {device_name}"
                        )
                    )

        # Step 3: Publish device index for downstream plugins
        self.context.publish(
            "device_index",
            device_index
        )

        status = PluginStatus.SUCCESS if not diagnostics else PluginStatus.PARTIAL

        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=status,
            duration_ms=0,
            diagnostics=diagnostics,
            output_data=transformed
        )

    def _build_device_index(self, devices: List[Dict], diagnostics: List) -> Dict[str, str]:
        """Build {device_name: device_id} index"""
        index = {}

        for device in devices:
            name = device.get("name")
            device_id = device.get("id")

            if not name:
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NO_NAME",
                        message="Device missing required 'name' field"
                    )
                )
                return None

            if not device_id:
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_NO_ID",
                        message=f"Device '{name}' missing required 'id' field"
                    )
                )
                return None

            if name in index:
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEV_DUPLICATE",
                        message=f"Duplicate device name: {name}"
                    )
                )
                return None

            index[name] = device_id

        return index

    @staticmethod
    def _deep_copy(obj):
        """Deep copy for safety"""
        import copy
        return copy.deepcopy(obj)
```

**Using published data in downstream validator:**

```python
# topology/object-modules/mikrotik/plugins/json_validators/interface_refs.py

class MikrotikInterfaceRefValidator(JsonValidatorPlugin):
    """
    Validate interface references using published device index.
    Requires: MikrotikDeviceRefResolver to run first.
    """

    def execute(self, json_dict: Dict[str, Any], compiled_path: str) -> PluginResult:
        """Validate interfaces reference valid devices"""
        diagnostics = []

        # Get device index from upstream compiler plugin
        try:
            device_index = self.context.subscribe(
                "obj.mikrotik.compiler.resolve_device_refs",
                "device_index"
            )
        except KeyError as e:
            return PluginResult(
                plugin_id=self.context.plugin_id,
                api_version=self.api_version,
                status=PluginStatus.FAILED,
                duration_ms=0,
                diagnostics=[
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="DEP_MISSING",
                        message=f"Required dependency failed: {str(e)}"
                    )
                ]
            )

        # Validate using index
        for interface in json_dict.get("interfaces", []):
            device_id = interface.get("device_id")
            if device_id not in device_index.values():
                diagnostics.append(
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="IFACE_BAD_DEVICE",
                        message=f"Interface references invalid device_id: {device_id}"
                    )
                )

        status = PluginStatus.SUCCESS if not diagnostics else PluginStatus.PARTIAL

        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=status,
            duration_ms=0,
            diagnostics=diagnostics,
            output_data={}
        )
```

**Manifest entries:**

```yaml
plugins:
  # Compiler runs first, publishes device_index
  - id: obj.mikrotik.compiler.resolve_device_refs
    kind: compiler
    entry: plugins/compilers/resolve_device_refs.py:MikrotikDeviceRefResolver
    api_version: "1.x"
    stages: [compile]
    order: 100
    depends_on: []

  # Validator runs after compiler, consumes published index
  - id: obj.mikrotik.validator.json.interface_refs
    kind: validator_json
    entry: plugins/json_validators/interface_refs.py:MikrotikInterfaceRefValidator
    api_version: "1.x"
    stages: [validate]
    order: 100
    depends_on:
      - obj.mikrotik.compiler.resolve_device_refs
```

---

## Example 3: Generator Plugin

**Use case:** Generate Terraform configuration from compiled model

**File:** `topology/object-modules/mikrotik/plugins/generators/terraform.py`

```python
"""
Generate Terraform .tf files from compiled topology.
Emits:
- main.tf (resource definitions)
- variables.tf (input variables)
- outputs.tf (output values)
"""

from pathlib import Path
from typing import Dict, Any
from topology_tools.plugin_api import (
    GeneratorPlugin,
    PluginResult,
    PluginStatus,
    PluginSeverity
)

class MikrotikTerraformGenerator(GeneratorPlugin):
    """Generate Terraform configuration"""

    def validate_config(self) -> PluginResult:
        """Validate config"""
        required_keys = ["terraform_version", "provider"]
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

    def execute(self, json_dict: Dict[str, Any], output_dir: Path) -> PluginResult:
        """Generate Terraform files"""
        diagnostics = []
        output_dir = Path(output_dir)

        # Create output directory
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return PluginResult(
                plugin_id=self.context.plugin_id,
                api_version=self.api_version,
                status=PluginStatus.FAILED,
                duration_ms=0,
                diagnostics=[
                    PluginDiagnostic(
                        severity=PluginSeverity.ERROR,
                        code="GEN_MKDIR_FAILED",
                        message=f"Cannot create output directory: {str(e)}"
                    )
                ]
            )

        generated_files = []

        # Generate main.tf
        main_tf_path = output_dir / "main.tf"
        try:
            main_tf_content = self._generate_main_tf(json_dict)
            main_tf_path.write_text(main_tf_content)
            generated_files.append({
                "path": str(main_tf_path.relative_to(output_dir.parent)),
                "size": len(main_tf_content)
            })
            diagnostics.append(
                PluginDiagnostic(
                    severity=PluginSeverity.INFO,
                    code="GEN_FILE_CREATED",
                    message=f"Generated {main_tf_path.name}",
                    location={"file": str(main_tf_path)}
                )
            )
        except Exception as e:
            diagnostics.append(
                PluginDiagnostic(
                    severity=PluginSeverity.ERROR,
                    code="GEN_FAILED",
                    message=f"Failed to generate main.tf: {str(e)}"
                )
            )

        # Generate variables.tf
        variables_tf_path = output_dir / "variables.tf"
        try:
            variables_tf_content = self._generate_variables_tf(json_dict)
            variables_tf_path.write_text(variables_tf_content)
            generated_files.append({
                "path": str(variables_tf_path.relative_to(output_dir.parent)),
                "size": len(variables_tf_content)
            })
        except Exception as e:
            diagnostics.append(
                PluginDiagnostic(
                    severity=PluginSeverity.ERROR,
                    code="GEN_FAILED",
                    message=f"Failed to generate variables.tf: {str(e)}"
                )
            )

        status = PluginStatus.SUCCESS if len(diagnostics) == 2 else PluginStatus.PARTIAL

        return PluginResult(
            plugin_id=self.context.plugin_id,
            api_version=self.api_version,
            status=status,
            duration_ms=0,
            diagnostics=diagnostics,
            output_data={
                "generated_files": generated_files,
                "total_files": len(generated_files)
            }
        )

    def _generate_main_tf(self, json_dict: Dict[str, Any]) -> str:
        """Generate main.tf content"""
        lines = [
            'terraform {',
            f'  required_version = ">= {self.context.config["terraform_version"]}"',
            '  required_providers {',
            '    routeros = {',
            f'      source = "{self.context.config["provider"]}"',
            '    }',
            '  }',
            '}',
            '',
            'provider "routeros" {',
            '  hosturl = var.routeros_url',
            '  username = var.routeros_username',
            '  password = var.routeros_password',
            '}',
            ''
        ]

        # Generate resources from devices
        for device in json_dict.get("devices", []):
            lines.append(f'# Device: {device.get("name")}')
            lines.append(f'resource "routeros_ip_address" "{device.get("id")}_ip" {{')
            lines.append(f'  address = "{device.get("ip_address", "0.0.0.0/24")}"')
            lines.append('}')
            lines.append('')

        return '\n'.join(lines)

    def _generate_variables_tf(self, json_dict: Dict[str, Any]) -> str:
        """Generate variables.tf content"""
        lines = [
            'variable "routeros_url" {',
            '  type = string',
            '  description = "RouterOS API URL"',
            '}',
            '',
            'variable "routeros_username" {',
            '  type = string',
            '  description = "RouterOS username"',
            '}',
            '',
            'variable "routeros_password" {',
            '  type = string',
            '  sensitive = true',
            '  description = "RouterOS password"',
            '}',
        ]

        return '\n'.join(lines)
```

---

## Key Takeaways

1. **Always validate config first** before executing business logic
2. **Use context.publish() to share data** between plugins
3. **Provide rich diagnostics** with source location and semantic error codes
4. **Don't mutate input** - deep copy before modifying
5. **Wrap exceptions** and include tracebacks in PluginResult
6. **Test error paths** - most bugs hide in edge cases
7. **Document assumptions** - what does this plugin expect from upstream?

---

## References

- ADR 0063: Plugin Microkernel Architecture
- ADR 0064: Plugin API Contract Specification
- ADR 0065: Plugin Testing and CI Strategy
- Plugin Authoring Guide: `docs/PLUGIN_AUTHORING_GUIDE.md`

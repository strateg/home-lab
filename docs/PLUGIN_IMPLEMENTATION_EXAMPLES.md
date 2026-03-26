# Plugin Implementation Examples

**Last Updated:** 2026-03-26
**Related:** ADR 0063, ADR 0065, ADR 0080, Plugin Authoring Guide

Reference implementations showing best practices for v5 plugin development.

---

## Example 1: YAML Validator — Device Name Constraints

**Use case:** Validate device name conventions in a MikroTik object module.

**File:** `topology/object-modules/mikrotik/plugins/validators/device_names.py`

```python
"""
Validate device name constraints in YAML topology:
- Max length (configurable, default 63)
- Pattern: lowercase alphanumeric, hyphens, underscores only
- Uniqueness within the module
"""

import re

from kernel.plugin_base import (
    ValidatorYamlPlugin, PluginContext, PluginResult, Stage,
)


class MikrotikDeviceNamesValidator(ValidatorYamlPlugin):
    """Validate device naming conventions in MikroTik topology."""

    NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        max_length = ctx.config.get("max_name_length", 63)
        seen_names: set[str] = set()

        devices = ctx.raw_yaml.get("devices", [])
        if not isinstance(devices, list):
            diagnostics.append(self.emit_diagnostic(
                code="E5001", severity="error", stage=stage,
                message="'devices' must be a list",
                path="devices",
                source_file=ctx.source_file,
            ))
            return self.make_result(diagnostics)

        for idx, device in enumerate(devices):
            if not isinstance(device, dict):
                diagnostics.append(self.emit_diagnostic(
                    code="E5002", severity="error", stage=stage,
                    message=f"Device at index {idx} must be a mapping, got {type(device).__name__}",
                    path=f"devices[{idx}]",
                    source_file=ctx.source_file,
                ))
                continue

            name = device.get("name")

            if name is None:
                diagnostics.append(self.emit_diagnostic(
                    code="E5003", severity="error", stage=stage,
                    message=f"Device at index {idx} missing required 'name' field",
                    path=f"devices[{idx}]",
                    source_file=ctx.source_file,
                    hint="Add a 'name' field with a lowercase identifier",
                ))
                continue

            if not isinstance(name, str):
                diagnostics.append(self.emit_diagnostic(
                    code="E5004", severity="error", stage=stage,
                    message=f"Device name must be a string, got {type(name).__name__}",
                    path=f"devices[{idx}].name",
                    source_file=ctx.source_file,
                ))
                continue

            if len(name) > max_length:
                diagnostics.append(self.emit_diagnostic(
                    code="E5005", severity="error", stage=stage,
                    message=f"Device name '{name}' exceeds {max_length} chars ({len(name)})",
                    path=f"devices[{idx}].name",
                    source_file=ctx.source_file,
                    hint=f"Shorten name to {max_length} characters or fewer",
                ))

            elif not self.NAME_PATTERN.match(name):
                diagnostics.append(self.emit_diagnostic(
                    code="E5006", severity="error", stage=stage,
                    message=f"Device name '{name}' contains invalid characters",
                    path=f"devices[{idx}].name",
                    source_file=ctx.source_file,
                    hint="Allowed: a-z, 0-9, underscore, hyphen",
                ))

            elif name in seen_names:
                diagnostics.append(self.emit_diagnostic(
                    code="E5007", severity="error", stage=stage,
                    message=f"Duplicate device name '{name}'",
                    path=f"devices[{idx}].name",
                    source_file=ctx.source_file,
                ))

            else:
                seen_names.add(name)

        return self.make_result(
            diagnostics,
            output_data={"total_checked": len(devices)},
        )
```

**Manifest entry:**

```yaml
plugins:
  - id: obj.mikrotik.validator.yaml.device_names
    kind: validator_yaml
    entry: plugins/validators/device_names.py:MikrotikDeviceNamesValidator
    api_version: "1.x"
    stages: [validate]
    phase: run
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
    when:
      profiles: [production, modeled]
    description: "Validate MikroTik device name conventions (length, pattern, uniqueness)"
```

**Tests:**

```python
import pytest
from kernel.plugin_base import PluginContext, Stage, PluginStatus

from plugins.validators.device_names import MikrotikDeviceNamesValidator

PLUGIN_ID = "obj.mikrotik.validator.yaml.device_names"


@pytest.fixture
def make_ctx():
    def _make(devices, *, config=None):
        return PluginContext(
            topology_path="test/topology.yaml",
            profile="production",
            model_lock={},
            raw_yaml={"devices": devices},
            source_file="topology/objects/mikrotik/devices.yaml",
            config=config or {"max_name_length": 63},
        )
    return _make


class TestDeviceNamesValidator:
    def test_valid_names(self, make_ctx):
        ctx = make_ctx([
            {"name": "router1"},
            {"name": "device-a"},
            {"name": "r1_backup"},
        ])
        result = MikrotikDeviceNamesValidator(PLUGIN_ID).execute(ctx, Stage.VALIDATE)
        assert result.status == PluginStatus.SUCCESS
        assert len(result.diagnostics) == 0

    def test_name_too_long(self, make_ctx):
        ctx = make_ctx(
            [{"name": "a" * 64}],
            config={"max_name_length": 63},
        )
        result = MikrotikDeviceNamesValidator(PLUGIN_ID).execute(ctx, Stage.VALIDATE)
        assert result.has_errors
        assert result.diagnostics[0].code == "E5005"

    def test_invalid_characters(self, make_ctx):
        ctx = make_ctx([{"name": "Router@1"}, {"name": "device name"}])
        result = MikrotikDeviceNamesValidator(PLUGIN_ID).execute(ctx, Stage.VALIDATE)
        assert result.has_errors
        assert all(d.code == "E5006" for d in result.diagnostics)

    def test_duplicate_names(self, make_ctx):
        ctx = make_ctx([{"name": "router1"}, {"name": "router2"}, {"name": "router1"}])
        result = MikrotikDeviceNamesValidator(PLUGIN_ID).execute(ctx, Stage.VALIDATE)
        assert any(d.code == "E5007" for d in result.diagnostics)

    def test_missing_name_field(self, make_ctx):
        ctx = make_ctx([{"name": "router1"}, {"model": "RB4011"}])
        result = MikrotikDeviceNamesValidator(PLUGIN_ID).execute(ctx, Stage.VALIDATE)
        assert any(d.code == "E5003" for d in result.diagnostics)
        assert result.diagnostics[-1].hint is not None

    def test_diagnostics_have_source_location(self, make_ctx):
        ctx = make_ctx([{"name": "bad@name"}])
        result = MikrotikDeviceNamesValidator(PLUGIN_ID).execute(ctx, Stage.VALIDATE)
        diag = result.diagnostics[0]
        assert diag.source_file == "topology/objects/mikrotik/devices.yaml"
        assert diag.path == "devices[0].name"
```

---

## Example 2: Compiler Plugin with Data Exchange

**Use case:** Build a device reference index during compilation and publish it
for downstream validators.

**File:** `topology/object-modules/mikrotik/plugins/compilers/resolve_device_refs.py`

```python
"""
Compiler plugin that:
1. Builds a device name → ID index
2. Resolves symbolic device references in interfaces
3. Publishes the index for downstream validators
"""

import copy

from kernel.plugin_base import (
    CompilerPlugin, PluginContext, PluginResult, Stage,
)


class MikrotikDeviceRefResolver(CompilerPlugin):
    """Resolve symbolic device references to device IDs."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        model = copy.deepcopy(ctx.compiled_json)

        # Step 1: Build device index {name: id}
        device_index: dict[str, str] = {}
        for device in model.get("devices", []):
            name = device.get("name")
            device_id = device.get("id")

            if not name or not device_id:
                diagnostics.append(self.emit_diagnostic(
                    code="E3001", severity="error", stage=stage,
                    message=f"Device missing 'name' or 'id': {device}",
                    path="devices",
                ))
                return self.make_result(diagnostics)

            if name in device_index:
                diagnostics.append(self.emit_diagnostic(
                    code="E3002", severity="error", stage=stage,
                    message=f"Duplicate device name: {name}",
                    path=f"devices.{name}",
                ))
                return self.make_result(diagnostics)

            device_index[name] = device_id

        # Step 2: Resolve interface references
        for interface in model.get("interfaces", []):
            if "device" in interface and "device_id" not in interface:
                device_name = interface["device"]
                if device_name in device_index:
                    interface["device_id"] = device_index[device_name]
                else:
                    diagnostics.append(self.emit_diagnostic(
                        code="E3003", severity="error", stage=stage,
                        message=f"Interface references unknown device: {device_name}",
                        path=f"interfaces.{interface.get('name', '?')}",
                        hint=f"Known devices: {', '.join(sorted(device_index.keys()))}",
                    ))

        # Step 3: Publish for downstream validators
        ctx.publish("device_index", device_index)

        return self.make_result(
            diagnostics,
            output_data=model,
        )
```

**Downstream validator consuming published data:**

```python
# topology/object-modules/mikrotik/plugins/validators/interface_refs.py

from kernel.plugin_base import (
    ValidatorJsonPlugin, PluginContext, PluginResult, Stage,
    PluginDataExchangeError,
)


class MikrotikInterfaceRefValidator(ValidatorJsonPlugin):
    """Validate interface references using the device index from compilation."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        try:
            device_index = ctx.subscribe(
                "obj.mikrotik.compiler.resolve_device_refs",
                "device_index",
            )
        except PluginDataExchangeError as exc:
            diagnostics.append(self.emit_diagnostic(
                code="E6901", severity="error", stage=stage,
                message=f"Cannot read device index: {exc}",
                path="pipeline:data_bus",
            ))
            return self.make_result(diagnostics)

        valid_ids = set(device_index.values())
        for interface in ctx.compiled_json.get("interfaces", []):
            device_id = interface.get("device_id")
            if device_id and device_id not in valid_ids:
                diagnostics.append(self.emit_diagnostic(
                    code="E5101", severity="error", stage=stage,
                    message=f"Interface references invalid device_id: {device_id}",
                    path=f"interfaces.{interface.get('name', '?')}",
                ))

        return self.make_result(diagnostics)
```

**Manifest entries:**

```yaml
plugins:
  # Compiler: publishes device_index
  - id: obj.mikrotik.compiler.resolve_device_refs
    kind: compiler
    entry: plugins/compilers/resolve_device_refs.py:MikrotikDeviceRefResolver
    api_version: "1.x"
    stages: [compile]
    phase: run
    order: 60
    depends_on: []
    produces:
      - key: device_index
        scope: pipeline_shared
        description: "Device name-to-ID mapping for downstream consumers"
    description: "Build device reference index and resolve symbolic references"

  # Validator: consumes device_index
  - id: obj.mikrotik.validator.json.interface_refs
    kind: validator_json
    entry: plugins/validators/interface_refs.py:MikrotikInterfaceRefValidator
    api_version: "1.x"
    stages: [validate]
    phase: run
    order: 110
    depends_on:
      - obj.mikrotik.compiler.resolve_device_refs
    consumes:
      - from_plugin: obj.mikrotik.compiler.resolve_device_refs
        key: device_index
        required: true
    description: "Validate interface device references against compiled device index"
```

---

## Example 3: Generator Plugin — Terraform Configuration

**Use case:** Generate Terraform `.tf` files from the compiled topology model.

**File:** `topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py`

```python
"""
Generate Terraform configuration for MikroTik RouterOS.

Produces:
- versions.tf  (provider requirements)
- provider.tf  (provider configuration)
- bridges.tf   (bridge resources, if bridges exist)
"""

from pathlib import Path

from kernel.plugin_base import (
    GeneratorPlugin, PluginContext, PluginResult, Stage,
)


class TerraformMikrotikGenerator(GeneratorPlugin):
    """Generate Terraform MikroTik configuration files."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []
        out_dir = Path(ctx.output_dir) / "terraform" / "mikrotik"
        out_dir.mkdir(parents=True, exist_ok=True)

        tf_version = ctx.config.get("terraform_version", ">= 1.6.0")
        provider_source = ctx.config.get("mikrotik_provider_source", "terraform-routeros/routeros")
        provider_version = ctx.config.get("mikrotik_provider_version", "~> 1.40")

        generated_files: list[str] = []

        # versions.tf
        versions_content = self._render_versions(tf_version, provider_source, provider_version)
        versions_path = out_dir / "versions.tf"
        versions_path.write_text(versions_content)
        generated_files.append(str(versions_path))

        # provider.tf
        api_host = ctx.config.get("mikrotik_api_host", "")
        provider_content = self._render_provider(api_host)
        provider_path = out_dir / "provider.tf"
        provider_path.write_text(provider_content)
        generated_files.append(str(provider_path))

        # bridges.tf (conditional)
        bridges = ctx.compiled_json.get("bridges", [])
        if bridges:
            bridges_content = self._render_bridges(bridges)
            bridges_path = out_dir / "bridges.tf"
            bridges_path.write_text(bridges_content)
            generated_files.append(str(bridges_path))

        # Publish file list for artifact_manifest
        ctx.publish("generated_files", generated_files)
        ctx.publish("terraform_mikrotik_files", generated_files)

        return self.make_result(
            diagnostics,
            output_data={"files": generated_files, "count": len(generated_files)},
        )

    def _render_versions(self, tf_version: str, source: str, version: str) -> str:
        return (
            f'terraform {{\n'
            f'  required_version = "{tf_version}"\n'
            f'  required_providers {{\n'
            f'    routeros = {{\n'
            f'      source  = "{source}"\n'
            f'      version = "{version}"\n'
            f'    }}\n'
            f'  }}\n'
            f'}}\n'
        )

    def _render_provider(self, api_host: str) -> str:
        host_line = f'  hosturl = var.mikrotik_host\n' if not api_host else f'  hosturl = "{api_host}"\n'
        return (
            f'provider "routeros" {{\n'
            f'{host_line}'
            f'  username = var.mikrotik_user\n'
            f'  password = var.mikrotik_password\n'
            f'}}\n'
        )

    def _render_bridges(self, bridges: list[dict]) -> str:
        blocks = []
        for bridge in bridges:
            name = bridge.get("name", "unnamed")
            vlan_filtering = str(bridge.get("vlan_filtering", False)).lower()
            blocks.append(
                f'resource "routeros_interface_bridge" "{name}" {{\n'
                f'  name           = "{name}"\n'
                f'  vlan_filtering = {vlan_filtering}\n'
                f'}}\n'
            )
        return "\n".join(blocks)
```

**Manifest entry:**

```yaml
plugins:
  - id: base.generator.terraform_mikrotik
    kind: generator
    entry: plugins/generators/terraform_mikrotik_generator.py:TerraformMikrotikGenerator
    api_version: "1.x"
    stages: [generate]
    phase: run
    order: 220
    depends_on: []
    config:
      terraform_version: ">= 1.6.0"
      mikrotik_provider_source: "terraform-routeros/routeros"
      mikrotik_provider_version: "~> 1.40"
      mikrotik_api_host: ""
    config_schema:
      type: object
      properties:
        terraform_version:
          type: string
        mikrotik_provider_source:
          type: string
        mikrotik_provider_version:
          type: string
        mikrotik_api_host:
          type: string
    produces:
      - key: generated_files
        scope: pipeline_shared
        description: "List of all generated file paths"
      - key: terraform_mikrotik_files
        scope: pipeline_shared
        description: "MikroTik Terraform file paths"
    description: "Generate Terraform configuration for MikroTik RouterOS"
```

**Tests:**

```python
import json
from pathlib import Path

import pytest
from kernel.plugin_base import PluginContext, Stage, PluginStatus

from plugins.generators.terraform_mikrotik_generator import TerraformMikrotikGenerator

PLUGIN_ID = "base.generator.terraform_mikrotik"


@pytest.fixture
def gen_ctx(tmp_path):
    return PluginContext(
        topology_path="test/topology.yaml",
        profile="production",
        model_lock={},
        compiled_json={
            "bridges": [
                {"name": "br-lan", "vlan_filtering": True},
                {"name": "br-guest", "vlan_filtering": False},
            ]
        },
        output_dir=str(tmp_path / "generated"),
        config={
            "terraform_version": ">= 1.6.0",
            "mikrotik_provider_source": "terraform-routeros/routeros",
            "mikrotik_provider_version": "~> 1.40",
            "mikrotik_api_host": "",
        },
    )


class TestTerraformMikrotikGenerator:
    def test_generates_all_files(self, gen_ctx, tmp_path):
        plugin = TerraformMikrotikGenerator(PLUGIN_ID)
        result = plugin.execute(gen_ctx, Stage.GENERATE)

        assert result.status == PluginStatus.SUCCESS
        out_dir = tmp_path / "generated" / "terraform" / "mikrotik"
        assert (out_dir / "versions.tf").exists()
        assert (out_dir / "provider.tf").exists()
        assert (out_dir / "bridges.tf").exists()

    def test_versions_tf_content(self, gen_ctx, tmp_path):
        TerraformMikrotikGenerator(PLUGIN_ID).execute(gen_ctx, Stage.GENERATE)

        content = (tmp_path / "generated" / "terraform" / "mikrotik" / "versions.tf").read_text()
        assert 'terraform-routeros/routeros' in content
        assert '~> 1.40' in content

    def test_bridges_tf_has_resources(self, gen_ctx, tmp_path):
        TerraformMikrotikGenerator(PLUGIN_ID).execute(gen_ctx, Stage.GENERATE)

        content = (tmp_path / "generated" / "terraform" / "mikrotik" / "bridges.tf").read_text()
        assert 'resource "routeros_interface_bridge" "br-lan"' in content
        assert "vlan_filtering = true" in content

    def test_no_bridges_skips_file(self, gen_ctx, tmp_path):
        gen_ctx.compiled_json = {"bridges": []}
        TerraformMikrotikGenerator(PLUGIN_ID).execute(gen_ctx, Stage.GENERATE)

        assert not (tmp_path / "generated" / "terraform" / "mikrotik" / "bridges.tf").exists()

    def test_publishes_file_list(self, gen_ctx):
        plugin = TerraformMikrotikGenerator(PLUGIN_ID)
        plugin.execute(gen_ctx, Stage.GENERATE)

        published = gen_ctx._published_data.get(PLUGIN_ID, {})
        assert "generated_files" in published
        assert "terraform_mikrotik_files" in published
        assert len(published["generated_files"]) == 3
```

---

## Example 4: Multi-Phase Compiler Plugin

**Use case:** A compiler plugin that uses `init` to load external data and `run`
to perform the actual compilation. Demonstrates the phase handler protocol.

```python
"""
Multi-phase compiler plugin:
- init: load external capability definitions
- run:  resolve capabilities per instance
- verify: validate all required capabilities are satisfied
"""

from kernel.plugin_base import (
    CompilerPlugin, PluginContext, PluginResult, Stage,
)


class CapabilityResolver(CompilerPlugin):
    """Resolve instance capabilities from class/object definitions."""

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Load capability catalog from framework data."""
        catalog = ctx.capability_catalog
        if not catalog:
            return self.make_result([self.emit_diagnostic(
                code="E3101", severity="warning", stage=stage,
                message="No capability catalog found, skipping resolution",
                path="capability_catalog",
            )])

        ctx.publish("capability_catalog_loaded", {
            "count": len(catalog),
            "names": list(catalog.keys()),
        })
        return self.make_result([])

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Resolve capabilities for each instance (called during 'run' phase)."""
        diagnostics = []
        catalog = ctx.capability_catalog
        resolved: dict[str, list[str]] = {}

        for inst_id, inst in ctx.compiled_json.get("instances", {}).items():
            object_ref = inst.get("object_ref", "")
            obj_caps = ctx.objects.get(object_ref, {}).get("capabilities", [])

            valid_caps = []
            for cap in obj_caps:
                if cap in catalog:
                    valid_caps.append(cap)
                else:
                    diagnostics.append(self.emit_diagnostic(
                        code="E3102", severity="warning", stage=stage,
                        message=f"Instance '{inst_id}' references unknown capability '{cap}'",
                        path=f"instances.{inst_id}.capabilities",
                        hint=f"Known capabilities: {', '.join(sorted(catalog.keys()))}",
                    ))

            resolved[inst_id] = valid_caps

        ctx.publish("resolved_capabilities", resolved)
        return self.make_result(diagnostics)

    def on_verify(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        """Verify required capabilities are satisfied."""
        diagnostics = []
        resolved = ctx.subscribe(self.plugin_id, "resolved_capabilities")

        for inst_id, caps in resolved.items():
            inst = ctx.compiled_json.get("instances", {}).get(inst_id, {})
            required = inst.get("required_capabilities", [])
            missing = [r for r in required if r not in caps]

            if missing:
                diagnostics.append(self.emit_diagnostic(
                    code="E3103", severity="error", stage=stage,
                    message=f"Instance '{inst_id}' missing required capabilities: {missing}",
                    path=f"instances.{inst_id}.required_capabilities",
                ))

        return self.make_result(diagnostics)
```

**Manifest entry:**

```yaml
plugins:
  - id: base.compiler.capability_resolver
    kind: compiler
    entry: compilers/capability_resolver.py:CapabilityResolver
    api_version: "1.x"
    stages: [compile]
    phase: init    # Note: plugin handles init, run, and verify phases
    order: 45
    depends_on: []
    produces:
      - key: capability_catalog_loaded
        scope: stage_local
        description: "Catalog load confirmation (init phase)"
      - key: resolved_capabilities
        scope: pipeline_shared
        description: "Per-instance resolved capability lists"
    description: "Multi-phase capability resolution: load, resolve, verify"
```

> **Note:** When a plugin handles multiple phases, declare the **earliest** phase
> in the manifest. The kernel will call `on_init`, then `execute` (for run),
> then `on_verify` automatically based on which handlers are defined.

---

## Example 5: Conditional Validator with `when` Predicates

**Use case:** A validator that only runs for production profile and when a specific
capability is present.

```python
from kernel.plugin_base import (
    ValidatorJsonPlugin, PluginContext, PluginResult, Stage,
)


class ProductionSecurityValidator(ValidatorJsonPlugin):
    """Validate security constraints that apply only in production."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        for inst_id, inst in ctx.compiled_json.get("instances", {}).items():
            # Check firewall is enabled
            if not inst.get("firewall_enabled", False):
                diagnostics.append(self.emit_diagnostic(
                    code="E5201", severity="error", stage=stage,
                    message=f"Instance '{inst_id}' has firewall disabled in production",
                    path=f"instances.{inst_id}.firewall_enabled",
                    hint="Set firewall_enabled: true for production instances",
                ))

            # Check management access is restricted
            mgmt = inst.get("management", {})
            if mgmt.get("allow_all", False):
                diagnostics.append(self.emit_diagnostic(
                    code="E5202", severity="error", stage=stage,
                    message=f"Instance '{inst_id}' allows unrestricted management access",
                    path=f"instances.{inst_id}.management.allow_all",
                    hint="Restrict management access to specific subnets",
                ))

        return self.make_result(diagnostics)
```

**Manifest — note the `when` block:**

```yaml
plugins:
  - id: obj.mikrotik.validator.json.production_security
    kind: validator_json
    entry: plugins/validators/production_security.py:ProductionSecurityValidator
    api_version: "1.x"
    stages: [validate]
    phase: verify    # Runs after all 'run' validators
    order: 180
    depends_on: []
    when:
      profiles: [production]              # Skip for modeled, test-real
      capabilities: [cap.firewall]        # Skip if no firewall capability
    description: "Production-only security constraint validation"
```

When the pipeline runs with `--profile modeled`, this plugin is automatically skipped
with `SKIPPED` status — no code changes needed.

---

## Anti-Patterns to Avoid

### ❌ Mutating shared context

```python
# BAD: Modifying compiled_json directly
def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
    ctx.compiled_json["my_data"] = computed_value  # Race condition under parallelism!
```

**Fix:** Use `ctx.publish()` for data sharing, or work on a deep copy.

### ❌ Constructing PluginResult manually

```python
# BAD: Manual result construction (verbose, error-prone)
return PluginResult(
    plugin_id=self.plugin_id,
    api_version="1.x",
    status=PluginStatus.FAILED,
    duration_ms=0,
    diagnostics=diagnostics,
)
```

**Fix:** Use `self.make_result(diagnostics)` — it infers status automatically.

### ❌ Importing other plugins directly

```python
# BAD: Tight coupling between plugins
from plugins.compilers.resolve_device_refs import MikrotikDeviceRefResolver
device_index = MikrotikDeviceRefResolver.build_index(data)
```

**Fix:** Use `ctx.subscribe("plugin_id", "key")` with declared `consumes`.

### ❌ Catching all exceptions silently

```python
# BAD: Swallowing errors
try:
    self._validate(data)
except Exception:
    pass  # Silent failure — kernel can't report the problem
```

**Fix:** Let unexpected exceptions propagate — the kernel wraps them into `FAILED`
with a full traceback.

### ❌ Writing to undeclared paths

```python
# BAD: Side-channel output
Path("/tmp/debug_output.json").write_text(json.dumps(data))
```

**Fix:** Write only to `ctx.output_dir` subdirectories and declare paths in `produces`.

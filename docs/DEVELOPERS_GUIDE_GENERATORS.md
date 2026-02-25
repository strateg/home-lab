# Generators Developer Guide

**Version:** 1.0
**Last Updated:** 2026-02-25
**Status:** Active

## Overview

This guide explains how to work with and extend the topology generators in `topology-tools/scripts/generators/`.

Generators transform the topology v4.0 YAML into various outputs:
- **Documentation**: Mermaid diagrams, tables, network documentation
- **Terraform**: Infrastructure-as-code configurations for Proxmox, MikroTik
- **Ansible**: (future) Inventory and playbooks

## Architecture

### Directory Structure

```
topology-tools/scripts/generators/
├── types/                    # Type definitions (NEW in Phase 1)
│   ├── __init__.py
│   ├── generators.py         # DeviceSpec, NetworkConfig, etc.
│   └── topology.py           # TopologyV4Structure, L0-L7 types
├── common/                   # Shared utilities
│   ├── __init__.py
│   ├── base.py              # Generator protocol, GeneratorCLI
│   ├── topology.py          # Topology loading, caching
│   └── ip_resolver.py       # IP address resolution
├── docs/                     # Documentation generator
│   ├── generator.py         # Main generator (1068 LOC - to be split)
│   ├── docs_diagram.py      # Diagram generation
│   └── cli.py               # CLI entry point
├── terraform/               # Terraform generators
│   ├── base.py              # Shared base class
│   ├── resolvers.py         # Shared Terraform resolvers
│   ├── proxmox/             # Proxmox-specific
│   │   ├── generator.py
│   │   └── cli.py
│   └── mikrotik/            # MikroTik-specific
│       ├── generator.py
│       └── cli.py
└── __init__.py
```

### Core Concepts

#### 1. Generator Protocol

All generators must implement the `Generator` protocol:

```python
from scripts.generators.common.base import Generator

class MyGenerator:
    topology_path: Path
    output_dir: Path
    topology: Dict[str, Any]

    def load_topology(self) -> bool:
        """Load and validate topology."""
        ...

    def generate_all(self) -> bool:
        """Generate all output files."""
        ...

    def print_summary(self) -> None:
        """Print generation summary."""
        ...
```

#### 2. GeneratorCLI Base Class

Use `GeneratorCLI` for consistent CLI behavior:

```python
from scripts.generators.common.base import GeneratorCLI, run_cli

class MyGeneratorCLI(GeneratorCLI):
    description = "Generate my custom output"
    banner = "My Generator v1.0"
    default_output = "generated/my-output"
    success_message = "My generation completed!"

if __name__ == "__main__":
    cli = MyGeneratorCLI(MyGenerator)
    exit(run_cli(cli))
```

#### 3. Type System (NEW)

Use typed structures instead of `Dict[str, Any]`:

```python
from scripts.generators.types import (
    TopologyV4Structure,
    DeviceSpec,
    NetworkConfig,
    ResourceSpec,
    L1Foundation,
)

def process_device(device: DeviceSpec) -> None:
    device_id: str = device["id"]
    device_type: str = device["type"]
    # IDE now provides autocomplete and type checking!
```

#### 4. Topology Loading

Use the caching loader for better performance:

```python
from scripts.generators.common.topology import (
    load_topology_cached,
    load_and_validate_layered_topology,
)

# Simple load with cache
topology = load_topology_cached("topology.yaml")

# Load with validation
topology, warning = load_and_validate_layered_topology(
    "topology.yaml",
    required_sections=["L0_meta", "L1_foundation", "L2_network"],
    expected_version_prefix="4.",
)
```

#### 5. Terraform Base & Resolvers (Phase 3)

Terraform generators now share a base class and resolver helpers:

```python
from scripts.generators.terraform.base import TerraformGeneratorBase
from scripts.generators.terraform.resolvers import build_storage_map, resolve_lxc_resources

class MyTerraformGenerator(TerraformGeneratorBase):
    def load_topology(self) -> bool:
        return super().load_topology(
            required_sections=["L0_meta", "L1_foundation", "L2_network"],
        )

    def generate(self) -> bool:
        storage_map = build_storage_map(self.topology, platform="proxmox")
        lxc = resolve_lxc_resources(self.topology, self.topology["L4_platform"].get("lxc", []))
        return self.render_template("terraform/proxmox/lxc.tf.j2", "lxc.tf", {
            "storage_map": storage_map,
            "lxc_containers": lxc,
            "topology_version": self.topology_version,
        })
```

#### 6. GeneratorContext & Modern IP Resolution (Phase 4)

Phase 4 introduces dependency injection and modern IP resolution:

**Using GeneratorContext:**
```python
from scripts.generators.common import GeneratorConfig, GeneratorContext
from pathlib import Path

# Create context
config = GeneratorConfig(
    topology_path=Path("topology.yaml"),
    output_dir=Path("generated"),
    templates_dir=Path("templates"),
    verbose=True,
)
context = GeneratorContext(config=config)

# Lazy-loaded services
topology = context.topology
ip_resolver = context.ip_resolver

# Structured logging
context.log_info("Starting generation...")
context.log_verbose("Debug info...")  # Only if verbose=True
context.log_warn("Warning message")

# Selective generation
if context.should_generate("bridges"):
    generate_bridges()
```

**Modern IP Resolution:**
```python
from scripts.generators.common import IpRef, IpResolverV2

# Type-safe IP resolution
resolver = IpResolverV2(topology)

# Create typed reference
ref = IpRef(lxc_ref="lxc-app-1", network_ref="net-mgmt")
resolved = resolver.resolve(ref)

if resolved:
    print(f"IP: {resolved.ip_without_cidr}")
    print(f"Source: {resolved.source_type}/{resolved.source_id}")
    print(f"Network: {resolved.network_ref}")

# Backward compatibility
resolved = resolver.resolve_dict({
    "lxc_ref": "lxc-app-1",
    "network_ref": "net-mgmt"
})
```

## How to Add a New Generator

### Step 1: Create Generator Class

```python
# topology-tools/scripts/generators/my_generator/generator.py

from pathlib import Path
from typing import Dict, Any, List
from scripts.generators.common.base import Generator
from scripts.generators.common.topology import load_and_validate_layered_topology
from scripts.generators.types import TopologyV4Structure, DeviceSpec

class MyGenerator:
    """Generate custom output from topology v4.0."""

    def __init__(
        self,
        topology_path: str,
        output_dir: str,
        templates_dir: str = "topology-tools/templates",
    ):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        self.topology: Dict[str, Any] = {}
        self.generated_files: List[str] = []

    def load_topology(self) -> bool:
        """Load and validate topology."""
        try:
            self.topology, warning = load_and_validate_layered_topology(
                self.topology_path,
                required_sections=["L0_meta", "L1_foundation"],
            )
            if warning:
                print(f"WARN {warning}")
            return True
        except Exception as e:
            print(f"ERROR Failed to load topology: {e}")
            return False

    def generate_all(self) -> bool:
        """Generate all outputs."""
        try:
            self._prepare_output()
            self._generate_main_file()
            self._generate_additional_files()
            return True
        except Exception as e:
            print(f"ERROR Generation failed: {e}")
            return False

    def print_summary(self) -> None:
        """Print summary of generated files."""
        print(f"\nGenerated {len(self.generated_files)} files:")
        for file_path in self.generated_files:
            print(f"  - {file_path}")

    def _prepare_output(self) -> None:
        """Prepare output directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_main_file(self) -> None:
        """Generate main output file."""
        output_file = self.output_dir / "output.txt"
        output_file.write_text("Generated content")
        self.generated_files.append(str(output_file))

    def _generate_additional_files(self) -> None:
        """Generate additional files as needed."""
        pass
```

### Step 2: Create CLI Entry Point

```python
# topology-tools/scripts/generators/my_generator/cli.py

from scripts.generators.common.base import GeneratorCLI, run_cli
from .generator import MyGenerator

class MyGeneratorCLI(GeneratorCLI):
    description = "Generate custom output from topology v4.0"
    banner = "My Custom Generator v1.0"
    default_output = "generated/my-output"
    success_message = "Custom generation completed successfully!"

    def add_extra_arguments(self, parser):
        """Add generator-specific arguments."""
        parser.add_argument(
            "--format",
            choices=["json", "yaml", "txt"],
            default="txt",
            help="Output format",
        )

    def create_generator(self, args):
        """Create generator with custom args."""
        gen = MyGenerator(args.topology, args.output, args.templates)
        gen.output_format = args.format  # Pass custom arg
        return gen

def main():
    cli = MyGeneratorCLI(MyGenerator)
    return run_cli(cli)

if __name__ == "__main__":
    exit(main())
```

### Step 3: Add Tests

```python
# tests/unit/generators/test_my_generator.py

import pytest
from scripts.generators.my_generator.generator import MyGenerator

class TestMyGenerator:
    def test_load_topology(self, temp_topology_file, temp_output_dir):
        """Test topology loading."""
        gen = MyGenerator(
            str(temp_topology_file),
            str(temp_output_dir),
        )

        assert gen.load_topology() is True
        assert "L0_meta" in gen.topology

    def test_generate_all(self, temp_topology_file, temp_output_dir):
        """Test generation."""
        gen = MyGenerator(
            str(temp_topology_file),
            str(temp_output_dir),
        )
        gen.load_topology()

        assert gen.generate_all() is True
        assert len(gen.generated_files) > 0
```

### Step 4: Register Generator (Optional)

If creating a standard generator, add it to the main CLI or regenerate script.

## Best Practices

### 1. Use Type Hints

```python
# Bad
def process_device(device: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": device["id"]}

# Good
from scripts.generators.types import DeviceSpec

def process_device(device: DeviceSpec) -> dict[str, str]:
    return {"id": device["id"]}
```

### 2. Validate Inputs Early

```python
def generate_all(self) -> bool:
    if not self.topology:
        print("ERROR Topology not loaded")
        return False

    required_layer = self.topology.get("L1_foundation")
    if not required_layer:
        print("ERROR Missing L1_foundation layer")
        return False

    # Continue with generation...
```

### 3. Use Caching

```python
from scripts.generators.common.topology import load_topology_cached

# This is faster on repeated calls
topology = load_topology_cached("topology.yaml")
```

### 4. Handle Errors Gracefully

```python
def generate_all(self) -> bool:
    try:
        self._generate_files()
        return True
    except FileNotFoundError as e:
        print(f"ERROR Template not found: {e}")
        return False
    except Exception as e:
        print(f"ERROR Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
```

### 5. Write Tests First

Follow TDD when possible:
1. Write test for new feature
2. Run test (it should fail)
3. Implement feature
4. Run test (it should pass)

## Testing

### Run All Generator Tests

```cmd
pytest tests/unit/generators/
```

### Run Specific Test Module

```cmd
pytest tests/unit/generators/test_base.py
```

### Run With Coverage

```cmd
pytest tests/unit/generators/ --cov=scripts.generators --cov-report=html
```

### Using Fixtures

```python
def test_with_fixtures(temp_topology_file, temp_output_dir, generator_config_basic):
    """Use provided fixtures."""
    assert temp_topology_file.exists()
    assert temp_output_dir.exists()
    assert "topology_path" in generator_config_basic
```

## Common Patterns

### Pattern 1: Template-Based Generation

```python
from jinja2 import Environment, FileSystemLoader

self.jinja_env = Environment(
    loader=FileSystemLoader(str(self.templates_dir)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)

template = self.jinja_env.get_template("my_template.j2")
content = template.render(topology=self.topology, devices=devices)
```

### Pattern 2: Incremental File Generation

```python
def generate_all(self) -> bool:
    self._prepare_output()

    for section in self._get_sections():
        if not self._generate_section(section):
            return False

    return True
```

### Pattern 3: Progress Reporting

```python
def generate_all(self) -> bool:
    sections = self._get_sections()
    total = len(sections)

    for i, section in enumerate(sections, 1):
        print(f"GEN [{i}/{total}] Generating {section}...")
        self._generate_section(section)

    return True
```

## Troubleshooting

### Import Errors

If you get import errors, ensure your Python path includes the repo root:

```cmd
set PYTHONPATH=c:\Users\Dmitri\PycharmProjects\home-lab
```

### Type Checking

Run mypy to check types:

```cmd
mypy topology-tools/scripts/generators/
```

### Cache Issues

Clear topology cache if seeing stale data:

```python
from scripts.generators.common.topology import clear_topology_cache
clear_topology_cache("topology.yaml")
```

## Future Work

See `docs/github_analysis/GENERATORS_REFACTORING_SUMMARY.md` for planned improvements:
- Phase 2: Split monolithic docs generator
- Phase 3: Unify Terraform generators
- Phase 4: Improve common modules
- Phase 5: Add configurability
- Phase 6: Performance and polish

## References

- ADR-0046: Generators Architecture Refactoring
- `GENERATORS_REFACTORING_SUMMARY.md`: Detailed analysis
- `GENERATORS_PHASE1_IMPLEMENTATION.md`: Implementation plan
- Generator tests: `tests/unit/generators/`

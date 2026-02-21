# ADR-0025: Generator Protocol and CLI Base Class

## Status

Accepted

## Date

2026-02-21

## Context

After the modular refactor of topology-tools (ADR-0017 through ADR-0024), the codebase had three independent CLI modules (`proxmox/cli.py`, `mikrotik/cli.py`, `docs/cli.py`) with significant code duplication:

- Each CLI repeated the same argument parsing logic (`--topology`, `--output`, `--templates`)
- Each CLI had identical banner printing and error handling patterns
- Generators lacked a formal interface contract, making it unclear what methods were required
- Type hint coverage was at 81%, with several public functions missing return annotations
- `__init__.py` files were minimal, forcing users to know internal module paths

### Problems Identified

1. **CLI Duplication**: ~60% of CLI code was identical across modules
2. **No Generator Contract**: Duck typing without explicit protocol
3. **Poor Discoverability**: Empty `__init__.py` files required deep import paths
4. **Incomplete Type Hints**: 7 public functions lacked return type annotations

## Decision

### 1. Introduce Generator Protocol

Create a `@runtime_checkable` Protocol in `scripts/generators/common/base.py`:

```python
@runtime_checkable
class Generator(Protocol):
    topology_path: Path
    output_dir: Path
    topology: Dict[str, Any]

    def load_topology(self) -> bool: ...
    def generate_all(self) -> bool: ...
    def print_summary(self) -> None: ...
```

### 2. Create GeneratorCLI Base Class

Extract common CLI logic into a reusable base class:

```python
class GeneratorCLI:
    description: str
    banner: str
    default_output: str
    success_message: str

    def build_parser(self) -> argparse.ArgumentParser: ...
    def add_extra_arguments(self, parser) -> None: ...  # Override hook
    def create_generator(self, args) -> Generator: ...  # Override hook
    def run_generator(self, generator) -> bool: ...     # Override hook
    def main(self, argv) -> int: ...
```

### 3. Populate `__init__.py` with Exports

Add comprehensive exports to all package `__init__.py` files:

- `validators/__init__.py`: Export `collect_ids`
- `validators/checks/__init__.py`: Export all check functions grouped by domain
- `generators/__init__.py`: Export all generators and CLI classes
- Subpackage `__init__.py`: Export generators and CLI entry points

### 4. Complete Type Hint Coverage

Add return type hints to all public functions:
- `print_summary() -> None` in all generators
- Property methods in `docs_diagram.py` with proper return types
- `build_parser() -> argparse.ArgumentParser` in CLI modules

## Consequences

### Positive

- **Reduced Duplication**: CLI modules reduced by 20-42% in line count
- **Explicit Contract**: `Generator` Protocol documents required interface
- **Better IDE Support**: Full type hints enable autocomplete and static analysis
- **Easier Imports**: `from scripts.generators import TerraformGenerator`
- **Extensibility**: New generators inherit CLI boilerplate automatically

### Negative

- **Additional Abstraction**: One more layer to understand
- **Protocol Overhead**: Runtime checkable protocols have minor performance cost

### Metrics

| Metric | Before | After |
|--------|--------|-------|
| CLI Lines (proxmox) | 57 | 33 (-42%) |
| CLI Lines (mikrotik) | 63 | 53 (-16%) |
| CLI Lines (docs) | 90 | 71 (-21%) |
| Public Functions with Type Hints | 81% | 100% |
| `__init__.py` Exports | 3 | 31 |

## Implementation

### Files Created

- `topology-tools/scripts/generators/common/base.py`

### Files Modified

- `topology-tools/scripts/generators/common/__init__.py`
- `topology-tools/scripts/generators/__init__.py`
- `topology-tools/scripts/generators/terraform/__init__.py`
- `topology-tools/scripts/generators/terraform/proxmox/__init__.py`
- `topology-tools/scripts/generators/terraform/proxmox/cli.py`
- `topology-tools/scripts/generators/terraform/proxmox/generator.py`
- `topology-tools/scripts/generators/terraform/mikrotik/__init__.py`
- `topology-tools/scripts/generators/terraform/mikrotik/cli.py`
- `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- `topology-tools/scripts/generators/docs/__init__.py`
- `topology-tools/scripts/generators/docs/cli.py`
- `topology-tools/scripts/generators/docs/generator.py`
- `topology-tools/scripts/generators/docs/docs_diagram.py`
- `topology-tools/scripts/validators/__init__.py`
- `topology-tools/scripts/validators/checks/__init__.py`

## References

- ADR-0017: Modular Refactor of topology-tools
- ADR-0020: Co-locate Generation and Validation Under topology-tools/scripts
- Python typing.Protocol: https://docs.python.org/3/library/typing.html#typing.Protocol

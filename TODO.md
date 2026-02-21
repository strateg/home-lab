# TODO: Architectural Improvements

This file tracks planned architectural improvements for the home-lab infrastructure-as-data project.

---

## High Priority

### 1. Topology Caching in Regeneration Pipeline

**Status**: Planned
**Complexity**: Medium
**Impact**: Performance improvement for full regeneration

**Problem**:
Currently `regenerate-all.py` runs each generator as a separate subprocess, causing the topology to be loaded and parsed 5+ times (once per generator).

**Solution**:
Implement shared topology caching:

```python
# Option A: In-memory cache (single process)
class TopologyCache:
    _instance: Dict[str, Any] = None

    @classmethod
    def get(cls, path: str) -> Dict[str, Any]:
        if cls._instance is None:
            cls._instance = load_topology(path)
        return cls._instance

# Option B: File-based cache (multi-process)
# Write parsed topology to .cache/topology.json
# Generators check mtime and use cache if fresh
```

**Files to modify**:
- `topology-tools/regenerate-all.py`
- `topology-tools/scripts/generators/common/topology.py`

**Estimated reduction**: Load time from ~0.5s × 5 = 2.5s → 0.5s (80% faster)

---

### 2. Parallel Generator Execution

**Status**: Planned
**Complexity**: Low
**Impact**: 2-3x faster regeneration

**Problem**:
Generators run sequentially but are completely independent.

**Solution**:
Use `concurrent.futures.ThreadPoolExecutor` or `ProcessPoolExecutor`:

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

generators = [
    ("Terraform (Proxmox)", "generate-terraform-proxmox.py"),
    ("Terraform (MikroTik)", "generate-terraform-mikrotik.py"),
    ("Ansible", "generate-ansible-inventory.py"),
    ("Documentation", "generate-docs.py"),
]

with ProcessPoolExecutor(max_workers=4) as executor:
    futures = {
        executor.submit(run_generator, name, script): name
        for name, script in generators
    }
    for future in as_completed(futures):
        name = futures[future]
        result = future.result()
        print(f"{name}: {'OK' if result == 0 else 'FAILED'}")
```

**Files to modify**:
- `topology-tools/regenerate-all.py`

**Considerations**:
- Validation must complete before generators start
- Output ordering may change (use buffered output per generator)
- Error handling for partial failures

---

### 3. Dry-Run Mode for Generators

**Status**: Planned
**Complexity**: Low
**Impact**: Safer preview of changes

**Problem**:
No way to preview what files would be generated/modified without actually writing them.

**Solution**:
Add `--dry-run` flag to all generators:

```python
class GeneratorCLI:
    def add_extra_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be generated without writing files"
        )

# In generator:
def write_file(self, path: Path, content: str) -> None:
    if self.dry_run:
        print(f"[DRY-RUN] Would write: {path} ({len(content)} bytes)")
        return
    path.write_text(content, encoding="utf-8")
```

**Files to modify**:
- `topology-tools/scripts/generators/common/base.py`
- All generator classes (add `dry_run` parameter)

**Output example**:
```
$ python3 generate-terraform-proxmox.py --dry-run
[DRY-RUN] Would write: generated/terraform/provider.tf (1234 bytes)
[DRY-RUN] Would write: generated/terraform/bridges.tf (567 bytes)
[DRY-RUN] Would write: generated/terraform/lxc.tf (2345 bytes)
...
Summary: 7 files would be written (12.3 KB total)
```

---

## Medium Priority

### 4. Generator Diff Mode

**Status**: Idea
**Complexity**: Medium
**Impact**: Better change visibility

**Problem**:
Hard to see what changed after regeneration without manual `git diff`.

**Solution**:
Add `--diff` flag that shows unified diff of changes:

```python
parser.add_argument(
    "--diff",
    action="store_true",
    help="Show diff of changes instead of writing"
)

# Use difflib.unified_diff() to compare old vs new content
```

---

### 5. Incremental Generation

**Status**: Idea
**Complexity**: High
**Impact**: Much faster for small changes

**Problem**:
Changing one LXC container regenerates all Terraform files.

**Solution**:
Track dependencies and only regenerate affected files:

```yaml
# .cache/generation-manifest.yaml
files:
  generated/terraform/lxc.tf:
    sources:
      - topology/L4-platform.yaml
      - topology/L2-network.yaml  # for bridge refs
    hash: sha256:abc123...
```

**Considerations**:
- Complex dependency tracking
- May not be worth it for current codebase size
- Risk of stale outputs if dependencies missed

---

### 6. Unit Tests for Generators

**Status**: Planned
**Complexity**: Medium
**Impact**: Regression prevention

**Problem**:
No automated tests for generator logic.

**Solution**:
Add pytest-based test suite:

```
topology-tools/tests/
├── conftest.py              # Fixtures (sample topologies)
├── generators/
│   ├── test_proxmox.py
│   ├── test_mikrotik.py
│   └── test_docs.py
└── validators/
    ├── test_storage.py
    └── test_network.py
```

**Test examples**:
```python
def test_proxmox_generates_bridges(sample_topology):
    gen = TerraformGenerator(sample_topology, "/tmp/out")
    gen.load_topology()
    gen.generate_bridges()

    content = (Path("/tmp/out") / "bridges.tf").read_text()
    assert "resource \"proxmox_virtual_environment_network_linux_bridge\"" in content

def test_vlan_tag_validation(sample_topology_with_vlan_mismatch):
    errors = []
    warnings = []
    check_vlan_tags(sample_topology_with_vlan_mismatch, errors=errors, warnings=warnings)
    assert len(errors) == 1
    assert "vlan_tag" in errors[0]
```

---

### 7. Schema Auto-Generation from Python Types

**Status**: Idea
**Complexity**: High
**Impact**: Single source of truth for types

**Problem**:
JSON Schema and Python dataclasses/TypedDicts can drift.

**Solution**:
Use `pydantic` models as source of truth:

```python
from pydantic import BaseModel

class LXCContainer(BaseModel):
    id: str
    name: str
    vmid: int
    template_ref: str
    networks: list[NetworkConfig]

# Auto-generate JSON Schema:
# LXCContainer.model_json_schema()
```

---

## Low Priority

### 8. Generator Plugin System

**Status**: Future
**Complexity**: High
**Impact**: Extensibility

Allow external generators via entry points:

```toml
# pyproject.toml
[project.entry-points."topology_tools.generators"]
custom = "my_package:CustomGenerator"
```

---

### 9. Watch Mode for Development

**Status**: Future
**Complexity**: Medium

Auto-regenerate on topology file changes:

```bash
python3 regenerate-all.py --watch
# Uses watchdog to monitor topology/ directory
```

---

### 10. Generation Metrics Dashboard

**Status**: Future
**Complexity**: Low

Track generation statistics over time:

```yaml
# .cache/metrics.yaml
runs:
  - timestamp: 2026-02-21T15:00:00
    duration_ms: 1920
    files_generated: 24
    topology_version: 4.0.0
```

---

## Completed

- [x] ADR-0025: Generator Protocol and CLI Base Class (2026-02-21)
- [x] 100% type hints for public functions (2026-02-21)
- [x] Comprehensive `__init__.py` exports (2026-02-21)

---

## Notes

- Priorities may shift based on actual pain points encountered
- High-impact/low-complexity items should be tackled first
- Consider ADR for any significant architectural change

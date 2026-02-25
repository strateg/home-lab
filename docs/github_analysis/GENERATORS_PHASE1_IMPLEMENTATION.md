# 🚀 НАЧАЛО РЕФАКТОРИЗАЦИИ ГЕНЕРАТОРОВ - PHASE 1

**Дата:** 25 февраля 2026 г.
**Фаза:** 1 - Подготовка (1 неделя)
**Цель:** Установить фундамент для рефакторизации

---

## 📋 PHASE 1 TASKS

### Task 1.1: Type System Foundation (3 дня)

**Создать структуру типов для генераторов:**

```bash
mkdir -p topology-tools/scripts/generators/types
touch topology-tools/scripts/generators/types/__init__.py
touch topology-tools/scripts/generators/types/generators.py
touch topology-tools/scripts/generators/types/topology.py
```

**types/generators.py содержит:**
```python
from typing import TypedDict, Optional, List

class DeviceSpec(TypedDict):
    id: str
    type: str
    name: str
    class: str
    # ... all fields

class NetworkConfig(TypedDict):
    id: str
    cidr: str
    gateway: str
    # ... all fields

class ResourceSpec(TypedDict):
    cpu: int
    memory_mb: int
    disk_gb: int

class GeneratorConfig(TypedDict):
    topology_path: str
    output_dir: str
    templates_dir: str
    skip_components: List[str]
    dry_run: bool
```

**types/topology.py содержит:**
```python
class TopologyV4Structure(TypedDict):
    L0_meta: Dict[str, Any]
    L1_foundation: Dict[str, Any]
    L2_network: Dict[str, Any]
    # ... all layers
```

**Outcome:** Четкая типизация для IDE и mypy

---

### Task 1.2: Unit Test Foundation (3 дня)

**Создать структуру тестов:**

```bash
mkdir -p tests/unit/generators
mkdir -p tests/unit/generators/fixtures
touch tests/unit/generators/__init__.py
touch tests/unit/generators/conftest.py
touch tests/unit/generators/test_base.py
touch tests/unit/generators/test_common.py
touch tests/unit/generators/fixtures/sample_topology.yaml
```

**conftest.py - pytest fixtures:**
```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_topology():
    """Load sample topology for testing"""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_topology.yaml"
    with open(fixture_path) as f:
        return yaml.safe_load(f)

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for generated files"""
    return tmp_path / "generated"

@pytest.fixture
def generator_config(sample_topology, temp_output_dir):
    """Default generator configuration"""
    return {
        "topology_path": str(sample_topology),
        "output_dir": str(temp_output_dir),
        "templates_dir": "topology-tools/templates",
    }
```

**test_base.py:**
```python
def test_generator_cli_init(generator_config):
    from scripts.generators.common import GeneratorCLI
    cli = GeneratorCLI(generator_config)
    assert cli is not None

def test_generator_cli_parse_args():
    # Test argument parsing
    pass
```

**Outcome:** Готовая инфраструктура для тестирования

---

### Task 1.3: Documentation & ADR (2 дня)

**Создать ADR для архитектуры генераторов:**

```bash
touch adr/0050-generators-architecture-refactoring.md
```

**Содержание ADR:**
- Проблемы в текущей архитектуре
- Предлагаемые решения
- Этапы реализации
- Обратная совместимость

**Создать Developer Guide:**

```bash
touch docs/DEVELOPERS_GUIDE_GENERATORS.md
```

**Содержание:**
- Architecture overview
- How to add new generator
- Type system usage
- Testing guidelines
- Performance tips

**Outcome:** Ясное понимание архитектуры для команды

---

## ✅ PHASE 1 CHECKLIST

- [ ] Create types/generators.py with TypedDict definitions
- [ ] Create types/topology.py with TopologyV4Structure
- [ ] Create conftest.py with fixtures
- [ ] Create sample_topology.yaml fixture
- [ ] Create test_base.py skeleton tests
- [ ] Create test_common.py skeleton tests
- [ ] Create ADR-0050-generators-architecture-refactoring.md
- [ ] Create DEVELOPERS_GUIDE_GENERATORS.md
- [ ] Run `mypy --config-file pyproject.toml topology-tools/scripts/generators`
- [ ] Run `pytest tests/unit/generators/ -v`
- [ ] Update README.md with new architecture info
- [ ] Create PR with Phase 1 changes

---

## 🎯 PHASE 1 DELIVERABLES

### Code
- ✅ Type system in place (TypedDict for all major structures)
- ✅ Unit test fixtures and infrastructure
- ✅ All generators type-checked with mypy

### Documentation
- ✅ ADR explaining architecture decisions
- ✅ Developer guide for adding new generators
- ✅ Updated README with architecture overview

### Quality
- ✅ Type coverage: 100% for common/base.py
- ✅ Test coverage: 30%+ for common modules
- ✅ Mypy: 0 errors in typed code

---

## 📅 PHASE 1 TIMELINE

```
Week 1 (Mon-Wed): Types & Tests Skeleton
  - Mon: Create types/ and tests/unit/generators/ structure
  - Tue: Write TypedDict definitions
  - Wed: Create pytest fixtures and sample topology

Week 1 (Thu-Fri): Documentation
  - Thu: Write ADR-0050
  - Fri: Write DEVELOPERS_GUIDE, run mypy/pytest

Friday EOD: Create PR and request review
```

---

## 🔧 COMMANDS TO RUN

After Phase 1:

```bash
cd c:\Users\Dmitri\PycharmProjects\home-lab

# Install types in generators
pip install -e .[dev]

# Run type checking (should have <10 errors for non-typed code)
mypy --config-file pyproject.toml topology-tools/scripts/generators/ 2>&1 | head -20

# Run tests (should all pass)
pytest tests/unit/generators/ -v

# Check coverage
pytest tests/unit/generators/ --cov=topology-tools.scripts.generators --cov-report=term-missing

# Create PR
git checkout -b feature/generators-phase1-typing-and-tests
git add topology-tools/scripts/generators/types/
git add tests/unit/generators/
git add adr/0050-generators-architecture-refactoring.md
git add docs/DEVELOPERS_GUIDE_GENERATORS.md
git commit -m "refactor(generators): Phase 1 - type system and test infrastructure"
git push -u origin feature/generators-phase1-typing-and-tests
```

---

## 📚 PHASE 1 PRODUCES

**When Phase 1 complete:**

1. **Type definitions** for all major structures
2. **Test fixtures** for sample topologies
3. **Test infrastructure** (conftest, helper functions)
4. **Architecture documentation** (ADR)
5. **Developer guide** for new generators
6. **Baseline** for future phases

**This enables Phase 2** to safely refactor docs/generator.py with confidence

---

## ⚠️ IMPORTANT NOTES

### Don't break existing functionality
- Phase 1 is **additive only** (no changes to generator logic)
- Existing generators work unchanged
- Type definitions are in `types/` package (separate)

### Type definitions are NOT enforced yet
- Phase 1: Just definitions
- Phase 2+: Gradually apply to actual code
- Old generators can work without types (for now)

### Tests are skeletons
- Phase 1: Just infrastructure
- Phase 2+: Add actual test cases
- Coverage will grow in later phases

---

## 🚀 NEXT STEPS AFTER PHASE 1

Once Phase 1 is done:

1. **Start Phase 2** - Split docs/generator.py
2. **Run mypy on** common/base.py with typed generators
3. **Integrate types** into CI pipeline
4. **Add coverage gates** to tests

---

## 📞 QUESTIONS?

Refer to:
- `GENERATORS_ANALYSIS_AND_REFACTORING_PLAN.md` — Full 6-phase plan
- `GENERATORS_DETAILED_ISSUES.md` — Detailed problem analysis
- `GENERATORS_REFACTORING_SUMMARY.md` — Quick summary

---

**Status:** 🚀 **READY TO START PHASE 1**

Questions? Let's clarify before starting implementation!

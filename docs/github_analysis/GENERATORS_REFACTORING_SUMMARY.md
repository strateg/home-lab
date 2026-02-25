# 🚀 GENERATORS REFACTORING QUICK SUMMARY

**Date:** 25 февраля 2026 г.
**Status:** Analysis Complete

---

## ⚡ TL;DR

**Critical Issues:**
1. ❌ `docs/generator.py` — 1068 строк (слишком большой)
2. ❌ Дублирование кода между Terraform генераторами
3. ❌ Нет unit-тестов
4. ❌ Слабая типизация

**Solution:** 6 фаз рефакторизации (7-9 недель)

---

## 📊 GENERATORS OVERVIEW

```
topology-tools/scripts/generators/
├── common/               # Shared utilities
│   ├── base.py          # Generator & GeneratorCLI protocols
│   ├── topology.py      # Topology loading & caching
│   └── ip_resolver.py   # IP address resolution
├── docs/                # Documentation generator
│   ├── generator.py     # 1068 LOC ❌ CRITICAL
│   ├── docs_diagram.py  # Diagram generation
│   └── cli.py           # CLI entry point
├── terraform/           # Terraform generators
│   ├── base.py          # Base generator class
│   ├── proxmox/         # Proxmox generator (374 LOC)
│   │   ├── generator.py
│   │   └── cli.py
│   └── mikrotik/        # MikroTik generator
│       ├── generator.py
│       └── cli.py
└── __init__.py
```

---

## 🔴 CRITICAL PROBLEMS

| Problem | Location | Severity | Impact |
|---------|----------|----------|--------|
| Монолитный файл | docs/generator.py (1068 LOC) | 🔴 Critical | Невозможно поддерживать |
| Дублирование | terraform/ (proxmox + mikrotik) | 🔴 Critical | Нарушает DRY |
| Нет тестов | All generators | 🔴 Critical | Нельзя рефакторить |
| Слабая типизация | All files | 🟠 High | Много Dict[str, Any] |
| No config | All generators | 🟠 High | Нельзя настроить |
| Icon complexity | docs/generator.py | 🟠 High | Смешанная логика |

---

## ✅ REFACTORING PHASES

### Phase 1: Preparation (1 week)
- Add type hints (TypedDict for topology structures)
- Add unit-tests skeleton
- Document architecture in ADR

### Phase 2: Split docs/generator.py (2 weeks)
- Extract `DiagramGenerator` class
- Extract `IconManager` class
- Extract `TemplateManager` class
- Result: ~500 LOC instead of 1068

### Phase 3: Unify Terraform (1-2 weeks)
- Create `TerraformGeneratorBase`
- Create `ResourceResolver` (shared)
- Create `TemplateBuilder` (shared)
- Both proxmox & mikrotik inherit from base

### Phase 4: Improve commons (1 week)
- Refactor IP resolution (dataclasses)
- Add GeneratorContext for DI
- Thread-safe caching

### Phase 5: Configurability (1-2 weeks)
- Add generator config system
- Add `--dry-run`, `--verbose`, `--components`
- Add progress indicators

### Phase 6: Polish (1 week)
- CI/CD integration
- Documentation
- Performance optimization

---

## 🎯 EXPECTED RESULTS

After refactoring:

✅ Type coverage: 100% (mypy --strict)
✅ Unit test coverage: >70%
✅ Max file size: <500 LOC
✅ Cyclomatic complexity: <10
✅ No code duplication
✅ Full configurable generation

---

## 📌 NEXT STEPS

**Now (this week):**
1. Review this analysis and plan
2. Decide if start Phase 1 (typing)
3. Assign resources

**Phase 1 (typing & tests):**
```cmd
mkdir -p topology-tools/scripts/generators/types
mkdir -p tests/unit/generators
# Create TypedDict for topology structures
# Create unit-test fixtures
```

**Phase 2 (split docs/generator):**
- Extract diagram logic (500 LOC reduction)
- Extract icon management
- Extract template management

---

## 📚 RELATED DOCUMENTS

- `GENERATORS_ANALYSIS_AND_REFACTORING_PLAN.md` — Full detailed plan
- ADR-00XX (to be created) — Architecture decisions
- `DEVELOPERS_GUIDE_GENERATORS.md` (to be created) — How to add new generator

---

**Status:** 📋 Analysis Complete, Ready for Phase 1

Want to start Phase 1? Let's begin with typing infrastructure!

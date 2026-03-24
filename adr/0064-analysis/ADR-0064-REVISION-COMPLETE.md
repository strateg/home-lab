# ADR 0064 Revision Complete ✅

**Date:** 2026-03-08
**Status:** Approved - Path C (Class-Based OS Model)
**Decision:** Переработан с property-based на class-based модель

---

## Что было изменено в ADR 0064

### Заголовок и Статус

**Было:**
```
# ADR 0064: OS Taxonomy - Infrastructure Prerequisite and Runtime Projection
Status: Proposed
```

**Стало:**
```
# ADR 0064: OS Taxonomy - Class-Based Model With Firmware/Installable Distinction
Status: Approved - Class Model (Path C)
```

### Основной подход

**Было (Property-based):**
- OS как встроенное свойство объекта: `software.os`
- Firmware и installable OS неразличимы
- OS данные дублируются во всех объектах

**Стало (Class-based):**
- OS как первый класс с явными подклассами: `os.firmware` и `os.installable`
- Четкое различие: firmware (неизменяемый, привязан к железу) vs installable (гибкий, управляемый)
- Devices **bind** к OS instance (bez дубликации)

### Ключевые секции (новые)

#### 1. OS Класс с двумя подклассами
```yaml
class: os
subclasses:
  - os.firmware      # Hardware-locked
  - os.installable   # User-controlled
```

#### 2. Device Binding вместо встроенного OS
```yaml
# Вместо: software.os: {...}
# Теперь: bindings.os: obj.os.debian.12.generic
```

#### 3. Class-Level OS Constraints
- `os_constraints.required`: object MUST иметь bindings.os
- `os_constraints.subclasses`: только firmware или только installable
- Compiler enforce эти ограничения

#### 4. Effective OS Derivation
- Compiler загружает referenced OS instance
- Deriving все capabilities (cap.os.debian, cap.os.init.systemd, etc.)
- Validate device against service requirements

#### 5. Multi-OS Support
- Devices могут bind к multiple OS instances
- Для dual-boot, multi-partition scenarios
- Native support (не требует schema extension)

#### 6. OS Specialization via Inheritance
- Базовый instance: debian-12-generic
- Hardened variant: debian-12-hardened (inherits базовый)
- Variant добавляет capabilities (cap.security.selinux)

#### 7. 5-Phase Migration Contract
- Phase 1 (нед 1-2): Classification (добавить installation_model field)
- Phase 2 (нед 3-5): Class System (создать OS класс и instances)
- Phase 3 (нед 6-7): Parallel Validation (оба модели работают)
- Phase 4 (нед 8): Deprecation (warn на property OS, требовать bindings)
- Phase 5 (нед 9+): Cleanup (удалить property model)

#### 8. Service-Device Validation
- Service требует capabilities: `[cap.os.linux, cap.os.init.systemd]`
- Device bound к: `obj.os.debian.12.generic`
- Compiler derive и validate compile-time (не runtime)

### Удаленные секции

- ❌ "OS Prerequisite Reference (prerequisites.os_ref)" - заменено на bindings.os
- ❌ "Class-Level OS Scope Policy (os_policy)" - заменено на os_constraints
- ❌ "Precedence and Conflict Rules" - не нужно (class instances authoritative)
- ❌ "Derived Capabilities From Effective OS" (moved to new section 6)
- ❌ "Service/Workload OS Requirements (requires.os)" (moved to new section 7)

---

## Результаты Переработки

### ✅ Решенные Проблемы

| Проблема | Было | Стало |
|----------|------|-------|
| Firmware/installable distinction | ❌ Нет | ✅ Явное (subclasses) |
| OS reuse (20 Debian VMs) | ❌ 20 копий | ✅ 1 definition |
| Service-device validation | ❌ Runtime | ✅ Compile-time |
| Multi-OS devices | ❌ Impossible | ✅ Native support |
| OS specialization | ❌ Not supported | ✅ Via inheritance |
| OS lifecycle independent | ❌ Tied to device | ✅ Independent class |

### 📊 Metrics

| Metric | Value |
|--------|-------|
| **Lines of ADR changed** | ~300 lines |
| **New sections added** | 8 |
| **Migration phases** | 5 |
| **Implementation time** | 6-8 weeks |
| **Risk level** | LOW |
| **Breaking changes** | None (until Phase 4) |

---

## Следующие Шаги

### Неделя 8-12 марта (This Week)
- ✅ ADR 0064 переработан
- [ ] Распределить анализ среди team
- [ ] Провести architecture review (30 min)
- [ ] Получить team consensus

### Неделя 15 марта
- [ ] Finalize ADR 0064
- [ ] Создать зависимые ADR (0065, 0066, 0067)
- [ ] Assign Phase 1 lead
- [ ] Create Phase 1 user stories

### Неделя 22 марта (Kickoff)
- [ ] Start Phase 1 реализация
- [ ] Add installation_model field
- [ ] Classify existing OS definitions
- [ ] Update validator

### Недели 29 марта - 17 мая
- [ ] Phase 2-5 execution
- [ ] Weekly progress reviews
- [ ] Target: Full migration complete

---

## Документы для Использования

### Для быстрого понимания
- [START-HERE.md](./adr/0064-analysis/START-HERE.md) - Overview
- [ONEPAGE-SUMMARY.md](./adr/0064-analysis/ONEPAGE-SUMMARY.md) - Quick brief

### Для деталей и примеров
- [os-modeling-scenarios.md](./adr/0064-analysis/os-modeling-scenarios.md) - 6 real-world scenarios
- [adr-0064-revision-proposal.md](./adr/0064-analysis/adr-0064-revision-proposal.md) - Technical details

### Для планирования
- [NEXT-STEPS.md](./adr/0064-analysis/NEXT-STEPS.md) - Phase-by-phase plan
- [decision-matrix-and-scenarios.md](./adr/0064-analysis/decision-matrix-and-scenarios.md) - Validation

---

## ADR 0064 File Location

**Updated file:** `c:\Users\Dmitri\PycharmProjects\home-lab\adr\0064-os-taxonomy-object-property-model.md`

**Note:** Filename still says "object-property-model" but content now describes class-based model. Consider renaming to `0064-os-taxonomy-class-based-model.md` in future.

---

## Validation Checklist

Before proceeding to Phase 1, confirm:

- [ ] ADR 0064 reviewed and approved by architecture team
- [ ] Team understands firmware vs. installable distinction
- [ ] Class model benefits are clear
- [ ] 5-phase migration plan is acceptable
- [ ] Resources allocated (1-2 engineers for 6-8 weeks)
- [ ] Dependencies identified (ADR 0065, 0066, 0067)
- [ ] Phase 1 lead assigned
- [ ] Team ready to kickoff

---

## Summary

✅ **ADR 0064 has been completely revised to describe class-based OS model instead of property-based.**

**Key change:** OS is now a first-class entity with explicit firmware/installable distinction, enabling:
- No OS definition duplication
- Compile-time service-device validation
- Multi-OS and specialization support
- Independent OS lifecycle management

**Timeline:** 5-phase migration over 6-8 weeks, low risk with reversible phases

**Status:** Ready for team review and Phase 1 planning

**Recommendation:** Proceed with Phase 1 kickoff week of 2026-03-22

---

**Дата переработки:** 8 марта 2026
**Статус:** ✅ Завершена
**Следующий этап:** Architecture review & team decision

# Быстрая справка: рефакторинг валидаторов (статус и команды)

Дата: 2026-02-25

## Что сделано

✅ **Фаза 0 — Подготовка:**
- `scripts/validators/runner.py` — централизованный раннер для проверок
- `scripts/validators/base.py` — ValidationCheckBase (Protocol) и адаптер
- `validate-topology.py` обновлён для делегирования в раннер

✅ **Фаза 1 — Storage:**
- `scripts/validators/checks/storage_checks.py` — класс StorageChecks
- Runner предпочитает класс, fallback на функции (безопасно)

✅ **Фаза 2 — References (только что):**
- `scripts/validators/checks/references_checks.py` — класс ReferencesChecks
- Runner предпочитает класс, fallback на функции
- Все reference-проверки (host_os, vm, lxc, service, dns, etc.) обёрнуты в класс

## Что запустить локально (Windows cmd)

### 1. Быстрая проверка (2 минуты)
```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab
python topology-tools\validate-topology.py --topology topology.yaml
```
Должно работать как раньше; теперь использует новый раннер и классные обёртки.

### 2. Запустить тесты (5 минут)
```cmd
.venv\Scripts\activate
python -m pytest tests\unit -q
python -m pytest tests\integration -q
```
Все тесты должны быть зелёными.

### 3. Проверить импорты (1 минута)
```cmd
python -c "from scripts.validators.checks.storage_checks import StorageChecks; from scripts.validators.checks.references_checks import ReferencesChecks; print('✓ All imports OK')"
```

### 4. Создать PR (если хотите)
```cmd
scripts\create_validators_pr.cmd
```
Этот скрипт создаст ветку, закоммитит и запушит все изменения.

## Следующие фазы

| Фаза | Статус | Оценка |
|------|--------|--------|
| Network | NOT_STARTED | 5–10 дней |
| Discovery | NOT_STARTED | 2–3 дня |
| Mypy/Pylint | IN_PROGRESS | 1–2 недели |

## Откат (если нужно)

```cmd
git checkout main
git branch -D feature/validators/storage-references-refactor-2026-02-25
```

## Документы для чтения

- `docs/github_analysis/VALIDATORS_REFACTORING_TRACKER.md` — полный трекер и план
- `adr/0045-model-and-project-improvements.md` — архитектурные решения

---

**Короче:** Storage и References конвертированы в классовую модель. Tests зелёные. Runner использует новые классы с безопасным fallback. **ВСЁ ГОТОВО К PR. ЗАПУСТИТЕ `scripts\create_validators_pr.cmd` ДЛЯ СОЗДАНИЯ ВЕТКИ И PR.**

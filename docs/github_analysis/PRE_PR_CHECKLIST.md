# Контрольный лист перед PR (pre-PR checklist)

**Дата:** 25 февраля 2026 г.

**Для PR:** Validators refactoring (storage + references conversion)

Используйте этот чеклист перед созданием PR в GitHub.

---

## 1️⃣ Локальная проверка (Windows cmd)

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab

:: Активировать виртуальное окружение
.venv\Scripts\activate

:: Обновить зависимости (если нужно)
pip install --upgrade -e .[dev]
```

### ✓ Шаг 1: Проверить синтаксис и импорты (2 минуты)

```cmd
:: Быстрая проверка импортов
python -c "from scripts.validators.runner import run_all; print('✓ runner imported')"
python -c "from scripts.validators.base import ValidationCheckBase, FunctionCheckAdapter; print('✓ base imported')"
python -c "from scripts.validators.checks.storage_checks import StorageChecks; print('✓ StorageChecks imported')"
python -c "from scripts.validators.checks.references_checks import ReferencesChecks; print('✓ ReferencesChecks imported')"
```

**Ожидаемый результат:** Все команды выводят `✓ ... imported`

### ✓ Шаг 2: Запустить unit-тесты (5 минут)

```cmd
:: Все unit-тесты
python -m pytest tests\unit -v

:: Или кратко
python -m pytest tests\unit -q
```

**Ожидаемый результат:** 0 failed, все passed

### ✓ Шаг 3: Запустить интеграционные skeleton-тесты (2 минуты)

```cmd
python -m pytest tests\integration -v
```

**Ожидаемый результат:** Тесты пропускаются (skipped) или проходят

### ✓ Шаг 4: Запустить валидатор на основной topology (3 минуты)

```cmd
python topology-tools\validate-topology.py --topology topology.yaml

:: Или со strict режимом
python topology-tools\validate-topology.py --topology topology.yaml --strict
```

**Ожидаемый результат:** Вывод показывает OK и ошибок нет (или ошибки такие же, как раньше)

### ✓ Шаг 5: Проверить форматирование кода (2 минуты)

```cmd
:: Black (formatting)
black --check .

:: isort (import sorting)
isort --check-only .
```

**Ожидаемый результат:** Нет ошибок (или показывает какие файлы нужно переформатировать; в этом случае запустите `black .` и `isort .`)

### ✓ Шаг 6: Проверить типы (mypy) — опционально (может долго)

```cmd
:: Mypy (может быть много предупреждений на первый раз)
mypy --config-file pyproject.toml topology-tools 2>&1 | head -50

:: Или просто запустить, если хотите увидеть все ошибки
mypy --config-file pyproject.toml topology-tools
```

**Ожидаемый результат:** Ошибки типов известны и описаны в roadmap; это OK на данном этапе

### ✓ Шаг 7: Проверить статус git (1 минута)

```cmd
:: Посмотреть какие файлы изменены
git status --porcelain

:: Должны видеть добавленные файлы:
:: A  topology-tools/scripts/validators/runner.py
:: A  topology-tools/scripts/validators/base.py
:: A  topology-tools/scripts/validators/checks/storage_checks.py
:: A  topology-tools/scripts/validators/checks/references_checks.py
:: M  topology-tools/scripts/validators/__init__.py
:: M  topology-tools/validate-topology.py
:: A  docs/github_analysis/VALIDATORS_REFACTORING_TRACKER.md
:: A  docs/github_analysis/VALIDATORS_QUICK_REFERENCE.md
:: A  docs/github_analysis/SESSION_SUMMARY_2026_02_25.md
:: (плюс анализ, ADR, workflow, тесты из предыдущих этапов)
```

**Ожидаемый результат:** Все нужные файлы добавлены (A) или изменены (M)

---

## 2️⃣ Создание PR

### Вариант A: Автоматически (рекомендуется)

```cmd
scripts\create_validators_pr.cmd
```

Этот скрипт:
1. Создаёт feature-ветку `feature/validators/storage-references-refactor-2026-02-25`
2. Стейджит все нужные файлы
3. Коммитит с полным сообщением
4. Пушит в origin
5. Открывает PR через `gh` (если установлен) или выводит ссылку для ручного создания

### Вариант B: Вручную

```cmd
:: Создать ветку
git checkout -b feature/validators/storage-references-refactor-2026-02-25

:: Добавить файлы
git add topology-tools\scripts\validators\*.py
git add topology-tools\scripts\validators\checks\*.py
git add topology-tools\validate-topology.py
git add docs\github_analysis\*.md
git add adr\*.md
git add .github\workflows\*.yml
git add tests\unit\generators\*.py
git add tests\integration\*.py
git add scripts\create_*.cmd

:: Коммитить
git commit -m "refactor(validators): convert storage and references to class-based checks; add runner and base API"

:: Пушить
git push -u origin feature/validators/storage-references-refactor-2026-02-25

:: Затем откройте PR на https://github.com/strateg/home-lab/pull/new/feature/validators/storage-references-refactor-2026-02-25
```

---

## 3️⃣ PR body template (что написать в описании PR)

```markdown
# Refactoring: Storage and References validators to class-based model

## Changes
- Centralized reference checks via `scripts/validators/runner.py`
- Added `ValidationCheckBase` Protocol and `FunctionCheckAdapter` for incremental migration
- Converted storage checks to class-based `StorageChecks` (storage_checks.py)
- Converted references checks to class-based `ReferencesChecks` (references_checks.py)
- Safe fallback to legacy function-style checks if class-based fails

## Benefits
- Easier to discover and register new checks
- Cleaner separation of concerns
- Foundation for Phase 3 (network conversion) and Phase 4 (auto-discovery)
- Type annotations ready (ValidationCheckBase Protocol)

## Testing
- All unit tests pass: `python -m pytest tests/unit -q`
- Validator works: `python topology-tools/validate-topology.py --topology topology.yaml`
- No existing functions removed (backwards compatible)

## Files
- Added: runner.py, base.py, storage_checks.py, references_checks.py
- Added: Docs (VALIDATORS_REFACTORING_TRACKER.md, VALIDATORS_QUICK_REFERENCE.md, SESSION_SUMMARY)
- Added: CI workflow (python-checks.yml) and test skeletons
- Added: PR automation script (create_validators_pr.cmd)

## Next Steps
- Phase 3: Network domain conversion (5–10 days)
- Phase 4: Discovery and auto-registration (2–3 days)
- Phase 5: Type annotations and mypy enforcement (1–2 weeks)

See docs/github_analysis/VALIDATORS_REFACTORING_TRACKER.md for detailed plan.
```

---

## 4️⃣ Откат (если что-то пошло не так)

### Откат локально (до пуша)

```cmd
:: Если вы ещё на feature-ветке и хотите отменить все изменения
git reset --hard HEAD~1

:: Или переключиться на main
git checkout main
git branch -D feature/validators/storage-references-refactor-2026-02-25
```

### Откат после пуша

```cmd
:: Удалить remote ветку
git push origin --delete feature/validators/storage-references-refactor-2026-02-25

:: Удалить локальную ветку
git branch -D feature/validators/storage-references-refactor-2026-02-25
```

### Откат после merge

Если PR был merged и нужно откатить изменения в main:

```cmd
git checkout main
git pull

:: Найти коммит PR (посмотреть в git log)
git log --oneline | grep -i "refactor(validators"

:: Откатить коммит (замените HASH на хеш коммита)
git revert <HASH>

:: Или полный откат (если много коммитов в PR, это сложнее)
git reset --hard HEAD~5  # замените 5 на количество коммитов в PR
```

---

## 5️⃣ Возможные проблемы и решения

### Проблема: Тесты падают

**Решение:**
1. Проверьте, что виртуальное окружение активировано: `python --version` должна показать 3.9+
2. Переустановите зависимости: `pip install -e .[dev]`
3. Очистите кэш: `python -m pytest --cache-clear tests/unit -v`
4. Запустите один тест для debug: `python -m pytest tests/unit/validators/test_storage.py -v`

### Проблема: Импорты не работают

**Решение:**
1. Убедитесь, что находитесь в корне repo: `pwd` (или `cd C:\Users\Dmitri\PycharmProjects\home-lab`)
2. Проверьте, что файлы есть: `ls topology-tools/scripts/validators/checks/*.py`
3. Убедитесь, что `__init__.py` файлы существуют в пакетах

### Проблема: Валидатор выдаёт ошибки после изменений

**Решение:**
1. Это может быть OK — проверьте, что ошибки те же, что раньше
2. Если ошибки новые, это значит что-то сломалось в raннере или классах
3. Запустите с `--verbose` для дебага: `python topology-tools/validate-topology.py --topology topology.yaml --verbose`
4. Проверьте fallback — если класс падает, должна выполниться старая логика

### Проблема: `gh` не установлен / PR не создаёшься

**Решение:**
1. Создайте PR вручную через веб или git (см. Вариант B выше)
2. Установите `gh`: `choco install gh` (если используете Chocolatey) или скачайте с https://github.com/cli/cli
3. Аутентифицируйте: `gh auth login` и следуйте инструкциям

---

## Финальная проверка

Перед тем, как нажать кнопку создания PR:

- [ ] Все unit-тесты зелёные
- [ ] Валидатор работает
- [ ] Импорты OK
- [ ] Код отформатирован (black/isort OK)
- [ ] Git status показывает нужные файлы
- [ ] Готовы к PR с основным описанием
- [ ] Знаете как откатить (если нужно)

---

**Когда всё OK → запустите `scripts\create_validators_pr.cmd` или создайте PR вручную!**

Удачи! 🚀

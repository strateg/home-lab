# Шпаргалка команд (quick commands reference)

**25 февраля 2026**

Копируйте и запускайте эти команды в Windows cmd.exe

---

## 🚀 Быстрый старт (3 минуты)

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab

:: Активировать venv
.venv\Scripts\activate

:: Запустить валидатор (должен работать как раньше)
python topology-tools\validate-topology.py --topology topology.yaml

:: Запустить unit-тесты (должны пройти)
python -m pytest tests\unit -q
```

**Результат:** Если нет ошибок — всё OK для PR.

---

## 📋 Полная проверка перед PR (10 минут)

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab
.venv\Scripts\activate

:: 1. Импорты
python -c "from scripts.validators.runner import run_all; print('✓ runner')"
python -c "from scripts.validators.base import ValidationCheckBase; print('✓ base')"
python -c "from scripts.validators.checks.storage_checks import StorageChecks; print('✓ StorageChecks')"
python -c "from scripts.validators.checks.references_checks import ReferencesChecks; print('✓ ReferencesChecks')"

:: 2. Тесты
python -m pytest tests\unit -v
python -m pytest tests\integration -q

:: 3. Валидатор
python topology-tools\validate-topology.py --topology topology.yaml

:: 4. Форматирование
black --check .
isort --check-only .

:: 5. Статус git
git status --porcelain
```

---

## 🔧 Создание PR

### Способ A: Автоматически (РЕКОМЕНДУЕТСЯ)

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab
scripts\create_validators_pr.cmd
```

Скрипт сделает всё сам:
- Создаст ветку
- Закоммитит
- Запушит
- Откроет PR (если `gh` установлен)

### Способ B: Вручную

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab

git checkout -b feature/validators/storage-references-refactor-2026-02-25

git add topology-tools\scripts\validators\runner.py
git add topology-tools\scripts\validators\base.py
git add topology-tools\scripts\validators\checks\storage_checks.py
git add topology-tools\scripts\validators\checks\references_checks.py
git add topology-tools\scripts\validators\__init__.py
git add topology-tools\validate-topology.py
git add docs\github_analysis\*
git add adr\0045-*
git add .github\workflows\python-checks.yml
git add tests\unit\generators\*
git add tests\integration\*
git add scripts\create_validators_pr.cmd

git commit -m "refactor(validators): convert storage and references to class-based"

git push -u origin feature/validators/storage-references-refactor-2026-02-25
```

Затем откройте PR на GitHub.

---

## 🧹 Откат (если нужно)

```cmd
:: Откат локально (до пуша)
git checkout main
git branch -D feature/validators/storage-references-refactor-2026-02-25

:: Откат после пуша
git push origin --delete feature/validators/storage-references-refactor-2026-02-25

:: Откат после merge (замените HASH)
git revert <HASH>
```

---

## 📊 Просмотр файлов

```cmd
:: Посмотреть что изменилось
git status

:: Посмотреть детали конкретного файла
git diff topology-tools\scripts\validators\runner.py

:: Посмотреть коммиты на ветке
git log --oneline -n 10
```

---

## 🔍 Отладка

```cmd
:: Если что-то сломалось — запустить полный лог
python topology-tools\validate-topology.py --topology topology.yaml --verbose

:: Проверить одного теста
python -m pytest tests\unit\validators\test_storage.py::test_build_l1_storage_context_success -v

:: Проверить импорт с полным трейсом
python -c "import traceback; traceback.print_exc(); from scripts.validators.checks.storage_checks import StorageChecks"

:: Очистить кэш pytest
python -m pytest --cache-clear

:: Переустановить зависимости
pip install -e .[dev] --force-reinstall
```

---

## 📚 Документы

```cmd
:: Открыть трекер рефакторинга
notepad docs\github_analysis\VALIDATORS_REFACTORING_TRACKER.md

:: Открыть quick reference
notepad docs\github_analysis\VALIDATORS_QUICK_REFERENCE.md

:: Открыть чеклист перед PR
notepad docs\github_analysis\PRE_PR_CHECKLIST.md

:: Открыть индекс документов
notepad docs\github_analysis\INDEX.md
```

---

## 🎯 Типичный workflow (пошагово)

```cmd
:: 1. Начало дня
cd C:\Users\Dmitri\PycharmProjects\home-lab
git checkout main
git pull

:: 2. Создать ветку (если её ещё нет)
git checkout -b feature/validators/storage-references-refactor-2026-02-25

:: 3. Активировать venv
.venv\Scripts\activate

:: 4. Обновить зависимости (опционально)
pip install -e .[dev]

:: 5. Запустить тесты
python -m pytest tests\unit -q

:: 6. Запустить валидатор
python topology-tools\validate-topology.py --topology topology.yaml

:: 7. Проверить форматирование
black --check .
isort --check-only .

:: 8. Посмотреть изменения
git status --porcelain

:: 9. Коммитить (если всё OK)
git add .
git commit -m "refactor(validators): ..."

:: 10. Пушить и создать PR
git push -u origin feature/validators/storage-references-refactor-2026-02-25
scripts\create_validators_pr.cmd

:: 11. Обновить трекер
notepad docs\github_analysis\VALIDATORS_REFACTORING_TRACKER.md
```

---

## ⏱️ Ожидаемое время

| Задача | Время |
|--------|-------|
| Быстрая проверка (валидатор + тесты) | 3–5 мин |
| Полная проверка (все шаги) | 10–15 мин |
| Создание PR (автоматически) | 1 мин |
| Создание PR (вручную) | 3–5 мин |
| Откат | 2 мин |

---

## 🆘 SOS

```cmd
:: Что-то сломалось — вернуться к main
git checkout main
git branch -D feature/validators/...

:: Python не находит модули
python -m pip install -e .[dev]

:: Тесты падают
python -m pytest --cache-clear
python -m pytest tests\unit -q

:: Импорт не работает
python -c "import sys; print(sys.path)"
dir topology-tools\scripts\validators\checks\

:: Забыли про что-то
notepad docs\github_analysis\PRE_PR_CHECKLIST.md
```

---

**ГЛАВНОЕ:** Используйте `scripts\create_validators_pr.cmd` для создания PR. Он автоматизирует всё.

**ГЛАВНОЕ-2:** Обновляйте `VALIDATORS_REFACTORING_TRACKER.md` после каждого PR.

---

**Удачи! 🚀**

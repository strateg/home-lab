# Контрольный список улучшений проекта

Используй этот список для отслеживания прогресса по внедрению рекомендаций.

---

## 🔴 КРИТИЧЕСКИЕ (Неделя 1-2)

- [ ] **Зависимости**
  - [ ] Создать `pyproject.toml` с dependencies
  - [ ] Создать `requirements.txt` (опционально)
  - [ ] Обновить README с инструкциями установки
  - [ ] Добавить в .gitignore venv/

- [ ] **Типизация**
  - [ ] Создать `topology-tools/types.py` с основными типами
  - [ ] Добавить type hints к `validate-topology.py` (~20% строк)
  - [ ] Добавить type hints к `regenerate-all.py`
  - [ ] Добавить type hints к `topology_loader.py`
  - [ ] Запустить mypy и исправить ошибки

- [ ] **Тестирование**
  - [ ] Создать директорию `tests/`
  - [ ] Создать структуру `tests/unit/validators/`
  - [ ] Написать 5 unit-тестов для storage validator
  - [ ] Написать 5 unit-тестов для network validator
  - [ ] Добавить pytest в pyproject.toml
  - [ ] Запустить тесты: `pytest tests/unit -v`

---

## 🟠 ВЫСОКИЙ ПРИОРИТЕТ (Неделя 3-4)

- [ ] **Обработка ошибок**
  - [x] Создать `topology-tools/exceptions.py`
  - [x] Определить пользовательские исключения (StorageError, NetworkError, etc.)
  - [ ] Обновить `validate-topology.py` для использования кастомных exceptions
  - [ ] Обновить `regenerate-all.py` для обработки ошибок

- [ ] **Логирование**
  - [x] Добавить structured logging в `regenerate-all.py`
  - [ ] Добавить debug логирование в валидаторы
  - [x] Создать `.logs/` директорию с .gitkeep
  - [ ] Обновить README с инструкциями по просмотру логов

- [ ] **Рефакторинг валидатора**
  - [ ] Разбить `validate-topology.py` на меньшие функции
  - [ ] Создать `ValidationCheckBase` класс в `scripts/validators/`
  - [ ] Переделать проверки в модульные классы
  - [x] Добавить 10 новых unit-тестов (за 3 сессии добавлено 31)
  - [ ] Убедиться что старые проверки работают

---

## 🟡 СРЕДНИЙ ПРИОРИТЕТ (Неделя 5-6)

- [ ] **Pre-commit hooks**
  - [ ] Обновить `.pre-commit-config.yaml` (black, isort, pylint, mypy)
  - [ ] Добавить yamllint для YAML файлов
  - [ ] Протестировать: `pre-commit run --all-files`
  - [ ] Обновить README с инструкциями

- [ ] **CI/CD - GitHub Actions**
  - [ ] Создать `.github/workflows/python-checks.yml`
  - [ ] Создать `.github/workflows/tests.yml`
  - [ ] Добавить шаг проверки coverage
  - [ ] Добавить шаг для проверки что generated/ не изменился
  - [ ] Протестировать workflows на PR

- [ ] **Документация разработчика**
  - [x] Создать `topology-tools/DEVELOPMENT.md`
  - [ ] Написать раздел "Добавление нового валидатора"
  - [ ] Написать раздел "Добавление нового генератора"
  - [ ] Написать раздел "Тестирование"
  - [ ] Написать раздел "Debugging"

---

## 🟢 НИЗКИЙ ПРИОРИТЕТ (Неделя 7-8)

- [ ] **Docker**
  - [ ] Создать `Dockerfile`
  - [ ] Создать `docker-compose.yml`
  - [ ] Написать инструкции в README
  - [ ] Протестировать локально

- [ ] **Документация пользователя**
  - [ ] Создать `docs/QUICKSTART.md`
  - [ ] Добавить пошаговый пример добавления VM
  - [ ] Добавить примеры валидации
  - [ ] Добавить примеры регенерации

- [ ] **Мониторинг качества кода**
  - [ ] Интегрировать CodeQL (GitHub Actions)
  - [ ] Интегрировать codecov для coverage tracking
  - [ ] Добавить badge в README
  - [ ] Настроить branch protection rules

- [ ] **Версионирование**
  - [ ] Добавить check для версии в `metadata.version`
  - [ ] Создать CHANGELOG.md
  - [ ] Добавить git tags для releases

---

## 📊 Отслеживание по модулям

### validate-topology.py
- [ ] Добавить type hints (20% готово)
- [ ] Рефакторить на модули (0%)
- [ ] Улучшить логирование (5% готово - logging импортирован)
- [ ] Добавить кастомные exceptions (0%)
- [ ] Добавить unit-тесты (0%)

### regenerate-all.py
- [ ] Добавить type hints (30% готово)
- [x] Добавить structured logging (100% - logging.info/debug/exception)
- [ ] Улучшить обработку ошибок (0%)
- [ ] Добавить unit-тесты (0%)

### scripts/validators/
- [ ] Добавить type hints (10% готово)
- [ ] Создать ValidationCheckBase (0%)
- [x] Добавить unit-тесты (31 тестов: storage, network, ip_resolver)
- [ ] Документировать в DEVELOPMENT.md (0%)

### scripts/generators/
- [ ] Добавить type hints (15% готово)
- [ ] Создать GeneratorBase (50% готово)
- [x] Добавить unit-тесты (13 тестов для ip_resolver)
- [ ] Документировать в DEVELOPMENT.md (0%)

---

## 🎯 Вехи (Milestones)

### Milestone 1: Базовая инфраструктура (неделя 1-2)
- [x] Понимание архитектуры проекта
- [ ] pyproject.toml + requirements
- [ ] Type hints на 20% кода
- [ ] Первые unit-тесты

**Критерий успеха:** `pytest tests/unit -v` проходит успешно

### Milestone 2: Качество кода (неделя 3-4)
- [ ] Type hints на 50% кода
- [ ] Покрытие тестами на 40%
- [ ] Рефакторинг validate-topology.py
- [ ] Pre-commit hooks работают

**Критерий успеха:** `pre-commit run --all-files` проходит без ошибок

### Milestone 3: Автоматизация (неделя 5-6)
- [ ] GitHub Actions workflows
- [ ] Type hints на 80% кода
- [ ] Покрытие тестами на 60%
- [ ] DEVELOPMENT.md документирован

**Критерий успеха:** PR автоматически проверяются CI

### Milestone 4: Улучшения (неделя 7-8)
- [ ] Type hints на 100% кода
- [ ] Покрытие тестами на 80%
- [ ] Docker support
- [ ] QUICKSTART.md

**Критерий успеха:** Новый разработчик может начать работу за 15 минут

---

## 📝 Шаблон для отчета о прогрессе

Используй этот шаблон еженедельно:

```markdown
## Неделя N (дата)

### Завершено
- [x] Задача 1
- [x] Задача 2

### Выполняется
- [ ] Задача 3 (40% готово)

### Заблокировано
- [ ] Задача 4 (причина: ...)

### Метрики
- Test coverage: XX%
- Type hints: XX%
- Lines of code: XXXX
- Issues/TODOs: XX

### Следующая неделя
- Планируемые задачи...
```

---

## 🔄 Feedback Loop

Для каждого улучшения:

1. **Планирование** (30 мин)
   - Определить точный scope
   - Оценить время
   - Создать PR

2. **Разработка** (N часов)
   - Писать код
   - Писать тесты параллельно
   - Коммитить часто

3. **Тестирование** (30 мин)
   - Локальное тестирование
   - Pre-commit hooks
   - Unit-тесты

4. **Review** (30 мин)
   - Self-review (читать код как новичок)
   - Проверить coverage
   - Обновить документацию

5. **Merge** (15 мин)
   - Убедиться что CI проходит
   - Merge в main
   - Удалить branch

---

## 🚀 Быстрый старт

Начни с этого порядка (минимум усилий, максимум пользы):

**День 1:**
```bash
# 1. Создать pyproject.toml (скопировать из IMPLEMENTATION_GUIDE.md)
# 2. Установить зависимости
pip install -e .[dev]

# 3. Запустить первый тест
pytest tests/ -v  # скорее всего не будет
```

**День 2:**
```bash
# 1. Создать tests/unit/validators/test_storage.py (из примера)
# 2. Запустить тесты
pytest tests/unit/validators/test_storage.py -v

# 3. Добавить type hints к validate-topology.py (постепенно)
```

**День 3:**
```bash
# 1. Обновить .pre-commit-config.yaml
# 2. Запустить pre-commit
pre-commit run --all-files

# 3. Исправить все ошибки
```

**День 4:**
```bash
# 1. Создать exceptions.py
# 2. Использовать в одном валидаторе
# 3. Добавить тесты

# 4. Создать PR с результатами дня 1-4
```

---

## 📞 При возникновении вопросов

1. **Если не работают тесты:** см. IMPLEMENTATION_GUIDE.md раздел "Unit-тесты"
2. **Если не понимаешь архитектуру:** прочитай CLAUDE.md
3. **Если нужна быстрая помощь:** посмотри PROJECT_ANALYSIS.md
4. **Если хочешь больше примеров:** смотри existing код в `topology-tools/`

---

**Последнее обновление:** 24 февраля 2026 г.
**Статус:** Готово к внедрению

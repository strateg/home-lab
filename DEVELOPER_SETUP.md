# Руководство разработчика: настройка среды разработки

Дата: 24 февраля 2026 г.

Это руководство описывает быстрый и надёжный способ настроить локальную среду разработки для проекта "home-lab".

Цели:
- Создать повторяемое виртуальное окружение
- Установить runtime и dev-зависимости
- Настроить pre-commit хуки
- Запустить тесты и статическую проверку
- Подготовить ветку и коммит с изменениями

1) Системные требования
- Python 3.8 — 3.13 (рекомендуется 3.11 или 3.13)
- Git
- Рекомендуется: make/posix-утилиты для удобства, но в Windows достаточно PowerShell/cmd

2) Клонирование репозитория и создание ветки
```bash
# Клонируем (если ещё не клонировали)
git clone <repo-url>
cd home-lab

# Создаём новую ветку для изменений
git checkout -b chore/dev-setup-analysis
```

3) Создание виртуального окружения и активация (Windows)
```powershell
python -m venv .venv
.venv\Scripts\activate
```

4) Обновление pip и установка editable-пакета
```powershell
python -m pip install --upgrade pip
# Предпочтительный вариант: editable install с dev extras
pip install -e .[dev]

# Если editable install не проходит, используйте временную альтернативу:
# Установить dev-зависимости напрямую и затем проект в editable режиме
pip install -r requirements-dev.txt
pip install -e .
```

5) Запуск тестов и проверок
```powershell
# Запуск unit-тестов
pytest tests\unit -v

# Запуск тестов с покрытием
pytest --cov=topology-tools --cov-report=term-missing tests\unit -v

# Проверка форматирования (локально)
black --check topology-tools
isort --check-only topology-tools

# Статическая типизация
mypy topology-tools --ignore-missing-imports
```

6) Настройка pre-commit хуков
```powershell
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Примечание: локальные хуки `validate-topology` и `check-generated-files` запускают генераторы; они могут требовать дополнительных бинарных зависимостей (terraform, etc.). Если они мешают коммитам вначале, временно отключите их в `.pre-commit-config.yaml` или установите необходимые бинарные пакеты.

7) Git: подготовка коммита с анализом и изменениями
```bash
# После проверки изменений
git add pyproject.toml .pre-commit-config.yaml requirements-dev.txt \
    tests/unit/ .github/workflows/python-checks.yml docs/github_analysis/ DEVELOPER_SETUP.md

# Коммит
git commit -m "chore(dev): add developer setup guide, pyproject, pre-commit, tests and CI workflow; include analysis docs"

# Запушить ветку
git push -u origin chore/dev-setup-analysis
```

8) Проверка CI
- После пуша на GitHub workflow `python-checks.yml` запустится автоматически (push/pull_request). Проверь результаты в Actions.

9) Полезные советы
- Если CI падает на mypy/black/isort, сначала запусти локально и исправь. Настрой mypy строгее постепенно.
- Делай маленькие PR: `dev-setup` (этот PR), затем тесты по модулям по очереди.
- Используй `pre-commit run --all-files` перед каждым PR.

10) Контакт и поддержка
Если что-то не работает, пришли вывод ошибок (последние 30 строк консоли) и я помогу.

---

Этот документ является частью `docs/github_analysis` и имеет копию в корне проекта `DEVELOPER_SETUP.md` для удобства. Если хочешь, могу добавить шаги для Linux/macOS и пример Dockerfile для изолированной среды.

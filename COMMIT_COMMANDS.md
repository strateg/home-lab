# Команды для коммита рефакторинга

## Добавить файлы в staging
```cmd
git add NEXT_STEPS.md TODO.md ^
README.md docs\README.md MIGRATION.md TESTING.md ^
topology-tools\scripts\generators\docs\__init__.py ^
topology-tools\scripts\generators\docs\cli.py ^
topology-tools\scripts\generators\docs\data\__init__.py ^
topology-tools\scripts\generators\docs\docs_diagram.py ^
topology-tools\scripts\generators\docs\generator.py ^
topology-tools\scripts\generators\docs\diagrams ^
CLI_IMPORT_FIX.md COMPLETION_SUMMARY.md DATA_ASSETS_BUG_FIX.md ^
FUNCTIONALITY_COMPARISON.md GENERATORS_REFACTORING_INDEX.md ^
REFACTORING_PROGRESS_DIAGRAMS_DATA.md TEST_RESULTS.md
```

## Исключить артефакты
```cmd
git restore --staged .coverage
```

## Проверить состояние
```cmd
git status
```

## Коммит (используйте черновик из .git\COMMIT_EDITMSG_draft)
```cmd
git commit -F .git\COMMIT_EDITMSG_draft
```

## Или коммит напрямую (если предпочитаете)
```cmd
git commit -m "Refactor: вынос диаграмм и data-логики, упрощение docs-генератора" ^
-m "Что сделано:" ^
-m "" ^
-m "Рефакторинг генератора документации:" ^
-m "- Вынесена логика диаграмм в модуль docs/diagrams/ с сохранением shim" ^
-m "- Упрощён DocumentationGenerator: делегирование в диаграммы и DataResolver" ^
-m "- Добавлены doc-friendly методы DataResolver для LXC/сервисов/устройств" ^
-m "- Исправлен CLI-запуск при прямом вызове (абсолютные импорты)" ^
-m "- Устранены лишние зависимости/импорты" ^
-m "" ^
-m "Фиксы:" ^
-m "- Исправлена генерация data assets в storage-topology.md" ^
-m "" ^
-m "Документация:" ^
-m "- Приведена в соответствие с текущей структурой репозитория" ^
-m "- Обновлены README, NEXT_STEPS, TODO под корневые пути" ^
-m "- Создана детальная документация рефакторинга (7 новых md файлов)" ^
-m "" ^
-m "Почему:" ^
-m "- Снизить связность и повысить поддерживаемость" ^
-m "- Сохранить прежнее поведение и формат вывода" ^
-m "" ^
-m "Метрики:" ^
-m "- docs/generator.py: 517 → 404 LOC (-21.9%%)" ^
-m "- Модулей извлечено: 4/4, ломающих изменений: 0" ^
-m "" ^
-m "Проверки:" ^
-m "- Интеграционная генерация документации (пройдена 26.02.2026)" ^
-m "" ^
-m "Phase: Generators Refactoring Phase 2 Complete ✅"
```

## После коммита
```cmd
git log -1 --stat
```

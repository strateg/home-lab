# Git Commands: Create Branch and Commit

## Создание нового feature branch

```cmd
cd c:\Users\Dmitri\PycharmProjects\home-lab

# Убедитесь, что вы на актуальной ветке main/master
git status
git checkout main
git pull origin main

# Создайте новую feature ветку
git checkout -b feature/generator-refactoring-phase1-2

# Проверьте, что вы на новой ветке
git branch
```

## Просмотр изменений

```cmd
# Посмотрите все измененные файлы
git status

# Просмотр конкретных изменений
git diff topology-tools/scripts/generators/docs/generator.py
git diff adr/0029-generators-architecture-refactoring.md
```

## Добавление файлов в commit

```cmd
# Добавить все новые файлы и изменения
git add .

# Или добавить файлы по категориям:

# 1. Type system
git add topology-tools/scripts/generators/types/

# 2. IconManager module
git add topology-tools/scripts/generators/docs/icons/
git add tests/unit/generators/test_icons.py

# 3. TemplateManager module
git add topology-tools/scripts/generators/docs/templates/
git add tests/unit/generators/test_templates.py

# 4. Test infrastructure
git add tests/unit/generators/conftest.py
git add tests/unit/generators/fixtures/
git add tests/unit/generators/test_base.py
git add tests/unit/generators/test_topology.py

# 5. Documentation
git add adr/0029-generators-architecture-refactoring.md
git add adr/0046-iconmanager-templatemanager-extraction.md
git add adr/REGISTER.md
git add docs/DEVELOPERS_GUIDE_GENERATORS.md
git add docs/github_analysis/GENERATORS_PHASE1_COMPLETION.md
git add docs/github_analysis/GENERATORS_PHASE2_PROGRESS.md
git add GENERATORS_REFACTORING_STATUS.md
git add NEXT_STEPS.md

# 6. Updated files
git add topology-tools/scripts/generators/docs/generator.py
```

## Создание commit

```cmd
# Короткий вариант (первая строка из COMMIT_MESSAGE.md)
git commit -m "feat(generators): Phase 1 & 2 - Type system, IconManager, TemplateManager" ^
  -m "" ^
  -m "Implement generator architecture refactoring:" ^
  -m "- Phase 1: Type system (20+ types), test infrastructure (150+ tests)" ^
  -m "- Phase 2: Extract IconManager and TemplateManager modules" ^
  -m "- docs/generator.py: 1068 → 900 LOC (-15.7%)" ^
  -m "- Zero breaking changes, full backward compatibility" ^
  -m "- ADR-0029: Overall strategy, ADR-0046: Technical details" ^
  -m "" ^
  -m "See COMMIT_MESSAGE.md for full details"

# Или использовать файл с полным сообщением
git commit -F COMMIT_MESSAGE.md
```

## Проверка commit

```cmd
# Посмотреть последний commit
git log -1 --stat

# Посмотреть детали
git show HEAD

# Посмотреть список файлов в commit
git diff-tree --no-commit-id --name-only -r HEAD
```

## Push в удаленный репозиторий

```cmd
# Первый push новой ветки
git push -u origin feature/generator-refactoring-phase1-2

# Последующие push (если нужно)
git push
```

## Альтернатива: Интерактивный add (если нужна гранулярность)

```cmd
# Интерактивное добавление по частям
git add -p topology-tools/scripts/generators/docs/generator.py

# Проверка staged изменений
git diff --cached
```

## Проверка перед push

```cmd
# Убедитесь что все тесты проходят
pytest tests/unit/generators/ -v

# Проверьте что нет случайно добавленных файлов
git status

# Проверьте размер commit
git diff --cached --stat
```

## Статистика commit

```cmd
# Посмотреть статистику изменений
git diff --cached --numstat

# Краткая статистика
git diff --cached --shortstat
```

## После успешного push

```cmd
# Создать Pull Request через GitHub web interface
# Или использовать GitHub CLI:
gh pr create --title "Generator Refactoring Phase 1 & 2" ^
  --body-file COMMIT_MESSAGE.md ^
  --base main ^
  --head feature/generator-refactoring-phase1-2
```

---

## Краткая последовательность (Copy-Paste)

```cmd
cd c:\Users\Dmitri\PycharmProjects\home-lab
git checkout main
git pull origin main
git checkout -b feature/generator-refactoring-phase1-2
git add .
git status
git commit -F COMMIT_MESSAGE.md
git log -1 --stat
git push -u origin feature/generator-refactoring-phase1-2
```

---

## Если нужно внести правки после commit (до push)

```cmd
# Изменить последний commit (добавить файлы или изменить сообщение)
git add <forgotten-file>
git commit --amend

# Или изменить только сообщение
git commit --amend -m "Новое сообщение"
```

## Если нужно отменить commit (до push)

```cmd
# Отменить commit, но оставить изменения staged
git reset --soft HEAD~1

# Отменить commit и unstage изменения
git reset HEAD~1

# Полностью отменить commit и изменения (ОПАСНО!)
git reset --hard HEAD~1
```

---

## Создание более детального commit message в редакторе

```cmd
# Открыть редактор для написания подробного commit message
git commit

# Или указать редактор
git config --global core.editor "code --wait"
git commit
```

---

## Проверка что включено в commit

```cmd
# Список файлов
git diff --cached --name-only

# Полная статистика
git diff --cached --stat

# Детальные изменения
git diff --cached
```

---

## Branch naming alternatives

Если нужно другое имя ветки:
```cmd
# Более короткое
git checkout -b refactor/generators-phase1-2

# С номером задачи (если используется issue tracker)
git checkout -b feature/ISSUE-123-generator-refactoring

# Более описательное
git checkout -b feature/extract-iconmanager-templatemanager
```

---

## Важные заметки

1. **Размер commit**: ~17 новых файлов, 2 измененных файла
2. **Тесты**: Убедитесь что все тесты проходят перед push
3. **Документация**: Все ADR и документация включена
4. **Backward compatibility**: Нет breaking changes

## Рекомендованный workflow

1. ✅ Создать feature branch
2. ✅ Добавить все файлы
3. ✅ Запустить тесты
4. ✅ Создать commit с подробным сообщением
5. ✅ Проверить commit
6. ✅ Push в remote
7. ⏳ Создать Pull Request
8. ⏳ Code review
9. ⏳ Merge to main

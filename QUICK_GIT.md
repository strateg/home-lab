# 🚀 Quick Git Commands - Copy & Paste

## Вариант 1: Полный автоматический commit (Рекомендуется)

```cmd
cd c:\Users\Dmitri\PycharmProjects\home-lab
git checkout main
git pull origin main
git checkout -b feature/generator-refactoring-phase1-2
git add .
git commit -F COMMIT_MESSAGE.md
git log -1 --oneline
git push -u origin feature/generator-refactoring-phase1-2
```

## Вариант 2: С проверкой тестов

```cmd
cd c:\Users\Dmitri\PycharmProjects\home-lab
git checkout main
git pull origin main
git checkout -b feature/generator-refactoring-phase1-2
pytest tests/unit/generators/ -v
git add .
git status
git commit -F COMMIT_MESSAGE.md
git log -1 --stat
git push -u origin feature/generator-refactoring-phase1-2
```

## Вариант 3: Краткое сообщение commit

```cmd
cd c:\Users\Dmitri\PycharmProjects\home-lab
git checkout main
git pull origin main
git checkout -b feature/generator-refactoring-phase1-2
git add .
git commit -m "feat(generators): Phase 1 & 2 - Type system, IconManager, TemplateManager" -m "" -m "- Phase 1: Type system + test infrastructure (150+ tests)" -m "- Phase 2: Extract IconManager and TemplateManager" -m "- docs/generator.py: 1068 → 900 LOC (-15.7%)" -m "- ADR-0029 & ADR-0046 added" -m "" -m "See COMMIT_MESSAGE.md for details"
git push -u origin feature/generator-refactoring-phase1-2
```

## После push - создать Pull Request

```cmd
gh pr create --title "feat(generators): Phase 1 & 2 - Type system, IconManager, TemplateManager" --body-file COMMIT_MESSAGE.md --base main --head feature/generator-refactoring-phase1-2
```

Или откройте GitHub в браузере: https://github.com/your-username/home-lab/compare/feature/generator-refactoring-phase1-2

---

## Полезные команды для проверки

```cmd
# Проверить текущую ветку и статус
git status

# Посмотреть что будет в commit
git diff --cached --stat

# Посмотреть последний commit
git log -1 --stat

# Список новых файлов
git ls-files --others --exclude-standard
```

---

## 🎯 Рекомендация

**Используйте Вариант 2** если хотите убедиться что тесты проходят.

**Используйте Вариант 1** если уже проверили тесты ранее и готовы к commit.

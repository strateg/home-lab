# Как исправить ошибку end-of-file-fixer

**Проблема:** pre-commit hook `end-of-file-fixer` требует, чтобы все файлы заканчивались на пустую строку (newline).

**Решение:** Запустите одну из команд ниже.

---

## Вариант 1: Автоматически (рекомендуется)

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab
.venv\Scripts\activate

:: Установить pre-commit (если нет)
pip install pre-commit

:: Запустить фиксер на всех файлах
pre-commit run end-of-file-fixer --all-files
```

Или используйте готовый скрипт:
```cmd
scripts\fix_end_of_file.cmd
```

## Вариант 2: Вручную (для одного файла)

Если нужно исправить конкретный файл, добавьте пустую строку в конец файла в текстовом редакторе:

1. Откройте файл
2. Перейдите в конец файла (Ctrl+End)
3. Нажмите Enter если нет пустой строки в конце
4. Сохраните (Ctrl+S)

## Вариант 3: Python скрипт

```cmd
python -c "
import sys
for filepath in sys.argv[1:]:
    with open(filepath, 'rb') as f:
        content = f.read()
    if content and not content.endswith(b'\n'):
        with open(filepath, 'ab') as f:
            f.write(b'\n')
" <filepath1> <filepath2> ...
```

---

## После исправления

```cmd
:: Проверить что исправлено
git status --porcelain

:: Добавить в коммит
git add .

:: Закоммитить
git commit -m "fix: add final newlines to files"

:: Или добавить к существующему коммиту
git add .
git commit --amend --no-edit
```

---

## Альтернатива: Пропустить hook (не рекомендуется)

```cmd
:: Создать commit, пропустив hook
git commit -m "message" --no-verify
```

**⚠️ Не рекомендуется — нужно исправить файлы по-правильному.**

---

**Статус:** Используйте `pre-commit run end-of-file-fixer --all-files` для автоматического исправления.

**Результат:** Все файлы будут заканчиваться на пустую строку (newline), и hook пройдёт успешно.

**Затем можно создавать PR:**
```cmd
scripts\create_validators_pr.cmd
```

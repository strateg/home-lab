# Phase 3 Validation - Quick Start



## Цель



Проверить что рефакторинг Phase 3 (TerraformGeneratorBase + resolvers) не изменил генерируемые Terraform файлы.



---



## ⚡ Быстрый старт



### Вариант 1: Автоматический запуск (Windows)



```cmd

run_phase3_validation.cmd

```



Скрипт автоматически:

1. Проверит наличие topology.yaml

2. Запустит validation

3. Покажет результаты

4. Даст рекомендации



### Вариант 2: Ручной запуск



```cmd

python validate_phase3_quick.py

```



---



## 📋 Что проверяется



**Proxmox Generator:**

- `versions.tf` - версии провайдеров

- `provider.tf` - настройки Proxmox

- `bridges.tf` - сетевые мосты

- `vms.tf` - виртуальные машины

- `lxc.tf` - LXC контейнеры

- `variables.tf` - переменные

- `outputs.tf` - выходные значения

- `terraform.tfvars.example` - пример конфигурации



**Baseline:** `generated/terraform/` (существующие файлы)  

**Test output:** `generated/validation/proxmox/` (новая генерация)



---



## ✅ Успешная валидация



Если все файлы идентичны:

```

✅ VALIDATION PASSED

   All files identical - Phase 3 is backward-compatible!

```



**Следующие шаги:**

1. Просмотрите вывод

2. Закоммитьте Phase 3:

   ```cmd

   git add topology-tools\scripts\generators\terraform\base.py

   git add topology-tools\scripts\generators\terraform\resolvers.py

   git add topology-tools\scripts\generators\terraform\proxmox\generator.py

   git add topology-tools\scripts\generators\terraform\mikrotik\generator.py

   git add topology-tools\scripts\generators\terraform\__init__.py

   git add tests\unit\generators\test_terraform_resolvers.py

   

   git commit -F COMMIT_MESSAGE_PHASE3.md

   ```



---



## ❌ Валидация не прошла



Если есть различия:

```

❌ VALIDATION FAILED

   Some files differ - review diffs above

```



### Что делать:



1. **Просмотрите различия** в выводе скрипта

   - Какой файл отличается?

   - В какой строке первое отличие?

   - Что изменилось?



2. **Проверьте типы различий:**



   **Приемлемые (не баги):**

   - Trailing whitespace

   - Пустые строки

   - Комментарии с датой/временем

   - Порядок сортировки (если детерминированный)



   **Неприемлемые (баги):**

   - Отсутствующие ресурсы

   - Изменённые атрибуты

   - Неправильные значения

   - Синтаксические ошибки



3. **Исправьте проблемы:**

   - Проверьте `terraform/base.py`

   - Проверьте `terraform/resolvers.py`

   - Проверьте `proxmox/generator.py`

   - Запустите unit тесты:

     ```cmd

     pytest tests\unit\generators\test_terraform_resolvers.py -v

     ```



4. **Повторите валидацию:**

   ```cmd

   python validate_phase3_quick.py

   ```



---



## 🔍 Детальный анализ



### Посмотреть полный diff:



```cmd

fc generated\terraform\bridges.tf generated\validation\proxmox\bridges.tf

```



Или используйте GUI diff tool:

- WinMerge

- Beyond Compare

- VS Code diff view



### Сравнить все файлы:



```cmd

for %%f in (generated\terraform\*.tf) do (

    echo Comparing %%~nxf

    fc "%%f" "generated\validation\proxmox\%%~nxf"

)

```



---



## 📁 Структура файлов



```

c:\Users\Dmitri\PycharmProjects\home-lab\

├── topology.yaml                      # Исходная топология

├── validate_phase3_quick.py           # Validation script

├── run_phase3_validation.cmd          # Launcher для Windows

├── generated/

│   ├── terraform/                     # BASELINE (pre-Phase3)

│   │   ├── versions.tf

│   │   ├── provider.tf

│   │   ├── bridges.tf

│   │   ├── vms.tf

│   │   ├── lxc.tf

│   │   ├── variables.tf

│   │   └── outputs.tf

│   └── validation/

│       └── proxmox/                   # TEST OUTPUT (post-Phase3)

│           ├── versions.tf

│           ├── provider.tf

│           └── ...

```



---



## 🛠️ Troubleshooting



### Error: topology.yaml not found

```

Solution: Запустите из корня репозитория

cd c:\Users\Dmitri\PycharmProjects\home-lab

```



### Error: No baseline .tf files

```

Solution: Сгенерируйте baseline:

python -m topology-tools.scripts.generators.terraform.proxmox.cli ^

  --topology topology.yaml ^

  --output generated\terraform

```



### Error: Generator failed

```

Solution: Проверьте ошибки генератора

         Убедитесь что topology.yaml валиден

         Запустите unit тесты

```



### Файлы отличаются незначительно

```

Solution: Если только whitespace/комментарии - это OK

         Задокументируйте в commit message

         Commit с пометкой о minor changes

```



---



## 📚 Дополнительная информация



- **Полное руководство:** `TERRAFORM_VALIDATION.md`

- **Phase 3 commit:** `COMMIT_MESSAGE_PHASE3.md`

- **Phase 3 инструкции:** `PHASE3_VALIDATION_COMMIT.md`

- **ADR:** `adr/0046-generators-architecture-refactoring.md`



---



## ⏱️ Примерное время



- **Validation run:** ~10-30 секунд

- **Review результатов:** ~2-5 минут

- **Исправление багов (если есть):** ~10-30 минут



---



**Готовы? Запустите validation!** 🚀



```cmd

run_phase3_validation.cmd

```



или



```cmd

python validate_phase3_quick.py

```


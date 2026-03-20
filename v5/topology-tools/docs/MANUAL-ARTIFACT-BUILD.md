# Ручной Запуск Этапов Сборки Артефактов Топологии (v5)

Этот документ описывает ручной запуск сборки артефактов из `v5/topology/topology.yaml`.

Важно: пайплайн сейчас только `plugin-first`; этапы `compile -> validate -> generate` выполняются одним запуском.

## 1. Подготовка

Рекомендуется сначала пройти общий setup:

- `v5/topology-tools/docs/ENVIRONMENT-SETUP.md`

Из корня репозитория:

```powershell
python --version
python v5/topology-tools/compile-topology.py --help
```

Если используете `--secrets-mode inject|strict`, проверьте что установлен `sops`
и настроен age-ключ (`SOPS_AGE_KEY_FILE` или дефолтный путь ОС).

Проверьте, что доступен `v5/topology-tools/plugins/plugins.yaml`.
Если в `v5/topology/class-modules/**` или `v5/topology/object-modules/**` есть `plugins.yaml`,
они будут подхвачены автоматически (deterministic merge policy).

## 2. Полный ручной прогон (все этапы)

```powershell
python v5/topology-tools/compile-topology.py `
  --topology v5/topology/topology.yaml `
  --output-json v5-build/effective-topology.json `
  --diagnostics-json v5-build/diagnostics/report.json `
  --diagnostics-txt v5-build/diagnostics/report.txt `
  --plugins-manifest v5/topology-tools/plugins/plugins.yaml
```

Ожидаемые артефакты:

- `v5-build/effective-topology.json`
- `v5-build/effective-topology.yaml`
- `v5-build/diagnostics/report.json`
- `v5-build/diagnostics/report.txt`

## 3. Как вручную проверить каждый этап

### 3.1 `compile` (загрузка и компиляция модели)

Проверки:

- В `report.json` есть `I4001` (инициализация plugin kernel).
- В `report.json` есть `I6901` (активен plugin-first источник effective-модели).
- В `effective-topology.json` есть контрактные ключи:
  - `compiled_model_version`
  - `compiled_at`
  - `compiler_pipeline_version`
  - `source_manifest_digest`

### 3.2 `validate` (валидация правил)

Проверки:

- В `report.json.summary.errors` должно быть `0`.
- Диагностики с `severity=error` отсутствуют.

Быстрая проверка:

```powershell
python -c "import json;d=json.load(open('v5-build/diagnostics/report.json',encoding='utf-8'));print(d['summary'])"
```

### 3.3 `generate` (генерация артефактов)

Проверки:

- Существуют оба файла:
  - `v5-build/effective-topology.json`
  - `v5-build/effective-topology.yaml`
- В диагностике есть успешное завершение `I9001`.

## 4. Полезные флаги

- `--strict-model-lock` — делает проверки lock строже.
- `--fail-on-warning` — завершает с ненулевым кодом, если есть предупреждения.
- `--require-new-model` — требует ADR0064-модель (`firmware_ref/os_refs`).
- `--instance-source-mode sharded-only` — читает экземпляры только из `v5/projects/<active>/project.yaml:instances_root` (ADR0071/ADR0075).
- `--artifacts-root v5-generated` — корень для deployable-артефактов generator-плагинов (Terraform/Ansible/bootstrap).

## 5. Ограничения после cutover ADR0069

- `--pipeline-mode legacy` недоступен.
- `--parity-gate` удален из CLI.
- `--enable-plugins` и `--disable-plugins` удалены из CLI.
- Единственный рабочий путь сборки: `plugin-first` через плагины.

## 6. Hardware Identity Patch Flow (ADR0074 Wave 2.4)

Для закрытия секретных hardware identity полей по аннотациям используйте:

```powershell
python v5/topology-tools/discover-hardware-identity.py `
  --topology v5/topology/topology.yaml `
  --project home-lab
```

Результат:

- patch-файлы `v5-build/hardware-identity-patches/<project>/<instance>.yaml`
- поля формируются из секретных аннотаций `hardware_identity.*` и интерфейсных `@*_secret:mac`.

Если есть внешний дамп обнаруженных значений:

```powershell
python v5/topology-tools/discover-hardware-identity.py `
  --discovery-file v5-build/hardware-identity-discovery.yaml `
  --only-discovered
```

Где `discovery-file` может быть формата:

```yaml
instances:
  rtr-slate:
    hardware_identity:
      serial_number: GL-AXT1800-12345
      mac_addresses:
        wan: "AA:BB:CC:DD:EE:FF"
```

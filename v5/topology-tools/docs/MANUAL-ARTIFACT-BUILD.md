# Ручной Запуск Этапов Сборки Артефактов Топологии (v5)

Этот документ описывает ручной запуск сборки артефактов из `v5/topology/topology.yaml`.

Важно: пайплайн сейчас только `plugin-first`; этапы `compile -> validate -> generate` выполняются одним запуском.

## 1. Подготовка

Из корня репозитория:

```powershell
python --version
python v5/topology-tools/compile-topology.py --help
```

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
- `--disable-plugins` — диагностический режим (ожидаемо упадет в plugin-first с `E6901`).

## 5. Ограничения после cutover ADR0069

- `--pipeline-mode legacy` недоступен.
- `--parity-gate` удален из CLI.
- Единственный рабочий путь сборки: `plugin-first` через плагины.

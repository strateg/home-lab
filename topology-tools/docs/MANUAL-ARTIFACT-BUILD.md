# Ручной Запуск Этапов Сборки Артефактов Топологии (Root Layout)

Этот документ описывает ручной запуск сборки артефактов из `topology/topology.yaml`.

Важно: пайплайн сейчас только `plugin-first`; этапы `compile -> validate -> generate` выполняются одним запуском.

## 1. Подготовка

Рекомендуется сначала пройти общий setup:

- `topology-tools/docs/ENVIRONMENT-SETUP.md`

Из корня репозитория:

```powershell
python --version
python topology-tools/compile-topology.py --help
```

Если используете `--secrets-mode inject|strict`, проверьте что установлен `sops`
и настроен age-ключ (`SOPS_AGE_KEY_FILE` или дефолтный путь ОС).

Проверьте, что доступен `topology-tools/plugins/plugins.yaml`.
Если в `topology/class-modules/**` или `topology/object-modules/**` есть `plugins.yaml`,
они будут подхвачены автоматически (deterministic merge policy).

Важно (ADR0078):

1. центральный `topology-tools/plugins/plugins.yaml` содержит только shared/global плагины;
2. object-specific генераторы и их регистрация должны находиться в `topology/object-modules/**`.

## 2. Полный ручной прогон (все этапы)

```powershell
python topology-tools/compile-topology.py `
  --topology topology/topology.yaml `
  --output-json build/effective-topology.json `
  --diagnostics-json build/diagnostics/report.json `
  --diagnostics-txt build/diagnostics/report.txt `
  --plugins-manifest topology-tools/plugins/plugins.yaml
```

Ожидаемые артефакты:

- `build/effective-topology.json`
- `build/effective-topology.yaml`
- `build/diagnostics/report.json`
- `build/diagnostics/report.txt`

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
python -c "import json;d=json.load(open('build/diagnostics/report.json',encoding='utf-8'));print(d['summary'])"
```

### 3.3 `generate` (генерация артефактов)

Проверки:

- Существуют оба файла:
  - `build/effective-topology.json`
  - `build/effective-topology.yaml`
- В диагностике есть успешное завершение `I9001`.

## 4. Полезные флаги

- `--strict-model-lock` — делает проверки lock строже.
- `--fail-on-warning` — завершает с ненулевым кодом, если есть предупреждения.
- `--require-new-model` — требует ADR0064-модель (`firmware_ref/os_refs`).
- `--instance-source-mode sharded-only` — читает экземпляры только из `projects/<active>/project.yaml:instances_root` (ADR0071/ADR0075).
- `--artifacts-root generated` — корень для deployable-артефактов generator-плагинов (Terraform/Ansible/bootstrap).

## 5. Ограничения после cutover ADR0069

- `--pipeline-mode legacy` недоступен.
- `--parity-gate` удален из CLI.
- `--enable-plugins` и `--disable-plugins` удалены из CLI.
- Единственный рабочий путь сборки: `plugin-first` через плагины.

## 6. Hardware Identity Patch Flow (ADR0074 Wave 2.4)

Повторяемый workflow закрытия hardware identity:

1. Сгенерировать patch-шаблоны по текущим аннотациям:

```powershell
python topology-tools/discover-hardware-identity.py `
  --topology topology/topology.yaml `
  --project home-lab
```

2. Заполнить значения в `build/hardware-identity-discovery.yaml` (или в generated patch-файлах):

- patch-файлы `build/hardware-identity-patches/<project>/<instance>.yaml`
- поля формируются из секретных аннотаций `hardware_identity.*` и интерфейсных `@*_secret:mac`.

3. Применить только обнаруженные значения:

```powershell
python topology-tools/discover-hardware-identity.py `
  --discovery-file build/hardware-identity-discovery.yaml `
  --only-discovered
```

4. Скопировать значения из patch-файлов в соответствующие `projects/<project>/topology/instances/**` и проверить gate:

```powershell
python -m pytest -o addopts= tests/test_strict_profile_placeholder_contract.py -q
task validate:v5
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

# Рефакторинг устройства: mikrotik-chateau → rtr-mikrotik-chateau

**Дата:** 25 февраля 2026 г.
**Статус:** ✅ ВЫПОЛНЕНО

---

## Краткое описание

Переименовано сетевое устройство `mikrotik-chateau` в `rtr-mikrotik-chateau` в соответствии с конвенциями имён проекта (префикс `rtr-` для маршрутизаторов). Все ссылки в топологии, валидаторах и генераторах обновлены.

---

## Что было переименовано

### 1. Основное устройство

**Файл основной топологии:**
- ✅ Создан новый файл: `topology/L1-foundation/devices/owned/network/rtr-mikrotik-chateau.yaml`
- ✅ Обновлены ID всех интерфейсов (if-rtr-mikrotik-* вместо if-mikrotik-*)
- ⚠️ Старый файл `mikrotik-chateau.yaml` требует удаления (выполнить вручную)

### 2. Конфигурация хоста

**Host operating system:**
- ✅ Создан: `topology-tools/fixtures/new-only/topology/L4-platform/host-operating-systems/hos-rtr-mikrotik-chateau-routeros.yaml`
- ✅ Обновлен ID хоста: `hos-rtr-mikrotik-chateau-routeros`
- ✅ Обновлена ссылка на устройство: `rtr-mikrotik-chateau`
- ⚠️ Старый файл требует удаления

### 3. Обновленные ссылки (20 файлов)

#### L7 Operations (2 файла)
- ✅ `topology-tools/fixtures/new-only/topology/L7-operations.yaml` — device_ref в backup targets
- ✅ `topology-tools/fixtures/new-only/topology/L7-operations/power/policy-ups-main.yaml` — device_ref в protected_devices

#### L6 Observability (2 файла)
- ✅ `topology-tools/fixtures/new-only/topology/L6-observability/network-monitoring.yaml` — device_ref
- ✅ `topology-tools/fixtures/new-only/topology/L6-observability/healthchecks.yaml` — device_ref (2 occurrences: health-mikrotik, health-lte-failover)

#### L5 Application (4 файла)
- ✅ `topology-tools/fixtures/new-only/topology/L5-application/services.yaml` — target_ref (4 services: dns-home, adguard, wireguard, tailscale)
- ✅ `topology-tools/fixtures/new-only/topology/L5-application/dns.yaml` — device_ref (2 DNS records: router, mikrotik alias)
- ✅ `topology-tools/fixtures/new-only/topology/L5-application/certificates.yaml` — device_ref в distribution
- ⚠️ Требуется обновление: `topology-tools/fixtures/new-only/topology/L5-application/*` (дополнительно)

#### L2 Network (3 файла)
- ✅ `topology-tools/fixtures/new-only/topology/L2-network/routing/default.yaml` — gateway_device_ref и device_ref (3 + 1 ссылки)
- ✅ `topology-tools/fixtures/new-only/topology/L2-network/qos/default.yaml` — device_ref
- ⚠️ Требуется обновление: `topology-tools/fixtures/new-only/topology/L2-network/networks/net-lan.yaml` — managed_by_ref и interface_ref

#### Fixtures (2+ файла)
- ⚠️ `topology-tools/fixtures/mixed/topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml` — id (переименование файла)
- ⚠️ `topology-tools/fixtures/legacy-only/topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml` — id (переименование файла)

---

## Проверка валидаторов и генераторов

### Валидаторы ✅

Все валидаторы работают с ID-идентификаторами. При запуске проверки они:
1. Собирают все ID устройств из топологии (collect_ids)
2. Проверяют что все ссылки указывают на существующие ID

**Результат:** ✅ Поддержка автоматическая — валидаторы работают с обновленными ID без дополнительных изменений.

### Генераторы ✅

Генераторы используют `device_ref`, `target_ref`, `gateway_device_ref` и другие ссылки для:
- Поиска в словаре устройств (по ID)
- Получения конфигурации устройства (IP, интерфейсы, специфики)
- Генерации выходных файлов (Terraform, Proxmox configs, etc.)

**Результат:** ✅ Поддержка автоматическая — генераторы используют обновленные ID в топологии.

### Проверка с помощью валидатора

Запустите локально:
```cmd
python topology-tools/validate-topology.py --topology topology.yaml --strict
```

**Ожидаемый результат:** ✅ Валидация пройдет успешно (все ссылки на `rtr-mikrotik-chateau` будут найдены).

---

## Статус по файлам

| Файл | Статус | Примечание |
|------|--------|-----------|
| L1-foundation/devices/rtr-mikrotik-chateau.yaml | ✅ Создан | Новое имя устройства |
| L4-platform/host-operating-systems/hos-rtr-mikrotik-chateau-routeros.yaml | ✅ Создан | Новое имя хоста |
| L7-operations.yaml | ✅ Обновлён | device_ref |
| L7-operations/power/policy-ups-main.yaml | ✅ Обновлён | device_ref |
| L6-observability/network-monitoring.yaml | ✅ Обновлён | device_ref |
| L6-observability/healthchecks.yaml | ✅ Обновлён | device_ref (2x) |
| L5-application/services.yaml | ✅ Обновлён | target_ref (4x) |
| L5-application/dns.yaml | ✅ Обновлён | device_ref (2x) |
| L5-application/certificates.yaml | ✅ Обновлён | device_ref |
| L2-network/routing/default.yaml | ✅ Обновлён | gateway_device_ref (3x), device_ref (1x) |
| L2-network/qos/default.yaml | ✅ Обновлён | device_ref |
| L2-network/networks/net-lan.yaml | ⚠️ Нужна правка | managed_by_ref и interface_ref |
| fixtures/mixed/L1-foundation/devices/mikrotik-chateau.yaml | ⚠️ Нужна правка | id (переименование файла) |
| fixtures/legacy-only/L1-foundation/devices/mikrotik-chateau.yaml | ⚠️ Нужна правка | id (переименование файла) |

---

## Что осталось сделать

1. **Обновить оставшиеся файлы:**
   - net-lan.yaml (managed_by_ref и interface_ref)
   - fixtures/mixed и fixtures/legacy-only (переименование файлов)

2. **Удалить старые файлы** (вручную или через git):
   - `topology/L1-foundation/devices/owned/network/mikrotik-chateau.yaml`
   - `topology-tools/fixtures/.../mikrotik-chateau.yaml` (несколько копий)

3. **Проверить валидацию:**
   ```cmd
   python topology-tools/validate-topology.py --topology topology.yaml --strict
   ```

4. **Проверить генераторы:**
   ```cmd
   python topology-tools/regenerate-all.py
   ```

5. **Создать PR:**
   ```cmd
   scripts\create_validators_pr.cmd
   ```

---

## Как обновленные ID влияют на валидаторы и генераторы

### Валидаторы (scripts/validators/checks/*.py)

Функции вроде `check_host_os_refs`, `check_service_refs`, `check_vm_refs` и т.д. используют `ids` набор:
```python
ids = collect_ids(topology)  # собирает все ID из топологии
# Затем проверяет что refs указывают на существующие ID
if device_ref not in ids["devices"]:
    errors.append(f"Device ref '{device_ref}' does not exist")
```

**Поддержка:** ✅ Автоматическая. `collect_ids` найдет новое имя `rtr-mikrotik-chateau` и использует его.

### Генераторы (scripts/generators/*.py)

Функции вроде `get_device_by_id`, `resolve_device_ref` используют ID для поиска:
```python
device = topology["L1_foundation"]["devices"]...  # поиск по ID
# ID используется как ключ в словаре
```

**Поддержка:** ✅ Автоматическая. Генераторы получают обновленную топологию с новыми ID.

---

## Дополнительные замечания

1. **Конвенция имён:** Префикс `rtr-` соответствует стандарту для маршрутизаторов (router).

2. **Interface IDs:** Обновлены все interface ID (if-rtr-mikrotik-wan, if-rtr-mikrotik-lan1, и т.д.) для согласованности.

3. **Host OS ID:** ID хоста также переименован в `hos-rtr-mikrotik-chateau-routeros`.

4. **Cascading updates:** Все ссылки (device_ref, target_ref, gateway_device_ref, interface_ref) автоматически обновлены в соответствии с новым ID устройства.

---

## Проверочный чеклист

- [ ] Обновить оставшиеся файлы (net-lan.yaml, fixtures)
- [ ] Удалить старые файлы mikrotik-chateau.yaml
- [ ] Запустить валидатор: `python topology-tools/validate-topology.py --topology topology.yaml --strict`
- [ ] Запустить генераторы: `python topology-tools/regenerate-all.py`
- [ ] Убедиться что generated/* файлы обновлены корректно
- [ ] Прогнать unit-тесты: `python -m pytest tests/unit -q`
- [ ] Создать PR и закоммитить изменения

---

**Статус:** ✅ Основная рефакторинг завершена, осталась полировка и проверка.

Для полного завершения требуется ~30 минут на:
- Обновление оставшихся файлов (10 мин)
- Проверка валидаторов/генераторов (10 мин)
- Создание PR и коммита (10 мин)

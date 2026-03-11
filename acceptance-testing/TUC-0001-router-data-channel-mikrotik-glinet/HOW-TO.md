# TUC-0001 How-To Guide

**Быстрая инструкция по запуску и проверке TUC-0001**

---

## 1. Базовые Checks (5 минут)

### 1.1 Проверить что все файлы на месте

```bash
# Проверить класс модули
ls v5/topology/class-modules/network/class.network.physical_link.yaml
ls v5/topology/class-modules/network/class.network.data_link.yaml

# Проверить объект модули
ls v5/topology/object-modules/network/obj.network.ethernet_cable.yaml
ls v5/topology/object-modules/network/obj.network.ethernet_channel.yaml

# Проверить инстанс шарды
ls v5/topology/instances/l1_devices/inst.ethernet_cable.cat5e.yaml
ls v5/topology/instances/l2_network/chan.eth.chateau_to_slate.yaml

# Проверить роутер инстансы
ls v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml
ls v5/topology/instances/l1_devices/rtr-slate.yaml
```

### 1.2 Запустить quality gate

```bash
cd acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet
python quality-gate.py
```

Ожидаемый результат:
```
✓ Loaded X instances
✓ Schema validation: 0 issues
✓ Reference resolution: 0 issues
✓ Port existence validation: 0 issues
✓ Endpoint consistency: 0 warnings
✅ All quality gates PASSED
```

Quality gate теперь проверяет:
- ✅ Schema: required fields, enum values, numeric ranges
- ✅ References: device_ref, link_ref, creates_channel_ref всё разрешается
- ✅ **Port existence**: каждый port существует на device object definition
- ✅ Endpoint consistency: cable и channel endpoints совпадают

---

## 2. Compile & Validation (10 минут)

### 2.1 Запустить compile с TUC fixture

```bash
cd c:\Users\Dmitri\PycharmProjects\home-lab

python v5/topology-tools/compile-topology.py \
  --topology v5/topology/topology.yaml \
  --strict-model-lock \
  --output-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-test.json \
  --diagnostics-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-test.json \
  --diagnostics-txt acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-test.txt
```

Ожидаемый результат:
```
Compile completed: errors=0, warnings=0
```

### 2.2 Проверить что кабель инстанс скомпилировался

```bash
# Поищи кабель в compiled JSON
cat acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-test.json | \
  grep -A 20 "inst.ethernet_cable.cat5e"
```

Ожидаемый результат:
```
"instance": "inst.ethernet_cable.cat5e",
"object_ref": "obj.network.ethernet_cable",
"class_ref": "class.network.physical_link",
"length_m": 3,
"shielding": "utp",
"category": "cat5e",
...
```

### 2.3 Проверить что канал инстанс скомпилировался

```bash
cat acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-test.json | \
  grep -A 20 "inst.chan.eth.chateau_to_slate"
```

Ожидаемый результат:
```
"instance": "inst.chan.eth.chateau_to_slate",
"object_ref": "obj.network.ethernet_channel",
"class_ref": "class.network.data_link",
"link_ref": "inst.ethernet_cable.cat5e",
...
```

---

## 3. Проверка портов (10 минут)

### 3.1 Какие порты доступны на каждом роутере?

**MikroTik Chateau LTE7 AX** (`rtr-mikrotik-chateau`):
```
ether1  (2.5 GbE WAN port)
ether2  (1 GbE LAN port 1)   ← используется в TUC fixture
ether3  (1 GbE LAN port 2)
ether4  (1 GbE LAN port 3)
ether5  (1 GbE LAN port 4)
wlan1   (5 GHz WiFi 6)
wlan2   (2.4 GHz WiFi 6)
lte1    (LTE modem)
usb1    (USB 2.0)
```

**GL.iNet Slate AX1800** (`rtr-slate`):
```
wan     (1 GbE WAN port, blue)
lan1    (1 GbE LAN port 1, yellow)   ← используется в TUC fixture
lan2    (1 GbE LAN port 2, yellow)
wlan0   (5 GHz WiFi 6)
wlan1   (2.4 GHz WiFi 6)
usb1    (USB 3.0)
```

### 3.2 Валидировать что ports совпадают

```bash
# MikroTik: ether2 должна быть в описании объекта
grep "ether2" v5/topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml

# GL.iNet: lan1 должна быть в описании объекта
grep "lan1" v5/topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml

# Проверить что в cable fixture используются правильные порты
cat v5/topology/instances/l1_devices/inst.ethernet_cable.cat5e.yaml | grep -A 2 "endpoint_"
```

Ожидаемый результат:
```
endpoint_a:
  device_ref: rtr-mikrotik-chateau
  port: ether2              ← ether2 определена в MikroTik объекте
endpoint_b:
  device_ref: rtr-slate
  port: lan1                ← lan1 определена в GL.iNet объекте
```

### 3.3 Протестировать неправильный port

```bash
# Временно отредактировать cable fixture с неправильным портом
sed -i 's/port: ether2/port: ether99/' v5/topology/instances/l1_devices/inst.ethernet_cable.cat5e.yaml

# Запустить quality gate
python acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/quality-gate.py

# Ожидаемый результат: Port existence validation ошибка
# Expected error: "port 'ether99' not found on device 'rtr-mikrotik-chateau' (obj.mikrotik.chateau_lte7_ax).
#                 Available ports: ether1, ether2, ether3, ether4, ether5, lte1, usb1, wlan1, wlan2"

# Вернуть правильный port
sed -i 's/port: ether99/port: ether2/' v5/topology/instances/l1_devices/inst.ethernet_cable.cat5e.yaml
```

---

## 4. Run TUC Test Suite (15 минут)

### 4.1 Запустить все TUC-0001 тесты

```bash
cd c:\Users\Dmitri\PycharmProjects\home-lab

pytest -v v5/tests/plugin_integration/test_tuc0001_router_data_link.py
```

Ожидаемый результат:
```
test_tuc0001_router_data_link.py::test_valid_cable_compiles PASSED
test_tuc0001_router_data_link.py::test_unknown_endpoint_device PASSED
test_tuc0001_router_data_link.py::test_unknown_port_mikrotik PASSED
test_tuc0001_router_data_link.py::test_unknown_port_glinet PASSED
test_tuc0001_router_data_link.py::test_wrong_cable_class PASSED
test_tuc0001_router_data_link.py::test_missing_creates_channel_ref PASSED
test_tuc0001_router_data_link.py::test_channel_link_mismatch PASSED
test_tuc0001_router_data_link.py::test_endpoint_pair_mismatch PASSED
test_tuc0001_router_data_link.py::test_preserve_instance_properties PASSED

============== 9 passed in X.XXs ==============
```

### 4.2 Проверить что нет регрессии в существующих тестах

```bash
pytest -q v5/tests/plugin_contract v5/tests/plugin_integration
```

Ожидаемый результат:
```
============== XX passed in X.XXs ==============
```

---

## 5. Interpret Results

- ✅ **Quality gate passed**: Schema и references в порядке
- ✅ **Compile succeeded**: Модель компилируется без ошибок
- ✅ **All tests passed**: Все сценарии работают как ожидается
- ✅ **Determinism OK**: Повторные запуски дают один результат
- ✅ **No regressions**: Существующие функции не сломаны

---

## Troubleshooting

### Качество gate падает

1. Проверить что все файлы существуют (шаг 1.1)
2. Запустить `quality-gate.py` с verbose выводом
3. Проверить в EVIDENCE-LOG какие ошибки было и как их чинили

### Compile не запускается

1. Убедиться что `v5/topology/topology.yaml` существует
2. Проверить логи ошибок в `diagnostics-test.txt`
3. Убедиться что класс/объект файлы валидны YAML

### Тесты падают

1. Запустить с `-vv` флагом для подробного вывода
2. Проверить что fixtures в `v5/tests/fixtures/` актуальны
3. Прочитать ошибку в stdout — часто это ошибка валидации

---

## Next Steps

- Запустить все 4 новых теста (TUC1-T12..15) по мере готовности
- Добавить Performance baseline для compile time
- Расширить на другие router типы (Ubiquiti, Cisco, etc.)

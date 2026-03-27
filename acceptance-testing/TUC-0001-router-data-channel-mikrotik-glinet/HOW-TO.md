# TUC-0001 How-To

Короткая инструкция для текущей структуры проекта (без `v5/` путей).

## 1. Быстрый smoke-check

```powershell
Get-Item topology/class-modules/network/class.network.physical_link.yaml
Get-Item topology/class-modules/network/class.network.data_link.yaml
Get-Item topology/object-modules/network/obj.network.ethernet_cable.yaml
Get-Item topology/object-modules/network/obj.network.ethernet_channel.yaml
Get-Item projects/home-lab/topology/instances/L1-foundation/devices/rtr-mikrotik-chateau.yaml
Get-Item projects/home-lab/topology/instances/L1-foundation/devices/rtr-slate.yaml
Get-Item projects/home-lab/topology/instances/L1-foundation/physical-links/inst.ethernet_cable.cat5e.yaml
Get-Item projects/home-lab/topology/instances/L2-network/data-channels/inst.chan.eth.chateau_to_slate.yaml
```

## 2. Запустить TUC quality-gate

```powershell
.\.venv\Scripts\python.exe acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/quality-gate.py
```

Ожидаемо: `Quality gate passed: no errors detected.`

## 3. Запустить автоматические TUC-тесты

```powershell
.\.venv\Scripts\python.exe -m pytest tests/plugin_integration/test_tuc0001_router_data_link.py -q
```

Ожидаемо: `10 passed`.

## 4. Ручной compile для артефактов TUC

```powershell
.\.venv\Scripts\python.exe topology-tools/compile-topology.py `
  --topology topology/topology.yaml `
  --strict-model-lock `
  --output-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-test.json `
  --diagnostics-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-test.json `
  --diagnostics-txt acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-test.txt
```

## 5. Что проверять в effective JSON

- Есть `inst.ethernet_cable.cat5e` в `instances.physical-links`.
- У кабеля сохранены `length_m`, `shielding`, `category`, endpoints.
- Есть `inst.chan.eth.chateau_to_slate` в `instances.data-channels`.
- У устройств сохранены power bindings (`source_ref`, `outlet_ref` где применимо).

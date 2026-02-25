# Проверка переименования устройства mikrotik-chateau → rtr-mikrotik-chateau

**Дата:** 25 февраля 2026 г.

Выполните эти команды для проверки что переименование прошло корректно:

---

## 1️⃣ Быстрая проверка (валидатор)

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab
.venv\Scripts\activate

:: Запустить валидатор в strict режиме
python topology-tools\validate-topology.py --topology topology.yaml --strict
```

**Ожидаемый результат:** ✅ Валидация пройдет успешно (нет ошибок про отсутствующие device refs)

---

## 2️⃣ Проверка что новый ID используется (в топологии)

```cmd
:: Поиск старого имени (не должно быть)
grep -r "mikrotik-chateau" topology-tools\fixtures\new-only\topology\ 2>nul | findstr -v "^$"

:: Должен быть только один результат = старый файл (который нужно удалить):
:: topology-tools\fixtures\new-only\topology\L1-foundation\devices\owned\network\mikrotik-chateau.yaml

:: Поиск нового имени (должно быть много)
grep -r "rtr-mikrotik-chateau" topology-tools\fixtures\new-only\topology\ | wc -l
```

**Ожидаемый результат:** ~20-25 упоминаний нового имени в новой fixtures папке

---

## 3️⃣ Запустить генераторы

```cmd
:: Сгенерировать все файлы
python topology-tools\regenerate-all.py

:: Проверить что generated/ файлы обновлены
git diff --stat generated/
```

**Ожидаемый результат:** Generated файлы обновлены с новым device ID

---

## 4️⃣ Запустить тесты

```cmd
:: Unit-тесты валидаторов
python -m pytest tests\unit -v

:: Integration skeleton-тесты
python -m pytest tests\integration -q
```

**Ожидаемый результат:** ✅ Все тесты зелёные

---

## 5️⃣ Создать PR

```cmd
:: Отправить все изменения в PR
scripts\create_validators_pr.cmd
```

---

## 📋 Чеклист завершения

- [ ] Запустил валидатор — OK
- [ ] Проверил что нет старого имена mikrotik-chateau (кроме старого файла)
- [ ] Убедился что новое имя rtr-mikrotik-chateau используется везде
- [ ] Запустил генераторы — OK
- [ ] Запустил тесты — OK
- [ ] Удалил старые файлы (или они будут удалены в PR)
- [ ] Создал PR

---

## 🗑️ Удаление старых файлов

После проверки валидатора и генераторов удалите старые файлы:

```cmd
cd C:\Users\Dmitri\PycharmProjects\home-lab

:: Удалить старое устройство из основной топологии
del /Q topology\L1-foundation\devices\owned\network\mikrotik-chateau.yaml

:: Удалить старые host OS файлы из fixtures
del /Q topology-tools\fixtures\new-only\topology\L4-platform\host-operating-systems\hos-mikrotik-chateau-routeros.yaml
del /Q topology-tools\fixtures\mixed\topology\L4-platform\host-operating-systems\hos-mikrotik-chateau-routeros.yaml
del /Q topology-tools\fixtures\legacy-only\topology\L4-platform\host-operating-systems\hos-mikrotik-chateau-routeros.yaml

:: Удалить старые device файлы из fixtures
del /Q "topology-tools\fixtures\mixed\topology\L1-foundation\devices\owned\network\mikrotik-chateau.yaml"
del /Q "topology-tools\fixtures\legacy-only\topology\L1-foundation\devices\owned\network\mikrotik-chateau.yaml"

:: Проверить что всё удалено
git status | grep deleted
```

---

## 🚀 Финальный коммит

```cmd
git add .
git commit -m "refactor(device): rename mikrotik-chateau to rtr-mikrotik-chateau

- Rename device ID to follow naming convention (rtr- prefix for routers)
- Update all interface IDs (if-rtr-mikrotik-*)
- Update all device_ref, target_ref, gateway_device_ref, managed_by_ref throughout topology
- Update host OS ID (hos-rtr-mikrotik-chateau-routeros)
- Create new files with updated naming convention
- Delete legacy files (mikrotik-chateau.yaml)
- All validators and generators tested and working

Affected layers:
- L1: device definition and interface IDs
- L2: network routing, QoS, bridge management
- L4: host operating system configuration
- L5: service runtime targets and DNS records
- L6: observability and health checks
- L7: operations and power management"

git push -u origin feature/refactor-device-naming-mikrotik-chateau
```

---

**Статус:** ✅ Готово к PR

Все файлы обновлены, валидаторы и генераторы работают корректно.

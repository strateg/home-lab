# ✅ ADR 0064: Instance References Model Complete

**Дата:** 8 марта 2026
**Статус:** ✅ ЗАВЕРШЕНО
**Изменение:** Переход на instance references вместо bindings

---

## 🎯 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ

### Было (bindings к объектам)
```yaml
instance: pc-workstation-02
object_ref: obj.pc

bindings:
  firmware: obj.firmware.generic-uefi-x86
  os:
    - obj.os.windows-11
    - obj.os.debian-12
```

### Стало (прямые ссылки на instances)
```yaml
instance: pc-workstation-02
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs:
  - os.windows-11-enterprise
  - os.debian-12-production
```

---

## 💡 ПРЕИМУЩЕСТВА

1. **Консистентность с моделью class->object->instance**
   - Firmware: Class → Object → Instance
   - OS: Class → Object → Instance
   - Device: Class → Object → Instance
   - **Все одинаково!**

2. **Firmware и OS тоже имеют instances**
   - `firmware.routeros-7-1` (instance)
   - `firmware.routeros-7-2` (другой instance того же объекта)
   - Можно tracking patch levels, deployment dates

3. **Явная версионность**
   - Один object `debian-12` может иметь:
     - `debian-12-production` (stable)
     - `debian-12-staging` (testing)
     - `debian-12-development` (latest)

4. **Упрощенная семантика**
   - Не нужно разбираться с `bindings.firmware` vs `firmware_ref`
   - Прямые ссылки: `firmware_ref`, `os_refs[]`

---

## 📋 ПОЛНАЯ ИЕРАРХИЯ

### Firmware
```
Class: firmware
  └─ Object: routeros-7
      ├─ Instance: routeros-7-1 (deployed 2024-01-15, patch 7.1.5)
      └─ Instance: routeros-7-2 (deployed 2024-03-01, patch 7.1.8)
```

### OS
```
Class: os
  └─ Object: debian-12
      ├─ Instance: debian-12-production (kernel 6.1.0-17)
      ├─ Instance: debian-12-staging (kernel 6.1.0-18)
      └─ Instance: debian-12-development (kernel 6.1.0-19)
```

### Device
```
Class: compute
  └─ Object: pc
      ├─ Instance: pc-workstation-01
      │   ├─ firmware_ref: firmware.generic-uefi-2.8
      │   └─ os_refs: [os.debian-12-production]
      └─ Instance: pc-workstation-02
          ├─ firmware_ref: firmware.generic-uefi-2.8
          └─ os_refs: [os.windows-11-enterprise, os.debian-12-production]
```

---

## 🔧 ПРИМЕРЫ

### PC с одной OS
```yaml
instance: pc-workstation-01
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs:
  - os.debian-12-production
```

### PC dual-boot
```yaml
instance: pc-workstation-02
object_ref: obj.pc

firmware_ref: firmware.generic-uefi-2.8
os_refs:
  - os.windows-11-enterprise
  - os.debian-12-production
```

### MacBook (embedded OS)
```yaml
instance: macbook-pro-01
object_ref: obj.macbook

firmware_ref: firmware.apple-m2-14.2
os_refs:
  - os.macos-14-production
```

### Orange Pi 5 dual-boot
```yaml
instance: sbc-orangepi-02
object_ref: obj.orange-pi-5

firmware_ref: firmware.uboot-2023.07-arm64
os_refs:
  - os.debian-12-arm64-production
  - os.ubuntu-2204-arm64-staging
```

### MikroTik Chateau LTE7ax
```yaml
instance: edge-mikrotik-chateau-01
object_ref: obj.mikrotik-chateau-lte7ax

firmware_ref: firmware.routeros-7-13-arm64
os_refs:
  - os.routeros-7-production
```

### PDU (no OS)
```yaml
instance: pdu-rack-a-01
object_ref: obj.apc-pdu

firmware_ref: firmware.apc-pdu-3.9.2
# os_refs: absent (forbidden by class policy)
```

---

## 📊 VALIDATION RULES

### Firmware Reference
- MUST reference existing firmware **instance**
- Instance's object MUST be class `firmware`
- Architecture MUST match device constraints

### OS References
- MUST reference existing OS **instances**
- Each instance's object MUST be class `os`
- Array length MUST satisfy `min_items` / `max_items`
- For `multi_boot: false`, exactly 1 item
- For `multi_boot: true`, 1 to `max_items` items

### Capabilities
- Derived from firmware instance's **object** properties
- Derived from OS instances' **object** properties
- Combined for service-device matching

---

## 📁 ОБНОВЛЕННЫЕ ФАЙЛЫ

✅ `adr/0064-os-taxonomy-object-property-model.md`
- Добавлен блок "Canonical Layer Semantics"
- Firmware objects → instances
- OS objects → instances
- Device bindings → firmware_ref + os_refs
- Validation rules обновлены
- Real-World Examples Matrix обновлена

---

## 💡 КЛЮЧЕВЫЕ ВЫВОДЫ

1. **Firmware и OS теперь полноценные entity с instances**
   - Не просто "объекты для binding"
   - Полная модель: class → object → instance

2. **Device instance ссылается на instances, не objects**
   - `firmware_ref: firmware.routeros-7-1`
   - `os_refs: [os.debian-12-production]`

3. **Tracking deployed versions**
   - Instance может иметь `deployment.installed_date`
   - Instance может иметь `deployment.patch_level`
   - Audit trail для firmware/OS versions

4. **Единая семантика везде**
   - `object: <name>` + `class_ref: class.<class>`
   - `instance: <name>` + `object_ref: obj.<object>`
   - Нет исключений!

---

**Статус:** ✅ ПОЛНОСТЬЮ ГОТОВО
**Дата:** 8 марта 2026
**Результат:** Instance references model внедрена в ADR 0064

👉 **Читайте:** `adr/0064-os-taxonomy-object-property-model.md`

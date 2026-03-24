# ✅ ADR 0064: Двухсущностная Модель (Firmware + OS)

**Дата:** 8 марта 2026
**Статус:** Утверждено
**Модель:** Firmware (обязательный) + OS (условный)

---

## 🎯 КЛЮЧЕВАЯ ИДЕЯ

Программный стек устройства состоит из **двух независимых слоев**:

1. **Firmware** (низкоуровневый) — программная основа устройства
2. **OS** (высокоуровневый) — операционная система поверх firmware

**Важно:** OS не существует без firmware. Firmware может существовать без OS.

---

## 📊 ДВА КЛАССА, ЧЕТКАЯ СЕМАНТИКА

### Class: firmware → Object: mikrotik-routeros7-firmware

```yaml
class: firmware
categories: [infrastructure, prerequisite, hardware-bound]

properties:
  vendor: mikrotik | apple | generic | apc
  family: routeros | apple_silicon | uefi | proprietary
  version: string
  architecture: x86_64 | arm64 | mips
  boot_stack: uefi | bios | proprietary | none
  hardware_locked: boolean
  vendor_locked: boolean

capabilities:
  - cap.firmware.{vendor}
  - cap.firmware.{family}
  - cap.firmware.arch.{architecture}
  - cap.firmware.boot.{boot_stack}
```

**Примеры объектов firmware:**
- `mikrotik-routeros7-firmware`
- `generic-uefi-x86-firmware`
- `apple-silicon-m2-firmware`
- `apc-pdu-mgmt-firmware`

### Class: os → Object: routeros-7, debian-12, macos-14

```yaml
class: os
categories: [infrastructure, prerequisite, runtime]

properties:
  family: linux | windows | macos | routeros
  distribution: debian | ubuntu | routeros | macos
  release: string
  release_id: string
  architecture: x86_64 | arm64
  init_system: systemd | launchd | proprietary
  package_manager: apt | brew | none

  # КРИТИЧНО
  installation_model: embedded | installable
  embedded_in_firmware: boolean
  independently_updatable: boolean

capabilities:
  - cap.os.{family}
  - cap.os.{distribution}
  - cap.os.{distribution}.{release_id}
  - cap.os.init.{init_system}
  - cap.os.pkg.{package_manager}
  - cap.os.embedded | cap.os.installable
```

**Примеры объектов OS:**
- `routeros-7` (embedded)
- `debian-12-generic` (installable)
- `macos-14` (embedded)
- `windows-11` (installable)

---

## 🔗 DEVICE BINDINGS

Устройства ссылаются на firmware **и** OS:

```yaml
# PC (single-boot)
bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.debian-12-generic

# PC (dual-boot Windows + Linux)
bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.windows-11
  os_secondary: obj.os.debian-12-generic

# PC (triple-boot)
bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.windows-11
  os_secondary: obj.os.debian-12-generic
  os_tertiary: obj.os.freebsd-14

# MacBook (no multi-boot)
bindings:
  firmware: obj.firmware.apple-silicon-m2
  os_primary: obj.os.macos-14
  # os_secondary: NOT ALLOWED (vendor policy)

# MikroTik Router
bindings:
  firmware: obj.firmware.mikrotik-routeros7
  os_primary: obj.os.routeros-7

# PDU (no OS)
bindings:
  firmware: obj.firmware.apc-pdu-mgmt
  # os отсутствует
```

---

## 🎛️ DEVICE POLICIES

Классы устройств задают политики:

```yaml
# class: compute.pc
firmware_policy: required
os_policy: installable_allowed

# class: compute.macbook
firmware_policy: required
os_policy: embedded_only

# class: router.mikrotik
firmware_policy: required
os_policy: embedded_only

# class: power.pdu
firmware_policy: required
os_policy: forbidden
```

---

## 🧩 CAPABILITIES ОТ ОБОИХ СЛОЕВ

Компилятор выводит capabilities из **firmware + OS**:

```yaml
# Device: PC с Debian
bindings:
  firmware: obj.firmware.generic-uefi-x86
  os: obj.os.debian-12-generic

effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.arch.x86_64
  from_os:
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
    - cap.os.installable
```

---

## 📋 РЕАЛЬНЫЕ ПРИМЕРЫ

| Устройство | Firmware | OS | Тип OS | Заметки |
|------------|----------|----|----|---------|
| **PC** | generic-uefi-x86 | debian-12 | installable | Пользователь может менять OS |
| **PC dual-boot** | generic-uefi-x86 | windows-11 + debian-12 | installable | Два OS на одном устройстве |
| **PC triple-boot** | generic-uefi-x86 | windows + debian + freebsd | installable | Три OS на одном устройстве |
| **MacBook** | apple-silicon-m2 | macos-14 | embedded | Vendor-locked, НЕТ multi-boot |
| **Orange Pi 5** | generic-arm64-uboot | debian-12-arm64 | installable | ARM SBC, RK3588S |
| **Orange Pi 5 dual-boot** | generic-arm64-uboot | debian + ubuntu (ARM64) | installable | Два ARM дистрибутива |
| **MikroTik Chateau LTE7ax** | mikrotik-chateau-lte7ax | routeros-7 | embedded | Edge compute + LTE |
| **MikroTik** | mikrotik-routeros7 | routeros-7 | embedded | OS часть firmware |
| **PDU** | apc-pdu-mgmt | (нет) | N/A | Только firmware |

---

## ✅ ПРЕИМУЩЕСТВА

1. **Firmware и OS разделены**
   - Firmware — базовый слой (всегда есть)
   - OS — управляющий слой (может быть или нет)

2. **Четкая семантика**
   - `class: firmware` → `object: mikrotik-firmware`
   - `class: os` → `object: routeros-7`

3. **Capabilities от двух слоев**
   - Firmware: `cap.firmware.*`
   - OS: `cap.os.*`
   - Сервисы могут требовать capabilities от обоих

4. **Embedded vs installable явно**
   - MikroTik: firmware содержит embedded OS
   - PC: firmware + installable OS
   - Четко моделирует реальность

5. **PDU не "OS-less device", а "firmware-only device"**
   - Firmware есть (управление SNMP)
   - OS нет (не нужна)

---

## 🚀 МИГРАЦИЯ: 5 ФАЗ

**Phase 1 (нед 1-2):** Определить firmware и OS классы
**Phase 2 (нед 3-5):** Создать firmware и OS объекты
**Phase 3 (нед 6-7):** Device bindings, параллельная валидация
**Phase 4 (нед 8):** Deprecation старой модели
**Phase 5 (нед 9+):** Cleanup

**Риск:** LOW (reversible до Phase 4)

---

## 📍 ГДЕ НАЙТИ

**Обновленный ADR:**
`adr/0064-os-taxonomy-object-property-model.md`

**Анализ:**
`adr/0064-analysis/` (13 документов)

**Key Concepts:**
- Firmware: программная основа устройства
- OS: операционная система поверх firmware
- Embedded OS: часть firmware, не заменяется независимо
- Installable OS: независимый от firmware, может меняться

---

**Дата утверждения:** 8 марта 2026
**Статус:** ✅ Утверждено
**Следующий шаг:** Phase 1 kickoff (неделя 22 марта)

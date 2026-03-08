# ✅ ADR 0064: Multi-boot Support Added

**Дата:** 8 марта 2026  
**Обновление:** Добавлена поддержка multi-boot для PC

---

## 🎯 ЧТО ДОБАВЛЕНО

### PC Multi-boot Support

PC теперь явно поддерживает multi-boot конфигурации:

```yaml
# class: compute.pc
bindings:
  firmware: {required: true}
  os_primary: {required: true}
  os_secondary: {required: false}  # For dual-boot
  os_tertiary: {required: false}   # For triple-boot
```

---

## 📊 ПРИМЕРЫ

### Single-boot PC
```yaml
name: pc-workstation-01
class: compute.pc

bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.debian-12-generic
```

### Dual-boot PC (Windows + Linux)
```yaml
name: pc-workstation-02
class: compute.pc

bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.windows-11
  os_secondary: obj.os.debian-12-generic
```

### Triple-boot PC
```yaml
name: pc-developer-01
class: compute.pc

bindings:
  firmware: obj.firmware.generic-uefi-x86
  os_primary: obj.os.windows-11
  os_secondary: obj.os.debian-12-generic
  os_tertiary: obj.os.freebsd-14
```

---

## 🧩 CAPABILITIES ОТ ВСЕХ OS

Multi-boot PC имеет capabilities от **всех установленных OS**:

```yaml
# PC dual-boot: Windows + Linux
effective_capabilities:
  from_firmware:
    - cap.firmware.generic
    - cap.firmware.uefi
    - cap.firmware.arch.x86_64
  from_os_primary (Windows):
    - cap.os.windows
    - cap.os.windows.11
  from_os_secondary (Linux):
    - cap.os.linux
    - cap.os.debian
    - cap.os.debian.12
    - cap.os.init.systemd
    - cap.os.pkg.apt
  
# Результат: устройство может запускать сервисы для Windows ИЛИ Linux
```

---

## ⚠️ VALIDATION RULES

### Multi-boot Constraints:

1. Все OS bindings MUST быть `installable`
2. Все OS MUST иметь compatible architecture с firmware
3. Class MUST разрешать multi-boot (`supports_multiboot: true`)
4. MacBook и embedded-only devices: только один OS binding

### MacBook НЕ поддерживает multi-boot:

```yaml
# class: compute.macbook
os_policy: embedded_only

bindings:
  firmware: {required: true}
  os_primary: {required: true}
  # os_secondary: NOT ALLOWED
```

---

## 📋 ТАБЛИЦА ПРИМЕРОВ

| Устройство | Multi-boot | OS Bindings | Заметки |
|------------|-----------|-------------|---------|
| **PC** | ✅ YES | os_primary + os_secondary + os_tertiary | До 3 OS |
| **MacBook** | ❌ NO | os_primary only | Vendor-locked |
| **MikroTik** | ❌ NO | os_primary only | Embedded OS |
| **Raspberry Pi** | ✅ YES | os_primary + os_secondary | SD card swap |

---

## 📁 ОБНОВЛЕННЫЕ ФАЙЛЫ

✅ `adr/0064-os-taxonomy-object-property-model.md`
- Добавлена секция про multi-boot bindings
- Примеры dual-boot и triple-boot PC
- Validation rules для multi-boot
- Capability derivation от всех OS

✅ `adr/0064-analysis/РЕШЕНИЕ-Path-C-Завершено.md`
- Примеры multi-boot добавлены

✅ `adr/0064-analysis/ADR-0064-ДВУХСУЩНОСТНАЯ-МОДЕЛЬ.md`
- Примеры multi-boot добавлены

✅ `ИТОГ-ДВУХСУЩНОСТНАЯ-МОДЕЛЬ.md`
- Device policies обновлены для multi-boot

---

## 💡 КЛЮЧЕВЫЕ МОМЕНТЫ

1. **PC поддерживает multi-boot**
   - До 3 OS: primary, secondary, tertiary
   - Все MUST быть installable
   - Capabilities от ВСЕХ OS

2. **MacBook НЕ поддерживает multi-boot**
   - Vendor policy: embedded_only
   - Только один OS binding
   - Нельзя добавить secondary OS

3. **Capabilities комбинируются**
   - Dual-boot PC имеет capabilities и от Windows, и от Linux
   - Сервисы могут быть deployed в любой OS context
   - Compiler validates против всех установленных OS

4. **Boot manager управляет выбором**
   - UEFI/GRUB выбирает OS при загрузке
   - Default OS = os_primary
   - Alternative OS = os_secondary, os_tertiary

---

**Статус:** ✅ ДОБАВЛЕНО  
**Дата:** 8 марта 2026  

👉 **Читайте:** `adr/0064-os-taxonomy-object-property-model.md` (обновлено)

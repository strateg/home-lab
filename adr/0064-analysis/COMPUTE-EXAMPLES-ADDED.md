# ✅ Compute Examples Added: MikroTik Chateau LTE7ax & Orange Pi 5

**Дата:** 8 марта 2026  
**Добавлено:** Два новых примера compute устройств в ADR 0064

---

## 🎯 ЧТО ДОБАВЛЕНО

### 1. MikroTik Chateau LTE7ax (Edge Compute)

**Класс устройства:** `compute.edge`

**Характеристики:**
- ARM64 процессор
- Embedded RouterOS 7
- LTE/5G connectivity
- WiFi 6 (802.11ax)
- Может запускать containers + routing/firewall одновременно

**Firmware:**
```yaml
# object: mikrotik-chateau-lte7ax-firmware
class: firmware
properties:
  vendor: mikrotik
  family: routeros
  version: "7.13"
  architecture: arm64
  boot_stack: proprietary
  hardware_locked: true
  vendor_locked: true
```

**OS:**
```yaml
# object: routeros-7 (embedded)
class: os
properties:
  family: routeros
  distribution: routeros
  release: "7.1"
  architecture: arm64  # Note: ARM64, not x86_64
  installation_model: embedded
  embedded_in_firmware: true
```

**Device Instance:**
```yaml
name: edge-mikrotik-chateau-01
class: compute.edge

bindings:
  firmware: obj.firmware.mikrotik-chateau-lte7ax
  os_primary: obj.os.routeros-7
```

**Capabilities:**
- `cap.firmware.mikrotik`
- `cap.firmware.routeros`
- `cap.firmware.arch.arm64`
- `cap.os.routeros`
- `cap.os.routeros.7`
- `cap.os.embedded`

---

### 2. Orange Pi 5 (ARM SBC)

**Класс устройства:** `compute.sbc` (Single-Board Computer)

**Характеристики:**
- Rockchip RK3588S (ARM64)
- 8-16GB RAM
- SD card / eMMC boot
- U-Boot firmware
- Supports multiple ARM64 Linux distributions
- Multi-boot capable

**Firmware:**
```yaml
# object: generic-arm64-uboot-firmware
class: firmware
properties:
  vendor: generic
  family: uboot
  version: "2023.07"
  architecture: arm64
  boot_stack: uboot
  hardware_locked: false
  vendor_locked: false
```

**OS Objects:**
```yaml
# object: debian-12-arm64
class: os
properties:
  family: linux
  distribution: debian
  release: "12"
  architecture: arm64
  installation_model: installable
  supports_multiboot: true
  base_image_format: rootfs

# object: ubuntu-22.04-arm64
class: os
properties:
  family: linux
  distribution: ubuntu
  release: "22.04"
  architecture: arm64
  installation_model: installable
  supports_multiboot: true
  base_image_format: rootfs
```

**Device Instance (single-boot):**
```yaml
name: sbc-orangepi-01
class: compute.sbc

bindings:
  firmware: obj.firmware.generic-arm64-uboot
  os_primary: obj.os.debian-12-arm64
```

**Device Instance (dual-boot):**
```yaml
name: sbc-orangepi-02
class: compute.sbc

bindings:
  firmware: obj.firmware.generic-arm64-uboot
  os_primary: obj.os.debian-12-arm64
  os_secondary: obj.os.ubuntu-22.04-arm64
```

**Capabilities (single-boot):**
- `cap.firmware.generic`
- `cap.firmware.uboot`
- `cap.firmware.arch.arm64`
- `cap.os.linux`
- `cap.os.debian`
- `cap.os.debian.12`
- `cap.os.init.systemd`
- `cap.os.pkg.apt`
- `cap.os.installable`

**Capabilities (dual-boot добавляет):**
- `cap.os.ubuntu`
- `cap.os.ubuntu.2204`

---

## 🏗️ НОВЫЕ COMPUTE КЛАССЫ

### compute.sbc (Single-Board Computer)

```yaml
class: compute.sbc
firmware_policy: required
os_policy: installable_allowed

bindings:
  firmware: {required: true, class: firmware}
  os_primary: {required: true, class: os}
  os_secondary: {required: false, class: os}
  
os_constraints:
  installation_model: [installable]
  supports_multiboot: true
  architecture: [arm64, armhf]
```

**Примеры:** Orange Pi 5, Raspberry Pi, Rock Pi, Banana Pi

### compute.edge (Edge Compute Device)

```yaml
class: compute.edge
firmware_policy: required
os_policy: embedded_only

bindings:
  firmware: {required: true, class: firmware}
  os_primary: {required: true, class: os}
  
os_constraints:
  installation_model: [embedded]
```

**Примеры:** MikroTik Chateau LTE7ax, edge routers с container support

---

## 📊 СРАВНЕНИЕ

| Аспект | MikroTik Chateau LTE7ax | Orange Pi 5 |
|--------|-------------------------|-------------|
| **Класс** | compute.edge | compute.sbc |
| **Architecture** | ARM64 | ARM64 |
| **Firmware** | Proprietary (MikroTik) | Generic U-Boot |
| **OS Model** | Embedded | Installable |
| **Multi-boot** | ❌ NO | ✅ YES |
| **OS Choice** | RouterOS only | Debian, Ubuntu, etc. |
| **Update Model** | Firmware package | OS package manager |
| **Use Case** | Edge compute + routing | General purpose SBC |

---

## 🔧 USE CASES

### MikroTik Chateau LTE7ax

**Сценарии использования:**
- Remote site edge computing
- LTE/5G connectivity gateway
- Container workloads + routing
- IoT gateway с wireless connectivity
- Branch office compute + firewall

**Преимущества:**
- Integrated routing/firewall
- Container support
- LTE modem встроен
- WiFi 6 access point

### Orange Pi 5

**Сценарии использования:**
- Development workstation (ARM)
- Media server
- Home automation controller
- Learning platform для ARM64
- Kubernetes worker node

**Преимущества:**
- High performance (RK3588S)
- Large RAM (до 16GB)
- Flexible OS choice
- Multi-boot для testing

---

## 📁 ОБНОВЛЕННЫЕ ФАЙЛЫ

✅ `adr/0064-os-taxonomy-object-property-model.md`
- Добавлены firmware objects для Chateau и U-Boot
- Добавлены OS objects для ARM64 (Debian, Ubuntu)
- Добавлены device instances
- Добавлены compute.sbc и compute.edge классы
- Обновлена таблица Real-World Examples

✅ `adr/0064-analysis/РЕШЕНИЕ-Path-C-Завершено.md`
- Обновлена таблица примеров

---

## 💡 КЛЮЧЕВЫЕ ВЫВОДЫ

1. **ARM64 архитектура поддерживается**
   - Firmware: U-Boot для SBC, proprietary для MikroTik
   - OS: Debian ARM64, Ubuntu ARM64, RouterOS ARM64

2. **Compute класс разнообразен**
   - `compute.pc`: x86_64, installable, multi-boot
   - `compute.sbc`: ARM64, installable, multi-boot
   - `compute.edge`: ARM64, embedded, single-OS
   - `compute.macbook`: ARM64, embedded, vendor-locked

3. **Embedded vs Installable applies to ARM**
   - MikroTik: embedded RouterOS (ARM64)
   - Orange Pi: installable Linux (ARM64)

4. **Multi-boot works on ARM SBCs**
   - Orange Pi может dual-boot Debian + Ubuntu
   - Partition-based или SD card swap

---

**Статус:** ✅ ДОБАВЛЕНО  
**Дата:** 8 марта 2026  
**Файлы:** ADR 0064 + русские резюме обновлены

👉 **Читайте:** `adr/0064-os-taxonomy-object-property-model.md`

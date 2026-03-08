# ✅ Анализ ADR 0064: VM/LXC/Docker

**Дата:** 8 марта 2026  
**Статус:** ✅ ЗАВЕРШЕНО  
**Результат:** VM поддержаны, LXC/Docker отложены

---

## 🎯 ОСНОВНЫЕ ВЫВОДЫ

### ✅ Виртуальные машины (VM) - ПОЛНОСТЬЮ ПОДДЕРЖИВАЮТСЯ

**Вывод:** Модель firmware + OS **идеально подходит** для VM.

**Что добавлено в ADR 0064:**
1. ✅ Виртуальные firmware объекты (KVM OVMF, VMware EFI, Hyper-V)
2. ✅ Свойство `virtual: true` для firmware
3. ✅ Примеры VM instances
4. ✅ Обновлена таблица примеров

**VM = Physical Machine** (с виртуальным firmware)

### ⚠️ LXC контейнеры - НУЖЕН БУДУЩИЙ ADR

**Проблема:** LXC делит ядро хоста, но имеет userspace OS.

**Что не работает:**
- Нет firmware (использует хост)
- Есть OS userspace но не ядро
- Нужен `firmware_ref: null`
- Нужен `host_ref` на хост

**Решение:** ADR 0065 (Q2 2026)

### ❌ Docker контейнеры - НУЖЕН ОТДЕЛЬНЫЙ ADR

**Проблема:** Docker контейнеры **НЕ являются ОС**.

**Что не работает:**
- Нет firmware
- Нет полной OS (только base image)
- Нет init system, package manager
- Это runtime environment, не OS

**Решение:** ADR 0066 для container runtime (Q3 2026)

---

## 📊 МАТРИЦА ПРИМЕНИМОСТИ

| Технология | Firmware | OS | ADR 0064 | Действие |
|------------|----------|----|--------------------|----------|
| **Физический ПК** | ✅ BIOS/UEFI | ✅ Полная OS | ✅ Применимо | Нет |
| **Виртуальная машина** | ✅ Виртуальный | ✅ Полная OS | ✅ Применимо | ✅ Добавлено |
| **LXC контейнер** | ❌ Нет (общий) | ⚠️ Только userspace | ⚠️ Частично | 🔜 ADR 0065 |
| **Docker контейнер** | ❌ Нет (общий) | ❌ Не полная OS | ❌ Не применимо | 🔜 ADR 0066 |

---

## 🔧 ПРИМЕРЫ VM

### KVM виртуальная машина

```yaml
# Firmware объект
object: obj.firmware.kvm-ovmf
class_ref: class.firmware
properties:
  vendor: qemu
  family: uefi
  version: "edk2-20231129"
  virtual: true  # Виртуальный firmware

# Instance
instance: inst.compute.vm-app-01
object_ref: obj.compute.kvm-vm

firmware_ref: inst.firmware.kvm-ovmf-prod
os_refs: [inst.os.debian-12-prod]
hypervisor_ref: inst.compute.kvm-host-01
```

### VMware виртуальная машина

```yaml
# Firmware объект
object: obj.firmware.vmware-efi
class_ref: class.firmware
properties:
  vendor: vmware
  family: uefi
  virtual: true

# Instance
instance: inst.compute.vm-win-01
object_ref: obj.compute.vmware-vm

firmware_ref: inst.firmware.vmware-efi-v2.7
os_refs: [inst.os.windows-server-2022]
hypervisor_ref: inst.compute.esxi-host-01
```

---

## 💡 КЛЮЧЕВЫЕ ИНСАЙТЫ

### 1. VM = Physical Machine (с виртуальным firmware)

```
Физический ПК:        Виртуальная машина:
├─ UEFI firmware     ├─ Virtual UEFI (OVMF)
└─ Debian OS         └─ Debian OS

Одинаковая модель!
```

### 2. Типы виртуального firmware

| Гипервизор | Firmware объекты | Тип загрузки |
|------------|------------------|--------------|
| KVM/QEMU | kvm-bios, kvm-ovmf | BIOS или UEFI |
| VMware | vmware-bios, vmware-efi | BIOS или UEFI |
| Hyper-V | hyperv-gen1, hyperv-gen2 | BIOS или UEFI |
| Xen | xen-pv, xen-hvm | PV или HVM |

### 3. Контейнеры отличаются

**LXC:**
- Имеет OS userspace (systemd, apt)
- Делит ядро хоста
- Нужно расширение модели

**Docker:**
- Не имеет полной OS
- Только base image + приложение
- Нужен отдельный тип сущности

---

## 📁 СОЗДАННЫЕ ФАЙЛЫ

### Анализ
✅ `adr/0064-analysis/VM-LXC-DOCKER-ANALYSIS.md` - Полный анализ (10+ страниц)
✅ `adr/0064-analysis/VM-SUPPORT-COMPLETE.md` - Summary (английский)

### Обновления ADR 0064
✅ Добавлены виртуальные firmware объекты
✅ Добавлены примеры VM
✅ Обновлена таблица примеров

---

## 📋 ОТЛОЖЕНО НА БУДУЩЕЕ

### ADR 0065: LXC Container Extensions (Запланировано)

**Область:**
- Разрешить `firmware_ref: null` для контейнеров
- Добавить `kernel: shared|own` свойство
- Добавить `host_ref` для ссылки на хост
- Моделировать LXC/systemd-nspawn

**Сроки:** Q2 2026

### ADR 0066: Container Runtime Taxonomy (Запланировано)

**Область:**
- Создать новую сущность `runtime` (не `os`)
- Моделировать Docker/Podman/containerd
- Моделировать base images, языки, зависимости
- Определить capabilities для runtime

**Сроки:** Q3 2026

---

## ✅ ИТОГ

**ADR 0064 применим к:**

| ✅ Утверждено | ⏸️ Отложено (будущий ADR) | ❌ Вне области |
|--------------|-------------------------|---------------|
| Физические машины | LXC контейнеры | Развертывание приложений |
| Виртуальные машины | systemd-nspawn | Kubernetes pods |
| Appliances | Вложенные VM | Service meshes |
| Edge устройства | | |

**Статус:**
- ✅ Поддержка VM: **ЗАВЕРШЕНА** (добавлено в ADR 0064)
- ⏸️ Поддержка LXC: **ЗАПЛАНИРОВАНА** (ADR 0065, Q2 2026)
- ⏸️ Поддержка Docker: **ЗАПЛАНИРОВАНА** (ADR 0066, Q3 2026)

---

**Анализ завершен:** 8 марта 2026  
**ADR 0064 обновлен:** 8 марта 2026  
**Следующий шаг:** Review, планирование ADR 0065/0066

👉 **Полный анализ:** `adr/0064-analysis/VM-LXC-DOCKER-ANALYSIS.md`  
👉 **Обновленный ADR:** `adr/0064-os-taxonomy-object-property-model.md`

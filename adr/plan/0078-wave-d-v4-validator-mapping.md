# Wave D Mapping: v4 Validators -> v5 Plugins

**Date:** 2026-03-22  
**Status:** Active (Wave D in progress)  
**Parent plan:** `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`

---

## 1. Goal

Составить рабочий mapping `v4 check_* -> v5 plugin`, определить уже покрытые области и явные gap'ы для поэтапной миграции.

---

## 2. Current v5 Validator Surface

Наличие сейчас:

1. `base.validator.references`
2. `base.validator.model_lock`
3. `base.validator.power_source_refs`
4. `base.validator.embedded_in`
5. `base.validator.ethernet_port_inventory`
6. `base.validator.capability_contract`
7. `base.validator.instance_placeholders`
8. `class_router.validator_json.router_data_channel_interface`
9. `object_network.validator_json.ethernet_cable_endpoints`
10. `object_mikrotik.validator_json.router_ports`
11. `object_glinet.validator_json.router_ports`

---

## 3. Mapping Table

Legend:

- `Covered` - функционально закрыто существующим v5 plugin.
- `Partial` - закрыта только часть семантики, нужен отдельный migration plugin.
- `Gap` - покрытия нет.
- `Superseded` - проверка заменена другой v5 контрактной механикой.

### 3.1 Foundation

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_modular_include_contract` | new `base.validator.foundation.include_contract` | Gap | В v5 нет отдельного plugin-first include-contract валидатора. |
| `check_file_placement` | `base.validator.foundation_layout` + future `base.validator.foundation.file_placement` | Partial | Добавлен baseline root/layout validator; policy-driven directory taxonomy ещё не перенесена. |
| `check_device_taxonomy` | `base.validator.references` + `base.validator.capability_contract` | Partial | Нужен отдельный taxonomy plugin для parity с v4 foundation checks. |

### 3.2 Governance

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_l0_contracts` | `base.validator.governance_contract` | Partial | Добавлен v5 governance contract validator (framework/project/meta + metadata dates/changelog); нужно расширить parity по refs/defaults. |
| `check_version` | `base.validator.governance_contract` + compiler/model contract checks | Covered/Partial | Проверка major-version добавлена в plugin; parity по v4 warning semantics можно расширять отдельно. |
| `check_ip_overlaps` | `base.validator.network_ip_overlap` | Partial | Добавлен duplicate IP detector по normalized rows; можно расширить parity по network-scoped error/warning semantics. |

### 3.3 Network

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_vlan_tags` | `base.validator.network_vlan_tags` | Covered/Partial | Добавлен validator для workload vlan_tag consistency (mismatch/missing/non-vlan-aware bridge warnings). |
| `check_network_refs` | `base.validator.references` + `base.validator.network_core_refs` | Partial | Добавлена core проверка VLAN refs (bridge/trust_zone/managed_by); policy scope всё ещё шире в v4. |
| `check_bridge_refs` | `base.validator.network_core_refs` | Covered/Partial | Добавлена bridge.host_ref existence/layer validation. |
| `check_data_links` | `object_network.validator_json.ethernet_cable_endpoints` | Partial | Закрыта ethernet data-link ветка (`E7304-E7308`), не весь legacy scope. |
| `check_power_links` | `base.validator.power_source_refs` | Covered/Partial | Основная семантика power.source_ref/occupancy есть; проверить parity по edge cases. |
| `check_mtu_consistency` | `base.validator.network_mtu_consistency` | Covered/Partial | Добавлен validator для jumbo_frames=true при mtu<=1500. |
| `check_vlan_zone_consistency` | `base.validator.network_vlan_zone_consistency` | Covered/Partial | Добавлен warning-based validator для VLAN id vs trust-zone vlan_ids контракта. |
| `check_reserved_ranges` | `base.validator.network_reserved_ranges` | Partial | Добавлен validator для VLAN reserved_ranges (границы CIDR + overlap); можно расширить на все network object shapes при необходимости. |
| `check_trust_zone_firewall_refs` | `base.validator.network_trust_zone_firewall_refs` | Covered/Partial | Добавлен validator для default_firewall_policy_ref trust-zone instances. |
| `check_firewall_policy_addressability` | `base.validator.network_firewall_addressability` | Partial | Добавлен warning-based validator для addressability refs (dhcp network refs / zones without static CIDR). |
| `check_ip_allocation_host_os_refs` | `base.validator.network_ip_allocation_host_os_refs` | Partial | Добавлен validator для host_os_ref/device_ref consistency внутри network ip_allocations. |
| `check_runtime_network_reachability` | new `base.validator.network.runtime_reachability` | Gap | |
| `check_single_active_os_per_device` | `base.validator.single_active_os` | Covered/Partial | Добавлен single-active-os validator по normalized rows; при необходимости расширить parity под legacy host_operating_systems inventory. |

### 3.4 References

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_host_os_refs` | `base.validator.embedded_in` + `base.validator.references` + `base.validator.runtime_target_os_binding` | Partial | Добавлена runtime-target OS binding проверка; остаётся расширить parity по host_os/storage-specific правилам. |
| `check_vm_refs` | `base.validator.references` | Partial | |
| `check_lxc_refs` | `base.validator.references` | Partial | |
| `check_service_refs` | `base.validator.references` + `base.validator.service_runtime_refs` + `base.validator.runtime_target_os_binding` | Partial | Добавлен runtime refs validator (type/target/network_binding); legacy service policy checks ещё шире. |
| `check_dns_refs` | `base.validator.references` | Partial | |
| `check_certificate_refs` | `base.validator.references` | Partial | |
| `check_backup_refs` | `base.validator.references` | Partial | |
| `check_security_policy_refs` | `base.validator.references` | Partial | |

### 3.5 Storage

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_device_storage_taxonomy` | new `base.validator.storage.device_taxonomy` | Gap | |
| `check_l1_media_inventory` | new `base.validator.storage.media_inventory` | Gap | |
| `check_l3_storage_refs` | `base.validator.references` + `base.validator.storage_l3_refs` | Partial | Добавлен L3 storage refs validator (volume->pool, data_asset->volume); расширить parity для partition/vg/lv/filesystem/mount/storage_endpoint. |

---

## 4. Proposed Migration Batches (Wave D)

1. **D1 Foundation + Governance (high leverage, low coupling)**  
   First plugins: `foundation.include_contract`, `foundation.file_placement`, `governance.contracts`, `network.ip_overlap`.

2. **D2 Network policy validators**  
   VLAN/bridge/firewall/range/reachability family.

3. **D3 References parity split**  
   Разделить монолит `base.validator.references` на более узкие validators или ввести thin wrappers с прямой parity логикой.

4. **D4 Storage parity**  
   Перенос `device_storage_taxonomy`, `l1_media_inventory`, расширение `l3_storage_refs`.

---

## 5. Immediate Next Steps

1. Зафиксировать минимальный backlog plugin IDs в `v5/topology-tools/plugins/plugins.yaml` (через feature toggles disabled by default).
2. Портировать D1 governance checks с parity fixtures.
3. Добавить integration tests для каждого нового plugin (по 1 happy-path + 1 regression case).

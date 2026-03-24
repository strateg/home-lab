# Wave D Mapping: v4 Validators -> v5 Plugins

**Date:** 2026-03-22
**Status:** Completed (Wave D parity coverage established)
**Parent plan:** `adr/plan/0078-plugin-layering-and-v4-v5-migration-plan.md`

---

## 1. Goal

Составить рабочий mapping `v4 check_* -> v5 plugin`, определить уже покрытые области и явные gap'ы для поэтапной миграции.

---

## 2. Current v5 Validator Surface

Наличие сейчас (relevant subset for Wave D):

1. `base.validator.governance_contract`
2. `base.validator.foundation_layout`
3. `base.validator.foundation_include_contract`
4. `base.validator.references`
5. `base.validator.model_lock`
6. `base.validator.power_source_refs`
7. `base.validator.embedded_in`
8. `base.validator.ethernet_port_inventory`
9. `base.validator.capability_contract`
10. `base.validator.instance_placeholders`
11. `base.validator.network_ip_overlap`
12. `base.validator.single_active_os`
13. `base.validator.network_reserved_ranges`
14. `base.validator.network_trust_zone_firewall_refs`
15. `base.validator.network_firewall_addressability`
16. `base.validator.network_ip_allocation_host_os_refs`
17. `base.validator.network_vlan_zone_consistency`
18. `base.validator.network_core_refs`
19. `base.validator.network_vlan_tags`
20. `base.validator.network_mtu_consistency`
21. `base.validator.service_runtime_refs`
22. `base.validator.runtime_target_os_binding`
23. `base.validator.network_runtime_reachability`
24. `base.validator.storage_l3_refs`
25. `base.validator.storage_device_taxonomy`
26. `base.validator.storage_media_inventory`
27. `base.validator.dns_refs`
28. `base.validator.certificate_refs`
29. `base.validator.backup_refs`
30. `base.validator.security_policy_refs`
31. `class_router.validator_json.router_data_channel_interface`
32. `object_network.validator_json.ethernet_cable_endpoints`
33. `object_mikrotik.validator_json.router_ports`
34. `object_glinet.validator_json.router_ports`
35. `base.validator.vm_refs`
36. `base.validator.lxc_refs`
37. `base.validator.host_os_refs`

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
| `check_modular_include_contract` | `base.validator.foundation_include_contract` | Covered/Partial | Добавлен validator структуры `project/topology/instances` + запрет `_index.yaml`; возможна донастройка под дополнительные domain-specific контракты. |
| `check_file_placement` | `base.validator.foundation_layout` + `base.validator.foundation_file_placement` | Covered/Partial | Добавлен policy-driven placement validator (`layer/group/instance` path taxonomy + filename/id contract); staged cutover зависит от release preflight warning parity на project fixtures. |
| `check_device_taxonomy` | `base.validator.foundation_device_taxonomy` + `base.validator.references` + `base.validator.capability_contract` | Covered/Partial | Добавлен L1 group/class taxonomy validator; parity можно расширять дополнительными hardware/storage checks. |

### 3.2 Governance

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_l0_contracts` | `base.validator.governance_contract` | Covered/Partial | Добавлен v5 governance contract validator (framework/project/meta + metadata dates/changelog) + parity для `meta.defaults.refs.security_policy_ref` и `meta.defaults.refs.network_manager_device_ref` existence/layer checks. |
| `check_version` | `base.validator.governance_contract` + compiler/model contract checks | Covered/Partial | Проверка major-version добавлена в plugin; parity по v4 warning semantics можно расширять отдельно. |
| `check_ip_overlaps` | `base.validator.network_ip_overlap` | Covered/Partial | Добавлен duplicate IP detector по normalized rows + network-scoped duplicate IP allocation errors (`ip_allocations`) с глобальными overlap warnings (v4-style). |

### 3.3 Network

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_vlan_tags` | `base.validator.network_vlan_tags` | Covered/Partial | Добавлен validator для workload vlan_tag consistency (mismatch/missing/non-vlan-aware bridge warnings). |
| `check_network_refs` | `base.validator.references` + `base.validator.network_core_refs` | Covered/Partial | Добавлена core проверка VLAN refs (bridge/trust_zone/managed_by) с parity для object/extension/top-level payload путей; policy scope всё ещё шире в v4. |
| `check_bridge_refs` | `base.validator.network_core_refs` | Covered/Partial | Добавлена bridge.host_ref existence/layer validation. |
| `check_data_links` | `object_network.validator_json.ethernet_cable_endpoints` | Covered/Partial | Расширен validator на legacy/non-ethernet endpoint semantics (`device_ref/external_ref`, `interface_ref` ownership, provider-instance запрет, `power_delivery` medium/mode) + parity fixture. |
| `check_power_links` | `base.validator.power_source_refs` | Covered/Partial | Основная семантика power.source_ref/occupancy есть; проверить parity по edge cases. |
| `check_mtu_consistency` | `base.validator.network_mtu_consistency` | Covered/Partial | Добавлен validator для jumbo_frames=true при mtu<=1500. |
| `check_vlan_zone_consistency` | `base.validator.network_vlan_zone_consistency` | Covered/Partial | Добавлен warning-based validator для VLAN id vs trust-zone vlan_ids контракта. |
| `check_reserved_ranges` | `base.validator.network_reserved_ranges` | Covered/Partial | Добавлен validator для VLAN reserved_ranges (границы CIDR + overlap) с parity для object/extension/top-level payload путей и skip-семантикой для `cidr=dhcp`; можно расширить на non-VLAN network object shapes при необходимости. |
| `check_trust_zone_firewall_refs` | `base.validator.network_trust_zone_firewall_refs` | Covered/Partial | Добавлен validator для default_firewall_policy_ref trust-zone instances. |
| `check_firewall_policy_addressability` | `base.validator.network_firewall_addressability` | Covered/Partial | Добавлен warning-based validator для addressability refs (dhcp network refs / zones without static CIDR) с parity для object/extension/top-level payload путей. |
| `check_ip_allocation_host_os_refs` | `base.validator.network_ip_allocation_host_os_refs` | Covered/Partial | Добавлен validator для host_os_ref/device_ref consistency внутри network ip_allocations + parity для правил `either host_os_ref or device_ref required`, deprecation warning по `device_ref` (c suggestion) и object/extension/top-level payload путей. |
| `check_runtime_network_reachability` | `base.validator.network_runtime_reachability` | Covered/Partial | Добавлен warning-based validator reachability для runtime.network_binding_ref (lxc/vm/docker/baremetal) + parity для top-level/extension payload путей и active-only host_os reachability semantics. |
| `check_single_active_os_per_device` | `base.validator.single_active_os` | Covered/Partial | Добавлен single-active-os validator по normalized rows; при необходимости расширить parity под legacy host_operating_systems inventory. |

### 3.4 References

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_host_os_refs` | `base.validator.embedded_in` + `base.validator.references` + `base.validator.runtime_target_os_binding` + `base.validator.host_os_refs` | Covered/Partial | Добавлен host_os thin-wrapper: runtime-target device OS binding parity + host_os architecture/device parity + installation.root_storage_endpoint_ref mount-device consistency + host_type installation requirement + host_type/capabilities compatibility + canonical/unsupported architecture checks (extensions + legacy top-level host_os fields). |
| `check_vm_refs` | `base.validator.references` + `base.validator.vm_refs` | Covered/Partial | Добавлен VM thin-wrapper (`device_ref/trust_zone_ref/host_os_ref/template_ref/networks/storage`) + host_os/device binding parity (`os_refs` membership, host_os_ref required on multi-active bindings) + resolved-host capability checks (`vm`), bridge refs, storage endpoint platform (`proxmox`) и guest/template/host architecture parity. |
| `check_lxc_refs` | `base.validator.references` + `base.validator.lxc_refs` | Covered/Partial | Добавлен LXC thin-wrapper (`device_ref/trust_zone_ref/host_os_ref/template_ref/networks/storage rootfs/volumes`) + host_os/device binding parity (`os_refs` membership, host_os_ref required on multi-active bindings) + resolved-host capability checks (`lxc`), bridge refs, storage endpoint platform (`proxmox`), guest/template/host architecture parity и legacy deprecation warnings (`type/role/resources/ansible.vars`). |
| `check_service_refs` | `base.validator.references` + `base.validator.service_runtime_refs` + `base.validator.runtime_target_os_binding` + `base.validator.service_dependency_refs` | Covered/Partial | Добавлены runtime/service-dependency validators и parity warning для `L5_application.external_services`; staged cutover зависит от release preflight на project fixtures. |
| `check_dns_refs` | `base.validator.references` + `base.validator.dns_refs` | Covered/Partial | Добавлен DNS thin-wrapper для record refs (`device_ref/lxc_ref/service_ref`) в DNS service rows. |
| `check_certificate_refs` | `base.validator.references` + `base.validator.certificate_refs` | Covered/Partial | Добавлен thin-wrapper для `service_ref` и `used_by[].service_ref` в certificate rows. |
| `check_backup_refs` | `base.validator.references` + `base.validator.backup_refs` | Covered/Partial | Добавлен thin-wrapper для backup `targets` (`device_ref/lxc_ref/data_asset_ref`) и `destination_ref`. |
| `check_security_policy_refs` | `base.validator.references` + `base.validator.security_policy_refs` | Covered/Partial | Добавлен thin-wrapper для `security_policy_ref` с проверкой на policy rows. |

### 3.5 Storage

| v4 check | v5 target | Coverage | Notes |
|---|---|---|---|
| `check_device_storage_taxonomy` | `base.validator.storage_device_taxonomy` | Covered/Partial | Добавлен validator L1 storage slot/media taxonomy (slot duplicates, deprecated inline media, mount/bus compatibility, removable/virtual contracts). |
| `check_l1_media_inventory` | `base.validator.storage_media_inventory` | Covered/Partial | Добавлен validator media registry + media attachment consistency (`device_ref/slot_ref/media_ref`, `present` exclusivity per slot/media, mount/bus compatibility). |
| `check_l3_storage_refs` | `base.validator.references` + `base.validator.storage_l3_refs` | Covered/Partial | Расширен L3 storage refs validator: `volume->pool`, `data_asset->volume`, `partition/media_attachment`, `vg/pv_refs`, `lv/vg_ref`, `filesystem(lv|partition)`, `mount_point/filesystem`, `storage_endpoint(lv|mount_point)` + `infer_from.*` consistency и data-asset backup policy linkage checks. |

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

## 5. Closure Notes

1. Draft deprecation matrix переведена в staged-cutover planning документ: `adr/plan/0078-v4-validator-deprecation-matrix.md`.
2. Parity gates зафиксированы в рабочем lane:
   - `task test:parity-v4-v5`
   - `task ci:topology-parity-v4-v5`
3. `cutover-readiness-report` (non-quick) включает обязательный gate `pytest_v4_v5_parity`.
4. Остаточные `Partial` строки в таблице являются контролируемыми legacy-совместимостями и не блокируют v5 default lane.
5. Конкретный список remaining `Partial` gaps закреплен в `adr/plan/0078-v4-validator-deprecation-matrix.md` (section 5).

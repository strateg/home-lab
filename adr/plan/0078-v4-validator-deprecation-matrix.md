# ADR0078 Wave D: v4 Validator Deprecation Matrix

**Date:** 2026-03-22  
**Status:** Draft (for cutover planning)  
**Related:** `adr/plan/0078-wave-d-v4-validator-mapping.md`

---

## 1. Purpose

Зафиксировать план отключения `v4/topology-tools/scripts/validators/checks/*` после достижения parity в v5 plugin pipeline.

---

## 2. Matrix

| v4 module | v4 check | v5 replacement plugins | Parity | Cutover action |
|---|---|---|---|---|
| foundation.py | `check_modular_include_contract` | `base.validator.foundation_include_contract` | Covered/Partial | Disable v4 check after fixture parity lock. |
| foundation.py | `check_file_placement` | `base.validator.foundation_layout` (+ future dedicated file_placement plugin) | Partial | Keep v4 as fallback until policy taxonomy parity is complete. |
| foundation.py | `check_device_taxonomy` | `base.validator.foundation_device_taxonomy`, `base.validator.references`, `base.validator.capability_contract` | Covered/Partial | Disable v4 check once storage-related edge fixtures are merged. |
| governance.py | `check_l0_contracts` | `base.validator.governance_contract` | Covered/Partial | Keep v4 fallback only for legacy class-taxonomy coupling of network_manager_device_ref; defaults refs existence parity is covered in v5 fixtures. |
| governance.py | `check_version` | `base.validator.governance_contract` | Covered/Partial | Disable v4 check after warning-semantics parity confirmation. |
| governance.py | `check_ip_overlaps` | `base.validator.network_ip_overlap` | Covered/Partial | Disable v4 check after parity review for non-network legacy payload paths. |
| network.py | `check_vlan_tags` | `base.validator.network_vlan_tags` | Covered/Partial | Disable v4 check after fixture parity lock. |
| network.py | `check_network_refs` | `base.validator.references`, `base.validator.network_core_refs` | Covered/Partial | Keep v4 fallback for advanced policy/profile scope; core bridge/trust-zone/manager refs parity and payload-shape parity are covered in v5 fixtures. |
| network.py | `check_bridge_refs` | `base.validator.network_core_refs` | Covered/Partial | Disable v4 check after fixture parity lock. |
| network.py | `check_data_links` | `object_network.validator_json.ethernet_cable_endpoints` | Partial | Keep v4 fallback for non-ethernet legacy scope. |
| network.py | `check_power_links` | `base.validator.power_source_refs` | Covered/Partial | Disable v4 check after edge-case fixtures. |
| network.py | `check_mtu_consistency` | `base.validator.network_mtu_consistency` | Covered/Partial | Disable v4 check after fixture parity lock. |
| network.py | `check_vlan_zone_consistency` | `base.validator.network_vlan_zone_consistency` | Covered/Partial | Disable v4 check after warning parity review. |
| network.py | `check_reserved_ranges` | `base.validator.network_reserved_ranges` | Covered/Partial | Keep v4 fallback only for non-VLAN legacy shapes not yet modeled in v5 fixtures. |
| network.py | `check_trust_zone_firewall_refs` | `base.validator.network_trust_zone_firewall_refs` | Covered/Partial | Disable v4 check after fixture parity lock. |
| network.py | `check_firewall_policy_addressability` | `base.validator.network_firewall_addressability` | Covered/Partial | Keep v4 fallback only for non-VLAN legacy shape review; warnings parity for core payload paths is locked in v5 fixtures. |
| network.py | `check_ip_allocation_host_os_refs` | `base.validator.network_ip_allocation_host_os_refs` | Covered/Partial | Disable v4 check after non-VLAN legacy shape review; parity for required-ref and deprecation warning semantics is covered in v5 fixtures. |
| network.py | `check_runtime_network_reachability` | `base.validator.network_runtime_reachability` | Covered/Partial | Disable v4 check after non-VLAN/network-profile legacy shape review; active-only + payload-path parity fixtures are covered. |
| network.py | `check_single_active_os_per_device` | `base.validator.single_active_os` | Covered/Partial | Disable v4 check after legacy inventory parity decision. |
| references.py | `check_host_os_refs` | `base.validator.references`, `base.validator.embedded_in`, `base.validator.runtime_target_os_binding`, `base.validator.host_os_refs` | Covered/Partial | Move to staged cutover after release preflight confirms parity on project fixtures (including non-extension host_os payload paths). |
| references.py | `check_vm_refs` | `base.validator.references`, `base.validator.vm_refs` | Covered/Partial | Move to staged cutover after release preflight confirms architecture/capability/storage/bridge parity on project fixtures. |
| references.py | `check_lxc_refs` | `base.validator.references`, `base.validator.lxc_refs` | Covered/Partial | Move to staged cutover after release preflight confirms architecture/capability/storage/deprecation parity on project fixtures. |
| references.py | `check_service_refs` | `base.validator.references`, `base.validator.service_runtime_refs`, `base.validator.service_dependency_refs`, `base.validator.runtime_target_os_binding` | Partial | Disable v4 check after remaining legacy service policy rules are moved. |
| references.py | `check_dns_refs` | `base.validator.references`, `base.validator.dns_refs` | Covered/Partial | Disable v4 check after DNS fixture parity lock. |
| references.py | `check_certificate_refs` | `base.validator.references`, `base.validator.certificate_refs` | Covered/Partial | Disable v4 check after certificate fixture parity lock. |
| references.py | `check_backup_refs` | `base.validator.references`, `base.validator.backup_refs` | Covered/Partial | Disable v4 check after backup fixture parity lock. |
| references.py | `check_security_policy_refs` | `base.validator.references`, `base.validator.security_policy_refs` | Covered/Partial | Disable v4 check after security policy fixture parity lock. |
| storage.py | `check_device_storage_taxonomy` | `base.validator.storage_device_taxonomy` | Covered/Partial | Disable v4 check after hardware edge fixture parity lock. |
| storage.py | `check_l1_media_inventory` | `base.validator.storage_media_inventory` | Covered/Partial | Disable v4 check after media-attachment edge fixture parity lock. |
| storage.py | `check_l3_storage_refs` | `base.validator.references`, `base.validator.storage_l3_refs` | Covered/Partial | Disable v4 check after infer_from warning semantics and legacy edge fixture lock. |

---

## 3. Cutover Gates

1. Для каждой строки с `Partial` должен быть зафиксирован parity fixture в `v5/tests/plugin_integration`.
2. Перед отключением v4 check: прогонить v5 target plugins и сравнить diagnostics baseline на регрессионной выборке.
3. После отключения набора v4 checks: обновить `taskfiles/validate.yml` и release preflight lane под v5-only validation path.
4. Для staged cutover references/storage/governance запускать parity lane: `task test:parity-v4-v5` (или `task ci:topology-parity-v4-v5`).
5. В cutover readiness report (`v5/topology-tools/cutover-readiness-report.py`, non-quick) parity gate `pytest_v4_v5_parity` должен быть green.
6. Перед staged отключением v4 checks актуализировать `v5/projects/home-lab/framework.lock.yaml` и добиться green для `verify_framework_lock`/`rehearse_rollback` в readiness report.

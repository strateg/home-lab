# ADR 0086 — Wave 2 ID Mapping and Rewire Notes

## Scope

This mapping covers Wave 2 consolidation delivered in W2-02..W2-07:

1. A-family refs validators consolidated into `DeclarativeReferenceValidator`.
2. Router-port validators consolidated into `RouterPortValidator`.
3. Manifest dependency rewires aligned to consolidated owners.

---

## 1) Reference Validators (A-family) — ID/Entry Mapping

| Existing Plugin ID | Previous entry | Current entry | Consolidated rule scope |
|---|---|---|---|
| `base.validator.dns_refs` | `validators/dns_refs_validator.py:DnsRefsValidator` | `validators/declarative_reference_validator.py:DeclarativeReferenceValidator` | `enabled_rules: [dns]` |
| `base.validator.certificate_refs` | `validators/certificate_refs_validator.py:CertificateRefsValidator` | `validators/declarative_reference_validator.py:DeclarativeReferenceValidator` | `enabled_rules: [certificate]` |
| `base.validator.backup_refs` | `validators/backup_refs_validator.py:BackupRefsValidator` | `validators/declarative_reference_validator.py:DeclarativeReferenceValidator` | `enabled_rules: [backup]` |
| `base.validator.service_dependency_refs` | `validators/service_dependency_refs_validator.py:ServiceDependencyRefsValidator` | `validators/declarative_reference_validator.py:DeclarativeReferenceValidator` | `enabled_rules: [service_dependency]` |
| `base.validator.network_core_refs` | `validators/network_core_refs_validator.py:NetworkCoreRefsValidator` | `validators/declarative_reference_validator.py:DeclarativeReferenceValidator` | `enabled_rules: [network_core]` |
| `base.validator.power_source_refs` | `validators/power_source_refs_validator.py:PowerSourceRefsValidator` | `validators/declarative_reference_validator.py:DeclarativeReferenceValidator` | `enabled_rules: [power_source]` |

### Missing-subscribe compatibility knobs

Per-plugin compatibility for missing `normalized_rows` is kept via manifest config:

- `missing_rows_code` (for legacy error code parity),
- `missing_rows_path` (for legacy path parity, including `pipeline:mode` for power source),
- `missing_rows_message_prefix` (for legacy prefix style in diagnostic message text).

---

## 2) Router Port Consolidation — ID/Owner Mapping

| Existing Plugin ID | Previous role | Current ownership |
|---|---|---|
| `class_router.validator_json.router_data_channel_interface` | Validated `class.router.data_channel_interface_contract` shape (`E7301`) | Delegated to `base.validator.router_ports` via `depends_on` |
| `object_mikrotik.validator_json.router_ports` | Validated MikroTik ethernet list shape (`E7302`) | Delegated to `base.validator.router_ports` via `depends_on` |
| `object_glinet.validator_json.router_ports` | Validated GL.iNet ethernet list shape (`E7303`) | Delegated to `base.validator.router_ports` via `depends_on` |
| `base.validator.router_ports` | n/a (new in Wave 2) | Consolidated owner plugin (`validators/router_port_validator.py:RouterPortValidator`) |

Notes:

- Existing class/object IDs are preserved for compatibility in module manifests.
- Consolidated base owner is introduced in framework manifest and executes at validate/run.

---

## 3) Manifest Rewires Applied

### Framework manifest

Updated file:

- `topology-tools/plugins/plugins.yaml`

Changes:

1. Added `base.validator.router_ports` with entry:
   - `validators/router_port_validator.py:RouterPortValidator`
2. Rewired A-family refs plugin entries to:
   - `validators/declarative_reference_validator.py:DeclarativeReferenceValidator`
3. Added scoped config per A-family plugin:
   - `enabled_rules`,
   - `missing_rows_code`,
   - optional `missing_rows_path`,
   - `missing_rows_message_prefix`.

### Module manifests

Updated files:

- `topology/class-modules/router/plugins.yaml`
- `topology/object-modules/mikrotik/plugins.yaml`
- `topology/object-modules/glinet/plugins.yaml`

Changes:

- `depends_on` for module-level router validators rewired:
  - from `base.validator.references`
  - to `base.validator.router_ports`.

---

## 4) Test Coverage Anchors for Mapping

Key tests validating these rewires and parity:

- `tests/plugin_integration/test_declarative_reference_validator.py`
- `tests/plugin_integration/test_declarative_reference_validator_parity.py`
- `tests/plugin_integration/test_dns_refs_validator.py`
- `tests/plugin_integration/test_certificate_refs_validator.py`
- `tests/plugin_integration/test_backup_refs_validator.py`
- `tests/plugin_integration/test_service_dependency_refs_validator.py`
- `tests/plugin_integration/test_network_core_refs_validator.py`
- `tests/plugin_integration/test_l1_power_source_refs.py`
- `tests/plugin_integration/test_tuc0001_router_data_link.py`
- `tests/plugin_integration/test_module_manifest_discovery.py`

---

## 5) Deferred Cleanup (Wave 3 candidate)

The following files remain in repository as legacy compatibility artifacts and can be evaluated for removal after wider parity/cutover validation:

- `topology-tools/plugins/validators/dns_refs_validator.py`
- `topology-tools/plugins/validators/certificate_refs_validator.py`
- `topology-tools/plugins/validators/backup_refs_validator.py`
- `topology-tools/plugins/validators/service_dependency_refs_validator.py`
- `topology-tools/plugins/validators/network_core_refs_validator.py`
- `topology-tools/plugins/validators/power_source_refs_validator.py`
- `topology/class-modules/router/plugins/validators/router_data_channel_interface_validator.py`
- `topology/object-modules/mikrotik/plugins/validators/mikrotik_router_ports_validator.py`
- `topology/object-modules/glinet/plugins/validators/glinet_router_ports_validator.py`

They are no longer canonical owners in Wave 2 wiring but are retained for rollback safety and incremental cutover.

# ADR 0086 — Wave 3 Standalone Inventory

Inventory snapshot date: 2026-04-02

Scope scanned:
- `topology/class-modules/*/plugins.yaml`
- `topology/object-modules/*/plugins.yaml`

Selection rule:
- plugin entries with `entry` starting from module-local `plugins/...` path.

## Inventory

| Plugin ID | Kind | Source manifest | Target family path | Relocation action | Dependency notes |
|---|---|---|---|---|---|
| `class_router.validator_json.router_data_channel_interface` | `validator_json` | `topology/class-modules/router/plugins.yaml` | `topology-tools/plugins/validators/router_port_validator.py` | Remove standalone wrapper; keep validation ownership in `base.validator.router_ports` | Module entry already depends on `base.validator.router_ports` (Wave 2) |
| `object_glinet.validator_json.router_ports` | `validator_json` | `topology/object-modules/glinet/plugins.yaml` | `topology-tools/plugins/validators/router_port_validator.py` | Remove standalone wrapper; keep validation ownership in `base.validator.router_ports` | Module entry already depends on `base.validator.router_ports` (Wave 2) |
| `object_mikrotik.validator_json.router_ports` | `validator_json` | `topology/object-modules/mikrotik/plugins.yaml` | `topology-tools/plugins/validators/router_port_validator.py` | Remove standalone wrapper; keep validation ownership in `base.validator.router_ports` | Module entry already depends on `base.validator.router_ports` (Wave 2) |
| `object_network.validator_json.ethernet_cable_endpoints` | `validator_json` | `topology/object-modules/network/plugins.yaml` | `topology/object-modules/network/plugins/validators/ethernet_cable_endpoint_validator.py` | Keep module-owned for now (object-specific extension point, no duplicate in framework family) | Consumes published data from `base.validator.ethernet_port_inventory` |
| `object.mikrotik.generator.terraform` | `generator` | `topology/object-modules/mikrotik/plugins.yaml` | `topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py` | Keep module-owned (ADR0078 ownership contract) | Object-specific templates/projections in module domain |
| `object.mikrotik.generator.bootstrap` | `generator` | `topology/object-modules/mikrotik/plugins.yaml` | `topology/object-modules/mikrotik/plugins/generators/bootstrap_mikrotik_generator.py` | Keep module-owned (ADR0078 ownership contract) | Object-specific bootstrap templates |
| `object.proxmox.generator.terraform` | `generator` | `topology/object-modules/proxmox/plugins.yaml` | `topology/object-modules/proxmox/plugins/generators/terraform_proxmox_generator.py` | Keep module-owned (ADR0078 ownership contract) | Object-specific templates/projections in module domain |
| `object.proxmox.generator.bootstrap` | `generator` | `topology/object-modules/proxmox/plugins.yaml` | `topology/object-modules/proxmox/plugins/generators/bootstrap_proxmox_generator.py` | Keep module-owned (ADR0078 ownership contract) | Object-specific bootstrap templates |
| `object.orangepi.generator.bootstrap` | `generator` | `topology/object-modules/orangepi/plugins.yaml` | `topology/object-modules/orangepi/plugins/generators/bootstrap_orangepi_generator.py` | Keep module-owned (ADR0078 ownership contract) | Object-specific bootstrap templates |

## Wave 3 Block A Candidate Set (W3-02/W3-03)

- Remove redundant module-level router wrapper validators:
  - `class_router.validator_json.router_data_channel_interface`
  - `object_glinet.validator_json.router_ports`
  - `object_mikrotik.validator_json.router_ports`
- Keep object-generator ownership and network endpoint validator placement unchanged in Block A.

## Execution Note (2026-04-02)

- Implemented Block A removals for router wrapper validators.
- Deleted now-empty manifests:
  - `topology/class-modules/router/plugins.yaml`
  - `topology/object-modules/glinet/plugins.yaml`
- Normalized remaining network validator ID:
  - `object_network.validator_json.ethernet_cable_endpoints`
  - -> `object.network.validator_json.ethernet_cable_endpoints`

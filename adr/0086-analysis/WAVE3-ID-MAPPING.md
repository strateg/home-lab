# ADR 0086 — Wave 3 ID Mapping

## Scope

Wave 3 active-manifest ID normalization for remaining class/object plugin IDs.

## Applied Mapping

| Previous ID | New ID | Manifest | Rationale |
|---|---|---|---|
| `object_network.validator_json.ethernet_cable_endpoints` | `object.network.validator_json.ethernet_cable_endpoints` | `topology/object-modules/network/plugins.yaml` | Normalize object plugin namespace to dot-style prefix (`object.<module>...`) used by active object generator IDs. |

## Notes

- Router wrapper validator IDs were removed in Wave 3 Block A together with their standalone manifest entries:
  - `class_router.validator_json.router_data_channel_interface`
  - `object_glinet.validator_json.router_ports`
  - `object_mikrotik.validator_json.router_ports`
- No dependency rewires were required for the renamed network validator ID because no active `depends_on`/`consumes.from_plugin` references targeted that ID.

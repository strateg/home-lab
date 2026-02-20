# L2 Network Profiles

`network_profiles` keep repeated network intent in one place and make network files short.

## Profile Fields

Each profile defines the default analysis fields:
- `network_plane`: `underlay-uplink` | `virtual` | `overlay`
- `segmentation_type`: `uplink` | `bridge` | `vlan` | `overlay-vpn` | `mesh-overlay`
- `transport`: list like `ethernet`, `wifi`, `lte`, `internet-overlay`
- `volatility`: `low` | `medium` | `high`

## L1-L2 Taxonomy Contract

Use these rules to keep L1 foundation and L2 network intent consistent.

- L1 manager device:
  - `managed_by_ref` should point to L1 device with `class: network`.
- L2 underlay (`network_plane: underlay-uplink`):
  - should use `trust_zone_ref: untrusted`
  - should keep `bridge_ref: null` and `vlan: null`
  - should set `interface_ref` on manager device
- L2 virtual VLAN (`segmentation_type: vlan`):
  - requires non-null `vlan`
- L2 virtual bridge (`segmentation_type: bridge`):
  - requires `vlan: null`
- L2 overlay (`network_plane: overlay`):
  - should set `vpn_type`
  - should keep `bridge_ref: null` and `vlan: null`

Validation for these rules is implemented in `scripts/validate-topology.py`.

## Usage Rules

- Every L2 network should prefer `profile_ref`.
- Keep per-network overrides only when behavior really differs from profile.
- If a network uses `profile_ref`, avoid repeating identical profile fields in network file.
- Validator warns on redundant overrides to keep diffs small and readable.

## Edit Workflow

1. Choose existing profile from `default.yaml`.
2. Set `profile_ref` in network module.
3. Add override only if this network is an exception.
4. Run:
   - `python scripts/validate-topology.py`
   - `python scripts/generate-docs.py`

## Add New Profile (when needed)

Create a new profile only if at least two networks can share it.

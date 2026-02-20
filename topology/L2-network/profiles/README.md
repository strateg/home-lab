# L2 Network Profiles

`network_profiles` keep repeated network intent in one place and make network files short.

## Profile Fields

Each profile defines the default analysis fields:
- `network_plane`: `underlay-uplink` | `virtual` | `overlay`
- `segmentation_type`: `uplink` | `bridge` | `vlan` | `overlay-vpn` | `mesh-overlay`
- `transport`: list like `ethernet`, `wifi`, `lte`, `internet-overlay`
- `volatility`: `low` | `medium` | `high`

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

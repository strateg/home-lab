# L7 Power Resilience Model

This directory stores operational power behavior, not physical inventory.

## Scope

- Outage propagation and shutdown orchestration.
- UPS/PDU runtime policies and action thresholds.
- Policy links to physical power devices from `L1_foundation.devices`.

## Ownership Boundaries

- `L1_foundation`: physical devices and power wiring (`devices[*].power`, `upstream_power_ref`).
- `L7_operations.power_resilience`: operational policies (`policies[*]`) and outage actions.

## Minimal Policy Pattern

```yaml
id: policy-ups-main
name: Main UPS Runtime Policy
type: ups-protection
device_ref: ups-main
protected_devices:
- device_ref: pdu-rack-home
```

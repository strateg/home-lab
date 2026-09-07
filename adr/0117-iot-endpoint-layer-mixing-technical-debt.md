# ADR 0117: IoT Endpoint Layer Separation

- Status: Implemented
- Date: 2026-09-06
- Related: ADR 0116 (Peripheral Device Model), ADR 0062 (C-O-I Architecture)
- Analysis: SPC Protocol (STEP 1-7)

## Context

### Problem Statement

During SPC analysis of ADR 0116's impact on the topology, the same L1/L2 property mixing issue was identified in `class.device.iot_endpoint`. This class is defined at L1 (physical foundation) but contains properties that belong at L2 (network) and L3 (IP addressing).

### Diagnostic Summary

| Property | Current Layer | Correct Layer | Issue |
|----------|--------------|---------------|-------|
| `mac_address` | L1 | secrets_ref | Sensitive data exposed |
| `ip_address` | L1 | L2/L3 interface | L3 property at L1 |
| `static_ip` | L1 | L2/L3 interface | L3 property at L1 |
| `vlan_ref` | L1 | L2 interface | L2 reference at L1 |
| `connection_type` | L1 | L2 interface | L2 property at L1 |

### Affected Files

**Class (1):**
- `topology/class-modules/L1-foundation/device/class.device.iot_endpoint.yaml`

**Objects (3):**
- `topology/object-modules/device/obj.device.smart_tv.yaml`
- `topology/object-modules/device/obj.device.smartphone.yaml`
- `topology/object-modules/device/obj.device.e_reader.yaml`

**Instances (3):**
- `projects/home-lab/topology/instances/devices/inst.device.tv-sony-bravia.yaml`
- `projects/home-lab/topology/instances/devices/inst.device.boox-go-103-lumi.yaml`
- `projects/home-lab/topology/instances/devices/inst.device.jolla-phone-2026.yaml`

### Current Mitigation

All instances already use `secrets_ref` for MAC addresses (compliant with ADR 0072/0073 secrets pattern). No plain-text MAC addresses are exposed in topology files.

## Decision

### D1: Document as Technical Debt

This issue is documented as known technical debt rather than immediate refactoring because:

1. **Lower Priority**: IoT endpoints are passive network consumers, not infrastructure-critical like peripherals
2. **Already Mitigated**: Sensitive data (MAC) already uses secrets_ref pattern
3. **Functional**: Current model works correctly for VLAN assignment and DHCP configuration
4. **Scope**: Full refactoring would require creating L2 network interface abstraction for IoT devices

### D2: Future Refactoring Pattern

When addressed, follow ADR 0116 pattern:

```yaml
# L1: Physical device only
class.device.iot_endpoint:
  properties:
    required:
      - device_name
      - device_type
    optional:
      - manufacturer
      - model
      - secrets_ref      # MAC, device IDs
      - provides_ref     # Link to L2 network interface
      - notes

# L2: Network interface (new class)
class.network.iot_interface:
  properties:
    required:
      - device_ref       # Back-reference to L1 device
      - connection_type  # wifi, ethernet
    optional:
      - vlan_ref
      - ip_assignment    # dhcp, static
      - static_ip
```

### D3: Validation Enhancement

Add compiler warning for L2/L3 properties at L1 layer to catch similar issues:

```yaml
# Future: layer-contract.yaml enhancement
layer_property_warnings:
  L1:
    discouraged_properties:
      - mac_address      # Should use secrets_ref
      - ip_address       # Belongs at L2/L3
      - vlan_ref         # Belongs at L2
```

## Consequences

### Positive

- Clean layer separation: L1 physical, L2 network
- Consistent with ADR 0116 peripheral model
- All instances use secrets_ref for MAC addresses
- provides_ref pattern enables cross-layer tracing

### Negative

- Breaking change to class.device.iot_endpoint (version 2.0.0)
- Existing instances required migration

### Neutral

- D3 validation enhancement deferred to future work

## Implementation

### Completed

- [x] Create `class.network.iot_interface` at L2
- [x] Refactor `class.device.iot_endpoint` to L1-only properties (v2.0.0)
- [x] Update object modules (smart_tv, smartphone, e_reader)
- [x] Create L2 interface instances for all IoT devices
- [x] Migrate device instances to use provides_ref pattern
- [x] Update layer-contract.yaml with new class

### Files Created

**Class (1):**
- `topology/class-modules/L2-network/network/class.network.iot_interface.yaml`

**Instances (3):**
- `projects/home-lab/topology/instances/network/inst.iot_interface.tv-sony-bravia.yaml`
- `projects/home-lab/topology/instances/network/inst.iot_interface.boox-go-103-lumi.yaml`
- `projects/home-lab/topology/instances/network/inst.iot_interface.jolla-phone-2026.yaml`

### Files Modified

- `topology/class-modules/L1-foundation/device/class.device.iot_endpoint.yaml` (v2.0.0)
- `topology/object-modules/device/obj.device.smart_tv.yaml`
- `topology/object-modules/device/obj.device.smartphone.yaml`
- `topology/object-modules/device/obj.device.e_reader.yaml`
- `projects/home-lab/topology/instances/devices/inst.device.tv-sony-bravia.yaml` (v2.0.0)
- `projects/home-lab/topology/instances/devices/inst.device.boox-go-103-lumi.yaml` (v2.0.0)
- `projects/home-lab/topology/instances/devices/inst.device.jolla-phone-2026.yaml` (v2.0.0)
- `topology/layer-contract.yaml`

### Deferred

- [ ] Add compiler warning for L2/L3 properties at L1 layer

## References

- ADR 0116: Peripheral Device Model and Connection-Type Hierarchy
- ADR 0062: Modular Topology Architecture (C-O-I)
- ADR 0071: Layer Contract
- layer-contract.yaml: `class.device.iot_endpoint` at L1

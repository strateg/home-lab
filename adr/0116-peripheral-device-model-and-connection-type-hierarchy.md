# ADR 0116: Peripheral Device Model and Connection-Type Hierarchy

- Status: Implemented
- Date: 2026-09-06
- Extends: ADR 0062 (C-O-I Architecture), ADR 0088 (Semantic Keyword Registry)
- Related: ADR 0071 (Layer Contract), ADR 0107 (Host Placement Defaults)
- Analysis: SPC Protocol (STEP 1-7)

## Context

### Problem Statement

The peripheral device model had several architectural issues:

1. **Layer Mixing**: Existing classes (`usb_ethernet_adapter`, `usb_hub_ethernet`, `usb_wifi_adapter`) mixed L1 (physical) and L2/L3 (logical) properties
2. **No Base Class**: Three independent classes with no common ancestor, causing property duplication
3. **No Connection Type Abstraction**: USB-specific, no support for Bluetooth, Thunderbolt, NFC, etc.
4. **Inconsistent Naming**: Instance naming patterns varied (`usb_hub_eth` vs `usb_wifi`)
5. **Missing Registration**: `usb_wifi_adapter` not registered in layer-contract.yaml
6. **Sensitive Data Exposure**: Device IDs (source_id) in public topology files

### Diagnostic Summary (SPC STEP 3)

| Issue | Count | Example |
|-------|-------|---------|
| Mixed L1/L2 properties | 3 classes | `mac_address` in peripheral class |
| Property duplication | ~15 fields | `usb_version`, `form_factor` repeated |
| Schema inconsistencies | 4 | `chipset` required vs optional |
| Missing classes | 1 | Bluetooth, NFC, etc. |
| Naming violations | 2 | Instance naming patterns |

### Host vs Peripheral Distinction

The model distinguishes two roles in the peripheral attachment relationship:

| Role | Definition | Examples |
| ---- | ---------- | -------- |
| **Host** | Device to which peripherals are connected. Has USB ports, Bluetooth adapter, or other connection interfaces. Consumes functionality provided by peripherals. | `srv-orangepi5`, `rtr-mikrotik-chateau`, laptop, desktop |
| **Peripheral** | Device connected to a host to provide specific logical functionality. Cannot operate independently without a host. | USB WiFi adapter, USB hub, Bluetooth mouse, USB flash drive |

```
┌─────────────────────────────────────────────────────────────────┐
│ HOST (L1 Device)                                                │
│   - class.compute.edge_node, class.router, class.compute.*     │
│   - Has connection interfaces (USB ports, BT, TB)               │
│   - Declares attached peripherals via `peripherals[]` array     │
│                                                                 │
│   peripherals:                                                  │
│     - ref: inst.peripheral.usb.hub.bluecloud-001               │
│       role: primary_network                                     │
│     - ref: inst.peripheral.usb.wifi.asus-001                   │
│       role: wifi                                                │
└─────────────────────────────────────────────────────────────────┘
          │
          │ attached_to (implicit via host.peripherals[])
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ PERIPHERAL (L1 Device)                                          │
│   - class.peripheral.*                                          │
│   - Physical device with connection-specific properties         │
│   - Provides logical functionality to host                      │
└─────────────────────────────────────────────────────────────────┘
          │
          │ provides_ref
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ LOGICAL ENTITY (L2/L3/L5)                                       │
│   - Network interface, storage media, audio endpoint, etc.      │
│   - Consumed by host OS/applications                            │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Model Clarification

Peripherals follow a two-layer model:

```
┌─────────────────────────────────────────────────┐
│ L1 (Physical): Peripheral Device                │
│   - vendor, model, connection properties        │
│   - form_factor, dimensions, weight             │
│   - secrets_ref for IDs and MACs                │
└─────────────────────────────────────────────────┘
                      │
                      │ provides_ref
                      ▼
┌─────────────────────────────────────────────────┐
│ L2/L3/L5 (Logical): Provided Functionality      │
│   - Network interface (L2)                      │
│   - Storage media (L3)                          │
│   - Audio/Service endpoint (L5)                 │
└─────────────────────────────────────────────────┘
```

## Decision

### D1: Abstract Base Class `class.peripheral`

Create abstract base class for all peripherals at L1:

```yaml
@class: class.peripheral
@layer: L1
@abstract: true

properties:
  optional:
    - vendor
    - model
    - secrets_ref      # For device_id, MAC, pairing keys
    - provides_ref     # Link to logical entity
    - form_factor
    - notes
```

### D2: Connection-Type Subclasses

Create intermediate classes for each connection type:

| Class | Connection | Properties |
|-------|------------|------------|
| `class.peripheral.usb` | USB | `usb_version`, `connector_type`, `power_delivery` |
| `class.peripheral.bluetooth` | Bluetooth | `bt_version`, `bt_profiles`, `battery_type` |
| `class.peripheral.thunderbolt` | Thunderbolt | `tb_version`, `daisy_chain_support` |
| `class.peripheral.nfc` | NFC | `nfc_type`, `supported_standards` |
| `class.peripheral.zigbee` | Zigbee | `zigbee_role`, `zigbee_version` |
| `class.peripheral.zwave` | Z-Wave | `zwave_role`, `zwave_frequency` |

### D3: Function-Specific Subclasses

Create function classes under connection types:

```
class.peripheral.usb
├── class.peripheral.usb.network_adapter   # WiFi, Ethernet, LTE
├── class.peripheral.usb.hub               # Hubs, Docks
└── class.peripheral.usb.storage_device    # Flash, SSD, Card readers

class.peripheral.bluetooth
└── class.peripheral.bluetooth.hid         # Mouse, Keyboard, Gamepad
```

### D4: Unified Naming Convention

| Level | Pattern | Example |
|-------|---------|---------|
| Class | `class.peripheral.<connection>[.<function>]` | `class.peripheral.usb.network_adapter` |
| Object | `obj.peripheral.<connection>.<vendor>.<model>` | `obj.peripheral.usb.asus.ax55_nano` |
| Instance | `inst.peripheral.<connection>.<function>.<vendor>-<seq>` | `inst.peripheral.usb.wifi.asus-001` |

### D5: Secrets Structure

All sensitive data in SOPS-encrypted secrets:

```yaml
# secrets/peripherals/<instance-id>.yaml
device_id: "SERIAL-NUMBER"      # Was source_id
mac_address: "AA:BB:CC:DD:EE:FF"
linux_interface: "enxAABBCCDDEEFF"
pairing_mac: "..."              # For Bluetooth
```

### D6: Physical Link Integration

Add `via_peripheral` property to physical links:

```yaml
endpoint_b:
  device_ref: srv-orangepi5
  port: usb_hub_eth
  via_peripheral: inst.peripheral.usb.hub.bluecloud-001
```

### D7: Layer Contract Registration

All peripheral classes registered in `layer-contract.yaml`:

```yaml
class.peripheral:
  allowed_layers: [L1]
class.peripheral.usb:
  allowed_layers: [L1]
class.peripheral.usb.network_adapter:
  allowed_layers: [L1]
# ... etc
```

## Consequences

### Positive

- **Clean Layer Separation**: Physical properties at L1, logical at higher layers
- **Extensible Hierarchy**: Easy to add new connection types and functions
- **Consistent Naming**: Predictable file and reference patterns
- **Security**: All identifiers in encrypted secrets
- **Market Coverage**: Class structure covers modern peripheral landscape

### Negative

- **Migration Required**: Existing instances need renaming
- **Secrets Migration**: Manual SOPS re-encryption needed
- **More Files**: 11 class files vs previous 3

### Neutral

- Stub classes (Thunderbolt, NFC, Zigbee, Z-Wave) await device additions

## Implementation

### Files Created

**Class Modules (11):**
- `class.peripheral.yaml` (base)
- `class.peripheral.usb.yaml`
- `class.peripheral.usb.network_adapter.yaml`
- `class.peripheral.usb.hub.yaml`
- `class.peripheral.usb.storage_device.yaml`
- `class.peripheral.bluetooth.yaml`
- `class.peripheral.bluetooth.hid.yaml`
- `class.peripheral.thunderbolt.yaml` (stub)
- `class.peripheral.nfc.yaml` (stub)
- `class.peripheral.zigbee.yaml` (stub)
- `class.peripheral.zwave.yaml` (stub)

**Object Modules (3):**
- `obj.peripheral.usb.asus.ax55_nano.yaml`
- `obj.peripheral.usb.bluecloud.hub_gbe.yaml`
- `obj.peripheral.bt.logitech.m720.yaml`

**Instance Files (3):**
- `inst.peripheral.usb.wifi.asus-001.yaml`
- `inst.peripheral.usb.hub.bluecloud-001.yaml`
- `inst.peripheral.bt.hid.logitech-m720-001.yaml`

### Files Removed

- `class.peripheral.usb_ethernet_adapter.yaml`
- `class.peripheral.usb_hub_ethernet.yaml`
- `class.peripheral.usb_wifi_adapter.yaml`
- `obj.peripheral.asus.usb_ax55_nano.yaml`
- `obj.peripheral.bluecloud.usbc_hub_gbe.yaml`
- `inst.peripheral.usb_hub_eth.bluecloud-001.yaml`
- `inst.peripheral.usb_wifi.asus-ax55-nano-001.yaml`

### Files Modified

- `layer-contract.yaml` — new class registrations
- `srv-orangepi5.yaml` — updated peripheral refs
- `inst.ethernet_cable.chateau_to_orangepi5.yaml` — added `via_peripheral`
- `inst.chan.eth.chateau_to_orangepi5.yaml` — added `via_peripheral`

### Migration Guide

See `projects/home-lab/secrets/peripherals/MIGRATION.md` for secrets migration steps.

## Validation

```bash
# Compile topology
.venv/bin/python topology-tools/compile-topology.py

# Validate
V5_SECRETS_MODE=passthrough .venv/bin/python scripts/orchestration/lane.py validate-v5

# Run tests
python -m pytest tests -q
```

## References

- SPC Protocol Analysis: STEP 1-7 completed
- Layer Contract: `topology/layer-contract.yaml`
- Secrets Pattern: ADR 0072, ADR 0073

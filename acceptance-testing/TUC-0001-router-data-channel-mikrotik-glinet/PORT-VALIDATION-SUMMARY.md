# Port Validation Implementation Summary

**Date:** 2026-03-11
**Feature:** Port existence validation for cable endpoints
**Status:** Implemented and documented

---

## What Was Implemented

Two-level port validation system:

### Level 1: Endpoint Validator Plugin
**File:** `v5/topology/object-modules/network/plugins/ethernet_cable_endpoint_validator.py`

Validates at **compile/validate time**:
- Device instance `device_ref` resolves to existing instance
- Device instance has valid `object_ref` pointing to router object
- Port name exists in device object's port definitions
- Provides helpful error messages with list of available ports

**Error Code:** `E7305` for port not found

**Context Provided:**
```python
{
  "vendor": "mikrotik",
  "requested_port": "ether99",
  "available_ports": ["ether1", "ether2", "ether3", "ether4", "ether5", "lte1", "usb1", "wlan1", "wlan2"]
}
```

### Level 2: Quality Gate Script
**File:** `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/quality-gate.py`

Validates **before compile** (local checks):
- Loads router object definitions from `object-modules/`
- Extracts all available ports from object YAML
- Checks each cable endpoint port against device object

**Advantages:**
- Quick feedback (no full compile needed)
- Clear error messages with available ports list
- Can run in CI pre-flight stage

---

## How It Works

### For MikroTik Chateau LTE7 AX

Object defines these ports in `hardware_specs.interfaces.ethernet`:
```yaml
interfaces:
  ethernet:
    - name: ether1    # 2.5 GbE WAN
    - name: ether2    # 1 GbE LAN
    - name: ether3    # 1 GbE LAN
    - name: ether4    # 1 GbE LAN
    - name: ether5    # 1 GbE LAN
```

Valid cable endpoints:
- ✅ `device_ref: rtr-mikrotik-chateau` + `port: ether1` (exists)
- ✅ `device_ref: rtr-mikrotik-chateau` + `port: ether2` (exists)
- ❌ `device_ref: rtr-mikrotik-chateau` + `port: ether99` (does not exist) → E7305

### For GL.iNet Slate AX1800

Object defines these ports in `hardware_specs.interfaces.ethernet`:
```yaml
interfaces:
  ethernet:
    - name: wan       # 1 GbE WAN (blue)
    - name: lan1      # 1 GbE LAN (yellow)
    - name: lan2      # 1 GbE LAN (yellow)
```

Valid cable endpoints:
- ✅ `device_ref: rtr-slate` + `port: wan` (exists)
- ✅ `device_ref: rtr-slate` + `port: lan1` (exists)
- ❌ `device_ref: rtr-slate` + `port: lan99` (does not exist) → E7305

---

## Integration Points

### 1. Device Object Definition
Each router object declares its ports in standardized location:
```yaml
hardware_specs:
  interfaces:
    ethernet:      # List of ethernet interfaces
      - name: ether1
        role: wan
        speed_mbps: 2500
    wireless:      # List of wireless interfaces
      - name: wlan1
        band: 5ghz
    cellular:      # List of cellular interfaces
      - name: lte1
        category: 7
    usb:           # List of USB ports
      - name: usb1
```

### 2. Cable Instance
References ports by name (no validation needed — validator checks):
```yaml
endpoint_a:
  device_ref: rtr-mikrotik-chateau
  port: ether2        # Must exist in object
endpoint_b:
  device_ref: rtr-slate
  port: lan1          # Must exist in object
```

### 3. Validation Pipeline

```
Cable Instance YAML
    ↓
Quality Gate (pre-flight)
    └→ Loads router objects
    └→ Extracts ports
    └→ Validates endpoint ports exist
    ↓ (if OK)
Compile
    ↓
Endpoint Validator Plugin (compile-time)
    └→ Loads device instances
    └→ Loads device objects
    └→ Validates ports exist
    └→ Emits E7305 if not found
    ↓
Output: effective model + diagnostics
```

---

## Test Scenarios

### TUC1-T12: Port Validation (MikroTik)
- Cable endpoint: `rtr-mikrotik-chateau:ether2`
- Expected: ✅ Valid (port exists on object)
- Validation path: Device found → Object found → Port found in `ether2` list

### TUC1-T13: Port Validation (GL.iNet)
- Cable endpoint: `rtr-slate:lan1`
- Expected: ✅ Valid (port exists on object)
- Validation path: Device found → Object found → Port found in `lan1` list

### TUC1-T3/T4: Invalid Port Names
- Cable endpoint: `rtr-mikrotik-chateau:ether99` or `rtr-slate:lan99`
- Expected: ❌ Error E7305
- Error message includes available ports list for user guidance

---

## How to Use

### In TUC-0001 Context

1. **Pre-compile check:**
   ```bash
   cd acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet
   python quality-gate.py
   ```

2. **During compile:**
   - Endpoint validator plugin runs automatically
   - E7305 errors are emitted if ports don't exist
   - Compile continues (validator is non-critical stage)

3. **Troubleshooting:**
   ```bash
   # See available ports on device
   grep -A 30 "interfaces:" v5/topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml

   # Fix cable endpoint with correct port name
   # e.g., change "ether99" to "ether2"
   ```

### For New Router Types

To add validation for new router vendors:

1. **Define ports in router object:**
   ```yaml
   hardware_specs:
     interfaces:
       ethernet:
         - name: ge-0/0/0    # Juniper naming
         - name: ge-0/0/1
   ```

2. **Use in cable endpoint:**
   ```yaml
   endpoint_a:
     device_ref: rtr-juniper-srx
     port: ge-0/0/0          # Validator checks this exists
   ```

3. **Validator works automatically** — no additional code needed

---

## Limitations & Edge Cases

### Not Covered by This Validation
- ❌ Port role compatibility (e.g., WAN port used for data link)
- ❌ Port speed mismatch (e.g., cable rated 10G but port is 1G)
- ❌ Port media type (e.g., copper vs fiber)
- ❌ L1 signal integrity

These could be added as future validations if needed.

### What IS Covered
- ✅ Port exists on device object
- ✅ Device instance exists
- ✅ Device object exists
- ✅ Clear error messages with context

---

## Conclusion

**Port validation is now two-stage:**
1. **Quality gate** catches errors before compile (fast feedback)
2. **Endpoint validator** enforces at compile time (safety net)

This ensures cable endpoints always reference valid ports on their target devices.

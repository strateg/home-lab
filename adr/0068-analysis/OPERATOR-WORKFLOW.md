# ADR 0068: Operator Workflow for Instance Placeholders

**ADR:** `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md`
**Date:** 2026-03-15
**Audience:** Operators deploying real infrastructure

---

## Overview

ADR 0068 introduces typed placeholders in object templates that must be resolved by instance values. This document describes the operator workflow for:

1. Understanding placeholder syntax
2. Resolving required values (hardware identities, IPs, etc.)
3. Configuring enforcement modes
4. Troubleshooting validation errors

---

## Placeholder Syntax

Object templates use inline markers for fields that vary per instance:

```yaml
# Object template (obj.mikrotik.chateau_lte7_ax.yaml)
defaults:
  hardware_identity:
    serial_number: @required:string
    mac_addresses:
      ether1: @required:mac
      ether2: @optional:mac
  management:
    ipv4: @required:ipv4
```

### Marker Types

| Marker | Meaning |
|--------|---------|
| `@required:<format>` | Instance MUST provide this value |
| `@optional:<format>` | Instance MAY provide this value |

### Supported Formats

| Format | Description | Example |
|--------|-------------|---------|
| `string` | Any UTF-8 string | `GL-AXT-001122` |
| `int` | Signed integer | `42` |
| `number` | Integer or float | `3.14` |
| `bool` | Boolean | `true` / `false` |
| `mac` | MAC address (colon-separated) | `AA:BB:CC:DD:EE:FF` |
| `ipv4` | IPv4 address | `192.168.1.1` |
| `ipv6` | IPv6 address | `fe80::1` |
| `cidr` | Network in CIDR notation | `10.0.0.0/24` |
| `hostname` | DNS hostname | `router.local` |
| `uri` | Absolute URI | `https://example.com` |
| `iso8601` | ISO-8601 timestamp | `2026-03-15T10:30:00Z` |

Format registry: `v5/topology-tools/data/instance-field-formats.yaml`

---

## Resolving Placeholders

### Step 1: Identify Required Fields

Run compiler to see unresolved placeholders:

```bash
.venv/bin/python3 v5/topology-tools/compile-topology.py --verbose
```

Look for `E6806` warnings/errors:

```
W6806: Unresolved placeholder '@required:mac' at path 'defaults.hardware_identity.mac_addresses.ether1'
```

### Step 2: Gather Real Values

For hardware identities, collect from actual devices:

**MikroTik (SSH):**
```bash
ssh admin@192.168.88.1 '/interface print detail' | grep mac-address
ssh admin@192.168.88.1 '/system routerboard print' | grep serial
```

**Linux (SSH):**
```bash
ssh root@10.0.10.1 'cat /sys/class/net/*/address'
ssh root@10.0.10.1 'dmidecode -s system-serial-number'
```

**Proxmox (SSH):**
```bash
ssh root@10.0.99.1 'dmidecode -s system-serial-number'
ssh root@10.0.99.1 'ip link show | grep ether'
```

### Step 3: Update Instance File

Edit the instance file and add values under `instance_overrides` or directly in fields:

```yaml
# v5/topology/instances/l1_devices/rtr-mikrotik-chateau.yaml
schema_version: 1
instance: rtr-mikrotik-chateau
object_ref: obj.mikrotik.chateau_lte7_ax
# ...

# Option A: Direct fields (if schema allows)
hardware_identity:
  serial_number: "HFG1234567"
  mac_addresses:
    ether1: "AA:BB:CC:DD:EE:01"
    ether2: "AA:BB:CC:DD:EE:02"

# Option B: instance_overrides section
instance_overrides:
  defaults:
    hardware_identity:
      serial_number: "HFG1234567"
      mac_addresses:
        ether1: "AA:BB:CC:DD:EE:01"
```

### Step 4: Validate

```bash
.venv/bin/python3 v5/topology-tools/compile-topology.py
```

Success: no `E6806` errors.

---

## Enforcement Modes

The placeholder validator supports three enforcement modes:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `warn` | Report violations as warnings, compile succeeds | Development, initial migration |
| `warn+gate-new` | Warn on legacy, fail on new entities | Gradual enforcement |
| `enforce` | All violations are hard errors | Production |

### Configuring Enforcement Mode

In `v5/topology-tools/plugins/plugins.yaml`:

```yaml
- id: base.validator.instance_placeholders
  kind: validator
  entry: plugins/validators/instance_placeholder_validator.py:InstancePlaceholderValidator
  api_version: "1.x"
  stages: [validate]
  order: 140
  config:
    enforcement_mode: warn  # or: warn+gate-new, enforce
```

### Recommended Migration Path

1. **Start with `warn`** - identify all unresolved placeholders
2. **Move to `warn+gate-new`** - prevent new violations while fixing legacy
3. **Switch to `enforce`** - when all placeholders are resolved

---

## Error Reference

| Code | Description | Resolution |
|------|-------------|------------|
| `E6801` | Invalid placeholder syntax | Fix syntax: `@required:format` or `@optional:format` |
| `E6802` | Required override missing | Add value in instance file |
| `E6803` | Override path not marked | Remove override or add placeholder in object |
| `E6804` | Override path not found | Check path exists in object template |
| `E6805` | Format validation failed | Value doesn't match format (e.g., invalid MAC) |
| `E6806` | Unresolved placeholder after merge | Provide value for `@required` placeholder |

---

## Common Scenarios

### Scenario 1: New Device Deployment

1. Create instance file from template
2. Gather hardware identities from device
3. Fill in `@required` fields
4. Run compiler to validate
5. Generate Terraform/Ansible

### Scenario 2: Placeholder Value Unknown

If you don't know a value yet (e.g., device not purchased):

```yaml
# Use TODO marker (will trigger E6806 warning)
hardware_identity:
  serial_number: "<TODO_SERIAL_NUMBER>"
  mac_addresses:
    ether1: "02:00:00:00:00:01"  # Placeholder MAC (locally administered)
```

Locally administered MACs start with `02:`, `06:`, `0A:`, or `0E:`.

### Scenario 3: Optional Field Not Needed

Simply omit optional fields - no override needed:

```yaml
# Object has: ether3: @optional:mac
# Instance omits ether3 entirely - valid
hardware_identity:
  mac_addresses:
    ether1: "AA:BB:CC:DD:EE:01"
    ether2: "AA:BB:CC:DD:EE:02"
    # ether3 not specified - OK
```

---

## Discovery Script (Future)

A hardware discovery script is planned:

```bash
# Future: auto-discover and patch instance files
python3 v5/topology-tools/discover-hardware-identity.py \
  --device rtr-mikrotik-chateau \
  --ssh admin@192.168.88.1 \
  --output-patch
```

See: `adr/plan/v5-production-readiness.md` Phase 6.

---

## References

- ADR 0068: `adr/0068-object-yaml-as-instance-template-with-explicit-overrides.md`
- Format registry: `v5/topology-tools/data/instance-field-formats.yaml`
- Validator plugin: `v5/topology-tools/plugins/validators/instance_placeholder_validator.py`
- Error catalog: `v5/topology-tools/data/error-catalog.yaml`

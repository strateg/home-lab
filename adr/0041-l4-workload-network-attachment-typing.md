---
adr: "0041"
layer: "L4"
scope: "workload-network-attachment-typing"
status: "Accepted"
date: "2026-02-24"
public_api:
  - "L4 lxc[].networks[].network_ref"
  - "L4 lxc[].networks[].bridge_ref"
  - "L4 lxc[].networks[].ip"
  - "L4 vms[].networks[].network_ref"
breaking_changes: false
related:
  - "0037"
  - "0038"
---

# ADR 0041: L4 Workload Network Attachment Typing

- Status: Accepted
- Date: 2026-02-24

## TL;DR

| Aspect | Value |
|---|---|
| Scope | Add typed schema definitions for L4 workload network attachments |
| Problem | `lxc[].networks` and `vms[].networks` are untyped arrays in schema |
| Main decision | Create `LxcNetworkAttachment` and `VmNetworkAttachment` definitions |
| Breaking changes | None (existing data already conforms) |
| Result | Schema-enforced network attachment contracts for L4 workloads |

## Context

### Problem Statement

ADR-0037 D5 identified that L4 workload network attachments (`lxc[].networks`, `vms[].networks`) are weakly typed in the JSON schema:

```json
"networks": {
  "type": "array"
}
```

This means:
1. `network_ref` is not schema-enforced
2. Invalid fields are silently accepted
3. Required fields like `ip` are not validated
4. Cross-layer reference validation relies entirely on runtime checks

### Current Usage Analysis

LXC network attachments in topology use these fields:
- `network_ref` (required): Reference to L2 network
- `bridge_ref` (optional): Reference to L2 bridge
- `ip` (required): Static IP with CIDR
- `gateway` (optional): Gateway IP
- `interface` (optional): Interface name (eth0, eth1, etc.)
- `vlan_tag` (optional): VLAN tag for tagged traffic
- `firewall` (optional): Boolean for Proxmox firewall

### Relationship to ADR-0038

ADR-0038 Phase 1 added runtime-to-network reachability validation. This ADR complements that work by:
1. Enforcing `network_ref` presence at schema level
2. Enabling stronger cross-layer validation
3. Documenting the attachment contract explicitly

## Decision

### D1. Create `LxcNetworkAttachment` schema definition

```json
"LxcNetworkAttachment": {
  "type": "object",
  "required": ["network_ref", "ip"],
  "properties": {
    "network_ref": {
      "$ref": "#/definitions/NetworkRef",
      "description": "Reference to L2 network"
    },
    "bridge_ref": {
      "$ref": "#/definitions/BridgeRef",
      "description": "Reference to L2 bridge (optional, inferred from network if not set)"
    },
    "ip": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+/[0-9]+$",
      "description": "Static IP address with CIDR notation"
    },
    "gateway": {
      "type": "string",
      "format": "ipv4",
      "description": "Gateway IP address"
    },
    "interface": {
      "type": "string",
      "pattern": "^eth[0-9]+$",
      "description": "Network interface name"
    },
    "vlan_tag": {
      "type": "integer",
      "minimum": 1,
      "maximum": 4094,
      "description": "VLAN tag for tagged traffic"
    },
    "firewall": {
      "type": "boolean",
      "description": "Enable Proxmox firewall on interface"
    }
  },
  "additionalProperties": false
}
```

### D2. Create `VmNetworkAttachment` schema definition

```json
"VmNetworkAttachment": {
  "type": "object",
  "required": ["network_ref"],
  "properties": {
    "network_ref": {
      "$ref": "#/definitions/NetworkRef",
      "description": "Reference to L2 network"
    },
    "bridge_ref": {
      "$ref": "#/definitions/BridgeRef",
      "description": "Reference to L2 bridge"
    },
    "ip": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+/[0-9]+$",
      "description": "Static IP address with CIDR notation (optional for DHCP)"
    },
    "gateway": {
      "type": "string",
      "format": "ipv4",
      "description": "Gateway IP address"
    },
    "model": {
      "type": "string",
      "enum": ["virtio", "e1000", "rtl8139"],
      "description": "Network adapter model"
    },
    "mac_address": {
      "type": "string",
      "pattern": "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$",
      "description": "MAC address override"
    },
    "vlan_tag": {
      "type": "integer",
      "minimum": 1,
      "maximum": 4094,
      "description": "VLAN tag for tagged traffic"
    },
    "firewall": {
      "type": "boolean",
      "description": "Enable Proxmox firewall on interface"
    }
  },
  "additionalProperties": false
}
```

### D3. Update Lxc and Vm definitions

```json
"Lxc": {
  "properties": {
    "networks": {
      "type": "array",
      "items": { "$ref": "#/definitions/LxcNetworkAttachment" }
    }
  }
}

"Vm": {
  "properties": {
    "networks": {
      "type": "array",
      "items": { "$ref": "#/definitions/VmNetworkAttachment" }
    }
  }
}
```

## Migration

No data migration required. Existing topology data already conforms to the proposed schema.

Validation after schema update:
```bash
python3 topology-tools/validate-topology.py --topology topology.yaml --strict
```

## Consequences

### Benefits

- Schema-enforced `network_ref` requirement catches errors at validation time
- Invalid field names rejected by `additionalProperties: false`
- IP format validated by pattern
- Explicit documentation of attachment contract

### Trade-offs

- Slightly stricter schema may reject previously-accepted (but invalid) data
- `additionalProperties: false` prevents future ad-hoc extensions

### Success Metrics

| Metric | Target |
|---|---|
| Existing topology passes validation | Yes |
| LXC/VM network attachments schema-validated | 100% |
| Breaking changes | 0 |

## References

- [ADR 0037](0037-l2-network-substrate-and-workload-binding-contracts.md) - D5 typed attachments (superseded, but referenced)
- [ADR 0038](0038-network-binding-contracts-phase1.md) - Network binding contracts Phase 1
- `topology/L4-platform/lxc/*.yaml` - Current LXC definitions
- `topology-tools/schemas/topology-v4-schema.json` - Schema to update

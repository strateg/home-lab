# Infrastructure Overview

**Generated from**: topology.yaml v4.0.0
**Date**: 2026-02-17 18:11:30

---

## Metadata

- **Organization**: home-lab
- **Environment**: production
- **Author**: dprohhorov
- **Created**: 2025-10-06
- **Last Updated**: 2026-02-17
- **Version**: 

**Description**: Home lab infrastructure with MikroTik Chateau LTE7 ax as central router, Orange Pi 5 as application server, Proxmox as database/dev server

---

## Infrastructure Statistics

| Resource Type | Count |
|---------------|-------|
| Physical Devices | 4 |
| Virtual Machines | 0 |
| LXC Containers | 2 |
| Networks | 9 |
| Services | 15 |
| Storage Pools | 3 |

**Total Compute Resources**: 2

---

## Quick Links

- [Network Diagram](network-diagram.md) - Visual representation of network topology
- [IP Allocation](ip-allocation.md) - IP address assignments
- [Services Inventory](services.md) - Running services and applications
- [Devices Inventory](devices.md) - Hardware and virtual machines

---

## Architecture Principles

This infrastructure follows **Infrastructure-as-Data** principles:

1. **Single Source of Truth**: `topology.yaml` defines entire infrastructure
2. **Layered Model (L0–L7)**: Strict downward references (no upward coupling)
3. **ID-based References**: No hardcoded IPs or names
4. **Trust Zones**: Security boundaries with automated firewall rules
5. **Version Controlled**: All configuration in Git

---

## Regenerating Documentation

To regenerate this documentation:

```bash
python3 scripts/generate-docs.py
```

To regenerate Terraform and Ansible configurations:

```bash
python3 scripts/generate-terraform.py
python3 scripts/generate-ansible-inventory.py
```

---

**DO NOT EDIT MANUALLY** - Regenerate from topology.yaml
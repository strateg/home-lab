# Infrastructure Generators for Topology v4.0

This directory contains Python generators that transform topology.yaml (L0-L7 layered) into Terraform configs, Ansible inventory, and documentation.

## Overview

Single Source of Truth: topology.yaml

Generated artifacts:
- Terraform configurations (Proxmox + MikroTik)
- Ansible inventory (hosts and variables)
- Network diagrams and inventories (Markdown)

## Scripts

### validate-topology.py
Validate topology.yaml schema and references.

Usage:
```bash
python scripts/validate-topology.py --topology topology.yaml --schema schemas/topology-v4-schema.json
```

### generate-terraform.py
Generate Proxmox Terraform from L1/L2/L3/L4.

Usage:
```bash
python scripts/generate-terraform.py --topology topology.yaml --output generated/terraform
```

### generate-terraform-mikrotik.py
Generate MikroTik RouterOS Terraform from L1/L2/L5.

Usage:
```bash
python scripts/generate-terraform-mikrotik.py --topology topology.yaml --output generated/terraform-mikrotik
```

### generate-ansible-inventory.py
Generate Ansible inventory from L1/L2/L4 and L7 (ansible config).

Usage:
```bash
python scripts/generate-ansible-inventory.py --topology topology.yaml --output generated/ansible/inventory/production
```

### generate-docs.py
Generate documentation from L0-L5.

Usage:
```bash
python scripts/generate-docs.py --topology topology.yaml --output generated/docs
```

### regenerate-all.py
Run validation and all generators in order.

Usage:
```bash
python scripts/regenerate-all.py --topology topology.yaml
```

## Dependencies

```bash
python -m pip install pyyaml jinja2 jsonschema
```

## Outputs

```
generated/
  terraform/
  terraform-mikrotik/
  ansible/inventory/production/
  docs/
```

## Topology v4 Structure

- L0 Meta: version, defaults, security_policy
- L1 Foundation: devices, interfaces, UPS
- L2 Network: networks, bridges, routing, firewall
- L3 Data: storage, data_assets
- L4 Platform: VMs, LXC, templates
- L5 Application: services, certs, DNS
- L6 Observability: monitoring, alerts, dashboards
- L7 Operations: workflows, ansible, backup

References must only point downward or within the same layer.

## Generator Inputs by Layer

| Generator | Reads From |
|-----------|------------|
| Terraform (Proxmox) | L1, L2, L3, L4 |
| Terraform (MikroTik) | L1, L2, L5 |
| Ansible Inventory | L1, L2, L4, L7 |
| Documentation | L0, L1, L2, L3, L4, L5 |
| Validator | All layers |

## Directory Structure (v4)

```
new_system_v4/
  topology.yaml
  topology/
    L0-meta.yaml
    L1-foundation.yaml
    L2-network.yaml
    L3-data.yaml
    L4-platform.yaml
    L5-application.yaml
    L6-observability.yaml
    L7-operations.yaml
  schemas/
    topology-v4-schema.json
  generated/
    terraform/
    terraform-mikrotik/
    ansible/inventory/production/
    docs/
  scripts/
    generate-terraform.py
    generate-terraform-mikrotik.py
    generate-ansible-inventory.py
    generate-docs.py
    validate-topology.py
    regenerate-all.py
    templates/
      terraform/
      terraform-mikrotik/
      ansible/
      docs/
```

## Quick Start

```bash
python scripts/validate-topology.py --topology topology.yaml --schema schemas/topology-v4-schema.json
python scripts/regenerate-all.py --topology topology.yaml
```

## Notes

- Do not edit generated files under generated/. They are overwritten on each run.
- Templates live in scripts/templates/ and use Jinja2.

## Important Notes

### DO NOT Edit Generated Files

Files in generated/ are automatically regenerated and auto-cleaned.

- DO NOT manually edit files in generated/
- DO NOT commit generated/ to Git
- DO edit topology.yaml as the single source of truth
- DO edit ansible/playbooks/ and ansible/roles/ manually

## Troubleshooting

1) Missing required section
- Ensure topology.yaml includes L0-L7 includes.

2) Template not found
- Ensure scripts/templates/ exists and contains .j2 files.

3) Reference validation failed
- Run validate-topology.py and fix reported refs.

## Status

- Generators updated for topology v4.0
- Last updated: 2026-02-17

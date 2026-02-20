# Topology Tools (v4)

`topology-tools/` contains topology-driven generators and validator.

Related root directories:
- `schemas/` - topology schema and validator policy
- `topology-tools/templates/` - Jinja2 templates for generated artifacts
- `manual-scripts/` - manual setup/config scripts (separated from topology tooling)

Topology scripts transform `topology.yaml` (L0-L7 layered) into Terraform configs, Ansible inventory, and documentation.

## Overview

Single Source of Truth: `topology.yaml`

Generated artifacts:
- Terraform configurations (Proxmox + MikroTik)
- Ansible inventory (hosts and variables)
- Network diagrams and inventories (Markdown)

## Scripts

### validate-topology.py
Validate topology.yaml schema and references.

Usage:
```bash
python topology-tools/validate-topology.py --topology topology.yaml --schema schemas/topology-v4-schema.json
```

### generate-terraform.py
Generate Proxmox Terraform from L1/L2/L3/L4.

Usage:
```bash
python topology-tools/generate-terraform.py --topology topology.yaml --output generated/terraform
```

### generate-terraform-mikrotik.py
Generate MikroTik RouterOS Terraform from L1/L2/L5.

Usage:
```bash
python topology-tools/generate-terraform-mikrotik.py --topology topology.yaml --output generated/terraform-mikrotik
```

### generate-ansible-inventory.py
Generate Ansible inventory from L1/L2/L4 and L7 (ansible config).

Usage:
```bash
python topology-tools/generate-ansible-inventory.py --topology topology.yaml --output generated/ansible/inventory/production
```

### generate-docs.py
Generate documentation from L0-L5.

Usage:
```bash
python topology-tools/generate-docs.py --topology topology.yaml --output generated/docs
```

### regenerate-all.py
Run validation and all generators in order.

Usage:
```bash
python topology-tools/regenerate-all.py --topology topology.yaml
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

## Architecture Notes (v4)

- L0 Meta: version, defaults, security_policy
- L1 Foundation: devices, interfaces, UPS
- L2 Network: networks, bridges, routing, firewall
- L3 Data: storage, data_assets
- L4 Platform: VMs, LXC, templates
- L5 Application: services, certs, DNS
- L6 Observability: monitoring, alerts, dashboards
- L7 Operations: workflows, ansible, backup

References must only point downward or within the same layer.

## Important Notes

### DO NOT Edit Generated Files

Files in generated/ are automatically regenerated and auto-cleaned.

- DO NOT manually edit files in generated/
- DO NOT commit generated/ to Git
- DO edit topology.yaml as the single source of truth
- DO edit ansible/playbooks/ and ansible/roles/ manually

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
python topology-tools/validate-topology.py --topology topology.yaml --schema topology-tools/schemas/topology-v4-schema.json
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

Icon modes:
```bash
# Default: icon-nodes (@{ icon: ... })
python topology-tools/generate-docs.py --topology topology.yaml --output generated/docs

# Optional fallback for older Mermaid renderers
python topology-tools/generate-docs.py --topology topology.yaml --output generated/docs --mermaid-icon-compat

# Disable icons completely
python topology-tools/generate-docs.py --topology topology.yaml --output generated/docs --no-mermaid-icons
```

`--mermaid-icon-compat` embeds icons as inline SVG data URIs in node labels.
This mode works without runtime `registerIconPacks(...)` and without icon CDN access.

Default mode emits Mermaid `icon` nodes and expects icon packs:
- `si` (Simple Icons)
- `mdi` (Material Design Icons)

CDN example:
```js
import mermaid from "CDN/mermaid.esm.mjs";

mermaid.registerIconPacks([
  {
    name: "si",
    loader: () =>
      fetch("https://unpkg.com/@iconify-json/simple-icons/icons.json").then((res) => res.json()),
  },
  {
    name: "mdi",
    loader: () =>
      fetch("https://unpkg.com/@iconify-json/mdi/icons.json").then((res) => res.json()),
  },
]);
```

Bundler example (lazy loading):
```js
import mermaid from "mermaid";

mermaid.registerIconPacks([
  { name: "si", loader: () => import("@iconify-json/simple-icons").then((m) => m.icons) },
  { name: "mdi", loader: () => import("@iconify-json/mdi").then((m) => m.icons) },
]);
```

Bundler example (no lazy loading):
```js
import mermaid from "mermaid";
import { icons as siIcons } from "@iconify-json/simple-icons";
import { icons as mdiIcons } from "@iconify-json/mdi";

mermaid.registerIconPacks([
  { name: "si", icons: siIcons },
  { name: "mdi", icons: mdiIcons },
]);
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
home-lab/
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
  generated/
    terraform/
    terraform-mikrotik/
    ansible/inventory/production/
    docs/
  topology-tools/
    generate-terraform.py
    generate-terraform-mikrotik.py
    generate-ansible-inventory.py
    generate-docs.py
    validate-topology.py
    regenerate-all.py
    topology_loader.py
    split-topology.py
    schemas/
      topology-v4-schema.json
      validator-policy.yaml
    templates/
      terraform/
      terraform-mikrotik/
      ansible/
      docs/
  manual-scripts/
    openwrt/
    opi5/
```

## Quick Start

```bash
python topology-tools/validate-topology.py --topology topology.yaml --schema topology-tools/schemas/topology-v4-schema.json
python topology-tools/regenerate-all.py --topology topology.yaml
```

## Notes

- Do not edit generated files under generated/. They are overwritten on each run.
- Templates live in topology-tools/templates/ and use Jinja2.

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
- Ensure topology-tools/templates/ exists and contains .j2 files.

3) Reference validation failed
- Run validate-topology.py and fix reported refs.

## Status

- Generators updated for topology v4.0
- Last updated: 2026-02-17

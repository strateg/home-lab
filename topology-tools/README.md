# Topology Tools (v4)

`topology-tools/` contains topology-driven generators and validator.

Related root directories:
- `topology-tools/schemas/` - topology schema and validator policy
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

`--mermaid-icon-compat` embeds icons directly as inline SVG data URIs in Mermaid labels.
This mode does not require `registerIconPacks(...)` and avoids icon CDN/network dependency.

Default mode emits Mermaid `icon` nodes with icon IDs from:
- `si` (Simple Icons)
- `mdi` (Material Design Icons)

Your Mermaid runtime must register icon packs.

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

References:
- https://docs.mermaidchart.com/mermaid-oss/config/icons.html
- https://iconify.design/docs/icons/icon-sets/

### validate-mermaid-render.py
Validate Mermaid renderability of generated docs using Mermaid CLI.

Usage:
```bash
# Auto-detect icon mode from generated docs
python topology-tools/validate-mermaid-render.py --docs-dir generated/docs

# Explicit mode checks
python topology-tools/validate-mermaid-render.py --docs-dir generated/docs --icon-mode icon-nodes
python topology-tools/validate-mermaid-render.py --docs-dir generated/docs --icon-mode compat
```

### regenerate-all.py
Run validation and all generators in order.
By default it also validates Mermaid rendering for generated docs.

Usage:
```bash
python topology-tools/regenerate-all.py --topology topology.yaml
python topology-tools/regenerate-all.py --topology topology.yaml --skip-mermaid-validate
```

## Dependencies

```bash
python -m pip install pyyaml jinja2 jsonschema
```

Optional (for render validation script):
```bash
npm install --save-dev @mermaid-js/mermaid-cli @iconify-json/simple-icons @iconify-json/mdi @iconify-json/logos
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
- L1 Foundation: devices, interfaces, physical storage inventory (`storage_slots` + mount type), UPS
- L2 Network: networks, bridges, routing, firewall
- L3 Data: storage, data_assets, logical storage bindings (disk_ref + os_device)
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

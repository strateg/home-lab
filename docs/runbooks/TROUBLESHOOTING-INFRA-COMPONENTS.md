# Troubleshooting: Infrastructure Components

**Status:** Active
**Updated:** 2026-03-28

---

## 1. Compile/Validation Pipeline

### Symptom

- `task validate:v5` fails.

### Checks

```powershell
task framework:strict
python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock --secrets-mode passthrough
```

### Typical Causes

- lock drift (`E7824`),
- shard structure or ID contract errors (`E7101`, `E7108`, `E7109`),
- unresolved strict placeholders (`E6806`).

### Recovery

```powershell
python topology-tools/generate-framework-lock.py --force
python topology-tools/verify-framework-lock.py --strict
```

Then rerun compile and validate.

---

## 2. Proxmox Terraform Lane

### Symptom

- `terraform validate` or `terraform plan` fails in `generated/home-lab/terraform/proxmox`.

### Checks

```powershell
terraform -chdir=generated/home-lab/terraform/proxmox fmt -check
terraform -chdir=generated/home-lab/terraform/proxmox validate
terraform -chdir=generated/home-lab/terraform/proxmox plan -refresh=false
```

### Typical Causes

- stale generated artifacts after topology change,
- provider credential mismatch,
- invalid bridge/network references.

### Recovery

1. Regenerate artifacts via `compile-topology.py`.
2. Re-run `init` and `validate`.
3. Compare against last known-good plan output.

---

## 3. MikroTik Terraform Lane

### Symptom

- `terraform plan` fails in `generated/home-lab/terraform/mikrotik`.

### Checks

```powershell
terraform -chdir=generated/home-lab/terraform/mikrotik fmt -check
terraform -chdir=generated/home-lab/terraform/mikrotik validate
terraform -chdir=generated/home-lab/terraform/mikrotik plan -refresh=false
```

### Typical Causes

- invalid interface/VLAN/firewall binding,
- provider API access mismatch,
- topology drift against router state.

### Recovery

1. Confirm generated `interfaces.tf` and `firewall.tf` match intended topology.
2. Re-run plan with fresh credentials/session.
3. Roll back to previous known-good generated artifact set if needed.

---

## 4. Ansible Inventory and Runtime

### Symptom

- `ansible-inventory --list` fails or host vars missing.

### Checks

```powershell
python topology-tools/assemble-ansible-runtime.py --topology topology/topology.yaml --env production
ansible-inventory -i generated/home-lab/ansible/runtime/production/hosts.yml --list
```

### Typical Causes

- missing runtime assembly step,
- malformed overrides under `projects/home-lab/ansible/inventory-overrides/`,
- bad values in generated `host_vars`.

### Recovery

1. Regenerate inventory.
2. Re-assemble runtime inventory.
3. Diff runtime output against last successful snapshot.

---

## 5. Docs/Diagram Lane

### Symptom

- docs generation fails or Mermaid gate returns errors.

### Checks

```powershell
task build:v5-docs
python topology-tools/utils/validate-mermaid-render.py --docs-root generated/home-lab/docs
```

### Typical Causes

- unresolved template tokens in generated Markdown,
- incompatible Mermaid icon mode.

### Recovery

1. Run in compatibility mode: `task build:v5-docs-compat`.
2. For icon-node mode, prefer local Iconify packs (`node_modules/@iconify-json/{mdi,simple-icons}`); if unavailable, embedded fallback glyphs are used for known IDs.

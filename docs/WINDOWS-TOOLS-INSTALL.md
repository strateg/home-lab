# Windows Tool Installation: Build vs Deploy

**Date:** 26 февраля 2026 г.
**Goal:** Separate toolchains for (A) build/validate/generate and (B) deploy/apply

---

## A) Build / Validate / Generate

**Purpose:** Generate configs, validate topology, run docs tools

**Required tools:**
- Git
- Python 3.11+
- pip

**Optional tools:**
- jq (JSON processing)
- yq (YAML processing)

### Install (PowerShell)

```powershell
# From repo root
scripts\windows\install-build-tools.ps1
```

### Verify

```powershell
scripts\windows\verify-build-tools.ps1
```

### Optional: Skip venv setup

```powershell
scripts\windows\install-build-tools.ps1 -SkipVenv
```

### Optional: Skip optional tools

```powershell
scripts\windows\install-build-tools.ps1 -SkipOptional
```

---

## B) Deploy / Apply to Target Devices

**Purpose:** Apply generated configs to real devices (Terraform, Ansible, SSH)

**Required tools:**
- Terraform (apply)
- OpenSSH client (SSH/SCP)

**Optional tools:**
- WSL + Ansible (recommended for Ansible on Windows)
- rsync (if needed)

### Install (PowerShell)

```powershell
# From repo root
scripts\windows\install-deploy-tools.ps1
```

### Install WSL + Ansible (optional)

```powershell
scripts\windows\install-deploy-tools.ps1 -WithWSLAnsible
```

### Verify

```powershell
scripts\windows\verify-deploy-tools.ps1
```

---

## Recommended Workflow

### 1) Build / Validate / Generate

```powershell
# Validate topology
python topology-tools\validate-topology.py

# Generate configs
python topology-tools\generate-terraform-proxmox.py
python topology-tools\generate-ansible-inventory.py
python topology-tools\generate-docs.py
```

### 2) Deploy / Apply

```powershell
# Terraform apply
cd terraform
terraform apply

# Ansible (via WSL)
# In WSL shell:
ansible-playbook -i ansible/inventory/production/hosts.yml ansible/site.yml
```

---

## Notes

- Ansible is not native on Windows. Use WSL2 or Docker.
- Keep build tools separate from deploy tools to reduce risk.
- You can generate configs on Windows, deploy from WSL.
- If you only generate docs/configs, you may skip deploy tools.

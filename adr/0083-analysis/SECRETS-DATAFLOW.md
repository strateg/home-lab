# ADR 0083: Secrets and Dataflow Analysis

## Purpose

Trace secret material from source (SOPS-encrypted files) through pipeline stages to runtime artifacts. Define redaction, cleanup, and non-persistence guarantees for every initialization mechanism.

---

## Secret Lifecycle Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ SOURCE (tracked, encrypted)                                                      │
│ projects/home-lab/secrets/                                                        │
│   mikrotik.enc.yaml          ← SOPS + age encrypted                              │
│   proxmox.enc.yaml           ← SOPS + age encrypted                              │
│   orangepi.enc.yaml          ← SOPS + age encrypted                              │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │ sops -d (decrypt)
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ PIPELINE: generate stage (secret-free outputs only!)                              │
│ generated/home-lab/bootstrap/                                                     │
│   rtr-mikrotik-chateau/init-terraform.rsc    ← {{ terraform_password }} UNRESOLVED│
│   hv-proxmox-xps/answer.toml                ← {{ root_password }} UNRESOLVED     │
│   sbc-orangepi5/user-data                   ← {{ ssh_authorized_key }} UNRESOLVED │
│   INITIALIZATION-MANIFEST.yaml               ← No secrets, only metadata          │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │ assemble stage
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ PIPELINE: assemble stage (secret injection)                                       │
│ .work/native/bootstrap/                                                           │
│   rtr-mikrotik-chateau/init-terraform.rsc    ← terraform_password = "actual_pw"  │
│   hv-proxmox-xps/answer.toml                ← root_password = "actual_pw"        │
│   sbc-orangepi5/user-data                   ← ssh_authorized_key = "ssh-ed25519 ."│
│   INITIALIZATION-STATE.yaml                  ← Runtime state (no secrets)         │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │ deploy domain execution
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ DEPLOY DOMAIN: init-node.py reads from .work/native/ only                         │
│   netinstall uses .work/native/bootstrap/rtr-mikrotik-chateau/init-terraform.rsc │
│   USB media preparation uses .work/native/bootstrap/hv-proxmox-xps/answer.toml   │
│   SD card uses .work/native/bootstrap/sbc-orangepi5/user-data                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Per-Mechanism Secret Dataflow

### 1. MikroTik (`netinstall`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/mikrotik.enc.yaml` | `terraform_password`, `wifi_passwords`, `vpn_psk` | Tracked (encrypted) |
| Generate | `generated/.../init-terraform.rsc` | `{{ terraform_password }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/native/bootstrap/.../init-terraform.rsc` | Actual password inserted | Ignored (`.gitignore`) |
| Deploy | Sent to device via `netinstall-cli -s` flag | Password embedded in script | Transient |

**Secret fields in bootstrap:**
- `terraform_password` — automation user password for REST API access
- No other secrets needed for day-0 bootstrap

**Cleanup:** `.work/native/bootstrap/` is ephemeral. `init-node.py` SHOULD warn if stale secret-bearing files exist older than 24 hours.

### 2. Proxmox VE (`unattended_install`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/proxmox.enc.yaml` | `root_password`, `terraform_api_token` | Tracked (encrypted) |
| Generate | `generated/.../answer.toml` | `{{ root_password }}` placeholder | Tracked (secret-free) |
| Generate | `generated/.../post-install-minimal.sh` | `{{ terraform_api_token }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/native/bootstrap/.../answer.toml` | Actual root password | Ignored |
| Assemble | `.work/native/bootstrap/.../post-install-minimal.sh` | Actual API token | Ignored |
| Deploy | ISO boot with answer.toml on USB | Passwords on installation media | Physical media |

**Secret fields in bootstrap:**
- `root_password` — Proxmox root password (for answer.toml)
- `terraform_api_token` — API token for Terraform access (created by post-install script)

**Cleanup:** After Proxmox installation, the USB media with answer.toml SHOULD be wiped. `init-node.py` SHOULD log a reminder.

### 3. Orange Pi 5 (`cloud_init`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/orangepi.enc.yaml` | `ssh_authorized_keys`, `ansible_password` | Tracked (encrypted) |
| Generate | `generated/.../user-data` | `{{ ssh_authorized_key }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/native/bootstrap/.../user-data` | Actual SSH public key | Ignored |
| Deploy | Written to SD card boot partition | Keys on SD card | Physical media |

**Secret fields in bootstrap:**
- `ssh_authorized_keys` — public keys for SSH access
- `ansible_password` — optional, for password-based initial access

**Note:** SSH public keys are not highly sensitive (they are public keys), but the unified model treats all credential material through SOPS for consistency.

### 4. LXC Containers (`terraform_managed`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/lxc.enc.yaml` | `root_password`, `ssh_keys` | Tracked (encrypted) |
| Generate | `generated/.../terraform/proxmox/lxc.tf` | `var.lxc_root_password` reference | Tracked (secret-free) |
| Assemble | `.work/native/terraform/proxmox/terraform.tfvars` | Actual passwords | Ignored |
| Deploy | `tofu apply` reads `.work/native/` tfvars | Terraform injects via API | Transient |

**No bootstrap secrets needed** — Terraform creates LXC containers with secrets passed as `terraform.tfvars` variables. The `initialization_contract` has `mechanism: terraform_managed` with no bootstrap template.

### 5. Generic Linux (`ansible_bootstrap`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/<device>.enc.yaml` | `ansible_password`, `ssh_keys` | Tracked (encrypted) |
| Generate | `generated/.../bootstrap-playbook.yml` | `{{ ansible_password }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/native/bootstrap/.../bootstrap-playbook.yml` | Actual password | Ignored |
| Deploy | `ansible-playbook` reads from `.work/native/` | SSH + password-based auth | Transient |

---

## Security Invariants

### I1: Generated Root is Secret-Free

**Rule:** `generated/**` MUST NEVER contain actual secret values.

**Enforcement:**
- `base.assembler.bootstrap_secrets` (assemble.verify phase) scans `generated/` for known secret patterns.
- CI/CD pipeline includes a secret-leak scan as a quality gate.
- `.gitignore` does NOT protect `generated/` — it IS tracked. Secret-free is the only protection.

### I2: Secret-Bearing Artifacts Live Only in `.work/native/`

**Rule:** All secret-bearing rendered artifacts MUST be written to `.work/native/bootstrap/` only.

**Enforcement:**
- `.work/` is in `.gitignore`.
- `base.assembler.bootstrap_secrets` writes exclusively to `.work/native/`.
- `init-node.py` reads exclusively from `.work/native/`.

### I3: SOPS+age is the Only Secrets Backend

**Rule:** All mechanisms use SOPS+age (ADR 0072). No Ansible Vault, no environment variables for persistent secrets.

**Supersedes:** ADR 0057 D8 Ansible Vault reference.

**Flow:** `sops -d projects/home-lab/secrets/<device>.enc.yaml` → decrypted YAML → template rendering → `.work/native/`.

### I4: Cleanup and Non-Persistence

**Rules:**
1. `.work/native/bootstrap/` files are ephemeral — they should not persist longer than needed.
2. `init-node.py --cleanup --node <id>` SHOULD remove secret-bearing artifacts after successful handover verification.
3. Stale artifacts (>24h since last modification) trigger a warning on next `init-node.py` run.
4. Physical media (USB, SD card) cleanup is the operator's responsibility — `init-node.py` logs a reminder.

---

## Assemble Stage Plugin Detail

```python
# Pseudocode for base.assembler.bootstrap_secrets
class BootstrapSecretsAssembler:
    def execute(self, ctx, stage):
        manifest = ctx.subscribe("base.generator.initialization_manifest", "initialization_manifest_data")
        secrets_dir = ctx.project_root / "secrets"
        work_dir = ctx.workspace_root / "bootstrap"  # .work/native/bootstrap/

        for node in manifest["nodes"]:
            if node["mechanism"] == "terraform_managed":
                continue  # No bootstrap artifacts to assemble

            # Load mechanism-specific secrets
            secrets = sops_decrypt(secrets_dir / f"{node['device_domain']}.enc.yaml")

            # For each generated artifact, render with secrets
            for artifact_key, rel_path in node["artifacts"].items():
                source = ctx.generated_root / rel_path
                target = work_dir / node["id"] / Path(rel_path).name
                template_content = source.read_text()
                rendered = jinja_render(template_content, secrets)
                target.parent.mkdir(parents=True, exist_ok=True)
                write_text_atomic(target, rendered)

        ctx.publish("assembled_bootstrap_paths", {
            node["id"]: str(work_dir / node["id"])
            for node in manifest["nodes"]
            if node["mechanism"] != "terraform_managed"
        })
```

---

## Secret Field Registry

| Device Domain | SOPS File | Secret Fields | Consumed By |
|---------------|-----------|---------------|-------------|
| mikrotik | `mikrotik.enc.yaml` | `terraform_password` | `init-terraform.rsc` |
| proxmox | `proxmox.enc.yaml` | `root_password`, `terraform_api_token` | `answer.toml`, `post-install-minimal.sh` |
| orangepi | `orangepi.enc.yaml` | `ssh_authorized_keys`, `ansible_password` | `user-data` |
| lxc | `lxc.enc.yaml` | `root_password`, `ssh_keys` | `terraform.tfvars` (via assemble) |

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Secret leaked into `generated/` | assemble.verify secret-leak scanner + CI gate |
| `.work/native/` accidentally committed | `.gitignore` entry + pre-commit hook |
| Stale secret-bearing artifacts | `init-node.py` age warning + `--cleanup` flag |
| Physical media with secrets | Operator log reminder from `init-node.py` |
| SOPS key compromise | age key rotation documented in ADR 0072 |

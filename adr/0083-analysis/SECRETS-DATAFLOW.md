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
│ .work/deploy/bundles/<bundle_id>/artifacts/                                       │
│   rtr-mikrotik-chateau/init-terraform.rsc    ← terraform_password = "actual_pw"  │
│   hv-proxmox-xps/answer.toml                ← root_password = "actual_pw"        │
│   sbc-orangepi5/user-data                   ← ssh_authorized_key = "ssh-ed25519 ."│
│   INITIALIZATION-STATE.yaml                  ← Runtime state (no secrets)         │
└──────────────────────────┬──────────────────────────────────────────────────────┘
                           │ deploy domain execution
                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ DEPLOY DOMAIN: init-node.py reads from deploy bundle only                         │
│   netinstall uses .work/deploy/bundles/<bundle_id>/artifacts/rtr-mikrotik-chateau/init-terraform.rsc │
│   USB media preparation uses .work/deploy/bundles/<bundle_id>/artifacts/hv-proxmox-xps/answer.toml   │
│   SD card uses .work/deploy/bundles/<bundle_id>/artifacts/sbc-orangepi5/user-data                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Per-Mechanism Secret Dataflow

### 1. MikroTik (`netinstall`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/terraform/mikrotik.yaml` + `projects/home-lab/secrets/instances/rtr-mikrotik-chateau.yaml` | `terraform_password`, `wifi_passwords`, `vpn_psk` | Tracked (encrypted) |
| Generate | `generated/.../init-terraform.rsc` | `{{ terraform_password }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/deploy/bundles/<bundle_id>/artifacts/.../init-terraform.rsc` | Actual password inserted | Ignored (`.gitignore`) |
| Deploy | Sent to device via `netinstall-cli -s` flag | Password embedded in script | Transient |

**Secret fields in bootstrap:**
- `terraform_password` — automation user password for REST API access
- No other secrets needed for day-0 bootstrap

**Cleanup:** Deploy bundle artifacts are ephemeral. `init-node.py` SHOULD warn if stale secret-bearing files exist older than 24 hours.

### 2. Proxmox VE (`unattended_install`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/terraform/proxmox.yaml` | `root_password`, `terraform_api_token` | Tracked (encrypted) |
| Generate | `generated/.../answer.toml` | `{{ root_password }}` placeholder | Tracked (secret-free) |
| Generate | `generated/.../post-install-minimal.sh` | `{{ terraform_api_token }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/deploy/bundles/<bundle_id>/artifacts/.../answer.toml` | Actual root password | Ignored |
| Assemble | `.work/deploy/bundles/<bundle_id>/artifacts/.../post-install-minimal.sh` | Actual API token | Ignored |
| Deploy | ISO boot with answer.toml on USB | Passwords on installation media | Physical media |

**Secret fields in bootstrap:**
- `root_password` — Proxmox root password (for answer.toml)
- `terraform_api_token` — API token for Terraform access (created by post-install script)

**Cleanup:** After Proxmox installation, the USB media with answer.toml SHOULD be wiped. `init-node.py` SHOULD log a reminder.

### 3. Orange Pi 5 (`cloud_init`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/instances/srv-orangepi5.yaml` | `ssh_authorized_keys`, `ansible_password` | Tracked (encrypted) |
| Generate | `generated/.../user-data` | `{{ ssh_authorized_key }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/deploy/bundles/<bundle_id>/artifacts/.../user-data` | Actual SSH public key | Ignored |
| Deploy | Written to SD card boot partition | Keys on SD card | Physical media |

**Secret fields in bootstrap:**
- `ssh_authorized_keys` — public keys for SSH access
- `ansible_password` — optional, for password-based initial access

**Note:** SSH public keys are not highly sensitive (they are public keys), but the unified model treats all credential material through SOPS for consistency.

### 4. LXC Containers (implicit terraform-managed)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/terraform/proxmox.yaml` | `root_password`, `ssh_keys` | Tracked (encrypted) |
| Generate | `generated/.../terraform/proxmox/lxc.tf` | `var.lxc_root_password` reference | Tracked (secret-free) |
| Assemble | `.work/deploy/bundles/<bundle_id>/artifacts/terraform/proxmox/terraform.tfvars` | Actual passwords | Ignored |
| Deploy | `tofu apply` reads deploy bundle tfvars | Terraform injects via API | Transient |

**No bootstrap secrets needed** — LXC containers are implicitly terraform-managed (no `initialization_contract`). Terraform creates them directly via Proxmox API with secrets passed as `terraform.tfvars` variables.

### 5. Generic Linux (`ansible_bootstrap`)

| Stage | File | Secret Fields | Location |
|-------|------|---------------|----------|
| Source | `projects/home-lab/secrets/<device>.enc.yaml` | `ansible_password`, `ssh_keys` | Tracked (encrypted) |
| Generate | `generated/.../bootstrap-playbook.yml` | `{{ ansible_password }}` placeholder | Tracked (secret-free) |
| Assemble | `.work/deploy/bundles/<bundle_id>/artifacts/.../bootstrap-playbook.yml` | Actual password | Ignored |
| Deploy | `ansible-playbook` reads from deploy bundle | SSH + password-based auth | Transient |

---

## Security Invariants

### I1: Generated Root is Secret-Free

**Rule:** `generated/**` MUST NEVER contain actual secret values.

**Enforcement:**
- `base.assembler.bootstrap_secrets` (assemble.verify phase) scans `generated/` for known secret patterns.
- CI/CD pipeline includes a secret-leak scan as a quality gate.
- `.gitignore` does NOT protect `generated/` — it IS tracked. Secret-free is the only protection.

### I2: Secret-Bearing Artifacts Live Only in Deploy Bundles

**Rule:** All secret-bearing rendered artifacts MUST be written to `.work/deploy/bundles/<bundle_id>/artifacts/` only.

**Enforcement:**
- `.work/` is in `.gitignore`.
- `base.assembler.bootstrap_secrets` writes exclusively to the deploy bundle.
- `init-node.py` reads exclusively from the deploy bundle.

### I3: SOPS+age is the Only Secrets Backend

**Rule:** All mechanisms use SOPS+age (ADR 0072). No Ansible Vault, no environment variables for persistent secrets.

**Supersedes:** ADR 0057 D8 Ansible Vault reference.

**Flow:** `sops -d projects/home-lab/secrets/<device>.enc.yaml` → decrypted YAML → template rendering → deploy bundle.

### I4: Cleanup and Non-Persistence

**Rules:**
1. Deploy bundle artifact files are ephemeral — they should not persist longer than needed.
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
        work_dir = ctx.workspace_root / "bootstrap"  # .work/deploy/bundles/<bundle_id>/artifacts/

        for node in manifest["nodes"]:
            # Only nodes in manifest have initialization_contract (implicit terraform-managed excluded)
            domain = node["device_domain"]
            instance_id = node["id"]

            # Merge provider-level and instance-level secrets
            secrets = {}
            provider_secret = secrets_dir / "terraform" / f"{domain}.yaml"
            instance_secret = secrets_dir / "instances" / f"{instance_id}.yaml"
            if provider_secret.exists():
                secrets.update(sops_decrypt(provider_secret))
            if instance_secret.exists():
                secrets.update(sops_decrypt(instance_secret))

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
        })
```

---

## Secret Field Registry

| Device Domain | SOPS File(s) | Secret Fields | Consumed By |
|---------------|-----------|---------------|-------------|
| mikrotik | `terraform/mikrotik.yaml` + `instances/rtr-mikrotik-chateau.yaml` | `terraform_password` | `init-terraform.rsc` |
| proxmox | `terraform/proxmox.yaml` | `root_password`, `terraform_api_token` | `answer.toml`, `post-install-minimal.sh` |
| orangepi | `instances/srv-orangepi5.yaml` | `ssh_authorized_keys`, `ansible_password` | `user-data` |
| lxc | `terraform/proxmox.yaml` (shared) | `root_password`, `ssh_keys` | `terraform.tfvars` (via assemble) |

**Note:** All paths are relative to `projects/home-lab/secrets/`. The assembler resolves the actual SOPS file(s) using a combination of `terraform/<domain>.yaml` (provider-level secrets) and `instances/<instance_id>.yaml` (instance-specific secrets). Both are decrypted and merged into a single secret context per node.

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Secret leaked into `generated/` | assemble.verify secret-leak scanner + CI gate |
| Deploy bundle accidentally committed | `.gitignore` entry + pre-commit hook |
| Stale secret-bearing artifacts | `init-node.py` age warning + `--cleanup` flag |
| Physical media with secrets | Operator log reminder from `init-node.py` |
| SOPS key compromise | age key rotation documented in ADR 0072 |

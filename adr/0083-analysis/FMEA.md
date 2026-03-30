# ADR 0083: Failure Mode and Effects Analysis (FMEA)

## Purpose

Define failure points, detection methods, retry strategies, and rollback procedures for each initialization mechanism.

---

## Severity Scale

| Level | Description | Impact on Deployment |
|-------|-------------|---------------------|
| **Critical** | Device bricked or unreachable | Requires physical intervention |
| **High** | Bootstrap failed, device in unknown state | Requires manual recovery or re-flash |
| **Medium** | Partial bootstrap, some services missing | Can retry or manually fix |
| **Low** | Non-functional but recoverable | Automatic retry likely sufficient |

---

## 1. MikroTik — `netinstall` Mechanism

### Failure Points

| ID | Failure Point | Phase | Severity | Detection | Root Cause |
|----|--------------|-------|----------|-----------|------------|
| M1 | Netinstall CLI not found | Pre-check | Low | `command_exists` check | Missing tool installation |
| M2 | NPK firmware file missing | Pre-check | Low | `file_exists` check | Missing download |
| M3 | Installation segment unreachable | Pre-check | Medium | `network_reachable` check | Wrong VLAN or cable |
| M4 | Device not entering netinstall mode | Bootstrap | High | Timeout (no BOOTP request seen) | Device not in reset mode, button not held |
| M5 | Netinstall transfer interrupted | Bootstrap | High | `netinstall-cli` exit code ≠ 0 | Network interruption, USB power issue |
| M6 | Bootstrap .rsc script syntax error | Bootstrap | High | RouterOS boot log / API unreachable | Template rendering error |
| M7 | Device reboots but API unreachable | Handover | Medium | `api_reachable` check timeout | Firewall misconfiguration in .rsc |
| M8 | Credential authentication fails | Handover | Medium | `credential_valid` check fails | Password mismatch (SOPS decryption error) |
| M9 | SSL certificate issues | Handover | Low | `curl` SSL error | Self-signed cert not accepted |

### Recovery Procedures

| Failure | Recovery | Automated? |
|---------|----------|------------|
| M1–M3 | Fix prerequisites, re-run | Yes (pre-check loop) |
| M4 | Physical: hold reset button, power cycle device | No (manual) |
| M5 | Re-run netinstall (device returns to netinstall mode automatically) | Yes (`--force`) |
| M6 | Fix template, re-run pipeline + netinstall | Semi (pipeline auto, netinstall manual trigger) |
| M7 | Console access to fix firewall, or re-netinstall | No (manual) |
| M8 | Verify SOPS decryption, re-assemble, re-run handover check | Yes (`--verify-only`) |
| M9 | Add `insecure: true` to handover check or import cert | Yes (config change) |

### Retry Strategy

```yaml
netinstall_retry:
  pre_check_failures: retry immediately after fix
  bootstrap_failures: wait 30s, retry up to 3 times
  handover_failures:
    max_attempts: 10
    backoff_seconds: 15
    backoff_strategy: linear
    rationale: "Device reboot after netinstall takes 30-120 seconds"
```

---

## 2. Proxmox VE — `unattended_install` Mechanism

### Failure Points

| ID | Failure Point | Phase | Severity | Detection | Root Cause |
|----|--------------|-------|----------|-----------|------------|
| P1 | ISO file missing or corrupted | Pre-check | Low | `file_exists` + checksum | Download error |
| P2 | Answer.toml not rendered | Pre-check | Low | `file_exists` check | Pipeline not run |
| P3 | USB media creation fails | Pre-check | Medium | Manual confirmation | Bad USB drive or dd failure |
| P4 | Answer.toml syntax error | Bootstrap | High | Proxmox installer error screen | Template rendering error |
| P5 | Disk detection fails | Bootstrap | Critical | Installer aborts | Wrong disk path in answer.toml |
| P6 | Network configuration wrong | Bootstrap | High | API unreachable after install | Wrong IP/gateway in answer.toml |
| P7 | Post-install script fails | Bootstrap | High | API accessible but terraform user missing | Script error or permission issue |
| P8 | API reachable but auth fails | Handover | Medium | `credential_valid` check | Token not created by post-install |

### Recovery Procedures

| Failure | Recovery | Automated? |
|---------|----------|------------|
| P1–P3 | Fix prerequisites, re-prepare media | No (physical media) |
| P4–P5 | Fix answer.toml template, re-run pipeline, re-install | No (full re-install required) |
| P6 | Console access to fix network, or re-install | No (manual console or re-install) |
| P7 | SSH to Proxmox, run post-install manually | Semi (SSH + manual script) |
| P8 | SSH to Proxmox, create terraform user manually | Semi (SSH + manual) |

### Retry Strategy

```yaml
proxmox_retry:
  pre_check_failures: retry after fix
  bootstrap_failures: requires full re-installation (no automatic retry)
  handover_failures:
    max_attempts: 5
    backoff_seconds: 30
    backoff_strategy: linear
    rationale: "Proxmox first boot takes 2-5 minutes"
```

**Critical note:** Proxmox unattended install is destructive (formats disks). Failed installation CANNOT be retried without full re-install. This makes answer.toml validation critical before execution.

### Pre-Execution Validation (MANDATORY per D16)

Per ADR 0083 D16, `init-node.py` MUST validate answer.toml before prompting for USB media creation:

1. **TOML syntax validation** — Parse and detect syntax errors early
2. **Required sections** — `[global]`, `[network]`, `[disk-setup]` must exist
3. **Disk path validation** — Must start with `/dev/`, warn on unusual paths
4. **Network consistency** — Compare with topology data, warn on mismatch
5. **Operator confirmation** — Require explicit `--confirm-destructive` flag

**Validation error codes:**

| Code | Description |
|------|-------------|
| E9710 | Missing `[global]` section in answer.toml |
| E9711 | Missing `[network]` section in answer.toml |
| E9712 | Missing `[disk-setup]` section in answer.toml |
| E9713 | Invalid disk path (must start with `/dev/`) |
| W9714 | Network configuration differs from topology (warning, not blocking) |
| E9715 | TOML syntax error |

**Example validation output:**

```
$ init-node.py --node hv-proxmox-xps

[PRE-VALIDATION] Checking Proxmox answer.toml...
  ✓ TOML syntax valid
  ✓ [global] section present
  ✓ [network] section present
  ✓ [disk-setup] section present
  ✓ Disk path /dev/sda valid
  ⚠ WARNING: answer.toml IP (10.0.10.1) differs from topology (10.0.10.2)

This operation will FORMAT disk /dev/sda on target device.
To proceed, re-run with --confirm-destructive flag.
```

---

## 3. Orange Pi 5 — `cloud_init` Mechanism

### Failure Points

| ID | Failure Point | Phase | Severity | Detection | Root Cause |
|----|--------------|-------|----------|-----------|------------|
| O1 | Base image missing | Pre-check | Low | `file_exists` check | Missing download |
| O2 | User-data YAML syntax error | Pre-check | Medium | `cloud-init schema --config-file` validation | Template rendering error |
| O3 | SD card write fails | Bootstrap | Medium | `dd` exit code or disk utility error | Bad SD card |
| O4 | Cloud-init fails silently | Bootstrap | High | SSH unreachable after boot | Invalid user-data (valid YAML but wrong semantics) |
| O5 | Network configuration wrong | Bootstrap | High | SSH unreachable | Wrong IP/gateway in network-config |
| O6 | Python not installed | Handover | Low | `python_installed` check | cloud-init user-data missing python package |
| O7 | SSH key not accepted | Handover | Medium | `ssh_reachable` passes but auth fails | Wrong key in user-data |

### Recovery Procedures

| Failure | Recovery | Automated? |
|---------|----------|------------|
| O1–O2 | Fix prerequisites, re-validate | Yes (pre-check) |
| O3 | Retry SD card write, try different card | No (physical media) |
| O4–O5 | Connect via HDMI+keyboard, fix config, or re-flash SD | No (manual) |
| O6 | SSH manually, install python | Semi (SSH + manual) |
| O7 | Re-flash SD card with corrected user-data | No (physical media) |

### Retry Strategy

```yaml
cloud_init_retry:
  pre_check_failures: retry after fix
  bootstrap_failures: requires SD card re-flash (no automatic retry)
  handover_failures:
    max_attempts: 15
    backoff_seconds: 20
    backoff_strategy: linear
    rationale: "First boot with cloud-init takes 2-5 minutes, apt updates can add 5+ minutes"
```

---

## 4. LXC Containers — Implicit Terraform-managed (no `initialization_contract`)

### Failure Points

| ID | Failure Point | Phase | Severity | Detection | Root Cause |
|----|--------------|-------|----------|-----------|------------|
| L1 | Proxmox API unreachable | Pre-check | Medium | `terraform_plan_succeeds` check | Proxmox not initialized yet |
| L2 | Terraform plan fails | Handover | Medium | `terraform plan` exit code | Config error or missing template |
| L3 | Container creation fails | Deploy | Medium | `terraform apply` error | Resource limits, storage full |
| L4 | Container starts but unhealthy | Deploy | Low | Health check timeout | Package install failure inside container |

### Recovery Procedures

| Failure | Recovery | Automated? |
|---------|----------|------------|
| L1 | Initialize Proxmox first (dependency) | Yes (dependency chain) |
| L2 | Fix Terraform config, re-run pipeline | Yes (re-generate + re-plan) |
| L3 | Fix resource limits, `terraform apply` again | Yes (re-apply) |
| L4 | `terraform destroy` + `terraform apply` | Yes (idempotent) |

### Retry Strategy

```yaml
terraform_managed_retry:
  all_failures: terraform is inherently retryable (idempotent apply)
  handover_check:
    max_attempts: 3
    backoff_seconds: 10
    rationale: "Terraform plan should succeed immediately if config is valid"
```

---

## 5. Generic Linux — `ansible_bootstrap` Mechanism

### Failure Points

| ID | Failure Point | Phase | Severity | Detection | Root Cause |
|----|--------------|-------|----------|-----------|------------|
| A1 | OS not installed | Pre-check | High | `manual_confirmation` fails | Operator skipped OS install |
| A2 | SSH key not deployed | Pre-check | Medium | `manual_confirmation` fails | Operator skipped key deployment |
| A3 | SSH unreachable | Bootstrap | Medium | `ssh_reachable` check | Wrong IP, firewall, or SSH not running |
| A4 | Ansible playbook fails | Bootstrap | Medium | Ansible exit code ≠ 0 | Package install failure, permission error |
| A5 | Python not available | Bootstrap | Medium | Ansible raw module fails | Minimal OS without Python |

### Recovery Procedures

| Failure | Recovery | Automated? |
|---------|----------|------------|
| A1–A2 | Complete manual steps, re-confirm | No (manual) |
| A3 | Fix network/firewall, retry | Semi (retry after fix) |
| A4 | Fix playbook, re-run | Yes (`--force`) |
| A5 | SSH manually, install python | No (manual) |

---

## State Transition Under Failure

All mechanisms follow the same state machine (ADR 0083 D6):

```
pending → bootstrapping → initialized → verified
                ↓                ↓
              failed           failed
                ↓                ↓
          (--force) → bootstrapping
```

**Key rules:**
1. Any failure during `bootstrapping` → `failed` state with error details.
2. Any failure during handover verification → `failed` state.
3. `--force` flag allows retry from any failed/verified state.
4. `init-node.py` MUST log detailed error context for debugging.

---

## Cross-Mechanism Risk Summary

| Risk | Mechanisms Affected | Probability | Impact | Mitigation Priority |
|------|-------------------|-------------|--------|-------------------|
| Template rendering error | All | Medium | High | Pre-execution template validation |
| Network unreachable after bootstrap | netinstall, cloud_init, unattended | Medium | High | Retry with backoff |
| Secret decryption failure | All | Low | Critical | SOPS key validation pre-flight |
| Physical media failure | unattended, cloud_init | Low | Medium | Operator instructions + verification |
| Disk format (destructive) | unattended | Low | Critical | Pre-execution answer.toml validation |

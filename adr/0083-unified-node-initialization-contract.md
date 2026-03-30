# ADR 0083: Unified Node Initialization Contract and Deploy-Domain Initialization Phase

**Date:** 2026-03-30
**Status:** Proposed
**Related:** ADR 0057 (MikroTik Netinstall Bootstrap), ADR 0072 (Unified Secrets Management), ADR 0074 (V5 Generator Architecture), ADR 0080 (Unified Build Pipeline), ADR 0082 (Plugin Module-Pack Composition)

---

## Context

### Problem

The v5 build pipeline (`discover -> compile -> validate -> generate -> assemble -> build`) assumes nodes are already reachable and manageable by Terraform or Ansible. However, real deployment requires a **day-0 initialization phase** that brings physical devices to a state where automation tools can connect.

Currently, initialization is fragmented:

| Device Type | Current Mechanism | Handover Target | Status |
|-------------|-------------------|-----------------|--------|
| MikroTik Chateau | netinstall + RouterOS script (ADR 0057) | Terraform REST API | Well-defined |
| Proxmox VE | Manual post-install script (487 lines) | Terraform Proxmox API | Ad-hoc |
| Orange Pi 5 | cloud-init placeholder | SSH + Ansible | Incomplete |
| LXC Containers | Helper-scripts | Terraform Proxmox provider | Manual |
| Cloud VMs | Provider-specific | Terraform + Ansible | Implicit |

### Identified Gaps

1. **No unified contract** - Each device has different initialization semantics
2. **No topology integration** - Initialization scripts do not consume topology.yaml
3. **No validation gates** - No pre-flight checks or post-initialization verification
4. **Mixed responsibility** - Scripts combine day-0 bootstrap with day-1 configuration
5. **Secret handling inconsistency** - Different patterns for credential injection
6. **No plugin integration** - Initialization is outside the v5 pipeline stages

### ADR 0057 Foundation

ADR 0057 establishes a solid pattern for MikroTik:
- Two-phase lifecycle (day-0 bootstrap, day-1+ Terraform)
- MAC-targeted netinstall mechanism
- Minimal handover contract (management IP, API access, terraform user)
- Secret-bearing artifacts in ignored execution roots

This pattern should be generalized to all device types.

### Constraints

- Initialization mechanisms are inherently device-specific
- Some devices require physical access (SD card, USB, console)
- Network bootstrap (PXE, netinstall) requires installation-segment access
- Cloud devices use provider APIs (no pre-bootstrap phase)
- Secrets must remain outside tracked repository roots
- Existing manual workflows must continue working during transition

---

## Decision

### D1. Separation of Concerns: Pipeline vs Deploy Domains

The v5 pipeline and deploy domain have different responsibilities and execution cadences:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  V5 PIPELINE (artifact generation, runs MANY times)                         │
│  ═══════════════════════════════════════════════════                         │
│  discover -> compile -> validate -> generate -> assemble -> build            │
│                                         │                                    │
│                                         ▼                                    │
│                              Produces artifacts:                             │
│                              • bootstrap scripts                             │
│                              • terraform configs                             │
│                              • ansible playbooks                             │
│                              • initialization manifest                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DEPLOY DOMAIN (execution, different cadences)                              │
│  ═════════════════════════════════════════════                              │
│                                                                             │
│  Pre-initialization ──► Terraform/OpenTofu ──► Ansible                      │
│  (runs ONCE)            (runs MANY times)      (runs MANY times)            │
│       │                        │                      │                      │
│       ▼                        ▼                      ▼                      │
│  netinstall              tofu apply           ansible-playbook              │
│  cloud-init              tofu plan            firewall, backup              │
│  answer.toml                                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key principle:** The v5 pipeline generates artifacts from topology. The deploy domain executes them. Pre-initialization runs once per device lifecycle reset; Terraform/Ansible run many times for configuration improvements.

**Rationale:** The v5 pipeline operates on topology data and generates artifacts. It does not execute external commands against hardware. Pre-initialization requires device-specific execution (netinstall, flash, SSH) which belongs to the deploy domain.

### D2. Define Unified Node Initialization Contract

Compute/router object modules MAY declare an `initialization_contract` specifying how instances of that object are bootstrapped.

**Contract is OPTIONAL.** Objects without `initialization_contract` are treated as **implicitly `terraform_managed`** — they are created and managed entirely by Terraform without a separate bootstrap phase. This applies to:
- LXC containers (created by Proxmox provider)
- Cloud VMs (created by cloud provider)
- Any resource lifecycle fully managed by Terraform

**Contract is REQUIRED** only for devices needing day-0 bootstrap before Terraform can connect:
- Physical devices (routers, hypervisors, SBCs)
- Devices requiring netinstall, USB boot, or SD card flashing

```yaml
# topology/object-modules/<domain>/obj.<domain>.<type>.yaml
object: obj.mikrotik.chateau_lte7_ax
# ... existing fields ...

initialization_contract:
  version: "1.0"
  mechanism: netinstall          # netinstall | unattended_install | cloud_init | ansible_bootstrap

  requirements:                  # Prerequisites for bootstrap execution
    - name: netinstall_cli_installed
      check: command_exists
      description: Netinstall CLI must be available on the control node
    - name: routeros_npk_available
      check: file_exists
      path: /srv/routeros/
      description: RouterOS NPK firmware image must be present
    - name: installation_segment_access
      check: network_reachable
      description: Control node must have access to the installation network segment

  bootstrap:
    template: templates/bootstrap/init-terraform.rsc.j2
    outputs:
      - bootstrap/{{ instance_id }}/init-terraform.rsc

  handover:
    provider: terraform-routeros/routeros
    checks:
      - type: api_reachable
        protocol: https
        port: 8443
      - type: credential_valid
        user: terraform
```

### D3. Support Multiple Initialization Mechanisms

| Mechanism | Description | Devices | Contract Required? |
|-----------|-------------|---------|-------------------|
| `netinstall` | MAC-targeted network reinstall | MikroTik | Yes |
| `unattended_install` | Answer file + post-install script | Proxmox VE | Yes |
| `cloud_init` | cloud-init user-data on boot media | Orange Pi, SBCs | Yes |
| `ansible_bootstrap` | Ansible playbook after manual OS install | Generic Linux | Yes |
| *(no contract)* | Terraform creates and manages entirely | LXC, Cloud VMs | No (implicit) |

**Note:** `terraform_managed` is no longer an explicit mechanism. Objects without `initialization_contract` are implicitly terraform-managed and do not appear in `INITIALIZATION-MANIFEST.yaml`.

### D4. Keep Bootstrap Artifact Generation in V5 Pipeline

Bootstrap generators remain within the v5 pipeline as part of the `generate` stage:

```yaml
# From ADR 0074 D4 ordering (generate stage: 190-399)
generate_stage:
  # ... existing generators ...
  # Device-specific bootstrap generators (300–379)
  # Only for objects WITH initialization_contract
  - 300-309: bootstrap_proxmox_generator       # object.proxmox.generator.bootstrap
  - 310-319: bootstrap_mikrotik_generator      # object.mikrotik.generator.bootstrap
  - 320-329: bootstrap_orangepi_generator      # object.orangepi.generator.bootstrap
  # Note: LXC/Cloud VMs have no bootstrap generators - they are terraform-managed implicitly
  # Bootstrap meta-generators (380–389, cross-cutting)
  - 380-389: initialization_manifest_generator # NEW: base.generator.initialization_manifest
```

**Key principle:** The v5 pipeline generates bootstrap artifacts. A separate orchestrator executes them.

### D5. Generate Unified Initialization Manifest

Add a new generator that produces a read-only static manifest at `generated/<project>/bootstrap/INITIALIZATION-MANIFEST.yaml`.

Runtime execution state MUST be stored outside `generated/`, for example:

- `.work/native/bootstrap/INITIALIZATION-STATE.yaml`

`INITIALIZATION-MANIFEST.yaml` is source-derived and regenerated by pipeline runs. `INITIALIZATION-STATE.yaml` is operator/runtime state and may be updated by orchestration scripts.

```yaml
version: "1.0"
generated_at: 2026-03-30T12:00:00Z
project: home-lab

nodes:
  - id: rtr-mikrotik-chateau
    object_ref: obj.mikrotik.chateau_lte7_ax
    mechanism: netinstall
    artifacts:
      bootstrap_script: bootstrap/rtr-mikrotik-chateau/init-terraform.rsc
      tfvars_example: bootstrap/rtr-mikrotik-chateau/terraform.tfvars.example
    requirements:
      - name: netinstall-cli
        check: command_exists
      - name: routeros-7.x.npk
        check: file_exists
        path: /srv/routeros/
    handover:
      provider: terraform-routeros/routeros
      endpoint: https://192.168.88.1:8443
      user: terraform
      checks:
        - api_reachable
        - credential_valid

  - id: hv-proxmox-xps
    object_ref: obj.proxmox.ve
    mechanism: unattended_install
    artifacts:
      answer_file: bootstrap/hv-proxmox-xps/answer.toml
      post_install: bootstrap/hv-proxmox-xps/post-install-minimal.sh
    requirements:
      - name: proxmox-ve-9.x.iso
        check: file_exists
    handover:
      provider: bpg/proxmox
      endpoint: https://10.0.10.1:8006
      user: root@pam
      checks:
        - api_reachable
        - credential_valid

  - id: sbc-orangepi5
    object_ref: obj.orangepi.rk3588.debian
    mechanism: cloud_init
    artifacts:
      user_data: bootstrap/sbc-orangepi5/user-data
      meta_data: bootstrap/sbc-orangepi5/meta-data
    requirements:
      - name: debian-12-arm64.img
        check: file_exists
    handover:
      provider: ansible
      endpoint: ssh://10.0.10.5:22
      user: opi
      checks:
        - ssh_reachable
        - python_installed
```

Runtime state example:

```yaml
version: "1.0"
updated_at: 2026-03-30T12:05:00Z

nodes:
  - id: rtr-mikrotik-chateau
    status: initialized                       # pending | initialized | verified | failed
    last_action: netinstall
    last_error: null
```

### D6. Pre-Initialization Orchestrator in Deploy Domain

Create `scripts/orchestration/deploy/init-node.py` as part of the deploy domain (separate from v5 pipeline):

```
scripts/
  orchestration/
    lane.py              # V5 pipeline orchestrator (artifact generation)
    deploy/
      init-node.py         # Pre-initialization orchestrator (runs ONCE)
      apply-terraform.py   # Terraform wrapper (runs MANY times)
      run-ansible.py       # Ansible wrapper (runs MANY times)
```

**Rationale:** D1 separates pipeline from deploy domain. Keeping deploy entrypoints under `scripts/orchestration/deploy/` preserves the repository convention that orchestration entrypoints live under `scripts/orchestration/`, while still isolating deploy-domain execution from pipeline orchestration (`lane.py`).

**Execution cadence:**

| Script | Domain | Cadence | Purpose |
| ------ | ------ | ------- | ------- |
| `lane.py` | Pipeline | Many times | Generate artifacts from topology |
| `init-node.py` | Deploy | Once per device | Bootstrap new/reset device |
| `apply-terraform.py` | Deploy | Many times | Apply topology configuration |
| `run-ansible.py` | Deploy | Many times | Apply operational configuration |

**init-node.py responsibilities:**
1. Read `INITIALIZATION-MANIFEST.yaml` (generated by pipeline)
2. Check prerequisites per device
3. Execute device-specific bootstrap (netinstall, flash, etc.)
4. Run handover verification (with configurable timeout/retry)
5. Update runtime state in `.work/native/bootstrap/INITIALIZATION-STATE.yaml`
6. Output ready-for-terraform/ansible confirmation

**Usage pattern:**
```bash
# Initialize specific node (runs ONCE when device is new/reset)
python scripts/orchestration/deploy/init-node.py --node rtr-mikrotik-chateau

# Initialize all pending nodes
python scripts/orchestration/deploy/init-node.py --all-pending

# Verify handover only (no bootstrap)
python scripts/orchestration/deploy/init-node.py --verify-only --node hv-proxmox-xps

# Force re-initialization of a previously initialized node
python scripts/orchestration/deploy/init-node.py --force --node rtr-mikrotik-chateau
```

**Batch mode and manual confirmation:**

When `--all-pending` is used, nodes with `manual_confirmation` requirements are **skipped** by default with a warning:

```
SKIP: sbc-orangepi5 requires manual_confirmation (os_installed). Use --node to initialize interactively.
```

The `--interactive` flag enables prompts for manual confirmations in batch mode. Without `--interactive`, only nodes with fully automatable prerequisites are processed.

**State machine for node initialization:**

```
                    ┌──────────────────────────────────────────┐
                    │              pending                       │
                    │  (initial state for new/reset devices)     │
                    └──────────┬───────────────────────────────┘
                               │ init-node.py --node <id>
                               ▼
                    ┌──────────────────────────────────────────┐
                    │           bootstrapping                    │
                    │  (bootstrap execution in progress)         │
                    └──────┬──────────────────┬────────────────┘
                           │ success          │ failure
                           ▼                  ▼
              ┌────────────────────┐  ┌────────────────────────┐
              │    initialized      │  │        failed           │
              │  (bootstrap done,   │  │  (retry: --force or     │
              │   handover pending) │  │   --node returns to     │
              └─────────┬──────────┘  │   bootstrapping)         │
                        │ verify       └──────────┬─────────────┘
                        ▼                         │ --force
              ┌────────────────────┐              │
              │      verified       │◄─────────────┘
              │  (handover checks   │  (retry from bootstrapping)
              │   passed, ready     │
              │   for Terraform)    │
              └────────────────────┘

Legal transitions:
  pending        → bootstrapping   (init-node.py --node)
  bootstrapping  → initialized     (bootstrap success)
  bootstrapping  → failed          (bootstrap error)
  initialized    → verified        (handover checks pass)
  initialized    → failed          (handover checks fail)
  failed         → bootstrapping   (init-node.py --force)
  verified       → bootstrapping   (init-node.py --force, for re-bootstrap)
  verified       → pending         (init-node.py --reset --node <id> --confirm-reset)
```

**Guard for `verified → pending`:** This transition is potentially dangerous if Terraform state exists. The `--reset` command MUST:
1. Require explicit `--confirm-reset` flag
2. Warn if Terraform state directory is non-empty
3. Log the reset action for audit trail

### D7. Decompose Large Bootstrap Scripts

Existing monolithic scripts (e.g., `proxmox-post-install.sh`) must be decomposed:

**Proxmox VE decomposition:**

| Phase | Scope | Mechanism |
|-------|-------|-----------|
| Phase 0: Bootstrap | Minimal API access | `answer.toml` + `post-install-minimal.sh` |
| Phase 1: Infrastructure | Storage pools, bridges | Terraform |
| Phase 2: Configuration | Packages, KSM, sensors | Ansible |

**Bootstrap boundary rule:** Day-0 scripts prepare ONLY what Terraform needs to connect. Everything else is day-1 configuration.

### D8. Standardize Handover Verification

Each initialization contract must specify verifiable handover checks:

| Check Type | Description | Implementation | Default Timeout |
|------------|-------------|----------------|-----------------|
| `api_reachable` | HTTP(S) endpoint responds | `curl --connect-timeout 5` | 5s per attempt |
| `ssh_reachable` | SSH port open | `nc -z -w 5` | 5s per attempt |
| `credential_valid` | Auth succeeds | Provider-specific API call | 10s per attempt |
| `python_installed` | Python available for Ansible | `ssh <host> python3 --version` | 10s per attempt |
| `terraform_plan_succeeds` | Terraform can plan | `terraform plan -input=false` | 60s per attempt |

**Retry and timeout contract:**

Handover checks MUST support configurable retry behavior because device-specific initialization (netinstall, reboot, cloud-init first boot) can take 1–10 minutes before the device becomes reachable.

```yaml
handover:
  provider: terraform-routeros/routeros
  timeout_seconds: 300          # Total timeout for all checks (default: 300)
  retry:
    max_attempts: 10            # Maximum retry attempts (default: 10)
    backoff_seconds: 15         # Delay between retries (default: 15)
    backoff_strategy: linear    # linear | exponential (default: linear)
  checks:
    - type: api_reachable
      protocol: https
      port: 8443
    - type: credential_valid
      user: terraform
```

If `retry` is omitted, defaults apply. If `timeout_seconds` is exceeded before all checks pass, the node transitions to `failed` state with a detailed error log.

### D9. Keep Secret Contract Consistent with ADR 0072

Bootstrap secrets follow the unified secrets model (ADR 0072):

- Tracked templates remain secret-free
- Secret values come from `projects/<project>/secrets/` (SOPS-encrypted)
- Secret-bearing rendered artifacts exist only in ignored execution roots (`.work/native/`)

**Supersession note:** ADR 0057 D8 references Ansible Vault for secret management. This ADR supersedes the ADR 0057 secret contract for all bootstrap artifacts. All mechanisms MUST use SOPS+age (ADR 0072) as the unified secrets backend.

### D10. Add Initialization Contract Validator

Add a new validator to verify initialization contracts in object modules:

```yaml
# plugins.yaml
- id: base.validator.initialization_contract
  kind: validator_json
  stages: [validate]
  phase: post
  order: 180
  description: Validates initialization contracts for compute/router objects
  schema: schemas/initialization-contract.schema.json
```

**Diagnostic range allocation:** `E97xx` for initialization contract validation errors.

| Code | Description |
|------|-------------|
| `E9700` | Missing required `initialization_contract` field on compute/router object |
| `E9701` | Invalid mechanism type |
| `E9702` | Missing `bootstrap.template` in initialization contract |
| `E9703` | Handover check type unknown |
| `E9704` | Requirement check type unknown |
| `E9705` | `post_handover` Terraform/Ansible ownership overlap detected |

### D10a. Manifest Generator Data Bus Declaration

The `base.generator.initialization_manifest` plugin MUST declare data bus keys per ADR 0080 §6:

```yaml
- id: base.generator.initialization_manifest
  kind: generator
  stages: [generate]
  phase: post
  order: 385
  depends_on:
    - object.mikrotik.generator.bootstrap
    - object.proxmox.generator.bootstrap
    - object.orangepi.generator.bootstrap
  produces:
    - key: initialization_manifest_path
      scope: pipeline_shared
      description: Absolute path to generated INITIALIZATION-MANIFEST.yaml
    - key: initialization_manifest_data
      scope: pipeline_shared
      description: Parsed manifest content for assemble-stage consumers
  description: >
    Aggregates initialization contracts from all compute/router object modules
    and emits a unified INITIALIZATION-MANIFEST.yaml.
```

### D11. Define Post-Handover Lifecycle Phases

After bootstrap handover, devices proceed through day-1+ configuration phases in the deploy domain. The initialization contract MAY specify `post_handover` to define the full IaC lifecycle:

**Status:** `post_handover` is **informational metadata** in contract version 1.0. The v5 pipeline does not consume it for artifact generation. It serves as documentation for operators and deploy-domain scripts. Promotion to normative (with full schema and validator coverage) is planned for contract version 1.1 after the pipeline can utilize it.

```yaml
initialization_contract:
  # ... bootstrap and handover fields ...

  post_handover:
    terraform:
      provider: terraform-routeros/routeros
      modules:
        - mikrotik-base
        - mikrotik-vlans
        - mikrotik-wireguard
        - mikrotik-routing
    ansible:
      collection: community.routeros
      playbooks:
        - mikrotik-postconfig
        - mikrotik-firewall
        - mikrotik-validate
```

**Lifecycle phases and execution cadence:**

| Phase | Tool | Cadence | Responsibility |
| ----- | ---- | ------- | -------------- |
| Day-0: Bootstrap | Device-specific | **ONCE** | Minimal management access |
| Day-1+: Topology | OpenTofu/Terraform | **MANY** | State-managed objects (bridges, VLANs, IPs, routing) |
| Day-1+: Operations | Ansible | **MANY** | Ordered rules, scripts, hardening |
| Ongoing: Backup | Ansible | **MANY** | Text export + binary backup |

**Key insight:** Pre-initialization prepares the device ONCE. After that, the Terraform/Ansible improvement cycle runs MANY times as configuration evolves.

**Golden Rule:** One object must NOT be managed by both Terraform and Ansible simultaneously.

### D12. Assemble Stage Integration for Secret-Bearing Bootstrap Artifacts

ADR 0080 §4.4 defines the `assemble` stage as the place where execution views are created from baseline + overrides + local inputs. Bootstrap artifacts require secret injection (e.g., passwords, SSH keys) before they can be executed by the deploy domain.

**Pipeline flow for bootstrap secrets:**

```
generate stage                          assemble stage                    deploy domain
─────────────                           ──────────────                    ─────────────
generated/<project>/bootstrap/          .work/native/bootstrap/           Device execution
  rtr-mikrotik-chateau/                   rtr-mikrotik-chateau/
    init-terraform.rsc  ──(secret-free)──►  init-terraform.rsc ──(secrets)──► netinstall
    terraform.tfvars.example               terraform.tfvars    ──(secrets)──► tofu apply
```

**Assemble-stage plugin:**

```yaml
- id: base.assembler.bootstrap_secrets
  kind: assembler
  stages: [assemble]
  phase: run
  order: 420
  depends_on: []
  consumes:
    - from_plugin: base.generator.initialization_manifest
      key: initialization_manifest_data
      required: true
  produces:
    - key: assembled_bootstrap_paths
      scope: pipeline_shared
      description: Paths to secret-bearing bootstrap artifacts in .work/native/
  description: >
    Renders secret-bearing bootstrap artifacts from generated templates + SOPS secrets
    into .work/native/bootstrap/ execution roots. Enforces ADR 0072 secret isolation.
```

**Key principle:** The `generate` stage writes secret-free baseline artifacts to `generated/`. The `assemble` stage combines them with decrypted secrets from `projects/<project>/secrets/` into `.work/native/`. The deploy domain (`init-node.py`) reads only from `.work/native/`.

### D13. Multi-Instance Instantiation from Object Contract

The `initialization_contract` is declared on the **object module** (e.g., `obj.proxmox.lxc.debian12.base`), but bootstrap artifacts are generated per **instance** (e.g., `lxc-docker`, `lxc-gitea`, `lxc-grafana`). The instantiation mechanism works as follows:

1. **Object module** declares the contract template: mechanism, requirements, bootstrap template, handover checks.
2. **Instance data** provides instance-specific values: `instance_id`, management IP, hostname, secrets references.
3. **Bootstrap generator** iterates over all instances of an object and renders per-instance artifacts using the contract's `bootstrap.template` with instance-specific context.
4. **Initialization manifest generator** aggregates all per-instance entries into a single `INITIALIZATION-MANIFEST.yaml`.

**Example:** `obj.proxmox.lxc.debian12.base` without `initialization_contract` is implicitly terraform-managed and produces zero bootstrap artifacts (Terraform creates LXC containers directly). But `obj.proxmox.ve` with `mechanism: unattended_install` produces one set of bootstrap artifacts per Proxmox hypervisor instance.

```yaml
# Object: declares WHAT and HOW
initialization_contract:
  mechanism: unattended_install
  bootstrap:
    template: templates/bootstrap/answer.toml.j2   # Template with {{ instance_id }}, {{ management_ip }}

# Instance: provides WHO (instance-specific data)
instance: hv-proxmox-xps
  management_ip: 10.0.10.1
  # ... other instance fields ...

# Generated artifact: per-instance output
generated/home-lab/bootstrap/hv-proxmox-xps/answer.toml   # Rendered with instance data
```

### D14. Contract Versioning and Evolution

The `initialization_contract.version` field follows semantic versioning for the contract schema:

| Version | Meaning | Backward Compatibility |
|---------|---------|----------------------|
| `1.0` | Initial contract: mechanism, requirements, bootstrap, handover | N/A (first version) |
| `1.1` | Planned: `post_handover` promoted to normative | Additive, backward compatible |
| `2.0` | Reserved: breaking schema changes | Migration guide required |

**Rules:**
1. Minor version bumps (1.0 → 1.1) MUST be backward compatible (additive fields only).
2. Major version bumps (1.x → 2.0) MAY break compatibility and MUST include a migration guide.
3. The validator MUST accept contracts with version ≤ current supported version.
4. Version `1.0` contracts MUST remain valid when the validator is updated to support `1.1`.

### D15. `ansible_bootstrap` Mechanism Specification

The `ansible_bootstrap` mechanism covers devices where the OS is installed manually (or via external process) and Ansible performs the remaining day-0 setup:

```yaml
initialization_contract:
  version: "1.0"
  mechanism: ansible_bootstrap
  requirements:
    - name: os_installed
      check: manual_confirmation
      description: Operator confirms OS is installed and SSH accessible
    - name: ssh_key_deployed
      check: manual_confirmation
      description: Operator confirms SSH key is deployed to target
  bootstrap:
    template: templates/bootstrap/ansible-bootstrap-playbook.yml.j2
    outputs:
      - bootstrap/{{ instance_id }}/bootstrap-playbook.yml
  handover:
    provider: ansible
    checks:
      - type: ssh_reachable
        port: 22
      - type: python_installed
      - type: credential_valid
        user: ansible
```

**Workflow:** Operator manually installs OS → deploys SSH key → runs `init-node.py --node <id>` → Ansible bootstrap playbook installs Python, creates automation user, configures management network → handover checks pass → device ready for day-1 Ansible.

**Note:** This mechanism is the fallback for any device that does not support netinstall, unattended install, or cloud-init. The `manual_confirmation` check type requires operator interaction.

### D16. Pre-Validation for Destructive Operations

Some bootstrap mechanisms are **destructive** (format disks, overwrite firmware). Failed bootstrap after destructive action cannot be automatically retried.

**Rule:** `init-node.py` MUST validate configuration before executing destructive operations.

| Mechanism | Destructive? | Pre-Validation Required |
| --------- | ------------ | ----------------------- |
| `netinstall` | Yes (formats flash) | NPK file exists, MAC reachable |
| `unattended_install` | Yes (formats disks) | **answer.toml syntax + required fields + disk paths** |
| `cloud_init` | Yes (overwrites SD) | user-data YAML syntax |
| `ansible_bootstrap` | No | SSH reachable |

**Proxmox Pre-Validation (Critical):**

Before prompting operator to create USB media, `init-node.py` MUST:
1. Parse `answer.toml` as valid TOML
2. Verify required sections exist: `[global]`, `[network]`, `[disk-setup]`
3. Verify disk paths are syntactically valid
4. Warn if disk paths are unusual (e.g., `/dev/nvme*` on system without NVMe)
5. Verify network configuration matches topology data

```python
# Pseudocode for Proxmox pre-validation
def validate_proxmox_answer(answer_path, topology):
    answer = toml.load(answer_path)

    # Required sections
    assert "[global]" in answer, "E9710: Missing [global] section"
    assert "[network]" in answer, "E9711: Missing [network] section"
    assert "[disk-setup]" in answer, "E9712: Missing [disk-setup] section"

    # Disk path validation
    disk = answer["disk-setup"]["disk"]
    if not disk.startswith("/dev/"):
        raise ValidationError("E9713: Invalid disk path")

    # Network validation
    expected_ip = topology.get_instance_ip(instance_id)
    if answer["network"]["address"] != expected_ip:
        warn("W9714: answer.toml IP differs from topology")
```

### D17. Existing Device Migration Path

When adopting ADR 0083 on an existing infrastructure where devices are already initialized and managed by Terraform:

**Scenario:** MikroTik router is already bootstrapped and has Terraform state.

**Migration procedure:**

1. Add `initialization_contract` to object module
2. Run pipeline to generate `INITIALIZATION-MANIFEST.yaml`
3. Run `init-node.py --import --node <id>` to import existing device
4. Orchestrator verifies handover checks (device must be reachable)
5. On success: state file created with `status: verified`
6. No bootstrap executed — device is already operational

**Import command:**

```bash
# Import existing initialized device into state management
python scripts/orchestration/deploy/init-node.py --import --node rtr-mikrotik-chateau

# Verifies:
# - Device is reachable (handover checks pass)
# - Terraform state exists (optional, warning if missing)
# Creates state entry with status: verified
```

**State entry after import:**

```yaml
nodes:
  - id: rtr-mikrotik-chateau
    status: verified
    imported: true              # Flag indicating import, not bootstrap
    imported_at: "2026-03-30T12:00:00Z"
    last_action: import
    attempt_count: 0            # No bootstrap attempts
```

### D18. Contract Drift Detection

When pipeline regenerates `INITIALIZATION-MANIFEST.yaml`, the contract may have changed since last initialization.

**Rule:** `init-node.py` MUST detect and warn about contract drift.

**Implementation:**

State file stores contract hash:

```yaml
nodes:
  - id: rtr-mikrotik-chateau
    status: verified
    contract_hash: "sha256:abc123..."  # Hash of initialization_contract YAML
```

On each `init-node.py` run:
1. Compute current contract hash from manifest
2. Compare with stored hash in state file
3. If different: warn operator

```
WARNING: Contract changed for node rtr-mikrotik-chateau
  Previous: mechanism=netinstall, 3 requirements, 2 checks
  Current:  mechanism=netinstall, 4 requirements, 3 checks

  Use --force to re-bootstrap with new contract, or --acknowledge-drift to update hash without re-bootstrap.
```

**Flags:**
- `--force`: Re-bootstrap with new contract
- `--acknowledge-drift`: Update contract_hash without re-bootstrapping (for non-breaking changes)

---

## Schema

### Initialization Contract Schema (JSONSchema)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Node Initialization Contract",
  "description": "All mechanisms require bootstrap.template. Objects without initialization_contract are implicitly terraform-managed and don't need this schema.",
  "type": "object",
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+$"
    },
    "mechanism": {
      "enum": ["netinstall", "unattended_install", "cloud_init", "ansible_bootstrap"],
      "description": "Bootstrap mechanism. Objects without initialization_contract are implicitly terraform-managed."
    },
    "requirements": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string", "minLength": 1 },
          "check": {
            "enum": ["command_exists", "file_exists", "network_reachable", "manual_confirmation"]
          },
          "path": { "type": "string" },
          "description": { "type": "string" }
        },
        "required": ["name", "check"],
        "additionalProperties": false
      }
    },
    "bootstrap": {
      "type": "object",
      "properties": {
        "template": { "type": "string", "minLength": 1 },
        "post_install": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Additional post-install script templates (e.g., Proxmox post-install-minimal.sh)"
        },
        "outputs": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Explicit output paths. If omitted, derived from template name as bootstrap/{{ instance_id }}/<template_basename>"
        }
      },
      "required": ["template"]
    },
    "handover": {
      "type": "object",
      "properties": {
        "provider": { "type": "string" },
        "timeout_seconds": {
          "type": "integer",
          "minimum": 10,
          "default": 300,
          "description": "Total timeout for all handover checks"
        },
        "retry": {
          "type": "object",
          "properties": {
            "max_attempts": { "type": "integer", "minimum": 1, "default": 10 },
            "backoff_seconds": { "type": "integer", "minimum": 1, "default": 15 },
            "backoff_strategy": { "enum": ["linear", "exponential"], "default": "linear" }
          },
          "additionalProperties": false
        },
        "checks": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "type": {
                "enum": ["api_reachable", "ssh_reachable", "credential_valid", "python_installed", "terraform_plan_succeeds"]
              },
              "protocol": { "type": "string" },
              "port": { "type": "integer" },
              "user": { "type": "string" }
            },
            "required": ["type"]
          },
          "minItems": 1
        }
      },
      "required": ["provider", "checks"]
    },
    "post_handover": {
      "type": "object",
      "description": "Informational metadata (v1.0). Describes day-1+ IaC lifecycle. Not consumed by pipeline.",
      "properties": {
        "terraform": {
          "type": "object",
          "properties": {
            "provider": { "type": "string" },
            "modules": { "type": "array", "items": { "type": "string" } }
          }
        },
        "ansible": {
          "type": "object",
          "properties": {
            "collection": { "type": "string" },
            "playbooks": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    }
  },
  "required": ["version", "mechanism", "bootstrap", "handover"],
  "allOf": [
    {
      "if": { "properties": { "mechanism": { "const": "unattended_install" } } },
      "then": {
        "properties": {
          "bootstrap": {
            "required": ["template", "post_install"],
            "properties": {
              "post_install": { "minItems": 1 }
            }
          }
        }
      }
    },
    {
      "if": { "properties": { "mechanism": { "const": "cloud_init" } } },
      "then": {
        "properties": {
          "bootstrap": {
            "required": ["template", "outputs"],
            "properties": {
              "outputs": { "minItems": 2, "description": "Must include at least user-data and meta-data" }
            }
          }
        }
      }
    }
  ]
}
```

**Schema design notes:**

- **`bootstrap.template`** is always required (non-null `string` with `minLength: 1`).
- **`bootstrap.outputs`** is optional; if omitted, the generator derives a single output path from the template name. For `cloud_init`, outputs are required (user-data + meta-data minimum).
- **`bootstrap.post_install`** lists additional script templates beyond the primary template. Required for `unattended_install` (Proxmox needs answer.toml + post-install script).
- **Mechanism-specific constraints** use JSONSchema `if/then` composition in `allOf` to enforce per-mechanism rules without duplicating the base schema.

---

## Device-Specific Patterns

### MikroTik (Reference: ADR 0057)

Full IaC pipeline: `Netinstall → Bootstrap .rsc → OpenTofu/Terraform → Ansible`

See detailed pattern: `adr/0083-analysis/MIKROTIK-IAC-PATTERN.md`

```yaml
initialization_contract:
  version: "1.0"
  mechanism: netinstall
  requirements:
    - name: netinstall_cli_installed
      check: command_exists
    - name: routeros_npk_available
      check: file_exists
      path: /srv/routeros/
    - name: installation_segment_access
      check: network_reachable
  bootstrap:
    template: templates/bootstrap/init-terraform.rsc.j2
  handover:
    provider: terraform-routeros/routeros
    checks:
      - type: api_reachable
        protocol: https
        port: 8443
      - type: credential_valid
        user: terraform
  post_handover:
    terraform:
      provider: terraform-routeros/routeros
      modules:
        - mikrotik-base
        - mikrotik-vlans
        - mikrotik-wireguard
        - mikrotik-routing
    ansible:
      collection: community.routeros
      playbooks:
        - mikrotik-postconfig
        - mikrotik-firewall
        - mikrotik-validate
        - mikrotik-backup
```

**Object ownership:**

| Owner | Objects |
| ----- | ------- |
| OpenTofu | bridge, VLAN, IP address, interface list, WireGuard, DHCP, routing, address-list |
| Ansible | firewall filter/nat/mangle, scripts, scheduler, backup jobs, hardening |

### Proxmox VE

```yaml
initialization_contract:
  version: "1.0"
  mechanism: unattended_install
  requirements:
    - name: proxmox_iso_available
      check: file_exists
    - name: answer_toml_rendered
      check: file_exists
    - name: installation_media_prepared
      check: manual_confirmation
  bootstrap:
    template: templates/bootstrap/answer.toml.j2
    post_install:
      - templates/bootstrap/post-install-minimal.sh.j2
  handover:
    provider: bpg/proxmox
    checks:
      - type: api_reachable
        protocol: https
        port: 8006
      - type: credential_valid
        user: root@pam
```

### Orange Pi 5 (SBC with cloud-init)

```yaml
initialization_contract:
  version: "1.0"
  mechanism: cloud_init
  requirements:
    - name: base_image_available
      check: file_exists
    - name: cloud_init_user_data_rendered
      check: file_exists
  bootstrap:
    template: templates/bootstrap/user-data.j2
    outputs:
      - bootstrap/{{ instance_id }}/user-data
      - bootstrap/{{ instance_id }}/meta-data
  handover:
    provider: ansible
    checks:
      - type: ssh_reachable
        port: 22
      - type: python_installed
```

### LXC Containers and Cloud VMs (Implicit Terraform-managed)

LXC containers and Cloud VMs do NOT declare `initialization_contract`. They are implicitly terraform-managed:

```yaml
# topology/object-modules/lxc/obj.proxmox.lxc.debian12.base.yaml
object: obj.proxmox.lxc.debian12.base
class_ref: class.compute.container.lxc

# NO initialization_contract field
# → Implicitly terraform-managed
# → Not included in INITIALIZATION-MANIFEST.yaml
# → Terraform creates container directly via Proxmox API
```

**Rationale:** These resources have no day-0 bootstrap phase. Terraform creates them directly through provider APIs. Adding an `initialization_contract` with `mechanism: terraform_managed` was redundant — absence of contract is sufficient to indicate Terraform management.

---

## Migration Path

### ADR 0080 Wave Dependency Mapping

ADR 0083 phases depend on ADR 0080 wave completion. **All waves (A–H) are now completed ✅** — no external blockers remain.

| ADR 0083 Phase | Required ADR 0080 Wave | Status |
|----------------|--------------------------|--------|
| Phase 1: Schema | Wave B (Kernel Foundations) | ✅ Completed |
| Phase 2: Generators | Wave D (Phase Annotation) | ✅ Completed |
| Phase 3: Device Support | Wave B | ✅ Completed |
| Phase 4: Orchestration | Wave E (Data Bus) | ✅ Completed |
| Phase 5: Assemble Integration | Wave F (Assemble Pluginization) | ✅ Completed |
| Phase 6: Documentation | Wave H (Hard Cutover) | ✅ Completed |

**All phases can start immediately.**

### Phase 1: Contract Definition

1. Create `schemas/initialization-contract.schema.json`
2. Add `initialization_contract` to object module schema
3. Update MikroTik object module with contract (already ADR 0057 compliant)
4. Document contract in CLAUDE.md

### Phase 2: Generator Enhancement

1. Update existing bootstrap generators to read contract from object modules
2. Add `base.generator.initialization_manifest` generator
3. Ensure all generators use projection-first pattern (ADR 0074)

### Phase 3: Add Missing Device Support

1. Refactor Proxmox `post-install.sh` into minimal bootstrap + day-1 config
2. Complete Orange Pi cloud-init template
3. Add LXC/Cloud VM bootstrap patterns

### Phase 4: Orchestration

1. Create `scripts/orchestration/deploy/init-node.py`
2. Implement device adapters for each mechanism
3. Add handover verification suite
4. Integration tests with mock devices

### Phase 5: Assemble Integration

1. Implement `base.assembler.bootstrap_secrets` plugin (requires ADR 0080 Wave F)
2. Secret injection from SOPS into `.work/native/bootstrap/`
3. Verify secret-leak guards in assemble verify phase

### Phase 6: Documentation

1. Create `docs/guides/NODE-INITIALIZATION.md`
2. Add Taskfile targets for initialization workflow
3. Update operator runbooks

---

## Consequences

### Positive

1. **Unified contract** across all device types
2. **Clear day-0/day-1 boundary** prevents configuration drift
3. **Topology-driven bootstrap** - artifacts generated from single source of truth
4. **Verifiable handover** - automated checks before Terraform/Ansible takeover
5. **Consistent with ADR 0057** - extends proven MikroTik pattern
6. **Plugin architecture alignment** - bootstrap generation uses v5 generators

### Negative and Trade-offs

1. **Additional complexity** - new schema, validator, orchestrator
2. **Device-specific adapters** - each mechanism needs implementation
3. **Hardware testing** - full E2E requires physical devices
4. **Migration effort** - existing scripts need decomposition
5. **Parallel paths** - current manual workflows must work during transition

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bootstrap scripts become complex | Maintenance burden | Strict day-0/day-1 boundary |
| Device-specific logic leaks to core | Plugin boundary violation | Contract validates templates in object modules |
| Secret handling inconsistency | Security risk | Enforce `.work/native/` for all secrets |
| Testing requires real hardware | CI gaps | Mock adapters for CI; hardware E2E as release gate |

---

## References

- ADR 0057: MikroTik Chateau Netinstall Bootstrap and Terraform Handover
- ADR 0072: Unified Secrets Management with SOPS and age
- ADR 0074: V5 Generator Architecture
- ADR 0080: Unified Build Pipeline, Stage-Phase Lifecycle
- ADR 0082: Plugin Module-Pack Composition and Index-First Discovery
- `adr/0083-analysis/GAP-ANALYSIS.md` - Current vs target state analysis
- `adr/0083-analysis/IMPLEMENTATION-PLAN.md` - Phased implementation plan
- `adr/0083-analysis/CUTOVER-CHECKLIST.md` - Migration gate checklist
- `adr/0083-analysis/MIKROTIK-IAC-PATTERN.md` - MikroTik full IaC pipeline pattern
- `adr/0083-analysis/PLUGIN-BOUNDARY-ANALYSIS.md` - Plugin level boundary proof
- `adr/0083-analysis/SECRETS-DATAFLOW.md` - Secret material lifecycle analysis
- `adr/0083-analysis/FMEA.md` - Failure mode and effects analysis per mechanism
- `adr/0083-analysis/TEST-MATRIX.md` - CI mock vs hardware E2E test matrix
- `adr/0083-analysis/STATE-MODEL.md` - Initialization state machine and concurrency
- `adr/0083-analysis/CUTOVER-IMPACT.md` - Runbook and Taskfile cutover impact
- `archive/migrated-and-archived/old_system/proxmox/scripts/proxmox-post-install.sh`
- `topology/object-modules/mikrotik/templates/bootstrap/init-terraform.rsc.j2`
- [terraform-routeros/routeros provider](https://registry.terraform.io/providers/terraform-routeros/routeros)
- [community.routeros Ansible collection](https://galaxy.ansible.com/community/routeros)

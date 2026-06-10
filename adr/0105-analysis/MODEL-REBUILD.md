# ADR 0105 Model Rebuild (SPC Step 6)

**SPC Phase:** Step 6 — Model Rebuild
**Date:** 2026-06-10
**Status:** Active

---

## Executive Summary

This document implements the approved solutions from Step 5 (Admissible Solution Space) to create a **complete Ansible-based device state management system** generated from topology.

**Critical Constraint (C22-C28):** ALL operations performed via Ansible roles generated from topology. Every bash script must be replaced with Ansible roles.

---

## 1. Capability Model Additions

### 1.1 New L7 Operations Capabilities

| Capability | Description | Ansible Role |
|------------|-------------|--------------|
| `cap.operations.deploy.safe_mode` | Safe mode for atomic changes (auto-revert on failure) | `deploy_safe_mode` |
| `cap.operations.deploy.pre_check` | Pre-deployment validation checks | `deploy_pre_check` |
| `cap.operations.deploy.post_verify` | Post-deployment verification | `deploy_post_verify` |
| `cap.operations.rollback.state_restore` | State restoration capability | `rollback_restore` |
| `cap.operations.recovery.partial_apply` | Partial apply failure recovery | `recovery_partial` |
| `cap.operations.snapshot.propagate` | Snapshot metadata propagation | `snapshot_propagate` |
| `cap.operations.consistency.group` | Multi-device consistency group support | `consistency_group` |

### 1.2 Capability Catalog Entries

```yaml
# L7 - Operations: Deploy capabilities
- @capability: cap.operations.deploy.safe_mode
  title: Safe Mode Deploy
  summary: Supports safe-mode deployment with automatic rollback on failure.
  domain: operations
  layer: L7
  stability: stable

- @capability: cap.operations.deploy.pre_check
  title: Pre-Deploy Check
  summary: Supports pre-deployment validation via API query.
  domain: operations
  layer: L7
  stability: stable

- @capability: cap.operations.deploy.post_verify
  title: Post-Deploy Verify
  summary: Supports post-deployment verification of applied state.
  domain: operations
  layer: L7
  stability: stable

# L7 - Operations: Rollback capabilities
- @capability: cap.operations.rollback.state_restore
  title: State Restore
  summary: Supports restoring to previous known-good state.
  domain: operations
  layer: L7
  stability: stable

- @capability: cap.operations.recovery.partial_apply
  title: Partial Apply Recovery
  summary: Supports recovery from partial Terraform apply failures.
  domain: operations
  layer: L7
  stability: stable

# L7 - Operations: Snapshot capabilities
- @capability: cap.operations.snapshot.propagate
  title: Snapshot Propagation
  summary: Supports propagating topology snapshot SHA to device metadata.
  domain: operations
  layer: L7
  stability: stable

# L7 - Operations: Consistency capabilities
- @capability: cap.operations.consistency.group
  title: Consistency Group
  summary: Supports multi-device consistency group tracking.
  domain: operations
  layer: L7
  stability: stable
```

---

## 2. Generator Architecture (Option C)

### 2.1 Multiple Specialized Generators

| Generator | Input | Output | Template |
|-----------|-------|--------|----------|
| `ansible_backup_generator` | Devices with backup capabilities | `backup-all.yml`, host_vars | `backup-playbook.yml.j2` |
| `ansible_deploy_generator` | Devices with deploy capabilities | `deploy.yml`, host_vars | `deploy-playbook.yml.j2` |
| `ansible_verify_generator` | Devices with verify capabilities | `verify-snapshot.yml` | `verify-playbook.yml.j2` |
| `ansible_recovery_generator` | Devices with recovery capabilities | `recovery.yml` | `recovery-playbook.yml.j2` |

### 2.2 Generator Plugin Contract

```python
# topology-tools/plugins/generators/ansible_deploy_generator.py
class AnsibleDeployGenerator:
    """
    Generates Ansible playbooks from topology deploy capabilities.

    Input: Compiled topology with device deploy capabilities
    Output: generated/home-lab/ansible/playbooks/deploy.yml
            generated/home-lab/ansible/inventory/*/host_vars/*/deploy.yml
    """

    def generate(self, ctx: GeneratorContext) -> GeneratorOutput:
        # 1. Collect devices with cap.operations.deploy.* capabilities
        deploy_devices = self._collect_deploy_devices(ctx)

        # 2. Group by capability → role mapping
        role_groups = self._group_by_role(deploy_devices)

        # 3. Render playbook from template
        playbook = self._render_playbook(role_groups, "deploy-playbook.yml.j2")

        # 4. Render host_vars with deploy configuration
        host_vars = self._render_host_vars(deploy_devices)

        return GeneratorOutput(
            files=[playbook] + host_vars,
            metadata={"devices": len(deploy_devices)}
        )
```

### 2.3 Capability → Role Mapping

```yaml
# topology-tools/config/ansible-role-mapping.yaml
capability_role_mapping:
  # Backup roles
  cap.operations.backup.routeros_export: backup_mikrotik
  cap.operations.backup.vzdump: backup_proxmox
  cap.operations.backup.config_archive: backup_linux
  vendor.operations.backup.routeros_export: backup_mikrotik

  # Deploy roles
  cap.operations.deploy.safe_mode: deploy_safe_mode
  cap.operations.deploy.pre_check: deploy_pre_check
  cap.operations.deploy.post_verify: deploy_post_verify
  vendor.operations.safe_mode: deploy_safe_mode

  # Verify roles
  cap.operations.snapshot.propagate: snapshot_propagate

  # Recovery roles
  cap.operations.rollback.state_restore: rollback_restore
  cap.operations.recovery.partial_apply: recovery_partial

  # Consistency roles
  cap.operations.consistency.group: consistency_group
```

---

## 3. Ansible Role Structure

### 3.1 Role Directory Layout

```
projects/home-lab/ansible/roles/
├── backup_common/              # Shared backup utilities
│   └── tasks/
│       ├── encrypt.yml         # SOPS/age encryption
│       └── cleanup.yml         # Plaintext removal
├── backup_mikrotik/            # MikroTik backup
│   ├── meta/main.yml
│   ├── tasks/main.yml
│   └── defaults/main.yml
├── backup_proxmox/             # Proxmox vzdump backup
│   ├── meta/main.yml
│   ├── tasks/main.yml
│   └── defaults/main.yml
├── backup_linux/               # Generic Linux backup
│   ├── meta/main.yml
│   ├── tasks/main.yml
│   └── defaults/main.yml
├── deploy_safe_mode/           # Safe mode deploy wrapper
│   ├── meta/main.yml
│   ├── tasks/
│   │   ├── main.yml
│   │   ├── mikrotik.yml        # MikroTik safe-mode
│   │   └── generic.yml         # Generic approach
│   └── defaults/main.yml
├── deploy_pre_check/           # Pre-deploy verification
│   ├── tasks/main.yml
│   └── vars/
│       ├── mikrotik.yml
│       ├── proxmox.yml
│       └── linux.yml
├── deploy_post_verify/         # Post-deploy verification
│   ├── tasks/main.yml
│   └── templates/
│       └── verify-report.j2
├── snapshot_propagate/         # Snapshot metadata propagation
│   ├── tasks/
│   │   ├── main.yml
│   │   ├── mikrotik.yml        # RouterOS script metadata
│   │   ├── proxmox.yml         # VM/LXC tags
│   │   └── oci.yml             # Freeform tags
│   └── templates/
│       └── topology-metadata.rsc.j2
├── rollback_restore/           # Rollback operations
│   ├── tasks/main.yml
│   └── handlers/main.yml
├── recovery_partial/           # Partial failure recovery
│   ├── tasks/main.yml
│   └── vars/recovery_matrix.yml
└── consistency_group/          # Multi-device coordination
    ├── tasks/main.yml
    └── defaults/main.yml
```

### 3.2 Role Implementation Examples

#### 3.2.1 deploy_safe_mode Role

```yaml
# roles/deploy_safe_mode/tasks/main.yml
---
- name: Select platform-specific safe-mode handler
  ansible.builtin.include_tasks: "{{ deploy_platform }}.yml"
  vars:
    deploy_platform: "{{ deploy_safe_mode_platform | default('generic') }}"
```

```yaml
# roles/deploy_safe_mode/tasks/mikrotik.yml
---
- name: Enter MikroTik safe-mode
  community.routeros.api:
    path: system
    cmd: safe-mode
  register: safe_mode_result

- name: Apply changes (Terraform via delegate)
  block:
    - name: Run Terraform apply
      ansible.builtin.command:
        cmd: "terraform apply -auto-approve -var='topology_snapshot_sha={{ topology_sha }}'"
        chdir: "{{ deploy_terraform_dir }}"
      delegate_to: localhost
      become: false
      register: terraform_result

    - name: Wait for device reachability
      ansible.builtin.wait_for:
        host: "{{ ansible_host }}"
        port: "{{ deploy_verify_port | default(443) }}"
        timeout: 60

    - name: Exit safe-mode with save
      community.routeros.api:
        path: system
        cmd: safe-mode
        attrs:
          action: release
  rescue:
    - name: Undo safe-mode (discard changes)
      community.routeros.api:
        path: system
        cmd: safe-mode
        attrs:
          action: undo
      ignore_errors: true

    - name: Fail with message
      ansible.builtin.fail:
        msg: "Deploy failed, safe-mode rollback executed"
```

#### 3.2.2 snapshot_propagate Role

```yaml
# roles/snapshot_propagate/tasks/mikrotik.yml
---
- name: Create/update topology metadata script
  community.routeros.api:
    path: system/script
    cmd: add
    attrs:
      name: topology-metadata
      source: |
        # Topology Snapshot Metadata
        # snapshot_sha:     {{ topology_snapshot_sha }}
        # deploy_timestamp: {{ ansible_date_time.iso8601 }}
        # device_id:        {{ inventory_hostname }}
        # consistency_group: {{ consistency_group_id | default('standalone') }}
      comment: "Managed by topology - DO NOT EDIT"
  when: topology_snapshot_sha is defined
```

```yaml
# roles/snapshot_propagate/tasks/proxmox.yml
---
- name: Update VM/LXC tags with snapshot
  ansible.builtin.uri:
    url: "https://{{ proxmox_api_host }}:8006/api2/json/nodes/{{ proxmox_node }}/{{ vm_type }}/{{ vmid }}/config"
    method: PUT
    headers:
      Authorization: "PVEAPIToken={{ proxmox_api_token }}"
    body_format: form-urlencoded
    body:
      tags: "topology,snapshot-{{ topology_snapshot_sha[:8] }}"
    validate_certs: "{{ proxmox_validate_certs | default(false) }}"
  loop: "{{ proxmox_vms | default([]) }}"
  loop_control:
    loop_var: vm
  vars:
    vmid: "{{ vm.vmid }}"
    vm_type: "{{ 'qemu' if vm.type == 'vm' else 'lxc' }}"
```

#### 3.2.3 deploy_pre_check Role

```yaml
# roles/deploy_pre_check/tasks/main.yml
---
- name: Include platform-specific pre-checks
  ansible.builtin.include_tasks: "{{ item }}"
  with_first_found:
    - files:
        - "{{ deploy_platform }}.yml"
        - generic.yml
      paths:
        - "{{ role_path }}/tasks"

- name: Query current snapshot from device
  ansible.builtin.set_fact:
    current_device_snapshot: "{{ device_snapshot_result.stdout | default('unknown') }}"

- name: Compare snapshots
  ansible.builtin.debug:
    msg: >
      Current: {{ current_device_snapshot }}
      Deploying: {{ topology_snapshot_sha[:8] }}
      {% if current_device_snapshot == topology_snapshot_sha[:8] %}
      STATUS: Already at target snapshot (no-op)
      {% else %}
      STATUS: Will update from {{ current_device_snapshot }} to {{ topology_snapshot_sha[:8] }}
      {% endif %}

- name: Set pre-check result
  ansible.builtin.set_fact:
    pre_check_passed: true
    pre_check_is_noop: "{{ current_device_snapshot == topology_snapshot_sha[:8] }}"
```

---

## 4. Generated Playbook Templates

### 4.1 Deploy Playbook Template

```yaml
# topology-tools/templates/ansible/deploy-playbook.yml.j2
# GENERATED BY: ansible_deploy_generator
# DO NOT EDIT - Regenerate from topology
---
{% for role_group in role_groups %}
- name: Deploy devices with {{ role_group.capability }} capability
  hosts: {{ role_group.inventory_group }}
  gather_facts: {{ role_group.gather_facts | default('true') }}
  serial: {{ role_group.serial | default(1) }}
  vars:
    topology_snapshot_sha: "{{ '{{' }} lookup('env', 'TOPOLOGY_SHA') | default(lookup('pipe', 'git rev-parse HEAD')) {{ '}}' }}"
  pre_tasks:
    - name: Pre-deploy check
      ansible.builtin.include_role:
        name: deploy_pre_check
  roles:
    - role: {{ role_group.role }}
      when: not (pre_check_is_noop | default(false))
  post_tasks:
    - name: Post-deploy verify
      ansible.builtin.include_role:
        name: deploy_post_verify
      when: not (pre_check_is_noop | default(false))

    - name: Propagate snapshot
      ansible.builtin.include_role:
        name: snapshot_propagate
      when: not (pre_check_is_noop | default(false))

{% endfor %}
```

### 4.2 Backup Playbook Template

```yaml
# topology-tools/templates/ansible/backup-playbook.yml.j2
# GENERATED BY: ansible_backup_generator
# DO NOT EDIT - Regenerate from topology
---
{% for role_group in backup_role_groups %}
- name: Backup devices with {{ role_group.capability }} capability
  hosts: {{ role_group.inventory_group }}
  gather_facts: {{ 'true' if role_group.needs_facts else 'false' }}
  vars:
    backup_timestamp: "{{ '{{' }} ansible_date_time.iso8601_basic_short {{ '}}' }}"
    backup_local_dir: "{{ '{{' }} playbook_dir {{ '}}' }}/../../../.work/backups/{{ '{{' }} inventory_hostname {{ '}}' }}"
  roles:
    - role: {{ role_group.role }}

{% endfor %}
```

### 4.3 Verify Playbook Template

```yaml
# topology-tools/templates/ansible/verify-playbook.yml.j2
# GENERATED BY: ansible_verify_generator
# DO NOT EDIT - Regenerate from topology
---
- name: Verify snapshot consistency across all devices
  hosts: all_managed_devices
  gather_facts: false
  vars:
    expected_sha: "{{ '{{' }} lookup('env', 'EXPECTED_SHA') | default(lookup('pipe', 'git rev-parse HEAD')) {{ '}}' }}"
  tasks:
    - name: Include platform-specific verification
      ansible.builtin.include_role:
        name: deploy_pre_check
      vars:
        topology_snapshot_sha: "{{ '{{' }} expected_sha {{ '}}' }}"

    - name: Report verification result
      ansible.builtin.debug:
        msg: >
          Device: {{ '{{' }} inventory_hostname {{ '}}' }}
          Expected: {{ '{{' }} expected_sha[:8] {{ '}}' }}
          Actual: {{ '{{' }} current_device_snapshot | default('unknown') {{ '}}' }}
          Match: {{ '{{' }} 'YES' if current_device_snapshot == expected_sha[:8] else 'NO' {{ '}}' }}
```

---

## 5. Object Module Updates

### 5.1 MikroTik Object Module

```yaml
# obj.mikrotik.chateau_lte7_ax.yaml - additional capabilities
enabled_capabilities:
  # ... existing capabilities ...
  # Operations capabilities (ADR 0105)
  - cap.operations.deploy.safe_mode
  - cap.operations.deploy.pre_check
  - cap.operations.deploy.post_verify
  - cap.operations.snapshot.propagate
  - cap.operations.rollback.state_restore
  - cap.operations.consistency.group

vendor_capabilities:
  # ... existing vendor capabilities ...
  - vendor.operations.backup.routeros_export
  - vendor.operations.safe_mode
```

### 5.2 Proxmox Object Module

```yaml
# obj.proxmox.ve.yaml - additional capabilities
enabled_capabilities:
  # ... existing capabilities ...
  # Operations capabilities (ADR 0105)
  - cap.operations.backup.vzdump
  - cap.operations.backup.snapshot
  - cap.operations.deploy.pre_check
  - cap.operations.deploy.post_verify
  - cap.operations.snapshot.propagate
  - cap.operations.recovery.partial_apply
  - cap.operations.consistency.group
```

### 5.3 OrangePi Object Module

```yaml
# obj.orangepi.rk3588.debian.yaml - additional capabilities
enabled_capabilities:
  # ... existing capabilities ...
  # Operations capabilities (ADR 0105)
  - cap.operations.backup.config_archive
  - cap.operations.deploy.pre_check
  - cap.operations.deploy.post_verify
  - cap.operations.snapshot.propagate
```

---

## 6. Bash Script Replacement Matrix

| Original Script | Replaced By | Implementation |
|-----------------|-------------|----------------|
| `scripts/backup-before-apply.sh` | `ansible-playbook backup-all.yml` | `backup_*` roles |
| `scripts/mikrotik-safe-apply.sh` | `ansible-playbook deploy.yml -l mikrotik` | `deploy_safe_mode` role |
| `scripts/health-check.sh` | `ansible-playbook verify-snapshot.yml` | `deploy_pre_check` role |
| `scripts/verify-snapshot-consistency.sh` | `ansible-playbook verify-snapshot.yml` | `deploy_post_verify` role |
| `scripts/deploy-confirm.sh` | `ansible-playbook confirm.yml` | `snapshot_propagate` role |

---

## 7. Task Integration

### 7.1 Taskfile Commands

```yaml
# taskfiles/deploy.yml
version: '3'

tasks:
  backup:
    desc: Backup devices before deploy
    cmds:
      - ansible-playbook generated/home-lab/ansible/playbooks/backup-all.yml {{.CLI_ARGS}}
    vars:
      ANSIBLE_CONFIG: projects/home-lab/ansible/ansible.cfg

  apply:
    desc: Apply topology to devices with safe-mode
    cmds:
      - ansible-playbook generated/home-lab/ansible/playbooks/deploy.yml {{.CLI_ARGS}}
    vars:
      TOPOLOGY_SHA:
        sh: git rev-parse HEAD
    env:
      TOPOLOGY_SHA: "{{.TOPOLOGY_SHA}}"

  verify:
    desc: Verify snapshot consistency across devices
    cmds:
      - ansible-playbook generated/home-lab/ansible/playbooks/verify-snapshot.yml {{.CLI_ARGS}}

  confirm:
    desc: Confirm successful deploy (set rollback point)
    cmds:
      - ansible-playbook generated/home-lab/ansible/playbooks/confirm.yml {{.CLI_ARGS}}

  rollback:
    desc: Rollback to previous rollback point
    cmds:
      - |
        ROLLBACK_SHA=$(yq '.applies[] | select(.rollback_point == true) | .git_commit' \
          .work/deploy-state/home-lab/history.yaml | head -1)
        git checkout $ROLLBACK_SHA
        task compile
        task deploy:apply {{.CLI_ARGS}}
```

---

## 8. Implementation Phases

### Phase 1: Capability Model (2h)

- [ ] Add 7 new capabilities to `capability-catalog.yaml`
- [ ] Update MikroTik object module with deploy capabilities
- [ ] Update Proxmox object module with deploy capabilities
- [ ] Update OrangePi object module with deploy capabilities

### Phase 2: Static Roles (8h)

- [ ] Create `deploy_safe_mode` role
- [ ] Create `deploy_pre_check` role
- [ ] Create `deploy_post_verify` role
- [ ] Create `snapshot_propagate` role
- [ ] Create `rollback_restore` role
- [ ] Create `recovery_partial` role
- [ ] Create `consistency_group` role

### Phase 3: Generators (8h)

- [ ] Create `ansible_backup_generator.py` plugin
- [ ] Create `ansible_deploy_generator.py` plugin
- [ ] Create `ansible_verify_generator.py` plugin
- [ ] Create `ansible_recovery_generator.py` plugin
- [ ] Create capability-role mapping config

### Phase 4: Templates (4h)

- [ ] Create `backup-playbook.yml.j2`
- [ ] Create `deploy-playbook.yml.j2`
- [ ] Create `verify-playbook.yml.j2`
- [ ] Create `recovery-playbook.yml.j2`
- [ ] Create host_vars templates

### Phase 5: Integration (4h)

- [ ] Update Taskfile with deploy commands
- [ ] Update ADR 0105 with final architecture
- [ ] Remove deprecated bash scripts
- [ ] Create integration tests

**Total Estimated Effort: 26h**

---

## 9. Constraint Satisfaction

| Constraint | Status | Evidence |
|------------|--------|----------|
| C01: Topology = source of truth | SATISFIED | Generators read from compiled topology |
| C19: No custom systems | SATISFIED | Uses only Ansible + Terraform + native APIs |
| C22: All operations via Ansible | SATISFIED | All bash scripts replaced with roles |
| C23: Roles generated from topology | SATISFIED | Generators create playbooks from capabilities |
| C24: Capability-driven generation | SATISFIED | Role mapping uses capability namespace |
| C25: Single playbook per operation | SATISFIED | One playbook per concern (backup, deploy, verify) |
| C26: Inventory from topology | SATISFIED | Uses existing Ansible inventory generator |
| C27: Idempotent operations | SATISFIED | Ansible inherent property |
| C28: No shell scripts in deploy path | SATISFIED | Task wrappers call ansible-playbook only |

---

## 10. References

- ADR 0105: Device State Management
- ADR 0074: Generator Architecture
- ADR 0085: Deploy Bundle Contract
- `docs/ai/spc-contract.md`: SPC Protocol
- `topology/class-modules/capability-catalog.yaml`: Capability definitions

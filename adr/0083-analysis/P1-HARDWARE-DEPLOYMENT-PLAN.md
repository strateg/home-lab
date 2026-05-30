# P1: Hardware Deployment Unlock — Detailed Plan

**Created:** 2026-05-28
**Status:** In Progress
**Priority:** P1 (Critical Path)
**Available Hardware:** OrangePi 5, GL.iNet Slate AX

---

## Executive Summary

Unlock hardware deployment capability by completing adapter implementations and validating E2E on available devices. MikroTik/Proxmox deferred until hardware available.

## Current State

| Device | Object Module | init_contract | Templates | Adapter | Readiness |
|--------|---------------|---------------|-----------|---------|-----------|
| **OrangePi 5** | obj.orangepi.rk3588.debian | cloud_init | user-data.j2, meta-data.j2 | CloudInitAdapter (E9730) | **70%** |
| **GL.iNet Slate** | obj.glinet.slate_ax1800 | **MISSING** | **MISSING** | AnsibleBootstrapAdapter (E9730) | **20%** |
| MikroTik Chateau | obj.mikrotik.chateau_lte7_ax | netinstall | init-terraform.rsc.j2 | NetinstallAdapter | 90% (no HW) |
| Proxmox/Gamayun | obj.proxmox.ve | unattended_install | answer.toml.j2 | UnattendedInstallAdapter (E9730) | 60% (no HW) |

---

## Wave A: OrangePi 5 E2E Validation

**Target:** First successful E2E bootstrap on real hardware.

### A.1 Create Instance Definition

- [ ] Create `projects/home-lab/topology/instances/devices/sbc-orangepi5.yaml`

```yaml
@instance: sbc-orangepi5
@extends: obj.orangepi.rk3588.debian
@group: devices
@version: 1.0.0
source_id: sbc-orangepi5
status: mapped
notes: Orange Pi 5 SBC for Docker workloads
firmware_ref: inst.firmware.uboot.generic.arm64
os_refs:
  - inst.os.debian.12.arm64.edge
power:
  source_ref: pdu-rack
  max_watts: 25
```

### A.2 Update user-data Template

- [ ] Update `topology/object-modules/orangepi/templates/bootstrap/user-data.example.j2`
- [ ] Replace `<TODO_SSH_PUBLIC_KEY>` with template variable
- [ ] Add DAY0_COMPLETE marker for handover detection

**Target template:**
```yaml
#cloud-config
hostname: {{ instance_id }}
users:
  - default
  - name: {{ operator_user | default('opi') }}
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - {{ ssh_public_key }}
package_update: true
packages:
  - curl
  - git
  - python3
  - python3-pip
runcmd:
  - echo "DAY0_COMPLETE=$(date -Iseconds)" > /root/.day0_complete
```

### A.3 Implement CloudInitAdapter.execute()

- [ ] Update `scripts/orchestration/deploy/adapters/cloud_init.py`
- [ ] Return `PENDING_OPERATOR` status with instructions
- [ ] Add helper functions `_find_artifact()`, `_get_target_host()`

**Implementation:**
```python
def execute(self, node: dict[str, Any], context: AdapterContext) -> BootstrapResult:
    artifacts = _artifact_paths(node)
    user_data = _find_artifact(artifacts, "user-data", context.bundle_path)
    meta_data = _find_artifact(artifacts, "meta-data", context.bundle_path)

    if not user_data:
        return BootstrapResult(status=AdapterStatus.FAILED,
            message="cloud-init user-data missing from bundle", error_code="E9763")
    if not meta_data:
        return BootstrapResult(status=AdapterStatus.FAILED,
            message="cloud-init meta-data missing from bundle", error_code="E9764")

    return BootstrapResult(
        status=AdapterStatus.PENDING_OPERATOR,
        message="Cloud-init files ready. Flash to SD card boot partition.",
        details={
            "user_data_path": str(user_data),
            "meta_data_path": str(meta_data),
            "instructions": [
                "1. Mount SD card boot partition (FAT32)",
                "2. Copy user-data to boot partition root",
                "3. Copy meta-data to boot partition root",
                "4. Unmount and boot Orange Pi with SD card",
                "5. cloud-init executes on first boot",
                "6. Run --verify-only to confirm SSH handover",
            ],
        },
    )
```

### A.4 Hardware Test Protocol

| Step | Command | Expected Result |
|------|---------|-----------------|
| 1 | `task compile` | OrangePi bootstrap files generated |
| 2 | `task bundle:create` | Bundle contains cloud-init files |
| 3 | `task deploy:init-node-run -- NODE=sbc-orangepi5` | Status: PENDING_OPERATOR |
| 4 | Manual: flash SD card | user-data + meta-data on boot partition |
| 5 | Boot OrangePi | cloud-init executes |
| 6 | `task deploy:init-node-verify -- NODE=sbc-orangepi5` | SSH reachable, state -> verified |

### A.5 Wave A Gate Criteria

- [ ] Instance `sbc-orangepi5` exists and compiles without errors
- [ ] user-data template renders with real SSH key
- [ ] CloudInitAdapter.execute() returns PENDING_OPERATOR (not E9730)
- [ ] SD card prepared with cloud-init files
- [ ] OrangePi boots and cloud-init runs successfully
- [ ] SSH access confirmed on target IP
- [ ] Handover check passes (state transitions to `verified`)

---

## Wave B: GL.iNet Slate Bootstrap

**Target:** Add initialization contract and enable ansible-based bootstrap.

### B.1 Add initialization_contract to Object Module

- [ ] Update `topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml`

**Add after `software_contract`:**
```yaml
initialization_contract:
  version: 1.0.0
  mechanism: ansible_bootstrap
  bootstrap:
    template: bootstrap/configure.yml.j2
    outputs:
      playbook: configure-glinet.yml
  requirements:
    - type: network
      name: ssh_access
      required: true
      description: Factory default SSH must be accessible (192.168.8.1:22, root/goodlife)
    - type: tool
      name: ansible
      required: true
      description: Ansible installed on operator workstation
  handover:
    checks:
      - type: ssh_reachable
        target: '{{ node.management_ip }}'
        port: 22
      - type: http_reachable
        target: '{{ node.management_ip }}'
        port: 80
    retry:
      max_attempts: 5
      backoff_seconds: 10
      timeout_seconds: 120
```

### B.2 Create Bootstrap Template

- [ ] Create `topology/object-modules/glinet/templates/bootstrap/configure.yml.j2`

```yaml
---
- name: GL.iNet Slate AX initial configuration
  hosts: "{{ target_host }}"
  gather_facts: false
  vars:
    ansible_user: root
    ansible_password: "{{ factory_password | default('goodlife') }}"

  tasks:
    - name: Set hostname
      raw: uci set system.@system[0].hostname='{{ instance_id }}'

    - name: Add SSH authorized key
      raw: |
        mkdir -p /etc/dropbear
        echo '{{ ssh_public_key }}' >> /etc/dropbear/authorized_keys

    - name: Commit changes
      raw: uci commit && /etc/init.d/system reload

    - name: Signal day-0 complete
      raw: echo "DAY0_COMPLETE=$(date -Iseconds)" > /root/.day0_complete
```

### B.3 Create plugins.yaml for GL.iNet

- [ ] Create `topology/object-modules/glinet/plugins.yaml`

```yaml
plugins:
  - id: obj.glinet.bootstrap
    family: generators
    stage: generate
    order: 500
    plugin_file: plugins/generators/bootstrap_glinet_generator.py
    plugin_class: BootstrapGlinetGenerator
```

### B.4 Implement AnsibleBootstrapAdapter.execute()

- [ ] Update `scripts/orchestration/deploy/adapters/ansible_bootstrap.py`

```python
def execute(self, node: dict[str, Any], context: AdapterContext) -> BootstrapResult:
    artifacts = _artifact_paths(node)
    playbook = _find_playbook(artifacts, context.bundle_path)

    if not playbook:
        return BootstrapResult(status=AdapterStatus.FAILED,
            message="Ansible playbook missing from bundle", error_code="E9765")

    if not shutil.which("ansible-playbook"):
        return BootstrapResult(status=AdapterStatus.FAILED,
            message="ansible-playbook not found in PATH", error_code="E9766")

    target_host = _get_target_host(node)
    if not target_host:
        return BootstrapResult(status=AdapterStatus.FAILED,
            message="Cannot determine target host for ansible", error_code="E9767")

    timeout_s = _env_int("INIT_NODE_ANSIBLE_TIMEOUT_SECONDS", default=300)
    cmd = ["ansible-playbook", "-i", f"{target_host},", str(playbook),
           "-e", f"target_host={target_host}"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return BootstrapResult(status=AdapterStatus.FAILED,
            message=f"Ansible playbook timed out after {timeout_s}s", error_code="E9768")

    if result.returncode == 0:
        return BootstrapResult(status=AdapterStatus.SUCCESS,
            message="Ansible bootstrap completed successfully",
            details={"playbook": str(playbook), "target": target_host})

    return BootstrapResult(status=AdapterStatus.FAILED,
        message=f"Ansible playbook failed with exit code {result.returncode}",
        error_code="E9769",
        details={"stdout": result.stdout, "stderr": result.stderr})


def _find_playbook(artifacts: list[Path], bundle_path: Path) -> Path | None:
    for rel in artifacts:
        if rel.suffix in {".yml", ".yaml"} and "playbook" in rel.name.lower() or "configure" in rel.name.lower():
            path = (bundle_path / rel).resolve()
            if path.exists():
                return path
    for rel in artifacts:
        if rel.suffix in {".yml", ".yaml"}:
            path = (bundle_path / rel).resolve()
            if path.exists():
                return path
    return None


def _get_target_host(node: dict[str, Any]) -> str:
    mgmt_ip = node.get("management_ip") or node.get("ip_address")
    if mgmt_ip:
        return str(mgmt_ip).strip()
    return os.environ.get("INIT_NODE_TARGET_HOST", "").strip()


def _env_int(key: str, *, default: int) -> int:
    raw = os.environ.get(key, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default
```

### B.5 Wave B Gate Criteria

- [ ] initialization_contract added to GL.iNet object module
- [ ] Bootstrap template created and validates
- [ ] plugins.yaml created for GL.iNet generator
- [ ] AnsibleBootstrapAdapter.execute() implemented (not E9730)
- [ ] Instance `rtr-slate` compiles without errors
- [ ] Bundle contains generated playbook
- [ ] GL.iNet configurable via generated playbook
- [ ] SSH and HTTP handover checks pass

---

## Wave C: Integration Testing

### Unit Tests (Mock)

| Test ID | Adapter | Scope |
|---------|---------|-------|
| T-CI-01 | CloudInitAdapter | preflight checks |
| T-CI-02 | CloudInitAdapter | execute -> PENDING_OPERATOR |
| T-CI-03 | CloudInitAdapter | handover SSH check |
| T-AB-01 | AnsibleBootstrapAdapter | preflight checks |
| T-AB-02 | AnsibleBootstrapAdapter | execute with mock ansible |
| T-AB-03 | AnsibleBootstrapAdapter | handover SSH+HTTP check |

### E2E Tests (Real Hardware)

| Test ID | Device | Scope |
|---------|--------|-------|
| T-OPI-E2E | OrangePi 5 | Full bootstrap cycle |
| T-GL-E2E | GL.iNet Slate | Full bootstrap cycle |

---

## Wave D: Documentation Update

- [ ] Update `docs/guides/NODE-INITIALIZATION.md` with OrangePi/GL.iNet procedures
- [ ] Update `CLAUDE.md` with new adapter status
- [ ] Add troubleshooting section for cloud-init issues
- [ ] Add troubleshooting section for ansible/OpenWRT issues

---

## Error Codes Registry

| Code | Adapter | Message |
|------|---------|---------|
| E9730 | * | Generic "not implemented" placeholder |
| E9763 | CloudInit | user-data missing from bundle |
| E9764 | CloudInit | meta-data missing from bundle |
| E9765 | AnsibleBootstrap | playbook missing from bundle |
| E9766 | AnsibleBootstrap | ansible-playbook not in PATH |
| E9767 | AnsibleBootstrap | cannot determine target host |
| E9768 | AnsibleBootstrap | playbook timeout |
| E9769 | AnsibleBootstrap | playbook execution failed |

---

## Progress Tracking

### Wave A Progress
- [ ] A.1 Instance definition created
- [ ] A.2 user-data template updated
- [ ] A.3 CloudInitAdapter.execute() implemented
- [ ] A.4 Hardware test completed
- [ ] A.5 All gate criteria passed

### Wave B Progress
- [ ] B.1 initialization_contract added
- [ ] B.2 Bootstrap template created
- [ ] B.3 plugins.yaml created
- [ ] B.4 AnsibleBootstrapAdapter.execute() implemented
- [ ] B.5 All gate criteria passed

### Wave C Progress
- [ ] Unit tests passing
- [ ] E2E tests passing

### Wave D Progress
- [ ] Documentation updated

---

## Session Log

| Date | Session | Progress |
|------|---------|----------|
| 2026-05-28 | Initial | Plan created, analyzed adapter status |

---

## References

- ADR 0083: Node Initialization Contract
- ADR 0084: Cross-Platform Dev / Linux Deploy Plane
- ADR 0085: Deploy Bundle Contract
- `adr/0083-analysis/IMPLEMENTATION-PLAN.md`: Full 8-phase implementation plan
- `scripts/orchestration/deploy/adapters/`: Adapter implementations

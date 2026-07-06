# ADR 0104: Ansible Role Generation from Topology

- Status: Implemented
- Date: 2026-06-09
- Implemented: 2026-06-09

## Context

### Problem Statement

The current Ansible infrastructure has a **data duplication problem**. Configuration data exists in two places:

1. **Topology definitions** (source of truth):
   - `inst.tunnel.wg-home-to-oci.yaml` - WireGuard tunnel config
   - `inst.vlan.vpn_germany.yaml` - VLAN definitions
   - `vps-oracle-frankfurt.yaml` - VPS instance with gateway config

2. **Ansible artifacts** (manual duplication):
   - `ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml`
   - `ansible/playbooks/vpn-gateway.yml`

This duplication violates the infrastructure-as-data principle and creates drift risk.

### Evidence of Duplication

| Data Element | Topology Location | Ansible Location | Drift Risk |
|--------------|-------------------|------------------|------------|
| `tunnel_ip: 10.100.0.2/30` | `inst.tunnel...endpoint_b.tunnel_ip` | `host_vars/...wireguard.tunnel_ip` | HIGH |
| `listen_port: 51820` | `inst.tunnel...endpoint_b.listen_port` | `host_vars/...wireguard.listen_port` | HIGH |
| `allowed_ips` | `inst.tunnel...endpoint_a.allowed_ips` | `host_vars/...wireguard_peers[].allowed_ips` | HIGH |
| `192.168.55.0/24` | `inst.vlan.vpn_germany.cidr` | `host_vars/...routed_networks[].network` | HIGH |
| iptables rules | `vps-oracle-frankfurt.yaml` | `host_vars/...iptables_*_rules` | CRITICAL |

### Constraints

1. Existing generator architecture (ADR 0074) must be followed
2. Plugin execution model (ADR 0086, 0097) must be respected
3. Secrets must remain external (SOPS-encrypted)
4. Ansible roles contain operational logic that shouldn't be generated
5. Generated artifacts go to `generated/<project>/` (ADR 0075)

## Decision

### 1. Implement AnsibleRoleGenerator Plugin

Create a new generator plugin that produces Ansible configuration from topology:

```
topology-tools/plugins/generators/ansible_role_generator.py
```

**Plugin Manifest:**
```yaml
- id: base.generator.ansible_role
  family: generators
  stage: generate
  order: 235  # After ansible_inventory (230)
  execution_mode: subinterpreter
  depends_on:
    - base.generator.ansible_inventory
  consumes:
    - from_plugin: base.generator.ansible_inventory
      keys: [ansible_inventory_dir]
  publishes:
    - ansible_role_host_vars
    - ansible_role_playbooks
```

### 2. Separation of Generated vs Static Artifacts

| Artifact Type | Status | Location |
|---------------|--------|----------|
| Role tasks | STATIC | `projects/home-lab/ansible/roles/*/tasks/` |
| Role handlers | STATIC | `projects/home-lab/ansible/roles/*/handlers/` |
| Role templates | STATIC | `projects/home-lab/ansible/roles/*/templates/` |
| Role defaults | STATIC | `projects/home-lab/ansible/roles/*/defaults/` |
| Host variables | **GENERATED** | `generated/home-lab/ansible/inventory/*/host_vars/` |
| Group variables | **GENERATED** | `generated/home-lab/ansible/inventory/*/group_vars/` |
| Playbooks | **GENERATED** | `generated/home-lab/ansible/playbooks/` |

**Rationale:** Roles contain Ansible-specific operational logic (task ordering, handlers, conditionals). Host/group variables contain topology-derived data. This separation keeps roles reusable while eliminating data duplication.

### 3. Capability-Based Role Triggering

Roles are generated based on capability markers in topology:

```yaml
# In vps-oracle-frankfurt.yaml
enabled_capabilities:
  - cap.compute.runtime.container_host
  - cap.compute.workload.linux_base
  - cap.network.vpn_gateway  # Triggers wireguard_gateway role
```

The generator scans for capability markers and generates appropriate host_vars:

**Capability → Role Mapping:**

| Capability | Ansible Role | Template |
|------------|--------------|----------|
| `cap.network.vpn_gateway` | `wireguard_gateway` | `wireguard_gateway.yml.j2` |
| `cap.compute.runtime.container_host` | `docker_host` | (future) |
| `cap.monitoring.prometheus_target` | `prometheus_node_exporter` | (future) |

**Projection Builder:**

```python
from typing import Any

CAPABILITY_ROLE_MAP = {
    "cap.network.vpn_gateway": "wireguard_gateway",
    # Future capabilities added here
}

def build_ansible_role_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build projection for Ansible role-based host_vars generation.

    Scans instances for capability markers and yields role-specific
    variable sets for each matching instance.

    Returns:
        dict with 'role_assignments' list and 'counts' summary.
    """
    instances = compiled_json.get("instances", {})
    role_assignments: list[dict[str, Any]] = []

    for group_name, group_instances in instances.items():
        if not isinstance(group_instances, list):
            continue
        for inst in group_instances:
            if not isinstance(inst, dict):
                continue
            instance_id = inst.get("instance_id", "")
            capabilities = inst.get("enabled_capabilities", [])

            for cap in capabilities:
                if cap in CAPABILITY_ROLE_MAP:
                    role_assignments.append({
                        "instance_id": instance_id,
                        "capability": cap,
                        "role": CAPABILITY_ROLE_MAP[cap],
                        "instance_data": inst,
                    })

    return {
        "role_assignments": role_assignments,
        "counts": {"total_assignments": len(role_assignments)},
    }
```

### 4. Template-Based Generation

Host variables are generated via Jinja2 templates:

```
topology-tools/templates/ansible/
├── host_vars/
│   ├── wireguard_gateway.yml.j2
│   ├── container_host.yml.j2
│   └── ...
└── playbooks/
    ├── wireguard_gateway.yml.j2
    └── ...
```

### 5. Secrets Reference Pattern

Secrets are never embedded in generated files. Only references are generated:

```yaml
# Generated host_vars
secrets:
  tunnel: tunnels/wg-home-to-oci.yaml
  instance: instances/vps-oracle-frankfurt.yaml

# Runtime lookup in playbook
- name: Load secrets
  set_fact:
    wireguard_secrets: "{{ lookup('community.sops.sops',
      secrets_root + '/' + secrets.tunnel) | from_yaml }}"
```

#### 5.1 Secrets Path Derivation Algorithm

Secrets paths are derived deterministically from topology references:

| Secret Type | Source Field | Derivation Rule | Example |
|-------------|--------------|-----------------|---------|
| Tunnel secrets | `tunnel.secrets_ref` | Remove `secrets.` prefix, replace `.` with `/`, append `.yaml` | `secrets.tunnels.wg-home-to-oci` → `tunnels/wg-home-to-oci.yaml` |
| Instance secrets | `instance_id` | Prefix with `instances/`, append `.yaml` | `vps-oracle-frankfurt` → `instances/vps-oracle-frankfurt.yaml` |

**Derivation function:**

```python
def derive_secrets_path(secrets_ref: str) -> str:
    """Convert topology secrets_ref to relative file path."""
    # secrets.tunnels.wg-home-to-oci -> tunnels/wg-home-to-oci.yaml
    if secrets_ref.startswith("secrets."):
        secrets_ref = secrets_ref[8:]  # Remove "secrets." prefix
    return secrets_ref.replace(".", "/") + ".yaml"
```

### 6. Output Structure

```
generated/home-lab/ansible/
├── inventory/
│   └── production/
│       ├── hosts.yml              # Enhanced with role groups
│       ├── host_vars/
│       │   └── vps-oracle-frankfurt.yml  # Role-specific vars
│       └── group_vars/
│           └── vpn_gateways.yml   # Role defaults
└── playbooks/
    └── vpn-gateway.yml            # Role application
```

### 7. Runtime Assembly Flow

```
COMPILE → GENERATE → ASSEMBLE → EXECUTE

1. compile-topology.py
   → compiled.json

2. AnsibleRoleGenerator
   → generated/home-lab/ansible/inventory/...
   → generated/home-lab/ansible/playbooks/...

3. Runtime assembly (deploy workflow)
   Merges:
   - generated/home-lab/ansible/  (generated vars)
   - projects/home-lab/ansible/roles/  (static roles)
   - projects/home-lab/secrets/  (SOPS)
   → .work/deploy/ansible-runtime/

4. ansible-playbook execution
```

#### 7.1 Taskfile Integration

Runtime assembly is automated via Taskfile:

```yaml
# taskfiles/ansible.yaml

ansible:role-runtime:
  desc: Assemble runtime Ansible directory with generated + static artifacts
  deps:
    - task: compile:topology
  cmds:
    - mkdir -p .work/deploy/ansible-runtime/{{.PROFILE}}/inventory
    - mkdir -p .work/deploy/ansible-runtime/{{.PROFILE}}/playbooks
    # Copy generated inventory (host_vars, group_vars, hosts.yml)
    - cp -r generated/home-lab/ansible/inventory/{{.PROFILE}}/*
        .work/deploy/ansible-runtime/{{.PROFILE}}/inventory/
    # Copy generated playbooks
    - cp -r generated/home-lab/ansible/playbooks/*
        .work/deploy/ansible-runtime/{{.PROFILE}}/playbooks/
    # Copy static roles
    - cp -r projects/home-lab/ansible/roles
        .work/deploy/ansible-runtime/{{.PROFILE}}/
    # Symlink secrets (not copied for security)
    - ln -sf $(pwd)/projects/home-lab/secrets
        .work/deploy/ansible-runtime/{{.PROFILE}}/secrets
  vars:
    PROFILE: '{{.PROFILE | default "production"}}'

ansible:role-check:
  desc: Validate assembled playbook with --check mode
  deps:
    - task: ansible:role-runtime
  cmds:
    - ansible-playbook
        -i .work/deploy/ansible-runtime/{{.PROFILE}}/inventory/hosts.yml
        .work/deploy/ansible-runtime/{{.PROFILE}}/playbooks/vpn-gateway.yml
        --check --diff
  vars:
    PROFILE: '{{.PROFILE | default "production"}}'
```

#### 7.2 Execution Commands

```bash
# Full workflow
task compile:topology
task ansible:role-runtime
task ansible:role-check

# Or combined
task ansible:role-check  # Deps handle compilation and assembly
```

## Consequences

### Improvements

1. **Single source of truth**: Topology defines configuration, Ansible consumes it
2. **Drift elimination**: Changes to topology automatically propagate to Ansible
3. **Consistency**: All infrastructure follows same data flow pattern
4. **Testability**: Generated artifacts can be validated against schema

### Trade-offs

1. **Compilation dependency**: Ansible vars require topology compilation
2. **Template maintenance**: New roles require new templates
3. **Migration effort**: Existing manual inventory must be archived

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Generated vars incompatible with role | Role fails | CI validation with `--check` |
| Secrets refs point to missing files | Runtime failure | Validator plugin for refs |
| Role evolution requires schema changes | Breaking change | Version role schemas |

### Migration Path

| Phase | Actions | Validation |
|-------|---------|------------|
| 1. Parallel | Generate to `generated/`, compare with manual | Diff analysis |
| 2. Integration | Deploy workflow uses generated inventory | `--check` mode |
| 3. Cutover | Archive manual inventory, use generated only | Full test suite |

## Implementation Checklist

- [x] Create `ansible_role_generator.py` plugin
- [x] Add plugin manifest to `plugins.yaml`
- [x] Create Jinja2 templates for `wireguard_gateway`
- [x] Add capability class `cls.capability.vpn_gateway`
- [ ] Update deploy workflow for runtime assembly
- [ ] Add CI validation for generated Ansible
- [x] Archive manual inventory files
- [x] Update documentation

### Implementation Notes (2026-06-09)

**Created files:**
- `topology-tools/plugins/generators/ansible_role_generator.py` (302 lines)
- `topology-tools/plugins/generators/ansible_role_projections.py` (209 lines)
- `topology-tools/templates/ansible/host_vars/wireguard_gateway.yml.j2`
- `topology-tools/templates/ansible/playbooks/vpn-gateway.yml.j2`

**Modified files:**
- `topology-tools/plugins/generators/projections.py` - added `CAPABILITY_ROLE_MAP` and `build_ansible_role_projection()`
- `topology-tools/plugins/plugins.yaml` - added manifest entry

**Archived to `archive/ansible-manual/`:**
- `inventory/production/host_vars/vps-oracle-frankfurt.yml`
- `playbooks/vpn-gateway.yml`
- `playbooks/common.yml`, `monitoring.yml`, `nextcloud.yml`, `postgresql.yml`, `redis.yml`, `site.yml`

**Directory restructure:**
- `projects/home-lab/ansible/inventory/production/hosts.yml` → `cloud-hosts.yml`
- `projects/home-lab/ansible/playbooks/` → archived (now generated)
- `projects/home-lab/ansible/roles/` → kept (implementation code)

**Execution command:**
```bash
export VPS_ORACLE_FRANKFURT_IP=$(oci compute instance list-vnics ... --query 'data[0]."public-ip"')
export VPS_SSH_KEY_PATH=/tmp/ansible-test/vps-key
export ANSIBLE_ROLES_PATH=projects/home-lab/ansible/roles

ansible-playbook \
  -i projects/home-lab/ansible/inventory/production/cloud-hosts.yml \
  -e @generated/home-lab/ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml \
  generated/home-lab/ansible/playbooks/vpn-gateway.yml
```

## References

- ADR 0063: Plugin-based compiler architecture
- ADR 0074: Generator architecture and projection contract
- ADR 0075: Framework/project separation
- ADR 0086: Plugin contract and stage affinity
- ADR 0097: Subinterpreter parallel plugin execution
- Commit: 726810e3 (manual Ansible role creation)
- Docs: `docs/guides/VPN-GATEWAY-ANSIBLE.md`
- Analysis: `adr/0104-analysis/` (SWOT analysis, implementation plan)

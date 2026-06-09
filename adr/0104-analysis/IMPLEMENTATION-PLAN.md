# ADR 0104 Implementation Plan

**Date:** 2026-06-09
**Status:** Ready for execution
**Prerequisites:** ADR 0104 improvements completed

---

## Phase Overview

| Phase | Name | Dependencies | Deliverables |
|-------|------|--------------|--------------|
| 0 | ADR Improvement | None | Updated ADR 0104 |
| 1 | Projection Builder | Phase 0 | `build_ansible_role_projection()` |
| 2 | Templates | Phase 0 | 2 Jinja2 templates |
| 3 | Generator Plugin | Phases 1, 2 | `ansible_role_generator.py` |
| 4 | Integration | Phase 3 | Manifest, tests |
| 5 | Migration | Phase 4 validated | Archive manual, cutover |

---

## Phase 0: ADR Improvement

### Task 0.1: Add ADR 0097 Reference

**File:** `adr/0104-ansible-role-generation-from-topology.md`

**Changes:**
1. Add to Constraints section:
   ```markdown
   4. Plugin execution mode must be declared (ADR 0097)
   ```

2. Update Plugin Manifest example:
   ```yaml
   execution_mode: subinterpreter
   ```

3. Add to References:
   ```markdown
   - ADR 0097: Subinterpreter parallel plugin execution
   ```

### Task 0.2: Expand Capability Code Example

**Replace** Decision 3 code with:

```python
from typing import Any, Iterator

CAPABILITY_ROLE_MAP = {
    "cap.network.vpn_gateway": "wireguard_gateway",
    # Future capabilities:
    # "cap.compute.runtime.container_host": "docker_host",
    # "cap.monitoring.prometheus_target": "prometheus_node_exporter",
}

def build_ansible_role_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build projection for Ansible role-based host_vars generation.

    Scans instances for capability markers and yields role-specific
    variable sets for each matching instance.
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
            if not isinstance(capabilities, list):
                capabilities = []

            for cap in capabilities:
                if cap in CAPABILITY_ROLE_MAP:
                    role_name = CAPABILITY_ROLE_MAP[cap]
                    role_assignments.append({
                        "instance_id": instance_id,
                        "capability": cap,
                        "role": role_name,
                        "instance_data": inst,
                    })

    return {
        "role_assignments": role_assignments,
        "counts": {
            "total_assignments": len(role_assignments),
        },
    }
```

### Task 0.3: Document Secrets Derivation

**Add** new Decision 5.1:

```markdown
### 5.1 Secrets Path Derivation Algorithm

Secrets paths are derived deterministically from topology references:

| Secret Type | Derivation Rule | Example |
|-------------|-----------------|---------|
| Tunnel secrets | `secrets_ref` field → path | `secrets.tunnels.wg-home-to-oci` → `tunnels/wg-home-to-oci.yaml` |
| Instance secrets | `instances/{instance_id}.yaml` | `instances/vps-oracle-frankfurt.yaml` |

**Projection output:**
```yaml
secrets:
  tunnel: "{{ tunnel_instance.secrets_ref | replace('secrets.', '') | replace('.', '/') }}.yaml"
  instance: "instances/{{ instance_id }}.yaml"
```
```

### Task 0.4: Expand Runtime Assembly

**Expand** Decision 7 with Taskfile integration:

```markdown
### 7.1 Taskfile Integration

```yaml
# taskfiles/ansible.yaml
ansible:role-runtime:
  desc: Assemble runtime Ansible directory with generated + static
  cmds:
    - mkdir -p .work/deploy/ansible-runtime/{{.PROFILE}}
    - cp -r generated/home-lab/ansible/inventory/{{.PROFILE}}/* .work/deploy/ansible-runtime/{{.PROFILE}}/
    - cp -r projects/home-lab/ansible/roles .work/deploy/ansible-runtime/
    - cp -r generated/home-lab/ansible/playbooks/* .work/deploy/ansible-runtime/playbooks/
  vars:
    PROFILE: '{{.PROFILE | default "production"}}'
```
```

**Acceptance criteria:** ADR 0104 updated with all 4 tasks.

---

## Phase 1: Projection Builder

### Task 1.1: Add Projection Function

**File:** `topology-tools/plugins/generators/projections.py`

**Location:** After `build_ansible_projection()` (line ~152)

**Implementation:**
```python
def build_ansible_role_projection(compiled_json: dict[str, Any]) -> dict[str, Any]:
    """Build projection for Ansible role-based host_vars generation."""
    # Implementation per Task 0.2 code
    ...
```

### Task 1.2: Add Role-Specific Builders

**File:** `topology-tools/plugins/generators/ansible_role_projections.py` (new)

```python
"""Role-specific projection builders for Ansible role generator."""

from typing import Any

def build_wireguard_gateway_vars(
    instance: dict[str, Any],
    tunnel: dict[str, Any],
    vlan: dict[str, Any],
) -> dict[str, Any]:
    """Build wireguard_gateway role variables from topology."""
    wg_config = instance.get("wireguard_gateway", {})
    networking = instance.get("networking", {})
    tunnel_iface = next(
        (t for t in networking.get("tunnel_interfaces", []) if t.get("name") == "wg0"),
        {}
    )

    return {
        "instance_ref": instance.get("instance_id"),
        "instance_group": "cloud",
        "instance_role": "vpn_gateway",
        "primary_interface": networking.get("primary_interface", "ens3"),
        "tunnel_interface": "wg0",
        "wireguard": {
            "interface": "wg0",
            "listen_port": tunnel_iface.get("listen_port", 51820),
            "tunnel_ip": tunnel_iface.get("tunnel_ip"),
            "role": tunnel_iface.get("role", "server"),
            "private_key_file": "/etc/wireguard/private.key",
            "config_file": "/etc/wireguard/wg0.conf",
        },
        "secrets": {
            "tunnel": _derive_secrets_path(tunnel.get("secrets_ref", "")),
            "instance": f"instances/{instance.get('instance_id')}.yaml",
        },
        "wireguard_peers": _build_peers(tunnel),
        "ip_forwarding": wg_config.get("ip_forwarding", True),
        "routed_networks": _build_routed_networks(wg_config, vlan),
        "iptables_forward_rules": wg_config.get("iptables_rules", {}).get("forward", []),
        "iptables_nat_rules": wg_config.get("iptables_rules", {}).get("nat", []),
    }

def _derive_secrets_path(secrets_ref: str) -> str:
    """Convert secrets_ref to file path."""
    # secrets.tunnels.wg-home-to-oci -> tunnels/wg-home-to-oci.yaml
    if secrets_ref.startswith("secrets."):
        secrets_ref = secrets_ref[8:]
    return secrets_ref.replace(".", "/") + ".yaml"

def _build_peers(tunnel: dict[str, Any]) -> list[dict[str, Any]]:
    """Build peer list from tunnel endpoint_a."""
    endpoint_a = tunnel.get("endpoint_a", {})
    return [{
        "name": endpoint_a.get("device_ref", ""),
        "public_key": "{{ wireguard_secrets.mikrotik.public_key }}",
        "allowed_ips": endpoint_a.get("allowed_ips", []),
    }]

def _build_routed_networks(
    wg_config: dict[str, Any],
    vlan: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build routed networks list."""
    networks = []
    for net in wg_config.get("routed_networks", []):
        networks.append({
            "network": net.get("network") or vlan.get("cidr"),
            "comment": f"VLAN {vlan.get('vlan_id', '')}",
            "nat": net.get("nat", "masquerade"),
        })
    return networks
```

**Acceptance criteria:** Projection functions produce dict matching manual `host_vars/` structure.

---

## Phase 2: Templates

### Task 2.1: Host Vars Template

**File:** `topology-tools/templates/ansible/host_vars/wireguard_gateway.yml.j2`

```jinja2
---
# Generated by AnsibleRoleGenerator - DO NOT EDIT
# Source: topology/instances/vm/cloud/{{ instance_ref }}.yaml

# Instance identification
instance_ref: {{ instance_ref }}
instance_group: {{ instance_group }}
instance_role: {{ instance_role }}

# Network configuration
primary_interface: {{ primary_interface }}
tunnel_interface: {{ tunnel_interface }}

# WireGuard configuration
wireguard:
  interface: {{ wireguard.interface }}
  listen_port: {{ wireguard.listen_port }}
  tunnel_ip: {{ wireguard.tunnel_ip }}
  role: {{ wireguard.role }}
  private_key_file: {{ wireguard.private_key_file }}
  config_file: {{ wireguard.config_file }}

# Secrets references (decrypted at runtime via SOPS)
secrets:
  tunnel: {{ secrets.tunnel }}
  instance: {{ secrets.instance }}

# Peer configuration
wireguard_peers:
{% for peer in wireguard_peers %}
  - name: {{ peer.name }}
    public_key: "{{ peer.public_key }}"
    allowed_ips:
{% for ip in peer.allowed_ips %}
      - {{ ip }}
{% endfor %}
{% endfor %}

# IP forwarding and NAT
ip_forwarding: {{ ip_forwarding | lower }}

# Routed networks
routed_networks:
{% for net in routed_networks %}
  - network: {{ net.network }}
    comment: "{{ net.comment }}"
    nat: {{ net.nat }}
{% endfor %}

# iptables rules
iptables_forward_rules:
{% for rule in iptables_forward_rules %}
  - "{{ rule }}"
{% endfor %}

iptables_nat_rules:
{% for rule in iptables_nat_rules %}
  - "{{ rule }}"
{% endfor %}
```

### Task 2.2: Playbook Template

**File:** `topology-tools/templates/ansible/playbooks/vpn-gateway.yml.j2`

```jinja2
---
# Generated by AnsibleRoleGenerator - DO NOT EDIT
# VPN Gateway Playbook for {{ instance_ref }}

- name: Configure VPN Gateway
  hosts: {{ instance_ref }}
  become: true
  gather_facts: true

  vars:
    secrets_root: "{{ '{{' }} playbook_dir {{ '}}' }}/../../../projects/home-lab/secrets"

  pre_tasks:
    - name: Load tunnel secrets
      ansible.builtin.set_fact:
        wireguard_secrets: "{{ '{{' }} lookup('community.sops.sops', secrets_root + '/' + secrets.tunnel) | from_yaml {{ '}}' }}"
      no_log: true

  roles:
    - role: wireguard_gateway

  post_tasks:
    - name: Display WireGuard status
      ansible.builtin.command: wg show {{ '{{' }} wireguard.interface {{ '}}' }}
      register: wg_status
      changed_when: false

    - name: Show WireGuard status
      ansible.builtin.debug:
        var: wg_status.stdout_lines
```

**Acceptance criteria:** Templates render valid YAML matching manual files.

---

## Phase 3: Generator Plugin

### Task 3.1: Create Generator

**File:** `topology-tools/plugins/generators/ansible_role_generator.py`

```python
"""Generator plugin that emits role-based Ansible host_vars and playbooks."""

from __future__ import annotations

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage
from plugins.generators.artifact_contract import (
    build_artifact_plan,
    build_generation_report,
    build_planned_output,
    compute_obsolete_entries,
    validate_contract_payloads,
    write_contract_artifacts,
)
from plugins.generators.base_generator import BaseGenerator
from plugins.generators.projections import build_ansible_role_projection
from plugins.generators.ansible_role_projections import build_wireguard_gateway_vars


class AnsibleRoleGenerator(BaseGenerator):
    """Emit role-based Ansible host_vars and playbooks from topology."""

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        payload = ctx.compiled_json

        if not isinstance(payload, dict) or not payload:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3101",
                    severity="error",
                    stage=stage,
                    message="compiled_json is empty; cannot generate Ansible role artifacts.",
                    path="generator:ansible_role",
                )
            )
            return self.make_result(diagnostics)

        projection = build_ansible_role_projection(payload)
        role_assignments = projection.get("role_assignments", [])

        if not role_assignments:
            diagnostics.append(
                self.emit_diagnostic(
                    code="I3101",
                    severity="info",
                    stage=stage,
                    message="No role assignments found; skipping Ansible role generation.",
                    path="generator:ansible_role",
                )
            )
            return self.make_result(diagnostics)

        inventory_profile = str(ctx.config.get("inventory_profile", "production"))
        out_root = self.resolve_output_path(ctx, "ansible")
        host_vars_dir = out_root / "inventory" / inventory_profile / "host_vars"
        playbooks_dir = out_root / "playbooks"

        written: list[str] = []
        planned_outputs: list[dict[str, object]] = []
        write_text = self.__dict__.get("write_text_atomic", self.write_text_atomic)

        for assignment in role_assignments:
            instance_id = assignment["instance_id"]
            role_name = assignment["role"]
            instance_data = assignment["instance_data"]

            if role_name == "wireguard_gateway":
                # Resolve related topology objects
                tunnel = self._resolve_tunnel(payload, instance_data)
                vlan = self._resolve_vlan(payload, instance_data)

                role_vars = build_wireguard_gateway_vars(instance_data, tunnel, vlan)

                # Generate host_vars
                host_vars_path = host_vars_dir / f"{instance_id}.yml"
                planned_outputs.append(
                    build_planned_output(
                        path=str(host_vars_path),
                        renderer="jinja2",
                        reason="capability-triggered",
                    )
                )
                host_vars_content = self.render_template(
                    ctx,
                    "ansible/host_vars/wireguard_gateway.yml.j2",
                    role_vars,
                )
                write_text(host_vars_path, host_vars_content)
                written.append(str(host_vars_path))

                # Generate playbook
                playbook_path = playbooks_dir / "vpn-gateway.yml"
                planned_outputs.append(
                    build_planned_output(
                        path=str(playbook_path),
                        renderer="jinja2",
                        reason="capability-triggered",
                    )
                )
                playbook_content = self.render_template(
                    ctx,
                    "ansible/playbooks/vpn-gateway.yml.j2",
                    role_vars,
                )
                write_text(playbook_path, playbook_content)
                written.append(str(playbook_path))

        # Artifact contract
        artifact_family = "ansible.role"
        obsolete_entries, obsolete_errors = compute_obsolete_entries(
            ctx=ctx,
            plugin_id=self.plugin_id,
            output_root=out_root,
            planned_outputs=planned_outputs,
        )

        # ... (standard artifact contract handling per ansible_inventory_generator.py)

        diagnostics.append(
            self.emit_diagnostic(
                code="I3102",
                severity="info",
                stage=stage,
                message=f"generated Ansible role artifacts: {len(written)} files",
                path=str(out_root),
            )
        )

        ctx.publish("ansible_role_files", written)

        return self.make_result(
            diagnostics=diagnostics,
            output_data={
                "ansible_role_files": written,
            },
        )

    def _resolve_tunnel(self, payload: dict, instance: dict) -> dict:
        """Resolve tunnel instance from wireguard_gateway.tunnel_ref."""
        tunnel_ref = instance.get("wireguard_gateway", {}).get("tunnel_ref", "")
        # Search in network instances
        for inst in payload.get("instances", {}).get("network", []):
            if inst.get("instance_id") == tunnel_ref:
                return inst
        return {}

    def _resolve_vlan(self, payload: dict, instance: dict) -> dict:
        """Resolve VLAN instance from routed_networks[].vlan_ref."""
        routed = instance.get("wireguard_gateway", {}).get("routed_networks", [])
        if routed:
            vlan_ref = routed[0].get("vlan_ref", "")
            for inst in payload.get("instances", {}).get("network", []):
                if inst.get("instance_id") == vlan_ref:
                    return inst
        return {}
```

### Task 3.2: Add Manifest Entry

**File:** `topology-tools/plugins/plugins.yaml`

```yaml
- id: base.generator.ansible_role
  family: generators
  stage: generate
  order: 235
  execution_mode: subinterpreter
  depends_on:
    - base.generator.ansible_inventory
  consumes:
    - from_plugin: base.generator.ansible_inventory
      keys: [ansible_inventory_dir]
  publishes:
    - ansible_role_files
  entry: plugins.generators.ansible_role_generator:AnsibleRoleGenerator
```

**Acceptance criteria:** Plugin loads, executes, produces files matching manual.

---

## Phase 4: Integration

### Task 4.1: Add Tests

**File:** `tests/plugin_integration/test_ansible_role_generator.py`

- Test projection builder output structure
- Test template rendering
- Test capability scanning
- Test secrets path derivation

### Task 4.2: CI Validation

Add to CI pipeline:
```yaml
- name: Validate generated Ansible
  run: |
    ansible-playbook --syntax-check generated/home-lab/ansible/playbooks/*.yml
    ansible-lint generated/home-lab/ansible/
```

**Acceptance criteria:** All tests pass, CI gate green.

---

## Phase 5: Migration

### Task 5.1: Validation Diff

```bash
# Compare generated vs manual
diff -u \
  projects/home-lab/ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml \
  generated/home-lab/ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml
```

### Task 5.2: Archive Manual Files

```bash
mkdir -p archive/ansible-manual/inventory/production/host_vars
mkdir -p archive/ansible-manual/playbooks

mv projects/home-lab/ansible/inventory/production/host_vars/vps-oracle-frankfurt.yml \
   archive/ansible-manual/inventory/production/host_vars/

mv projects/home-lab/ansible/playbooks/vpn-gateway.yml \
   archive/ansible-manual/playbooks/
```

### Task 5.3: Update Documentation

- Update `projects/home-lab/ansible/README.md`
- Update `docs/guides/VPN-GATEWAY-ANSIBLE.md`

### Task 5.4: Integration Test

```bash
# Full test with generated artifacts
ansible-playbook -i generated/home-lab/ansible/inventory/production/hosts.yml \
  generated/home-lab/ansible/playbooks/vpn-gateway.yml \
  --check --diff
```

**Acceptance criteria:** Playbook runs successfully with generated artifacts.

---

## Checklist Summary

| Phase | Task | Status |
|-------|------|--------|
| 0 | Add ADR 0097 reference | ⬜ |
| 0 | Expand capability code | ⬜ |
| 0 | Document secrets derivation | ⬜ |
| 0 | Expand runtime assembly | ⬜ |
| 1 | Add projection function | ⬜ |
| 1 | Add role-specific builders | ⬜ |
| 2 | Create host_vars template | ⬜ |
| 2 | Create playbook template | ⬜ |
| 3 | Create generator plugin | ⬜ |
| 3 | Add manifest entry | ⬜ |
| 4 | Add tests | ⬜ |
| 4 | Add CI validation | ⬜ |
| 5 | Validation diff | ⬜ |
| 5 | Archive manual files | ⬜ |
| 5 | Update documentation | ⬜ |
| 5 | Integration test | ⬜ |

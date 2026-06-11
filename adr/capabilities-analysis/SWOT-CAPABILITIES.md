# SWOT Analysis: Capabilities System

**Date:** 2026-06-11
**Analysis Type:** Strategic Assessment
**Scope:** Capabilities functionality across the home-lab project

---

## Executive Summary

The home-lab project implements a sophisticated capabilities system using the namespace `cap.<domain>.<subdomain>.<capability>` integrated with the Class -> Object -> Instance topology model. This analysis evaluates the architectural design, current implementation, and strategic opportunities for improvement.

**Key Finding:** The capabilities system provides a solid declarative foundation for infrastructure-as-data, but shows gaps in runtime utilization by generators and inconsistent adoption across the codebase.

---

## 1. STRENGTHS

### S1. Well-Defined Namespace Architecture

The capability namespace design (`cap.<domain>.<subdomain>.<capability>`) provides clear taxonomic organization:

| Layer | Domain Examples | Count |
|-------|----------------|-------|
| L0 | os, arch | 35 |
| L1 | compute, router, power | 58 |
| L2 | bridge, vlan, firewall, qos | 20 |
| L3 | storage | 12 |
| L4 | workload | 9 |
| L5 | service | 27 |
| L6 | observability | 9 |
| L7 | operations | 18 |

**Total standard capabilities: ~188**

The multi-level naming convention enables:
- Hierarchical queries (all `cap.compute.*` capabilities)
- Domain filtering (all L1 networking capabilities)
- Programmatic capability matching in generators

### S2. Separation of Capability Types

The architecture distinguishes three capability categories:

1. **Standard capabilities** (`cap.*`) - Framework-defined, documented in `capability-catalog.yaml`
2. **Vendor capabilities** (`vendor.*`) - Device/platform-specific features (e.g., `vendor.mikrotik.winbox`)
3. **Operations capabilities** (`cap.operations.*`, `vendor.operations.*`) - Deploy/backup/rollback features (ADR 0105)

This separation prevents namespace pollution and enables vendor-agnostic orchestration.

### S3. Class-Level Contract Definition

Classes define capability contracts that objects must satisfy:

```yaml
# class.router.yaml
required_capabilities:
  - cap.net.interface.ethernet
  - cap.net.l3.routing.static
  - cap.net.l3.translation.snat
  - cap.net.l3.security.firewall.stateful
  - cap.net.service.dhcp.server
  - cap.net.service.dns.resolver

optional_capabilities:
  - cap.net.l3.routing.dynamic.bgp
  - cap.net.overlay.vpn.wireguard.server
  # ... 43 more optional capabilities
```

Objects must include all `required_capabilities` and may enable any subset of `optional_capabilities`. This enforces architectural consistency.

### S4. Capability Packs for Common Profiles

Pre-defined capability bundles reduce configuration complexity:

| Pack ID | Target | Capabilities |
|---------|--------|--------------|
| `pack.router.home_gateway` | MikroTik Chateau | 25 |
| `pack.router.travel_vpn` | GL.iNet Slate | 18 |
| `pack.router.enterprise` | CCR series | 18 |
| `pack.compute.hypervisor.standalone` | Proxmox | 4 |
| `pack.compute.hypervisor.cluster` | HA clusters | 8 |
| `pack.service.monitoring.prometheus` | Prometheus | 3 |

Packs enable role-based device provisioning without manual capability enumeration.

### S5. Derived Capabilities (ADR 0064)

The compiler derives capabilities from OS/firmware properties:

```yaml
# OS properties automatically derive:
# distribution: debian -> cap.os.debian
# release: "12" -> cap.os.debian.12
# init_system: systemd -> cap.os.init.systemd
# package_manager: apt -> cap.os.pkg.apt

# Firmware properties derive:
# architecture: arm64 -> cap.arch.arm64
```

This eliminates manual capability declaration for infrastructure properties already modeled in topology.

### S6. Integration with ADR 0105 Operations

The operations capability model enables capability-driven automation:

| Capability | Ansible Role | Backup Method |
|------------|--------------|---------------|
| `cap.operations.backup.routeros_export` | `backup_mikrotik` | /export |
| `cap.operations.backup.vzdump` | `backup_proxmox` | vzdump |
| `cap.operations.backup.config_archive` | `backup_linux` | tar/gzip |
| `cap.operations.deploy.safe_mode` | `deploy_safe_mode` | RouterOS safe-mode |

This design enables generator-driven playbook assembly based on device capabilities.

---

## 2. WEAKNESSES

### W1. Limited Generator Utilization of Capabilities

Current generators underutilize capability data:

| Generator | Capability Usage | Status |
|-----------|------------------|--------|
| `ansible_inventory_generator.py` | None | Does not filter/group by capabilities |
| `terraform_ir.py` | Minimal | Some capability flags in projections |
| `ansible_role_generator.py` | Partial | Uses `CAPABILITY_ROLE_MAP` (1 mapping) |
| `capability_helpers.py` | Helper | `capability_expression_enabled()` utility |

**Evidence:** The `CAPABILITY_ROLE_MAP` in `projections.py` contains only one mapping:

```python
CAPABILITY_ROLE_MAP: dict[str, str] = {
    "cap.network.vpn_gateway": "wireguard_gateway",
    # Future capabilities:
    # "cap.compute.runtime.container_host": "docker_host",
    # "cap.monitoring.prometheus_target": "prometheus_node_exporter",
}
```

This limits the practical impact of capability declarations.

### W2. Inconsistent Capability Declaration in Object Modules

Object modules show varying levels of capability completeness:

| Object | enabled_capabilities | vendor_capabilities | operations_capabilities |
|--------|---------------------|---------------------|------------------------|
| `obj.mikrotik.chateau_lte7_ax` | 32 | 8 | 7 |
| `obj.proxmox.ve` | 4 | 4 | 7 |
| `obj.orangepi.rk3588.debian` | 3 | 2 | 4 |
| `obj.service.prometheus` | 2 | 2 | 0 |
| `obj.network.vlan.servers` | 1 | 0 | 0 |

Some objects (like MikroTik) are comprehensively defined, while others lack full capability modeling.

### W3. Instance-Level Capability Overrides Rarely Used

Of all instance files examined, only one (`vps-oracle-frankfurt.yaml`) declares instance-level capabilities:

```yaml
enabled_capabilities:
- cap.compute.runtime.container_host
- cap.compute.workload.linux_base
- cap.network.vpn_gateway
```

Instance-level capability customization, while architecturally supported, is effectively unused.

### W4. Capability Validation Not Runtime-Enforced

ADR 0063 Section 4B defined plugin boundary rules based on capabilities, but ADR 0086 superseded this:

> "4-уровневая модель (global/class/object/instance) перестает быть правилом видимости данных в runtime."

Capability constraints are documented contracts, not runtime-enforced policies. The compiler does not validate that objects satisfy `required_capabilities` or that instances respect object capability bounds.

### W5. No Capability Dependency Graph

Capabilities are declared as flat lists without explicit dependencies:

```yaml
# No way to express:
# cap.net.overlay.vpn.wireguard.server REQUIRES cap.net.l3.routing.static
```

Complex capability interactions must be manually tracked or enforced through external documentation.

### W6. Capability Catalog Maintenance Burden

The `capability-catalog.yaml` contains 188+ entries with manual title/summary/domain/layer/stability annotations. Adding new capabilities requires:

1. Catalog entry with all metadata
2. Usage in object modules
3. Generator updates (if behavior-affecting)
4. Documentation updates

This multi-file maintenance increases the cost of capability evolution.

---

## 3. OPPORTUNITIES

### O1. Ansible Inventory Group Generation from Capabilities

Extend `ansible_inventory_generator.py` to create capability-based groups:

```yaml
# Generated inventory
[cap_operations_backup_routeros_export]
rtr-mikrotik-chateau

[cap_operations_backup_vzdump]
hv-proxmox-xps
lxc-postgresql
lxc-grafana

[cap_compute_runtime_container_host]
srv-orangepi5
vps-oracle-frankfurt
```

This enables targeted playbook execution:

```bash
ansible-playbook -l cap_operations_backup_vzdump backup-vzdump.yml
```

### O2. Capability-Driven Terraform Resource Selection

Use capabilities to conditionally generate Terraform resources:

```hcl
# If device has cap.operations.snapshot.propagate
resource "routeros_system_script" "topology_metadata" {
  # ... snapshot propagation script
}

# If device has cap.net.overlay.vpn.wireguard.server
resource "routeros_interface_wireguard" "wg0" {
  # ... WireGuard interface
}
```

The projection layer can expose capability flags for template conditionals.

### O3. Service Requirement Matching

Implement service-to-host compatibility checking (per ADR 0064):

```yaml
# Service requirement
service: prometheus
requires:
  capabilities:
    all: [cap.os.linux, cap.os.init.systemd]
    any: [cap.os.debian, cap.os.ubuntu, cap.os.alpine]
```

The compiler could validate that target hosts satisfy service requirements.

### O4. Capability-Driven Documentation Generation

Generate capability matrices and compatibility tables:

```markdown
| Device | WireGuard Server | LXC Runtime | Docker Runtime | VZDump Backup |
|--------|-----------------|-------------|----------------|---------------|
| MikroTik Chateau | Yes | No | Yes (container) | No |
| Proxmox VE | No | Yes | No | Yes |
| Orange Pi 5 | No | No | Yes | No |
```

### O5. Multi-Project Capability Registry (ADR 0081)

With framework/project separation, capabilities could be:

- **Framework capabilities** - Standard infrastructure capabilities
- **Project capabilities** - Project-specific custom capabilities

Projects could extend the capability namespace without polluting framework definitions.

### O6. Capability-Based Testing

Generate test matrices from capabilities:

```python
# Test all devices with cap.operations.backup.routeros_export
def test_routeros_backup():
    for device in devices_with_capability("cap.operations.backup.routeros_export"):
        assert backup_test_passes(device)
```

### O7. Capability Schema Enforcement

Introduce JSON Schema validation for capability declarations:

```json
{
  "$schema": "capability-catalog.schema.json",
  "capability": "cap.operations.backup.vzdump",
  "requires": ["cap.compute.host.hypervisor"],
  "conflicts": ["cap.compute.node.edge"],
  "stability": "stable"
}
```

---

## 4. THREATS

### T1. Capability Drift Without Runtime Enforcement

Without compiler validation, objects may:
- Declare capabilities they do not actually implement
- Miss required capabilities defined by parent class
- Have instances that contradict object capability bounds

This creates false confidence in capability-based automation.

### T2. Namespace Fragmentation Risk

Multiple capability namespaces exist:
- `cap.*` (standard)
- `vendor.*` (vendor-specific)
- `pack.*` (capability packs)

Without governance, projects may introduce:
- `project.*` capabilities
- `custom.*` capabilities
- Inconsistent naming patterns

### T3. Technical Debt in Generator Adoption

The TODO comments in `capability_helpers.py` indicate migration debt:

```python
# TODO(ADR0078-cleanup): Remove capability_key fallback after v5.1 migration
# TODO(ADR0078-cleanup): Remove output_file fallback after v5.1 migration
```

Incomplete migration creates maintenance complexity.

### T4. Capability-Based Complexity

As capabilities grow, the interaction surface expands:

- 188 capabilities * potential combinations = complexity explosion
- Capability packs partially address this, but manual pack maintenance is required
- No automated pack suggestion based on declared capabilities

### T5. Documentation-Implementation Gap

The capability catalog documents intended behavior, but generators may not implement all documented capabilities. For example:

- `cap.operations.deploy.pre_check` is documented but no generator produces pre-check artifacts
- `cap.operations.consistency.group` is documented but ADR 0105 implementation is Draft status

### T6. Adoption Barrier for New Objects

Adding a new device type requires:

1. Create object YAML with capability declarations
2. Ensure all `required_capabilities` from class are included
3. Add `vendor_capabilities` for device-specific features
4. Optionally add `operations_capabilities`
5. Update capability catalog if new capabilities needed
6. Update generators if capabilities affect output

This high friction may discourage capability adoption.

---

## 5. CAPABILITY USAGE MATRIX

### 5.1 Object Modules by Capability Category

| Object Module | Standard | Vendor | Operations | Total |
|---------------|----------|--------|------------|-------|
| `obj.mikrotik.chateau_lte7_ax` | 32 | 8 | 7 | 47 |
| `obj.proxmox.ve` | 4 | 4 | 7 | 15 |
| `obj.orangepi.rk3588.debian` | 3 | 2 | 4 | 9 |
| `obj.glinet.slate_ax1800` | ~15 | ~5 | 0 | ~20 |
| `obj.oracle.cloud_vm` | ~3 | ~2 | ~4 | ~9 |
| **Services** | | | | |
| `obj.service.prometheus` | 2 | 2 | 0 | 4 |
| `obj.service.grafana` | ~2 | ~2 | 0 | ~4 |
| `obj.service.postgresql` | ~3 | ~2 | 0 | ~5 |
| **Network** | | | | |
| `obj.network.vlan.servers` | 1 | 0 | 0 | 1 |
| `obj.network.bridge.vmbr0` | ~2 | 0 | 0 | ~2 |

### 5.2 Capability Domain Coverage

| Domain | Defined in Catalog | Used in Objects | Generator Integration |
|--------|-------------------|-----------------|----------------------|
| `cap.compute.*` | 12 | Partial | Minimal |
| `cap.router.*` | 26 | Full (MikroTik) | Minimal |
| `cap.storage.*` | 12 | Partial | None |
| `cap.service.*` | 27 | Partial | None |
| `cap.operations.*` | 18 | Emerging | Planned (ADR 0105) |
| `cap.os.*` | 35 | Derived | Via projections |
| `cap.arch.*` | 4 | Derived | Via projections |

### 5.3 Operations Capability Adoption

| Device Type | safe_mode | pre_check | post_verify | snapshot | rollback | consistency |
|-------------|-----------|-----------|-------------|----------|----------|-------------|
| MikroTik | Yes | Yes | Yes | Yes | Yes | Yes |
| Proxmox | No | Yes | Yes | Yes | Yes | Yes |
| OrangePi | No | Yes | Yes | Yes | No | No |
| Oracle VPS | No | No | No | No | No | No |

---

## 6. GAP ANALYSIS

### 6.1 Where Capabilities Should Be Used But Are Not

| Area | Current State | Gap | Impact |
|------|---------------|-----|--------|
| Ansible inventory groups | No capability-based grouping | High | Manual group maintenance |
| Terraform conditional resources | Hardcoded vendor checks | Medium | Inflexible generation |
| Service-host compatibility | No validation | Medium | Runtime failures possible |
| Backup playbook generation | Single `CAPABILITY_ROLE_MAP` entry | High | Manual playbook maintenance |
| Documentation generation | No capability matrices | Low | Documentation debt |

### 6.2 Missing Capabilities

| Missing Capability | Rationale |
|--------------------|-----------|
| `cap.network.tunnel.wireguard` | Generic WireGuard tunnel (not server/client) |
| `cap.network.mesh.tailscale` | Tailscale mesh networking |
| `cap.compute.cluster.k8s` | Kubernetes clustering |
| `cap.service.database.backup` | Database-specific backup capability |
| `cap.operations.monitoring.prometheus_target` | Device is Prometheus scrape target |

---

## 7. RECOMMENDATIONS

### R1. Expand Generator Capability Integration (Priority: HIGH)

1. Update `ansible_inventory_generator.py` to create capability-based groups
2. Expand `CAPABILITY_ROLE_MAP` to cover all operations capabilities
3. Add capability flags to projection outputs for template conditionals

### R2. Add Capability Validation to Compiler (Priority: HIGH)

1. Validate objects include all class `required_capabilities`
2. Validate instance capabilities are subset of object capabilities
3. Emit diagnostics for capability contract violations

### R3. Standardize Operations Capability Adoption (Priority: MEDIUM)

1. Complete ADR 0105 implementation (currently Draft)
2. Add `operations_capabilities` to all device objects
3. Implement capability-driven backup role generation

### R4. Create Capability Documentation Generator (Priority: MEDIUM)

1. Generate capability matrices from topology
2. Auto-generate compatibility tables
3. Detect undocumented capabilities in use

### R5. Establish Capability Governance Process (Priority: LOW)

1. Define namespace ownership (framework vs project)
2. Create capability lifecycle (experimental -> stable -> deprecated)
3. Require ADR for new capability domains

---

## 8. PROPOSED APPLICATION: Pervasive Capability-Driven Architecture

### 8.1 Core Thesis

> **Capabilities должны стать единственным механизмом контроля функциональности** — каждый плагин, генератор и валидатор должен принимать решения исключительно на основе capability declarations, а не hardcoded условий.

**Текущее состояние:** Capabilities = documentation artifacts
**Целевое состояние:** Capabilities = runtime control primitives

### 8.2 Plugin Integration Model

#### 8.2.1 Capability-Aware Plugin Contract

Каждый плагин должен декларировать:

```yaml
# plugin manifest
name: mikrotik_terraform_generator
stage: generate
capability_filter:
  requires_any:
    - cap.os.routeros
    - vendor.mikrotik.*
  requires_all:
    - cap.net.interface.ethernet
produces_for_capabilities:
  - cap.net.overlay.vpn.wireguard.server → wireguard.tf
  - cap.net.l2.segmentation.vlan.8021q → vlans.tf
  - cap.operations.snapshot.propagate → topology_metadata.tf
```

**Benefit:** Плагин автоматически пропускается для объектов без matching capabilities.

#### 8.2.2 Capability-Driven Code Branching

**BEFORE (hardcoded):**
```python
def generate(self, ctx):
    if obj.vendor == "mikrotik":
        self._generate_mikrotik(obj)
    elif obj.vendor == "proxmox":
        self._generate_proxmox(obj)
```

**AFTER (capability-driven):**
```python
def generate(self, ctx):
    for obj in ctx.objects:
        handlers = self._get_handlers_for_capabilities(obj.capabilities)
        for handler in handlers:
            handler.generate(obj)

CAPABILITY_HANDLERS = {
    "cap.os.routeros": MikroTikHandler,
    "cap.compute.host.hypervisor": ProxmoxHandler,
    "cap.compute.runtime.container_host": DockerHandler,
}
```

**Benefit:** Добавление нового устройства = добавление capabilities, не изменение кода плагинов.

### 8.3 Generator Optimization Patterns

#### 8.3.1 Conditional Resource Generation

```python
# topology-tools/plugins/generators/terraform_generator.py

CAPABILITY_RESOURCE_MAP = {
    # Network capabilities → Terraform resources
    "cap.net.overlay.vpn.wireguard.server": [
        "routeros_interface_wireguard",
        "routeros_interface_wireguard_peer",
    ],
    "cap.net.l2.segmentation.vlan.8021q": [
        "routeros_interface_vlan",
    ],
    "cap.net.service.dhcp.server": [
        "routeros_ip_dhcp_server",
        "routeros_ip_pool",
    ],

    # Operations capabilities → Management resources
    "cap.operations.snapshot.propagate": [
        "routeros_system_script.topology_metadata",
    ],
    "cap.operations.backup.routeros_export": [
        "routeros_scheduler.backup_schedule",
    ],

    # Compute capabilities → VM/LXC resources
    "cap.compute.runtime.container_host": [
        "proxmox_virtual_environment_container",
    ],
    "cap.compute.runtime.vm_host": [
        "proxmox_virtual_environment_vm",
    ],
}

def generate_resources(self, obj):
    resources = []
    for cap in obj.all_capabilities:
        if cap in CAPABILITY_RESOURCE_MAP:
            resources.extend(CAPABILITY_RESOURCE_MAP[cap])
    return resources
```

**Benefit:** Zero-code resource selection — capabilities drive output.

#### 8.3.2 Template Capability Guards

```jinja2
{# templates/mikrotik/main.tf.j2 #}

{% if "cap.net.overlay.vpn.wireguard.server" in capabilities %}
{% include "wireguard.tf.j2" %}
{% endif %}

{% if "cap.net.l2.segmentation.vlan.8021q" in capabilities %}
{% include "vlans.tf.j2" %}
{% endif %}

{% if "cap.operations.snapshot.propagate" in capabilities %}
{% include "topology_metadata.tf.j2" %}
{% endif %}

{% if "cap.net.service.dhcp.server" in capabilities %}
{% include "dhcp.tf.j2" %}
{% endif %}
```

**Benefit:** Templates become capability-composable building blocks.

### 8.4 Compiler Validation Integration

#### 8.4.1 Capability Contract Enforcement

```python
# topology-tools/plugins/validators/capability_validator.py

class CapabilityContractValidator:
    """Validates capability contracts at compile time."""

    def validate_object(self, obj, parent_class):
        errors = []

        # Check required capabilities
        for req_cap in parent_class.required_capabilities:
            if req_cap not in obj.enabled_capabilities:
                errors.append(f"E8001: Object {obj.id} missing required capability {req_cap}")

        # Check capability dependencies
        for cap in obj.enabled_capabilities:
            deps = CAPABILITY_DEPENDENCIES.get(cap, [])
            for dep in deps:
                if dep not in obj.enabled_capabilities:
                    errors.append(f"E8002: Capability {cap} requires {dep}")

        # Check capability conflicts
        for cap in obj.enabled_capabilities:
            conflicts = CAPABILITY_CONFLICTS.get(cap, [])
            for conflict in conflicts:
                if conflict in obj.enabled_capabilities:
                    errors.append(f"E8003: Capability {cap} conflicts with {conflict}")

        return errors

CAPABILITY_DEPENDENCIES = {
    "cap.net.overlay.vpn.wireguard.server": ["cap.net.l3.routing.static"],
    "cap.compute.clustering.ha": ["cap.compute.clustering.node"],
    "cap.operations.deploy.safe_mode": ["cap.os.routeros"],
}

CAPABILITY_CONFLICTS = {
    "cap.compute.node.edge": ["cap.compute.host.hypervisor"],
}
```

**Benefit:** Compile-time detection of capability contract violations.

#### 8.4.2 Instance Capability Validation

```python
def validate_instance(self, instance, parent_object):
    errors = []

    # Instance capabilities must be subset of object capabilities
    for cap in instance.enabled_capabilities:
        if cap not in parent_object.all_capabilities:
            errors.append(
                f"E8004: Instance {instance.id} declares capability {cap} "
                f"not available in object {parent_object.id}"
            )

    return errors
```

### 8.5 Ansible Inventory Integration

#### 8.5.1 Capability-Based Groups

```python
# topology-tools/plugins/generators/ansible_inventory_generator.py

def generate_capability_groups(self, instances):
    """Generate Ansible groups from capabilities."""
    groups = defaultdict(list)

    for inst in instances:
        for cap in inst.all_capabilities:
            # Convert capability to group name
            # cap.operations.backup.vzdump → cap_operations_backup_vzdump
            group_name = cap.replace(".", "_")
            groups[group_name].append(inst.hostname)

    return groups
```

**Generated inventory:**
```ini
[cap_operations_backup_routeros_export]
rtr-mikrotik-chateau

[cap_operations_backup_vzdump]
hv-proxmox-xps
lxc-postgresql
lxc-grafana

[cap_compute_runtime_container_host]
srv-orangepi5
vps-oracle-frankfurt
lxc-docker

[cap_os_debian]
hv-proxmox-xps
srv-orangepi5
lxc-postgresql
lxc-grafana

[cap_net_overlay_vpn_wireguard_server]
rtr-mikrotik-chateau
vps-oracle-frankfurt
```

**Usage:**
```bash
# Backup all vzdump-capable devices
ansible-playbook -l cap_operations_backup_vzdump playbooks/backup-vzdump.yml

# Deploy to all WireGuard servers
ansible-playbook -l cap_net_overlay_vpn_wireguard_server playbooks/wireguard-sync.yml

# Update all Debian systems
ansible-playbook -l cap_os_debian playbooks/apt-upgrade.yml
```

### 8.6 Service Placement Validation

#### 8.6.1 Service Requirements Model

```yaml
# topology/class-modules/class.service.prometheus.yaml
@class: class.service.prometheus
required_host_capabilities:
  all:
    - cap.os.linux
    - cap.os.init.systemd
  any:
    - cap.os.debian
    - cap.os.ubuntu
    - cap.os.alpine
conflicts_with_capabilities:
  - cap.os.routeros  # Cannot run on RouterOS
  - cap.os.windows   # Not supported
```

#### 8.6.2 Placement Validator

```python
def validate_service_placement(self, service_instance, host_instance):
    service_class = self.get_class(service_instance)
    host_caps = host_instance.all_capabilities

    # Check required_all
    for cap in service_class.required_host_capabilities.all:
        if cap not in host_caps:
            return Error(f"Host missing required capability {cap}")

    # Check required_any
    if service_class.required_host_capabilities.any:
        if not any(cap in host_caps for cap in service_class.required_host_capabilities.any):
            return Error(f"Host missing any of {service_class.required_host_capabilities.any}")

    # Check conflicts
    for cap in service_class.conflicts_with_capabilities:
        if cap in host_caps:
            return Error(f"Service conflicts with host capability {cap}")

    return OK
```

### 8.7 Plugin Discovery Optimization

#### 8.7.1 Capability-Based Plugin Filtering

```python
# topology-tools/kernel/plugin_loader.py

def filter_plugins_for_object(self, obj, all_plugins):
    """Return only plugins relevant to object's capabilities."""
    relevant = []

    for plugin in all_plugins:
        if not plugin.manifest.capability_filter:
            # Plugin applies to all objects
            relevant.append(plugin)
            continue

        filter = plugin.manifest.capability_filter

        # Check requires_any
        if filter.requires_any:
            if not any(self._matches(cap, obj.capabilities) for cap in filter.requires_any):
                continue  # Skip plugin

        # Check requires_all
        if filter.requires_all:
            if not all(self._matches(cap, obj.capabilities) for cap in filter.requires_all):
                continue  # Skip plugin

        relevant.append(plugin)

    return relevant
```

**Benefit:** O(plugins * objects) → O(relevant_plugins * objects) — performance optimization.

### 8.8 Documentation Generation

#### 8.8.1 Auto-Generated Capability Matrix

```python
# topology-tools/plugins/generators/docs_generator.py

def generate_capability_matrix(self, objects):
    """Generate markdown capability matrix."""

    # Collect all capabilities in use
    all_caps = set()
    for obj in objects:
        all_caps.update(obj.all_capabilities)

    # Group by domain
    domains = defaultdict(list)
    for cap in sorted(all_caps):
        domain = cap.split(".")[1]  # cap.DOMAIN.subdomain.name
        domains[domain].append(cap)

    # Generate matrix per domain
    for domain, caps in domains.items():
        self._render_matrix(domain, caps, objects)
```

**Generated output:**
```markdown
## Network Capabilities Matrix

| Device | WireGuard Server | VLAN | DHCP Server | DNS Resolver |
|--------|-----------------|------|-------------|--------------|
| MikroTik Chateau | ✓ | ✓ | ✓ | ✓ |
| GL.iNet Slate | ✓ | ✓ | ✓ | ✓ |
| Proxmox VE | ✗ | ✓ | ✗ | ✗ |
| Orange Pi 5 | ✗ | ✗ | ✗ | ✗ |

## Operations Capabilities Matrix

| Device | Backup | Safe-Mode | Snapshot Propagate | Recovery |
|--------|--------|-----------|-------------------|----------|
| MikroTik Chateau | routeros_export | ✓ | ✓ | state_restore |
| Proxmox VE | vzdump | ✗ | ✓ | partial_apply |
| Orange Pi 5 | config_archive | ✗ | ✓ | ✗ |
```

### 8.9 Implementation Roadmap

| Phase | Focus | Deliverables | Effort |
|-------|-------|--------------|--------|
| **Phase 1** | Plugin Manifest Extension | `capability_filter` in manifests | 4h |
| **Phase 2** | Compiler Validation | `capability_validator.py` plugin | 8h |
| **Phase 3** | Generator Integration | `CAPABILITY_RESOURCE_MAP`, template guards | 12h |
| **Phase 4** | Ansible Inventory | Capability-based groups | 4h |
| **Phase 5** | Service Placement | Host capability validation | 6h |
| **Phase 6** | Documentation | Capability matrix generator | 4h |
| **Total** | | | **38h** |

### 8.10 Expected Outcomes

| Metric | Before | After |
|--------|--------|-------|
| Lines of hardcoded vendor checks | ~50+ | 0 |
| Plugin code duplication | High | Low (capability handlers) |
| New device onboarding | Modify plugins | Add capabilities only |
| Compile-time error detection | Minimal | Full contract validation |
| Ansible targeting precision | Manual groups | Auto-generated from caps |
| Documentation freshness | Manual updates | Auto-generated |

---

## 9. CONCLUSION

The capabilities system provides a solid architectural foundation with well-defined namespaces, class contracts, and capability packs. However, significant gaps exist in:

1. **Generator utilization** - Capabilities are declared but not consumed
2. **Runtime enforcement** - No validation of capability contracts
3. **Consistent adoption** - Varying completeness across object modules

The highest-impact improvements are:
1. Capability-based Ansible inventory groups
2. Compiler validation of capability contracts
3. Operations capability implementation per ADR 0105

These changes would transform capabilities from documentation artifacts into active infrastructure-as-data primitives that drive code generation and validation.

---

## References

- ADR 0063: Plugin Microkernel Architecture
- ADR 0064: Software Stack Taxonomy (Firmware/OS Model)
- ADR 0074: V5 Generator Architecture
- ADR 0086: Flatten Plugin Hierarchy
- ADR 0105: Device State Commit and Rollback Contract
- `topology/class-modules/capability-catalog.yaml`
- `topology/class-modules/capability-packs.yaml`
- `topology-tools/plugins/generators/capability_helpers.py`
- `topology-tools/plugins/generators/projections.py`

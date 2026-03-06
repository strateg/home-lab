# ADR 0058: Core Abstraction Layer and Device Module Architecture

**Date:** 2026-03-06
**Status:** Superseded by ADR 0062
**Related:** ADR 0057 (MikroTik Netinstall Bootstrap)
**Superseded By:** [ADR 0062](0062-modular-topology-architecture-consolidation.md)

---

## Context

### Problem

The home-lab project has grown to support multiple device types (MikroTik routers, Proxmox hypervisors, Orange Pi SBCs) with distinct initialization, configuration, and management requirements. Currently, device-specific logic is interleaved with core infrastructure code, creating several issues:

1. **Tight coupling** — Adding a new device type (e.g., GL.iNet Slate AX1800, Ubiquiti switches) requires modifying core generators and validators
2. **Code duplication** — Similar patterns are reimplemented for each device type
3. **Testing difficulty** — Device-specific logic cannot be tested in isolation
4. **Reusability barrier** — The core topology model and validation logic could benefit other network modeling projects but is locked to specific hardware

### Observation

Network devices from different vendors perform the same logical functions at the network layer:

| Logical Concept | MikroTik Chateau | GL.iNet Slate | Ubiquiti Switch |
|-----------------|------------------|---------------|-----------------|
| Router | RouterOS config | OpenWrt config | N/A |
| Switch | Bridge + VLANs | Bridge + VLANs | UniFi config |
| Firewall | /ip firewall | iptables/nftables | ACLs |
| DHCP Server | /ip dhcp-server | dnsmasq | N/A |

The **what** (network topology, VLANs, firewall policies) is universal.
The **how** (configuration syntax, initialization scripts, API protocols) is vendor-specific.

### Harmonization Note (2026-03-06)

This ADR remains the historical foundation for core/module separation and coupling analysis.
Terminology and contracts are refined by later ADRs:

- ADR 0059 defines the canonical `Class -> Object -> Instance` model
- ADR 0060 defines the YAML-to-JSON compiler and structured diagnostics contract

Terminology mapping from this ADR to ADR 0059:

- `abstract type` -> `Class`
- `implementation` -> `Object`
- concrete topology device entry -> `Instance`

### Current State Analysis

#### Base Layer Components (Device-Agnostic)

| Component | Location | Description |
|-----------|----------|-------------|
| Topology Loading | `topology-tools/topology_loader.py` | YAML parsing with `!include` |
| Generator Base | `scripts/generators/common/base.py` | `Generator` protocol, `GeneratorCLI` |
| IP Resolver | `scripts/generators/common/ip_resolver_v2.py` | Reference-based IP resolution |
| Validation Framework | `scripts/validators/` | `ValidationCheckBase`, runner |
| Docs Generator | `scripts/generators/docs/` | Mermaid diagrams, network docs |
| Ansible Inventory | `generate-ansible-inventory.py` | Host/group generation |

**Estimated:** ~55-60% of codebase

#### Device-Specific Components

| Component | Location | Vendor |
|-----------|----------|--------|
| Terraform MikroTik | `scripts/generators/terraform/mikrotik/` | MikroTik |
| Terraform Proxmox | `scripts/generators/terraform/proxmox/` | Proxmox |
| Bootstrap MikroTik | `scripts/generators/bootstrap/mikrotik/` | MikroTik |
| Bootstrap Proxmox | `scripts/generators/bootstrap/proxmox/` | Proxmox |
| Bootstrap OrangePi5 | `scripts/generators/bootstrap/orangepi5/` | Orange Pi |
| Templates | `templates/terraform/*/`, `templates/bootstrap/*/` | All |

**Estimated:** ~40-45% of codebase

#### Critical Coupling Points

| Issue | File | Impact |
|-------|------|--------|
| Mixed resolvers | `terraform/resolvers.py` | Proxmox + MikroTik logic in one file |
| Hardcoded device types | `validators/checks/foundation.py` | Assumes specific device roles |
| Workload-type caches | `common/ip_resolver_v2.py` | Proxmox-specific LXC/VM types |
| No bootstrap base class | `bootstrap/*/generator.py` | Each device reimplements extraction |

---

## Decision

### 1. Adopt Two-Layer Architecture

Split the system into:

1. **Core Layer** (`topology-core/`) — Abstract network modeling primitives
2. **Implementation Layer** (`topology-modules/`) — Vendor-specific generators and templates

```
home-lab/
├── topology-core/                    # Base layer (future: separate repo)
│   ├── schemas/                      # Abstract JSON schemas
│   │   ├── device.schema.json        # Generic device: router, switch, server
│   │   ├── network.schema.json       # VLAN, subnet, firewall policy
│   │   └── workload.schema.json      # VM, container, service
│   ├── validators/                   # Device-agnostic validation
│   │   ├── base.py
│   │   ├── network.py
│   │   ├── references.py
│   │   └── governance.py
│   ├── generators/                   # Abstract generator protocols
│   │   ├── base.py                   # Generator, GeneratorCLI
│   │   ├── terraform_base.py         # TerraformGeneratorBase
│   │   └── bootstrap_base.py         # BootstrapGeneratorBase
│   ├── resolvers/                    # IP, reference resolution
│   │   └── ip_resolver.py
│   └── docs/                         # Device-agnostic documentation
│       └── generator.py
│
├── topology-modules/                 # Device-specific implementations
│   ├── mikrotik/
│   │   ├── __init__.py
│   │   ├── terraform/
│   │   │   ├── generator.py          # Extends TerraformGeneratorBase
│   │   │   ├── resolvers.py          # MikroTik-specific data extraction
│   │   │   └── templates/
│   │   └── bootstrap/
│   │       ├── generator.py          # Extends BootstrapGeneratorBase
│   │       └── templates/
│   ├── proxmox/
│   │   ├── terraform/
│   │   └── bootstrap/
│   ├── orangepi5/
│   │   └── bootstrap/
│   └── glinet/                       # Future: GL.iNet support
│       ├── terraform/
│       └── bootstrap/
│
├── abstract-topology/                # Reference topology (abstract devices)
│   ├── topology.yaml
│   └── L0-L7.yaml
│
├── topology/                         # Concrete topology (real devices)
│   ├── topology.yaml
│   └── L0-L7.yaml
│
└── topology-tools/                   # Orchestration (uses core + modules)
    ├── regenerate-all.py
    ├── validate-topology.py
    └── generate-*.py
```

### 2. Define Abstract Device Types

Core layer defines abstract device roles:

```yaml
# topology-core/schemas/device-types.yaml
device_types:
  router:
    description: "Layer 3 packet forwarding device"
    capabilities:
      - routing
      - nat
      - firewall
      - dhcp_server
      - vpn_endpoint

  switch:
    description: "Layer 2 frame forwarding device"
    capabilities:
      - vlan
      - spanning_tree
      - port_mirroring

  hypervisor:
    description: "Virtualization host"
    capabilities:
      - vm_hosting
      - container_hosting
      - storage_management

  sbc:
    description: "Single-board computer"
    capabilities:
      - container_hosting
      - service_hosting
```

Concrete devices inherit from abstract types:

```yaml
# topology/L1-foundation.yaml
devices:
  - id: rtr-mikrotik-chateau
    type: router                      # Abstract type
    implementation: mikrotik          # Module reference
    model: "Chateau LTE7 ax"
    capabilities:
      - routing
      - nat
      - firewall
      - container_hosting             # Device-specific capability
```

### 3. Create Generator Plugin System

Base generators define extension points:

```python
# topology-core/generators/terraform_base.py
class TerraformGeneratorBase(Generator):
    """Base class for Terraform generators."""

    @abstractmethod
    def get_device_type(self) -> str:
        """Return the device type this generator handles."""
        pass

    @abstractmethod
    def extract_device_data(self, topology: dict) -> dict:
        """Extract device-specific data from topology."""
        pass

    def pre_generation(self, context: GeneratorContext) -> None:
        """Hook for device-specific preprocessing."""
        pass

    def generate(self) -> dict:
        """Standard generation workflow."""
        self.pre_generation(self.context)
        data = self.extract_device_data(self.topology)
        return self.render_templates(data)
```

Device modules implement the protocol:

```python
# topology-modules/mikrotik/terraform/generator.py
class MikrotikTerraformGenerator(TerraformGeneratorBase):

    def get_device_type(self) -> str:
        return "mikrotik"

    def extract_device_data(self, topology: dict) -> dict:
        return {
            "interfaces": self._extract_interfaces(),
            "firewall": self._extract_firewall(),
            "vlans": self._extract_vlans(),
            # ...MikroTik-specific extraction
        }
```

### 4. Abstract Topology for Testing

Create `abstract-topology/` with generic device definitions:

```yaml
# abstract-topology/L1-foundation.yaml
devices:
  - id: router-main
    type: router
    implementation: generic           # No specific vendor
    interfaces:
      - id: wan
        type: ethernet
      - id: lan
        type: bridge

  - id: switch-core
    type: switch
    implementation: generic
    ports: 24
    vlans: [10, 20, 30]
```

This enables:
- Testing core validators without device-specific modules
- Documenting network architecture independently of hardware
- Planning migrations between vendors

### 5. Module Discovery and Registration

Modules self-register with the core:

```python
# topology-modules/mikrotik/__init__.py
from topology_core.registry import register_module

register_module(
    name="mikrotik",
    device_types=["router", "switch"],
    generators={
        "terraform": "mikrotik.terraform.generator:MikrotikTerraformGenerator",
        "bootstrap": "mikrotik.bootstrap.generator:MikrotikBootstrapGenerator",
    },
    validators=[
        "mikrotik.validators:MikrotikConfigValidator",
    ],
)
```

Core discovers modules at runtime:

```python
# topology-core/registry.py
def get_generator(device_type: str, generator_type: str) -> Generator:
    """Get appropriate generator for device and generation type."""
    module = REGISTRY.get(device_type)
    if not module:
        raise UnknownDeviceType(device_type)
    return module.generators[generator_type]()
```

---

## Migration Plan

### Phase 1: Extract Core Interfaces (Week 1-2)

1. Create `topology-core/generators/base.py` with `TerraformGeneratorBase`, `BootstrapGeneratorBase`
2. Create `topology-core/validators/base.py` with abstract validation protocols
3. Split `terraform/resolvers.py` into device-specific files
4. Add `pre_generation()` hook to existing generators

**Deliverables:**
- Core interfaces defined
- Existing generators refactored to use base classes
- No functional changes to generation output

### Phase 2: Create Module Structure (Week 3-4)

1. Create `topology-modules/` directory structure
2. Move MikroTik-specific code to `topology-modules/mikrotik/`
3. Move Proxmox-specific code to `topology-modules/proxmox/`
4. Move OrangePi5-specific code to `topology-modules/orangepi5/`
5. Update imports in `topology-tools/`

**Deliverables:**
- Clear separation of core vs device-specific code
- Module structure established
- Existing functionality preserved

### Phase 3: Abstract Topology (Week 5-6)

1. Create `abstract-topology/` with generic device definitions
2. Define abstract device type schema
3. Add `implementation` field to concrete topology
4. Update validators to support both abstract and concrete topologies

**Deliverables:**
- Abstract topology usable for documentation and planning
- Concrete topology continues to work unchanged

### Phase 4: Module Registry (Week 7-8)

1. Implement module discovery system
2. Add module registration in each device module
3. Update orchestration scripts to use registry
4. Document module creation process

**Deliverables:**
- Dynamic module loading
- Clear path for adding new device support

### Phase 5: Repository Split Evaluation (Future)

After stabilization, evaluate splitting into:
- `topology-core` — Standalone package for network modeling
- `home-lab` — This project, using topology-core as dependency

---

## Consequences

### Positive

1. **Extensibility** — Adding GL.iNet, Ubiquiti, or other vendors requires only a new module
2. **Testability** — Core logic testable without device-specific dependencies
3. **Reusability** — Core layer usable for other network modeling projects
4. **Clarity** — Clear separation of "what" (topology) from "how" (device config)
5. **Maintainability** — Device-specific bugs isolated to their modules

### Negative

1. **Complexity** — Additional abstraction layers increase cognitive load
2. **Migration effort** — Significant refactoring of existing code
3. **Documentation** — Need to document both core concepts and device modules
4. **Testing** — Need integration tests across core + modules

### Trade-offs

1. **Abstraction depth** — Too abstract loses device-specific optimizations; too concrete loses reusability
2. **Module granularity** — One module per vendor vs one per device model
3. **Schema strictness** — Strict abstract schema vs flexible device-specific extensions

---

## Open Questions

1. Should modules be Python packages installable via pip, or local directories?
2. How to handle device capabilities that don't map to abstract types?
3. Should abstract-topology support simulation/emulation for testing?
4. How to version core independently from modules?

---

## References

- Current project structure analysis (see below)
- ADR 0057: MikroTik Netinstall Bootstrap
- Superseded by ADR 0059 for model contract details
- Extended by ADR 0060 for compiler/diagnostics execution contract
- [Terraform Provider Plugin Architecture](https://developer.hashicorp.com/terraform/plugin)
- [Ansible Collection Structure](https://docs.ansible.com/ansible/latest/dev_guide/developing_collections.html)

---

## Appendix: Current Coupling Analysis

### Files Requiring Refactoring

| Priority | File | Issue | Target |
|----------|------|-------|--------|
| Critical | `terraform/resolvers.py` | Mixed Proxmox + MikroTik | Split to modules |
| High | `validators/checks/network.py` | Hardcoded network patterns | Abstract network model |
| High | `bootstrap/*/generator.py` | No base class | Create BootstrapGeneratorBase |
| Medium | `common/ip_resolver_v2.py` | Workload-type caches | Abstract ComputeTarget |
| Medium | `validators/checks/foundation.py` | Hardcoded device roles | Extensible role system |
| Low | `docs/generator.py` | Some device assumptions | Parameterize device rendering |

### Module Boundary Definition

**Core Layer Owns:**
- Topology YAML structure and loading
- L0-L7 layer semantics
- Cross-reference validation
- IP allocation and resolution
- Documentation generation (device-agnostic parts)
- Generator/validator protocols

**Device Modules Own:**
- Terraform resource generation
- Bootstrap script generation
- Device-specific templates
- Vendor API interactions
- Device-specific validation rules

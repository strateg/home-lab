# ADR 0019: Proxmox Answer Generator Uses Layered Topology Only (No Legacy Root Sections)

- Status: Superseded by [0028](0028-topology-tools-architecture-consolidation.md)
- Date: 2026-02-21

## Context

`topology-tools/generate-proxmox-answer.py` still relied on legacy root-level topology paths
(`physical_topology`, `logical_topology`, `metadata`, `security`) after migration to layered topology.

This created false validation warnings and brittle behavior because authoritative data now lives in L0..L7.

## Decision

1. Remove legacy root-path reads from Proxmox answer generator.
2. Use layered sources only:
   - Proxmox node inventory: `L1_foundation.devices`
   - Management IP/network: `L2_network.networks`
   - Disk mapping: `L3_data.storage` (via `disk_ref` -> `os_device`)
   - DNS domain for FQDN: `L5_application.dns.zones`
   - Root password hash: `L7_operations.security.proxmox.root_password_hash`
3. Keep hardcoded password hash as explicit fallback only when L7 value is not defined.

## Consequences

Benefits:

- Topology interpretation matches layered architecture.
- No hidden dependence on removed/legacy root keys.
- Validation output is cleaner and deterministic for v4 topology.

Trade-offs:

- Generator now requires layered sections (`L0`, `L1`, `L2`, `L3`, `L5`, `L7`) to exist.
- Mixed legacy topologies are no longer a supported input for this generator.

Compatibility:

- CLI usage remains unchanged.
- Output structure (`answer.toml`) remains compatible.

## References

- File:
  - `topology-tools/generate-proxmox-answer.py`

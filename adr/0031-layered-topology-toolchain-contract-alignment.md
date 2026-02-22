# ADR 0031: Layered Topology Toolchain Contract Alignment

- Status: Proposed
- Date: 2026-02-22

## Context

Repository architecture is built around layered topology (`L0..L7`) as the single source of truth.
Validation of `topology.yaml` passes in strict mode, but there are contract gaps between model, generators, and operational scripts:

1. Generated MikroTik Terraform may reference non-existent address-lists and non-runtime interface names.
2. Ansible deployment phase can fall back to legacy inventory due to path mismatch with generated inventory.
3. Generator logic still relies on deprecated/legacy fields in places where new runtime/layered fields are canonical.
4. Documentation generation shows partial data loss for service ports and device memory due to schema-to-template field mismatch.
5. Cross-layer semantic checks are incomplete for some L6/L7 references and backup storage references.

As a result, topology may be syntactically valid but operationally inconsistent after generation.

## Decision

Adopt a strict toolchain contract: all generated artifacts and deployment flows must be derived from layered topology fields only, with no implicit legacy fallbacks.

The contract is defined as follows:

1. Canonical runtime binding:
   - Services are bound via `L5_application.services[].runtime`.
   - L4 workload grouping/generation must not depend on deprecated `lxc.type` / `lxc.role`.

2. Canonical endpoint modeling:
   - Service endpoint fields must be normalized (single canonical representation for `port`/`ports` and protocol mapping).
   - Documentation and dependency outputs must consume normalized model only.

3. Canonical network-to-firewall mapping:
   - MikroTik firewall generation must emit address-lists for every referenced trust zone or network.
   - Interface names in generated RouterOS resources must map to runtime-valid RouterOS interface names.

4. Canonical deployment inputs:
   - Deployment scripts must use generated inventory location as primary path and fail fast on mismatch.
   - Legacy static inventory is allowed only as an explicit compatibility mode.

5. Canonical semantic validation:
   - Validator must enforce cross-layer semantic references used by operations:
     - backup `storage_ref` -> L3 storage endpoint IDs,
     - alert trigger references to observability entities,
     - workflow command/script path existence and expected working directories.

6. Secret handling boundary:
   - Sensitive values in topology must be represented as vault/secret references, not inline materialized secrets.

## Consequences

Benefits:

- Reduced drift between architecture model and executable artifacts.
- Fewer runtime failures during `terraform apply` / `ansible-playbook`.
- Clear migration path away from legacy field assumptions.
- Higher confidence in generated documentation as an operational artifact.

Trade-offs:

- Generator and validator refactoring work is required across multiple modules.
- Some current fields and fallback behaviors will be deprecated and removed.
- CI checks may become stricter and fail existing workflows until migration is complete.

Migration impact:

1. Introduce contract checks in validator first (non-breaking in compatibility mode, strict in mainline).
2. Update generators/templates to consume canonical fields.
3. Update deploy scripts to generated inventory path contract.
4. Remove implicit legacy fallbacks after compatibility window.

## References

- Topology root: `topology.yaml`
- Layer guides: `topology/MODULAR-GUIDE.md`
- Validator entrypoint: `topology-tools/validate-topology.py`
- Proxmox generator: `topology-tools/scripts/generators/terraform/proxmox/generator.py`
- MikroTik generator: `topology-tools/scripts/generators/terraform/mikrotik/generator.py`
- Docs generator: `topology-tools/scripts/generators/docs/generator.py`
- Ansible inventory generator: `topology-tools/generate-ansible-inventory.py`
- Deployment phases: `deploy/phases/03-services.sh`
- Related ADRs:
  - [0026](0026-l3-l4-taxonomy-refactoring-storage-chain-and-platform-separation.md)
  - [0028](0028-topology-tools-architecture-consolidation.md)
  - [0029](0029-storage-taxonomy-and-layer-boundary-consolidation.md)
  - [0030](0030-l2-network-layer-enhancements.md)

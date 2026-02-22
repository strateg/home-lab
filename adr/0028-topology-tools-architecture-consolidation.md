# ADR 0028: Consolidate topology-tools Architecture and Module Boundaries

- Status: Accepted
- Date: 2026-02-22
- Supersedes:
  - [0017](0017-topology-tools-modular-refactor-validation-generation.md)
  - [0018](0018-generation-common-loader-and-output-preparation.md)
  - [0019](0019-proxmox-answer-layered-topology-only.md)
  - [0020](0020-topology-tools-scripts-domain-layout.md)
  - [0021](0021-docs-generation-moved-to-scripts-generation-docs.md)
  - [0022](0022-docs-diagram-module-canonical-location.md)
  - [0023](0023-terraform-generators-and-templates-domain-layout.md)
  - [0024](0024-validators-namespace-alignment.md)
  - [0025](0025-generator-protocol-and-cli-base-class.md)

## Context

`topology-tools` architecture evolved through several incremental ADRs while modularization was actively in progress.
The implementation is now stable, but decision context is fragmented across many small ADRs.

This creates practical friction:

1. Contributors must read many files to understand the current module contract.
2. The ADR register is noisy relative to the current steady-state architecture.
3. Repeated refinements to the same boundary are spread across separate ADRs.

## Decision

1. Canonical top-level architecture for `topology-tools` is:
   - `schemas/`
   - `templates/` (and domain-specific template roots where already adopted)
   - `scripts/`
2. Canonical code domains under `scripts/` are:
   - `scripts/generators/`
   - `scripts/validators/`
   - shared/common helper modules as required by those domains.
3. Top-level executables (`topology-tools/*.py`) remain stable compatibility entry points and delegate to domain modules.
4. Generators use shared loading/output preparation helpers and common CLI abstractions.
5. Generator interface contract is explicit (protocol/base class pattern), not ad-hoc duck typing.
6. Layered topology (L0-L7) is the authoritative input model for generators; legacy root sections are non-canonical.
7. Validator package namespace remains `scripts/validators` as the canonical validation domain.

## Consequences

Benefits:

- One canonical ADR for `topology-tools` structure and extension rules.
- Faster onboarding and lower navigation overhead.
- Stable CLI surface with modular internals.

Trade-offs:

- Historical migration rationale is now mostly in superseded ADRs.
- Future changes in this domain should update this ADR unless a new boundary is introduced.

## References

- Replaced ADRs:
  - [0017](0017-topology-tools-modular-refactor-validation-generation.md)
  - [0018](0018-generation-common-loader-and-output-preparation.md)
  - [0019](0019-proxmox-answer-layered-topology-only.md)
  - [0020](0020-topology-tools-scripts-domain-layout.md)
  - [0021](0021-docs-generation-moved-to-scripts-generation-docs.md)
  - [0022](0022-docs-diagram-module-canonical-location.md)
  - [0023](0023-terraform-generators-and-templates-domain-layout.md)
  - [0024](0024-validators-namespace-alignment.md)
  - [0025](0025-generator-protocol-and-cli-base-class.md)
- Canonical code paths:
  - `topology-tools/scripts/generators/`
  - `topology-tools/scripts/validators/`
  - `topology-tools/*.py`

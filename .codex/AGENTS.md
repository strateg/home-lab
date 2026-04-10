# Codex Agent Configuration

This file is a Codex-specific adapter/bootloader for the repository rule system. It must not become a separate architectural source of truth.

## Mandatory Load Order

1. Read `docs/ai/AGENT-RULEBOOK.md` as the compact ADR-derived rulebook.
2. Use `docs/ai/ADR-RULE-MAP.yaml` to select scoped rule packs under `docs/ai/rules/`.
3. Load `.codex/rules/tech-lead-architect.md` only as a Codex role overlay.
4. If this adapter conflicts with ADRs or the universal rulebook, ADRs and `docs/ai/AGENT-RULEBOOK.md` win.

## Role

Operate as a pragmatic Tech Lead Architect for this infrastructure-as-data repository. Enforce architecture through the universal rulebook, ADRs, and validation evidence rather than through local-only policy.

Intervene when:

- architectural decisions are being made;
- infrastructure design is modified;
- topology, generator, deploy, or validation contracts change;
- Terraform or Ansible artifact behavior changes;
- new services are introduced;
- refactoring is proposed.

## Repository Guardrails

- Active lane is repository root layout: `topology/`, `topology-tools/`, `projects/`, `tests/`, `scripts/`, `taskfiles/`.
- Legacy `v4` baseline is archived under `archive/v4/` and treated as frozen reference.
- Do not create or use root `v4/` or root `v5/` directories.
- Do not create or modify files under `archive/v4/` unless the user explicitly requests a `v4` hotfix/parity check.
- Do not edit `generated/` as the source of a fix; modify sources and regenerate.
- Architecture-changing work is not complete until ADR documentation and `adr/REGISTER.md` are updated when required.

## Plugin Runtime Contract

ADR0086 supersedes the old runtime 4-level visibility policy from ADR0063 Section 4B. Runtime safety is enforced by lifecycle stage, manifest contracts, deterministic discovery order, and tests.

- Applies to all plugin families (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).
- Runtime lifecycle has 6 stages: `discover -> compile -> validate -> generate -> assemble -> build`.
- Stage affinity must be preserved: `discover -> discoverers`, `compile -> compilers`, `validate -> validators`, `generate -> generators`, `assemble -> assemblers`, `build -> builders`.
- Plugin data exchange must be declared through manifest contracts: `depends_on`, `consumes`, and `produces`.
- Discovery order remains framework -> class -> object -> project.
- Class/object module placement is an ownership convention, not a runtime visibility ACL.

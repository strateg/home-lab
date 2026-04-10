# Tech Lead Architect Rules

This file is a Codex role overlay. It routes to the universal AI rulebook and must not define divergent architecture policy.

Required sources:

- `docs/ai/AGENT-RULEBOOK.md`
- `docs/ai/ADR-RULE-MAP.yaml`
- relevant scoped rule packs under `docs/ai/rules/`
- ADRs when a compact rule is ambiguous or architecture changes

If this file conflicts with ADRs or `docs/ai/AGENT-RULEBOOK.md`, the ADR and universal rulebook prevail.

---

## Core Architectural Model

This repository uses an infrastructure-as-data model.

Active source-of-truth inputs are:

- `topology/topology.yaml`
- `topology/class-modules/`
- `topology/object-modules/`
- `projects/<project>/topology/instances/`

Generated Terraform, Ansible, bootstrap, and documentation outputs are not source-of-truth inputs. Never use manual edits to `generated/` as the fix.

---

## Responsibility Boundaries

Terraform manages infrastructure provisioning concerns such as Proxmox resources, storage, networks, and hardware-resource allocation.

Ansible manages OS configuration, service configuration, and runtime configuration.

Generators implement deterministic transformation logic from validated topology/model inputs to generated artifacts.

---

## Plugin Runtime Contract

ADR0086 supersedes the old runtime 4-level visibility policy from ADR0063 Section 4B. Plugin safety is enforced through runtime lifecycle, stage affinity, manifest contracts, discovery order, and tests.

- Applies to all plugin families (`discoverers`, `compilers`, `validators`, `generators`, `assemblers`, `builders`).
- Runtime lifecycle has 6 stages: `discover -> compile -> validate -> generate -> assemble -> build`.
- Stage affinity must be preserved: `discover -> discoverers`, `compile -> compilers`, `validate -> validators`, `generate -> generators`, `assemble -> assemblers`, `build -> builders`.
- Manifest contracts are mandatory: `depends_on`, `consumes`, and `produces`.
- Discovery order is framework -> class -> object -> project.
- Class/object module placement is an ownership convention, not a runtime visibility ACL.
- Shared standalone plugins belong in `topology-tools/plugins/<family>/`.

---

## Evaluation Framework

Evaluate changes against:

1. source-of-truth integrity;
2. regeneration capability;
3. responsibility separation;
4. maintainability;
5. hardware constraints;
6. consistency with ADRs and scoped rule packs;
7. validation evidence.

---

## Hardware Constraint Awareness

Current lab hardware is constrained. Treat resource sizing changes as topology/model changes and validate them through the relevant topology and deploy gates.

Prefer LXC over VM when appropriate for the workload and supported by the topology model.

---

## ADR Governance

Architecture decisions must be tracked in ADRs.

For every new architecture decision:

1. Create or update the appropriate ADR file in `adr/`.
2. Update `adr/REGISTER.md`.
3. Keep deep plans and evidence in `adr/NNNN-analysis/` when the content would bloat the ADR.
4. State clearly when a change is non-architectural: `ADR: not required`.

---

## Review Protocol

When reviewing, prioritize findings over narrative. Include:

- architectural assessment;
- specific issues with file references;
- recommended changes;
- implementation guidance;
- risks;
- validation steps.

---

## Anti-Patterns To Block

- Manual edits to generated Terraform/Ansible as the source of a fix.
- Hardcoded infrastructure data outside source-of-truth topology/model inputs.
- Duplication of infrastructure definitions.
- Imperative infrastructure scripts that bypass the compiler/runtime contracts.
- Hidden plugin coupling outside manifest contracts.
- Editing frozen `archive/v4/` without explicit user approval.
- Creating root `v4/` or root `v5/` directories.

---

## Migration Lane Rule

- Active lane is repository root layout.
- Legacy `v4` is frozen under `archive/v4/` and used only as baseline/reference.
- Default behavior: no file creation or modification under `archive/v4/`.
- Do not create or use root `v4/` or root `v5/` directories.
- All ongoing migration work must target root layout: `topology/`, `topology-tools/`, `projects/`, `tests/`, `scripts/`, `taskfiles/`.
- Touch `archive/v4/` only when the user explicitly asks for a `v4` fix/parity check.

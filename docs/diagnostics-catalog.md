# Diagnostics Catalog (Canonical)

**Updated:** 2026-09-11
**Source of truth:** `topology-tools/data/error-catalog.yaml`

---

## Purpose

This document provides a human-readable index of diagnostic code ownership and non-overlap rules.

For exact titles/hints/severity, always use:

- `topology-tools/data/error-catalog.yaml`

---

## Core Ranges

Corrected 2026-09-11 against the catalog and the emitting source. The previous
list named five families and omitted four that are in daily use, including the
whole of `E8xxx`; a range map that does not describe the system cannot be used to
choose a free number, which is how collisions get made.

- `E1xxx`: load/parse/config shape errors
- `E2xxx`: reference resolution, duplicates, profile and model-lock contracts
- `E3xxx`: manifest/model contract errors
- `E4xxx`: plugin lifecycle, scheduling and crash reporting
- `E5xxx`: secrets and deployment-input contracts
- `E6xxx`: compile/model consistency errors
- `E7xxx`: layer/relation/instance contract errors
- `E8xxx`: kernel envelope, semantic-key and build/release contracts
- `E9xxx`: generator-family errors

`W` and `I` codes mirror these families at warning and info severity; they are
part of the same numbering space and collide the same way.

### Occupancy, measured 2026-09-11

`E78xx` holds 93 of its 100 numbers and is where ADR 0110 and ADR 0111 live. It
is full, and the fourteen collisions still inside it are the consequence. Do not add to
it. `E70xx` was the only empty band inside `E7xxx` and is now allocated below.

Two ledgers are frozen in `tests/test_diagnostic_code_registry.py`: 274 codes
that are emitted without a catalog entry, and 30 that are emitted with unrelated
meanings by different modules. Both may shrink; neither may grow. The debt is
recorded rather than paid because writing 274 titles by machine would fill the
catalog with entries nobody chose.

Both numbers grew when the checker was corrected on the same day. Its `SCAN_DIRS`
omitted the top level of `topology-tools/`, so every code emitted by
`compile-topology.py`, `compiler_runtime.py` and `framework_lock.py` was invisible
to it - hiding 4 unregistered codes and 11 collisions, among them the whole
`E7821..E7827` framework-lock family colliding with network validators. A registry
check that does not read the compiler measures the wrong system, and a clean
report from one is not evidence.

---

## Reserved Family Ranges

- `I31xx`: Ansible role generator (ADR 0104)
- `E91xx`: Terraform Proxmox generator
- `E92xx`: Terraform MikroTik generator
- `E93xx`: Ansible inventory generator
- `E94xx`: Bootstrap Proxmox generator
- `E95xx`: Bootstrap MikroTik generator
- `E96xx`: Bootstrap Orange Pi generator

---

## Strict-Only Project Contract

`E7808` is reserved for strict-only project contract enforcement:

- `E7808`: legacy `paths.*` contract detected (unsupported in strict-only mode)

Compatibility/versioning range for framework/project contract:

- `E7811`: framework version too old
- `E7812`: project schema not supported
- `E7813`: contract migration required

Note: `E7811..E7813` are cataloged and reserved; runtime activation is staged with ADR 0076 work.

---

## Framework Distribution Contract (ADR 0076)

Reserved range `E7821..E7828` for framework dependency/lock hard errors:

- `E7821`: framework dependency not resolvable
- `E7822`: framework lock missing in strict mode
- `E7823`: lock revision mismatch
- `E7824`: integrity hash mismatch
- `E7825`: missing or invalid artifact signature
- `E7826`: missing provenance attestation
- `E7827`: lock contract violation
- `E7828`: SBOM missing

Info code for dev profile:

- `I7829`: framework.lock.yaml auto-regenerated (dev profile only, triggered by E7824 mismatch)

Note: These codes are reserved; runtime implementation is staged per `adr/plan/0076-multi-repo-extraction-plan.md`.

---

Notes:

1. `E7801..E7805` are already used by L1 power source relation validation.
2. New framework/project diagnostics MUST avoid collisions with existing `E780x` assignments.

---

## Universal Container Network Model (ADR 0118 / ADR 0119)

Allocated range `E70xx` / `W70xx` / `I70xx`, 2026-09-11 at gate G1.

ADR 0118 D7 withdrew the numeric ranges first suggested in that document and
required allocation "with a collision test" at implementation time, with
diagnostics identified until then by semantic obligation ID plus a provisional
`NET-*`/`SEC-*` prefix. This is that allocation. The check that justified the
band: `E70xx` was the only hundred inside `E7xxx` with no number claimed by
source, catalog, ADR or documentation.

- `E7001..E7006`: schema and shape of a v2 network intent block
- `E7020..E7023`: attachments and address domains (`NET-ATTACHMENT`, `NET-ADDRESS-OWNER`)
- `E7040..E7042`: publications, which are delivery facts and authorize nothing
- `E7060..E7064`: policies and bindings (`NET-POLICY-BINDING`, `SEC-AUTH` authoring)
- `E7080..E7089`: plan order and the ADR 0119 obligations `SEC-ORDER`, `SEC-AUTH`,
  `SEC-AVAIL`, `SEC-PATH`, `SEC-NAT`, `SEC-STATE`, `SEC-TRANSITION`, `SEC-CAP`

Numbers are registered only where a rule exists to raise them. The gaps between
the sub-ranges are deliberate room for the neighbouring family, not reservations
for diagnostics nobody has specified; ADR 0118 D7 rejects speculative tables.

### Erratum: `E7854` and the terminal drop-all

ADR 0110 section 4.4 assigns `E7854` to "final drop-all rule missing in generated
Terraform", owned by a `security_matrix_validator`. Two things are wrong with
that entry:

1. `E7854` was already taken. `storage_media_inventory_validator` has emitted it
   since 2026-03-24; ADR 0110 claimed it on 2026-06-22, three months later.
2. No `security_matrix_validator` exists, and no module emits `E7854` for a
   drop-all. The assignment was never implemented.

Governance rule 1 makes codes immutable once released, so the storage validator
keeps `E7854`. **The terminal default deny is `E7082`.** ADR 0118 D4.1, ADR 0119
D4, `class.network.firewall_policy` and `docs/ai/rules/network-security.md` refer
to the new code; ADR 0110's table entry is superseded by this erratum.

A source-only scan cannot find a conflict of this kind - only one module emits
the code, so there is nothing to collide with. It was found by reading the ADR
against the implementation, and `tests/test_diagnostic_code_registry.py` now
holds it in place.

---

## Governance Rules

1. Diagnostic codes are immutable once released.
2. Reuse of retired codes is forbidden.
3. New ranges must be registered before implementation.
4. CI should fail on duplicate code ownership.

---

## References

- `adr/0074-v5-generator-architecture.md`
- `adr/0075-framework-project-separation.md`
- `adr/0076-framework-distribution-and-multi-repository-extraction.md`

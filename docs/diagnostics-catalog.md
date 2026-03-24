# Diagnostics Catalog (Canonical)

**Updated:** 2026-03-20
**Source of truth:** `v5/topology-tools/data/error-catalog.yaml`

---

## Purpose

This document provides a human-readable index of diagnostic code ownership and non-overlap rules.

For exact titles/hints/severity, always use:

- `v5/topology-tools/data/error-catalog.yaml`

---

## Core Ranges

- `E1xxx`: load/parse/config shape errors
- `E3xxx`: manifest/model contract errors
- `E6xxx`: compile/model consistency errors
- `E7xxx`: layer/relation/instance contract errors
- `E9xxx`: generator-family errors

---

## Reserved Family Ranges

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

Note: These codes are reserved; runtime implementation is staged per `adr/plan/0076-multi-repo-extraction-plan.md`.

---

Notes:

1. `E7801..E7805` are already used by L1 power source relation validation.
2. New framework/project diagnostics MUST avoid collisions with existing `E780x` assignments.

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

# ADR 0118/0119 SPC rebuild record — 2026-09-10 (rev 2)

Status: change record for a **Proposed** architecture. No topology, compiler,
generator, deploy code, secret, framework lock or device configuration changed.
No migration, no apply, no backend qualification.

## Reference

The pre-rebuild edition is preserved in git as commit
`c788237e379a32150ad328b2596cf86678981edc` on branch `development`. Nothing in
that edition was deleted or reinterpreted silently: every change below is an
addition or an explicit reference to an already implemented ADR. No decision
`D1`-`D7` of either ADR was withdrawn, and no numeric value was altered.

## Method

Strict Process Compliance per `docs/ai/spc-contract.md`, steps 0-7. The rebuild
implements only the mechanisms approved after step 5:

| Approved mechanism | Meaning |
|---|---|
| Full in-document set | Clusters A, B, C, D, E, G; topology data changes excluded |
| Budget plus comparison | Both an absolute authoring budget and a comparison to the current surface, with a written exception procedure |
| Translation table plus derive-review-freeze | Legacy outcomes stated explicitly, and candidates that never authorize traffic before human approval |
| Object defaults plus derived-field list | Reuse on the object level, and an enumerated set of fields the author never writes |

Mechanisms classified as requiring topology data, a backend property or a human
owner decision were **not** executed. They remain open, listed below.

## Changes by file

| File | Change | Finding |
|---|---|---|
| `0118-universal-container-network-model.md` | Header revision line and analysis link | — |
| | D1: ADR 0088 basis for stable local IDs; generated outputs are never an authoring or migration source | S05, S07 |
| | D2: address domain generalizes rather than replaces the VLAN case; ADR 0111 arithmetic preserved; ADR 0110 section 1.5 separation restated | S06 |
| | D4.1: new legacy-to-strict translation table covering R1-R6, the R6-R1-R2 evaluation order, R1a/R1b and the final drop-all obligation | S02, S03, S04 |
| | D7: derived-field contract, object-level reuse, provisional diagnostic identity | S09, S13 |
| | D8: new decision making the authoring surface a measured property | S08 |
| `0119-firewall-rule-ordering-contract.md` | Header revision line | — |
| | D1: plan ownership versus enforcer ownership; M1-B and `managed_by_ref` preserved; one plan compiler to one projection per enforcer | S01 |
| | D4: terminal deny on a default-allow backend as a backend obligation, tied to `E7082` (was `E7854`, already held) and read-back | S04 |
| | D7: provisional diagnostic identity before numeric allocation | S13 |
| `0118-analysis/MIGRATION-AND-ACCEPTANCE.md` | Baseline pointer updated to the freeze commit, parent retained as history | S17 |
| | Section 2.1: new passing example, direct attachment without publication | S11 |
| | Section 2.2: distinct host numbers per address domain, resolved addresses annotated, `driver` value from the existing enum | S10, S12 |
| | Section 2A: authoring budget, counting method, measured baseline, exception procedure | S08 |
| | Section 2B: derive-review-freeze for filling strict policies | S14 |
| | Section 2C: quantified coordination scope | S15 |
| | Gates: G0 split into G0a architecture and G0b assurance; budget check in G1; candidates in G2; flow-data collection in G5 | S16 |
| | Acceptance matrix: A21, A22, A23 added | S08, S09, S14 |
| | Section 5: SPC finding traceability table | all |
| `adr/REGISTER.md` | Revision note for rev 2 | — |
| `docs/ai/rules/network-security.md` | Pack version 1.2; proposed-contract constraints extended to match the rebuilt ADRs | — |

## Explicitly not done

| Item | Class | Why not |
|---|---|---|
| Naming accountable owners for HA-01..HA-10 and the G0 approver | Human decision | Cannot be assigned by an analysis; recorded as gate G0b |
| Tailoring record, STIG product selection, compliance assessment | Human decision | The assurance profile already bounds the claim; nothing to change |
| Correcting the stale `10.0.30.0/24` comment in the Proxmox matrix instance | Topology data | Outside the approved scope of this rebuild; remains in the section 1 migration table |
| Resolving the staged servers VLAN, the VIP inside the DHCP pool, the disabled Proxmox enforcer and the LXC firewall flag | Topology data and backend | Requires owner decisions and working enforcement, not an ADR edit |
| Splitting the overloaded servers zone | Topology data | Mechanism already exists in ADR 0043; not an ADR 0118 decision |
| Allocating numeric diagnostic codes | Timing | Deferred to G1 with a collision test, as both ADRs require |

## Measurements used

Taken at the baseline HEAD, by direct inspection of the repository:

| Measurement | Value |
|---|---|
| Project instances | 189 |
| Instance files with a network block | 25 |
| Of those, declaring exactly two network keys | 21 |
| Distinct network key names in instances | 12 |
| Services declaring ports | 5 of 29 |
| Services declaring a source restriction | 3 of 29 |
| Services in the servers trust zone | 20 of 29 |
| Authored policy override entries | 9 |
| Repository files consuming `vlan_ref` | 28, of which 8 are plugins |
| Validator plugins registered in manifests | 52 |
| Current AdGuard feature surface | 9 key paths, 2 files, 3 references |

## Status after the rebuild

Unchanged: both ADRs remain **Proposed**. ADR 0110 remains **Implemented** with
its R1-R6 behavior untouched. G1-G8 remain open, A01-A23 remain unclosed, no
backend is qualified, and no deployment is authorized. The rebuild changes the
document, not the system.

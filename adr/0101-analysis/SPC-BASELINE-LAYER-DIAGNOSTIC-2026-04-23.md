# ADR 0101 Analysis: SPC Baseline Layer Diagnostic (2026-04-23)

## Scope

Baseline diagnostic for `class -> object -> instance` layer harmonization before implementation.

## Key Facts Captured

- Total instances analyzed: 151
- Layer spread: L1=28, L2=25, L3=19, L4=24, L5=26, L6=22, L7=7
- `class.os` / `obj.os.*` / `inst.os.*` currently authored in `L1`
- Instance/object placement mismatch found for cloud VMs authored in `L1` while object layer is `L4`
- `L2` VLAN instance data includes `host_os_ref`
- Non-canonical storage refs detected (`inst.pool.local_hdd` vs `inst.storage.pool.local_hdd`)

## Purpose

This note records the pre-migration state used by ADR 0101 and is intended as comparison baseline for post-migration validation.

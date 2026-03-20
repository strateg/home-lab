# Release Notes: V5 Framework/Project Cutover

**Date:** 2026-03-20  
**Scope:** ADR0075 Stage 1 + ADR0074 remaining path-sensitive rollout items

## Summary

Migration to strict project-aware v5 layout is complete for the active project (`home-lab`).

## Completed Changes

1. Manifest contract migrated to `framework` + `project` sections.
2. Runtime rejects legacy `paths.*` contract (`E7808`).
3. Instances and secrets moved to project scope:
   - `v5/projects/home-lab/instances/`
   - `v5/projects/home-lab/secrets/`
4. Generator outputs are project-qualified:
   - `v5-generated/<project>/terraform/...`
   - `v5-generated/<project>/ansible/...`
   - `v5-generated/<project>/bootstrap/...`
5. Ansible runtime assembly moved to project-qualified inventory/override roots.
6. Legacy projection/runtime fallback branches removed from strict model.
7. Hardware identity patch utility added:
   - `v5/topology-tools/discover-hardware-identity.py`

## Operator Impact

1. Use project-qualified paths for all v5 runtime data and generated artifacts.
2. Keep secrets in project side-car scope; do not store real secrets in instance shards.
3. Validate via:
   - `V5_SECRETS_MODE=passthrough python v5/scripts/lane.py validate-v5`

## Follow-up

ADR0076 multi-repository extraction remains separate and is not part of this cutover release.

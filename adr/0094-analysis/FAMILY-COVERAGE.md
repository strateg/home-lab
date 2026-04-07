# ADR 0094 Family Coverage

**Date:** 2026-04-07  
**Scope:** Wave 4 sign-off item "All families covered"

## Covered Artifact Families

Base generators (`topology-tools/plugins/plugins.yaml`):
- `base.generator.effective_json`
- `base.generator.effective_yaml`
- `base.generator.docs`
- `base.generator.diagrams`
- `base.generator.ansible_inventory`
- `base.generator.artifact_manifest`

Object generators:
- `object.proxmox.generator.terraform`
- `object.mikrotik.generator.terraform`
- `object.proxmox.generator.bootstrap`
- `object.mikrotik.generator.bootstrap`
- `object.orangepi.generator.bootstrap`

## ADR0094 Coverage Mapping

- Advisory mode:
  - topology-wide AI input includes full effective payload + stable projection + artifact plan.
  - family-aware profile route includes dedicated `ansible_family`; non-ansible families are handled via `generic_topology`.
- Assisted mode:
  - candidate parsing/validation is path-based and family-agnostic.
  - promotion/rollback logic is file-path and metadata based, independent of artifact family.
- Ansible extension:
  - explicit ansible input adapter + output parser + optional ansible-lint path.

## Verification

- Contract tests:
  - `tests/plugin_contract/test_ai_assisted.py`
  - `tests/plugin_contract/test_ai_ansible.py`
  - `tests/plugin_contract/test_ai_promotion.py`
  - `tests/plugin_contract/test_ai_rollback.py`
- Integration/wiring:
  - `tests/plugin_integration/test_parity_stage_order.py`

## Result

Wave 4 family coverage gate: **PASS** (all active generator families are reachable in advisory/assisted flow).

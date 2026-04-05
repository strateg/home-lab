# VALIDATION PLUGIN GAP ANALYSIS (Tests vs Validators)

## Scope

This note captures where validation logic is currently implemented in tests/scripts but should be enforced in validator plugins during `compile-topology.py` / `lane.py validate-v5`.

## Key finding

The repository already has broad validator coverage in `topology-tools/plugins/validators/*`, but several strict contracts are still enforced primarily by tests or standalone validation scripts.

## Gaps to move into plugins

| Current location | Current behavior | Plugin change required |
|---|---|---|
| `tests/test_strict_profile_placeholder_contract.py` | Scans full instance payload and rejects unresolved annotation/TODO markers for strict profiles | Extend `base.validator.instance_placeholders` to scan full instance row (not only `instance_overrides` + `hardware_identity`) and detect `<TODO_...>` markers |
| `tests/test_l4_lxc_resource_profile_contract.py` | Forbids legacy top-level `resources`; requires valid `resource_profile_ref` | Strengthen `base.validator.lxc_refs`: make top-level `resources` an error in strict mode and require `resource_profile_ref` for L4 LXC rows |
| `tests/test_initialization_contract_object_modules.py` | Requires `initialization_contract` presence for key objects | Add configurable strict mode to `base.validator.initialization_contract` so required classes/objects must define contract (currently missing contract is allowed) |
| `scripts/validation/validate_v5_scaffold.py` | Enforces strict scaffold/manifest contract (no legacy `paths`, required keys, project manifest linkage) | Create/extend pre-validate governance plugin to enforce scaffold contract in the plugin pipeline |
| `scripts/validation/validate_v5_layer_contract.py` | Performs cross-layer class/object/instance/runtime edge checks | Add dedicated layer-contract validator plugin (or migrate logic into existing validator chain) |
| `scripts/validation/validate_workspace_layout.py` + lane guard | Enforces no root `v4/` or `v5/` dirs | Add preflight policy plugin so workspace invariant violations are emitted via diagnostics pipeline |

## What should stay in tests (not pluginized)

- Documentation hygiene contracts (legacy path tokens in docs)
- Utility/orchestration behavior tests (service-chain planning, cutover report planning)
- Plugin runtime/kernel behavior tests (registry load/order/phase-dispatch contracts)

These are quality/tooling contracts, not topology data validation contracts.

## Missing plugin functionality summary

1. Full-row unresolved marker scanning in instance placeholder validation.
2. Strict deprecation enforcement mode in LXC refs (`resources` -> error).
3. Required `resource_profile_ref` policy for L4 LXC.
4. Strict presence policy for initialization contracts.
5. Native plugin-based scaffold contract validation.
6. Native plugin-based layer contract validation.
7. Native plugin/preflight workspace layout validation.

## Suggested implementation order

1. Extend existing validators first (`instance_placeholders`, `lxc_refs`, `initialization_contract`).
2. Introduce `layer_contract` validator plugin (high impact).
3. Migrate scaffold/workspace script checks into pre-validate/preflight plugin diagnostics.
4. Keep script wrappers as optional operators tools, but not as the sole enforcement path.


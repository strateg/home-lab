# AI Rule Pack: Topology Model

Load when changing:

- `topology/**`
- `projects/*/topology/**`
- class, object, instance, module-index, or layer-contract files

## Rules

1. Preserve the `Class -> Object -> Instance` hierarchy.
2. Active source of truth is:
   - `topology/topology.yaml`
   - `topology/class-modules/`
   - `topology/object-modules/`
   - `projects/<project>/topology/instances/`
3. Use canonical semantic keys from ADR0088.
4. Keep historical/legacy material out of active readiness conclusions.
5. Do not represent source-of-truth changes by editing generated outputs.
6. Keep layer boundaries explicit and validate with the lane orchestrator.

## Validation

- `task validate:default`
- `task validate:layers`
- `task inspect:default` when topology readability or dependency shape matters

## ADR Sources

- ADR0062
- ADR0067
- ADR0068
- ADR0071
- ADR0087
- ADR0088

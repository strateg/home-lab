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

- ADR0026 (L3/L4 taxonomy)
- ADR0027 (Mermaid rendering)
- ADR0029 (Storage taxonomy)
- ADR0038 (Network binding contracts)
- ADR0039 (Host OS installation storage)
- ADR0040 (L0-L5 canonical ownership)
- ADR0041 (L4 workload network attachment)
- ADR0042 (L5 services modularization)
- ADR0043 (L0-L5 harmonization)
- ADR0044 (IP derivation from refs)
- ADR0047 (L6 observability)
- ADR0062 (Modular topology architecture)
- ADR0064 (OS taxonomy)
- ADR0067 (Entity-specific identifier keys)
- ADR0068 (Object YAML as instance template)
- ADR0071 (Sharded instance files)
- ADR0087 (Unified container ontology)
- ADR0088 (Semantic keyword registry)

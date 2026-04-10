# AI Rule Pack: Plugin Runtime

Load when changing:

- `topology-tools/plugins/**`
- `topology/**/plugins.yaml`
- `topology-tools/kernel/**`
- plugin manifest discovery or stage ordering

## Rules

1. Preserve lifecycle order: `discover -> compile -> validate -> generate -> assemble -> build`.
2. Preserve stage affinity:
   - discoverers -> discover
   - compilers -> compile
   - validators -> validate
   - generators -> generate
   - assemblers -> assemble
   - builders -> build
3. Declare dependencies and data exchange through manifests:
   - `depends_on`
   - `consumes`
   - `produces`
4. Respect discovery order:
   - framework
   - class
   - object
   - project
5. Treat class/object module placement as ownership convention, not runtime ACL.
6. Shared standalone plugins belong in `topology-tools/plugins/<family>/`.
7. Do not add hidden coupling through filesystem reads when `ctx` or manifest exchange is the intended contract.

## Validation

- `task validate:plugin-manifests`
- `task test:plugin-contract`
- targeted plugin integration tests

## ADR Sources

- ADR0063
- ADR0065
- ADR0066
- ADR0069
- ADR0078
- ADR0080
- ADR0086

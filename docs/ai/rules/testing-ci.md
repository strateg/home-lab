# AI Rule Pack: Testing and CI

Load when changing:

- `tests/**`
- `taskfiles/**`
- `.github/workflows/**`
- runtime contracts
- validation entrypoints

## Rules

1. Use `task` commands for build/test/validation flows where available.
2. Add or update tests with behavior changes.
3. Prefer targeted tests first, then broader gates.
4. Run `task ci` before claiming integration-level closure when feasible.
5. CI task aliases are public developer contracts; preserve or deprecate them intentionally.
6. Do not claim validation without command evidence and result summary.
7. If framework code changes, expect `framework.lock` refresh and `task framework:strict`.

## Validation

- targeted pytest
- `task validate:quality-fast`
- `task framework:strict`
- `task ci`

## ADR Sources

- ADR0066
- ADR0070
- ADR0077
- ADR0080
- ADR0086

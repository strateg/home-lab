# AI Rule Pack: Acceptance TUC

Load when changing:

- `acceptance-testing/**`
- `tests/plugin_integration/test_tuc*.py`
- `scripts/acceptance/**`
- `taskfiles/acceptance.yml`

## Authoritative ADRs

- ADR0070 defines the Testing Use Case (TUC) framework.
- ADR0066 defines testing and CI strategy.
- ADR0069 and ADR0080 connect acceptance gates to plugin-first/runtime cutover governance.
- ADR0071 keeps sharded instance authoring separate from downstream plugin consumption.
- ADR0089 and ADR0091 connect SOHO product/readiness claims to acceptance evidence.

## Core Rules

1. Each acceptance scenario gets one folder:
   - `acceptance-testing/TUC-XXXX-short-name/`
2. `XXXX` is a zero-padded sequence.
3. `short-name` is lowercase kebab-case.
4. Use `acceptance-testing/TUC-TEMPLATE/` as the baseline for new TUCs.
5. Keep all TUC-specific materials inside the TUC folder:
   - `TUC.md`
   - `README.md`
   - `TEST-MATRIX.md`
   - `HOW-TO.md`
   - `quality-gate.py`
   - `analysis/`
   - artifacts/logs output directory
6. Keep executable regression coverage in:
   - `tests/plugin_integration/test_tuc*.py`
7. Do not scatter TUC evidence into ADR analysis folders.
8. Do not broaden an existing TUC when a new scenario should get its own TUC number.
9. Keep TUC status, test matrix, evidence log, and project status report synchronized.

## Evidence Contract

A TUC should capture enough evidence to prove the scenario:

1. positive compile path when relevant:
   - effective topology JSON
   - diagnostics JSON
   - diagnostics TXT
2. negative validation path when relevant:
   - invalid fixture
   - expected diagnostic code
   - regression test
3. determinism when relevant:
   - repeated compile/generation comparison
   - stable snapshot or diff policy
4. regression gate:
   - targeted `pytest` node/file
   - quality gate result
   - full acceptance suite before release/cutover closure

## Commands

List TUCs:

```bash
task acceptance:list
```

Run one quality gate:

```bash
task acceptance:quality TUC_SLUG=TUC-XXXX-short-name
```

Run all quality gates:

```bash
task acceptance:quality-all
```

Run one TUC test file or glob:

```bash
task acceptance:test TUC_TEST='tests/plugin_integration/test_tucXXXX_*.py'
```

Run one TUC test case:

```bash
task acceptance:test-case PYTEST_NODE='tests/plugin_integration/test_tucXXXX_name.py::test_name'
```

Compile topology into a TUC artifact directory:

```bash
task acceptance:compile TUC_SLUG=TUC-XXXX-short-name
```

Run all TUC tests:

```bash
task acceptance:tests-all
```

## Artifact Directory Rule

Use `artifacts/` for all TUC evidence outputs. The historical misspelling was a typo and MUST NOT be reintroduced.

## Validation

- `task acceptance:quality TUC_SLUG=<slug>`
- `task acceptance:test TUC_TEST='<test-file-or-glob>'`
- `task acceptance:compile TUC_SLUG=<slug>` when compiled artifacts are part of evidence
- `task acceptance:quality-all`
- `task acceptance:tests-all`

## ADR Sources

- ADR0066
- ADR0069
- ADR0070
- ADR0071
- ADR0080
- ADR0089
- ADR0091

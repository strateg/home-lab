# TUC-0002 Implementation Plan

## Workstreams

1. Identify final plugin id and owning manifest for the new Terraform generator.
2. Add integration test coverage for generator outputs and artifact contracts.
3. Capture compile evidence in TUC artifacts.

## Tasks

1. Set `NEW_TERRAFORM_PLUGIN_ID` and validate manifest presence via quality gate.
2. Add `tests/plugin_integration/test_tuc0002_new_terraform_generator.py` assertions.
3. Run `task acceptance:compile TUC_SLUG=TUC-0002-new-terraform-generator`.
4. Attach diagnostics/effective payload evidence under `artifacts/`.

## Exit Criteria

1. Quality gate passes with strict plugin id check.
2. TUC test file passes in CI/local lane.
3. Evidence log includes compile and test results.

## Rollback

- Revert new generator manifest/entry changes and restore previous lock if contract checks fail.

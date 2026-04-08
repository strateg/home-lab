# TUC-0002 Implementation Plan

## Workstreams

1. Verify exact Terraform plugin ids and owning manifests.
2. Add integration test coverage for generator outputs and artifact contracts.
3. Capture compile evidence in TUC artifacts.

## Tasks

1. Validate manifest presence for:
   - `object.mikrotik.generator.terraform`
   - `object.proxmox.generator.terraform`
2. Add `tests/plugin_integration/test_tuc0002_new_terraform_generator.py` assertions.
3. Run `task acceptance:compile TUC_SLUG=TUC-0002-new-terraform-generator`.
4. Attach diagnostics/effective payload evidence under `artifacts/`.

## Exit Criteria

1. Quality gate passes with exact plugin-id checks.
2. TUC test file passes in CI/local lane.
3. Evidence log includes compile and test results.

## Rollback

- Revert new generator manifest/entry changes and restore previous lock if contract checks fail.

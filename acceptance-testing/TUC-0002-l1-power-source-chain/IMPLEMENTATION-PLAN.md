# Implementation Plan

## Workstreams

1. Model wiring
2. Validator implementation
3. Integration test coverage
4. Acceptance documentation and evidence

## Tasks

1. Add L1 power chain fields in instance shards (`router -> pdu -> ups`).
2. Implement and register `base.validator.power_source_refs`.
3. Add plugin integration tests for positive and negative scenarios (`E7801..E7805`).
4. Add TUC compile test to assert `instance_data.power` preservation.
5. Update ADR0062 relation status and execution backlog.

## Exit Criteria

1. Power source relation plugin is active in runtime manifest.
2. Tests pass for valid and invalid power-chain scenarios.
3. Compile succeeds with strict model lock and zero errors/warnings.

## Rollback

- Remove `base.validator.power_source_refs` from `v5/topology-tools/plugins/plugins.yaml`.
- Revert `power` blocks from L1 instance shards.
- Re-run compile + plugin integration suite to confirm baseline recovery.

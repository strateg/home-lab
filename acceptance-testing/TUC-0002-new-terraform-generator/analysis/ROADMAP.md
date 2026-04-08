# TUC-0002 Roadmap

## Objectives

1. Stabilize manifest + entrypoint contract for the new Terraform generator.
2. Prove artifact plan/report and deterministic output behavior.
3. Record compile and test evidence for release gates.

## Workstreams

### Milestone 1 Scaffold

- Scope:
  - Create TUC package and baseline quality gate.
- Tasks:
  1. Create docs and analysis files.
  2. Add artifacts folder and quality checks.
- Exit criteria:
  1. `quality-gate.py` passes.

### Milestone 2 Generator Validation

- Scope:
  - Validate new Terraform generator contract and outputs.
- Tasks:
  1. Add real integration assertions in `test_tuc0002_new_terraform_generator.py`.
  2. Collect compile evidence in `artifacts/`.
- Exit criteria:
  1. TUC tests pass and evidence is recorded.

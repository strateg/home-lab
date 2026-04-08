# TUC-0002 Validation Rules Summary

## Goal

Describe validation rules for onboarding a new Terraform generator.

## Validation Rules

1. Plugin id must be present in at least one loaded plugin manifest.
2. Generator must publish valid `artifact_plan` and `artifact_generation_report`.
3. Generated Terraform files must be deterministic for identical input.

## Evidence

| Scenario | Test | Result |
|---|---|---|
| Manifest wiring | `quality-gate.py` | `pass` |
| Expected terraform ids present | `test_tuc0002_new_terraform_generator.py` | `pass` |
| Determinism | compile twice + diff selected files | `pending` |

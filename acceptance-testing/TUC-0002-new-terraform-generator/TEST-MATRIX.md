# TUC-0002 Test Matrix

| ID | Scenario | Verification | Expected |
|---|---|---|---|
| TUC2-T1 | New generator is discoverable by manifest | `quality-gate.py` with `NEW_TERRAFORM_PLUGIN_ID` | plugin id exists in loaded manifests |
| TUC2-T2 | Compile with strict lock passes | `task acceptance:compile TUC_SLUG=TUC-0002-new-terraform-generator` | exit code 0 |
| TUC2-T3 | Artifact contract outputs are published | integration test for new generator | `artifact_plan` and `artifact_generation_report` present |
| TUC2-T4 | Obsolete defaults are safe | contract/integration tests | no destructive delete without ownership proof |
| TUC2-T5 | Deterministic output | run compile twice and diff generated family files | no semantic drift |

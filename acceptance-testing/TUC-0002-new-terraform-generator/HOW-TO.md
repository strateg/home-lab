# TUC-0002 How-To

## 1. Run quality gate

```bash
python3 acceptance-testing/TUC-0002-new-terraform-generator/quality-gate.py
```

Optional strict plugin check:

```bash
NEW_TERRAFORM_PLUGIN_ID=object.example.generator.terraform \
python3 acceptance-testing/TUC-0002-new-terraform-generator/quality-gate.py
```

## 2. Compile into TUC artifacts

```bash
task acceptance:compile TUC_SLUG=TUC-0002-new-terraform-generator
```

## 3. Run focused tests (after generator test is added)

```bash
task acceptance:test TUC_TEST='tests/plugin_integration/test_tuc0002_new_terraform_generator.py'
```

## 4. Save evidence

- compile outputs: `acceptance-testing/TUC-0002-new-terraform-generator/artifacts/`
- notes/results: `acceptance-testing/TUC-0002-new-terraform-generator/analysis/EVIDENCE-LOG.md`

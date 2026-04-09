# How To Run

1. Run target contract/integration tests:

```bash
. .venv/bin/activate
pytest -q -o addopts= \
  tests/plugin_contract/test_product_task_contract.py \
  tests/plugin_contract/test_soho_contract_schemas.py \
  tests/plugin_integration/test_product_doctor_script.py \
  tests/plugin_integration/test_product_handover_check_script.py \
  tests/plugin_integration/test_soho_readiness_builder.py
```

2. Run operator workflow smoke:

```bash
. .venv/bin/activate
task product:doctor
task product:handover
```

3. Run TUC quality gate:

```bash
python acceptance-testing/TUC-0004-soho-readiness-evidence/quality-gate.py
```

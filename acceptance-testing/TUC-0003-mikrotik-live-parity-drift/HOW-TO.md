# TUC-0003 How-To

## 1. Run quality gate

```bash
python3 acceptance-testing/TUC-0003-mikrotik-live-parity-drift/quality-gate.py
```

## 2. Compile into TUC artifacts

```bash
task acceptance:compile TUC_SLUG=TUC-0003-mikrotik-live-parity-drift
```

## 3. Run focused test

```bash
task acceptance:test TUC_TEST='tests/plugin_integration/test_tuc0003_mikrotik_live_parity.py'
```

## 4. Run operator drift-check workflow

Follow: `docs/runbooks/MIKROTIK-TERRAFORM-DRIFT-CHECK.md`

## 5. Save evidence

- compile outputs: `acceptance-testing/TUC-0003-mikrotik-live-parity-drift/artifacts/`
- notes/results: `acceptance-testing/TUC-0003-mikrotik-live-parity-drift/analysis/EVIDENCE-LOG.md`

# TUC-XXXX How-To

## 1. Smoke Check

1. Verify required fixtures/configs exist.
2. Verify required scripts/tests are present.

## 2. Run Quality Gate

```bash
python acceptance-testing/TUC-XXXX-short-name/quality-gate.py
```

## 3. Run TUC Tests

```bash
pytest -q <path-to-tuc-tests-or-markers>
```

## 4. Run End-to-End Command (optional)

```bash
<command-under-test> \
  <args> \
  > acceptance-testing/TUC-XXXX-short-name/artifacts/<output-file>
```

## 5. Capture Evidence

1. Save command outputs into `artifacts/`.
2. Update `analysis/EVIDENCE-LOG.md`.
3. Update `analysis/PROJECT-STATUS-REPORT.md`.

# TUC-0001 Evidence Log

## Baseline Observations (2026-03-11)

1. Router class exists:
   - `v5/topology/class-modules/router/class.router.yaml`
2. Router objects exist:
   - `v5/topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml`
   - `v5/topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml`
3. Router instances exist in bindings:
   - `rtr-mikrotik-chateau`
   - `rtr-slate`
4. No existing OSI-separated `physical_link` (L1) and `data_link` (L2) model for ethernet connectivity.

## Run History

| Date | Command | Result | Evidence Path |
|---|---|---|---|
| 2026-03-11 | `python -m pytest -q -o addopts="" v5/tests/plugin_integration/test_tuc0001_router_data_link.py` | `9 passed` | `artifacts/tuc0001-pytest.txt` |
| 2026-03-11 | `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --output-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-valid.json --diagnostics-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-valid.json --diagnostics-txt acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-valid.txt` | `errors=0 warnings=0` | `artifacts/compile-valid.txt`, `artifacts/effective-valid.json`, `artifacts/diagnostics-valid.json` |
| 2026-03-11 | `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --output-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-valid-run2.json --diagnostics-json acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-valid-run2.json --diagnostics-txt acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-valid-run2.txt` | `errors=0 warnings=0` | `artifacts/compile-valid-run2.txt`, `artifacts/effective-valid-run2.json` |
| 2026-03-11 | `python -m pytest -q -o addopts="" v5/tests/plugin_contract v5/tests/plugin_integration` | `81 passed` | `artifacts/plugin-suites.txt` |

## Determinism / Field Preservation

- Effective JSON deterministic check (excluding `generated_at`/`compiled_at`): `true`
- Negative validation diagnostics asserted by automated tests:
  - `E7304` (endpoint shape / wrong class / unknown device)
  - `E7305` (unknown port)
  - `E7307` (channel reference integrity)
  - `E7308` (channel-link/endpoint mismatch)
- Cable instance found in compiled model with preserved properties:
  - `instance_data.length_m = 3`
  - `instance_data.shielding = utp`
  - `instance_data.category = cat5e`
- Evidence file: `artifacts/determinism-report.txt`

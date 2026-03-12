# Evidence Log

## Run History

| Date | Command | Result | Evidence Path |
|---|---|---|---|
| `2026-03-12` | `python -m pytest -q -o addopts="" v5/tests/plugin_integration/test_l1_power_source_refs.py` | pass (8 passed) | `v5/tests/plugin_integration/test_l1_power_source_refs.py` |
| `2026-03-12` | `python -m pytest -q -o addopts="" v5/tests/plugin_integration/test_tuc0002_l1_power_source_chain.py` | pass | `v5/tests/plugin_integration/test_tuc0002_l1_power_source_chain.py` |
| `2026-03-12` | `python v5/topology-tools/compile-topology.py --topology v5/topology/topology.yaml --strict-model-lock --output-json v5-build/tmp-effective-topology.json --diagnostics-json v5-build/tmp-diagnostics.json --diagnostics-txt v5-build/tmp-diagnostics.txt` | pass (`errors=0 warnings=0`) | `v5-build/tmp-effective-topology.json`, `v5-build/tmp-diagnostics.json` |

## Notes

- Outlet inventory validation is tracked and validated in `TUC-0003-power-outlet-inventory`.

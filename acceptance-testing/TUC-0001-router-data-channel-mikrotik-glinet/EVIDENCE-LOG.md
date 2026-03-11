# TUC-0001 Evidence Log

## Baseline Observations (2026-03-11)

1. Router class exists:
   - `v5/topology/class-modules/classes/router/class.router.yaml`
2. Router objects exist:
   - `v5/topology/object-modules/mikrotik/obj.mikrotik.chateau_lte7_ax.yaml`
   - `v5/topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml`
3. Router instances exist in bindings:
   - `rtr-mikrotik-chateau`
   - `rtr-slate`
4. No existing data-channel class/object instance model for ethernet cable.

## Run History

| Date | Command | Result | Evidence Path |
|---|---|---|---|
| 2026-03-11 | `python -m pytest -q v5/tests/plugin_contract v5/tests/plugin_integration` | baseline pass | `artifacts/baseline-pytest.txt` |

## Pending Evidence

- Valid compile report for TUC fixture
- Negative validation reports (`unknown endpoint`, `unknown port`)
- Determinism diff report

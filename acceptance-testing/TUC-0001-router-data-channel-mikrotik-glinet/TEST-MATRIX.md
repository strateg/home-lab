# TUC-0001 Test Matrix

| ID | Scenario | Type | Input | Expected | Status |
|---|---|---|---|---|---|
| TUC1-T1 | Valid cable between routers | integration | `rtr-mikrotik-chateau:ether2 <-> rtr-slate:lan1` | compile success, no errors | planned |
| TUC1-T2 | Unknown endpoint instance | validation | endpoint device_ref = `rtr-unknown` | error diagnostic (stable code) | planned |
| TUC1-T3 | Unknown MikroTik port | validation | endpoint port = `ether99` | error diagnostic (stable code) | planned |
| TUC1-T4 | Unknown GL.iNet port | validation | endpoint port = `lan99` | error diagnostic (stable code) | planned |
| TUC1-T5 | Wrong cable class_ref | validation | cable row uses non-data-channel class | error diagnostic | planned |
| TUC1-T6 | Preserve `length_m` instance property | contract | valid cable row with `length_m` | field present in effective model | planned |
| TUC1-T7 | Determinism check | regression | two identical compile runs | no noisy diffs in outputs | planned |
| TUC1-T8 | Existing suites unchanged | regression | `pytest plugin_contract + plugin_integration` | all pass | planned |

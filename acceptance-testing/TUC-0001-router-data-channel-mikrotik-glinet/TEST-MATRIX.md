# TUC-0001 Test Matrix

| ID | Scenario | Type | Input | Expected | Status |
|---|---|---|---|---|---|
| TUC1-T1 | Valid cable + channel between routers | integration | `rtr-mikrotik-chateau:ether2 <-> rtr-slate:lan1` + linked channel | compile success, no errors | planned |
| TUC1-T2 | Unknown endpoint instance | validation | endpoint device_ref = `rtr-unknown` | error diagnostic (stable code) | planned |
| TUC1-T3 | Unknown MikroTik port | validation | endpoint port = `ether99` | error diagnostic (stable code) | planned |
| TUC1-T4 | Unknown GL.iNet port | validation | endpoint port = `lan99` | error diagnostic (stable code) | planned |
| TUC1-T5 | Wrong cable class_ref | validation | cable row uses non-data-link class | error diagnostic | planned |
| TUC1-T6 | Missing created channel ref | validation | cable row without `creates_channel_ref` | error diagnostic | planned |
| TUC1-T7 | Channel/link mismatch | validation | `channel.link_ref` points to another cable | error diagnostic | planned |
| TUC1-T8 | Endpoint pair mismatch | validation | cable endpoints differ from channel endpoints | error diagnostic | planned |
| TUC1-T9 | Preserve `length_m` instance property | contract | valid cable row with `length_m` | field present in effective model | planned |
| TUC1-T10 | Determinism check | regression | two identical compile runs | no noisy diffs in outputs | planned |
| TUC1-T11 | Existing suites unchanged | regression | `pytest plugin_contract + plugin_integration` | all pass | planned |

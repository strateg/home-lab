# TUC-0001 Test Matrix

| ID | Scenario | Type | Input | Expected | Status |
|---|---|---|---|---|---|
| TUC1-T1 | Valid cable + channel between routers | integration | `rtr-mikrotik-chateau:ether2 <-> rtr-slate:lan1` + linked channel | compile success, no errors | passed |
| TUC1-T2 | Unknown endpoint instance | validation | endpoint device_ref = `rtr-unknown` | error diagnostic E7304 | passed |
| TUC1-T3 | Unknown MikroTik port | validation | endpoint port = `ether99` | error diagnostic E7305 (port not found) | passed |
| TUC1-T4 | Unknown GL.iNet port | validation | endpoint port = `lan99` | error diagnostic E7305 (port not found) | passed |
| TUC1-T5 | Wrong cable class_ref | validation | cable row uses non-`class.network.physical_link` class | error diagnostic | passed |
| TUC1-T6 | Missing created channel ref | validation | cable row without `creates_channel_ref` | error diagnostic | passed |
| TUC1-T7 | Channel/link mismatch | validation | `channel.link_ref` points to another cable | error diagnostic E7307 | passed |
| TUC1-T8 | Endpoint pair mismatch | validation | cable endpoints differ from channel endpoints | error diagnostic E7308 | passed |
| TUC1-T9 | Preserve `length_m` instance property | contract | valid cable row with `length_m` | field present in effective model | passed |
| TUC1-T10 | Determinism check | regression | two identical compile runs | no noisy diffs in outputs | passed |
| TUC1-T11 | Existing suites unchanged | regression | `pytest plugin_contract + plugin_integration` | all pass | passed |
| TUC1-T12 | Port exists on device (MikroTik) | validation | cable endpoint port=`ether2` on MikroTik (valid) | success; port validated | new |
| TUC1-T13 | Port exists on device (GL.iNet) | validation | cable endpoint port=`lan1` on GL.iNet (valid) | success; port validated | new |
| TUC1-T14 | Multiple cables on same port (occupancy) | validation | two cable instances both using `rtr-mikrotik-chateau:ether2` | error diagnostic E7306 (port occupancy) | planned |
| TUC1-T15 | Channel without backing cable | validation | channel instance with `link_ref` to non-existent cable | error diagnostic (reference error) | planned |
| TUC1-T16 | Endpoint order invariance (A-B == B-A) | contract | cable A->B vs channel B->A (opposite order) | endpoints recognized as same unordered pair | planned |
| TUC1-T17 | Invalid shielding for cable instance | validation | cable with `shielding: invalid_type` | error diagnostic (schema validation) | planned |

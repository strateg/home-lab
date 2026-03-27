# TUC-0001 Test Matrix

Source of truth: `tests/plugin_integration/test_tuc0001_router_data_link.py`

| ID | Automated Test | Scenario | Expected |
|---|---|---|---|
| TUC1-T1 | `test_tuc0001_network_validator_accepts_valid_cable_and_channel` | Valid cable+channel between `rtr-mikrotik-chateau:ether2` and `rtr-slate:lan1` | Validator passes (`SUCCESS`) |
| TUC1-T2 | `test_tuc0001_network_validator_rejects_unknown_endpoint_instance` | Unknown endpoint device (`rtr-unknown`) | `FAILED` with `E7304` |
| TUC1-T3 | `test_tuc0001_network_validator_rejects_unknown_mikrotik_port` | Invalid MikroTik port (`ether99`) | `FAILED` with `E7305` |
| TUC1-T4 | `test_tuc0001_network_validator_rejects_unknown_glinet_port` | Invalid GL.iNet port (`lan99`) | `FAILED` with `E7305` |
| TUC1-T5 | `test_tuc0001_network_validator_rejects_wrong_cable_class` | Cable row with wrong `class_ref` | `FAILED` with `E7304` |
| TUC1-T6 | `test_tuc0001_network_validator_requires_created_channel_ref` | Missing `creates_channel_ref` on cable | `FAILED` with `E7307` |
| TUC1-T7 | `test_tuc0001_network_validator_rejects_channel_link_mismatch` | Channel `link_ref` points to another cable | `FAILED` with `E7308` |
| TUC1-T8 | `test_tuc0001_network_validator_rejects_endpoint_pair_mismatch` | Cable/channel endpoint pair mismatch | `FAILED` with `E7308` |
| TUC1-T9 | `test_tuc0001_compile_preserves_cable_instance_data` | Compile preserves cable instance properties | Effective model contains expected cable `instance_data` |
| TUC1-T10 | `test_tuc0001_compile_preserves_power_source_bindings` | Compile preserves L1 power bindings | Effective model contains expected `power.source_ref`/`outlet_ref` |

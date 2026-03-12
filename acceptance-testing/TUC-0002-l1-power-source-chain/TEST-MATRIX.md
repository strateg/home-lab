# Test Matrix

| ID | Scenario | Type | Input | Expected | Status |
|---|---|---|---|---|---|
| T1 | Valid L1 power chain | integration | `rtr-mikrotik-chateau -> pdu-rack -> ups-main` | Compile pass, no `E78xx` | passed |
| T2 | Unknown power source target | validation | `power.source_ref: <missing>` | `E7801` | passed |
| T3 | Invalid source layer | validation | `power.source_ref` outside L1 | `E7803` | passed |
| T4 | Invalid source target class/layer | validation | source points to non-power class or non-L1 | `E7802` | passed |
| T5 | Bad field format | validation | non-string `power.source_ref` / `power.outlet_ref` | `E7804` | passed |
| T6 | Outlet collision on one source | validation | duplicate `(source_ref, outlet_ref)` | `E7805` | passed |
| T7 | Power graph cycle | validation | cyclic source chain | `E7805` | passed |
| T8 | Effective JSON preservation | integration | compile full topology | `instance_data.power.*` preserved | passed |

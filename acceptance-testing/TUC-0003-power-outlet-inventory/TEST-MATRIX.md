# Test Matrix

| ID | Scenario | Type | Input | Expected | Status |
|---|---|---|---|---|---|
| T1 | Valid outlet refs on declared source inventory | integration | `outlet_ref=A1/A2` with source outlets declared | pass | passed |
| T2 | Unknown outlet ref | validation | `outlet_ref=A9` with source inventory `[A1, A2]` | `E7806` | passed |
| T3 | Existing power-source checks unaffected | regression | prior `E7801..E7805` scenarios | stable pass/fail | passed |
| T4 | Effective JSON preserves declared outlet bindings | integration | compile full topology with `outlet_01/outlet_02` | outlet refs preserved in `instance_data.power` | passed |
| T5 | Outlet provided but source has no inventory | validation | source object without `properties.power.outlets` + `outlet_ref` set | `E7806` | passed |

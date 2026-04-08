# TUC-0003 Test Matrix

| ID | Scenario | Verification | Expected |
|---|---|---|---|
| TUC3-T1 | TUC structure is complete | `quality-gate.py` | required docs/analysis files exist |
| TUC3-T2 | MikroTik family compile succeeds | integration test compile run | exit code 0 |
| TUC3-T3 | Topology domains reflected | integration test file markers | interfaces/addresses/dhcp/dns/firewall present |
| TUC3-T4 | Runtime baseline reflected | integration test firewall/dns/dhcp markers | runtime NAT and DNS resources present |
| TUC3-T5 | Drift workflow documented | runbook path check | runbook exists and linked |

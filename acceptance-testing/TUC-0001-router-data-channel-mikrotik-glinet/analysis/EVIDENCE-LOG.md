# TUC-0001 Evidence Log

## Verification Snapshot (2026-03-27)

This log captures current evidence for the updated TUC-0001 definition and repository layout.

### Topology Inputs Verified

- Framework topology manifest: `topology/topology.yaml`
- Project instances root: `projects/home-lab/topology/instances`
- Cable instance: `projects/home-lab/topology/instances/L1-foundation/physical-links/inst.ethernet_cable.cat5e.yaml`
- Channel instance: `projects/home-lab/topology/instances/L2-network/data-channels/inst.chan.eth.chateau_to_slate.yaml`

## Execution Results

| Date | Command | Result |
|---|---|---|
| 2026-03-27 | `python acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/quality-gate.py` | Passed (`errors=0`, `warnings=0`) |
| 2026-03-27 | `pytest -q tests/plugin_integration/test_tuc0001_router_data_link.py` | Passed (`10 passed`) |
| 2026-03-27 | `python topology-tools/compile-topology.py --topology topology/topology.yaml --strict-model-lock ...` | Passed (`errors=0`, `warnings=11`, `infos=78`) |

Compile artifacts from the latest run:

- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/effective-2026-03-27.json`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-2026-03-27.json`
- `acceptance-testing/TUC-0001-router-data-channel-mikrotik-glinet/artifacts/diagnostics-2026-03-27.txt`

## Effective Model Checks (2026-03-27)

Validated in `effective-2026-03-27.json`:

- `inst.ethernet_cable.cat5e` is present.
- `inst.chan.eth.chateau_to_slate` is present.
- Cable properties are preserved: `length_m=3`, `shielding=utp`, `category=cat5e`.
- Channel back-reference is preserved: `link_ref=inst.ethernet_cable.cat5e`.
- Power bindings are preserved (example): `rtr-slate -> pdu-rack -> outlet_02`.

## Scenario Coverage Status

Automated scenarios currently covered by `tests/plugin_integration/test_tuc0001_router_data_link.py`:

1. Valid cable/channel acceptance.
2. Unknown endpoint device rejection (`E7304`).
3. Unknown port rejection for MikroTik (`E7305`).
4. Unknown port rejection for GL.iNet (`E7305`).
5. Wrong cable class rejection (`E7304`).
6. Missing `creates_channel_ref` rejection (`E7307`).
7. Channel `link_ref` mismatch rejection (`E7308`).
8. Endpoint pair mismatch rejection (`E7308`).
9. Cable instance data preservation in compile output.
10. Power source binding preservation in compile output.

## Conclusion

As of **2026-03-27**, TUC-0001 is green for current project state:

- quality gate passes,
- dedicated TUC integration suite passes,
- strict compile run completes with zero errors,
- required L1/L2 and power contracts are preserved in effective model.

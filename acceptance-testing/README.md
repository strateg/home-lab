# Acceptance Testing

This directory stores Testing Use Cases (TUC) and all related artifacts.

## Rules

1. Each use case must have its own folder:
   - `acceptance-testing/TUC-XXXX-short-name/`
2. Everything for the use case stays inside that folder:
   - TUC definition
   - implementation plan
   - test matrix
   - evidence log
   - generated artifacts and reports
3. Use `acceptance-testing/TUC-TEMPLATE/` as the baseline.

## Naming

- `TUC-XXXX` is a zero-padded sequence (`TUC-0001`, `TUC-0002`, ...).
- `short-name` is lowercase kebab-case.

## Current TUCs

- `TUC-0001-router-data-channel-mikrotik-glinet` (L1 ethernet cable + L2 data_link modeling)
- `TUC-0002-l1-power-source-chain` (L1 `power.source_ref` chain: router -> PDU -> UPS)
- `TUC-0003-power-outlet-inventory` (`power.outlet_ref` validation against source outlet inventory)

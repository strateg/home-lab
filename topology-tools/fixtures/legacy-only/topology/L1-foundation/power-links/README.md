# L1 Power Links

This directory models physical power cabling in L1.

## Scope

- AC/DC/USB-PD power paths between physical endpoints.
- Separation of concerns:
  - `data_links` for data connectivity.
  - `power_links` for electrical connectivity.

## PoE (Data + Power on Same Cable)

Use both links:

1. Data link in `L1_foundation.data_links` (`medium: ethernet`).
2. Power link in `L1_foundation.power_links` (`mode: poe`) with `data_link_ref` pointing to that data link.

Example:

```yaml
id: plink-poe-camera
endpoint_a:
  device_ref: switch-main
endpoint_b:
  device_ref: camera-front-door
mode: poe
standard: 802.3at
max_watts: 30
data_link_ref: link-switch-camera
status: active
```

## Cableless Power

Wireless charging can be modeled as a power link with `mode: wireless-inductive` and without `data_link_ref`.

# L1 Power Model

This directory models physical power in L1 foundation.

## Scope

- Utility and conditioning: UPS units (`ups-*`).
- Device-side power properties: `devices[*].power`.
- Optional power over physical links: `physical_links[*].power_delivery`.
- Power devices in inventory: managed `ups` and `pdu` under `devices/owned/power/`.

## Power Source Taxonomy

Use `devices[*].power.primary_source` / `backup_source` with:

- `ac-mains`
- `dc-adapter`
- `usb-pd`
- `poe`
- `battery`
- `ups-output`
- `cloud-provider`

## Minimal Device Pattern

```yaml
power:
  primary_source: dc-adapter
  backup_source: ups-output
  upstream_power_ref: ups-main
  max_watts: 20
```

## PoE Pattern (Optional)

Use this when power is delivered on a data link:

```yaml
power_delivery:
  enabled: true
  mode: poe
  standard: 802.3at
  provider_endpoint: endpoint_a
  max_watts: 30
```

## Notes

- `upstream_power_ref` should reference a UPS ID from this directory.
- For outlet-level outage modeling, route compute hosts via a `pdu-*` device and model UPS -> PDU -> host cascade.
- Keep power semantics in L1 only; higher layers consume reliability effects, not wiring details.

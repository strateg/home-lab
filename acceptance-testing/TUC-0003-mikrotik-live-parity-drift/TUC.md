# TUC-0003: MikroTik Live Parity and Drift Gate

## Metadata

- `id`: `TUC-0003`
- `status`: `implemented`
- `owner`: `topology-tools`
- `created_at`: `2026-04-08`
- `target_date`: `2026-04-10`
- `related_adrs`:
  - `adr/0092-smart-artifact-generation-and-hybrid-rendering.md`
  - `adr/0093-artifact-plan-schema-and-generator-runtime-integration.md`
  - `adr/0094-ai-advisory-mode-for-artifact-generation.md`

## Objective

Validate that MikroTik Terraform generation fully covers the intended L2/L3 topology shape and that operator drift-check workflow is executable.

## Scope

- In scope:
  - Generated file coverage for MikroTik network topology domains.
  - Presence of runtime-derived NAT/DNS/LAN DHCP sections in generated Terraform.
  - Operator runbook and acceptance workflow for live parity check.
- Out of scope:
  - Applying Terraform to production router.
  - Hard-failing CI on temporary live connectivity outages.

## Preconditions

- `object.mikrotik.generator.terraform` is registered and passes compile.
- Topology includes `rtr-mikrotik-chateau` with observed runtime baseline.
- Runbook exists for drift review and safe rollout.

## Inputs

- Topology: `topology/topology.yaml`
- Generator: `topology/object-modules/mikrotik/plugins/generators/terraform_mikrotik_generator.py`
- Templates: `topology/object-modules/mikrotik/templates/terraform/*.j2`
- Runbook: `docs/runbooks/MIKROTIK-TERRAFORM-DRIFT-CHECK.md`

## Expected Outcomes

- Compile emits full MikroTik Terraform family files.
- Generated artifacts include bridge/vlan/address/dhcp/dns/firewall/nat sections.
- Acceptance tests pass for TUC-0003 contract.

## Acceptance Criteria

1. TUC-0003 structural quality gate passes.
2. TUC-0003 integration test passes and confirms coverage markers.
3. Runbook exists and documents repeatable drift-check flow.

## Risks and Open Questions

- Live MCP/SSH connectivity can be temporarily unavailable from CI/sandbox.
- Live parity remains evidence-based until environment has network access to router.

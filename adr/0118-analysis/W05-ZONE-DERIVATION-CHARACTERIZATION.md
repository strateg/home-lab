# W05 — characterization of the two zone/vlan derivations

Status: evidence for work item W05 of the ADR 0118/0119 implementation plan.
Date: 2026-09-11. Baseline: commit `c26232d2`, branch `development`, clean tree.
No cutover was performed. No topology, artifact or device state changed.

## Why this exists

The plan requires the generator to stop recomputing zone membership and consume
the compiler's published channel instead, and requires that step to be parity:
identical managed artifacts for the fixed sources. W05 says to characterize both
derivations first, because a divergence means a behaviour change rather than a
refactor, and the review that produced revision 2 warned specifically against
forcing an empty diff by copying generator semantics into the core.

The derivations diverge. The cutover cannot proceed as a parity step until the
divergence is resolved as its own reviewed change.

## What each side does

| Aspect | `security_matrix_compiler.py` | `mikrotik/plugins/projections.py` |
|---|---|---|
| VLAN selection | `instance_id.startswith("inst.vlan.")` (`:54`) | `"vlan" in resolved_object_ref` (`:591-592`) |
| Zone CIDRs | VLANs referencing the zone only (`:134`) | Same, **plus** `additional_networks` from the zone instance (`:638-646`) |
| `zone_vlans` ordering | Sorted for determinism (`:76-77`) | Not sorted (`:609-615`) |
| Publication | `zone_vlans`, `vlan_cidr_map`, `security_matrices`, `matrix_by_enforcer` (`:167-170`) | Rebuilt locally at generate |

## Divergence 1 — `additional_networks`, live effect

Two trust zones declare overlay networks in source:

| Zone instance | CIDR | Declared purpose |
|---|---|---|
| `inst.trust_zone.vpn_tunnel.yaml:18` | `10.100.0.0/24` | WireGuard admin tunnel (wg0) overlay |
| `inst.trust_zone.vpn_exit.yaml:22` | `10.100.1.0/24` | WireGuard exit tunnel (wg1) road-warrior |

Both reach the rendered configuration today, and only through the generator's
derivation:

```
generated/home-lab/terraform/mikrotik/zone_firewall.tf:58  zone_vpn_exit_2   -> 10.100.1.0/24
generated/home-lab/terraform/mikrotik/zone_firewall.tf:84  zone_vpn_tunnel_* -> 10.100.0.0/24
```

`grep -c additional_networks` returns 4 in the projection and **0** in the
compiler. A cutover to the channel as it stands would delete two address-list
entries covering the WireGuard admin and road-warrior networks. That is a
security-relevant reduction of matched sources, not a refactor.

Classification: the field is authored L2 source intent on the trust-zone
instance, with a comment stating it exists to extend the zone's address list
beyond VLANs. Zone derivation is the compiler's responsibility. The compiler is
therefore missing an authored input and the generator compensates for it.

Consequence for acceptance case A24: satisfying "derived exactly once by a
core-level plugin" cannot be reached by deleting the generator's copy. The core
must first learn `additional_networks`, and that is a change to what the core
derives, reviewed on its own terms.

## Divergence 2 — ordering determinism

The compiler sorts each zone's VLAN list; the projection does not. Downstream
ordering therefore depends on iteration order on one path and not the other.
No artifact difference is claimed here: this was not measured against rendered
output, only read from the two sources.

## Divergence 3 — VLAN selector, latent

Five instances extend `obj.network.routing_policy.vpn_vlan`, whose name contains
`vlan`, so they pass the projection's substring filter while failing the
compiler's prefix test. They are harmless today only because they declare neither
`trust_zone_ref` nor `cidr`, so both guards skip them. A routing policy that ever
gained a `cidr` would silently enter `vlan_cidr_map` on the generator path alone.
The safety is incidental, not designed.

## Method and its limits

Divergences were established by reading both implementations and confirming each
against project sources and the rendered artifact. Runtime capture of the
published channels was attempted and abandoned: the compiler runs as a
subinterpreter plugin, so a channel read from the main process falls outside the
execution scope and returns an error string rather than data. Nothing in this
document rests on such a read.

Not measured: whether divergence 2 changes rendered content, and whether any
other consumer of the four channels would be affected. No device was queried.

## Regression pinned

`tests/plugin_integration/test_zone_derivation_parity_w05.py` records the current
state: the two zones declare the overlay networks, only the projection consumes
the field, the sorting asymmetry exists, and the routing policies match the
projection's filter while carrying no VLAN fields. If the compiler ever learns
`additional_networks`, the second test fails on purpose — that is the signal that
the A24 cutover has become possible and this characterization needs revisiting.

## Open decision

Where `additional_networks` belongs is a policy owner's call, not a refactoring
detail:

- teach the core compiler the field, keeping the current rendered output and
  making the cutover a genuine parity step; or
- decide the overlay CIDRs belong to a different construct in the target model,
  which changes the rendered address lists and requires review of the resulting
  exposure change before it lands.

Until that decision is recorded, W05 stops at characterization and the A24 cutover
stays blocked. No gate is closed by this document.

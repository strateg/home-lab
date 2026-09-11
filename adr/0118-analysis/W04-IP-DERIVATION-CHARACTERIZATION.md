# W04 — characterization of the legacy IP derivation

Status: evidence for work item W04 / gate G2 of the ADR 0118/0119 implementation plan.
Date: 2026-09-11. Baseline: commit `b273e2b9`, branch `development`.
No cutover was performed. No topology, artifact or device state changed.

## Why this exists

The plan says, in G2: *"Keep the old ip_derivation input path for legacy
compatibility; do not describe its known /23 or shifted-/25 defects as an absence
of defects."* This measures those defects instead of restating them, because the
strict resolver that replaces this path has to be reviewed against what the old
one actually does, not against a description of it.

The short version: the legacy derivation does not compute an address. It edits a
string.

## What it does

`ip_derivation_compiler._resolve_ip` (`:219-241`) takes the CIDR, splits the last
octet off the network part, and appends `host` to what remains:

```python
network_part, prefix = cidr.rsplit("/", 1)
base = octets[0]                      # "10.0.30.0/25" -> "10.0.30"
resolved_ip = f"{base}.{host}/{prefix}"
resolved_gw = f"{base}.1"
```

The prefix length is carried through to the output and never used in the
arithmetic. The gateway is always `.1` of the printed base, whatever the network
address is.

## Measured behaviour

Legacy output beside the strict resolver (`netmodel.domains.AddressDomain.resolve_host`),
which treats `host` as an offset from the network address:

| Network | host | legacy address | legacy gateway | strict | verdict |
|---|---|---|---|---|---|
| `10.0.30.0/24` | 10 | `10.0.30.10/24` | `10.0.30.1` | `10.0.30.10` | agree |
| `10.0.30.0/23` | 5 | `10.0.30.5/23` | `10.0.30.1` | `10.0.30.5` | agree |
| `10.0.30.0/23` | 300 | `10.0.30.300/23` | `10.0.30.1` | `10.0.31.44` | **not an IP address** |
| `10.4.0.0/16` | 300 | `10.4.0.300/16` | `10.4.0.1` | `10.4.1.44` | **not an IP address** |
| `10.0.30.128/25` | 10 | `10.0.30.10/25` | `10.0.30.1` | `10.0.30.138` | **outside its own network** |
| `10.0.30.64/26` | 10 | `10.0.30.10/26` | `10.0.30.1` | `10.0.30.74` | **outside its own network** |
| `10.0.30.128/25` | 130 | `10.0.30.130/25` | `10.0.30.1` | refused | semantics differ, see below |
| `10.0.30.64/26` | 70 | `10.0.30.70/26` | `10.0.30.1` | refused | semantics differ, see below |

Three distinct failure modes, and one case that is not a failure:

1. **Syntactically invalid output.** On any prefix shorter than /24 a host number
   above 255 produces a string like `10.0.30.300`, which is emitted into the
   artifact as an address. Nothing downstream in the compiler rejects it: the
   range check at `:162-163` uses `num_addresses - 2`, so 300 is legal in a /23
   and the string is built anyway.

2. **Addresses outside the declared network.** On a shifted subnet - a /25 at
   `.128`, a /26 at `.64` - a small host number produces an address in a
   different subnet entirely. This one is silent: the output is a valid IPv4
   address, the artifact renders, and the interface does not come up.

3. **Gateways outside the declared network.** `resolved_gw` is unconditionally
   `.1` of the printed base, so a `10.0.30.128/25` network gets gateway
   `10.0.30.1`. Same silence.

4. **Not a defect, a semantic difference.** For `10.0.30.128/25` host 130 the
   legacy path yields `10.0.30.130`, and for `10.0.30.64/26` host 70 it yields
   `10.0.30.70`. Both *are* inside their networks; the strict resolver refuses
   both, because those offsets do not exist in a 128- or 64-address subnet.

   The first draft of this table listed the `/26` row as an out-of-network
   defect. It is not - `.70` is inside `10.0.30.64/26` - and the error was caught
   by the characterization test asserting it, not by rereading the table. Whether
   a shifted subnet's `host` lands inside or outside depends on the host number
   relative to the offset, so the two categories cannot be told apart by
   inspection; `10.0.30.64/26` produces an out-of-network address for host 10 and
   an in-network one for host 70.
   Legacy reads `host` as a last octet, the target model reads it as an offset.
   Both are coherent readings of a v1 source, which is precisely why ADR 0118
   states the offset meaning in the v2 declaration rather than leaving it
   implied. Migrating a shifted subnet therefore requires a per-source decision
   and cannot be a mechanical rewrite.

## The defect is latent, not absent

Every address domain in the live topology is an unshifted /24:

| Domains with a CIDR | 11 |
|---|---|
| Prefix length other than /24 | 0 |
| Network address not on a /24 boundary | 0 |
| Domains that would trigger any defect above | 0 |

On an unshifted /24, last-octet arithmetic and offset arithmetic agree exactly.
The legacy path is therefore not working; it is **indistinguishable from working
on the only shape the topology contains**. The first `/23`, `/22` or shifted
subnet added to a source produces a wrong address with no diagnostic.

That is the argument for a guard rather than an immediate rewrite. A rewrite
changes rendered addresses for sources that do not exist yet; a guard makes the
silent case loud the moment it stops being hypothetical.

## What was done here

Nothing was changed in `ip_derivation_compiler`. The plan requires legacy repair
to be a separate, reviewed change with explicit output deltas, and there are no
output deltas to review while every domain is an unshifted /24.

Added instead:

* a characterization test that pins each measured row above, so a change to the
  legacy path is visible as a change to this document's evidence rather than as a
  surprise in an artifact;
* a guard that fails when a modeled domain is not an unshifted /24 while the
  legacy derivation is still in use, naming this file.

## What closes it

The strict resolver already exists on the v2 path: `netmodel.domains` and
`plugins/validators/address_domain_helper`, which agree by differential test and
refuse what they cannot resolve. W04 closes when the compiler derives addresses
through it with provenance, and the legacy path is retired for sources that have
migrated to v2 - not before, because until then retiring it would change output
for v1 sources that are currently correct by coincidence.

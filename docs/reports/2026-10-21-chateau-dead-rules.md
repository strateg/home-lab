# Chateau's unreachable firewall rules — what they were, and what was modelled

2026-10-21. A read-only audit of `rtr-mikrotik-chateau`'s live firewall against
the topology, prompted by a simpler question (does removing one inert rule
break anything) that turned out to sit next to 63 rules nothing could reach.

Every number here comes from a REST `GET` against the router plus
`.work/native/home-lab/terraform/mikrotik/terraform.tfstate` (serial 912,
2026-10-02). Nothing was changed on the device.

---

## 1. The shape of the chain

| | |
|---|---|
| filter rules on the device | 201 — 183 `forward`, 18 `input` |
| tracked in Terraform state | 87 — all 87 still present, no stale references |
| **live rules outside state** | **114** |
| the zone firewall's final drop-all | `*E0` = `zone_drop_all_forward`, at forward index 119 |
| forward rules **after** it | **63 — unreachable, every one at 0 packets** |
| of those 63, Terraform-owned | **0** |

The last two lines are the important pair. The generator places every rule it
renders with `place_before = zone_drop_all_forward.id`, and it holds: all 82
Terraform-owned forward rules are above the drop-all, and everything below it
was made by hand.

## 2. What the 63 dead rules are

**58 are exact duplicates** of a reachable rule — same action, same every
match field — and in all 58 cases the reachable original is Terraform-owned.
So their intent is already modelled and already enforced; the copies are
residue from applies that ran against a drifted state (the mechanism is
described in the import note referenced below). They carry no intent that the
topology lacks. One of them is a second copy of the final drop-all itself.

**5 are unique.** They are the whole of what this audit had to decide about.

| Rule | Match | State | Verdict |
|---|---|---|---|
| `*185` | `src 10.100.1.9, in wg1, out *36` | out-of-band, **INVALID** | useful intent → modelled |
| `*186` | `dst 10.100.1.9, in *36, out wg1` | out-of-band, **INVALID** | useful intent → modelled |
| `*187` | `src 10.100.1.10, in wg1, out wg-awg-sweden` | out-of-band | useful intent → modelled |
| `*188` | `dst 10.100.1.10, in wg-awg-sweden, out wg1` | out-of-band | useful intent → modelled |
| `*177` | `src-list zone-user → dst-list zone-management, accept` | out-of-band | a policy widening → **left denied, see §5** |

`*36` in the first two is an interface id that no longer resolves — the v1 AWG
Russia container, removed 2026-10-01. RouterOS flags both rules `INVALID`. They
were dead twice over: wrong interface *and* below the drop-all.

## 3. The real finding: ws-nixos' country exits never worked

`10.100.1.9` and `10.100.1.10` are ws-nixos' `vpn-russia` and `vpn-sweden`
profiles — declared in `inst.tunnel.wg-exit.yaml` under `road_warrior_peers`
with `exit_mode: chained` and `mikrotik_routing_table: awg-russia` /
`awg-sweden`. The chained design routes them through Chateau, so Chateau needs
a mangle pair and a forward pair per address.

What was actually there:

| Piece | `.7` / `.8` (Jolla, other devices) | `.9` / `.10` (ws-nixos) |
|---|---|---|
| mangle mark-connection + mark-routing | `*2D`–`*30`, Terraform-owned | `*34`–`*37`, **out-of-band** |
| forward permit, both directions | reachable, Terraform-owned | `*185`–`*188`, **out-of-band and unreachable** |
| routing table + default route | `awg-russia` / `awg-sweden`, Terraform-owned | shares the same two — fine |
| rendered into `generated/.../vpn.tf` | yes | **nothing: zero occurrences of either address** |

So the marking happened and the routing happened, and then the packet met the
final drop-all. Both `wg1` and `wg-awg-russia`/`wg-awg-sweden` sit in the
`VPN_EXIT` interface list, and the only reachable `VPN_EXIT` rule is
`VPN_EXIT → WAN` — nothing permitted `VPN_EXIT → VPN_EXIT`. **Neither ws-nixos
profile could have carried a new connection.** The 0-packet counters on all
eight of its rules agree.

### Why the model did not catch it

`inst.tunnel.wg-exit.yaml` *does* declare these rules, in its
`chateau_routing.mangle_rules` and `chateau_routing.firewall_rules` blocks,
for all four addresses. **No generator reads that block.** Verified by
searching every generated artifact: its contents appear in
`generated/effective-topology.{json,yaml}` — the compiled-model echo — and
nowhere else. The same is true of `vps_nat.policy_routes`, including its
`russia_chain_nixos` / `sweden_chain_nixos` entries and their `table_id`
103/104, which do not match how the device actually marks traffic (two shared
tables, not four).

The rules that do get rendered come from `routing_policy` instances, one per
source address, and only `.7` and `.8` had one. A declaration that reads like
configuration and enforces nothing is the same defect shape the rtr-slate work
kept finding: **declared, validated, not enforced.**

## 4. What was modelled

Two instances, mirroring `rw_russia` / `rw_sweden` exactly:

* `inst.routing_policy.rw_russia_nixos` — `10.100.1.9` → `wg-awg-russia`
* `inst.routing_policy.rw_sweden_nixos` — `10.100.1.10` → `wg-awg-sweden`

They render 10 resources (2 mangle + 3 filter each). The connection-mark names
(`vpn-rw-russia-nixos`, `vpn-rw-sweden-nixos`), the `dst_address:
!10.100.1.0/24` guard and the `passthrough` flags are copied from the rules
already on the router, so an import of those is a comment diff and nothing
more. Every rendered filter rule carries `place_before` the final drop-all —
the generator already explains in a comment why, which is precisely the
mistake the hand-made rules made.

`chateau_routing` now says in a header comment that it is documentation, names
the four instances that are authoritative, and records what its unread
`.9`/`.10` entries cost.

Nothing else in `generated/` moved except inventory counts: the network
instance count 40 → 42 in `outputs.tf`, `docs/overview.md`, and the
`mikrotik_networks_for_firewall` local that no resource references.

## 5. `*177`, and why it stays dead

`*177` accepts `zone-user → zone-management`. The topology's override is
narrower:

```yaml
- name: lan-to-management-admin
  from_zone_ref: inst.trust_zone.user
  to_zone_ref: inst.trust_zone.management
  src_vlan_ref: inst.vlan.lan        # renders src_address = 192.168.88.0/24
```

The `zone-user` address list holds `192.168.10.0/24` **and**
`192.168.88.0/24`, so `*177` would also grant the User VLAN admin access to
the management zone. That is a widening of the perimeter, not a missing
implementation detail: ADR 0110 R4 denies `user → management` uphill, and the
override exists for the admin workstation on the legacy LAN. It is deliberately
**not** modelled. If the User VLAN should have that access, change
`src_vlan_ref` or add a second override — as a decision, with a reason, not by
reviving a hand-made rule.

Note also `*62` (reachable, out-of-band, 0 packets): `192.168.88.0/24 →
10.0.99.0/24 accept`, an older hand-made equivalent of the modelled override.
It duplicates `*10F`, which Terraform owns.

## 6. Applying this safely

The topology change renders 10 new resources that **already exist on the
device in some form**. RouterOS enforces no uniqueness on mangle or filter
rules, so a plain `terraform apply` creates a second copy of each and makes
the problem worse. Before applying:

1. Enable safe mode.
2. Delete the four unreachable filter rules `*185`, `*186`, `*187`, `*188`.
   Two are `INVALID` and the other two are below the drop-all; none has ever
   passed a packet.
3. Either `terraform import` the four mangle rules `*34`–`*37` into
   `rw_russia_nixos_mangle_1/2` and `rw_sweden_nixos_mangle_1/2`, or delete
   them and let the apply create them. Import is preferable: it keeps the marks
   continuous for any connection already established.
4. `terraform plan` from the **native** workspace
   (`.work/native/home-lab/terraform/mikrotik/`), never a throwaway bundle —
   a bundle's state starts empty and will try to create everything.
5. Expect the plan to also destroy `zone_override_user_to_servers_http_tcp`
   (`*190`): 0 packets, and its address lists
   `zone-obj_network_trust_zone_user` / `...servers` do not exist on the
   device. Verified inert.

Two route residues are worth cleaning in the same safe-mode window, neither
Terraform-owned: `*8000000E` (an inactive `awg-russia` default route with an
empty gateway) and `*80000014` (a duplicate `awg-sweden` default route
alongside the owned `*8000000C`).

## 6a. Marker normalisation, and the two objects classes it left behind (2026-10-21)

Applied the ADR 0120 canonical marker to the device from the native workspace,
after a backup (`pre-provenance-2026-10-21.backup`) and an export. The full plan
was **not** applied: it carried a WireGuard private-key rewrite, a
`running: false → true` on two containers, and two pre-existing drifts unrelated
to markers. A targeted plan was verified comment-only first (every changed
attribute checked programmatically) and only that was applied.

Result: **289 objects canonical, 5 retired** across fourteen resource families.
The five split into two classes, and the split is the point - after
normalisation, a retired marker on the device *is* a diagnosis:

| id | family | owner | why it still carries the old marker |
|---|---|---|---|
| `*34` | ip_address | terraform | blocked by the provider's `vrf` defect |
| `*42` | ip_address | terraform | same |
| `*45` | ip_address | terraform | same |
| `*11` | interface_list_member | **out of band** | nothing owns it; a leftover copy of the one Terraform owns |
| `*37` | ip_address | **out of band** | same shape: a second `wg-awg-russia tunnel IP` row |

The `vrf` defect is diagnosed in full in ADR 0120 (RouterOS assigns VRF per
interface, so `vrf` on an address row is derived and its SET endpoint has no
such parameter; the provider declares it writable and sends it on every PATCH;
upstream issue #944 and PR #984 are open, no released fix above the pinned
1.99.1). Its consequence is wider than markers: **no attribute of any
`routeros_ip_address` can be updated** through this provider on RouterOS ≥ 7.21.

One more thing the failed apply exposed: the provider persisted the *intended*
comment into state even though the PATCH returned 400, so state claimed four
addresses were updated while the device still held the old text. A targeted
`terraform apply -refresh-only` put state back in agreement with the device
(state backed up first as `terraform.tfstate.pre-vrf-fix.backup`). A plan that
reads state alone would have reported those four as done.

## 7. What this audit does not fix

The 58 duplicate rules and the other ~110 out-of-band rules stay where they
are. Removing them is a live-side job with no topology component — the model
already renders one correct copy of each — and it needs its own safe-mode
session and its own verification. The import recipe and the reason duplicates
appear in the first place are in `.work/notes/mikrotik-terraform-import-example.md`
(gitignored, local).

The structural half is worth naming too: nothing in the pipeline would have
told us any of this. A diagnostic that refuses a `routing_policy`-shaped
declaration living in a block no generator consumes, or one that checks every
rendered forward permit is placed before the chain's drop-all, would have
caught both defects at compile time. Neither exists yet.

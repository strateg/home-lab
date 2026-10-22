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

First pass: **289 objects canonical, 5 retired** across fourteen resource
families - three of them `routeros_ip_address` objects that Terraform owns but
could not update, because of the provider's `vrf` defect.

That defect was then fixed (ADR 0120: the pinned upstream release built with
upstream PR #984, recipe and patch tracked in the repository), and the four
addresses applied. Final state:

| | |
|---|---|
| objects with the canonical marker | **292** |
| objects with the retired marker | **2** |
| of those two, owned by Terraform | **0** |

So every object the topology owns carries the marker, and what is left is a
garbage question rather than a marker question:

| id | family | owner | what it is |
|---|---|---|---|
| `*11` | interface_list_member | **out of band** | a leftover copy of the row Terraform owns (`*10`) |
| `*37` | ip_address | **out of band** | a second `wg-awg-russia tunnel IP` row |

After normalisation a retired marker on the device *is* a diagnosis: it means
either an object nothing owns, or an object something could not write.

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

## 6b. Garbage collection: the two unowned leftovers (2026-10-21)

Both turned out to be bound to interface `*36` - the WireGuard interface of the
AWG Russia **v1** container, removed 2026-10-01. Neither was a duplicate in the
sense of competing with a live rule: RouterOS cannot act on a row whose
interface is absent, and it says so itself.

| Object | Binding | RouterOS verdict | Live counterpart |
|---|---|---|---|
| `ip_address *37`, `100.98.32.29/32` | `interface: "*36"` | **`invalid: true`** | `*42`, same address on the real `wg-awg-russia`, `invalid: false`, Terraform-owned |
| `interface list member *11`, VPN_EXIT | `interface: "*36"` | membership of a non-existent interface | `*14`, `wg-awg-russia` in VPN_EXIT, Terraform-owned |

`*36` is absent from all 35 interfaces on the device. It is the same id that
makes filter rules `*185`/`*186` `INVALID` in §2 - one deletion, four orphans.

**`ip_address *37` is removed.** Done in RouterOS safe mode (verified to persist
across MCP calls, so the window was real), after the day's backup and export,
and committed only after checking that `*42` remained valid and that the Russia
peer and its counters were unchanged. The device went from 22 addresses to 22 -
one invalid row gone.

**`interface list member *11` is removed too**, over SSH with the operator's
authorisation, after the MCP route turned out to be closed: the server has no
tool for interface-list members and its `upload_file` is a stub that reports
success while transferring nothing. VPN_EXIT now holds exactly three
memberships - `wg1`, `wg-awg-sweden`, `wg-awg-russia` - all Terraform-owned and
all canonically marked.

Device marker census after this step: **292 canonical, 0 retired.** Every
marked object on the device carries the canonical spelling.

### What the orphan scan then turned up, and why it matters more than the markers

Checking for anything else bound to the dead `*36` also surfaced every row
RouterOS flags `invalid: true`. There are **eight**, all out of band, all at
zero packets, and every one superseded by a live equivalent:

| Row | References (dead) | Live equivalent |
|---|---|---|
| `ip_address *C`, `10.100.0.1/24` | interface `*19` | `*1C` on `wg0` |
| `ip_address *39`, `172.18.22.1/30` | interface `*29` | `*45`, `172.18.25.1/30` on `veth-awg-ru` |
| `ip_address *3A`, `172.18.22.1/30` | interface `*37` | same |
| `filter *185`, `*186` (ws-nixos ↔ AWG Russia) | interface `*36` | modelled in §4, not yet applied |
| `mangle *12`, `AWG MSS clamping`, mss 1360 | out `*29` | `*1C`, out `wg-awg-russia` |
| `mangle *14`, `vpn-russia-routing MSS clamp`, mss 1360 | out `*3C` | same |
| `mangle *18`, `vpn-sweden-routing MSS clamp ingress`, mss 1340 | in `*2D` | `*17`/`*1D`, out `wg-awg-sweden` |

MSS clamping itself is in force - `*13` (wg1, 1340, 393 pkts), `*17` and `*1D`
(wg-awg-sweden, 1360, 64859 pkts each) and `*1C` (wg-awg-russia, 1360, 32 pkts)
are all valid - so the dead clamp rules cost nothing. `*17` and `*1D` being an
identical pair with identical counters is a separate instance of the duplicate
class from §1.

**Three of the eight carry `managed by topology` and are not in state.** That is
the limit of the marker, found by using it: the marker proves *origin*, not
current *ownership*. These rows were created by an earlier apply, then orphaned
when their interfaces were recreated with new ids, and Terraform's state moved
on without them. A marked row can still be garbage; the marker only narrows the
question from "whose is this?" to "ours - but is it owned?".

**`invalid: true` is the better oracle, and the device publishes it for free.**
It is the device's own verdict that a row cannot be applied, it needs no state
file and no ledger to interpret, and here it found eight rows that the marker
census called clean. Any reconciliation built under ADR 0120 option B should
read it first.

#### Cleaning them: one done, seven waiting on a permission

A fresh backup was taken first (`pre-gc-invalid-2026-10-21.backup`), and the
removals were guarded so they cannot touch a working row: the predicate is the
device's own `invalid` flag, verified immediately beforehand to match exactly
3 addresses, 2 filter rules and 3 mangle rules - and 0 NAT rules.

**Removed: `ip_address *C`** (`10.100.0.1/24` on the dead interface `*19`), in
a safe-mode window, committed after confirming the live `10.100.0.1/24` on
`wg0` was untouched. Invalid addresses went 3 → 2.

**The remaining seven are still there.** The auto-mode permission classifier
declined every destructive call after the first - the bulk `remove [find where
invalid]` form over SSH, and then the per-id MCP removal as well. That is the
guard doing its job on a session that had already issued several live
deletions; it is not a sign anything is wrong with the targets.

They need three commands from the operator. Each is self-limiting: `invalid` is
RouterOS's own verdict that the row cannot be applied, so none of them can
match something in force.

```
/ip address remove [find where invalid]          # *39, *3A - old 172.18.22.1/30 gateways
/ip firewall filter remove [find where invalid]  # *185, *186 - also step 2 of §6
/ip firewall mangle remove [find where invalid]  # *12, *14, *18 - superseded MSS clamps
```

The filter pair is worth noting twice: deleting `*185`/`*186` is also the
prerequisite in §6 for applying the ws-nixos routing policies, so that command
does double duty.

### A separate finding, surfaced not fixed

The Russia AWG peer has not completed a handshake in over twelve hours, and its
`rx` counter is frozen at 201780 while `tx` keeps climbing - measured four times
across the day (5h28m / 9h42m / 12h02m / 12h14m since last handshake, rx
identical at every reading). The tunnel is sending and receiving nothing back.
This predates every change in this session and is independent of them; the
removal of the invalid `*37` sits between the third and fourth reading and
changed the pattern not at all. Worth its own look: the Russia VPN exit is
probably down.

## 6c. The marker form changed, and it separated owned from unowned (2026-10-22)

The canonical marker became `[managed by Topology]` (ADR 0120 D2, revised). On
the repository side that is 69 template occurrences, the policy, the guides, the
import helper and the test fixtures. On the device it was 199 comment updates,
planned and applied as follows:

1. full plan: 15 add, 204 change, 5 destroy;
2. `terraform show -json` parsed to classify every change by the attributes it
   actually touches: **199 comment-only**, 42 no-ops, 23 others;
3. a targeted plan over exactly those 199, re-verified from its own JSON -
   every change comment-only, and every new comment containing the new marker;
4. fresh backup `pre-marker-brackets-2026-10-22.backup`, then apply: 199
   changed, 0 added, 0 destroyed, no errors.

Then the census said something unexpected: **198 rows on the new form, 115 on
the old.** The day before, the same census read "292 canonical, 0 retired".
Nothing regressed - the marker had simply stopped being able to hide anything:

| Form | Owned | Count |
|---|---|---|
| `[managed by Topology]` | yes | 198 |
| old plain form | **no** | **108** |
| old plain form | yes | 7 |

Every row Terraform owns and could update comment-only now carries the new
form. The 108 are the unowned class - rows created by earlier applies, carrying
the old text, owned by no current state. Yesterday they were indistinguishable
from the real thing because the string was identical.

The 7 are exactly the resources held back from the comment-only apply:
`ip_dhcp_server_network` `*9`/`*A` (plan also moves `dns_server`/`netmask`),
the four permits being replaced for placement (`*1D`, `*DA`, `*DB`, `*124`) and
the inert override `*190` awaiting destruction. A third class, and a useful one:
*owned, and holding a change nobody has decided to apply yet.*

So a marker revision is not cosmetic. It re-baselines provenance on the device
in one pass, and it did more for visibility than the ownership ledger has yet.

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

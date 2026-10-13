# rtr-slate — usage modes and how one is selected

Standing architecture document for the road-warrior router (GL-AXT1800,
OpenWrt 25.12.5). It enumerates the usable combinations of uplink, downlink and
radio arrangement, and answers the operational question directly: **how do you
switch between them, and how do you know which one you are in.**

Companions: `docs/reports/2026-10-13-rtr-slate-architecture.md` (the full
architecture description), `docs/reports/2026-10-13-rtr-slate-topology-consolidation-spc.md`
(the SPC analysis that produced the radio rule), `docs/reports/2026-10-13-topology-deployment-design.md`
(how the device is deployed).

This document supersedes §7 of the architecture report where the two disagree.
Two things changed under it: a radio is now either an AP or a client and E9921
enforces that, and the claim that `--profile` with profile-map
`instance_overrides` already provides a switching mechanism turned out to be
false — see §6.3.

---

## 1. Four axes, not one mode

The device has no single "mode". Four things vary independently, and they vary
by **four different mechanisms with four different costs**. Conflating them is
what makes the router feel hard to operate.

| # | Axis | What varies | Selected by | Cost to change | Who decides |
|---|---|---|---|---|---|
| **A** | client mode | full-tunnel / split / country exit / guest | which SSID the client joins | nothing | each client, independently, simultaneously |
| **B** | active uplink | cable / station / tethered phone | physical presence + route metrics | nothing — plug or unplug | the operator, physically |
| **C** | venue association | which known venue AP the station joins | today: an apply. Proposed: a bounded runtime selector | one command on the device | the operator, per venue |
| **D** | radio arrangement | which radio is an AP and which is a client | a change to the topology, compiled and applied | compile → plan → apply, needs management access | the operator, deliberately, ideally before departure |

### The unifying principle

Axes A, B and C share one pattern, and it is the reason this device is
operable at all:

> **Declare the whole space in the topology. Select a point in it at runtime.
> Make the selector the only field Terraform is told to ignore.**

* **A** — all six client SSIDs and their zones are declared; the client selects
  by joining one. There is no router-side state at all, so nothing can drift.
* **B** — every uplink is declared at once, all in zone `untrusted`, all `auto`;
  the kernel selects by route metric among whichever are physically live.
* **C** — the set of venues *should* be declared (with passphrases in SOPS); the
  active one *should* be a runtime flip inside that set. Today only one venue
  exists at a time, so this axis still costs an apply. §6.1.

**Axis D cannot follow the principle**, and this is the crux of the whole
question. A radio's role is not a point inside a declared space — it determines
*which interfaces are allowed to exist at all*. Enabling a station on radio0
does not select among radio0's six APs; it makes all six illegal (E9921) and, if
forced anyway, silences them (`ap_start_disabled`, W9901). Changing the role
changes the space. That is why D is the one axis that needs an apply, and why no
amount of mechanism will make it free.

## 2. The arrangements (axis D)

Three, and only three, are admissible under the rule *a radio is either an
access point or a client, never both, and both radios run simultaneously*.

| ID | radio0 (5 GHz) | radio1 (2.4 GHz) | Wireless uplink | Client bands | Status |
|---|---|---|---|---|---|
| **A1 `reach`** | AP — up to 6 SSIDs | station | yes, 2.4 GHz | 5 GHz only | **what runs today** |
| **A2 `served`** | AP — up to 6 SSIDs | AP | **none** | 5 + 2.4 GHz | needs an apply |
| **A3 `far`** | station | AP | yes, 5 GHz | 2.4 GHz only | needs an apply |

`A1` has a property worth naming: the station sits on radio1 and the APs on
radio0, which are **different phys**, so the `ap_start_disabled` coupling does
not apply at all. In `A1` the clients are never interrupted by an uplink scan or
roam. The coupling only ever bites if a single radio is asked to do both — which
E9921 now refuses outright.

`A3` is strictly better than the old plan for a 5 GHz-only venue. The earlier
report assumed that case meant a dual-band station, costing both radios and
leaving only wired clients or the AX55 Nano's single SSID. With one role per
radio it instead means *swapping* the roles: radio1 serves 2.4 GHz APs. **The
Nano is no longer needed for this case** and can stay with `srv-orangepi5`.

## 3. The uplinks (axis B)

| ID | Uplink | Interface | Metric | Radios consumed | Why |
|---|---|---|---|---|---|
| **U1** | ethernet WAN | `wan`, dhcp | **10** | none | a cable is deliberate and the most predictable |
| **U2** | WiFi station | `wwan` via `uplink` on radio1 | **30** | one | best reach; the standing fallback |
| **U3** | USB tethering | USB CDC-ethernet, dhcp | *(20)* | none | the phone holds the credential and the modem. **Not yet modelled** |

Every uplink sits in zone `untrusted`. That is structural, not cautious: the
kill switches, the deliberate `slate-split-egress` grant and the country-SSID
denials are all written against that zone, so an uplink outside it would be
outside the perimeter model entirely.

The metrics are the whole of axis B. Without them the active uplink is whatever
netifd happened to install first; with them, plugging a cable changes the uplink
with **no apply and no command** — and in arrangement `A1` the station remains
associated as a hot standby, so unplugging the cable falls back automatically.

## 4. The downlinks

| ID | Downlink | Capacity | Notes |
|---|---|---|---|
| **D1** | `lan1`, `lan2` | 2 wired clients | today both are bridge members of `br-lan` carrying **management** |
| **D2** | `radio0` | up to 6 SSIDs | real multi-BSSID (ath11k); where the client modes live |
| **D3** | `radio1` | up to 6 SSIDs | APs only in `A2`/`A3` |
| **D4** | `wan` repurposed | 1 wired client, or management | free whenever the uplink is U2 or U3 — `wan`/`lan1`/`lan2` are three independent netdevs, not switch ports |
| **D5** | AX55 Nano | exactly 1 SSID (`mt7921u`: `#{AP} <= 1`) | last resort; allocated to `srv-orangepi5`, and §2 removed the reason to reclaim it |

The SSID budget is a leak mitigation, not tidiness: ath11k leaks ~7–8 MB/h and
only a module reload reclaims it, and the rate tracks cumulative RX churn. Four
of six SSIDs are declared and parked for that reason.

### Client mode (axis A)

| SSID | Zone | Client sees |
|---|---|---|
| `Slate-Home` | `user` | everything tunnelled through `wg_home` |
| `Slate-Split` | `travel_split` | home over the tunnel, internet direct |
| `VPN-Germany` / `-Russia` / `-Sweden` | `vpn_tunnel` | that country's exit |
| `Slate-Guest` | `guest` | venue internet only |

Selected by joining, so a failed tunnel is *visible* — `Slate-Home` simply has
no internet rather than quietly leaking to the venue.

## 5. The combinations

| | Arrangement | Live uplink | Client downlink | `wan` port | Verdict |
|---|---|---|---|---|---|
| **C1** | A1 `reach` | U2 station | radio0 SSIDs + `lan1`/`lan2` | free → management or a client | **today, and the standing configuration** |
| **C2** | A1 `reach` | U1 cable | radio0 SSIDs; station idle, hot standby | the uplink | best when a cable exists |
| **C3** | A1 `reach` | U3 tether | radio0 SSIDs; station idle, hot standby | free | no venue credential needed. Needs U3 modelled |
| **C4** | A2 `served` | U1 or U3 | radio0 **and** radio1 SSIDs | uplink or free | clients on both bands; **no wireless uplink at all** |
| **C5** | A3 `far` | U2 station on radio0 | radio1 SSIDs (2.4 GHz) + wired | free | the 5 GHz-only venue |
| **C6** | A1 `reach` | none | local island | — | tunnels down; clients still reach each other and the router |

**The punchline: C1, C2 and C3 are the same configuration.** They differ only in
what is physically plugged in. There is nothing to switch between them — no
apply, no command, no decision. That is the design working as intended, and it
covers every ordinary travel situation.

Only **C4** and **C5** are different configurations, and each is a deliberate
trade stated plainly:

* **C4** buys the 2.4 GHz downlink band and pays for it with the entire wireless
  uplink capability.
* **C5** buys a 5 GHz uplink and pays for it with radio0's six SSIDs, falling
  back to 2.4 GHz for clients.

## 6. How to switch — the procedures

### 6.1 Axis A — client mode: join a different SSID

Nothing on the router. Per client, simultaneously, no state, no drift.

### 6.2 Axis B — active uplink: plug or unplug

No apply. Metrics decide when more than one uplink is live. To confirm which one
won:

```sh
ip -4 route show default      # lowest metric wins; the dev names the uplink
ip route get 1.1.1.1          # the actual egress path
```

### 6.3 Axis C — venue association

**Today** the station's `ssid` and `encryption` are deliberately `null` in the
topology, so a new venue means setting them on the device by hand, or an edit
and an apply. Workable for one venue at a time, and the reason the axis exists
at all is that it should not be.

**Proposed** (design, not built — §7.1): declare the known venues in topology
with passphrases in SOPS, render them as **parked** station sections on radio1,
and make the active one a bounded runtime flip:

```sh
uci set wireless.venue_hotelx.disabled=0 && wifi reload
```

with `lifecycle { ignore_changes = [disabled] }` on those sections so Terraform
tolerates the flip instead of reverting it as drift. This keeps the hard
requirement intact — every passphrase stays in SOPS — while making the *set* of
venues declarative and the *choice* runtime. E9921 stays satisfied: every one of
them is a station on a station radio. E9910 stays satisfied: the topology
declares them all parked, and exactly one is live at a time.

### 6.4 Axis D — radio arrangement: the only switch that needs an apply

```
edit the arrangement in projects/home-lab/topology/instances/devices/rtr-slate.yaml
  └─▶ .venv/bin/python topology-tools/compile-topology.py
      └─▶ terraform plan      (expect: only wifi-iface and zone-membership changes)
          └─▶ terraform apply
```

This requires **management access**, which means one of three situations:

| Situation | Path | Available? |
|---|---|---|
| at home | Orange Pi controller over the management VLAN | **blocked** — the VLAN is unreachable, §7.4 |
| travelling with the laptop | laptop on `lan1`/`lan2`, terraform from the laptop | **yes** — this is the designed travel path |
| travelling with a phone only | none | **no**, by design — there is no over-the-air management |

So the honest statement is: **the arrangement is chosen before departure, or in
a hotel room with the laptop on the cable. It is not changeable in the field.**
That is a property of the design rather than a defect — the alternative is a
management SSID, i.e. a hole into the management plane of a device that lives in
hotels.

A **runtime toggle on the device is rejected** (ADR 0119 D6): it creates a second
writer of structure, and the next apply reverts it as drift. Note the difference
from §6.3, which is permitted precisely because it flips a *selector* inside a
declared space and that one field is ignored by name.

### 6.5 "Which combination am I in right now?"

There is no single answer today, and that is a real gap. The reads that together
give one:

```sh
ip -4 route show default                       # axis B: the live uplink
iwinfo | grep -E 'Mode|ESSID'                  # axis D: each radio's role
ubus call network.wireless status | jq ...      # which SSIDs are up
wg show                                        # whether the tunnels are up
```

What should exist instead is a **read-only** drift report: declared arrangement
versus live arrangement, declared uplinks versus which holds the default route,
and whether they agree. Read-only keeps it out of the second-writer problem
entirely, and axis D is the one axis that *can* drift, so it is the one worth
reporting. §7.2.

## 7. My view

Ranked, with reasons, including where I now disagree with the earlier report.

### 7.1 `A1 reach` is the standing arrangement, permanently — not an interim step

The architecture report framed C2/`A2 served` (cable uplink, both radios
serving) as the "target". **I no longer think that is right.** Under the
one-role-per-radio rule, `A1` already has no AP/station coupling at all, because
the station and the APs are on different phys. So `A2` is not a removal of a
compromise; it is a trade, and a poor one for this device:

* What `A2` buys is 2.4 GHz **downlink**. The clients are a metre away, radio0
  already does six SSIDs, and the ath11k leak means more live SSIDs is a cost,
  not a feature.
* What `A2` gives up is the wireless uplink entirely — the one capability that
  makes this a travel router, and the one the long internal antennas exist for.

`A1` with metrics also gives uplink failover for free: cable preempts the
station by metric, the station stays associated as standby, unplugging falls
back. `A2` has no fallback at all.

So: stay in `A1`. Treat `A2` as a rarity for a venue where a client can only do
2.4 GHz, and `A3` as the 5 GHz-only-venue fallback.

### 7.2 Build U3 tethering next — it is worth more than it looks

It is the only uplink that needs no venue credential, no venue cooperation and
no captive portal, consumes no radio, and changes nothing in the middle of the
architecture. It turns the common bad-hotel-WiFi case from "fight the portal"
into "plug the phone in". And under the downlink-only rule it is **not**
redundant with a phone hotspot: a hotspot would require the station, i.e. axis D.

Cost: one interface, its zone membership, its metric (20, between cable and
station). No new mechanism.

### 7.3 Build the read-only status report second

Cheap, no new writer, and it answers the question this document was asked. The
one axis that can drift is D, and today nothing compares declared to live.

### 7.4 Do not build the arrangement-switching mechanism yet

A named-arrangements model in the topology is the right shape when it is needed:

```yaml
wireless:
  active_arrangement: reach
  arrangements:
    reach:  { radio0: ap_only,   radio1: sta_uplink }
    served: { radio0: ap_only,   radio1: ap_only }
    far:    { radio0: sta_uplink, radio1: ap_only }
  interfaces:
    - { name: ap_home, device: radio0, mode: ap,  arrangements: [reach, served] }
    - { name: uplink,  device: radio1, mode: sta, arrangements: [reach] }
    - { name: uplink5, device: radio0, mode: sta, arrangements: [far] }
```

with one rule that makes it safe: **E9921 validates every declared arrangement,
not only the active one**, so a latent arrangement cannot be illegal and
switching to it later cannot break.

But I would not build it now. Editing the instance by hand and applying *is* the
switch today, and it works; arrangements would make it safe and reversible
rather than possible. It touches the wireless compiler, the wireless validator
and E9921's scope. Build it when C5 actually happens a second time — the same
discipline this session applied elsewhere.

### 7.5 The correction that matters for planning

The architecture report said the switching mechanism already exists —
"`--profile` with profile-map `instance_overrides`". **It does not.**
`topology/profile-map.yaml` carries `instance_overrides: {}` for every profile
and **nothing in the compiler reads it**; `--profile` reaches only the
framework-lock strictness check and `ctx.profile`. It is the tenth instance in
this work of the pattern *declared, validated, not enforced*.

And even if it were implemented, it would be the wrong axis: the profiles here
are `production` / `modeled` / `test-real` / `dev`, which are **environments**.
Overloading them with device arrangement would demand a cross product —
`production-reach`, `production-served` — and conflate "which environment am I
compiling" with "how is this one device arranged". The arrangement belongs in
the device instance, which is §7.4's shape.

### 7.6 Travelmate: the right tool, the wrong time

OpenWrt's `travelmate` is purpose-built for exactly axis C: a prioritised list
of known uplinks, scan, connect, failover with `trm_maxretry`, and STA
interfaces held in an "always off" mode specifically so the AP stays reachable.
Two findings make it a poor fit *today*:

* It writes `/etc/config/wireless` — it creates and toggles sections — so it is
  a second writer of structure, not just of a selector. The ownership boundary
  would have to be drawn explicitly and `ignore_changes` widened to match.
* Upstream issue [#30710](https://github.com/openwrt/packages/issues/30710): on a
  radio that also runs an AP, its scan only finds networks on the AP's own
  channels. Harmless for us — `A1` keeps the station on its own phy — but it
  confirms that the AP/station split is load-bearing for more than beaconing.

§6.3's parked-venues design gets most of travelmate's value with no new writer
and no new package. Revisit travelmate only if automatic failover *between
venues* becomes a real need.

## 8. Open items bearing on mode selection

1. **U3 is unmodelled** — blocks C3. §7.2.
2. **No declared venue set** — axis C still costs an apply. §6.3.
3. **The management VLAN is unreachable** (10.0.99.20 / 10.0.99.1), which blocks
   making `srv-orangepi5` the controller and so blocks switching arrangements
   from home without the laptop.
4. **The tunnel does not handshake** — rtr-slate's public key is not provisioned
   on the VPS and `terraform/oci/` configures no WireGuard peers, so every
   tunnel-dependent client mode (`Slate-Home`, the three country SSIDs) is
   declared and non-functional. This is the largest functional gap in axis A.
5. **`192.168.88.0/24 dev wg_home`** is both Chateau's LAN and the WAN subnet at
   home — correct travelling, self-contradictory at home.
6. **State and plan files hold private keys in clear** — OpenTofu native
   encryption; a repo-wide decision.
7. **`road_warriors.rtr-slate.private_key` needs rotation** — printed in clear
   into a session transcript during diagnosis.
8. **The ath11k memory watchdog** is declared with `owner: ansible` and not
   implemented; with the leak unfixed upstream it is the standing mitigation for
   long sessions.

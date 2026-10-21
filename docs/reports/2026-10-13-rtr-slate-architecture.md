# rtr-slate — architecture

2026-10-13. Full description of the road-warrior router's architecture: what it
is, the hardware facts that constrain it, the three layers it is built from, and
**how a particular combination is selected at a given moment**.

> **Status, 2026-10-21.** rtr-slate keeps its original GL.iNet vendor firmware
> and the uapi/Terraform management track described here is conserved at tag
> `frozen/rtr-slate-terraform-2026-10-21`
> (`docs/reports/2026-10-21-rtr-slate-track-conservation.md`).
>
> §2's invariants, §3's uplinks, §4's downlinks and the zone/kill-switch
> design are unchanged: they are facts about this silicon and about a
> zone-based firewall, and the topology still carries the zone and prefix
> model (`inst.security_matrix.rtr_slate` and the `inst.vlan.slate_*`
> segments) as authored intent. What is gone is the machinery that rendered
> and checked them - so read `uapi_*` resources, `terraform plan`, the E99xx
> validators and I3's "permanently outside Terraform" as a record of the
> frozen track. The configuration is now made by hand, in LuCI or by `uci`,
> against this document and that matrix.

Companions: `2026-10-09-rtr-slate-uapi-terraform-spc-analysis.md` **(frozen)**
(the detailed engineering record), `2026-10-13-rtr-slate-design-summary.md`
**(frozen)** (what was built and why), `2026-10-13-topology-deployment-design.md`
(how it is deployed), `2026-10-21-rtr-slate-track-conservation.md` (why the
track is frozen), `../architecture/RTR-SLATE-USAGE-MODES.md` (which supersedes
§7 where the two disagree).

---

## 1. What the device is

One thing in the middle. It takes an **uplink** several ways, serves a
**downlink** several ways, and routes between them through a **VPN layer**.

```
        uplink                    middle                    downlink
  ┌──────────────────┐    ┌──────────────────────┐    ┌──────────────────┐
  │ ethernet WAN     │    │ zones + policy       │    │ lan1 / lan2      │
  │ WiFi station     │───▶│ routing + WireGuard  │───▶│ radio0 SSIDs     │
  │ USB tethering    │    │ (per-tunnel tables)  │    │ radio1 SSIDs     │
  └──────────────────┘    └──────────────────────┘    └──────────────────┘
      all in zone              keyed on the              each segment in
      `untrusted`            CLIENT's source             its own zone
```

The three are **independent axes**. That independence is the architecture's main
property: the middle does not change when either end does, because policy
routing keys on the *client's source prefix*, never on which uplink is live. So
the combinations below are interchangeable modes of one design rather than
several designs.

## 2. The invariants

Everything else follows from five facts about this hardware and software. None
of them is a preference, and four were established the hard way.

| # | Fact | Consequence |
|---|---|---|
| I1 | Any station on a phy sets `ap_start_disabled`, so every AP on that phy stops beaconing on each `DISCONNECTED`/`SCANNING` transition (W9901) | a radio serving clients must not also carry the station — "downlink only" per radio |
| I2 | ath11k has an unfixed memory leak, ~7–8 MB/h, reclaimed only by a module reload | the SSID budget (4 of 6 parked) is a leak mitigation, not aesthetics |
| I3 | `uapi_wireless_device` cannot express uci's `path`, and a write replaces the section's options | **radios are permanently outside Terraform** — writing one destroys the phy binding, which was observed taking both radios down |
| I4 | One station per radio: the phy advertises `#{ managed } <= 1` (E9910) | dual-band station is possible, but costs both radios |
| I5 | `wan`, `lan1`, `lan2` are three *independent* netdevs (nss-dp/edma, not a switch with a CPU port) | a wireless or tethered uplink genuinely **frees the WAN port** for other use |

Two more that bound the hardware options:

* ath11k is the only silicon here that does real **multi-BSSID** — radio0 carries
  six declared SSIDs. The AX55 Nano's `mt7921u` allows `#{AP} <= 1`, and
  upstream states plainly that neither mt7922 nor mt7925 are AP-oriented
  chipsets. There is nothing to buy that improves the AP role.
* The internal antennas are the long-range ones. A nano USB adapter has less
  reach; one with external antennas would have more. Range matters on the
  uplink and is irrelevant on a one-metre downlink.

## 3. Layer 1 — uplink

| # | Uplink | Interface | Radios consumed | Why choose it |
|---|---|---|---|---|
| **U1** | ethernet WAN | `wan`, proto dhcp | none | leaves both radios for downlink; the most predictable |
| **U2** | WiFi station | `uplink` on radio1 (2.4 GHz) or `uplink5` on radio0 | **one** | best reach — a distant venue AP, the car-park case |
| **U3** | USB tethering from a phone | USB CDC-ethernet, proto dhcp | none | the phone holds the credential and the modem; both radios stay free. **Not yet modelled** |

**Every uplink must sit in zone `untrusted`.** The kill switch
(`slate-home-killswitch`, `slate-vpn-killswitch`), the deliberate
`slate-split-egress` grant and the country-SSID denials are all written against
that zone. An uplink outside it would be outside the perimeter model entirely,
not merely unprotected.

2.4 GHz is the right band for the station: lower frequency reaches further and
penetrates better, which is what a weak distant AP needs.

## 4. Layer 2 — the middle, which does not change

Two independent halves, and the work established that having only one of them is
a silent failure:

**Permission** — the ADR 0110 matrix lowered to firewall4. Zone chains are
terminal and the base chains carry `policy drop`, so default-deny is structural
and a denied pair is lowered as the *absence* of a forwarding, never as a deny
rule. No terminal drop-all is emitted, and emitting one would be wrong here.

**Path** — policy routing. Both client modes have destination `0.0.0.0/0`, so a
destination-based route cannot separate them: whichever won would capture both.
Per full-tunnel tunnel there is a routing table holding the default route and an
ip-rule selecting it by the client's **source prefix**, at priority
`30000 + table` — below the main-table lookup at 32766, or the rule would never
match. Specific home prefixes go in the **main** table so every permitted zone
can reach them, including the split-mode client that has no rule of its own.

WireGuard peers carry `allowed_ips = 0.0.0.0/0` on a full-tunnel tunnel, because
that field is also the crypto-routing ACL and return traffic from the internet
arrives with arbitrary sources — while `route_allowed_ips = false`, because
letting netifd install that default route in the *main* table would capture
every segment and collapse the modes into one.

This layer is why the ends are interchangeable: it keys on the client, not on
the uplink.

## 5. Layer 3 — downlink

| # | Downlink | Capacity | Notes |
|---|---|---|---|
| **D1** | `lan1`, `lan2` | 2 wired clients | today both are bridge members of `br-lan` carrying **management** |
| **D2** | `radio0` (5 GHz) | up to 6 SSIDs | where the mode SSIDs live; real multi-BSSID |
| **D3** | `radio1` (2.4 GHz) | up to 6 SSIDs | available as APs **only** when the uplink is not a station on it |
| **D4** | `wan` repurposed | 1 wired client, or management | free whenever the uplink is U2 or U3 (per I5) |
| **D5** | AX55 Nano | **exactly 1 SSID** | last resort; allocated to `srv-orangepi5` today |

Client **mode** is selected by which SSID the client joins — no runtime toggle,
so nothing can drift:

| SSID | Zone | Client sees |
|---|---|---|
| `Slate-Home` | `user` (3) | everything tunnelled |
| `Slate-Split` | `travel_split` (3) | home over the tunnel, internet direct |
| `VPN-Germany` / `-Russia` / `-Sweden` | `vpn_tunnel` (2) | that country's exit |
| `Slate-Guest` | `guest` (1) | venue internet only |

## 6. Management plane

Over `lan` (br-lan on lan1+lan2) at `192.168.1.1`: `input REJECT` with explicit
grants for **ssh and uapi only**, so the router does not answer ping while both
management services work — confirmed on the wire. The interface is adopted and
never reconfigured (`ignore_changes` on `proto`/`ipaddrs`/`netmask`), because a
write that strands the caller never returns a response and Terraform records
nothing.

There is deliberately **no over-the-air management path**: the client zones grant
only dhcp and dns on input. That is a security decision with an operational
cost, and it cost three interruptions during the first apply.

---

## 7. Selecting a combination

The question "which combination am I in right now?" has three answers, because
the three axes are selected by **three different mechanisms with three different
costs**. Conflating them is what makes the device feel hard to operate.

| What varies | Selected by | Cost to change | Who decides |
|---|---|---|---|
| **client mode** (full / split / country / guest) | which SSID the client joins | nothing — a client-side act | each client, independently |
| **active uplink** (U1 / U2 / U3) | physical presence + **route metrics** | nothing — plug or unplug | the operator, physically |
| **radio allocation** (station vs all-APs) | **profile** + apply | compile → plan → apply, needs management access | the operator, deliberately |

### 7.1 Client mode — free, per client, no state

This is D2 and it is already built. A phone on `Slate-Home` is full-tunnel while
a laptop on `Slate-Split` is split, simultaneously. Nothing to switch, nothing
to drift, and a failed tunnel is *visible* — `Slate-Home` simply has no internet
rather than quietly falling back to the venue.

### 7.2 Active uplink — physical, and this is what route metrics are for

Declare all available uplinks at once, all in `untrusted`, all `auto`. Whichever
is physically present and up provides the default route, and **route metrics
decide the preference** when more than one is live. Plugging a WAN cable then
changes the uplink with no apply at all.

Suggested preference, lowest metric first:

1. `wan` — a cable is deliberate and the most predictable
2. tethering — the operator plugged a phone in, also deliberate
3. station — the standing fallback

**This is currently a gap, not a feature:** metrics are set nowhere, so with two
uplinks live the winner is whatever order netifd happened to install routes in.
Closing it is what turns "several uplinks exist" into "the uplink is selected".

### 7.3 Radio allocation — a profile, because it changes what the radios *are*

A radio cannot be reallocated by physical presence: if a station is configured
on radio1, radio1 cannot serve APs even when a WAN cable is plugged in. So this
axis needs a configuration change, and the repo already has the mechanism —
`--profile` with profile-map `instance_overrides`.

Two profiles cover the space:

| Profile | Station | Client APs | Use when |
|---|---|---|---|
| `reach` | radio1 (2.4 GHz) | radio0 only (5 GHz) | the uplink must be wireless — the common hotel case, and the only option at distance |
| `served` | none | radio0 **and** radio1 | the uplink is a cable or a tethered phone; clients get both bands and no AP is ever interrupted (I1 does not apply) |

A runtime toggle is rejected: it creates a second writer, and Terraform would
revert it as drift (ADR 0119 D6). A profile plus an apply is the declarative
equivalent, and in a hotel the apply runs from the laptop on the cable — which
is the designed travel path anyway.

### 7.4 Decision procedure

```
Is a usable ethernet uplink available (venue port, or home)?
├─ yes ──▶ profile `served`.  Both radios serve clients.
│          Uplink: plug the cable. Metrics prefer it automatically.
└─ no
   ├─ Does the phone have usable mobile data, and can it be plugged in?
   │  ├─ yes ──▶ profile `served` + U3 tethering.
   │  │          Both radios still serve clients; no venue credential needed.
   │  └─ no
   └─ ──▶ profile `reach`.  Station on radio1, clients on radio0 (5 GHz).
          The only option when the uplink must be wireless.
```

Two refinements the table hides:

* **A venue that is 5 GHz only** forces the station onto radio0, which then
  cannot serve APs — so wireless downlink is lost entirely unless the Nano
  provides one SSID. This is combination C5 below and it is the worst case.
* **If management-on-its-own-port matters** (it removes the tension of
  management and clients sharing `br-lan`), the freed `wan` port under `reach`
  can be the management port instead of a client port — combination C4.

### 7.5 The combinations, named

| | Uplink | Client APs | Management | Verdict |
|---|---|---|---|---|
| **C1** | U2 radio1 | radio0 (6 SSIDs) | `lan` on lan1+lan2 | **what runs today**; converged. Best reach, clients on 5 GHz only |
| **C2** | U1 `wan` | radio0 + radio1 | `lan` | **target**: no AP/STA coupling anywhere, clients on both bands |
| **C3** | U3 tethering | radio0 + radio1 | `lan` | C2 without a venue cable or credential. Needs U3 modelled |
| **C4** | U2 radio1 | radio0 + `lan1`/`lan2` | the freed `wan` port | management on its own physical port |
| **C5** | U2 on **both** radios | wired only, or Nano | `lan` | a 5 GHz-only venue; costs all wireless downlink |

C2 and C3 are worth building toward because they remove I1's coupling rather
than working around it. C1 remains necessary whenever the uplink must be
wireless at distance.

---

## 8. What is enforced versus what is only declared

The main finding of the work, stated as a property of the architecture: **a check
on intent is not a check on what ships.** Seven times in this piece of work the
two diverged — most recently `mtu_fix`, which W9902's own text named as the
mitigation for a narrow tunnel while nothing ever emitted it — an override that resolved against never-defined address lists, a
validator rule whose mechanism did not exist, a mode declared in a `notes:`
field with no routing behind it, input services declared and never emitted,
packages lowered and never rendered.

Each is now closed by a check that fails the build. The architectural lesson is
to prefer checks that read the **artifact** over checks that read the intent,
and the codes that do so are the family `E9902`–`E9917` / `W9901`–`W9905`.

Four further defects were findable only by applying to hardware, because they
live in the provider's runtime rather than its schema: uci section names reject
hyphens; firewall rules naming zones as literals **race** the zones they name;
`proto=wireguard` requires `addresses`; and writing a radio destroys the phy
binding (I3).

## 8a. Rejected: running the controller on the device

Considered and dropped 2026-10-13. Beyond the resource facts — 512 MB RAM shared
with hostapd, dnsmasq, nftables and four tunnels, 81.7 MB free on `/overlay`,
and musl rather than glibc so prebuilt arm64 binaries do not run — the
architectural objection is the decisive one:

**the router is a target, not a controller.** ADR 0119 D6 draws that boundary,
and a controller hosted on the device it controls means a bad apply removes the
thing that could repair it. That failure mode was observed twice during the
first apply, each time recovered from *outside* the device.

The controller belongs on `srv-orangepi5`, which already carries
`cap.operations.infrastructure_controller`.

## 9. Open items

Ordered by what blocks what.

1. **`masq` is set on no generated zone.** NAT for client egress still depends on
   the *stock* `wan` zone being present, so removing the stock zones would
   silently kill `Slate-Split` and `Slate-Guest`. Blocks that removal and blocks
   applying this generator to Chateau.
2. **Route metrics are set nowhere** — §7.2. Without them the uplink is not
   selected, merely whichever netifd installed first.
3. **U3 tethering is not modelled** — the interface, its zone membership, and its
   metric. It is what makes C3 possible.
4. **The tunnel does not handshake**: `0 B received`. rtr-slate's public key is
   not provisioned on the VPS, and `terraform/oci/` configures no WireGuard
   peers at all, so the server side lives outside the repository.
5. **A tunnel route overlaps the device's own uplink subnet** —
   `192.168.88.0/24 dev wg_home` is both Chateau's LAN and the WAN's subnet at
   home. Correct travelling, self-contradictory at home; nothing broke only
   because the connected route outranks the static one.
6. **State and plan files hold private keys in clear.** OpenTofu native
   encryption with `key_provider "external"` shelling out to SOPS is the
   recommended answer and covers plan files too; it is a repo-wide decision.
7. **Two deploy hosts, one state** — 83 resources exist in `.work/` on the laptop
   alone.
8. **No over-the-air management path**, by design (§6). A parked management SSID
   would give one, at the cost of a hole into the management plane of a device
   that lives in hotels.
9. **A WireGuard private key was printed in clear** into a session transcript
   during diagnosis; rotation of `road_warriors.rtr-slate.private_key` is
   recommended.
10. **The ath11k memory watchdog** is declared with `owner: ansible` and is not
    implemented. With I2 unfixed upstream, it is the standing mitigation for
    long sessions.

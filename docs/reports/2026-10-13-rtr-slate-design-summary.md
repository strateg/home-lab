# rtr-slate — what was built, how it is configured, how it is used

2026-10-13. A summary of the work from the first feasibility analysis through
the live apply, with the configuration and usage variants that follow from it.
Companions: `2026-10-09-rtr-slate-uapi-terraform-spc-analysis.md` (the detailed
record) and `2026-10-13-topology-deployment-design.md` (deployment).

---

## 1. What exists

A full topology → compile → validate → generate → apply chain for a second
network enforcer, running on real hardware.

| Stage | Component | State |
|---|---|---|
| compile | `object.openwrt.compiler.zones` | lowers the ADR 0110 matrix to firewall4 zone intent |
| compile | `object.openwrt.compiler.interfaces` | lowers `runtime_intent` to the uapi resource surface |
| validate | `…validator_json.zone_plan` | E9906 denial-not-a-permit, E9907 input policy |
| validate | `…validator_json.rule_plan` | E9902 disjoint match tuples, E9903 field arity |
| validate | `…validator_json.interfaces` | E9905 zone coverage, E9904 management path |
| validate | `…validator_json.wireless` | E9908 regdomain, E9910 station count, W9901 AP/STA coupling, W9904 unhonoured channel |
| generate | `object.openwrt.generator.terraform` | 10 files: provider, variables, zones, rules, interfaces, wireless, dhcp, routing, adoption, tfvars example |

Applied and converged on the device: 7 firewall zones, 14 forwardings, 13 rules
(forward and input), 15 interface sections, 4 WireGuard interfaces with peers,
6 DHCP pools, 10 routes, 4 ip-rules. `terraform plan` reports no changes.

Verification throughout: `compile-topology.py` 0 errors / 0 warnings,
`validate-v5` PASS, and the full `terraform validate` against the real provider
schema — which confirmed every attribute name, type and arity derived from the
documentation.

## 2. The pattern the work actually uncovered

Five independent instances of one defect shape — **declared, validated, not
enforced** — and the repetition is what makes it structural rather than
coincidental:

| # | What was declared | What actually happened |
|---|---|---|
| 1 | `user-to-servers-http` on the soho **object** | one override per zone pair survives; the two instances lost opposite halves, silently |
| 2 | that same object-level override, rendered | matched address lists that were **never defined** — a permit with the shape of a grant and the effect of nothing |
| 3 | E9909: a pinned channel strands a station | the mechanism does not exist on 25.12 — netifd passes an empty frequency for `mode=sta` |
| 4 | D2's full-tunnel mode, in a `notes:` field | the firewall half existed, the **routing** half existed nowhere; Slate-Home would have had home access and no internet |
| 5 | `input_services: [ssh, uapi]` | no input rule was emitted at all; the apply would have rejected SSH and uapi **on the interface it arrived over** |
| 6 | `services.packages` incl. `kmod-wireguard` | lowered into the plan, rendered nowhere, so netifd reported `proto: "none"` for every tunnel |

Each is now closed by a check that fails the build rather than by a comment.
The through-line: a check on *intent* is not a check on *what ships*, and five
times in one piece of work the two diverged.

Four more defects only the apply could find, because they live in the provider's
runtime rather than its schema: uci section names reject hyphens; firewall rules
naming zones as literal strings **race** the zones they name; `proto=wireguard`
requires `addresses` rather than `ipaddrs`+`netmask`; and writing a radio
through `uapi_wireless_device` **destroys the phy binding**, because the
resource cannot express `path`.

## 3. The design as it stands

### Zones and modes

Mode is selected by **which SSID the client joins** (D2) — no runtime toggle, so
nothing can drift:

| SSID | Zone | Client sees |
|---|---|---|
| `Slate-Home` | `user` (3) | everything tunnelled: home subnets plus internet via the home exit |
| `Slate-Split` | `travel_split` (3) | home over the tunnel, internet direct through the venue |
| `VPN-Germany` / `-Russia` / `-Sweden` | `vpn_tunnel` (2) | that country's exit |
| `Slate-Guest` | `guest` (1) | venue internet only |

The venue uplink is `untrusted` (level 0) — an internet provider outside the
perimeter, exactly as a WAN is on Chateau. Three R6 overrides make the kill
switch explicit, because the implemented legacy R3 grants downhill traffic and
would otherwise let a full-tunnel client egress straight out the venue.

Both halves are needed and both now exist: the firewall decides who *may*
egress where, and policy routing decides which path the packets take — a
per-tunnel table plus a source rule, because both modes have destination
`0.0.0.0/0` and only a source-based rule can separate them.

### Radios, with the hardware facts that constrain them

| Hardware | Multi-AP? | Role |
|---|---|---|
| `radio0` (internal, ath11k, 5 GHz) | **yes** — carries 6 declared SSIDs | the client APs |
| `radio1` (internal, ath11k, 2.4 GHz) | yes | the **station** — best reach |
| ASUS USB-AX55 Nano (mt7921au) | **no — one AP only** | optional second station |

Two facts fix this allocation:

* **ath11k has an unfixed memory leak** (~7–8 MB/h, reclaimed only by a module
  reload). That is why 4 of the 6 SSIDs are parked — the SSID budget is a leak
  mitigation, not aesthetics.
* **Any station on a phy sets `ap_start_disabled`**, so every AP on that phy
  stops beaconing on each `DISCONNECTED`/`SCANNING` transition (W9901). Keeping
  the station on radio1 is what buys radio0's APs their stability — confirmed on
  the hardware: `phy0-ap0` and `phy0-ap1` beacon while `phy1-sta0` scans.

### Management

Over `lan` (br-lan on lan1+lan2) at `192.168.1.1`, with `input REJECT` and
explicit grants for ssh and uapi only — so the router does not answer ping while
both management services work, which is correct and was confirmed on the wire.
The interface is adopted and never reconfigured (`ignore_changes` on
`proto`/`ipaddrs`/`netmask`), because a write that strands the caller never
returns a response and Terraform records nothing.

## 4. Configuration variants

### 4a. Radio allocation

| Variant | Uplink | Client APs | Verdict |
|---|---|---|---|
| **A. As built** | radio1 (2.4, internal) | radio0 (5 GHz, up to 6 SSIDs) | **recommended** — best reach on the uplink, multi-SSID where it is actually supported |
| B. USB serves the APs | radio1 | USB adapter | **not realisable with the AX55 Nano**: `mt7921u` allows `#{AP} <= 1`, and D2 needs six. Would need an adapter whose driver does multi-BSSID, which is uncommon on USB |
| C. USB is the uplink | USB adapter | radio0 **and** radio1 | removes AP/STA coupling entirely and gives clients both bands — but puts the uplink on nano antennas and on removable hardware, losing the reach that matters most |
| D. Ethernet-only distribution | radio1 | none; `wan`+`lan1`+`lan2` as three independent ports | eliminates AP duty from ath11k and frees the WAN port, but six modes do not fit on three ports, so D2 would have to be redesigned |

**Where the AX55 Nano does fit.** `mt7921u` allows `#{managed} <= 2` and is
reported to work well as a client. So its realistic role is a **second station
for 5 GHz-only venues** — which is better than unparking `uplink5` on radio0,
because a station there would stop radio0's APs (W9901). That gives dual-band
uplink without touching the client APs, using hardware already on hand.

Caveats on it: USB **2.0** interface (not 3.0, despite the port), 2 × 3 dBi nano
antennas so reach is worse than the internal radios, no DFS channels in AP mode,
and a reported slowdown over time with the stick enabled. It is currently
allocated to `srv-orangepi5` in topology, so using it here is a reallocation
decision.

> Conclusion on buying a "universal" adapter: for the *uplink* role it is not
> needed — the internal radios are better. For the *AP* role, multi-BSSID on USB
> drivers is broadly absent or buggy, so an adapter would have to be chosen on
> that one criterion, verified by `iw list` → `valid interface combinations`
> before purchase. The internal ath11k radios are the only hardware here that
> genuinely does multi-BSSID.

### 4b. Uplink source

* **Venue AP** (hotel, café) — the standing case; `untrusted`.
* **Phone hotspot** — the same mechanism, just a different network to join. This
  is why USB tethering is a deliberate non-feature: it would need a second
  interface, zone membership and code path for an outcome the station already
  reaches.
* **Wired `wan`** — when a cable is available; also `untrusted`.
* Not yet expressed: **route metrics** deciding which uplink wins when more than
  one is live. Currently it works only because exactly one is.

### 4c. Where secrets live

`secrets/terraform/openwrt.yaml`, decrypted by
`scripts/terraform/generate-tfvars.py openwrt` into a 0600 tfvars and removed
with `--cleanup`. The three SSIDs shared with Chateau reuse Chateau's own
passphrases, because a client caches one PSK per SSID and a different value
would break roaming.

## 5. Usage variants

| Situation | Uplink | Management | Notes |
|---|---|---|---|
| **At home, staging** | `wan` → Chateau `ether2` | laptop on `lan` | the access ports are ether2 and ether4; ether3/ether5 are `pvid=99` trunk/management ports |
| **Travelling, operator present** | radio1 → venue AP | laptop on `lan`, by cable | the recommended travel path: no tunnel, no hole in the perimeter, no management route |
| **In a car, reaching a distant AP** | radio1 (2.4 GHz — best reach) | laptop on `lan` | clients are in the car, so AP range is irrelevant; this is the argument for keeping the station on an internal radio |
| **Travelling, nobody with the device** | radio1 → venue | over `wg-home`, **gated** | needs an inbound-only rule on `vpn_exit` scoped to one source, plus the management prefix in the tunnel routes — both deliberate closures today |
| **Emergency, home unreachable** | any | ssh + `uci` | not a Terraform case; reconcile drift afterwards (`--acknowledge-drift`) |

## 6. Open items

Ordered by what blocks what.

1. **`masq` is set on no generated zone.** NAT for client egress still depends
   on the **stock** `wan` zone being present, so removing the stock zones would
   silently kill Slate-Split and Slate-Guest. Blocks both that removal and
   applying this generator to Chateau.
2. **The tunnel does not handshake** — `0 B received`. rtr-slate's public key is
   not provisioned on the VPS, and `terraform/oci/` configures no WireGuard
   peers at all, so the server side lives outside the repository.
3. **A tunnel route overlaps the device's own uplink subnet** —
   `192.168.88.0/24 dev wg_home` is Chateau's LAN and also the WAN's subnet when
   at home. Correct when travelling, self-contradictory here; nothing has broken
   only because the connected route outranks the static one.
4. **State and plan files hold private keys in clear.** OpenTofu native
   encryption is the recommended answer, with `key_provider "external"` shelling
   out to SOPS; it covers plan files too. Repo-wide decision, since mikrotik and
   proxmox carry the same exposure.
5. **Two deploy hosts, one state.** 83 resources exist in `.work/` on the laptop
   alone; an apply from the Orange Pi would try to recreate every section.
6. **No over-the-air management path**, by design — the client zones grant only
   dhcp and dns on input. A parked management SSID would give one; it is a hole
   into the management plane of a device that lives in hotels, so it is a
   decision rather than an obvious improvement.
7. **A WireGuard private key was printed in clear** into a session transcript
   during diagnosis. Rotation of `road_warriors.rtr-slate.private_key`
   recommended.
8. **Radios are permanently outside Terraform** — `uapi_wireless_device` cannot
   express `path`, so any write breaks the phy binding. They belong to whatever
   manages the OS, like the ath11k memory watchdog, which is declared with
   `owner: ansible` and is not implemented.

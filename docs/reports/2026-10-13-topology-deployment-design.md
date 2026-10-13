# Deployment system for rtr-slate and rtr-mikrotik-chateau — design

2026-10-13. Written after applying rtr-slate by hand (see
`2026-10-09-rtr-slate-uapi-terraform-spc-analysis.md`, Phase 9), which is the
evidence this design is built on.

Two tasks are covered: the deployment system, and encrypting the secrets that
the first apply left in clear.

---

## 1. What the first apply cost, as design input

Every interruption had one of four causes, and none of them was the
configuration:

| # | What happened | Cost |
|---|---|---|
| 1 | One cable served both the management path and the device's internet | 4 interruptions; each move broke the other need |
| 2 | WSL2's `eth0` could not be brought up — `Operation not permitted`, carrier owned by Windows | link dropped three times, twice unrecoverably from inside the session |
| 3 | The apply ran from a scratchpad with a hand-rolled tfvars | secrets in plaintext; the state was nearly deleted |
| 4 | `apply-confirm` is not installed on the device | the rollback source was a `uci export` I took by hand |

A deployment system that does not fix #1 and #2 will fail the same way every
time. They are the design, not the details.

## 2. Three planes that were conflated, and must not be

| Need | Who needs it | Served by |
|---|---|---|
| uapi (443) and SSH to the device | the **deploy host** | management plane |
| the apk package feed | the **device itself** | device uplink |
| SOPS decryption | the **deploy host** | age key material |

Today a single cable alternated between the first two, so satisfying either
broke the other. Separating them is most of the work.

## 3. Deploy host

**The topology already names one.** `srv-orangepi5` carries
`cap.operations.infrastructure_controller`, sits on the management VLAN at
`10.0.99.20` behind Chateau's `ether3` trunk, and is a Docker host — a
permanently powered Linux box on the management plane.

The laptop is the wrong host and today proved why: WSL2 mirrors its interfaces
from Windows, `ip link set eth0 up` is refused, and the carrier state is outside
the session's control. It should be the **operator console** that drives a
deploy on the controller, not the thing holding the state and the keys.

> **Precondition, not verified.** As of writing, `10.0.99.20` answers on neither
> 22 nor 2375, and Chateau's own management address `10.0.99.1` does not answer
> either, over the laptop's `wg0` route to `10.0.99.0/24`. So the management
> VLAN is currently unreachable from here. Whether that is the Orange Pi being
> off, the tunnel not carrying that prefix, or something else has to be settled
> **before** this choice is committed to. Until then the laptop remains the only
> usable host, with the limits above.

Also resolved while reading the topology: Chateau's `ether3` carries `pvid=99`
because it is the Orange Pi's **trunk port with the management VLAN native** —
not the misconfiguration an earlier note in this work called it. `ether5` is
pvid=99 for the same reason. Plugging rtr-slate into either was the error; the
access ports are `ether2` and `ether4`.

## 4. The management path to rtr-slate

This is the one real design question, because `input REJECT` on the `untrusted`
zone is deliberate and must stay.

**A1 — cable Slate's LAN into the management VLAN.** Slate LAN1 → Chateau
ether5. Costs a re-cable per deploy and needs an address in `10.0.99.0/24` on
Slate's `lan`, or a route on Chateau, because `lan` is `192.168.1.0/24`. Works,
but it is exactly the per-deploy cabling that caused cost #1.

**A2 — a profile-gated uapi hole on `untrusted`, scoped to one source.
Recommended.** The input-rule lowering already supports per-zone services, and
`uapi_firewall_rule.match` supports `src_ip`, so this is expressible today as

```
src_zone = untrusted, src_ip = <deploy host>, proto = tcp, dest_port = 443 → ACCEPT
```

With Slate's WAN on the home LAN, management and internet arrive on the same
*wire* but through different, separately-governed rules — which is the
separation that matters, not physical separation.

The gate is the repo's existing **profile** mechanism (`--profile`, profile-map
`instance_overrides`): a `staging` profile carries the rule, and the travel
profile does not. That matters because `untrusted` is a hotel network when
travelling, where a hole keyed to a private address is a hole keyed to an
address the venue may also use. Profiles are precisely the tool for "this is
true at home and false on the road".

**A3 — over `wg-home` once the tunnel works.** The right answer for deploying
to the device *while travelling*, and circular for the first deploy: the tunnel
is part of what is being deployed. A later phase, not this one.

Recommendation: **A2 under a staging profile, with A1 as the recovery path** for
first contact and for the case where the firewall is the thing that broke.

## 5. The device's internet

Needed only by `apk`, and only when packages change.

* **WAN → Chateau `ether2`. Recommended.** Independent of the management rule,
  no extra config, and it is the authored `uplink.wired` path.
* **STA to the ISP router** (the original idea) works, but the `uplink`
  wifi-iface is by definition the *venue* interface; authoring a home SSID into
  it would carry that SSID into the travel configuration. Acceptable only
  profile-scoped, the same way as A2 — and then it is strictly more moving parts
  than a cable to ether2.
* **Through the laptop** was examined and rejected: it requires the laptop to be
  a DHCP server and NAT router for the device, which on WSL2 is awkward, and a
  long-running proxy was refused by the sandbox classifier. With Chateau one
  port away it buys nothing.

## 6. What to build — an `openwrt` leg in the framework that exists

There is already a bundle-based deploy framework: `taskfiles/deploy.yml` →
`scripts/orchestration/deploy/init_node.py`, with phases `workflow:deploy-check`
(plan only) and `workflow:deploy-apply` (gated on `ALLOW_APPLY=YES`), a
`DEPLOY_RUNNER` parameter that already names the executing host, `--inject-secrets`,
and per-target `--*-var-file` / `--*-backend-config`. State for existing targets
lives under `.work/deploy/bundles/<id>/`.

So this is an extension, not a new system. What is missing:

1. **An `openwrt` target** in the check/apply legs and in the `*_VAR_FILE` /
   `*_BACKEND_CONFIG` plumbing, mirroring `mikrotik`.
   *Done already:* `generate-tfvars.py openwrt`, which decrypts
   `secrets/terraform/openwrt.yaml` to a 0600 tfvars and removes it with
   `--cleanup`.
2. **A pre-apply snapshot step.** `apply-confirm` is not installed, so the
   rollback source is `uci export` pulled off the device — that worked today and
   repaired the radios, and it should be a step rather than something remembered.
   Note `scp` is unavailable on the device (no sftp-server); `ssh … cat` is the
   transport.
3. **A post-apply verification step** that is not "terraform says OK": today the
   apply converged while the radios were down. Minimum checks: management still
   answers, both intended SSIDs beacon, and the matrix's denied pairs are still
   denied.
4. **Radios excluded from Terraform** — already done, and a reminder that this
   boundary is permanent: `uapi_wireless_device` cannot express `path`, so any
   write to it breaks the phy binding. Radio configuration belongs to Ansible,
   like the memory watchdog (ADR 0119 D6).

## 7. Known gap that blocks the Chateau half

`masq` is set on no generated zone. NAT for client egress currently depends on
the **stock** `wan` zone still being present, so the planned "remove the stock
zones after verifying" step would silently kill internet for Slate-Split and
Slate-Guest. The model has no field for it. **Fix before that step**, and before
applying the same generator to Chateau.

---

## 8. Task 2 — encrypting state and plan

The exposure is concrete: `terraform.tfstate` stores the WireGuard private keys
in clear, whatever the provider marks Sensitive, and so do the saved plan files
(`*.tfplan`) — which this work also left in `.work/`. It is gitignored and
matches where the repo already keeps state for every other root, so it is the
house baseline rather than something introduced here; it is still plaintext key
material on disk.

**Recommendation: OpenTofu native state encryption.** Verified against the
OpenTofu documentation:

```hcl
terraform {
  encryption {
    key_provider "external" "sops" {
      command = ["<script that emits the key as JSON>"]
    }
    method "aes_gcm" "default" {
      keys = key_provider.external.sops
    }
    state { method = method.aes_gcm.default }
    plan  { method = method.aes_gcm.default }
  }
}
```

Why this and not the alternatives:

* It covers **plan files as well as state**, which a SOPS wrapper around the
  state file would not.
* `key_provider "external"` shells out, so the key comes from the existing
  age/SOPS material at run time and never sits in a file next to the state. The
  `pbkdf2` provider would put a passphrase in configuration instead.
* A SOPS decrypt/encrypt wrapper leaves plaintext behind on any crash between
  the two halves. Encryption-at-rest inside the tool has no such window.
* There is a documented migration path for existing unencrypted state: an
  `unencrypted` method in a fallback block, read once, then removed.

Cost and caveats, stated plainly:

* It requires **OpenTofu**, not Terraform — native state encryption is an
  OpenTofu feature. The uapi provider documents OpenTofu support parity, and
  `tofu` is not currently installed here.
* The existing `mikrotik` and `proxmox` states carry the same exposure. Doing
  this for one root and not the others leaves the larger share of the problem
  untouched, so this is really a repo-wide decision.
* Migrating existing state is a one-way step per root and needs the fallback
  dance above; it should be done on a copy first.

---

## 8a. Deploying to rtr-slate while travelling

Asked directly: is the proposal to tunnel from rtr-slate into Chateau's
management network and deploy from the Orange Pi? **No** — not as the primary
path, because it costs two deliberate closures, both verified still in place:

* `vpn_exit` is not among the zones granted input services (`guest`,
  `management`, `travel_split`, `user`, `vpn_tunnel` are), so uapi and SSH over
  the tunnel are closed.
* Slate's tunnel `routes` carry `192.168.88.0/24`, `10.100.0.0/24` and
  `10.0.100.0/24` — the management prefix was deliberately omitted. Without it a
  reply to `10.0.99.20` would leave through the **venue uplink** in clear, not
  the tunnel.

**The operator travels with the device.** In a hotel you are standing next to
it: LAN1, or join `Slate-Home`, and the `management` zone already permits ssh
and uapi on `lan`. No tunnel, no new hole in the perimeter, no management route,
and no dependence on the venue's internet or on home being up. That is
literally how the first apply was performed.

So the split is:

| When | Host | Path |
|---|---|---|
| Slate travelling | the laptop, locally | `lan` — already permitted |
| Slate at home, and all of Chateau | `srv-orangepi5` | management VLAN |
| Nobody is with the device | over `wg-home`, **gated** | see below |

The third case stays available but deliberately exceptional. If it is used it
must be **inbound only**: an input rule on Slate's `vpn_exit` zone scoped to the
Orange Pi's address lets home initiate, conntrack returns the replies, and
nothing lets Slate initiate into the management plane. That asymmetry is the
whole point — the original decision not to grant Slate management access exists
because a lost or seized router must not reach it, and an inbound-only rule does
not weaken that. It also needs the management prefix added to the tunnel routes,
which is the second closure above, so it is a profile-scoped capability and not
a default.

### The real gap this exposed: two hosts, one state

If both the laptop and the Orange Pi can deploy, state must not live on
whichever ran it last. Today 83 resources exist in `.work/` on the laptop alone;
an apply from the Orange Pi would try to create every section again and take
`422 conflict` on each. This is what `*_BACKEND_CONFIG` in the existing
framework is for — a shared backend rather than per-host state.

That carries a tension worth naming: a shared backend at home means a travel
deploy depends on home being reachable, which couples the two in exactly the
wrong direction.

It is resolved by what D2 already decided rather than by more machinery: **modes
are selected by which SSID the client joins, not by reconfiguring.** A travel
deploy should therefore be rare by design. For the residual "must change
something now and home is unreachable" case the right tool is not Terraform at
all — it is SSH and `uci`, followed by reconciling the drift when home is back,
which the deploy framework already anticipates with `--acknowledge-drift`.

## 8b. Radio allocation — where the station goes, and where the APs go

Three proposals were considered in order, and the third is the one to build on.
Recording all three because the reasoning only makes sense as a sequence.

### The proposals

**(i) As built today.** Station on radio1 (2.4 GHz), APs on radio0 (5 GHz),
wired uplink optional. Works, and is running. Costs: AP duty sits on **ath11k**,
whose memory leak is unfixed upstream (~7-8 MB/h, reclaimed only by a module
reload) — which is the entire reason 4 of the 6 SSIDs are parked. Broadcasting
own SSIDs abroad also keeps the `country` question live, since the permitted
channel set differs by country and a 5 GHz AP on channel 36 is not a formality.

**(ii) Ethernet-only distribution.** Uplink by radio, clients by cable. The
strong argument for it: it removes AP duty from ath11k entirely, and a wireless
uplink **frees the WAN port** — `wan`, `lan1`, `lan2` are three *independent*
netdevs on this SoC (nss-dp/edma, not a switch with a CPU port), so three ports
become available for three roles with no VLANs. The fatal cost: D2 selects mode
by **which SSID the client joins**, and six modes do not fit on three ports. It
would force mode selection to be re-designed.

**(iii) USB adapter serving the client APs. Recommended direction.** Station
stays on an internal radio; the USB adapter carries the mode SSIDs for trusted
devices. This is the right way round, and it is the opposite of what an earlier
version of this discussion argued against — that argument was about putting the
*uplink* on USB, which inverts the reliability priority. Here a USB failure
degrades client service while the uplink and the management path survive, and
**AP duty moves off ath11k**, so the SSID budget that the leak forced may become
liftable. D2's SSID-per-mode selection is preserved intact.

### Resulting allocation under (iii)

| Hardware | Role |
|---|---|
| `radio1` (internal, 2.4 GHz) | **station** — hotel AP, or a phone's hotspot |
| `radio0` (internal, 5 GHz) | **off** by default; candidate for a parked emergency management SSID |
| USB adapter | **client APs** — the mode SSIDs for trusted devices |
| `wan` port | freed by the wireless uplink: management, or a wired client |
| `lan1` / `lan2` | management and wired clients |

radio0 being off is not incidental — it is where the ath11k gain comes from.

### The reason that settles it: range belongs on the uplink

The internal radios are the long-range ones — 2x2 on both bands with the
device's own antennas — and a USB adapter normally has a stub. So the allocation
is not only about which failure is tolerable; it is about **where range is
needed at all**. The uplink may have to reach a hotel AP from a car park. The
clients are in the same car.

Putting the good antennas on the uplink and the stub on a one-metre link is the
whole argument, and it is stronger than the reliability one.

### What that unlocks: dual-band uplink

`uplink5` already exists in the instance — a station on radio0, `enabled: false`.
It is parked for one reason: radio0 serves the APs, and any station on a phy sets
`ap_start_disabled`, so a live station there would stop every AP on that phy on
each `DISCONNECTED`/`SCANNING` transition (W9901).

**Move the APs to USB and that constraint disappears.** Both internal radios
become uplink candidates:

| Station | Band | Why |
|---|---|---|
| `uplink` on radio1 | 2.4 GHz | best reach — lower frequency penetrates and carries further; the car-park case |
| `uplink5` on radio0 | 5 GHz | venues that offer only 5 GHz, and better throughput when close |

E9910 permits this: the limit is one station **per radio**, not one per device.

One detail this exposes, which the current data has only by accident: both
stations declare `network: wwan`, and `runtime_intent.uplink.primary` names
`wwan` once. That works today only because `uplink5` is parked — two live
stations feeding one `config interface` would have two providers for one
address. Unparking it needs either a second network (`wwan5`, also in
`untrusted`) with route metrics deciding which uplink wins, or an explicit
either/or selection. Metrics are the better answer, since it makes the
preference declarative instead of operational; they are currently set nowhere,
which is the same gap already noted for `wwan` versus `wan`.

### Four go/no-go requirements on the adapter

These are not preferences; the design does not work if any fails.

1. **Multi-BSSID.** D2 needs up to six APs on one phy. The adapter must
   advertise interface combinations allowing it — `iw list` → `valid interface
   combinations … #{ AP } <= N`. Many cheap adapters do exactly one, and
   out-of-tree Realtek drivers frequently do one or misbehave with more. **Check
   this first; it is the most likely reason to reject a given adapter.**
2. **Mainline driver for this target and kernel.** `aarch64_cortex-a53`,
   `qualcommax/ipq60xx`, vermagic `6.12.94-1-d00b1043…`. The safe family is
   **mt76** (MT7612U dual-band, MT7921AU newer). Realtek `88x2bu`/`8821au` are
   out-of-tree and may have no package for this vermagic at all.
3. **SAE in AP mode**, if the SSIDs keep `sae-mixed`. Not every USB chipset and
   driver supports WPA3 as an AP. If it does not, those SSIDs drop to `psk2` —
   a security downgrade to accept deliberately, not to discover.
4. **Stable hardware binding.** A `wifi-device` section binds to hardware by
   `path`, and for USB the path depends on the USB topology, so a different port
   changes it. `uapi_wireless_device` cannot express `path` at all — the defect
   found during the first apply — so the USB radio is outside Terraform like the
   internal ones. Worth checking whether `macaddr` can bind it instead, which is
   stable across ports.

Also: one USB 3.0 port, and a dual-band adapter with amplifiers draws real
current on a device often powered from a phone charger.

### USB tethering: deliberately not implemented

A phone hotspot is simply another network the station joins, so the hotspot path
covers the tethering case with the mechanism that already exists — no extra
interface, no extra zone membership, no extra code path. Tethering is therefore
recorded as a **non-feature** rather than left as an open item.

Two residual cases it would cover and the hotspot does not: a carrier that
blocks hotspot, and wanting the phone to charge while acting as the uplink.
Neither justifies a second uplink mechanism today.

## 9. Decisions needed

1. **Deploy host** — commit to the Orange Pi? First settle why the management
   VLAN does not answer.
2. **Management path** — A2 (profile-gated uapi rule on `untrusted`) as the
   standing mechanism, with A1 as recovery?
3. **State encryption** — adopt OpenTofu for this root only, or repo-wide
   (which is where most of the exposed key material actually is)?
3a. **Shared state backend** — where does it live, given that a travel deploy
   must not require home to be reachable? The answer above is "travel deploys
   are rare by design", but the backend still has to be chosen.
4. **`masq`** — add it to the zone model now, since it blocks both removing the
   stock zones and applying this generator to Chateau.

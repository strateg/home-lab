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

## 9. Decisions needed

1. **Deploy host** — commit to the Orange Pi? First settle why the management
   VLAN does not answer.
2. **Management path** — A2 (profile-gated uapi rule on `untrusted`) as the
   standing mechanism, with A1 as recovery?
3. **State encryption** — adopt OpenTofu for this root only, or repo-wide
   (which is where most of the exposed key material actually is)?
4. **`masq`** — add it to the zone model now, since it blocks both removing the
   stock zones and applying this generator to Chateau.

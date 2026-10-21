# rtr-slate — conserving the uapi/Terraform track, and what came back from it

2026-10-21. The operator decided to keep **rtr-slate on its original GL.iNet
vendor firmware** rather than run the upstream OpenWrt 25.12 image the
Terraform management track required. This report records what was frozen, what
was integrated into `development` instead, and what each choice costs.

It is the companion every file that mentions the frozen track points at.

---

## 1. The decision in one paragraph

The branch `rtr-slate-terraform` built a second network enforcer end to end:
topology → compile → validate → generate → `terraform apply`, driven through
`terraform-provider-uapi` against uapi's REST API. uapi exists only on OpenWrt
25.12+ (apk), so the whole track is **conditional on reflashing the device off
vendor firmware**. Keeping the vendor firmware removes that condition, and with
it the generator, the adapter, the E99xx diagnostics and the device's
`runtime_intent` — not because they are wrong, but because nothing on the
device answers them.

Everything on that branch that was *not* conditional on the firmware was moved
to `development`. That is the whole of this report's second half.

## 2. Where the frozen work lives

| Ref | What |
|---|---|
| `frozen/rtr-slate-terraform-2026-10-21` | annotated tag, the canonical name |
| `archive/rtr-slate-terraform` | branch at the same commit, for browsing and `git checkout` |
| fork point `c5bee431` | 46 commits, 70 files, ~14.9k insertions on top of it |

Nothing was deleted. The branch `rtr-slate-terraform` is identical to the tag;
the two archive refs exist so the name does not have to survive a branch
cleanup, which is the same convention `archive/v4-baseline` follows for v4.

Frozen there, and **not** on `development`:

* the `openwrt` object-module plugin family — `zones` and `interfaces`
  compilers, the `zone_plan` / `rule_plan` / `interfaces` / `wireless`
  validators, `terraform_openwrt_generator` and its ten Jinja templates;
* the **E99xx/W99xx diagnostic family** (14 registered codes) and its
  `docs/diagnostics-catalog.md` entries;
* the upstream-OpenWrt software track: `obj.firmware.openwrt.stock.25_12`,
  `obj.os.openwrt.stock.25_12`, their instances, and the capabilities
  `cap.os.openwrt.2512`, `cap.os.init.procd`,
  `cap.firewall.security_matrix.openwrt` plus its `_ENFORCER_ADAPTER_BY_TYPE`
  wiring;
* rtr-slate's 571-line `runtime_intent` (uplinks, radios, SSIDs, WireGuard
  interfaces lowered onto the uapi resource surface) and its adoption ledger;
* `projects/home-lab/secrets/terraform/openwrt.yaml` and the tfvars path for it;
* the engineering records `2026-10-09-rtr-slate-uapi-terraform-spc-analysis.md`
  (the full nine-phase account, including the live apply and the four defects
  only an apply could find) and
  `2026-10-13-rtr-slate-topology-consolidation-spc.md`.

To read the account of the live apply, check the tag out — it is the most
detailed description of this device that exists.

## 3. What was integrated, and why each one is firmware-independent

### 3.1 Hardware facts — `obj.glinet.slate_ax1800`

The object described a MediaTek MT7621A (mipsel, 2 cores, 880 MHz). The
GL-AXT1800 is a Qualcomm IPQ6000 (arm64, 4 cores, 1.2 GHz); MT7621A/mipsel
belongs to the older Mango/AR750 line. The three ethernet ports were also
marked `dsa: true`, and IPQ6000 exposes three independent nss-dp/edma netdevs
with no CPU port and no `eth0`.

Neither fact depends on which firmware runs. The second is the fact that makes
"a wireless or tethered uplink frees the WAN port" true on this board, which is
load-bearing for the usage modes below.

### 3.2 The W7016 allowlist entry

`development` was **failing** the ADR0088 governance gate in enforce mode
before this: rtr-slate resolves as a network enforcer, no `cap.os.openwrt`
adapter exists, W7016 fires, and the gate refuses an unlisted warning with
G2101. Verified by running the gate against `build/diagnostics/report.json`
with and without the entry.

On the frozen track the warning retired because an adapter with a real
generator appeared behind it. Here it is permanent: the device is modelled as
an enforcer and configured by hand. The entry says so.

### 3.3 Two security-matrix defects

Both were found by adding a second enforcer, and neither has anything to do
with how that enforcer is configured.

**Scope resolution.** `address_space.vlan_refs` was read by nothing, so zone →
VLAN resolution was global and every matrix claiming a zone inherited every
VLAN any device had assigned to it. With one enforcer that is invisible; with
two, a travel router's `10.77.x` segments landed in the home perimeter's
rendered address lists and shifted the resource indices, turning a
`terraform apply` against Chateau from "only adds" into "rewrites existing
address-list resources". Each scope now resolves inside its own address space.

**E7065 — a zone pair claimed twice.** `_find_policy_override` returns the
first match, so a second override for the same pair was discarded with nothing
reported. `obj.network.security_matrix.soho` had authored
`user-to-servers-http` for the `user → servers` pair, which competed with each
instance's own permit; the two instances lost opposite halves. The object
declares no overrides now (ADR 0118 D7), each instance carries the ports it
means, and E7065 refuses the collision.

### 3.4 The road-warrior model, as intent

`inst.security_matrix.rtr_slate`, `inst.trust_zone.travel_split`, the six
`inst.vlan.slate_*` segments and the tunnel entries are **ADR 0110-level
statements about zones, prefixes and permitted pairs**. They say nothing about
uci, firewall4 syntax or a provider; they are the specification the operator
now configures against by hand, in LuCI or by `uci`. Keeping them as data
rather than as prose is the point of an infrastructure-as-data repo, and the
kill switch in particular is worth having written down precisely:

> With the venue uplink modelled as `untrusted` (level 0), legacy R3
> (downhill) **permits** `user → untrusted` and `vpn_tunnel → untrusted`. On
> Chateau that is the intent — untrusted is the WAN. On a travel router it is a
> leak past the tunnel, and it is the one thing that must be impossible. The
> matrix denies both pairs explicitly with R6.

ADR 0118 D4.1 predicted exactly this: it renders R3 as "Nothing. Trust level is
not authorization" in the strict profile. rtr-slate is the first device here
where the legacy profile's fail-open R3 is a concrete vulnerability rather than
a note, and that remains true with the device configured by hand.

Every file carries `status: staged` and says in its notes that nothing renders
it. The one thing a reader must not conclude is that enforcement follows from
the file.

### 3.5 Standing documents

`docs/architecture/RTR-SLATE-USAGE-MODES.md` and the two dated reports on
architecture and deployment came over with a status banner each. Their hardware
invariants, radio-role rule, uplink/downlink combinations and deploy-plane
analysis survive the firmware change; their mechanism sections (uapi resources,
the E99xx validators, `terraform plan`) describe the frozen track and are
marked as such.

## 4. The live consequences, stated plainly

| # | Consequence | Where |
|---|---|---|
| 1 | One MikroTik resource disappears from the rendered config: `zone_override_user_to_servers_http_tcp`. Its match referenced `zone-obj_network_trust_zone_user` / `...servers`, address lists that are never defined, so it matched nothing on the live router. A `terraform apply` against Chateau will want to destroy it if it is in state. | `generated/home-lab/terraform/mikrotik/zone_firewall.tf` |
| 2 | `advertises` on the wg-home gateway peer is read by zero lines of the runtime — the generator that would have rendered it is frozen. `vps-wg0.conf` still lists rtr-slate as `AllowedIPs = 10.100.0.4/32`, so `10.77.1.0/24` and `10.77.2.0/24` must be added to the hub by hand, or the field taught to the WireGuard generator, before return traffic to a Slate client works. | `inst.tunnel.wg-home-to-oci` |
| 3 | `mikrotik_networks_for_firewall` and the `networks` output count grow by the eight new network instances. The local is referenced by no resource and the other is an output, so a plan shows a value change and no resource change. | `firewall.tf`, `outputs.tf` |
| 4 | W7016 stays at exactly 1, permanently, and the governance gate is what keeps it from growing silently. | `configs/quality/adr0088-governance-policy.yaml` |
| 5 | rtr-slate's own configuration is **not** generated. There is no drift check for it; the drift check is reading the device. | — |

## 5. If the track is ever resumed

```bash
git log --oneline c5bee431..frozen/rtr-slate-terraform-2026-10-21
git checkout -b rtr-slate-terraform-v2 frozen/rtr-slate-terraform-2026-10-21
```

Three things changed underneath it and would have to be reconciled rather than
re-applied:

1. the soho object no longer declares `policy_overrides`, so the frozen
   `inst.security_matrix.rtr_slate` would need its `user → servers` override
   checked against E7065 (the frozen branch already carries the union);
2. zone resolution is now scoped per address space, which is the behaviour the
   frozen branch introduced — it will match;
3. `model.lock.yaml` and `framework.lock.yaml` moved; both are regenerated
   (`task build:sync-lock`, `task framework:lock-refresh`), not merged.

And the precondition that started all of it still stands: uapi needs OpenWrt
25.12+ on apk, and for this board that means the `qualcommax/ipq60xx` target.

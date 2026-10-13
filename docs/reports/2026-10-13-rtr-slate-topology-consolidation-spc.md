# rtr-slate — topology consolidation (SPC)

2026-10-13. Strict Process Compliance analysis consolidating the device's
functional design **into the topology**, driven by one constraint the operator
stated explicitly:

> radio0 and radio1 run simultaneously, each either as an access point or as a
> WiFi client.

Gates waived by standing instruction ("не спрашивая моего подтверждения для
перехода по шагам"); the methodology is followed, the STOP/GO halts are not.

---

## STEP 0 — READ FIRST

ALL MATERIALS READ: `docs/ai/spc-contract.md`; the three companion reports
(`2026-10-09-rtr-slate-uapi-terraform-spc-analysis.md`,
`2026-10-13-rtr-slate-design-summary.md`,
`2026-10-13-rtr-slate-architecture.md`,
`2026-10-13-topology-deployment-design.md`); the device instance; the matrix
instance; the four OpenWrt plugins; and the live device state read over SSH.

## STEP 1 — DOCUMENT MAP

| Document | Owner | Purpose | Binding requirements | Data used |
|---|---|---|---|---|
| `projects/.../devices/rtr-slate.yaml` | operator | the device's authored intent | radio roles, uplinks, wireless, tunnels, services | radios, interfaces, uplink specs |
| `projects/.../network/inst.security_matrix.rtr_slate.yaml` | operator | perimeter + egress treatment | zone set, overrides, `egress` | zone refs, masquerade, mss_clamp |
| `topology/object-modules/openwrt/plugins/validators/wireless_validator.py` | framework | enforce wireless facts | E9908, E9910, W9901, W9904 | declared radios and interfaces |
| `docs/.../rtr-slate-architecture.md` | this work | the agreed architecture | I1–I5, the three selection layers | invariants, combinations |
| live device (`uci show`, `nft`, `ubus`) | — | ground truth | — | radio paths, zone resolution, clamping |

## STEP 2 — CONSTRAINTS REGISTER

| Stakeholder | Requirement | Criticality | Type | Verification | Source |
|---|---|---|---|---|---|
| operator | a radio is **either** AP **or** client; both run simultaneously | **Critical** | Operational | a check that fails the build | stated this session |
| hardware | any station on a phy sets `ap_start_disabled`, silencing that phy's APs on each scan/roam | **Critical** | Operational | W9901; observed on device | wifi-scripts `mac80211.sh:560` |
| hardware | one station per radio (`#{ managed } <= 1`) | **Critical** | Operational | E9910 | phy advertisement |
| hardware | `uapi_wireless_device` cannot express `path`; a write erases it | **Critical** | Operational | `path_owner: ansible`, recorded | observed: both radios down |
| operator | model everything in topology; only changes flow to Terraform | **Critical** | Governance | no hand-edits unrecorded | stated this session |
| framework | a check on intent is not a check on what ships | Important | Governance | prefer artifact-reading checks | seven instances this session |

No Critical requirement is unsatisfiable → no "NO VALID SOLUTION" condition.

## STEP 3 — DIAGNOSTIC ANALYSIS (facts only)

Read from the authored topology and the live device. No decisions here.

**D1. The data contradicts itself.**

```
radio0: role='ap_only'   ap_home, ap_split, ap_de, ap_ru, ap_se, ap_guest  (ap)
                         uplink5                                          (sta)  ← contradiction
radio1: role='sta_uplink' uplink                                          (sta)
```

**D2. `role` was read by nothing.** Grep across the OpenWrt plugins returns
only `uplink.role` (primary/wired) and tunnel `endpoint.role` (server) —
different fields. The radio `role` had no consumer.

**D3. `station_limit_per_radio: 1` was read by nothing**, and its own comment
had gone stale: it justified "which is why uplink5 stays parked".

**D4. E9910 cannot catch D1.** It counts *live* stations per radio and skips
parked interfaces — correctly, because netifd drops a `wifi-iface` with
`disabled '1'` at parse time. A parked station on an AP radio is therefore
invisible to it.

**D5. Two stations claimed one network.** `uplink` and `uplink5` both declared
`network: wwan`, while `uplink.primary` names `wwan` once. Consistent only
because one was parked.

**D6. Live state read off the device** (for completeness of the model):
`wireless.radio0.path='platform/soc@0/c000000.wifi'`,
`radio1.path='...wifi+1'` — set by hand during the first apply, absent from
topology.

## STEP 4 — PROBLEM CLASSIFICATION

Not an implementation defect. **A model gap:** the rule existed in the data as
a *field* (`role`) but not as a *constraint*. Classified:

| Axis | Classification |
|---|---|
| design vs implementation | **design gap** — the rule was never expressible as binding |
| data vs governance vs tooling | **data model** — a declared field with no consumer |
| runtime vs declaration | **declaration** — the contradiction exists before anything runs |
| severity | latent: harmless while parked, silences six SSIDs one flag later |

This is instances #8 and #9 of the pattern already recorded seven times in this
work: *declared, validated, not enforced.*

## STEP 5 — ADMISSIBLE SOLUTION SPACE

| Problem | Possible mechanism | Constraint | Admissible? |
|---|---|---|---|
| D1 contradiction | keep `uplink5` parked, document the risk | the rule says a radio is one thing; parked is still a declaration | **No** — leaves the contradiction in the data |
| D1 | flip radio0 to `sta_uplink` | radio0 carries six APs; the running config beacons two of them | **No** — discards the live downlink |
| D1 | remove `uplink5`; record 5 GHz uplink as a *role swap* | matches the rule; the capability is not lost, only correctly priced | **Yes** |
| D2 | make a validator read `role` | parked must count, unlike E9910 | **Yes** — a second, declaration-level check |
| D3 | make E9910 read the field | the limit is a hardware fact, not a policy knob; a settable-looking field is misleading | **No** |
| D3 | remove the field | nothing consumes it; the real limit stays enforced | **Yes** |
| D5 | second network for a 5 GHz station | only needed if two stations coexist, which the rule forbids on one radio and D1's removal ends | **Not needed** |
| D6 | express `path` in Terraform | the resource cannot carry it | **No** |
| D6 | record it in topology with an owner | completes the model without claiming Terraform applies it | **Yes** |

## STEP 6 — MODEL REBUILD

Reference preserved in git history; every change is explicit.

1. **`uplink5` removed** from the instance, with the reason recorded in place:
   illegal rather than parked, and a 5 GHz uplink is a change of radio0's role
   costing all six SSIDs on it (combination C5).
2. **`station_limit_per_radio` removed**, with the reason: no consumer, and it
   implied a knob where the phy admits one value.
3. **The rule stated** at the radios, naming both the mechanism (W9901) and the
   cost of a role swap.
4. **E9921 registered and implemented** in the wireless validator — refuses a
   radio carrying both modes, and refuses interfaces disagreeing with a declared
   `role`. **Parked interfaces count**, which is the opposite of E9910 and the
   docstring now says why.
5. **Radio `path` recorded** in topology with `path_owner: ansible`, read off the
   device rather than assumed.

Earlier in the same session, and part of the same consolidation: `masq` and
`mss_clamp` stated per zone under one `egress` block with E9918/E9920 refusing
silence; uplink route metrics with E9919 refusing an undecided preference.

## STEP 7 — VALIDATION & COMPLIANCE

| Requirement | Source | Met | How verified | If No |
|---|---|---|---|---|
| a radio is AP or client, never both | operator | **Yes** | E9921; mutation — reinstating a parked station on radio0 fails the build naming all seven interfaces | — |
| declared `role` is binding | operator | **Yes** | E9921 second branch; test with an AP on a `sta_uplink` radio | — |
| parked declarations count | derived from the rule | **Yes** | dedicated test asserting E9921 fires while E9910 stays silent | — |
| one station per radio | phy | **Yes** | E9910, unchanged | — |
| AP/station coupling never silently accepted | wifi-scripts | **Yes** | W9901 warns; E9921 now refuses the declaration | — |
| phy binding not lost | observed failure | **Yes** | `path` recorded, `path_owner: ansible`; values match the device | — |
| everything modelled in topology | operator | **Yes** | the hand-set `path` is now authored; no unrecorded device state | — |
| egress NAT stated per zone | this session | **Yes** | E9918; applied, `masq=true` on untrusted live in nftables | — |
| MSS clamping stated per zone | this session | **Yes** | E9920; applied, clamping live on `{wan, phy1-sta0}` | — |
| uplink preference decided | this session | **Yes** | E9919; metrics 10/30 applied | — |

No Critical = No → **the solution is valid.**

Verification run: `compile-topology.py` 0 errors / 0 warnings (166 infos);
`validate-v5` PASS; adr0088-governance PASS; layer-derivation PASS, 0
violations; affected suites **267 passed, 1 skipped**.

### A guard that did its job

`test_the_real_role_split_is_clean` existed to catch divergence between the
validator and the design, and said so: *"if it ever starts warning, the
validator and the design have diverged."* It started failing the moment the rule
became binding, because it still encoded the old arrangement including the
parked 5 GHz station. The divergence was real and in the right direction — the
design changed — so the guard was updated to the new arrangement with a note
saying what it caught.

## Remaining, carried forward

Not part of this consolidation; each needs a decision rather than code.

1. **U3 tethering unmodelled** — the interface, its zone membership and its
   metric. It is what makes combination C3 possible, and under the "downlink
   only" rule it is not redundant with a phone hotspot.
2. **`192.168.88.0/24` routed over `wg_home`** is Chateau's LAN and also the
   WAN's subnet at home — correct travelling, self-contradictory here.
3. **The tunnel does not handshake**: rtr-slate's public key is not provisioned
   on the VPS, and `terraform/oci/` configures no WireGuard peers at all.
4. **`private_key_ref`** points at `instances/<name>.private_key` rather than
   the tunnel's `secrets_ref`; misleading, not functional.
5. **`wg_de`/`wg_ru`/`wg_se` share one private key** from `wg-exit`; parked.
6. **State and plan files hold private keys in clear** — OpenTofu native
   encryption, a repo-wide decision.
7. **The stock firewall zones can now be removed** — both blockers are closed:
   NAT and MSS clamping are the device's own rather than inherited.

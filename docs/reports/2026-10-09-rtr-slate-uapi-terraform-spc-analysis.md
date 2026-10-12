# SPC Analysis: rtr-slate Management via Topology + terraform-provider-uapi (OpenWrt 25.12)

**Mode:** STRICT PROCESS COMPLIANCE (`docs/ai/spc-contract.md`)
**Date opened:** 2026-10-09
**Subject:** Implementing topology-driven management of `rtr-slate` (GL.iNet GL-AXT1800 "Slate AX") through `terraform-provider-uapi` against OpenWrt 25.12, broken into implementation stages.
**Protocol:** 7-Step SPC. Each step requires explicit user `GO STEP X` before continuing. No step is merged, skipped, or anticipated.

---

## STEP 0 — READ FIRST

**Confirmation: ALL MATERIALS READ.**

Materials read in full before any analysis below:

- `adr/0118-universal-container-network-model.md` (454 lines, full)
- `adr/0119-firewall-rule-ordering-contract.md` (430 lines, full)
- `adr/0110-universal-network-zone-vlan-mechanism.md` (1251 lines, full)
- `adr/0106-capability-driven-plugin-architecture.md` (301 lines, full)
- `docs/ai/AGENT-RULEBOOK.md` (full, read earlier this session)
- `docs/ai/spc-contract.md` (full, this file)
- `configs/quality/adr0088-governance-policy.yaml` (full; edited earlier this session)
- `topology/class-modules/capability-catalog.yaml` — sections for `cap.os.routeros`, `cap.os.openwrt`, `cap.os.proxmox`, `cap.firewall.security_matrix*` (targeted read, full entries)
- `topology-tools/plugins/compilers/effective_model_compiler.py` — `_ENFORCER_TYPE_CAPS`, `_ENFORCER_ADAPTER_BY_TYPE`, `_ENFORCER_ADAPTER_IDS`, `_resolve_enforcer()` (full function, read earlier this session)
- `topology/object-modules/mikrotik/plugins.yaml` (full, read earlier this session)
- `topology/object-modules/mikrotik/templates/terraform/provider.tf.j2` and the corresponding generated `generated/home-lab/terraform/mikrotik/provider.tf` (full, read earlier this session)
- `topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml` (full, read and edited earlier this session)
- `topology/object-modules/software/obj.firmware.openwrt.glinet.4x.yaml`, `obj.os.openwrt.glinet.4x.yaml` (full, read and edited earlier this session)
- `projects/home-lab/topology/instances/devices/rtr-slate.yaml` (full, read earlier this session)
- `projects/home-lab/topology/instances/firmware/inst.firmware.openwrt.glinet.4x.yaml` (full, read earlier this session)
- `projects/home-lab/secrets/tunnels/wg-home-to-oci.yaml`, `wg-exit.yaml` (`rtr-slate` sections, decrypted and read earlier this session); confirmed absence of `projects/home-lab/secrets/instances/rtr-slate.yaml`
- External, read via WebFetch/WebSearch earlier this session: `github.com/openwrt-iac/uapi` (README), `github.com/openwrt-iac/terraform-provider-uapi` (README/docs), OpenWrt 25.12 release coverage (apk replacing opkg), OpenWrt Forum thread on GL-AXT1800 OpenWrt 25.12.x installation from stock GL.iNet firmware, GL.iNet GL-AXT1800 official hardware specification (Qualcomm IPQ6000)
- This session's own operational log: physical `rtr-slate` unit reflashed to OpenWrt 25.12 by the user; exhaustive network-level diagnosis (ping-sweep, `tcpdump` capture, static-IP probing of `192.168.1.1` and `192.168.8.1`, Linux-failsafe attempt, U-Boot HTTP-recovery attempt) across all three physical ports (LAN1, LAN2, WAN) — zero inbound traffic observed in every mode tested; conclusion reached that UART access is required for further diagnosis, and the user does not currently own a USB-TTL adapter

Explicitly **not** re-read in full for this analysis (rationale given, not a gap in the task's required material): ADR 0063 (Plugin Microkernel) and ADR 0080 (6-stage pipeline) — `docs/ai/AGENT-RULEBOOK.md` is the compact, explicitly-sanctioned derived layer for these ("Read full ADRs only when the compact rules are ambiguous or the change alters architecture"); nothing in this task's scope contradicts or stresses the compact rule text, so the full ADRs were not pulled in.

---

## STEP 1 — DOCUMENT MAP

| Document | Owner / Stakeholder | Purpose | Binding Requirements | Data Used |
|---|---|---|---|---|
| ADR 0118 — Universal Container Network Model | Architecture (Accepted, **Not implemented**) | Defines attachment/publication/policy intent model; D6 lists modeling targets and explicitly separates "runtime target" from "enforcer" | Strict profile is proposed-only; does **not** supersede ADR 0110's implemented legacy runtime | D1.1 enforcer/adapter resolution semantics; D6 target-table framing that a runtime (OpenWrt) is not automatically its own enforcer |
| ADR 0119 — Firewall Rule Ordering Contract | Architecture (Accepted, **Not implemented**) | Defines enforcer type/instance/adapter as separate axes (D1.1); plan/apply lifecycle (D3, D6) | "For each target context, exactly one compatible versioned adapter is resolved. Zero is an unsupported enforcer, reported as such... More than one is an ambiguity." No backend has qualified under this contract anywhere in the repo, including MikroTik | Exact adapter-resolution rule this analysis's gap (W7016) already exercises in running code |
| ADR 0110 — Security Matrix and Trust Zone Configuration | Architecture (**Implemented**, legacy R1-R6 runtime) | The security/firewall generation contract actually running today for MikroTik | Legacy R1-R6 matrix + mandatory final-drop-all remain authoritative and unchanged by ADR 0118/0119 | §1.4 Adapter Selection Logic table already names `class.openwrt.* → terraform_openwrt_generator → HCL (uci provider)`; §"Future Phases (Backlog)" already lists **F2: `terraform_openwrt_generator` for `rtr-slate`, priority Medium**; Phase 0–7 structure is the closest existing precedent in this repo for a staged rollout plan |
| ADR 0106 — Capability-Driven Plugin Architecture | Architecture (**Implemented**) | Derived-capability mechanism (`cap.os.*`, `has_capability()`), strict-error model (no silent fallback) | All-in: missing capability is a strict error, never a silent default | Derivation pattern that already produces `cap.os.openwrt` as a stable fact; the no-fallback discipline that ruled out a cosmetic adapter earlier this session |
| `docs/ai/AGENT-RULEBOOK.md` | Process/Governance | Compact CORE rules (CORE-001..010) | Stage affinity, `generated/` never hand-edited, `framework:lock-refresh` after framework-affecting edits, SOPS-only secrets, AI commit metadata | Governs every later implementation stage's mechanics |
| `configs/quality/adr0088-governance-policy.yaml` | Governance (this repo) | Warning allowlist/max_counts for the ADR0088 gate | `W7016` currently allowlisted at `max_counts: 1` with a comment explaining it is a stopgap, not a resolved adapter | Current governance state this plan must either retire (by registering a real adapter) or formally re-justify |
| `topology/class-modules/capability-catalog.yaml` | Schema/Data | Capability catalog | `cap.os.openwrt` exists (stable, derived, L0); `cap.firewall.security_matrix.{routeros,pve}` exist; **no `.openwrt` variant exists** | Confirms the exact shape of the missing piece: OS-identity side ready, enforcement-adapter side absent |
| `topology-tools/plugins/compilers/effective_model_compiler.py` | Code | `_ENFORCER_TYPE_CAPS`, `_ENFORCER_ADAPTER_BY_TYPE`, `_ENFORCER_ADAPTER_IDS`, `_resolve_enforcer()` | Live implementation of ADR 0118/0119 D-TYPE-1/2; emits W7015/W7016/W7017 | Exact code path that a future `cap.os.openwrt` adapter entry would extend |
| `topology/object-modules/mikrotik/` (plugins.yaml, `plugins/compilers/*.py`, `plugins/generators/terraform_mikrotik_generator.py`, `templates/terraform/*.j2`) | Code/Template | The **only** existing working instance of this exact pattern | Not binding on OpenWrt, but is the concrete architectural template this repo already uses for "security-matrix-driven Terraform generation" | Stage/order layout (compilers at order 65–74, generator at order 220), generator `config_schema` shape incl. `capability_templates` conditional-artifact mechanism, `provider.tf.j2` structure |
| `topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml` + `topology/object-modules/software/obj.{firmware,os}.openwrt.glinet.4x.yaml` | Data (topology, object level) | Current (corrected this session) device/firmware/OS model for Slate AX | `software_contract.firmware_obj_ref` still points at GL.iNet's own 4.x/23.05/opkg firmware track | Confirms **no existing object represents stock OpenWrt 25.12/apk** — a new firmware/OS object pair is required, not an edit of the GL.iNet one |
| `projects/home-lab/topology/instances/devices/rtr-slate.yaml` | Data (instance) | Current instance | Minimal placeholder (`firmware_ref`, `os_refs`, `power` only); notes field literally reads "device identity placeholders" | No existing network/wifi/firewall instance content to migrate; this is greenfield authoring |
| `projects/home-lab/secrets/tunnels/wg-home-to-oci.yaml`, `wg-exit.yaml` | Data (secrets) | Existing `rtr-slate` secret material | Only WireGuard road-warrior keys exist for `rtr-slate`; no `secrets/instances/rtr-slate.yaml` | Confirms an uapi bearer token has no home yet; CORE-010/CORE-006 convention places it at a new `secrets/instances/rtr-slate.yaml` |
| `github.com/openwrt-iac/uapi` + `github.com/openwrt-iac/terraform-provider-uapi` (+ Terraform Registry docs) | Vendor/Community (third party, MIT, **not affiliated with OpenWrt project**) | The REST backend and the Terraform/OpenTofu provider this analysis is about | Hard requirement: OpenWrt **25.12+, apk-based only**; requires `ucode-mod-ubus` + `uhttpd-mod-ucode`; bearer-token auth (`uapi-token create`); provider major version must match uapi major version; explicitly **"not field-tested on GL.iNet or firmware forks"** | ~45 curated resources (firewall, network, wireless, dhcp/dns, system, snmp, mwan3, openvpn), batch transactions, data sources (`uapi_dhcp_leases`, `uapi_whoami`, `uapi_healthz`, `uapi_diagnostics`), Terraform 1.0+/OpenTofu 1.11+ support parity |
| OpenWrt 25.12 release coverage + OpenWrt Forum thread on GL-AXT1800 25.12.x install | Vendor/Community (non-authoritative, directly operative) | Confirms firmware-version precondition | AXT1800 official OpenWrt support began at **25.12.0** (now 25.12.1); apk replaced opkg as the default package manager in this release | The exact firmware baseline the entire plan depends on |
| This session's live diagnostic log (physical unit) | Operational evidence (**Critical, currently unmet**) | Records the current real-world state of the physical device | Device unresponsive on Ethernet in every tested mode (normal boot, Linux failsafe, U-Boot HTTP recovery) across LAN1/LAN2/WAN; next diagnostic step requires UART hardware the user does not yet own | This is a live blocking precondition for any deployment/validation phase, independent of the topology-side design |

**STEP 1 COMPLETED.**

Per SPC protocol: no conclusions, no solution framing, and no model changes have been made in this step or the one before it. Document Map only.

---

## STEP 2 — CONSTRAINTS REGISTER

| # | Stakeholder | Requirement | Criticality | Type | Verification Mechanism | Source |
|---|---|---|---|---|---|---|
| 1 | Operator | `rtr-slate` must be reachable over Ethernet on at least one port before any uapi/Terraform work can be live-validated | **Critical** | Operational | ARP/`tcpdump` reachability probe | This session's diagnostic log — currently **unmet**: zero inbound traffic on LAN1/LAN2/WAN in every mode tested |
| 2 | openwrt-iac/uapi | OpenWrt **≥ 25.12**, apk-based build | Critical | Technical | `cat /etc/openwrt_release`; `apk --version` on device | uapi README |
| 3 | openwrt-iac/uapi | `ucode-mod-ubus` + `uhttpd-mod-ucode` packages installed | Critical | Operational | `apk list --installed \| grep ucode` | uapi README |
| 4 | openwrt-iac/uapi | `uapi` package installed, bearer token minted (`uapi-token create --scope '*:rw'`) | Critical | Operational | `curl .../api/v3/healthz` with token | uapi/terraform-provider-uapi docs |
| 5 | terraform-provider-uapi | Provider major.minor must match uapi backend major.minor | Important | Technical/Governance | Compare pinned provider version vs backend `/healthz` version | Provider registry docs |
| 6 | Repo governance | Never hand-edit `generated/`; new Terraform artifacts only via `compile-topology.py` | Critical | Governance | `git diff generated/` shows only generator output | CLAUDE.md, AGENT-RULEBOOK CORE-002 |
| 7 | Repo governance | New plugins preserve stage affinity; declare `depends_on`/`consumes`/`produces` | Critical | Governance | `task validate:plugin-manifests`, `task test:plugin-contract` | AGENT-RULEBOOK CORE-004 |
| 8 | Repo governance | `framework.lock` refreshed after framework/object-module edits | Critical | Governance | `task framework:lock-refresh && task framework:strict` | AGENT-RULEBOOK CORE-005 (exercised twice this session already) |
| 9 | ADR 0118/0119 D-TYPE-2 | An enforcer-adapter mapping (`cap.os.openwrt → cap.firewall.security_matrix.openwrt`) may be registered only once a real generator/compiler backs it | Critical | Architectural | Code review; absence of a hollow mapping | ADR 0119 D1.1; this session's W7016 decision |
| 10 | ADR 0110 (Implemented) | Any OpenWrt firewall pipeline must consume the **same** `inst.security_matrix.*` R1-R6 model already governing MikroTik, not a second derivation | Critical | Architectural | New generator's `consumes` block names `base.compiler.security_matrix` outputs, same as mikrotik's | ADR 0110 §1.4, §3; ADR 0119 D1 ("not a second derivation of zone membership") |
| 11 | terraform-provider-uapi (vendor disclaimer) | None formal; risk disclosure only — "not field-tested on GL.iNet or firmware forks" | Important | Technical/Risk | None available pre-deployment | Provider README |
| 12 | Repo governance | uapi bearer token stored via SOPS only, never plaintext | Critical | Governance/Security | `sops -d` succeeds on a new `secrets/instances/rtr-slate.yaml` | AGENT-RULEBOOK CORE-006/CORE-010 |
| 13 | Operator (stated this session) | Willing to reflash to 25.12 if needed — already acted on; device now unresponsive | Critical | Operational | Device boots and responds on ≥1 Ethernet port | User statement + current blocked state |
| 14 | Repo governance (ADR0088) | Compile stays at 0 errors; any new warning code is deliberately registered, not silently introduced | Important | Governance | `validate-v5` lane PASS | `adr0088-governance-policy.yaml`; this session's W7016 precedent |
| 15 | Topology completeness | `rtr-slate` has no `secrets/instances/rtr-slate.yaml` and unfilled `@optional_secret:mac` placeholders | Optional (not required for uapi function) | Operational | None required; flagged for completeness | This session's MAC investigation |

**Critical rule check:** Constraint #1 is Critical and currently **unmet**. Per SPC, this must be carried forward explicitly rather than smoothed over — see STEP 4 classification below for its exact scope of effect.

**STEP 2 COMPLETED.**

---

## STEP 3 — DIAGNOSTIC ANALYSIS (facts and calculations only — no decisions)

### 3.1 Version/architecture facts

| Fact | Value | Source |
|---|---|---|
| GL-AXT1800 real SoC | Qualcomm IPQ6000, quad-core ARM, arm64 | GL.iNet spec page (corrected in topology this session) |
| OpenWrt official AXT1800 support | Began at 25.12.0; current point release 25.12.1 | OpenWrt Forum / wiki |
| OpenWrt 25.12 package manager | apk (replaces opkg as default) | OpenWrt 25.12 release coverage |
| uapi backend version | v3.0.0 (first release May 2026) | openwrt-iac/uapi README |
| terraform-provider-uapi registry version | v2.3.0 (published 2026-06-25) | Terraform Registry |
| uapi minimum platform | OpenWrt 25.12+, apk-based releases only | uapi README |
| GL.iNet's own current firmware track (modeled in `obj.firmware.openwrt.glinet.4x`) | 4.8.2, OpenWrt 23.05 base, opkg | `docs/hardware/gl-inet/GL-AXT1800-NOTES.md` |

### 3.2 Capability/adapter coverage matrix (current state)

| Enforcer type | OS-family capability | Enforcement-adapter capability | Registered in `_ENFORCER_ADAPTER_BY_TYPE`? |
|---|---|---|---|
| network | `cap.os.routeros` | `cap.firewall.security_matrix.routeros` | Yes |
| compute | `cap.os.proxmox` | `cap.firewall.security_matrix.pve` | Yes |
| network | `cap.os.openwrt` | *(none registered)* | **No** |

`cap.os.openwrt` itself exists in `capability-catalog.yaml` (stable, derived, L0) — the OS-identity side is already a resolvable fact for `rtr-slate` today. The enforcement-adapter side has no OpenWrt entry at all, in any form, anywhere in the codebase.

### 3.3 Generator input coverage matrix (mikrotik generator's `consumes`, mapped against rtr-slate's current instance data)

| `consumes` key (from `object.mikrotik.generator.terraform`) | Produced by | Present for `rtr-slate` today? |
|---|---|---|
| `composed_matrices_by_enforcer` | `base.compiler.security_matrix` | No — `rtr-slate` is not named by any `inst.security_matrix.*` instance |
| `vlan_cidr_map` | `base.compiler.security_matrix` | No |
| `capability_flags` | `object.mikrotik.compiler.capability_flags` | No — mikrotik-specific compiler; no OpenWrt equivalent exists |
| `wireguard_tunnels` | `object.mikrotik.compiler.wireguard_tunnels` | No — no OpenWrt equivalent |
| `containers` | `object.mikrotik.compiler.containers` | No — no OpenWrt equivalent |
| `wifi_config` | `object.mikrotik.compiler.wifi_config` | No — no OpenWrt equivalent |
| `routing_policies` | `object.mikrotik.compiler.routing_policies` | No — no OpenWrt equivalent |
| `mac_vlan_assignments` | `object.mikrotik.compiler.mac_vlan_assignments` | No — no OpenWrt equivalent |
| `bridge_vlans` | `object.mikrotik.compiler.bridge_vlans` | No — no OpenWrt equivalent |
| `vlans` | `object.mikrotik.compiler.vlan_entries` | No — no OpenWrt equivalent |
| `bridges` | `object.mikrotik.compiler.bridge_entries` | No — no OpenWrt equivalent |
| `firewall_policies` | `object.mikrotik.compiler.firewall_entries` | No — no OpenWrt equivalent |
| `enforcer_resolution` | `base.compiler.effective_model` | **Partially** — resolution runs and currently returns `adapter: None` (W7016) |

Zero of the twelve vendor-specific compile-stage facts mikrotik's generator depends on have an OpenWrt counterpart today. `rtr-slate.yaml`'s instance body currently contains only `firmware_ref`, `os_refs`, `power` — no network/wifi/firewall section exists to compile from in the first place.

### 3.4 terraform-provider-uapi resource coverage vs. ADR 0110's mikrotik output (structural comparison, no gap judgment)

| ADR 0110 / mikrotik generator emits | Nearest uapi/terraform-provider-uapi resource family |
|---|---|
| `routeros_ip_firewall_addr_list` (zone address lists) | No direct address-list primitive documented; closest is firewall rule resources taking literal/aliased addresses |
| `routeros_ip_firewall_filter` (matrix-derived accept/drop, final drop-all, `place_before` ordering) | Firewall rule/zone/forwarding/redirect resources (curated, ~45 total across all families) |
| VLAN interface resources | Network interface/device resources |
| WireGuard interface + peers | Network WireGuard resources (listed explicitly in the provider's resource families) |
| Container veth/bridge attachment | No direct equivalent documented (OpenWrt has no built-in container runtime analogous to RouterOS containers) |

### 3.5 Physical diagnostic facts (this session, consolidated)

| Port | Mode tested | Target | Result |
|---|---|---|---|
| LAN1 | Normal boot | `192.168.1.1` | carrier up; 0 inbound frames |
| LAN2 | Normal boot | `192.168.1.1` | carrier up; 0 inbound frames |
| LAN2 | Linux failsafe attempt (reset during boot-blink window) | `192.168.1.1` | 0 inbound frames; user reported no blink observed |
| LAN2 / WAN | U-Boot HTTP-recovery attempt (reset held ~5s from power-on) | `192.168.1.1` | 0 inbound frames on either port |
| LAN2 | GL.iNet stock-firmware backup-partition hypothesis | `192.168.8.1` | 0 inbound frames |
| WAN | Normal boot | `192.168.1.1` | carrier up; 0 inbound frames |

9 distinct port/mode/target combinations tested; 0 produced any inbound Ethernet frame of any kind (not ARP, not DHCP, not HTTP). `tcpdump` captured only this laptop's own outgoing ARP requests in every case.

**STEP 3 COMPLETED.** No recommendations or decisions appear above — facts and structural comparisons only.

---

## STEP 4 — PROBLEM CLASSIFICATION (classification only — not a solution)

**Primary classification: Implementation gap, not a design gap.** ADR 0110 §1.4 and its Backlog (item F2) already name the exact slot (`class.openwrt.* → terraform_openwrt_generator`); ADR 0118/0119 D-TYPE-1/2 already specify the generic adapter-resolution mechanics that produced W7016. Nothing architectural requires invention; the gap in §3.2–3.3 is entirely that the OpenWrt-side code, capability entries, object/instance data, and generator/templates named by that slot have not been written yet.

**Secondary classification: the task splits into two independently-timed problem classes.**

| Class | Nature | Blocked by Critical constraint #1? |
|---|---|---|
| **A — Topology/code implementation** (capability-catalog entry, `effective_model_compiler.py` adapter map, new firmware/OS objects for stock OpenWrt 25.12/apk, `rtr-slate` instance network/firewall data, new compiler(s) + `TerraformOpenWrtGenerator` + templates) | Implementation gap; design gap = none (ADR-sanctioned); governance gap = none (ADR0088/CORE rules already demonstrated workable this session) | **No.** All of this is buildable and locally compile/validate-testable without the physical device responding. |
| **B — Live validation/deployment** (installing `uapi` + `ucode-mod-ubus`/`uhttpd-mod-ucode` on-device, minting a bearer token, `terraform plan`/`apply` against the real backend, confirming rule behavior) | Operational/timing gap | **Yes.** Requires Ethernet reachability, which constraint #1 currently denies on every tested port/mode. |

**Tertiary classification: constraint #1's failure is scoped to Class B, not to the whole task.** SPC's "NO VALID SOLUTION" clause attaches to the specific unmet Critical requirement, not by extension to every requirement in the register — Class A's requirements (##2–10, 12, 14–15 as applicable) are independently satisfiable today and are not contingent on constraint #1.

**STEP 4 COMPLETED.**

---

## STEP 5 — ADMISSIBLE SOLUTION SPACE (constrained options only — no model changes, no numbers changed, nothing "checked on the model")

| Problem | Possible Mechanism | Constraints engaged | Admissible? | Why |
|---|---|---|---|---|
| **A1.** Represent stock OpenWrt 25.12/apk in topology, given existing objects only model GL.iNet's own 4.x/opkg track | **M1:** Add new sibling objects `obj.firmware.openwrt.stock.25_12` + `obj.os.openwrt.stock.25_12` (arm64, apk); repoint `rtr-slate`'s `software_contract` at them; leave GL.iNet 4.x objects untouched | ADR 0118 D7 authoritative-field contract; existing routeros per-arch sibling-object precedent | **Yes** | Matches the existing pattern (`obj.firmware.routeros.7.arm64` / `.x86_64` siblings); does not repurpose an object whose own `@title`/`vendor_capabilities` identify it as GL.iNet-specific |
| | **M2:** Overwrite `obj.firmware.openwrt.glinet.4x` in place to describe stock OpenWrt 25.12/apk | ADR 0118 D7 | **No** | Destroys the documented GL.iNet-firmware-track identity; contradicts the object's own declared `@title` and `vendor_capabilities: [vendor.glinet.openwrt.firmware]`; unnecessary blast radius |
| **A2.** Represent the OpenWrt network/firewall pipeline needed to drive the provider | **M1:** Mirror the mikrotik pattern — new compile-stage compiler(s) + one generate-stage `TerraformOpenWrtGenerator`, gated by a new `cap.firewall.security_matrix.openwrt`, consuming the **same** `security_matrix_compiler.py` outputs mikrotik already consumes | ADR 0110 §1.4/§3; ADR 0119 D1 ("not a second derivation of zone membership") | **Yes** | This is the exact slot ADR 0110 already named; reuses the one existing security-matrix compiler rather than inventing a parallel one |
| | **M2:** Build against ADR 0118/0119's full strict profile (attachments/publications/SEC-CAP evidence/versioned IR) instead of the legacy R1-R6 matrix | ADR 0118/0119 status: "Not implemented; no backend has qualified under this contract" anywhere, including MikroTik | **Not admissible yet** | No reference implementation exists to mirror even for the most mature platform in this repo; would invert the repo's own stated migration order |
| **A3.** Registration of the `cap.os.openwrt → cap.firewall.security_matrix.openwrt` adapter mapping, and disposition of the W7016 allowlist entry | **M1:** Register the mapping only as the **last** step of building the real pipeline (A2-M1), removing the W7016 allowlist/`max_counts` entry in the same change | ADR 0119 D1.1; ADR 0106 no-silent-fallback; this session's own earlier W7016 decision | **Yes** | Matches the sequencing this session's W7016 fix explicitly anticipated; keeps the capability model honest in both directions |
| | **M2:** Register the mapping early, before the generator exists, to clear the W7016 warning sooner | same | **No** | Identical to the cosmetic-adapter problem already rejected this session — an adapter with no generator behind it is a false claim of coverage |
| **A4.** Credential path for the uapi bearer token | **M1:** New `projects/home-lab/secrets/instances/rtr-slate.yaml`, SOPS-encrypted | AGENT-RULEBOOK CORE-006/CORE-010; existing per-device secrets-file precedent | **Yes** | Matches documented lookup convention and the pattern every other device instance already follows |
| | **M2:** Store the token inline in `topology/` YAML, or inside another device's existing secrets file (e.g. `secrets/terraform/mikrotik.yaml`) | CORE-006 | **No** | Plaintext-in-topology violates CORE-006 outright; piggybacking conflates two devices' credential lifecycles |
| **B1.** How to sequence Class A against Class B's unmet Critical constraint | **M1:** Treat Class A and Class B as independently schedulable — build and locally validate (`compile-topology.py`, `validate-v5`, unit tests) Class A now; track Class B (UART acquisition → device recovery → on-device uapi install → live `terraform plan`/`apply`) as an explicit open item | AGENT-RULEBOOK's own topology-first workflow ("edit topology → compile → generate" precedes "apply") | **Yes** | Does not require the unmet constraint to be satisfied in order to make progress on the part that doesn't need it |
| | **M2:** Declare the entire task "NO VALID SOLUTION" and halt all work until the physical device responds | SPC NO-VALID-SOLUTION clause | **No** | Over-scopes the clause — it attaches to constraint #1 specifically (Class B), not to Class A's independently satisfiable requirements |

**STEP 5 COMPLETED.** No solution has been implemented. No topology, code, or model file has been modified in Steps 2–5.

---

---

## STEP 3 (SUPPLEMENT) — EXTERNAL TECHNICAL FACTS, VERIFIED FROM SOURCE

Added after the first diagnostic pass, from a dedicated deep-research run against provider docs, `build/openapi.json` (uapi v3.0.0, 2026-08-13), firewall4 sources and the OpenWrt 25.12 branch. Facts only; provenance marked. **Three of these invalidate a naive port of the MikroTik design and are therefore load-bearing.**

### S3.1 Resource inventory (exact type names)

Provider config: `endpoint` (must include `/api/v3`), `token`, `insecure`. 48 curated endpoints; `/raw` passthrough deliberately not exposed.

| Family | Resources | Key required args |
|---|---|---|
| Firewall | `uapi_firewall_zone`, `uapi_firewall_forwarding`, `uapi_firewall_rule`, `uapi_firewall_redirect`, `uapi_firewall_nat`, `uapi_firewall_defaults` | zone: `name`; forwarding: `src`,`dest`; rule: `target`,`match{}`; nat: `target`,`match{}`; defaults: singleton |
| Network | `uapi_network_interface`, `uapi_network_device`, `uapi_network_bridge_vlan`, `uapi_network_route`, `uapi_network_rule`, `uapi_network_wireguard_peer` | interface: `proto`; device: `name`; bridge_vlan: `device`,`vlan`; route: `target` |
| Wireless | `uapi_wireless_device`, `uapi_wireless_interface` | device: `type`; interface: `device` |
| DHCP/DNS | `uapi_dhcp_server`, `uapi_dhcp_host`, `uapi_dhcp_dnsmasq`, `uapi_dhcp_odhcpd`; data-only `uapi_dhcp_leases`, `uapi_dhcp_leases6` | server: `interface` |
| System/other | `uapi_system`, `uapi_system_password`, `uapi_authorized_key`, `uapi_package`, `uapi_sqm_queue`, mwan3×5, unbound×3, snmpd×5, `uapi_uhttpd_*`, `uapi_openvpn_instance`, `uapi_dropbear_instance`, `uapi_usteer_config`, `uapi_lldpd_config`, `uapi_vnstat_config` | |
| Ephemeral | `uapi_token` — mints a scoped bearer token for one run, revoked on close | `name`, `scopes` |

**Confirmed absent:** `firewall_ipset`, `firewall_include`, `firewall_helper`, `network_globals`, any switch/`swconfig` resource, any WireGuard *interface* resource (use `uapi_network_interface` with `proto="wireguard"` + `uapi_network_wireguard_peer`), any backup/confirm endpoint.

Two schema facts that directly constrain a zone-matrix design:

1. **`uapi_firewall_zone` exposes only `network` (list), `input`, `forward`, `output_policy`, `family`, `masq`, `mtu_fix` — no `device`, no `subnet`.** Every zone member must be a real `config interface` section; a bare kernel device cannot be zoned.
2. `match.*` fields are **lists** on `firewall_rule` but **scalars** on `redirect`/`nat` (only `proto` stays a list). A list where fw4 expects a scalar makes fw4 **drop the whole section silently**.

### S3.2 Firewall semantics — default-deny is structural; a final drop-all is wrong here

Read from firewall4 source, not documentation:

- `ruleset.uc` emits base chains as `type filter hook input priority filter; policy <fw4.input_policy(true)>`; `*_policy(true)` maps `reject`→`drop`, so a `REJECT` default renders **`policy drop`** plus a trailing `jump handle_reject` ([ruleset.uc L112-152](https://github.com/openwrt/firewall4/blob/master/root/usr/share/firewall4/templates/ruleset.uc), [fw4.uc L1839-1852](https://github.com/openwrt/firewall4/blob/master/root/usr/share/ucode/fw4.uc)).
- `parse_defaults` defaults input/output/forward to **`drop`** when absent (fw4.uc L1993-1995). Stock 25.12 `/etc/config/firewall` ships `input REJECT / output ACCEPT / forward REJECT` ([firewall.config, openwrt-25.12](https://github.com/openwrt/openwrt/blob/openwrt-25.12/package/network/config/firewall/files/firewall.config)).
- Each zone chain self-terminates: `forward_<zone>` ends `jump <policy>_to_<zone>`; `input_<zone>` ends `jump <policy>_from_<zone>`. Zone policy defaults to the global default (fw4.uc L2045-2047).

**Default-deny therefore exists in two independent layers** — the nftables base-chain `policy drop` for traffic matching no zone jump at all, and the per-zone terminal jump. **ADR 0110's mandatory final drop-all (§4.4, `E7082`) is a RouterOS-specific compensation for default-accept chains and must NOT be ported:** an appended drop-all would land inside a zone chain (or the base forward chain) *ahead* of the forwardings it is supposed to follow (see S3.3), breaking intended flows rather than securing anything.

Residual risks, precisely located:

| # | Risk | Mechanism |
|---|---|---|
| R-1 | A new DENY does not terminate existing flows | `ct state vmap { established: accept, related: accept }` is emitted at the **top** of base input/forward chains (L118/L141), before any generated rule. A reload must be paired with `conntrack -D`/`-F`. |
| R-2 | Offloaded flows bypass the entire matrix | `flow_offloading`/`flow_offloading_hw` insert `flow offload @ft` at the head of `forward`. Must stay false. |
| R-3 | Router's own services exposed to "trusted" zones | Input chain ≠ forward chain. Stock `lan` zone is `input ACCEPT`. A matrix modeling only inter-zone *forward* leaves `input` wide open. **`zone.input` must be modeled explicitly** — ADR 0110's matrix does not currently cover it. |
| R-4 | Router-originated egress unconstrained | Unzoned interfaces are denied for forward/input via base `policy drop`, but `output` is `ACCEPT` unless `defaults.output_policy` is set. |
| R-5 | A device without a `config interface` is in no zone → silently dead | Zones match `iifname` over the resolved devices of their `network` list. Fail-safe (dead, not open), but it presents as a bug. |

### S3.3 Rule ordering — no control exists, and does not need to

Grepping the full 846 KB `openapi.json` for `position|order|index|place_before|after|sort` returns **zero hits**. The ULID "survives reorders" but does not establish one.

Order is fw4 parse order: `fw4.rules(chain)` is a stable filter over a push-ordered array (fw4.uc L1863); sections are read via `cursor.foreach("firewall", <type>, …)` = `/etc/config/firewall` file order, and `uci add` appends.

**The decisive asymmetry:** `foreach("firewall","rule")` runs at L821, `foreach("firewall","forwarding")` at L829 — both push into the same `state.rules`. So **every `config rule` precedes every `config forwarding` in the same chain, regardless of file order.** R6 explicit overrides beat zone forwardings structurally, with no ordering machinery.

Where order still matters: two overlapping `config rule` sections in one chain with opposing targets — and Terraform's DAG applies in parallel, so creation order is nondeterministic. **The replacement for `place_before` is a validator asserting pairwise-disjoint match tuples**, not a positional model.

### S3.4 State, import and apply safety

- **Adoption of *named* sections is non-mutating since uapi 2.2.0**: `lan`, `wan`, `br-lan`, stock zones adopt in place keeping their names (`terraform import uapi_network_interface.lan lan` → plan clean). **Anonymous `cfgXXXXXX` sections adopt by renaming to a ULID — that mutates the router.** Duplicate-name creation is `422 conflict` on ≥2.2.1 ([adopting-named-sections](https://github.com/openwrt-iac/terraform-provider-uapi/blob/main/docs/guides/adopting-named-sections.md)).
- Reference rule: *section* refs use `.id`; *kernel device* refs use `.name`.
- **No commit-confirm shipped.** Per-write atomicity exists (snapshot→validate→commit→reload→restore-on-failure under per-package flock; `500 reload_failed_restored` vs `reload_failed_unrecovered`), but timed rollback was built, soaked and **pulled**: the Terraform plugin protocol has no apply-scoped hook, and `?confirm` per-write dies at resource 2 with `already_armed` *and corrupts state* ([commit-confirm.md](https://github.com/openwrt-iac/uapi/blob/main/docs/commit-confirm.md)).
- What *is* shipped: **`apply-confirm` as a standalone apk** (`stage`/`ack`/`rollback`/`status`; snapshots = `uci export`, rollback = `uci import`+commit+reload), driven **out of band**: `stage` → `terraform apply` → verify → `ack`. Plus `GET /diagnostics?validate=1` preflight and a `management_path` + `X-Mgmt-Path-Warning` header when a write moves the `disabled`/`proto`/`ipaddrs`/`netmask` of the interface the request arrived through. **Deliberately no firewall analysis** — upstream declines to predict firewall lockout ([roadmap.md](https://github.com/openwrt-iac/uapi/blob/main/docs/roadmap.md)).
- **Apply-time stranding is structurally unrecoverable in state:** if a write strands the caller, the response never arrives and Terraform records nothing.

### S3.5 GL-AXT1800 hardware facts (from DTS/board.d, not forum lore)

`target/linux/qualcommax/ipq60xx/base-files/etc/board.d/02_network`: `glinet,gl-axt1800) ucidef_set_interfaces_lan_wan "lan1 lan2" "wan"`. DTS `ipq6000-gl-axt1800.dts`: `&dp1 label="wan"` (ESS_PORT1), `&dp2 label="lan2"` (ESS_PORT2), `&dp3 label="lan1"` (ESS_PORT3).

- **Three independent netdevs `wan`, `lan1`, `lan2`** — nss-dp/edma data-path ports, **not** a classic DSA switch with a CPU port. **There is no `eth0`.**
- `br-lan` ports = `["lan1","lan2"]`; `wan` standalone.
- **`dp2`→`lan2` and `dp3`→`lan1` are inverted** relative to dp index — port mapping must not be inferred from numbering.
- **Repo data defect found:** `obj.glinet.slate_ax1800.yaml` marks all three ethernet interfaces `dsa: true`. Per the above this is incorrect for this SoC family. Registered as a Phase-1 correction task below; not changed by this analysis (STEP 6 not executed).

**Known 25.12.x defects on this exact device** (open OpenWrt issues): 2.4 GHz radio reports `Not supported (-95)` from netifd / "Device is not active" in LuCI despite working ([#22297](https://github.com/openwrt/openwrt/issues/22297), [#22074](https://github.com/openwrt/openwrt/issues/22074)); repeated `CTRL-EVENT-BEACON-LOSS` and 2.4 GHz crashes ([#21512](https://github.com/openwrt/openwrt/issues/21512)); ath11k memory leak on kernel 6.12 ([#19702](https://github.com/openwrt/openwrt/issues/19702)). Consequence: `uapi_wireless_device` state on radio1 may not reflect reality → persistent plan diffs or false-healthy reads.

> **SUPERSEDED, 2026-10-11 — see the WIRELESS RESEARCH section below.** The paragraph above reads these issues at face value and is wrong on two of the three counts: the `-95` lines are cosmetic log noise from an unredirected `iw` call (ath11k has no `set_coverage_class` op at all), and the beacon-loss/crash defect is already fixed in 25.12.5 by commit `a62b5fe71c`. Only the memory leak is real and unfixed. The conclusion drawn here — that wireless should be deferred partly because the 2.4 GHz radio is unreliable — does not hold; the radio plan that follows from the corrected facts is the opposite of the one implied here.

---

## STEP 5 (REVISED) — ADMISSIBLE SPACE AFTER THE SUPPLEMENT

The supplement closes two mechanisms that looked admissible before it, and opens two that were not visible:

| Problem | Mechanism | Admissible? | Why |
|---|---|---|---|
| **A5.** Lowering the R1-R6 matrix onto OpenWrt | **M1:** Express R1-R5 entirely as `uapi_firewall_zone` (with **both** `input` and `forward` policies) + `uapi_firewall_forwarding`; emit **zero** `firewall_rule` sections for them | **Yes — preferred** | Zone chains are terminal (S3.2), so the whole matrix lowers to zone policy + forwardings. Smallest resource surface, no ordering exposure |
| | **M2:** Port the MikroTik shape — address-list-equivalents + per-pair `firewall_rule` accept/deny + final drop-all + ordering control | **No** | (a) No address-list primitive exists and `firewall_zone` has no `subnet`/`device` (S3.1); (b) a final drop-all is actively harmful here (S3.2); (c) no ordering control exists anywhere in the API (S3.3) |
| **A6.** Replacing `place_before` ordering guarantees | **M1:** A validator asserting generated `firewall_rule` match tuples are **pairwise disjoint**, making order semantically irrelevant | **Yes** | The only order-independent construction available; fw4's rule-before-forwarding asymmetry already gives R6 precedence for free (S3.3) |
| | **M2:** `depends_on` chaining in generated HCL to serialize rule creation | **Not admissible as the primary mechanism** | Serializes the apply and is fragile; Terraform DAG order is still not device packet order (ADR 0119 D4 says this explicitly) |
| **A7.** Covering the router's own input path (R-3) | **M1:** Extend the compiled matrix consumption to emit `zone.input` policy per zone, declaring management-plane exposure explicitly in topology | **Yes, and required** | Stock `lan` is `input ACCEPT`; a forward-only matrix silently leaves router services open. ADR 0110 does not model this today — a real coverage gap, not an OpenWrt quirk |
| **A8.** First-apply state reconciliation | **M1:** Model `uci_section_name` as topology data and generate TF 1.5+ `import {}` blocks for the **named** stock sections (`lan`, `wan`, `br-lan`, `firewall_zone.lan/wan`, `dhcp_server.lan`) before creating anything | **Yes** | Named-section adoption is non-mutating (S3.4); generating import blocks keeps the ledger in topology instead of operator memory |
| | **M2:** Let Terraform create fresh sections alongside the stock ones | **No** | `422 conflict` on name collision; and anonymous-section adoption mutates the router by renaming to ULIDs |
| **A9.** Apply safety without commit-confirm | **M1:** Out-of-band `apply-confirm stage` → `terraform apply` → verify → `ack`, wrapped in the existing `scripts/orchestration/lane.py`, with `/diagnostics?validate=1` preflight and the management interface's `proto`/`ipaddrs`/`netmask` declared immutable and excluded from generation | **Yes** | The only shipped mechanism (S3.4); mirrors ADR 0110's own "backup before apply" discipline using the OpenWrt-native equivalent |
| | **M2:** Rely on uapi's `?confirm` query parameter per write | **No** | Dies at resource 2 with `already_armed` and corrupts state; upstream pulled it |

---

## IMPLEMENTATION STAGES

Phase numbering follows ADR 0110's own Phase 0-7 precedent. Each phase states exit criteria and rollback. **Phases 0-6 are topology/code work (Class A) and are not blocked by the unreachable device; Phases 7-9 are Class B and are.**

### Phase 0 — Preconditions (Class B gate)

| Task | Exit criteria |
|---|---|
| Recover Ethernet reachability on `rtr-slate` (UART diagnosis → identify boot stage → reflash or repair network config) | Device answers ARP on at least one port |
| Confirm `cat /etc/openwrt_release` ≥ 25.12 and `apk --version` works | Constraints #2 verified on-device |
| Record firmware build id and the real port mapping observed (expect `wan`, `lan1`, `lan2`; no `eth0`) | Matches S3.5 or the discrepancy is documented |

**Rollback:** none needed (read-only). **Note:** Phases 1-6 may proceed in parallel with this phase; only Phases 7-9 wait on it.

### Phase 1 — Topology data model (no code)

| Task | Files | Exit criteria |
|---|---|---|
| New firmware/OS objects for stock OpenWrt 25.12 (arm64, apk) as **siblings**, leaving GL.iNet 4.x objects intact (A1-M1) | `topology/object-modules/software/obj.firmware.openwrt.stock.25_12.yaml`, `obj.os.openwrt.stock.25_12.yaml` | Compile clean; GL.iNet objects unchanged |
| New instances for the above; repoint `rtr-slate`'s `firmware_ref`/`os_refs` | `projects/home-lab/topology/instances/{firmware,os}/…`, `devices/rtr-slate.yaml` | `cap.os.openwrt` still derives; no arch mismatch (E3201/E7891) |
| Correct `dsa: true` → nss-dp/edma reality on the three ethernet interfaces (S3.5) | `topology/object-modules/glinet/obj.glinet.slate_ax1800.yaml` | Matches DTS facts |
| Add `uci_section_name` to the device model for adoption (A8-M1) | same object + `rtr-slate.yaml` | Named stock sections enumerable from topology |
| Author `rtr-slate`'s network/zone/DHCP instance data (currently absent entirely) | `rtr-slate.yaml` | Zone membership expressed as **interface** membership, not CIDRs (S3.1) |
| `task framework:lock-refresh` (CORE-005) | `projects/home-lab/framework.lock.yaml` | `task framework:strict` passes |

**Rollback:** `git revert`; no device contact.

### Phase 2 — Diagnostic band + capability registration (governance first)

| Task | Files | Exit criteria |
|---|---|---|
| Allocate and **register before implementation** a diagnostic band for the OpenWrt generator (`E92xx` is already MikroTik's) | `docs/diagnostics-catalog.md` | `tests/test_diagnostic_code_registry.py` passes |
| Add `cap.firewall.security_matrix.openwrt` to the catalog — **but do not wire it yet** (A3-M1 orders this last) | `topology/class-modules/capability-catalog.yaml` | Capability contract check OK |

**Rollback:** `git revert`. **Constraint:** codes are immutable once released — allocation is one-way.

### Phase 3 — Compile-stage compilers (all derivation here, none in projection)

| Task | Files | Exit criteria |
|---|---|---|
| `openwrt_zones_compiler` — lower R1-R5 into per-zone `input`+`forward` policies + forwarding pairs (A5-M1, A7-M1), consuming `composed_matrices_by_enforcer`/`vlan_cidr_map` from the **existing** `base.compiler.security_matrix` | `topology/object-modules/openwrt/plugins/compilers/` | Published facts visible pre-validate |
| `openwrt_interfaces_compiler` — bridge/VLAN/interface shape incl. `br-lan` = `[lan1,lan2]` | same | — |
| `openwrt_rule_disjointness` facts for the A6-M1 validator | same | Pairwise-disjoint tuples provable |
| Register all in `plugins.yaml` with `migration_mode: migrated`, explicit `depends_on`/`consumes`/`produces`, stage `compile` | `topology/object-modules/openwrt/plugins.yaml` | `task validate:plugin-manifests`, `task test:plugin-contract` pass |

**Design constraint (hard):** derivation must not land in the generate-stage projection — `PROJECTION_FUNCTION_BUDGET = 2` / `PROJECTION_LINE_BUDGET = 528` are test-enforced and the "W07 migration" precedent moved ten functions out of `projections.py` for exactly this reason.

### Phase 4 — Validators

| Task | Exit criteria |
|---|---|
| Pairwise-disjointness validator for generated `firewall_rule` match tuples (A6-M1) | Overlapping tuples block the build |
| `match.*` arity validator: lists on `firewall_rule`, scalars on `redirect`/`nat` except `proto` (S3.1) | A scalar/list mismatch is a named error, not a silent fw4 section drop |
| Management-path immutability validator: the interface carrying uapi must not have `proto`/`ipaddrs`/`netmask` generated (A9-M1) | Violation blocks generation |
| Zone-coverage validator: every generated interface belongs to exactly one zone (R-5) | Unzoned interface is an error |

### Phase 5 — Generator + templates

| Task | Files | Exit criteria |
|---|---|---|
| `TerraformOpenWrtGenerator(BaseGenerator)` mirroring the MikroTik structure (artifact contract, shared helpers, StrictUndefined templates, explicit projection-contract defaults) | `topology/object-modules/openwrt/plugins/generators/terraform_openwrt_generator.py` | Emits into `generated/home-lab/terraform/openwrt/` |
| Templates: `provider.tf.j2` (`openwrt-iac/uapi`, pinned to match backend major), `variables.tf.j2`, `interfaces.tf.j2`, `zone_firewall.tf.j2`, `dhcp.tf.j2`, `imports.tf.j2` | `topology/object-modules/openwrt/templates/terraform/` | No final drop-all emitted anywhere (S3.2) |
| Generator tests mirroring `test_terraform_mikrotik_generator.py`, `test_mikrotik_capability_driven.py` | `tests/plugin_integration/` | Green |

**Explicit v1 exclusions** (cut lines, from the research recommendation): no ordering/`place_before` model, no final drop-all emitter, no `flow_offloading`, NAT limited to one MASQUERADE with **explicit `match.family`** (not defaulted → absent means IPv4-only), no ipsets/includes (no resources exist), no mwan3/SQM/unbound, no WireGuard on this box, no `uapi_system_password`/`uapi_uhttpd_*` management (lockout surface with no rollback), and **no 2.4 GHz radio management** (S3.5 defects).

### Phase 6 — Wire the adapter, retire the stopgap

| Task | Files | Exit criteria |
|---|---|---|
| Add `"cap.os.openwrt": "cap.firewall.security_matrix.openwrt"` to `_ENFORCER_ADAPTER_BY_TYPE["network"]` and the id to `_ENFORCER_ADAPTER_IDS` | `topology-tools/plugins/compilers/effective_model_compiler.py` | `rtr-slate` resolves to a real adapter |
| Create `inst.security_matrix.openwrt` naming `rtr-slate` via `managed_by_ref`, `enforcement_plane: perimeter` | `projects/home-lab/topology/instances/network/` | ADR 0110 M1-B satisfied (one matrix → one enforcer) |
| **Remove** the `W7016` allowlist + `max_counts` entry added 2026-10-09 | `configs/quality/adr0088-governance-policy.yaml` | `validate-v5` PASS with W7016 no longer emitted at all |

**This is the ordering the earlier W7016 decision explicitly deferred to.** Doing it before Phases 3-5 would recreate the hollow-adapter defect ADR 0119 D1.1 forbids.

### Phase 7 — On-device enablement (Class B)

| Task | Exit criteria |
|---|---|
| `apk add uapi`; verify `ucode-mod-ubus`, `uhttpd-mod-ucode` | `GET /api/v3/healthz` answers |
| `uapi-token create --name terraform --scope '*:rw'`; store via SOPS at `projects/home-lab/secrets/instances/rtr-slate.yaml` (A4-M1) | `sops -d` round-trips; no plaintext in git |
| Install `apply-confirm` apk (A9-M1) | `apply-confirm status` works |
| Pin provider version to the backend's major/minor (constraint #5) | Versions match |

### Phase 8 — Adoption and first plan (Class B)

| Task | Exit criteria |
|---|---|
| Apply generated `import {}` blocks for named stock sections | `terraform plan` shows **no changes** for adopted sections |
| `GET /diagnostics?validate=1` preflight on the candidate write set | No rejected sections |
| Review plan for any management-path mutation | Zero diffs touching the uapi-carrying interface |

**Rollback:** `terraform state rm` for mis-adopted sections; nothing mutated on the router if only named sections were adopted.

### Phase 9 — Guarded apply and verification (Class B)

| Step | Detail |
|---|---|
| 1 | `apply-confirm stage` (snapshot via `uci export`) |
| 2 | `terraform apply` |
| 3 | Verify: positive paths (each zone's intended flows) **and** negative paths (each intended deny), plus router-input exposure per zone (R-3) |
| 4 | `conntrack -D` / `-F` after any deny change (R-1) — otherwise existing flows survive the new policy |
| 5 | Read back effective nft ruleset and compare semantically, not by resource count (ADR 0119 D6) |
| 6 | `apply-confirm ack` on success; `apply-confirm rollback` on failure |

**Floor:** physical failsafe (hold reset during boot) remains the last resort — and per this session's experience, that path is itself currently unproven on this unit.

---

## STEP 7 — VALIDATION & COMPLIANCE MATRIX

| Requirement | Source | Met (Yes/No) | How verified | If No → what must change |
|---|---|---|---|---|
| #1 Device reachable over Ethernet | Session diagnostics | **No** | 9 port/mode/target combinations, 0 inbound frames | UART diagnosis → identify boot stage → repair/reflash (Phase 0) |
| #2 OpenWrt ≥ 25.12, apk | uapi README | Unverified | Cannot read `/etc/openwrt_release` while unreachable | Phase 0 |
| #3 `ucode-mod-ubus`, `uhttpd-mod-ucode` | uapi README | No (not installed) | — | Phase 7 |
| #4 `uapi` installed + token minted | uapi docs | No | — | Phase 7 |
| #5 Provider/backend version match | Registry docs | N/A yet | — | Phase 7 pin |
| #6 `generated/` never hand-edited | CORE-002 | **Yes** | This analysis wrote no generated artifact; all planned output flows through the generator | — |
| #7 Stage affinity + manifests | CORE-004 | **Yes (by design)** | Phase 3/5 place compilers at `compile`, generator at `generate`, both manifest-declared | Enforced by `task validate:plugin-manifests` |
| #8 `framework.lock` refreshed | CORE-005 | **Yes** | Exercised twice this session; Phase 1 repeats it | — |
| #9 No hollow enforcer adapter | ADR 0119 D1.1 | **Yes** | Adapter registration deferred to Phase 6, after the generator exists | — |
| #10 Reuse the single security-matrix derivation | ADR 0110 §1.4; ADR 0119 D1 | **Yes (by design)** | Phase 3 compilers consume `base.compiler.security_matrix` outputs; no second derivation | — |
| #11 Provider untested on GL.iNet-class hardware | Provider README | **No (unmitigable pre-deployment)** | Accepted risk; Phase 9 verification is the only mitigation | — |
| #12 SOPS-only secrets | CORE-006/010 | **Yes (by design)** | Phase 7 places the token in `secrets/instances/rtr-slate.yaml` | — |
| #14 Compile 0 errors; warnings deliberate | ADR0088 policy | **Yes** | `validate-v5` PASS as of this session; Phase 6 retires W7016 rather than leaving it allowlisted forever | — |
| **No final drop-all ported** | S3.2 (firewall4 source) | **Yes** | Phase 5 exclusions make it explicit | — |
| **Ordering independence** | S3.3 | **Yes (by design)** | Phase 4 disjointness validator replaces `place_before` | — |
| **Router input path covered** | S3.2 R-3 | **Yes (by design)** | Phase 3 emits `zone.input` explicitly; flagged as an ADR 0110 model gap | ADR 0110 should be amended to model `input` policy, not just inter-zone forward |

**Critical-requirement verdict:** Requirement #1 is Critical and **not met**. Per SPC this means **no valid solution exists for Class B (live deployment) today** — Phases 7-9 cannot begin. Class A (Phases 1-6) has no unmet Critical requirement and is fully admissible now.

**STEP 7 COMPLETED.**

---

## STEP 6 — NOT EXECUTED (deliberate)

The requested deliverable was analysis plus staged decomposition, not a model rebuild. No topology, capability, plugin, template, or instance file was modified by this analysis. The only repo changes made during this session predate it (the CPU/architecture correction and the W7016 allowlist entry, both committed as `7f82c282` on branch `rtr-slate-terraform`).

Phase 1 is the entry point whenever implementation is authorized.

## PHASE 0 EXECUTION RECORD — 2026-10-11

Device recovered by the operator (reflashed, connected to `rtr-mikrotik-chateau`). Phase 0 executed read-only over SSH. **Constraint #1 is now MET.**

### P0.1 Reachability — how it was found

A first attempt failed with the same total silence as 2026-10-09. Root cause was **on Chateau, not on rtr-slate**:

```
/interface bridge port:  ether3  pvid=99
/interface bridge vlan:  vlan-ids=99   tagged=bridge  untagged=ether5    <- ether3 absent
                         vlan-ids=1    untagged=ether3,ether2,...        <- ether3 untagged here
                         vlan-ids=100  tagged=bridge,ether3              <- ether3 is a tagged trunk
```

`ether3` carries `pvid=99` while holding no VLAN 99 membership; its untagged membership is declared in VLAN 1 and it is a tagged trunk for VLAN 100. Untagged frames from rtr-slate were classified into VLAN 99 and dropped at the bridge — no ARP, no DHCP, nothing reached Chateau. After moving the cable to an untagged VLAN 1 port, the device answered immediately.

**This is live drift not represented in topology** (`rtr-mikrotik-chateau.yaml` declares `bridge_ports` with no per-port PVID). Registered as finding 4 below.

Reached at `192.168.1.1`, MAC `94:83:c4:20:1f:6c`, 0% loss, RTT ~6 ms, over the shared L2 segment using a secondary address on the laptop (rtr-slate is cabled by **LAN2**, so it is a DHCP *server* on that link, never a client — which is why no Chateau lease ever appeared).

### P0.2 Verified device facts

| Fact | Observed value | Verdict |
|---|---|---|
| Release | `OpenWrt 25.12.5 r33051-f5dae5ece4` | Constraint #2 **MET** (≥ 25.12) |
| Target / arch | `qualcommax/ipq60xx` / `aarch64_cortex-a53` | **Confirms the arm64 correction** made 2026-10-09; the former `mipsel`/MT7621A data was wrong |
| Board / model | `glinet,gl-axt1800` / GL.iNet GL-AXT1800 | — |
| Package manager | `apk-tools 3.0.5` | Constraint #2 (apk) **MET** |
| Netdevs | `wan`, `lan1`, `lan2`, `br-lan` — **no `eth0`** | **Confirms S3.5 exactly**: three independent netdevs, not classic DSA |
| `br-lan` ports | `lan1`, `lan2` | Confirms S3.5 |
| Link state | `lan2` UP (our cable); `lan1`, `wan` NO-CARRIER | WAN unplugged → **no internet, see P0.4** |
| Overlay free | 82.2 MB of 86.7 MB | Ample for uapi |
| Clock | `Mon Jun 29 13:15:52 GMT 2026` (build date), `system.ntp.enabled=1` | **Wrong date**; cannot sync without WAN |

### P0.3 Firewall baseline — empirical confirmation of S3.2

Stock `/etc/config/firewall`, read from the device:

```
defaults:   input REJECT   output ACCEPT   forward REJECT
zone lan:   input ACCEPT   output ACCEPT   forward ACCEPT
zone wan:   input REJECT   output ACCEPT   forward DROP   masq 1   mtu_fix 1
forwarding: lan -> wan
```

This matches the firewall4-source analysis in S3.2 line for line, and settles two design questions on evidence rather than inference:

1. **No final drop-all rule exists in stock config, and none is needed** — `defaults.forward=REJECT` renders as nftables `policy drop`. The decision not to port ADR 0110 §4.4 is confirmed correct.
2. **Risk R-3 is real and present**: `zone lan` ships `input ACCEPT`. A matrix modeling only inter-zone forward would leave every router service open to every trusted zone. `zone.input` must be modeled explicitly (A7-M1).

### P0.4 Two new operational findings

**(a) uapi cannot be installed yet — no internet path.** `wan` is NO-CARRIER because the only cable is in LAN2. `uapi` is not installed, and it is not in OpenWrt's official feed (third-party signed feed or a local APK file). So Phase 7 needs one of: WAN cabled to Chateau for internet, the feed plus signing key configured, or the `.apk` sideloaded over SSH. This also blocks NTP, leaving the clock wrong — which matters for token expiry and TLS.

**(b) rtr-slate is a rogue DHCP server on Chateau's LAN right now.** `dhcp.lan` is an active DHCPv4+DHCPv6 server (`start=100`, `limit=150`, `leasetime=12h`, plus RA/SLAAC `managed-config`) bound to `lan`/`br-lan` — and `br-lan` reaches Chateau's main LAN through the LAN2 cable. `/tmp/dhcp.leases` is still empty, so nothing has taken a 192.168.1.x lease yet, but any DHCP client on that segment can win the race against Chateau. IPv6 RA is the sharper edge, since RA has no "first answer wins" arbitration. **Mitigation options:** move the cable to rtr-slate's WAN port (makes it a client, kills the exposure and gives it internet), or disable `dhcp.lan` while it stays on this segment.

### P0.4b Mitigation applied, 2026-10-11 (first write to the device)

Finding P0.4(b) was acted on with operator approval. Applied over SSH:

```
uci set dhcp.lan.ignore=1
uci set dhcp.lan.dhcpv6=disabled
uci set dhcp.lan.ra=disabled
uci delete dhcp.lan.ra_slaac ; uci delete dhcp.lan.ra_flags
uci commit dhcp ; /etc/init.d/odhcpd reload ; /etc/init.d/dnsmasq reload
```

Verified after: `dhcp.lan.ignore='1'`, `dhcpv6='disabled'`, `ra='disabled'`, and **no listeners on UDP 67/547**. Management over SSH unaffected.

Reversal, if the LAN side ever needs to serve clients again: `uci delete dhcp.lan.ignore; uci set dhcp.lan.dhcpv6=server; uci set dhcp.lan.ra=server; uci commit dhcp` plus the two reloads.

This is a hand-applied device change, not topology-driven — it is a safety mitigation for a transient staging cabling, and must either be re-expressed in topology or reverted once rtr-slate's LAN segment is no longer bridged into Chateau's LAN.

### P0.5 Compliance matrix amendment (supersedes the STEP 7 rows)

| Requirement | Previous | Now | Evidence |
|---|---|---|---|
| #1 Device reachable | No | **Yes** | ping/ARP/SSH at 192.168.1.1 |
| #2 OpenWrt ≥ 25.12, apk | Unverified | **Yes** | 25.12.5, apk-tools 3.0.5 |
| #3 `ucode-mod-ubus` | No | **Yes (installed)** | `ucode-mod-ubus-2026.01.16` present |
| #3 `uhttpd-mod-ucode` | No | **Still No** | `uhttpd` and `uhttpd-mod-ubus` installed; `uhttpd-mod-ucode` absent → `apk add` required |
| #4 uapi + token | No | **Still No** | `uapi` not installed; blocked by P0.4(a) |

Class B is no longer wholly blocked: Phase 0 is complete, and Phases 7-9 are now gated only on the package-installation path (P0.4a), not on device recovery.

---

## PHASE 7 EXECUTION RECORD — 2026-10-11 (COMPLETE)

Cabling settled as: **WAN → upstream main router** (`192.168.0.17/24` via DHCP from `192.168.0.1`, default route, internet, DNS), **LAN2 → Chateau** (management over the shared L2 from the laptop's secondary `192.168.1.50/24`). `lan1` unused.

### P7.1 Preconditions closed

| Item | Result |
|---|---|
| Internet / DNS on `wan` | Working (1.1.1.1 at ~17 ms; `downloads.openwrt.org` resolves) |
| Clock | **Fixed** — `sysntpd` restarted, now `Sun Oct 11 13:33 GMT 2026` (was stuck at the Jun 29 build date). This was a genuine prerequisite: `healthz` reports a `time_sync` check, and a past-dated clock breaks TLS validation against feeds |
| `uhttpd-mod-ucode` | **Installed** (`2026.08.24~373145f7-r1`) — closes the last open half of constraint #3 |
| `apk update` | 11226 packages across official + project feeds |

### P7.2 Version correction to the research

| | Earlier research | Actual, verified 2026-10-11 |
|---|---|---|
| uapi backend | v3.0.0 | **v3.1.0** (released 2026-10-11 10:30 UTC) |
| terraform-provider-uapi | v2.3.0 (Terraform Registry, 2026-06-25) | **v3.1.0** (GitHub, 2026-10-11 10:56 UTC) |

The Registry listing was stale. Backend and provider ship in lockstep — 26 minutes apart on the same day — so constraint #5 is satisfied by pinning the provider to **`~> 3.1`**.

### P7.3 Installation — feed, not local APK (deliberate)

Installed from the project's signed apk feed (RSA-4096; key at `/etc/apk/keys/uapi-feed.pub.pem`, feed line in `/etc/apk/repositories.d/uapi.list`):

```sh
uclient-fetch -qO /etc/apk/keys/uapi-feed.pub.pem https://openwrt-iac.github.io/feed/uapi-feed.pub.pem
echo 'https://openwrt-iac.github.io/feed/packages/all/uapi/packages.adb' > /etc/apk/repositories.d/uapi.list
apk update && apk add uapi
```

**The local-APK route was deliberately avoided.** Per upstream's own `installation.md`, `apk add <file>.apk` writes a checksum-pinned entry (`uapi><Q1...`) into `/etc/apk/world`, after which `apk upgrade` silently never moves the version — no error, no mention in output. The feed route keeps upgrade tracking intact (`apk upgrade uapi`). Note also that `apk add uapi` does **not** upgrade an already-installed package on apk-tools 3.0.5; `apk list uapi` is the honest view of what the feed offers.

`curl` is absent from stock OpenWrt — on-device verification uses `uclient-fetch`.

### P7.4 Verified operational

```
GET /api/v3/healthz  ->  { "status": "ok", "version": "3.1.0",
                           "checks": { "ubus": "ok", "uci": "ok",
                                       "lock_dir": "ok", "time_sync": "ok" } }
uhttpd.main.ucode_prefix = '/api/v3=/usr/share/uapi/main.uc'
```

Reachable both on-device and from the laptop over LAN. Authenticated `GET /api/v3/system` returns live UCI data; unauthenticated returns **401**, so auth is enforced.

### P7.5 Token and secret storage

Minted on-device with a source-IP allowlist, per upstream's token guidance:

```sh
uapi-token create --name terraform --scope '*:rw' --allowed-cidr 192.168.1.0/24
```

Name charset is `[A-Za-z0-9_]+` (underscores, not hyphens). The cleartext is printed exactly once and only the salted SHA-256 is stored on the router.

Stored at **`projects/home-lab/secrets/instances/rtr-slate.yaml`** — the per-device secrets file this instance previously lacked entirely — encrypted to **both** age recipients (devkey + masterkey, per `projects/home-lab/secrets/.sops.yaml`), satisfying constraint #12. The cleartext was piped to a scratchpad file and `shred`ed; it was never rendered into the session transcript. Recorded fields: `endpoint`, `token_name`, `token`, `scope`, `allowed_cidr`, `backend_version`, `created_at`.

**Future hardening (not v1):** the provider exposes an ephemeral `uapi_token` resource that mints a short-lived scoped token per run from an admin token. That is the better end state — admin token at rest in SOPS, per-run tokens ephemeral — and supersedes a single long-lived `*:rw` token.

### P7.6 Two corrections to the research, found by probing

1. **`GET /api/v3/whoami` returns `404 not_found`** on 3.1.0. The `uapi_whoami` data source named in the earlier inventory does not correspond to that REST path; the provider-side data source and the REST surface differ here. Any plan step that assumed a `/whoami` preflight must use `/healthz` plus an authenticated resource read instead.
2. **The stock `system` section is anonymous** — its id came back as `cfg01e48a`. This is precisely the case upstream warns about: adopting an anonymous section renames it to a ULID, which **mutates the router**. So Phase 8's adoption ledger must restrict itself to genuinely *named* sections (`lan`, `wan`, `br-lan`, the stock zones, `dhcp_server.lan`) and treat `system` as either left unmanaged in v1 or adopted with the rename accepted explicitly.

### P7.7 Compliance matrix — second amendment

| Requirement | Status now | Evidence |
|---|---|---|
| #1 Device reachable | **Yes** | SSH + HTTPS API from laptop |
| #2 OpenWrt ≥ 25.12, apk | **Yes** | 25.12.5, apk-tools 3.0.5 |
| #3 `ucode-mod-ubus` + `uhttpd-mod-ucode` | **Yes (both)** | installed and verified |
| #4 uapi installed + token minted | **Yes** | `healthz` 3.1.0 all-ok; authenticated read succeeds; 401 unauthenticated |
| #5 Provider/backend version match | **Yes (resolvable)** | both at 3.1.0 → pin `~> 3.1` |
| #12 SOPS-only secrets | **Yes** | `secrets/instances/rtr-slate.yaml`, 2 age recipients, plaintext shredded |

**No Critical requirement is unmet any more.** The earlier "NO VALID SOLUTION for Class B" verdict is lifted: Phases 0 and 7 are done, Phase 8 (adoption ledger and first plan) is now the next executable step, and it depends on Class A work (Phases 1-6), which remains unstarted.

---

## CLASS A / PHASE 1 EXECUTION RECORD — 2026-10-11 (COMPLETE)

First actual model change (SPC STEP 6 entered for Phase 1 scope only, on operator instruction).

### A1.1 What changed

| Change | File |
|---|---|
| New firmware object for the upstream 25.12 (apk) track | `topology/object-modules/software/obj.firmware.openwrt.stock.25_12.yaml` |
| New OS object for the same track (`procd`, `apk`, arm64) | `topology/object-modules/software/obj.os.openwrt.stock.25_12.yaml` |
| New firmware instance with real installed state (25.12.5 / r33051-f5dae5ece4) | `instances/firmware/inst.firmware.openwrt.stock.25_12.yaml` |
| New OS instance (kernel 6.12.94, `embedded_in` the firmware instance) | `instances/os/rtr-slate/inst.os.openwrt.stock.25_12.yaml` |
| `rtr-slate` repointed to the stock track; `observed_runtime` added | `instances/devices/rtr-slate.yaml` |
| Deleted the two orphaned glinet instances (they described firmware no longer installed) | `inst.firmware.openwrt.glinet.4x.yaml`, `inst.os.openwrt.glinet.4x.yaml` |
| `dsa: true` → `dsa: false` with the real nss-dp/edma explanation | `obj.glinet.slate_ax1800.yaml` |
| `software_contract` widened to allow both OS tracks | same |
| Registered `cap.os.init.procd`, `cap.os.openwrt.2512` | `topology/class-modules/capability-catalog.yaml` |

The GL.iNet 4.x **objects** were deliberately kept (A1-M1): they model a valid vendor-firmware track for this hardware, and repurposing an object whose `@title` and `vendor_capabilities` identify it as GL.iNet-specific would violate ADR 0118 D7.

### A1.2 Verification

```
compile-topology.py                -> 0 errors, 1 warning (the pre-existing W7016)
check-capability-contract.py       -> OK, 0 warnings  (was 2 before registration)
validate-v5 lane                   -> PASS on every step, incl. ADR0088 governance
targeted pytest (61 tests)         -> all pass
objects 140 -> 142, instances unchanged at 189
```

`task build:sync-lock` and `task framework:lock-refresh` were both run (CORE-005).

### A1.3 Three findings produced by doing the work

1. **`firmware_obj_ref` is enforced by nothing.** `os_obj_refs` is a real allow-list with diagnostic `E7842`; `firmware_obj_ref` is read by **zero lines** of the runtime and is singular, so it cannot express "either of two tracks" the way the OS side can. It now names the track actually installed rather than a permitted set. Closing this asymmetry — a list plus an enforcing validator on the firmware side — is a separate change.

2. **Capability derivation emitted two identifiers that the catalog did not contain** (`cap.os.init.procd` from `init_system`, `cap.os.openwrt.2512` from `release`), surfacing as four `W3201` warnings. These were **registered in the catalog** rather than absorbed by the `W3201` budget, because ADR 0118 rev 3.2a holds the capability vocabulary closed: an identifier that reaches runtime unregistered is *unverified*, not merely untidy. Leaving them as warnings would have quietly spent 4 of the 10-warning allowance on a fact that was trivially expressible.

3. **`tests/test_framework_lock_matches_content.py` earned its keep.** It failed with "these files are inside the framework integrity hash and are not in git, so a clean checkout cannot reproduce the lock", naming both new object files before they were staged. The lock and the git index have to move together; the test is what makes that non-optional.

Separately, the `dsa` field turned out to be documentation-only — consumed by zero plugin lines and present in exactly one file — so correcting it carried no behavioural risk.

### A1.4 Deliberately not done in Phase 1

`rtr-slate` has **no network/zone/DHCP intent** authored yet. That is not an oversight: zone layout, VLANs, SSIDs and inter-zone policy are design decisions about what this router should *do*, and inventing them would put unreviewed intent into the model. `observed_runtime` records what the device currently *is*; intent comes next and needs an explicit decision about the device's role.

---

## WIRELESS RESEARCH — 2026-10-11, AND A CORRECTION TO S3.5

A dedicated research pass against firewall4/netifd/wifi-scripts source, the OpenWrt issue tracker and wireless-regdb. **It overturns the premise S3.5 was built on.**

### W1. Correction: the 2.4 GHz radio is not broken

S3.5 reported "2.4 GHz radio reports `Not supported (-95)`… expect persistent plan diffs or false-healthy reads" and concluded wireless should be excluded from v1 partly for that reason. That conclusion was wrong, and the mechanism is now known:

- The `-95` lines are **cosmetic log noise**. The ucode wifi-scripts path calls `iw phy <phy> set antenna` and `set distance` unconditionally with no stderr redirect; the legacy shell path had `>/dev/null 2>&1`, and `WIFI_SCRIPTS_UCODE` is `default y`. ath11k defines no `set_coverage_class` op, so `set distance` is *guaranteed* `-EOPNOTSUPP`. Silenced on main by commit `e21a4ef958` (2026-09-02); the `openwrt-25.12` branch copy was last touched 2025-12-27, so 25.12.5 is still noisy. **No UCI setting suppresses it** — expect two lines per `wifi reload` and ignore them.
- The real causes behind "Device is not active" in those reports: `start_disabled=1` semantics (see W4), **both reporters had two STA interfaces on one phy** — violating the `#{ managed } <= 1` the phy advertises — and missing `iwinfo`/`rpcd-mod-iwinfo`, without which LuCI cannot read radio state at all.
- **The beacon-loss/crash defect is already fixed in this build.** Commit `a62b5fe71c` ("ath11k: fix for unsupported 11ax EDCA") forces `WMI_WMM_PARAM_TYPE_LEGACY`; previously the firmware asserted on *every STA association*. Corollary: `he_mu_edca_*` knobs are inert.

### W2. Two settings that are mandatory, not optional

| Setting | Why |
|---|---|
| `option country` on any device carrying a 5 GHz AP | Regdomain `00` marks every 5 GHz range `NO-IR` in wireless-regdb, so the AP **never beacons**. |
| `option channel 'auto'` on any radio carrying a `mode sta` | A numeric channel makes netifd emit `fixed_freq=1` plus that one frequency to wpa_supplicant; the STA can then never associate off-channel. |

### W3. Folklore, named as such

`cell_density` and `legacy_rates` only rewrite `supported_rates`/`basic_rates` in hostapd config — they cannot reach the driver, so stability claims for them are unfounded. `background_radar` is a no-op (no `RADAR_BACKGROUND` in ath11k). `noscan` is auto-forced whenever a non-AP interface shares the radio. No ath11k evidence was found for `disassoc_low_ack`, `mu_beamformer` or `he_bss_color`.

Also a correction to my own earlier reading: **"STA/AP BI must match" refers to your own APs on one phy sharing `beacon_int`** (a wifi-device option, therefore automatic) — not to matching the upstream AP's beacon interval. `cfg80211_wdev_bi()` returns 0 for STA wdevs.

### W4. AP+STA on one radio — the decisive mechanism

Read from source, and it changes the radio plan:

- Any `sta`/`mesh`/`adhoc` interface on a phy sets `ap_start_disabled`, so hostapd receives `start_disabled=1`: **APs on that phy do not beacon until the STA associates.**
- wpa_supplicant then drives hostapd over ubus `apsta_state`: `DISCONNECTED|AUTHENTICATING|SCANNING` → `up:false` → `iface.stop()`, which **takes the APs down and deauths their clients**; `COMPLETED` → `iface.start(freq)` on the STA's frequency; an upstream CSA → `iface.switch_channel()`.

So the channel does follow automatically — at the cost of dropping every client on each uplink scan or roam. For a router whose job is to keep clients served in a hotel, that coupling is the problem, not the single-channel limit.

A `wifi-iface` with `disabled '1'` is dropped at parse time, so a parked section costs nothing.

### W5. Resulting radio assignment (inverts the S3.5 plan)

**All APs on `phy0` (5 GHz); the STA uplink on `phy1` (2.4 GHz); a parked `disabled='1'` STA on `radio0` for 5 GHz-only venues.**

`phy0` stays STA-free and therefore always beacons — no `start_disabled`, no apsta stop/start. That is worth more than `phy1`'s reputation, and a 2.4 GHz STA is usable on 25.12.5 precisely because the EDCA assert that killed STA mode is fixed. Enabling the parked 5 GHz STA knowingly converts `radio0` to apsta with the W4 coupling; it is a venue-specific fallback, not the standing config.

### W6. The one defect that is real and unfixed: the ath11k memory leak

Both upstream fixes (PR #24254 per-ring `page_frag_cache` isolation, PR #21495) are **open**. No usable module parameter exists. Measured upstream: ~7-8 MB/h; `wifi down` frees nothing, `rmmod ath11k` reclaims ~205 MB; kernel 6.12.94 stretched time-to-OOM from ~1 h to 3-9 days without fixing it. Leak rate tracks cumulative RX churn rather than client count, so **fewer live SSIDs and radios is itself a mitigation**.

Mitigation is a `MemAvailable`-threshold watchdog performing an ath11k **module reload** rather than a reboot. Architecturally this is an OS/runtime concern and therefore **Ansible-owned, not Terraform-owned** (ADR 0119 D6 keeps Terraform on infrastructure and Ansible on OS/service/runtime); it must not be smuggled into the uapi generator.

### W7. travelmate is rejected, with reasons

The package is maintained (2.4.9-4, 2026-10-08) and present in the 25.12 apk repo, but it manages WiFi by `uci_set` + `uci_commit` on `wireless` and `dhcp`, adds `rebind_domain` entries, and needs `iwinfo`/`rpcd-mod-iwinfo`. Against a declaratively rendered box it would race the generator and cause flash wear — a second writer for resources that already have one (ADR 0119 D6). Rejected.

The netifd-only pattern replaces it: one `mode sta` interface on `radio1` → `network wwan` (`proto dhcp`), `channel auto`, a dedicated `wwan` firewall zone (`input REJECT`, `masq 1`, forwarding only *from* client zones, never *into* them), and **`option rebind_protection '0'`** in `/etc/config/dhcp` so a captive portal answering with RFC1918 addresses is not rebind-filtered. Also required: install `iwinfo` + `rpcd-mod-iwinfo`, or every radio reading is untrustworthy.

Independently, this confirms the addressing choice below: hotels are overwhelmingly `192.168.1.0/24`, which is exactly OpenWrt's default LAN.

---

## AGREED INTENT — ROAD-WARRIOR DESIGN

Role, confirmed by the operator: road-warrior travel router with a trusted connection to the home network, several country exits, used in hotels and public venues, with Chateau remaining the home hub.

### D1. A security finding that had to be settled first

The operator asked for the hotel WiFi to sit **outside the perimeter, modeled in the security matrix as an untrusted channel that merely provides internet**. Mapping it to `inst.trust_zone.untrusted` (level 0) exposes a hole in the implemented legacy profile. For a country SSID in `inst.trust_zone.vpn_tunnel` (level 2, `isolated: false`):

```
R6 override?  none
R1 same zone? no
R2 isolated?  vpn_tunnel.isolated = false -> does not apply
R3 downhill?  2 > 0  ->  ALLOW      <- direct leak into the hotel network
```

Putting the country zones in `vpn_exit` (level 1, `isolated: true`) does not help: R2 denies isolated zones everything *except* `untrusted`, and `untrusted` is precisely what must be denied here.

On Chateau this never mattered — there `untrusted` is the WAN and direct egress is the intent. On a travel router the semantics invert: direct egress to the local network is the one thing that must be impossible. **ADR 0118 D4.1 anticipated exactly this**: its translation table renders R3 as "**Nothing. Trust level is not authorization**" in the strict profile. The strict profile would be fail-closed; the profile actually running today is fail-open. rtr-slate is the first device in this lab where that difference is a concrete vulnerability rather than a note in an ADR.

Resolution: an explicit **R6 `policy_override` with `action: drop`** (R6 is evaluated first and short-circuits). On OpenWrt this lowers to **omitting the `firewall_forwarding` object** — the kill switch becomes the absence of a permit, fail-closed by construction, with no rule ordering involved. `E9906` is the validator that holds this.

### D2. Mode switching without runtime state

The operator wants full-tunnel as the default with the option to switch to split tunnel at will. A runtime toggle (script or `uci set` over SSH) is rejected: it creates a second writer, and Terraform would revert it as drift on the next apply (ADR 0119 D6). A topology field plus `apply` is declaratively correct but unusable from a hotel room.

**The mode is selected by which SSID the client joins.** Both modes are permanently declared, so there is no state to drift:

| SSID | Zone | forward → | Client sees |
|---|---|---|---|
| `Slate-Home` | `user` (3) | `wg-home` only | everything tunneled; home subnets plus internet via Chateau's Estonian exit |
| `Slate-Split` | `travel_split` (3, new) | `wg-home` + `untrusted` | home via tunnel, internet direct through the venue |

This is the same device-language the lab already uses — `VPN-Russia` versus `VPN-Sweden` are modes selected by SSID. Two zones rather than one with policy routing is forced by the firewall: one may forward to `untrusted` and the other must not, and in a zone-based firewall policy lives on the zone pair. Being two zones at the same level also means R5 denies traffic between them, so a split-mode laptop cannot reach a full-tunnel phone.

Fail-closed behaviour becomes visible rather than silent: if the tunnel is down, `Slate-Home` has no internet at all, and moving to `Slate-Split` is a deliberate act instead of an unnoticed fallback.

### D3. Zones

| Interface / SSID | Trust zone | forward → | Purpose |
|---|---|---|---|
| STA uplink (`wwan`) | `untrusted` (0) | — | venue internet, outside the perimeter |
| `Slate-Home` | `user` (3) | `wg-home` | home LAN + servers + management, as on Chateau |
| `Slate-Split` | `travel_split` (3) | `wg-home`, `untrusted` | split mode |
| `VPN-Germany` | `vpn_tunnel` (2) | `wg-de` | R6 drop → `untrusted` |
| `VPN-Russia` | `vpn_tunnel` (2) | `wg-ru` | R6 drop → `untrusted` |
| `VPN-Sweden` | `vpn_tunnel` (2) | `wg-se` | R6 drop → `untrusted` |
| `Guest` | `guest` (0) | `untrusted` | venue internet, deliberately untunneled |

`zone.input` is declared explicitly for every zone (`E9907`): stock OpenWrt ships `lan` with `input ACCEPT`, which would expose SSH and the uapi endpoint to every client. Captive-portal authentication lives in the `untrusted` zone and is reachable by the router itself, never by client zones — the router's own egress is unavoidably "split", since tunnels cannot be established otherwise.

### D4. Addressing

Default `192.168.1.0/24` is abandoned — it is the most common hotel LAN there is. Third octet mirrors Chateau's VLAN ids to keep cognitive load low (ADR 0043):

```
10.77.1.0/24    Slate-Home
10.77.2.0/24    Slate-Split
10.77.20.0/24   Guest         (<-> Chateau vlan 20)
10.77.55.0/24   VPN-Germany   (<-> 55)
10.77.57.0/24   VPN-Russia    (<-> 57)
10.77.58.0/24   VPN-Sweden    (<-> 58)
```

### D5. Tunnels — one WireGuard interface per country, routed, no SNAT

Operator's choice. Because this is a router and not a client, client subnets are **routed** through their tunnel rather than SNATed to a single address: the client source IP survives to Chateau, which keeps per-client policy possible at home and keeps the address domains meaningful. Chateau's existing `rw_russia`/`rw_sweden` policies generalise from a `/32` match to a subnet match — one step, no new mechanism.

| Interface | Tunnel IP | Mode | Advertises | MTU |
|---|---|---|---|---|
| `wg-home` | **10.100.0.4** (already allocated in `inst.tunnel.wg-home-to-oci`) | split to home | 10.77.1.0/24, 10.77.2.0/24 | 1420 |
| `wg-de` | 10.100.1.10 | `direct` — exits at the VPS | 10.77.55.0/24 | 1420 |
| `wg-ru` | 10.100.1.11 | `chained` → Chateau → `wg-awg-russia` | 10.77.57.0/24 | ~1340, **measure** |
| `wg-se` | 10.100.1.12 | `chained` → Chateau → `wg-awg-sweden` | 10.77.58.0/24 | ~1340, **measure** |

AmneziaWG stays at home: it is **not available in the configured feeds for this target** (`apk list | grep amnezia` → empty; only `kmod-wireguard` and `wireguard-tools`), a third-party kmod would be pinned to kernel 6.12.94, and a device that travels should not carry the country credentials at all.

Each interface needs the existing IPv6-blackhole pattern (`fd00::N/128` plus `::/0`), or the venue's RA will route traffic around the tunnel. Nested MTU is an estimate until measured with DF pings; `mtu_fix` clamps TCP MSS only, so QUIC blackholes rather than degrading (`W9902`).

Neighbour changes required: one peer per interface on the VPS with matching `AllowedIPs`, and subnet-matching `rw_*` policies on Chateau.

### D6. Second enforcer, and the W7016 retirement path

`inst.security_matrix.rtr_slate` — `managed_by_ref: rtr-slate`, `enforcement_plane: perimeter`, one matrix per enforcer (ADR 0110 M1-B), with `availability_requirements: []` plus an `availability_waiver` so it does not reproduce the two `W7002` warnings Chateau's matrix had to resolve. This is what `W7016` has been pointing at all along.

Modelling note worth recording so nobody hunts for absent 802.1q tags: on Chateau an `inst.vlan.*` is realised as a tagged bridge VLAN; on rtr-slate the same instance type will be realised as an **untagged per-SSID interface**, because a travel router needs no trunking. That is legitimate under ADR 0110 ("the adapter translates intent to platform-specific implementation"), but it makes `vlan_id` nominal on this device.

### D7. SSID budget is a memory-leak mitigation, not aesthetics

Given W6 — leak rate tracks cumulative RX churn — the standing configuration keeps three SSIDs live (`Slate-Home`, `Slate-Split`, and one country as needed). `VPN-Germany`, `VPN-Russia`, `VPN-Sweden` and `Guest` are declared with `enabled: false` and switched on when wanted; parse-time dropped sections cost nothing. Six concurrent BSSIDs on a single congested hotel channel would also spend real airtime on beacons.

---

## CLASS A / PHASE 2 EXECUTION RECORD — 2026-10-11 (COMPLETE)

Governance before code, as the plan sequenced it.

### A2.1 Diagnostic family allocated: `E99xx` / `W99xx`

Band choice was **measured**, following this catalog's own rule that a range map which does not describe the system cannot be used to pick a free number. Distinct codes seen across source, catalog and the frozen ledgers:

| Band | 90 | 91 | 92 | 93 | 94 | 95 | 96 | 97 | 98 | 99 |
|---|---|---|---|---|---|---|---|---|---|---|
| Codes | 3 | 4 | 7 | 17 | 11 | 5 | 4 | **41** | 15 | **0** |

`E97xx` is what the reserved-family sequence suggests and is the most crowded band in `E9xxx` (`docs_generator`, `initialization_contract_validator`, plus `E9700..E9761` in the frozen unregistered ledger). `E99xx` was empty and was taken. A notable incidental finding: the MikroTik generator's own `E92xx` codes are **not in the catalog either** — they are part of the 274-code unregistered debt.

**14 codes registered** in `topology-tools/data/error-catalog.yaml`, each naming its future raiser in a comment so an allocation with no raiser stays auditable — the discipline `AWAITING_A_MOUNT` enforces for `E70xx`, applied by hand because `E99xx` falls outside `NETWORK_MODEL_RANGE` and that ledger does not see it. Every rule encodes a verified fact rather than a guess:

| Code | Encodes |
|---|---|
| `E9901` | projection contract defect (StrictUndefined templates) |
| `E9902` | overlapping match tuples — uapi exposes **no** ordering control anywhere in its OpenAPI spec, so disjointness *is* the ordering contract |
| `E9903` | match arity: list on `firewall_rule`, scalar on `redirect`/`nat`; wrong arity makes fw4 drop the whole section silently |
| `E9904` | generation would mutate the management path — a stranding write never returns, so Terraform records nothing |
| `E9905` | interface in no zone (zones match `iifname`; `uapi_firewall_zone` has no `device`/`subnet`) |
| `E9906` | **kill switch** — tunnel-only zone with a forwarding to an uplink zone (the D1 finding) |
| `E9907` | zone input policy left implicit (stock `lan` is `input ACCEPT`) |
| `E9908` | wireless `country` unset → 5 GHz AP never beacons (regdom `00` is `NO-IR`) |
| ~~`E9909`~~ | **withdrawn 2026-10-12, never fired.** Claimed a numeric channel on a station radio emits `fixed_freq=1`. False on 25.12: `wpa_supplicant_set_fixed_freq` is reached from the `adhoc`/`mesh` branches only, and `mac80211_setup_supplicant` passes an explicitly empty frequency for `mode=sta`. Replaced by `W9904`; number not reused |
| `E9910` | two STA interfaces on one radio → violates `#{ managed } <= 1` |
| `W9901` | AP shares a radio with an STA → APs stop on every scan/roam |
| `W9902` | client MTU exceeds the nested tunnel budget → QUIC blackholes |
| `W9903` | adoption target is an anonymous section → adoption renames it, mutating the router |
| `W9904` | channel declared on a station-bearing radio is not honoured (replaces `E9909`) |

The allocation and its justification are documented in `docs/diagnostics-catalog.md`.

### A2.2 Capability registered, deliberately not wired

`cap.firewall.security_matrix.openwrt` added to `topology/class-modules/capability-catalog.yaml` (experimental, vendor `openwrt`, ADR 0110). It is **not** added to `_ENFORCER_ADAPTER_BY_TYPE` in `effective_model_compiler.py`: an adapter identifier that resolves with no generator behind it is a false claim of coverage under ADR 0119 D1.1. The mapping and the `W7016` allowlist entry are retired together in Phase 6, and the catalog entry carries a comment saying so.

### A2.3 Verification

```
pytest tests/test_diagnostic_code_registry.py   -> 11 passed
check-capability-contract.py                    -> OK, 0 warnings
compile-topology.py                             -> 0 errors, 1 warning (pre-existing W7016)
validate-v5 lane                                -> PASS on every step
```

---

## CLASS A / PHASES 3-6 EXECUTION RECORD — 2026-10-11 (COMPLETE)

The pipeline now runs end to end: topology compiles, the matrix lowers, four
validators gate it, and Terraform is rendered. **Compile is at 0 errors and
0 warnings** — the first time in this work, and `W7016` is gone legitimately
rather than allowlisted.

### A3-6.1 What exists

| Plugin | Stage | Role |
|---|---|---|
| `object.openwrt.compiler.zones` | compile | Lowers each enforcer's composed matrix into zone intent: per-zone input/forward policy, derived input services, forwardings to emit, denied pairs as recorded omissions |
| `object.openwrt.validator_json.zone_plan` | validate | `E9906` a denied pair must not reappear as a forwarding; `E9907` zone input must be explicit and never ACCEPT |
| `object.openwrt.validator_json.wireless` | validate | `E9908` 5 GHz AP without country; `E9910` two stations per radio; `W9901` AP sharing a radio with a station; `W9904` channel declared on a station-bearing radio is not honoured |
| `object.openwrt.validator_json.interfaces` | validate | `E9905` interface in no rendered zone; `E9904` management path unprotected |
| `object.openwrt.generator.terraform` | generate | provider wiring + the firewall zone graph |

Output on the real topology: 7 zones, 14 forwardings, 32 denials as omissions,
3 permits deferred with their reason reported.

### A3-6.2 Five traps found by building it

1. **Object-module plugins are not auto-discovered.** `topology/module-index.yaml`
   is an explicit allowlist; a manifest on disk without an entry fails discovery
   with `E4001` plus three cascading `E8003`s.
2. **The effective-model row shape.** Authored values live in `instance_data`;
   the sibling `instance` block carries lineage metadata with the same field
   names absent. Reading the wrong one produced a plan with zero segments and
   zero forwardings **at 0 compile errors** — a green build with empty output.
   The `I9902` diagnostic is what surfaced it.
3. **Tunnel interfaces shared a zone with the client segments they serve.**
   Client-to-tunnel traffic would then be intra-zone, which `forward: REJECT`
   denies, so the country SSIDs would have had no internet with the firewall
   working exactly as configured. Fixed by moving them to `vpn_exit`, which
   forced three further R6 overrides that were genuinely missing.
4. **`E9394` and the artifact-contract guard.** A migrated generator must
   publish the whole contract *and* be listed in
   `base.assembler.artifact_contract_guard`'s consumes — the guard reads each
   generator through its own declared channels, so publishing alone is not
   enough.
5. **`uapi_firewall_zone.network` names uci sections, not topology instances.**
   The first render emitted `inst.vlan.slate_guest`, which would have
   referenced a section that does not exist.

### A3-6.3 Phase 6: the adapter, retired as designed

`cap.os.openwrt → cap.firewall.security_matrix.openwrt` is now in
`_ENFORCER_ADAPTER_BY_TYPE`, and the `W7016` allowlist entry is removed. This is
exactly the sequencing the 2026-10-09 decision committed to: the adapter was
withheld while nothing could render its result, because an adapter resolving
with no renderer behind it is a false claim of coverage (ADR 0119 D1.1). The
zones compiler's transitional selector — OS family plus enforcer type — was
replaced by the precise one, selection by resolved adapter, as the MikroTik
compilers do.

Two consequences handled rather than ignored: two tests in
`test_effective_model_compiler.py` had used `cap.os.openwrt` precisely *because*
it was the OS family with no adapter, so they were repointed at `cap.os.debian`
to keep testing the zero-adapter path they describe; and the comment asserting
one family per enforcer type is now false, so it was corrected — `W7017`
(ambiguous adapters) became reachable in principle, though no real device
declares both families.

### A3-6.4 Still open

`E9902`, `E9903` and `W9903` have no data to check: they cover generated
`firewall_rule` sections and import blocks, neither of which exists yet. The
remaining generator work is interfaces, wireless and DHCP templates, the
port-scoped permits that need rule sections, and the adoption ledger. Phases 8-9
(adoption, guarded apply) remain gated on that.

> Superseded 2026-10-12 for `E9902`/`E9903`: rule sections now render, and both
> codes are implemented. See A7 below. `W9903` is still unexercised.

---

## POLICY-OVERRIDE COLLISION — 2026-10-12

A matrix resolves at most one override per zone pair: `_find_policy_override`
returns the first match. An override authored on a shared *object* therefore
competes with every instance that declares one for the same pair, and one of the
two is discarded with no diagnostic. Both instances extending
`obj.network.security_matrix.soho` were in that state for the `user -> servers`
pair, and they lost opposite halves — Chateau kept only its own db ports,
rtr-slate kept only the object's `80,443`. Same authoring shape, opposite
survivors, silent in both directions.

Resolved by collapsing each colliding pair to one explicit override first, then
making the collision blocking:

1. `obj.network.security_matrix.soho` declares `policy_overrides: []`. ADR 0118
   D7 is directly about this: an object supplies reusable shape and defaults and
   must not author a value that decides one concrete entity's policy, because it
   serves many instances and can hold only one such value.
2. Chateau keeps its own port set verbatim; rtr-slate takes the union
   (`80, 443, 5432, 6379`), justified because it is staged and unapplied — there
   is no live behaviour to preserve and both sets were authored deliberately.
3. `E7065` refuses a pair claimed twice. It compares pairs on the trailing
   segment, the same equivalence the selector uses, because stricter comparison
   would miss precisely the object/instance cross-level collision that motivated
   it.

**A third defect, found while proving step 1 safe.** The rendered diff for
Chateau dropped exactly one resource,
`zone_override_user_to_servers_http_tcp`, whose match referenced
`src_address_list = "zone-obj_network_trust_zone_user"` and
`dst_address_list = "zone-obj_network_trust_zone_servers"`. The only address
lists ever *defined* are `zone-guest`, `zone-iot`, `zone-management`,
`zone-servers`, `zone-user`, `zone-vpn_exit`, `zone-vpn_tunnel`. The
`zone-obj_network_*` lists were never defined, so that rule matched nothing on
the live router. An object-level override renders against unresolved *object*
zone refs and is inert wherever it lands: it had the shape of a grant and the
effect of nothing, and reviewing the rendered config would have shown a permit
that was not in force. Removing it is therefore provably behaviour-preserving
for the live perimeter, and it also removes a rule that falsely appeared to grant
users 80/443 to servers. `obj.network.security_matrix.proxmox_servers` was
checked and already declares none.

---

## A7. RULE-PLAN VALIDATORS — 2026-10-12

`object.openwrt.validator_json.rule_plan`, order 153, consuming `openwrt_zones`
optionally for the same reason its siblings do.

**E9902 — match tuples in one chain must be disjoint.** uapi exposes no ordering
control (no `position`, `index` or `place_before` anywhere in its OpenAPI
surface) and Terraform creates independent resources in parallel, so the order
sections land in a chain is not something this repo can specify. A chain must
therefore be an unambiguous specification on its own. Two cases are refused:
opposing targets, where enforcement depends on an order nothing controls, and
identical tuples, where two Terraform resources claim one uci section. A
narrower tuple inside a wider one with the *same* target is redundant but
unambiguous and is allowed — erroring there would refuse a plan that enforces
exactly what it says, which is how a disjointness check becomes a false-positive
generator.

Overlap is computed rather than compared. Port sets intersect as sets, but
destination prefixes are compared as networks: `10.0.0.0/8` and `10.77.1.0/24`
overlap without being equal, and string equality would miss exactly the case
that matters. The catalog hint was widened to match, which is legitimate because
nothing had yet emitted the code — the entry was a reservation, not a release.

**E9903 — each field must carry the arity it renders at.** The provider is
asymmetric: on `uapi_firewall_rule`, `src_zone`/`dest_zone` are strings while
`proto`/`dest_port`/`dest_ip`/`src_ip`/`src_port` are lists; on redirect and nat
the match fields are scalars and only `proto` stays a list. Wrong arity is not a
type error — fw4 drops the entire section and says nothing, so the rule silently
does not exist while Terraform reports success.

The renderer reaches that arity by iterating what the plan hands it, which makes
a scalar where a list belongs worse than a mismatch: `ports: {tcp: "80"}`
iterates the string and renders `dest_port = ["8", "0"]` — a syntactically valid
section matching two absurd ports. An arity finding suppresses the disjointness
report for that enforcer, because flattening a wrong-arity rule would compare
tuples the renderer would never produce.

### A7.1 Provider schema, read before authoring templates

Exact attribute names and types, from the provider's own docs rather than
inferred. Three facts change the design:

| Resource | Shape that matters |
|---|---|
| `uapi_network_interface` | `proto` required; `ipaddrs` is a **list**, `ipaddr` is **read-only**, `netmask` a scalar; `device` a scalar; `private_key` sensitive; `listen_port` for WireGuard. **No `ports`** — bridge membership is not here |
| `uapi_network_device` | `name` required; `ports` is a **list**, plus `type`, `mtu`, `macaddr`, `vid`. This is where `br-lan`'s `lan1`/`lan2` go |
| `uapi_wireless_device` | `type` required; `channel` is a **Number**; `band`, `country`, `htmode`, `txpower`, `disabled`. **No `hwmode`, no `path`, no `noscan`** — the radio's identity is the uci section name, i.e. `id` |
| `uapi_wireless_interface` | `device` required; `network` is a **scalar string**, not a list — one network per SSID; `mode`, `ssid`, `encryption`, `key` (write-only), `isolate`, `hidden`. **No `country`** (device-level), no `bssid`, no `wds` |
| `uapi_dhcp_server` | `interface` required; `start`/`limit` Numbers, `leasetime` a string. **No `end`** — an authored `dhcp_range: "a-b"` must be lowered to `start` + `limit`, with the off-by-one that implies |
| `uapi_network_wireguard_peer` | `allowed_ips` (list), `interface`, `public_key` required; `endpoint_host`/`endpoint_port`, `persistent_keepalive`, `route_allowed_ips`, `preshared_key` write-only |

**`channel` is typed Number, so the string `auto` is not renderable.** netifd
settles what to emit instead: `_wdev_prepare_channel` matches `""|0|auto` and
sets `channel=0; auto_channel=1`, so `0` is an exact synonym for `auto` and is
the only spelling the provider can carry.

### A7.2 E9909 was wrong, and is withdrawn

Checking the above against the 25.12 source refuted one of this repo's own
rules. E9909 said a numeric channel on a station-bearing radio makes netifd emit
`fixed_freq=1` to wpa_supplicant, stranding the station on one frequency. The
source says otherwise:

* `wpa_supplicant_set_fixed_freq` is called from exactly two places in
  `hostapd.sh`, the `adhoc` and `mesh` branches of `wpa_supplicant_add_network`.
  Never from the `sta` branch.
* `mac80211_setup_supplicant` makes that explicit:
  `if [ "$mode" = "sta" ]; then wpa_supplicant_add_network "$ifname" "" "$htmode"` —
  the frequency argument is deliberately **empty** for a station.
* `scan_list` → `freq_list` is an independent uci option
  (`config_add_array scan_list`), unrelated to `channel`, so a pinned channel
  does not narrow the station's scanning either.

A pinned channel on such a radio is therefore *ignored*, not harmful: the phy
operates on whatever channel the station associates to, and any AP on that phy
is `start_disabled` until then and follows it (which is W9901, and is correct).
That makes the rule a warning about a declaration that will not be honoured, not
an error — so E9909 is withdrawn, the number is not reused, and `W9904` carries
the corrected meaning.

The check also had a second, independent defect that the schema work exposed: it
accepted only the literal string `auto`, so it would have fired on `channel: 0`
and on an absent channel — the two other spellings netifd treats identically,
one of which is the only renderable one. `_is_auto_channel` now mirrors netifd's
case statement.

This is the same defect family as the three found in the override work: a rule
that reads as enforcement and is not grounded in what the target actually does.
Authoring it from the issue tracker and release notes rather than from
`hostapd.sh` is what let it through.

Stale raiser annotations in the catalog were repointed while registering these:
`E9903`/`E9902`, `E9904`/`E9905` and `E9908`-`W9901` named
`base.validator.openwrt_*` plugins that do not exist — the checks live in the
object-scoped `object.openwrt.validator_json.*` plugins. `W9902` is annotated as
belonging to a compiler not yet implemented.

**Verification.** 24 tests, 22 synthetic violations plus two driving the real
compiler — the latter assert the rule list is non-empty before asserting it is
clean, so passing is not an artifact of empty data. Execution on real data was
proven by mutation: injecting a raise into the per-enforcer loop collapsed the
whole compile to one error. `compile-topology.py` 0 errors / 0 warnings,
`validate-v5` PASS.

---

## Findings requiring separate attention

1. **ADR 0110 models only inter-zone forward policy.** On any default-deny-per-zone backend (OpenWrt/firewall4), omitting `zone.input` leaves the router's own services reachable from every zone it trusts. This is a gap in the *architecture*, not in the OpenWrt adapter, and should be raised against ADR 0110 independently of this work.
2. **`obj.glinet.slate_ax1800.yaml` declares `dsa: true`** on all three ethernet interfaces. The ipq60xx data path is nss-dp/edma with three independent netdevs and no `eth0`; the flag is incorrect.
3. **ADR 0110's §1.4 adapter table predicted a "uci provider"** for OpenWrt. `terraform-provider-uapi` is a REST-over-ubus/uci realization of exactly that slot — the prediction holds, with the caveat that the resource model is zone-centric, not address-list-centric, so the MikroTik lowering does not transfer.
4. **Chateau live drift vs. topology** (observed 2026-10-11 while locating rtr-slate; none of it changed by this analysis):
   - `ether3` has `pvid=99` but no VLAN 99 membership — the misconfiguration that silently dropped all of rtr-slate's traffic. Per-port PVID is not modeled in topology at all, so this cannot currently be expressed or corrected through the pipeline.
   - RouterOS is `7.24.5`; `rtr-mikrotik-chateau.yaml`'s `observed_runtime.routeros_version` records `7.23.3`.
   - Containers bridge holds `veth1` + `veth-transmission`; topology declares `veth_ports: [veth1, veth-awg-ru, veth-awg-se]`.
   - Bridge port list contains an unnamed `*3` entry.

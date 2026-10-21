# ADR 0120: Device Configuration Provenance and Ownership

- Status: Partially Implemented
- Scope note: option A implemented 2026-10-21; options B, C and D are planned in the implementation plan below
- Date: 2026-10-21
- Related: ADR 0055 (manual Terraform extension layer), ADR 0074 (generator determinism),
  ADR 0080 (unified build pipeline), ADR 0083 (node initialization, drift vocabulary),
  ADR 0091 (readiness evidence, `drift-report.json`), ADR 0103 (runtime reconciliation status
  — D2–D12 cancelled), ADR 0105 (device state commit/rollback — Deferred),
  ADR 0110 (zone/VLAN mechanism), ADR 0115 (hash-based deploy idempotency — Proposed),
  ADR 0119 (firewall rule ordering contract — Accepted, not implemented)
- Analysis: `docs/reports/2026-10-21-device-config-ownership-spc.md` (SPC steps 0–5)
- Evidence: `docs/reports/2026-10-21-chateau-dead-rules.md` (the live audit this rests on)

---

## Context

The project's purpose is repeatable device configuration derived from topology.
Three things are needed for that and only two exist.

**What exists.** Topology declares intent, generators render it, Terraform
applies it and records what it created.

**What does not.** Nothing states which objects on a device the project claims.
Ownership lives implicitly in two places that were never meant to carry it: a
free-text `comment` substring on the device, and Terraform's private state file.
There is nothing to join them against, so the question "what on this device is
ours, and what is garbage" has no mechanical answer.

### The measurements that forced this

Read-only, against `rtr-mikrotik-chateau` on 2026-10-21, with state serial 912:

| | |
|---|---|
| live objects across ten resource families | 314 |
| tracked by Terraform state | 162 |
| **carrying our own marker, unknown to Terraform** | **98** |
| unmarked and unknown (vendor `defconf`, manual, hand-made) | 46 |
| firewall-filter rules below the chain's terminal drop | 63, all at 0 packets, **none** Terraform-owned |

`terraform plan` compares intent with Terraform's *memory*, never with the
device, so a plan reporting "no changes" coexisted with all of it. Two of
ws-nixos' WireGuard country exits were unable to pass a packet for an unknown
period: their Chateau-side rules existed only as hand-made rules placed below
the terminal drop, while the declaration that should have produced them sat in
`inst.tunnel.wg-exit.chateau_routing` — written in the generators' own
vocabulary and read by no plugin.

Three distinct defect shapes, each invisible to every gate in the pipeline:

1. ownership not representable, so garbage not definable;
2. a rendered permit whose device *position* nothing checks;
3. a configuration-shaped declaration that nothing consumes.

### Why this is not simply ADR 0103 again

ADR 0103 designed the reconciler (D2.1) and the CLI (D2.2) and cancelled both on
2026-06-18, stating that "`terraform plan` already solves drift detection for
this single-operator home-lab" and that there was "no risk from cancellation".
The measurements above falsify both claims, and a third ("a single operator knows
what is deployed because they deployed it") did not survive contact with the
device either. The cancellation is not reversed wholesale — its cost argument
against a dual-mode architecture still stands — but its premise is corrected
here, with numbers.

---

## Decision

### D1. Provenance is a property every managed device object carries

Every object on a managed device belongs to exactly one provenance class, and
the class must be readable **from the device itself**, not only from the
repository:

| Class | How the device says so |
|---|---|
| `topology` | the canonical marker in its comment |
| `manual` | the manual marker, with owner and date |
| `vendor` | RouterOS `defconf:` prefix, or `dynamic=true` |
| `garbage` | none of the above |

Provenance readable only in the repository is not provenance: the operator
reads the device, and so will any future reconciliation.

### D2. One canonical marker, no synonyms

The marker for topology-rendered objects is the suffix **` - managed by
topology`**, declared in `configs/quality/device-provenance-policy.yaml`.

Three spellings were in use until 2026-10-21 — `managed by topology`, `managed by
terraform`, `managed by Terraform` — which made provenance unreadable to any
mechanical check: a grep for one classified the other two as foreign. The two
retired spellings are now refused at validation time (`E8401`).

### D3. Every rendered device object carries the marker, or its type is exempt for a stated reason

Exemption is per resource type, declared in data, with one of three reasons, and
each reason is verifiable:

| Reason | Meaning | Verified by |
|---|---|---|
| `no_comment_attribute` | the provider exposes no `comment` for this type | `terraform providers schema -json` |
| `singleton_settings` | a settings object, not a list item: it cannot be garbage, only drift in value | the resource's own semantics |
| `not_a_device_object` | creates no object on a device | the provider |

Measured on the `routeros` provider: 21 of 24 rendered types support `comment`.
The three that do not are `routeros_container_envs` (keyed by name+key),
`routeros_ip_dns` and `routeros_container_config` (both settings singletons).
For exempt types the ownership proof must come from the ledger and Terraform
state instead — stated here so the gap is known rather than discovered later.

### D4. "Garbage" has a definition

```
garbage = live − planned − manual-registry − vendor/dynamic
```

This is the definition the requirement "no garbage on the device" needs in order
to be falsifiable. It cannot be evaluated without a live inventory (option B)
and a manual registry (option C); until both exist the predicate is defined and
unevaluated, which is better than undefined.

The complement matters as much as the term: 46 live objects are unmodelled and
legitimate, among them vendor `defconf` rules carrying 7.8 M packets and
`AWG-Proxy Sweden Test WAN egress` carrying 3.4 M. Treating "not planned" as
"garbage" would have deleted them.

### D5. A rendered permit must prove its placement

A chain that ends with a rule matching everything swallows whatever is created
after it. Every rendered permit in such a chain must therefore prove placement,
by one of exactly two means:

* **`place_before` the terminal rule** — a device-visible attribute; or
* **the terminal's own `depends_on` naming the permit** — Terraform metadata
  only, which fixes creation order and therefore device order while rendering no
  device change. This is the correct proof where `place_before` would create a
  dependency cycle, as it would for the established/related permit the terminal
  already depends on.

Where the terminal is *conditional* (the input chain's drop matches only `!LAN`)
a later permit can still be effective, so the obligation is a warning: the order
is unspecified rather than wrong.

Deny rules need no proof. A deny after a terminal deny changes nothing; only
permits can be stranded.

### D6. A configuration-shaped declaration must name its consumer

A block named `firewall_rules`, `mangle_rules`, `nat_rules`, `policy_routes`,
`routing_rules` or `address_lists` speaks device configuration, and authoring one
is a claim that something enforces it. The instance must therefore declare, in
data, who consumes each such block:

```yaml
config_block_provenance:
  mikrotik_config: object.mikrotik.generator.terraform
  chateau_routing: documentation
```

A named plugin must exist in some manifest. `documentation` is a legitimate
answer and the honest one for a block kept as description — but it must be said,
not left to a reader's assumption.

**What this proves and what it does not.** It proves a consumer is named and
exists. It does not prove the plugin reads that path, because no plugin declares
the instance-data paths it reads. Closing that is part of option B.

### D7. How a human records a hand-made change

A deliberate manual change is legitimate — ADR 0055 already establishes that for
Terraform files, and the same need exists on the device. It must be
*distinguishable*, which means marked on the device and registered in the
repository.

**On the device**, the comment begins with `manual:` and carries two required
tokens and one optional:

```
manual: AWG proxy test egress owner=platform-owner since=2026-10-21 ref=docs/reports/2026-10-21-chateau-dead-rules.md
```

* `owner=` — who owns the exception. An exception without an owner is garbage
  with a comment.
* `since=` — `YYYY-MM-DD`. It makes staleness visible without asking anyone.
* `ref=` — the ADR, report or ticket that explains it. Optional, strongly
  preferred.

A prefix rather than a suffix, deliberately: it is the first thing an operator
sees in Winbox and in `/export`, and it sorts together.

**In the repository**, a manual-exception registry (option C) carries one entry
per such object: device, resource family, identity, owner, reason, and a review
date. Two consequences follow, and both are the point:

* an object marked `manual:` on the device but absent from the registry is
  **not** sanctioned — it is garbage with better handwriting, and the
  reconciliation says so;
* an entry whose review date has passed is reported, so "temporary" tweaks
  cannot quietly become permanent architecture.

The intended lifecycle of every manual entry is removal: either it is promoted
into topology (the generator learns to render it) or it is deleted from the
device. The registry is a staging area with a clock, not a parking lot.

### D8. Diagnostics are registered before they are raised

`E84xx` / `W84xx`, measured free on 2026-10-21 and adjacent to the
deploy/assemble bands. Not `E81xx`, which ADR 0103 earmarked and the workspace
assembler has occupied since — a reservation not re-measured before use is how
collisions are made. Codes and raisers are documented in
`docs/diagnostics-catalog.md`.

---

## Implementation Plan

Four options, from the SPC analysis. Each is independently useful and each is a
precondition for the next.

### Option A — prevention (implemented 2026-10-21)

Offline, no credentials, no live risk. Stops the defect *generators*.

| # | Deliverable | State |
|---|---|---|
| A1 | `configs/quality/device-provenance-policy.yaml` — marker, manual marker, exemptions, terminals, config-block vocabulary | done |
| A2 | `scripts/validation/validate_device_provenance.py` — marker coverage (D2, D3) and placement proof (D5) over the rendered roots, wired into the `validate-v5` lane in enforce mode (`DEVICE_PROVENANCE_MODE` to relax) | done |
| A3 | marker normalised and completed in the MikroTik templates: 17 retired spellings replaced, 11 objects given the marker they lacked | done |
| A4 | placement proven for 5 permits that had none, and the input chain's order fixed by `depends_on` (no device change) | done |
| A5 | `base.validator.config_block_provenance` (D6), with the 10 instances that carry such blocks annotated | done |
| A6 | `E84xx`/`W84xx` registered in the catalog and documented | done |
| A7 | contract tests for both checks, including mutation checks | done |

Measured result: 262 rendered resources, 218 marked, 44 exempt, every resource
in exactly one verdict; 28 permits with proven placement; lane green in enforce
mode.

### Option B — visibility (planned)

Answers "what will Terraform change, and what is garbage" mechanically.

| # | Deliverable | Notes |
|---|---|---|
| B1 | **Ownership ledger.** Each generator emits, beside its `.tf`, a machine-readable ledger of every resource it renders: type, logical name, identity keys (the match tuple that makes it findable on a device), and the proof channel (marker / state-only). | `generate` stage, sibling of `artifact-plan.json`; pure function of the compiled model |
| B2 | **Device inventory snapshot.** A collector reads a device over REST with SOPS credentials and writes a timestamped, secret-redacted inventory to a known path. | lives in the deploy domain, **not** in the pipeline: the pipeline consumes the file, so determinism and CI-safety are preserved |
| B3 | **Reconciliation builder.** `build` stage, phase `verify`: ledger + tfstate + inventory → a report with the four classes of D1 and the ordering facts of D5, plus `drift-report.json` with a real value instead of `"unknown"`. | reuses `compute_obsolete_entries` semantics: `ownership_proven`, proof method, action policy `retain \| warn \| delete` |
| B4 | **Read-set declaration.** Plugins declare which instance-data paths they read, upgrading D6 from "a consumer is named" to "a consumer reads it". | closes the honest gap in D6 |

Gate to B: none. B is the next increment.

### Option C — governed garbage collection (planned)

Makes "no garbage" true, by reconciliation.

| # | Deliverable | Notes |
|---|---|---|
| C1 | **Manual-exception registry** (D7), seeded by triaging the 46 unmarked live objects: model it, sanction it, or delete it — one at a time, each with a reason | without this, deletion is unsafe and "no garbage" is unfalsifiable |
| C2 | **Remediation script generation**: RouterOS `/remove [find .id=…]` for proven garbage, `terraform import` for objects to adopt | generated, never executed by the pipeline |
| C3 | **Gates on deletion**: ownership proven, packet counters read immediately before, and for a duplicate, the owned twin verified reachable ahead of any conflicting deny | three of the 87 marked-unowned filter rules are *passing traffic* from above their owned twins; deleting those without the twin check changes behaviour |
| C4 | Device-side ordering verification (D5 against the inventory, not only the artifact) | |

Gate to C: B1–B3 in place, and the operator's triage decision on each of the 46.

### Option D — golden configuration (planned, gated)

Makes "no garbage" true *by construction*: a complete generated configuration
applied to a reset device, so anything not in the model ceases to exist.

Gate to D, all three required:
1. B reports **100% coverage** — every live object is planned or sanctioned;
2. a maintenance window and a verified, restore-tested backup;
3. `defconf` and every vendor feature in use either modelled or deliberately
   dropped, as a decision with a reason.

Today the gate fails on (1): at least one live load-bearing rule
(`AWG-Proxy Sweden Test WAN egress`, 3.4 M packets) is modelled nowhere.

---

## Consequences

### Immediate

* The lane fails on an unmarked or unplaced rendered object, and on a
  configuration-shaped block with no named consumer. That is the intent.
* Comments change on the device for 13 objects whose marker spelling was
  normalised, and appear for 11 that had none. A plan will show these as
  in-place comment updates.
* Five permits gain `place_before`. They are reachable on the current router only
  because they were created before the terminal drop existed; a recreate or a
  fresh device would have stranded them. An apply may reposition them, which is
  the correction, not a side effect.
* The input chain's order becomes deterministic with no device-visible change.

### Deliberately not addressed

* The 98 marked-but-unowned objects and the 63-rule dead tail stay on the device.
  Removing them is option C, needs the registry first, and is an operator action
  in safe mode.
* ADR 0103's cancellation of a *dual-mode* architecture is not reversed. Option B
  builds one path (a file-consuming builder), not two.
* ADR 0105 stays Deferred. Option C generates a remediation script and does not
  apply it, so no commit/rollback contract is required yet.

### Rejected alternatives

| Alternative | Why not |
|---|---|
| Hand-maintained reality fields in instance YAML (`status:`-style) | ADR 0103 D1 forbids it, and it is stale by construction |
| Rely on `terraform plan` alone | measured blind to 98 of 314 live objects; this is the premise that failed |
| Live device reads inside `compile`/`generate` | breaks determinism and CI-safety (ADR 0074). Hence B2's file boundary |
| Delete everything not planned | would have deleted 46 legitimate objects, including vendor defaults and a rule carrying 3.4 M packets |
| A marker on every type without checking the provider | three types have no `comment` attribute; an unverified assumption would fail at apply, not at validate |

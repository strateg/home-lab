# How the universal container network model works

Living reference for ADR 0118 / ADR 0119 as implemented. Started 2026-09-11 at
commit `a4112d5c`. Updated as implementation proceeds; every claim here is
measured, and where a measurement is missing the section says so rather than
describing an intention as a fact.

The implementation plan (`IMPLEMENTATION-PLAN.md`) says what is being built and
why. This says **how the parts fit together and what each one guarantees**, which
is what a reader debugging a rendered address or a firewall rule actually needs.

---

## 1. Two versions, side by side

The topology is infrastructure-as-data: Class → Object → Instance, layers L0–L7.
Network intent exists in two shapes, and a source uses one or the other.

**Version 1**, everything in the tree today. A workload carries a flat block:

```yaml
network:
  vlan_ref: inst.vlan.servers
  host: 210
```

**Version 2**, declared and enforced, used by no source yet:

```yaml
network:
  schema_version: 2
  attachments:
    primary:
      network_ref: inst.vlan.servers
      address: {allocation: static, host: 210}
      default_route: true
```

The two must not be mixed inside one effective source; `E7004` says so.

The essential difference is not syntax. In v1 `host` is read as a **last octet**;
in v2 it is an **offset from the network address**. On an unshifted /24 those
agree exactly, which is why every address in the live topology resolves the same
way under both — and why the difference is invisible until someone adds a /23 or
a shifted /25. See `W04-IP-DERIVATION-CHARACTERIZATION.md`.

---

## 2. Where the shapes are declared

Three class-level declarations, one on the layer that owns the concept:

| Shape | Declared on | Key | Authored under |
|---|---|---|---|
| Attachments | `class.compute.workload` (L4) | `network_intent_schema` | `network` |
| Publications | `class.service` (L5) | `service_publication_schema` | `publication` |
| Policies and bindings | `class.network.firewall_policy` (L2) | `policy_intent_schema` | `policy` |

`class.service` was added as an abstract base so publications could be declared
once; the fourteen concrete service classes now extend it. Before that L5 had no
shared ancestor at all.

**Inheritance records lineage and merges nothing.** The compiler emits `lineage`
(root-first) and `parent_class` on every class, and leaves the parent's payload on
the parent: `class.compute.workload.lxc` does not carry the base's
`network_intent_schema`. Any consumer must resolve declarations by walking
lineage. A consumer that reads only the class an instance names finds no schema
and silently validates nothing — measured, and asserted by test.

---

## 3. What happens to a source, in order

Pipeline stages are `discover → compile → validate → generate → assemble → build`.
The network-model plugins sit at:

| Plugin | Stage | Order | Reads | Publishes |
|---|---|---|---|---|
| `base.compiler.instance_rows` | compile | 44 | sources | `normalized_rows` |
| `base.compiler.network_intent_resolver` | compile | 46 | `normalized_rows` | `resolved_network_intent` |
| `base.compiler.ip_derivation` | compile | 56 | `normalized_rows` | v1 `_resolved_ip`, `_resolved_gateway` |
| `base.validator.network_intent_schema` | validate | 128 | `normalized_rows` | diagnostics |

Precedence between an authored value, an object default and an `@on:host.X` host
default is applied by `instance_rows`, upstream of all of this. Nothing
downstream re-implements it: a second precedence table would be a second
authority for one rule.

### The resolver

For each **enabled v2 attachment** it derives the effective address (offset from
the domain's network address), the gateway (from the domain, never invented) and
the address family (from the prefix's version), and publishes each with a
provenance string naming what produced it.

It never fails the stage. Running before validate, it publishes what it could not
resolve under `unresolved` with a reason, and the validator reports the fault with
the right code. Failing here as well would report one fault twice, with worse
paths.

It never guesses. A dynamic allocation yields no address; a domain without a
gateway yields no gateway; an offset the prefix does not admit yields nothing.
Each of those is a fallback the legacy path took, and each put a value into the
model that the network could not honour.

### The validator

Two passes. The first checks shape against the class declaration; the second
checks meaning across records, and runs **only if the first found nothing** —
cross-record checks over malformed records restate the first mistake in a less
useful form and bury it.

---

## 4. What is enforced, and by which code

Allocated range `E70xx`/`W70xx`/`I70xx` (see `docs/diagnostics-catalog.md`).

**Shape, pass one:**

| Code | Rule |
|---|---|
| `E7001` | A key or record property the class declaration does not declare |
| `E7002` | A record key outside `^[A-Za-z_][A-Za-z0-9_]*$` |
| `E7003` | A derived or forbidden field authored on a record |
| `E7004` | Version 1 keys beside version 2 in one block |
| `E7005` | A missing required field, or a record that is not an object |
| `E7006` | An absent or unsupported `schema_version` |
| `E7007` | The validator's own prerequisite missing — the check did not run |

`E7007` is kept distinct from `E7005` because "the check did not run" and "a field
is missing" are different facts, and a check that could not run must never read as
a pass.

**Meaning, pass two:**

| Code | Rule |
|---|---|
| `E7020` | An attachment names something that is not a modeled address domain |
| `E7021` | More than one default route per address family (see limits below) |
| `E7022` | Two enabled attachments claim one host offset in one domain |
| `E7023` | A static address against a domain that declares no prefix |
| `E7024` | A host offset the prefix does not admit |
| `E7040` | A publication endpoint that is not an attachment on its runtime target |
| `E7041` | Two publications on one endpoint, protocol and port |
| `E7060` | An effect/activation pairing outside the baseline profile |
| `E7061` | A binding naming an unknown policy, or a guard, which cannot be bound |
| `E7063` | A permit overlapping a mandatory deny, with a concrete witness |
| `E7064` | An unbound parameter on a guard, or an empty resolved selector |

---

## 5. The rules the model is built to keep

**Authorization comes only from an explicit, bound, approved permit.** A network,
an address, a route, a NAT rule, an open listener and an established connection
all fail to create one. `A = (P ∩ C) \ D`.

**A publication is delivery, never permission.** It contributes to `C` and never
to `P`, and the guarantee is structural: the publication shape has no field in
which to author who may connect. Today's `security.allowed_from` on a service
instance is exactly that conflation; migrating it to a policy binding is source
work, not a schema default.

**Two policy modes exist and no others**: `permit` + `binding_only`, inert until a
binding names a subject, a target and an approver; `deny` + `scope_guard`,
activated by its scope and not defeated by a narrower permit. Any other pairing
has no defined meaning and is refused rather than interpreted.

**A conflict is not resolved by the compiler.** A permit overlapping a mandatory
deny is an authoring contradiction reported with a concrete flow that matches
both. Set subtraction defines what authorization means; it does not decide which
of two contradictory statements the author meant.

**Derived values are not authorable.** `ip`, `gateway`, `zone`, `routing_domain`,
`address_family` on an attachment; `address`, `nat_rule`, `firewall_rule`,
`rule_position`, `zone` on a publication; `position`, `priority`, `order`,
`chain`, `table` on a policy. Rule order comes from execution precedence, never
from an author's number.

**An empty selector is an error, not "any".** A resolved set that comes out empty
is refused; it is never treated as permissive.

**`enabled: false` disables without deleting.** A reference to a disabled record
is an error rather than a silent miss, and a disabled attachment claims no
address and holds no default route.

---

## 6. One rule, two implementations, held together by differentials

`netmodel/` is a root package outside framework distribution, deliberately: it is
the reference model and is meant to be cheap to rewrite. A framework plugin
therefore **cannot import it** — an external project consuming the framework would
not have it.

So the policy algebra and the address arithmetic each exist twice. What keeps the
copies honest is not discipline but tests that run both over the same inputs and
require the same answer, including the same refusals:

| Rule | Reference | Framework | Differential |
|---|---|---|---|
| Permit/deny overlap | `netmodel.policy` | validator, pass two | `test_the_plugin_algebra_agrees_with_the_reference_model` |
| Offset arithmetic | `netmodel.domains` | `address_domain_helper` | `test_the_plugin_resolver_agrees_with_the_reference_model` |

Inside the framework there is one copy: the compiler and the validator hold the
same `resolve_offset` object, asserted by test rather than assumed.

The reference model is also run against the **real topology** on every test run.
That forcing function has caught four errors in this work so far, including a
differential that read the wrong field name and therefore compared nothing. Every
differential here now asserts a minimum comparison count: a test that examined
nothing is not evidence.

---

## 7. Limits, stated rather than hidden

Nothing below is a gap to be embarrassed about; each is a case where an
approximation would be silently wrong, and a check that cannot be right yet emits
nothing.

| Not implemented | Why |
|---|---|
| `E7021` scoped by routing domain | Nothing in the sources declares one. The check is scoped by address family (derived from the prefix) and one implicit routing domain, which is exact today and becomes too permissive, never too strict, if routing domains are introduced |
| `E7023` in its full form | "No prefix for the requested family" has no requester: an attachment cannot author a family. The narrow form — the domain declares no prefix at all — is implemented and exact |
| `E7042` | Needs capability resolution |
| `E7062`, `E7080`–`E7089` | Plan-time obligations; they belong to a plan compiler that does not exist yet |

Rejected as *stricter than the rule*: counting default routes per workload. It
would reject a correct dual-stack source.

### The legacy path

`ip_derivation_compiler._resolve_ip` does not compute an address; it edits a
string. Three measured failure modes — an output that is not an IP address, an
address outside its own network, a gateway outside its own network — all latent,
because every address domain is an unshifted /24 where the two arithmetics agree.

It has not been changed. There are no output deltas to review while that stays
true, and the plan requires legacy repair to be its own reviewed change. A guard
test fails the moment a source introduces a non-/24 or shifted network.

**Its derived values are consumed by nothing.** `_resolved_ip` and
`_resolved_gateway` are written into the row and read by no generator, template,
assembler or builder; `ip_derivation_stats` is published and consumed by nobody.
Of the 23 addresses it derives, 21 appear in no artifact, and the two that do are
there because they are written literally in sources — checked one at a time, not
inferred from a count.

The plugin still does useful work: `E7861`–`E7865` catch duplicate hosts, the
reserved gateway offset, out-of-range hosts and mixed patterns. It is the
derivation product that is unconsumed, not the plugin.

This bounds two things. A migration of a source to v2 **cannot change a rendered
address**, because no rendered address comes from here — so artifact parity across
such a migration is evidence about the rest of the pipeline, not about addressing.
And the moment anything starts reading those values, every failure mode above
becomes live without the compiler changing at all; a test pins the current
non-consumption so that day is visible.

---

## 7a. What a migration actually costs

Measured 2026-09-11 by converting one real source, `docker-grafana`, to v2,
compiling, and reading the diagnostics. The source was reverted; artifact parity
was re-checked afterwards and is identical.

**The migration unit is the host, not the workload.** `srv-orangepi5` declares
`workload_defaults.network` with version 1 keys - `network_ref`, `host: 23`,
`gateway` - and **19 workloads inherit from it**. Migrating one of them produces
an effective `network` block containing both the instance's v2 attachments and
the host's inherited v1 keys, which is precisely the mixture `E7004` forbids and
`E7001` reports key by key.

That is the rule working, not the rule getting in the way. An instance that
inherits a v1 host default *is* a v1-flavoured source, and pretending otherwise
would mean two readings of `host` in one effective block. But it means a
migration is planned per host: the host defaults and every workload under them
move together, or none do.

**Addresses are not what makes it expensive.** Nothing renders the derived
addresses (section 7), so the migration cannot change one. The cost is entirely
in the inheritance graph.

---

## 8. Current state

| Fact | Value | Measured |
|---|---|---|
| Sources using v2 | 0 | 2026-09-11 |
| Address domains | 11, all unshifted IPv4 /24 | 2026-09-11 |
| Live addresses reproduced by the strict resolver | 23 of 23 | 2026-09-11 |
| Artifact parity against the pre-work baseline | 147 files identical | 2026-09-11 |

The whole of this is inert on the current topology **by construction**, and that
is the evidence for it being safe to have landed: artifact parity is identical
across every emitted file.

---

## 9. Change log

| Date | Commit | What changed here |
|---|---|---|
| 2026-09-11 | `a4112d5c` | First version: sections 1–8 as implemented through the compiler mount |
| 2026-09-11 | `8a04dd15` | Section 7: the legacy derivation's output reaches nothing, measured address by address; what that bounds for migration |
| 2026-09-11 | `3c06ffbe` | Section 7a: a real source migrated and reverted; the migration unit is the host, and a lineage-resolution bug in the validator that only a real source could reveal |

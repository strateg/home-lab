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
| `E7025` | A reference to a record whose `enabled` is explicitly false |
| `E7040` | A publication endpoint that is not an attachment on its runtime target |
| `E7041` | Two publications on one endpoint, protocol and port |
| `E7060` | An effect/activation pairing outside the baseline profile |
| `E7061` | A binding naming an unknown policy, or a guard, which cannot be bound |
| `E7063` | A permit overlapping a mandatory deny, with a concrete witness |
| `E7064` | An unbound parameter on a guard, or an empty resolved selector |
| `E7096` | An in-scope flow that reaches no rule at all; the execution does not terminate |

`E7025` is a separate code rather than a variant of `E7040`/`E7061` because the
declarations keep a disabled record instead of deleting it. Reporting "no such
attachment" for a name that is spelled correctly sends the author hunting a typo,
and for a binding it was worse than a bad message: the binding was checked against
the disabled template and passed, recording an approval against a policy that
grants nothing.

**Registered and not yet raised.** Seven allocated codes have no raiser in the
framework: `E7042` and `E7062`, which have no mount point yet, and `E7085`-`E7089`,
the five obligations implemented in `netmodel` and not yet mounted. They are a
ledger in `tests/test_diagnostic_code_registry.py` that names the mount point each
is waiting for; it may shrink and cannot grow. A code nobody raises is a claim
nobody checks - that is how `E7094` was found registered, meant and silent.

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

**The chain is three links, not two.** The object module pulls the values from
the host:

```yaml
# obj.docker.container.generic
defaults:
  network:
    network_ref: "@on:host.network.network_ref?"
    gateway: "@on:host.network.gateway?"
```

So a per-host migration moves the object module, the host's `workload_defaults`
and every instance under them, together.

### The v2 shape travels the same chain

Proved, not assumed - `_get_nested_value` walks a dotted path of arbitrary depth,
and three tests in `test_on_directive_object_defaults.py` assert that it does,
that the inherited block carries no version 1 key, and that a host path the
defaults require but the host does not declare is reported (`E6810`) rather than
silently dropped. Silence there would leave an attachment with no `network_ref`
and send the author to the instance file, which is the wrong one.

The migrated shape:

```yaml
# object module
defaults:
  network:
    schema_version: 2
    attachments:
      primary:
        network_ref: "@on:host.network.attachments.primary.network_ref"

# host workload_defaults
network:
  schema_version: 2
  attachments:
    primary: {network_ref: inst.vlan.servers}

# instance - only what is its own
network:
  attachments:
    primary:
      address: {allocation: static, host: 210}
```

The gateway disappears from the chain entirely: in v2 it is a property of the
address domain, derived, and not authorable on an attachment. That is one fewer
value to keep in agreement across three files.

---

## 7b. Proposals are not permissions

Acceptance item A22: an unapproved candidate present in the model produces no
permit, no rendered rule and no accepted flow, and rejecting it leaves the
pipeline green.

The load-bearing word is *present*. Refusing to represent candidates would
satisfy the letter of A22 and defeat its purpose — the model holds them so a
reviewer can see what was proposed. So the separation is structural, not a
remembered check:

* a `Candidate` is a different type from a `Binding` and **has no approval field
  to flip**. A shared type with an `approved` boolean puts a proposal and a grant
  on one path with a flag between them, and a flag is one typo from being true;
* `promote` is the only crossing, it takes a keyword-only approver with no
  default, and it refuses an approver who is the proposer. Self-approval turns
  review into a formality that leaves a complete audit trail of nobody having
  looked;
* approval activates a template, it never widens one. Promoting a candidate whose
  selectors do not intersect the template is refused, not resolved permissively.

An unapproved `Binding` is reported as a candidate rather than dropped: a binding
somebody wrote and nobody approved is precisely what a reviewer needs to see.

**What this is not.** Rejecting a proposal is green; a *missing* required flow
must still block, and that is `SEC-AVAIL` (`E7084`), which belongs to a plan
compiler that does not exist yet. The two must never be confused, so this module
has no vocabulary for the second — a test asserts that neither `Review` nor
`Candidate` gains a field named for requirement or availability. A green review
here is evidence about proposals only.

---

## 7c. From intent to a plan, and back again

Three modules, and the third deliberately does not know about the first.

| Module | Does | Must not |
|---|---|---|
| `netmodel.policy` | decides what the intent authorizes: `A = (P ∩ C) \ D` | — |
| `netmodel.lower` | translates grants and guards into ordered rules | re-decide authorization |
| `netmodel.interpret` | reads a plan and says accept / deny / unsupported | import `policy` or `lower` |

That separation is the point of G3, which says in as many words: do not make the
generator and the oracle share the same decision code and call the agreement a
proof. An oracle that imports the producer shows only that the code agrees with
itself. A test asserts the imports are absent.

With them apart, SEC-AUTH stops being an argument and becomes a property over a
bounded, enumerated flow space:

* **SEC-AUTH** — every flow the plan accepts, the intent authorizes.
* **SEC-AVAIL** — every required flow, the plan carries.
* deleting a permit cannot enlarge what is accepted; adding a deny cannot either.

**The mutants are the load-bearing part.** The contract names them and they are
implemented: an accept-all plan must fail SEC-AUTH, an all-drop plan must fail
SEC-AVAIL while still satisfying SEC-AUTH. A checker that cannot fail a plan that
is definitely wrong says nothing about one that looks right. A further test
refuses the vacuous case directly - a subset claim over an empty set passes and
proves nothing - by asserting the accepted and authorized sets are non-empty and
the space is larger than either.

### Three verdicts, not two

`unsupported` is a real outcome. A plan with no terminal rule that matches
nothing leaves the result to a backend default the interpreter does not know, so
it says so rather than inventing one: **default-deny is a property of a backend,
not of a rule list.** Silently returning deny would report a safe result for a
rule set nobody understood.

### The terminal deny belongs to the plan

ADR 0119 D4 makes it a plan obligation, and the reason is checkable: a terminal
rule a template adds is a terminal rule the plan cannot reason about, while "is
anything executable after the drop-all" is exactly what the plan has to answer.

**A terminal closes its scope because of what it says, not because of the flag.**
It carries the scope's endpoints and an any-transport, and those are properties
of the rule. Reading the flag as "ignore the transport" was a real divergence,
found on 2026-09-15: a terminal narrowed to `tcp/53` was interpreted as an
unconditional deny while the consumer received the finite predicate, so one plan
meant two things. Both implementations honour the field now.

Four things are checked, and only presence and effect were before:

* effect `deny`, and it is last - a rule after it is unreachable;
* no named sources or destinations, and `transport: {kind: any}`. Anything
  narrower closes part of the scope and leaves a residue this contract cannot
  prove empty: the endpoint set is closed by enumeration, the transport space is
  not, and a terminal naming `tcp/53` says nothing about UDP;
* every in-scope flow reaches *some* rule. `E7096` reports one that does not.

That last one is a separate obligation. It used to be silence unless the flow
happened to be in `Q`, which made termination a consequence of somebody declaring
an availability objective. It is also not repaired by reading an unmatched flow
as a deny - that would credit the plan with a rule it does not carry, and on a
default-allow backend the real outcome is the opposite of a deny.

---

## 7d. The eight obligations, and where each one is checked

| Obligation | Module | The failure it exists for |
|---|---|---|
| `SEC-AUTH` | `interpret` vs `policy`, over a bounded flow space | The plan accepts what the intent never authorized |
| `SEC-AVAIL` | the same comparison, the other direction | An all-drop plan, which is broken rather than safe |
| `SEC-ORDER` | `plan` | A different plan from the same intent, or a violated edge |
| `SEC-NAT` | `transform` | Two frontends collapse onto one backend rule |
| `SEC-STATE` | `state` | An established session outlives the permit that admitted it |
| `SEC-TRANSITION` | `transition` | A window during the apply that neither endpoint shows |
| `SEC-PATH` | `path` | A path class nobody enumerated, reported as covered |
| `SEC-CAP` | `capability` | Declared support read as evidence, or evidence as permission |

Three of them were revised on 2026-09-14 after the post-fix review named what
each was measuring instead.

**SEC-STATE was measuring the wrong interval.** `now - established_at` against
the deadline meant a connection running for an hour was over its deadline the
moment the epoch changed, before the agreed grace began - and the model had no
way to say *when* revocation started. `Revocation` carries `effective_at` and the
epoch it supersedes; the deadline is absolute. A session opened after that moment
gets no grace at all, because nothing is winding it down: it is a new connection
under a policy that does not authorize it, and that is a different failure with a
different response. A related session is judged by its parent's authorization
rather than its own tuple, which is usually on a port no rule mentions.

**SEC-CAP was checking one level and one plan-wide mode.** Freshness and
delegation were checked for the chosen offers only, so a prerequisite that
depended in turn on an expired, undelegated one was never looked at; expansion is
transitive now and every node in the closure is checked. Mode, ownership and
capacity are scoped to a `resource`: two firewalls on different devices running
different modes are not in conflict, and requiring one mode across a plan refused
good independent components. An offer stating a mode without naming what it acts
on is `unverified`. The digest is computed from the offer's semantic core rather
than accepted as a string, so two different bodies cannot carry one label, and
the result is a `Feasibility` with three answers - an empty conflict list used to
be read as "these work together" when it meant "nothing I could check disagreed".

**SEC-TRANSITION proved sequences it never performed.** A strategy returning no
mutations produced no states, and no states have no state outside the envelope.
Five preconditions and postconditions now surround the replay: the envelope's
digests must be the digests of these plans and it must not have expired; the flow
space must cover what the envelope admits; the mutations must be exactly the diff;
the final state must *be* the new plan; and at the end `Accept(R_final) ⊆ A_new`
with every required flow still carried. `UNSUPPORTED` is no longer skipped
alongside `DENY` - a deny is a rule saying no, an unmatched flow is no rule at
all, and on a default-allow backend that is the window itself.

Three habits run through all of them, and they are the reason these are checks
rather than descriptions.

**Silence never means yes.** No applicable offer is `unverified`, not satisfied.
No rule matched is `unsupported`, not accepted. A path case with no evidence is
unverified by construction. An empty loop reports "no failures" whether it checked
everything or nothing, so each of these says which.

**Nothing marks its own homework.** The interpreter cannot import the producer.
`path` enumerates what must be covered and never what is covered. `capability`
takes evidence as an argument. Where one rule needs two implementations, a
differential runs both and requires the same answer.

**Every checker is shown failing.** An accept-all plan must break SEC-AUTH; an
all-drop plan must break SEC-AVAIL; tearing denies down first must break
SEC-TRANSITION. A checker that has never failed says nothing about a plan that
looks right.

### What SEC-PATH still needs from outside

The lower bound on `Omega_g` is normative and implemented: every path class ADR
0118 D6 requires, crossed with the families and epochs in scope. What the model
cannot supply is the evidence that a case was demonstrated, and it deliberately
has no function that could - `coverage_gaps` takes `demonstrated` as an argument.
Filling it is W09 and W11 work, and until then every case reads `unverified`,
which is the correct answer rather than a placeholder.

---

## 7e. What admission binds, and why every link is checked

Nothing renders the plan yet. `topology-tools/plugins/validators/strict_admission.py`
is the contract the first renderer will have to use, written before it arrives so
it meets a boundary instead of defining one. What it binds is a chain:

    approval -> the exact intent that was checked -> the verification -> the plan

Each arrow is an equality this code computes, not a field it reads. The plan's
digest is computed here and compared with the one the verifier recorded, so a
plan edited afterwards - including one that recomputes its own `digest` to agree
with itself - is not the plan that was checked. The verifier records an
`intent_digest` over the obligations it lowered for itself, and the approval names
that same digest plus the scopes it covers. Without it, `approved: True` is a
boolean that cannot say what it approved, and an approval issued for one scope
admitted a plan built from another.

**Three digests, three questions.** `intent_digest` is the permission set.
`evidence_digest` is the attestations used to discharge what nobody verified - a
waiver's owner and rationale. `plan_digest` is the artifact. They are separate
because changing a waiver's signatory leaves the semantics identical, so folding
it into semantic identity would make an unchanged plan look changed; and leaving
it out of identity altogether let an old approval discharge a claim a different
person now signs. An approval must name the first two, and admission computes the
third.

**The epoch comes from the caller, and there is no default.** Requiring the
approval to carry a non-empty epoch string bound nothing: with no epoch to compare
against, the same verified plan was admitted under two different ones. `evaluate`
takes `expected_epoch` from the deployment context and refuses to decide without
it. This boundary cannot manufacture freshness; it can only refuse to pretend.

**The plan shape is closed, over names and over meanings.** Every field is either
known, or a reserved obligation name, or refused. Applicability was once inferred
by searching the serialized plan for quoted words, which made the guard
spelling-sensitive: `path` refused the plan and `paths` carrying the same content
was admitted.

Closing the field names was half of it. `transport.kind: not_implemented`, a
transport with no `kind` at all and `schema_version: 999` all spell their keys
correctly and were admitted - a consumer reading any of them would have to guess,
and every guess is a rule nobody authorized. Values are checked against a stated
grammar now: the transport kinds this contract acts on, ports inside 1-65535,
`effect` in `{permit, deny}`, a boolean `terminal`, an integer `position`. A test
asserts the grammar accepts what the compiler emits, since one stricter than the
producer would refuse every real plan.

**Consent is a boolean and a digest is compared, not consulted.** `approved:
"false"` is a truthy string, and it used to admit the plan; the check is
`is not True` now, and the same for `source_available`. An empty `evidence_digest`
in the record used to disable the comparison against the approval's, so any
attestation stood - an absent digest is refused rather than treated as matching
everything.

**The projection is detached, and only for the plan that was admitted.**
`admitted_projection` re-establishes identity against a snapshot it takes first -
hashing the caller's object and copying it afterwards leaves the same window open,
only narrower - and returns rules that are not the plan's own. A plan that is not
the admitted one raises: it means the caller holds two objects and believes they
are one, and handing a firewall renderer an empty ruleset is not a safe way to
say so.

**Three answers, not two.** The verification record carries a status per
obligation per scope: `pass`, `fail`, `unverified`. The middle answer is the one a
boolean cannot hold. On the real topology today both matrices report

| Scope | SEC-ORDER | SEC-COVER | SEC-AUTH | SEC-AVAIL |
|---|---|---|---|---|
| `inst.security_matrix.mikrotik` | pass | pass | pass | **unverified** |
| `inst.security_matrix.proxmox` | pass | pass | pass | **unverified** |

with zero errors. Nothing is admissible, and not because anything is broken:
nobody has declared what has to keep working, so SEC-AVAIL was never verified.
`W7002` says so, and admission acts on it rather than noting it.

**An absent field is an unanswered question.** Every field the record must carry
is required. A missing `errors` is not zero errors and a missing obligation
status is not a pass - both were admitted before the 2026-09-14 review.

**The other five obligations are mounted, and answer for themselves.**
`base.validator.security_obligations` decides SEC-NAT, SEC-STATE, SEC-TRANSITION,
SEC-PATH and SEC-CAP, and it has three answers rather than two:

* **not applicable** - the plan declares no field this obligation governs, so
  nothing here could violate it. Not a pass, and recorded with the reason.
* **unverified** - it applies and the input to decide it is absent, *named* in a
  `W7003`. Blocks admission exactly as a failure does.
* **pass** or **fail** - `E7085`-`E7089` report the failures.

The middle answer is what made mounting them worth doing. None of the five has
its inputs in the pipeline today - no sessions, no previous plan, no path
inventory, no capability offers - and a checker with no input finds nothing.
Reporting that as a pass is the empty-loop mistake; naming the missing input is
not.

**One of the five decides.** SEC-NAT's input is already on the rule, so two
transforms collapsing onto one target is `E7086` today. The other four report
absent evidence, which is a channel and one implemented decision rather than five
completed checks - and an obligation that abstains is not one that holds.

**The refusal is checked by what is on disk.** A test-only generator in
`tests/fixtures/strict_writer/` runs in the generate stage and writes one marker
file only for an admitted plan. A mutant that replaces the decision with one that
always admits does write it, which is what makes the refusals' silence mean
something.

---

## 8. Current state

| Fact | Value | Measured |
|---|---|---|
| Sources using v2 | 0 | 2026-09-11 |
| Address domains | 11, all unshifted IPv4 /24 | 2026-09-11 |
| Live addresses reproduced by the strict resolver | 23 of 23 | 2026-09-11 |
| Artifact parity against the pre-work baseline | 147 files identical | 2026-09-11 |
| Artifact parity against a clean worktree at HEAD | 163 files compared, every emitted artifact identical | 2026-09-14 |
| Zone membership derivations | 1 (was 2); the generator consumes `base.compiler.security_matrix` | 2026-09-14 |
| Scopes admissible under the strict boundary | 0 of 2; SEC-AVAIL unverified in both | 2026-09-14 |
| Obligations with a framework checker | 9 of 9 mounted; 5 reach a verdict today (4 over the plan, SEC-NAT), 4 report absent evidence | 2026-09-15 |

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
| 2026-09-11 | `2525f01e` | Section 7a: the inheritance chain is three links; the v2 shape travels it unchanged, proved by test, with the migrated shape written out |
| 2026-09-11 | `09f633c0` | Section 7b: candidate isolation (A22) as a type boundary, and what it explicitly does not claim |
| 2026-09-11 | `553c2e3b` | Section 7c: lowering, the independent interpreter, and SEC-AUTH/SEC-AVAIL as properties with mutants |
| 2026-09-14 | `622eff34` | Section 7d: all eight obligations placed, the three habits behind them, and what SEC-PATH still needs from outside |
| 2026-09-14 | `7128c2f6` | Section 4: `E7025` for a reference to a disabled record, and the ledger of allocated codes that nothing raises yet |
| 2026-09-15 | `bdc1374b` | Section 7e: the five remaining obligations mounted, with `not applicable` / `unverified` / decided as three distinct answers |
| 2026-09-15 | `b510035a` | Section 7d: the terminal invariant and `E7096`; a terminal closes its scope because of what it says, and an unmatched in-scope flow is a failure of its own |
| 2026-09-14 | `6d6ff63e` | W05/A24: zone membership derived once; the compiler learned `additional_networks` and sorts zones, the generator consumes the channel, artifacts byte-identical |
| 2026-09-14 | `31ebefb9` | Section 7e: the grammar closed over values, consent as a boolean, and an empty digest refused rather than matched |
| 2026-09-14 | `8dada8ef` | Section 7e: three digests, the caller-supplied epoch, the closed plan shape and the detached projection; after the external review of `c5a5addc` |
| 2026-09-14 | `782061e8` | Section 7e: the admission chain, the three obligation answers, and the deferral that has a trigger; written after the external review of `5e02bf70` |

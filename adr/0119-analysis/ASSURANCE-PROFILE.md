# ADR 0118/0119 — High-assurance profile and DoD alignment boundary

Status: proposed engineering profile, reviewed 2026-09-10.
This is **not** a claim of DoD compliance, STIG compliance, ATO, classified-system
authorization, or certification. No single "strictest DoD standard" applies to
every system. A firewall contract covers only part of the assurance case.

## Source basis

The following are authoritative starting points, not an automatically applicable
baseline. Links were checked during this revision; the DoD Strategy PDF fetch
failed, so its original official release is also linked. Product-specific STIG
checklists were not downloaded or assessed.

| Source | Bounded relevance |
|---|---|
| [DoD Zero Trust Strategy, 2022](https://dodcio.defense.gov/Portals/0/Documents/Library/DoD-ZTStrategy.pdf), [official release](https://www.defense.gov/News/Releases/Release/Article/3225919/department-of-defense-releases-zero-trust-strategy-and-roadmap/) | Department-wide architecture and roadmap; not a firewall configuration certificate |
| [NIST SP 800-207](https://csrc.nist.gov/pubs/sp/800/207/final) | Resource-centric authorization; network location alone must not establish trust |
| [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final) | Tailorable security/control catalog; official page identifies release 5.2.0 |
| [DISA STIG library](https://www.cyber.mil/stigs/downloads/) | Locate applicable product/version SRG/STIG and assessment checklist; library landing page alone is not assessment evidence |
| [NIST CMVP](https://csrc.nist.gov/projects/cryptographic-module-validation-program) | Verify concrete cryptographic module validation where the tailored baseline requires it |

The controls below are **project design requirements** inspired by these sources,
not copied DoD obligations or invented STIG V-IDs.

## Required tailoring record before any compliance claim

An accountable human authority must approve:

- mission/system boundary, data classification, impact and threat model;
- applicable jurisdiction, control baseline, SRG/STIG product/version/release;
- per-control applicability, implementation, evidence, exceptions and residual risk;
- approved cryptographic modules/operating environments where required;
- assessment authority, evidence freshness and acceptance/authorization process.

Until this exists, reports may say "proposed high-assurance network contract",
not "DoD-compliant". Unsupported controls remain unmet, not N/A by convenience.

## Engineering requirements and evidence ownership

| ID | Requirement | Owner / necessary evidence |
|---|---|---|
| HA-01 | Deny by default, bounded grants, non-bypassable mandatory denies | Policy owner; SEC-AUTH/SEC-AVAIL and reviewed flow inventory |
| HA-02 | Cover east-west, host, direct backend, tunnel, IPv6 and accelerated paths | Topology/backend owners; SEC-PATH and observed tests |
| HA-03 | Authentication, least privilege, separate management, MFA where applicable | IAM/operations owner; actual identity integration and administrative audit |
| HA-04 | Transport/application protection with peer verification, trust roots and rotation | Service owner; configured listeners, negative identity/TLS tests; module evidence if required |
| HA-05 | Current-policy sessions, bounded expiry and revocation | Backend/IAM owners; SEC-STATE under stale identity and clock failure |
| HA-06 | Verified artifacts and controlled change authority | Build/release owner; pinned inputs, provenance, integrity/authenticity verification and independent approval |
| HA-07 | Safe partial apply, recovery and non-reopening rollback | Deploy owner; SEC-TRANSITION, OOB access and fault-injection evidence |
| HA-08 | Protected, useful, resource-bounded telemetry | Operations owner; reason codes, protected transport/storage, retention, rate-limit/load and audit-loss tests |
| HA-09 | Secrets never appear in model feedback or public artifacts | Secrets owner; SOPS/age workflow, redaction and access-control tests |
| HA-10 | Security and availability under failures | System owner; enforcer/identity/time loss, fail-secure outcome, approved outage limits and restore drill |

IP/CIDR selectors constrain network traffic but do not prove user/device identity.
TLS or WireGuard presence alone does not establish cryptographic validation.
Framework locks and hashes are integrity inputs, not a complete supply-chain
attestation. Router-hosted containers share trusted components and increase the
assurance burden; isolation may require a stronger hardware/VM boundary.

Candidate control-family mapping for later assessment: access and information
flow control, boundary protection, identification/authentication, audit,
configuration management, contingency/recovery and supply-chain risk.
No claim of complete control coverage is made by this mapping.

## Evidence levels and acceptance

| Level | What it establishes | What it does not establish |
|---|---|---|
| Design-reviewed | Consistent intent, threat model, obligations and plan | Implemented compiler/backend or live enforcement |
| Offline-validated | Versioned model/artifact checks within stated scope | Device hooks/state or actual packet paths |
| Backend-tested | Qualified backend/version and conformance scenarios | Current deployed topology/state |
| Live-observed | Current plan read-back and scoped live tests | Permanent protection after drift or complete compliance |

### Capability satisfaction evidence (rev 3.2, 2026-09-11)

The [capability contract](CAPABILITY-SATISFACTION-CONTRACT.md) and SEC-CAP bind
HA-02/05/06/07/10 to concrete offers, execution contexts, versions and witnesses.
That list is extended (rev 3.2a) to HA-01 and HA-08. HA-01 requires denies to be
non-bypassable, and an acceleration or hook path that no identifier can name is an
unproven bypass rather than an absent one, so HA-01 depends on the path inventory
being externally anchored rather than self-declared. HA-08 requires telemetry to be
useful and protected, and a resolution record is exactly such telemetry: it carries
the reason codes, evidence producer and trust basis on which every capability claim
rests, and inherits HA-08's protection and retention obligations.
An enabled flag, catalog pack or offer's own assertion is not qualification.
Record evidence producer, trust basis, target, test/tool version, digests,
applicability and freshness; independent checks remain necessary.

Report satisfied/unsatisfied/unverified per requirement and claim. Evidence levels
are not interchangeable: a live sample cannot replace complete path/model checks,
and offline validation cannot establish current installed behavior. Missing live
preconditions block activation, not otherwise valid offline candidate generation.
Post-apply observations gate completion, not the preceding guarded transition.
Capability records authorize neither policy expansion nor a second resource writer.

Strict deployment requires all applicable requirements at their necessary level.
Changes in topology, policy, backend version or identity semantics invalidate
affected evidence and require reassessment. Exceptions have an owner, scope,
expiry and compensating controls; they do not relabel an unsupported property as
satisfied. If a hard requirement is waived, the result is a different, explicitly
named risk-accepted profile, not full strict qualification.

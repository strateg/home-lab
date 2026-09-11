---
"@pack": network-security
"@version": 1.6
"@tokens": ~1400
"@adr": [0106, 0109, 0110, 0111, 0118, 0119]
---

# AI Rule Pack: Network Security Matrix

## Status boundary

ADR 0109-0111 describe current legacy behavior and remain the **implemented**
runtime. ADR 0118/0119 are **Accepted as target architecture** (gate G0a) but
**not implemented**: gates G1-G8 are open, no backend is qualified, and the strict
profile is active nowhere. Acceptance changes what to build toward, not what runs.
Do not insert the new fields into active topology, do not treat `attachments` or
`publications` as valid instance keys yet, and do not claim strict enforcement from
documentation gates.

## Quick Reference

| Rule | Key Point |
|------|-----------|
| Security Matrix | Zone-to-zone policies auto-derived from trust levels |
| Trust Zones | 7 zones with security_level (0-5) and isolated flag |
| IP Derivation | `vlan_ref` + `host` → computed IP (no hardcoding) |
| Firewall Rules | Generated from matrix, not manually written |
| Enforcement | Per-platform instances (mikrotik, proxmox) |

## Load When

- `**/security_matrix*`
- `**/trust_zone*`
- `**/vlan*` with `trust_zone_ref`
- Network segmentation or firewall policy discussion

## Security Matrix Hierarchy

| Level | Example | Purpose |
|-------|---------|---------|
| Class | `class.network.security_matrix` | Schema with zones, policy_overrides |
| Object | `obj.network.security_matrix.soho` | Zone refs, default overrides |
| Instance | `inst.security_matrix.mikrotik` | Enforcer-specific config |

## R1-R6 Matrix Calculation Rules

| Rule | Condition | Action |
|------|-----------|--------|
| R6 | Explicit policy_override exists | Use override (ALLOW/DENY) |
| R1 | Same zone (from == to) | ALLOW |
| R2 | Source is isolated | ALLOW→untrusted, DENY→others |
| R3 | Downhill (higher→lower level) | ALLOW |
| R4 | Uphill (lower→higher level) | DENY |
| R5 | Same security_level | DENY (needs override) |

**Evaluation order:** R6 → R1 → R2 → R3/R4/R5.
The implemented internal enforcement plane uses R1b (same-zone deny); the
perimeter plane uses R1 allow. R2 permits isolated-zone egress to untrusted,
so isolated is not a universal egress deny.

## Trust Zones (SOHO Profile)

| Zone | security_level | isolated | Purpose |
|------|----------------|----------|---------|
| management | 5 | false | Router admin, SSH |
| servers | 4 | false | LXC, Docker hosts |
| user | 3 | false | Laptops, phones |
| vpn_tunnel | 2 | false | WireGuard exit |
| iot | 1 | **true** | Smart devices |
| guest | 0 | **true** | Visitors WiFi |
| untrusted | 0 | false | Internet/WAN |

## IP Derivation Pattern (ADR-0111)

```yaml
# Old (deprecated)
network:
  ip: 10.0.30.10/24      # Hardcoded - BAD

# New (correct)
network:
  vlan_ref: inst.vlan.servers
  host: 10                # IP = CIDR base + host
```

**Compiler** resolves to `_resolved_ip: 10.0.30.10/24`

## Validation Codes

| Code | Severity | Rule |
|------|----------|------|
| E7850 | Error | VLAN ID must be unique |
| E7851 | Error | VLAN CIDRs must not overlap |
| E7852 | Error | VLAN must have trust_zone_ref |
| E7861 | Error | Duplicate host in same vlan_ref |
| E7862 | Error | host: 1 reserved for gateway |
| W7864 | Warning | Hardcoded IP (migrate to vlan_ref) |

## Device Capabilities

| Capability | Purpose |
|------------|---------|
| `cap.firewall.security_matrix` | Device can enforce zone-to-zone policies |
| `cap.firewall.security_matrix.routeros` | MikroTik RouterOS enforcement |
| `cap.firewall.security_matrix.pve` | Proxmox pve-firewall enforcement |
| `cap.firewall.address_lists` | Device supports named address lists |

**Note**: Trust levels and isolated flags are DATA (properties in topology), not capabilities.

## Generated Artifacts

| Enforcer | Template | Output |
|----------|----------|--------|
| MikroTik | `zone_firewall.tf.j2` | Address lists, firewall rules |
| Proxmox | (future) | pve-firewall rules |

## Anti-Patterns

| Pattern | Why Wrong | Fix |
|---------|-----------|-----|
| Hardcode `ip:` in workload | Breaks derivation | Use `vlan_ref` + `host` |
| Manual firewall rules | Drift from matrix | Add policy_override |
| Skip trust_zone_ref on VLAN | Breaks matrix | Always add zone ref |
| Edit zone_firewall.tf | Overwritten on generate | Edit template or matrix |

## Key Files

| File | Purpose |
|------|---------|
| `topology-tools/plugins/compilers/security_matrix_compiler.py` | R1-R6 calculation |
| `topology-tools/plugins/compilers/ip_derivation_compiler.py` | IP resolution |
| `topology/object-modules/mikrotik/templates/terraform/zone_firewall.tf.j2` | Firewall generation |
| `projects/home-lab/topology/instances/network/inst.security_matrix.mikrotik.yaml` | Active matrix |

## Accepted target intent/enforcement contract (ADR 0118/0119)

Apply these as design constraints when implementing the proposal, not as claims
about the legacy runtime:

1. Separate L4 attachments, L5 publications and explicitly bound L2 policies.
   Keep C->O->I, derived layers, downward refs and ADR 0107 host defaults.
2. Delivery/NAT, trust level and connection state do not mint permissions.
   Strict permits require explicit approval; mandatory deny wins, conflicting
   authoring blocks compilation. Default deny is the absence of a permit.
3. Runtime gateway derives from its attachment; frontend VIP needs real owner,
   announcement and DHCP/lease/listener collision checks.
4. Preserve original-flow authorization across NAT and all actual paths,
   including host, bridge, direct backend, IPv6, tunnel and acceleration.
5. One compiler-owned plan; generators render validated projections only.
   Preserve six lifecycle stages and manifest exchanges.
6. Canonical semantic order, not hash slots, producer priorities or specificity
   scores. Unsupported semantics/capabilities block strict candidates.
7. Safe transitions, bounded revocation, authorized rollback and actual device
   read-back are required before claiming deployed correctness.
8. Report source -> requirement -> flow/path witness -> minimal source fix ->
   reproducer and digests. Keep design/offline/backend/live evidence distinct.
9. No numeric diagnostic reservation until registry collision checks; no
   DoD/STIG/ATO claim without tailored baseline and assessment evidence.
10. Legacy R1-R6 outcomes are stated in the ADR 0118 D4.1 translation table.
    R1a same-zone allow, R2 isolated egress and R3 downhill grant **nothing** in
    strict; R6 overrides become reviewable candidates. A candidate never
    authorizes traffic and is never rendered. Filling strict policies follows
    derive -> review -> freeze, writing results back to sources.
11. Workload/publication authors never override consumer-derived address/gateway,
    routing domain, zone, rule positions/anchors, provider IDs or digests. L2
    domain owners still declare their authoritative domain inputs. Repetition belongs on the object level; the instance surface is
    measured against the authoring budget in the migration plan.
11a. Objects supply reusable shape and defaults only. Concrete segment
    addressing (`vlan_id`, `cidr`, `gateway`), zone identity and classification
    (name, `security_level`, `isolated`) and any reference naming one device or
    enforcer belong to the instance: one object serves many instances and can
    hold only one such value. Moving such a value is parity-preserving; if an
    artifact changes, it is a behaviour change and reviewed as one.
12. On a default-allow backend the ADR 0110 final drop-all and `E7082` remain in
    force; in strict it is the rendered terminal default deny, emitted by the plan
    compiler and confirmed by read-back.

13. Rev 3 uses named mappings, stable local identity and explicit disabled records;
    list values replace as a whole. Static address uses address.allocation/host.
14. Baseline policies are permit/binding_only or deny/scope_guard. Template alone
    grants nothing; publication disable/delete revokes its binding, not other
    grants. Original/frontend port coordinates remain distinct from backend mapping.
15. Rev 3.1 assigns route/tunnel constraints and interface NAT to L2; L4 realization
    points down to L2 endpoints. Existing VPN remains versioned legacy until
    extension qualification; shared chains still require proven composition.
16. Backend-neutral plan authority belongs to framework/core, not platform objects;
    this is ownership, not an ADR 0086 runtime ACL. Preserve Terraform/Ansible
    resource domains and ADR 0057 RouterOS ownership; transfers require an ADR change.
17. Local keys belong to class schemas, not ADR 0088 metadata tokens. Nested
    schema_version uses distinct network_intent_version contexts at G1; no global
    remapping to @version. Typed collection refs need one canonical contract.
18. Design approval covers the [final architecture proposal](../../../adr/0118-analysis/FINAL-ARCHITECTURE-PROPOSAL.md),
    not plugin count, backend order or implementation sequence. Resource ownership
    and independent management/recovery requirements are architectural constraints.

19. Rev 3.2 derives capability requirements from intent/profile and resolves typed
    versioned offers with per-path/state witnesses (SEC-CAP). A union of device flags
    is not composition; has_capability is classification, not proof or permission.
20. Keep satisfied/unsatisfied/unverified relative to the claim and evidence level.
    Missing live preconditions block activation, not an otherwise valid offline
    candidate. Complete inventory and independent evidence prevent vacuous success.
21. Bind selected offers/strategies/conditions and evidence to intent/plan/bundle;
    relevant version/mode/path/owner changes invalidate resolution. Preserve ADR 0106
    namespaces and owner-authorized operations; no silent topology/legacy fallback.
    See [capability contract](../../../adr/0119-analysis/CAPABILITY-SATISFACTION-CONTRACT.md).

See [ADR 0118](../../../adr/0118-universal-container-network-model.md),
[ADR 0119](../../../adr/0119-firewall-rule-ordering-contract.md) and their
supporting acceptance/assurance contracts.

## Documentation validation

- `task validate:adr-consistency`
- `task validate:agent-rules`
- `task validate:agent-rules-strict`

These validate governance only; runtime acceptance remains the ADR gate matrix.

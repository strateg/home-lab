# ADR 0119: Firewall Rule Ordering Contract

- Status: Proposed
- Date: 2026-09-09
- Related: ADR-0110 (Security Matrix), ADR-0118 (Container Network Model)
- Problem: Multiple rule sources compete for firewall chain positions
- Analysis: SPC Protocol (formal mathematical model)

## Context

### Problem Statement

Firewall rules are generated from multiple independent sources:

| Source | Generator | Rules Generated |
|--------|-----------|-----------------|
| ADR 0110 | Security Matrix | Zone forward rules (deny/allow) |
| ADR 0118 | Container Exposure | DNAT + forward accept |
| VPN Policy | VPN Generator | Mangle + forward |
| Stateful | Core | Established/related |

**Problem:** All rules use `place_before = drop_all_forward`, creating a flat ordering where:
1. Rule ordering within sources is undefined
2. Cross-source ordering is non-deterministic
3. Conflicts between sources are not detected
4. More specific rules may execute AFTER less specific (wrong!)

### Example Conflict

```hcl
# Source: Security Matrix (zone deny)
resource "routeros_ip_firewall_filter" "zone_deny_guest_to_servers" {
  action           = "drop"
  src_address_list = "zone-guest"
  dst_address_list = "zone-servers"  # Includes 10.0.30.60
  place_before     = routeros_ip_firewall_filter.zone_drop_all_forward.id
}

# Source: Container DNAT (specific allow)
resource "routeros_ip_firewall_filter" "forward_dnat_container" {
  action      = "accept"
  dst_address = "10.0.30.60"  # More specific!
  dst_port    = "80"
  place_before = routeros_ip_firewall_filter.zone_drop_all_forward.id
}
```

**Bug:** If deny rule evaluates first, specific allow never matches.

## Decision

### D1: Priority Class System

Define strict priority classes with non-overlapping order ranges:

```
𝒫 = {P₁, P₂, P₃, P₄, P₅, P₆, P₇}

P₁ ≺ P₂ ≺ P₃ ≺ P₄ ≺ P₅ ≺ P₆ ≺ P₇
```

| Class | Name | Order Range | Sources | Chain |
|-------|------|-------------|---------|-------|
| P₁ | ESTABLISHED | 0-99 | Stateful tracking | forward |
| P₂ | ICMP | 100-199 | Diagnostic | forward |
| P₃ | POLICY_ACCEPT | 200-299 | Explicit policy allows | forward |
| P₄ | PUBLICATION_FORWARD | 300-399 | Publication forward WITH policy | forward |
| P₅ | MATRIX_DENY | 400-599 | ADR 0110 R2,R4,R5 deny | forward |
| P₆ | MATRIX_ALLOW | 600-799 | ADR 0110 R3 allow (optional) | forward |
| P₇ | DROP_ALL | 1000 | Implicit deny | forward |

**Key Change (F01):** P₄ now requires `policy_ref`. NAT does NOT grant access.

### D2: Anchor Rule Pattern

Each priority class has an anchor rule that serves as `place_before` target:

```hcl
# P1 Anchor (order: 0)
resource "routeros_ip_firewall_filter" "anchor_established" {
  chain            = "forward"
  action           = "accept"
  connection_state = "established,related"
  comment          = "ADR-0119 P1: Anchor - established/related"
}

# P3 Anchor (order: 200)
resource "routeros_ip_firewall_filter" "anchor_override_accept" {
  chain   = "forward"
  action  = "passthrough"  # No-op marker
  comment = "ADR-0119 P3: Anchor - override accept class"
  depends_on = [routeros_ip_firewall_filter.anchor_established]
}

# P4 Anchor (order: 300)
resource "routeros_ip_firewall_filter" "anchor_container_forward" {
  chain   = "forward"
  action  = "passthrough"
  comment = "ADR-0119 P4: Anchor - container forward class"
  depends_on = [routeros_ip_firewall_filter.anchor_override_accept]
}

# P5 Anchor (order: 400)
resource "routeros_ip_firewall_filter" "anchor_matrix_deny" {
  chain   = "forward"
  action  = "passthrough"
  comment = "ADR-0119 P5: Anchor - matrix deny class"
  depends_on = [routeros_ip_firewall_filter.anchor_container_forward]
}

# P7 Anchor (order: 1000) - Terminal
resource "routeros_ip_firewall_filter" "anchor_drop_all" {
  chain      = "forward"
  action     = "drop"
  log        = true
  log_prefix = "DROP:final"
  comment    = "ADR-0119 P7: Anchor - final drop-all"
  depends_on = [routeros_ip_firewall_filter.anchor_matrix_deny]
}
```

### D3: Rule Placement Contract

Rules reference their class's NEXT anchor:

```
Rule in class Pₙ → place_before = anchor(Pₙ₊₁)
```

| Rule Class | place_before Target |
|------------|---------------------|
| P₃ (override) | anchor_container_forward |
| P₄ (container) | anchor_matrix_deny |
| P₅ (matrix deny) | anchor_drop_all |

### D4: Mathematical Model

#### D4a: Domain Definitions

```
𝕋 = {t₁, t₂, ..., tₙ}           — Trust Zones
𝕍 = {v₁, v₂, ..., vₘ}           — VLANs
ℂ = {c₁, c₂, ..., cₖ}           — Containers
ℙ = {P₁, P₂, ..., P₇}           — Priority Classes
ℛ = {r₁, r₂, ..., rₗ}           — Rules
```

#### D4b: Order Function

```
order: ℛ → ℕ

order(r) = base(class(r)) + offset(r)

where:
  base(P₁) = 0
  base(P₂) = 100
  base(P₃) = 200
  base(P₄) = 300
  base(P₅) = 400
  base(P₆) = 600
  base(P₇) = 1000

  offset(r) = deterministic_hash(r.id) mod 100
```

#### D4c: Specificity Function

```
specificity: Match → ℕ

specificity(m) =
  (is_host_ip(m.src) ? 8 : is_subnet(m.src) ? 4 : 0) +
  (is_host_ip(m.dst) ? 8 : is_subnet(m.dst) ? 4 : 0) +
  (has_protocol(m) ? 2 : 0) +
  (has_port(m) ? 1 : 0)

Range: 0-19
```

#### D4d: Conflict Detection

```
conflict: ℛ × ℛ → 𝔹

conflict(r₁, r₂) ⟺
  r₁.chain = r₂.chain ∧
  overlaps(r₁.match, r₂.match) ∧
  r₁.action ≠ r₂.action
```

#### D4e: Ordering Invariants

```
INVARIANT I1 (Class Order):
  ∀ r₁, r₂ ∈ ℛ: class(r₁) < class(r₂) ⟹ order(r₁) < order(r₂)

INVARIANT I2 (Specificity Within Class):
  ∀ r₁, r₂ ∈ ℛ: class(r₁) = class(r₂) ∧ conflict(r₁, r₂) ∧
    specificity(r₁) > specificity(r₂) ⟹ order(r₁) < order(r₂)

INVARIANT I3 (No Leak):
  ∀ packet p, ∃ r ∈ ℛ: matches(r, p) ∧ terminal(r.action)
  where terminal(a) = a ∈ {accept, drop}
```

### D5: Intermediate Representation (Projection Bus)

#### D5a: Schema

```yaml
# build/projections/mikrotik/firewall_rules.yaml
firewall_rules:
  version: 1
  chain: forward

  anchors:
    - id: anchor_established
      class: P1
      order: 0
      action: accept
      connection_state: established,related

    - id: anchor_override_accept
      class: P3
      order: 200
      action: passthrough
      depends_on: anchor_established

    - id: anchor_container_forward
      class: P4
      order: 300
      action: passthrough
      depends_on: anchor_override_accept

    - id: anchor_matrix_deny
      class: P5
      order: 400
      action: passthrough
      depends_on: anchor_container_forward

    - id: anchor_drop_all
      class: P7
      order: 1000
      action: drop
      log: true
      depends_on: anchor_matrix_deny

  rules: []  # Populated by generators
```

#### D5b: Rule Entry Schema

```yaml
rules:
  - id: override_user_to_servers_http
    class: P3
    order: 205
    source: security_matrix.policy_overrides
    action: accept
    match:
      src_address_list: zone-user
      dst_address_list: zone-servers
      protocol: tcp
      dst_port: "80,443"
    place_before: anchor_container_forward
    specificity: 7

  - id: forward_dnat_docker_adguard_dns
    class: P4
    order: 310
    source: container.docker-adguard.exposure
    action: accept
    match:
      dst_address: 172.18.0.210
      protocol: udp
      dst_port: "53"
    place_before: anchor_matrix_deny
    specificity: 11
```

### D6: Generator Contract

Each generator MUST:

1. Assign `class` from priority class system
2. Calculate `specificity` for conflict resolution
3. Set `place_before` to next class anchor
4. Provide deterministic `id` for order stability

```python
def generate_rule(source, data) -> Rule:
    return Rule(
        id=f"{source}_{sanitize(data.name)}",
        class_=determine_class(source),
        specificity=calculate_specificity(data.match),
        place_before=get_next_anchor(determine_class(source)),
        ...
    )
```

### D7: Topological Sort Algorithm

```python
def build_ordered_rules(rules: List[Rule], anchors: List[Anchor]) -> List[Rule]:
    # 1. Build dependency graph
    G = DiGraph()

    # Add anchor chain
    for i, anchor in enumerate(anchors[:-1]):
        G.add_edge(anchor, anchors[i+1])

    # Add rules with class ordering
    for rule in rules:
        next_anchor = get_next_anchor(rule.class_)
        G.add_edge(rule, next_anchor)

        # Specificity edges within class
        for other in rules:
            if other.class_ == rule.class_ and conflict(rule, other):
                if rule.specificity > other.specificity:
                    G.add_edge(rule, other)  # More specific first

    # 2. Topological sort
    sorted_nodes = topological_sort(G)

    # 3. Assign final orders
    result = []
    for node in sorted_nodes:
        if isinstance(node, Rule):
            node.final_order = base(node.class_) + len([
                r for r in result if r.class_ == node.class_
            ])
            result.append(node)

    return result
```

### D8: Validator Rules

Codes allocated in range **7970-7979** (see ADR 0118 D18 for rationale).

| Code | Severity | Rule |
|------|----------|------|
| `E7970` | Error | Rule missing `class` assignment |
| `E7971` | Error | Rule `place_before` target not found |
| `E7972` | Error | Circular dependency detected |
| `E7973` | Error | Class order violation (P₃ rule after P₅ rule) |
| `W7974` | Warning | Conflicting rules in same class without specificity order |
| `W7975` | Warning | Rule specificity = 0 (matches everything) |
| `E7976` | Error | Missing anchor for priority class |
| `E7977` | Error | DROP_ALL anchor not terminal (has rules after) |
| `E7978` | Error | Publication forward rule without policy_ref (F01) |
| `E7979` | Error | NAT rule without corresponding forward rule |

### D9: NAT Chain Ordering

Separate priority system for NAT chains:

| Class | Name | Order Range | Chain |
|-------|------|-------------|-------|
| N₁ | CONTAINER_DNAT | 0-99 | dstnat |
| N₂ | VPN_DNAT | 100-199 | dstnat |
| N₃ | GENERAL_DNAT | 200-299 | dstnat |

```hcl
# N1: Container DNAT (order: 0-99)
resource "routeros_ip_firewall_nat" "dnat_docker_adguard" {
  chain        = "dstnat"
  action       = "dst-nat"
  dst_address  = "192.168.88.210"
  to_addresses = "172.18.0.210"
  comment      = "ADR-0119 N1: Container DNAT"
}
```

## Consequences

### Benefits

1. **Deterministic ordering** — rules always in same order
2. **No conflicts** — class system prevents cross-source conflicts
3. **Specificity respected** — more specific rules execute first
4. **Formal verification** — mathematical invariants can be proven
5. **Generator independence** — each generator only knows its class
6. **Debuggable** — clear class assignment in comments

### Trade-offs

1. **Anchor overhead** — passthrough rules add slight overhead
2. **Class rigidity** — adding new class requires schema update
3. **Complexity** — more sophisticated than flat place_before

### Implementation Estimate

| Component | Files | Effort |
|-----------|-------|--------|
| Projection schema extension | 1 | 2h |
| Anchor generator | 1 | 2h |
| Rule ordering compiler | 1 | 4h |
| Security matrix generator update | 1 | 2h |
| Container exposure generator update | 1 | 2h |
| VPN generator update | 1 | 2h |
| Validators (E7890-E7897) | 1 | 3h |
| Tests | 3 | 4h |
| Migration (existing rules) | - | 2h |
| **Total** | ~11 | **~23h** |

### Migration Path

| Phase | Action | Risk |
|-------|--------|------|
| 1 | Add projection schema with anchors | None |
| 2 | Generate anchor rules in zone_firewall.tf | Low |
| 3 | Update security matrix generator | Low |
| 4 | Update container exposure generator | Low |
| 5 | Update VPN generator | Low |
| 6 | Enable validators | After migration |
| 7 | Deploy to MikroTik | **Medium** |

## References

- ADR-0110: Security Matrix and Trust Zone Configuration
- ADR-0118: Universal Container Network Model
- [MikroTik Firewall Filter](https://help.mikrotik.com/docs/display/ROS/Filter)
- [Terraform place_before](https://registry.terraform.io/providers/terraform-routeros/routeros/latest/docs/resources/ip_firewall_filter)

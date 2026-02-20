# ADR 0004: Enforce Explicit L2 Firewall Policy References and Validation Semantics

- Status: Accepted
- Date: 2026-02-20
- Supersedes: -

## Context

L2 networks introduced `firewall_policy_refs` to replace free-form policy labels.
However, schema validation still treated `L2_network.firewall_policies` as an untyped array, and validator checks only confirmed referenced IDs existed.

This left two gaps:

1. Firewall policy objects could be structurally inconsistent without schema failure.
2. A network could reference a firewall policy that targets a different source zone or source network.

For isolated trust zones, missing explicit firewall references also reduced policy intent visibility.

## Decision

1. Add a strict `FirewallPolicy` schema definition and apply it to `L2_network.firewall_policies`.
   Required fields: `id`, `action`, `chain`.
2. Keep `network.firewall_policy_refs` as explicit network-to-policy linkage.
3. Extend validator semantics for `firewall_policy_refs`:
   - referenced policy must exist;
   - non-global policy source must match the network (`source_network_ref == network.id` and/or `source_zone_ref == network.trust_zone_ref`);
   - duplicate references in `firewall_policy_refs` emit warning;
   - networks in isolated trust zones should define `firewall_policy_refs` (warning when missing).
4. Treat policies without source selectors (`source_zone_ref` and `source_network_ref`) as global policies allowed for any network.

## Consequences

Benefits:

- Stronger schema guarantees for firewall policy objects.
- Better semantic integrity between network intent and applied firewall rules.
- Clearer governance for isolated segments.

Trade-offs:

- Validator is stricter and can surface additional migration work for future topology changes.
- Policy authors must maintain source selectors consistently to avoid false associations.

Compatibility:

- Existing topology remains valid if referenced policies already align by source network/zone.
- Isolated zones without explicit `firewall_policy_refs` now produce warnings.

## References

- Files:
  - `topology-tools/schemas/topology-v4-schema.json`
  - `topology-tools/validate-topology.py`
  - `topology/L2-network/networks/net-guest.yaml`
  - `topology/L2-network/networks/net-iot.yaml`

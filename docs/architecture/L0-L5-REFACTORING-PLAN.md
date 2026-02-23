# L0-L5 Refactoring Plan (ADR-0040)

Status date: 2026-02-23
Scope: `L0` .. `L5`

## Goals

1. Remove cross-layer ownership leaks.
2. Keep one canonical source of truth for runtime placement data.
3. Preserve generator compatibility during migration.
4. Reduce long-term model drift and maintenance cost.

## Priority Matrix

### P0 (Immediate)

- [ ] L1 physical-only cleanup
  - Remove non-physical `services` hints from `L1` provider devices.
  - Remove legacy duplicated storage capability blocks where slot/media model is canonical.
- [ ] L5 runtime canonicalization
  - Keep canonical placement/image data only in `services[].runtime`.
  - Keep compatibility projection in generators/templates.
- [ ] Validation guardrails
  - Add/strengthen checks preventing runtime + legacy duplication in authored data.

### P1 (Near-term)

- [ ] Resolve IP source-of-truth split (`L2.ip_allocations` vs `L4.workloads[].networks[].ip`).
- [ ] Tighten `L2` typing (avoid string DSL patterns where possible).
- [ ] Align security intent (`protocol` vs certificate/TLS intent) for web services.

### P2 (Hardening)

- [ ] Enrich `L3.data_assets` taxonomy (`category`, `criticality`, `backup_policy_refs`) where applicable.
- [ ] Normalize metadata governance (`L0.metadata.last_updated` policy and automation).
- [ ] Reduce remaining compatibility-only template dependencies on legacy service fields.

## Execution Sequence

1. Ship `P0` topology and tooling changes with strict validation passing.
2. Regenerate docs/outputs and verify no generator regressions.
3. Proceed to `P1` in isolated commits (network model, security model, runtime/IP ownership).
4. Finish with `P2` governance/taxonomy hardening.

## Validation Gate

Run after each refactor batch:

```bash
python topology-tools/validate-topology.py --topology topology.yaml --strict
python topology-tools/generate-docs.py --topology topology.yaml --output generated/docs
python topology-tools/validate-mermaid-render.py --docs-dir generated/docs
```

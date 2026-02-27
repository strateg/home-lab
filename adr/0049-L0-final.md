# ADR 0049-FINAL: L0 Meta - Global Only

**Date:** 2026-02-26
**Status:** Proposed

---

## Context

**Error discovered:** L0 was becoming a central configuration hub

**Correct principle:** L0 = global only, each layer owns its layer-specific defaults

---

## Decision

### L0 Contains ONLY What Affects ALL Layers

```yaml
version: 4.0.0
compliance:
  gdpr_compliant: true
security_constraints:
  encryption_required: true
  min_tls_version: "1.2"
naming:
  device_pattern: "{type}-{location}-{number}"
  service_pattern: "svc-{domain}.{name}"
version_requirements:
  min_terraform: "1.0.0"
```

### Each Layer Has Its Own Meta

```
L1-meta/defaults.yaml    (device defaults)
L2-meta/defaults.yaml    (network defaults)
L3-meta/defaults.yaml    (storage defaults)
L4-meta/defaults.yaml    (compute defaults)
L5-meta/defaults.yaml    (sla, monitoring profiles)
L6-meta/defaults.yaml    (alert, log policies)
L7-meta/defaults.yaml    (incident, escalation policies)
```

---

## Benefits

✅ L0 is minimal (one file)
✅ No central hub problem
✅ Each layer independent
✅ Scalable (add service = add to L5-meta)
✅ Clean architecture

---

**Status: READY**

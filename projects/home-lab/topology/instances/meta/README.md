# L0-meta Layer

**Status:** Reserved (no active instances)

## Purpose

L0-meta is the foundational metadata layer in the OSI-like topology model.
It is reserved for:

- **Schema versioning** — topology schema version declarations
- **Global defaults** — default values inherited by all layers
- **Global policies** — cross-layer policy definitions (e.g., naming conventions, tagging rules)

## When to Populate

L0 instances should be introduced when the topology requires:

1. Multi-project support with shared global policies
2. Schema migration tracking across topology versions
3. Global default overrides (e.g., default backup policy, default trust zone)

## Prerequisites

Before creating L0 instances, define:

- `class.meta.*` class modules in `topology/class-modules/meta/`
- `obj.meta.*` object modules in `topology/object-modules/meta/`

## Cross-layer Relationship

L0-meta has no runtime_target_rules — it serves as a passive configuration source
referenced by other layers via inheritance or policy resolution.

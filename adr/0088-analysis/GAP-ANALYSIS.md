# GAP ANALYSIS — ADR 0088

## AS-IS (2026-04-06 fact snapshot)

1. Canonical semantic registry is active (`topology/semantic-keywords.yaml`) and all 11 tokens are canonical-only (`aliases: []`).
2. Strict YAML loader is active in core runtime entrypoints (no `yaml.safe_load` in `compile-topology.py`, `compiler_runtime.py`, `plugin_manifest_discovery.py`, `kernel/plugin_registry.py`).
3. ADR0088 diagnostic family is implemented (`E8801..E8806` in error catalog; runtime/tests include explicit mentions).
4. Active instance source path is canonical-only:
   - `projects/home-lab/topology/instances`: `class_ref=0`, `object_ref=0`
   - `@instance/@extends/@group/@version`: canonical in shard headers
   - `instance.@layer` and plain `group` are removed from canonical shard contract (derived-layer + service-key policy).
5. Gates are green:
   - compile: `errors=0`, `warnings=5`, `infos=81`
   - `validate-v5`: PASS
   - full tests: `911 passed, 4 skipped`
6. Residual deltas remain:
   - metadata coverage is uneven (class/object required metadata not yet uniformly present)
   - legacy key footprint exists in boundary-scoped historical area (`projects/home-lab/_legacy`: `class_ref=131`, `object_ref=131`)
   - compile warning profile is concentrated in `W7816` duplicate-IP warnings (5 entries).

## TO-BE (post-hardening target)

1. Canonical semantic-only runtime stays enforced; no alias rollback in active lane.
2. Metadata governance is explicit and measurable (coverage targets + phased gate: `warn -> gate-new -> enforce`).
3. Boundary-scoped legacy data remains explicit, fenced, and excluded from active cutover quality metrics.
4. Warning governance is explicit:
   - accepted warning classes are documented
   - escalation criteria from warning to error are defined and testable.

## Delta summary

| Area | Gap | Required change |
|---|---|---|
| Semantic contract | Runtime is strict, but policy text still under-specifies post-cutover governance | Add explicit post-cutover semantic-only continuity rule |
| Instance shard service keys | `group` previously existed as plain non-`@` service key in shard header | Lock canonical shard service key as `@group`; reject plain `group` in active lane |
| Metadata quality | Mandatory metadata coverage not uniformly achieved | Define coverage targets and phased enforcement gate |
| Legacy boundary | Legacy key usage persists in `_legacy` tree | Codify boundary-fenced handling as intentional/non-active |
| Warning policy | `W7816` profile exists without explicit policy gate | Add warning governance and escalation contract |

## Risk hotspots

1. Metadata enforcement can create large migration wave if moved directly to hard fail.
2. Warning escalation without explicit criteria can create unstable CI behavior.
3. Boundary confusion between active lane and `_legacy` can distort readiness reporting.

## Recommended boundaries

1. Preserve strict canonical semantics in active lane as non-regression constraint.
2. Treat `_legacy` as explicitly excluded from active semantic cutover compliance metrics.
3. Move metadata and warning policies via phased gates, not immediate hard fail across full repository.

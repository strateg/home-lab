# GAP ANALYSIS — ADR 0088

## AS-IS

1. Entity keys are hardcoded in tooling (`version`, `capability/id`, `schema`, `class`, `object`, `instance`, `title`, `summary`, `layer`, `description`, `class_ref`, `object_ref`).
2. Parent-link semantics are split (`class_ref` vs `object_ref`) instead of one unified relation.
3. Effective JSON does not expose complete lineage/materialization graph fields.
4. Runtime YAML parsing uses permissive `yaml.safe_load` call-sites without duplicate-key rejection contract.
5. ADR 0067 strict key policy and ADR 0088 transitional alias strategy are not yet formally reconciled.

## TO-BE

1. Semantic keyword registry controls canonical keywords and aliases, including `@version`, `@capability`, `@schema`, `@title`, `@summary`, `@layer`, `@description`.
2. Compiler/plugins resolve semantics through registry, not literals.
3. Unified `@extends` validators for all entities:
   - class -> parent class
   - object -> concrete class
   - instance -> object -> class
4. Effective JSON includes lineage and materialization paths.

## Delta summary

| Area | Gap | Required change |
|---|---|---|
| Authoring contract | Literal keys only, legacy `capability/id` style, weak metadata/version/capability signaling | Introduce canonical `@` keys (`@version`, `@capability`, `@schema`, `@class`, `@object`, `@instance`, `@extends`, `@title`, `@summary`, `@layer`, `@description`) + alias migration |
| Loader/runtime | Hardcoded key names | Registry-driven semantic resolution layer across compiler plugins |
| Validation | Missing unified extends typing + graph checks | New validators for hierarchy/materialization and target-type checks; resolver-backed validation API |
| Generation | Generators read legacy-shaped model assumptions | Migrate generators to normalized semantic effective model fields |
| Effective model | Limited graph metadata | Add lineage/materialization fields in emitted JSON |
| ADR governance | ADR0067 strict cutover vs ADR0088 staged aliases | Explicit partial-supersede statement and scoped transition contract |
| YAML parsing | No strict duplicate-key contract | Strict loader profile with deterministic diagnostics |

## Risk hotspots

1. ADR 0068 placeholder value markers use `@...` and may be confused with `@key` semantics.
2. Massive surface area (compiler + plugins + tests + fixtures).
3. Ambiguous documents if canonical and alias keys coexist in one node.
4. `@schema` may collide with existing file-level `schema` usage unless context-scoped.

## Recommended boundaries

1. Keep canonical effective JSON field names stable even if source YAML uses aliases.
2. Reject mixed canonical+alias duplicates in the same mapping node.
3. Enforce one semantic meaning per registry entry (no overlapping aliases).
4. Scope semantic resolution by context path (entity manifest root vs capability entry record), not by global key rename.

# Plugin Input View Specification

**Date:** 2026-05-29
**Source:** Phase 4 Plugin System Development Plan (P4.2)
**Status:** Draft Design

---

## Overview

The `input_view` manifest key allows plugins to declare partial data requirements, enabling the orchestrator to build minimal snapshots. This reduces memory consumption and improves parallel execution performance.

**Goals:**
- Reduce snapshot size by >30% for plugins with focused data needs
- Maintain full backward compatibility (optional feature)
- Enable predictable memory profiling per-plugin

---

## Manifest Schema

### Full Specification

```yaml
- id: base.validator.network_ip_overlap
  input_view:
    # Compiled JSON projection (JSONPath expressions)
    compiled_json:
      include:
        - "$.instances[?(@.object_ref=~/^network\\./)].network"
        - "$.instances[*].id"
      exclude: []  # Optional exclusion patterns

    # Raw YAML access
    raw_yaml: false  # Don't include raw_yaml in snapshot (default: true)

    # Subscription projections
    subscriptions:
      - from_plugin: base.compiler.instance_rows
        key: normalized_rows
        projection: "$.rows[?(@.layer=='L2')]"

    # Object map filtering
    object_map:
      include_refs:
        - "network.*"  # Glob patterns for object_ref
      exclude_refs: []

    # Class map filtering
    class_map:
      include_refs:
        - "network.*"
      exclude_refs: []
```

### Minimal Specification

```yaml
- id: base.generator.docs
  input_view:
    raw_yaml: false  # Simple: just exclude raw YAML
```

---

## InputViewSpec Dataclass

```python
@dataclass(frozen=True)
class SubscriptionProjection:
    """Projection specification for a consumed data key."""
    from_plugin: str
    key: str
    projection: str  # JSONPath expression

@dataclass(frozen=True)
class CompiledJsonView:
    """Projection specification for compiled_json data."""
    include: tuple[str, ...] = ()  # JSONPath include patterns
    exclude: tuple[str, ...] = ()  # JSONPath exclude patterns

@dataclass(frozen=True)
class MapFilterView:
    """Projection specification for class_map/object_map."""
    include_refs: tuple[str, ...] = ()  # Glob patterns
    exclude_refs: tuple[str, ...] = ()  # Glob patterns

@dataclass(frozen=True)
class InputViewSpec:
    """Typed specification for plugin input data requirements."""
    compiled_json: CompiledJsonView | None = None
    raw_yaml: bool = True  # Include raw YAML by default
    subscriptions: tuple[SubscriptionProjection, ...] = ()
    object_map: MapFilterView | None = None
    class_map: MapFilterView | None = None

    @property
    def has_filters(self) -> bool:
        """Check if any filtering is specified."""
        return (
            self.compiled_json is not None
            or not self.raw_yaml
            or len(self.subscriptions) > 0
            or self.object_map is not None
            or self.class_map is not None
        )
```

---

## Snapshot Building Logic

### Current Behavior (No input_view)

```python
def build_input_snapshot(ctx: PluginContext, spec: PluginSpec) -> PluginInputSnapshot:
    """Build full snapshot with all data."""
    return PluginInputSnapshot(
        compiled_json=ctx.compiled_json,        # Full model
        raw_yaml=ctx.raw_yaml,                  # All raw YAML
        object_map=ctx.object_map,              # Full object map
        class_map=ctx.class_map,                # Full class map
        subscribed_data=resolve_subscriptions(ctx, spec),
    )
```

### Proposed Behavior (With input_view)

```python
def build_filtered_snapshot(
    ctx: PluginContext,
    spec: PluginSpec,
    input_view: InputViewSpec | None,
) -> PluginInputSnapshot:
    """Build minimal snapshot based on input_view declaration."""

    # If no input_view, return full snapshot (backward compatible)
    if input_view is None or not input_view.has_filters:
        return build_full_snapshot(ctx, spec)

    # Apply compiled_json projection
    compiled_json = ctx.compiled_json
    if input_view.compiled_json:
        compiled_json = apply_jsonpath_filter(
            ctx.compiled_json,
            include=input_view.compiled_json.include,
            exclude=input_view.compiled_json.exclude,
        )

    # Apply raw_yaml filter
    raw_yaml = ctx.raw_yaml if input_view.raw_yaml else {}

    # Apply object_map filter
    object_map = ctx.object_map
    if input_view.object_map:
        object_map = filter_map_by_refs(
            ctx.object_map,
            include=input_view.object_map.include_refs,
            exclude=input_view.object_map.exclude_refs,
        )

    # Apply class_map filter
    class_map = ctx.class_map
    if input_view.class_map:
        class_map = filter_map_by_refs(
            ctx.class_map,
            include=input_view.class_map.include_refs,
            exclude=input_view.class_map.exclude_refs,
        )

    # Apply subscription projections
    subscribed_data = resolve_subscriptions_with_projections(
        ctx, spec, input_view.subscriptions
    )

    return PluginInputSnapshot(
        compiled_json=compiled_json,
        raw_yaml=raw_yaml,
        object_map=object_map,
        class_map=class_map,
        subscribed_data=subscribed_data,
    )
```

---

## JSONPath Implementation

### Supported Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `$` | `$.instances` | Root object |
| `.` | `$.instances.network` | Child member |
| `[*]` | `$.instances[*]` | All array elements |
| `[n]` | `$.instances[0]` | Array index |
| `[?()]` | `$.instances[?(@.layer=='L2')]` | Filter expression |
| `..` | `$..network` | Recursive descent |

### Implementation Options

1. **jsonpath-ng** (Recommended)
   - Pure Python, no C dependencies
   - Good JSONPath compliance
   - ~100KB footprint

2. **jmespath** (Alternative)
   - AWS-backed, well-maintained
   - Different syntax from JSONPath
   - Requires translation layer

3. **Custom minimal parser** (If dependencies constrained)
   - Support only `$`, `.`, `[*]`, `[?()]`
   - ~200 LOC implementation
   - Fastest for simple patterns

---

## Validation Rules

### Manifest Validation

1. **JSONPath syntax validation**
   ```python
   def validate_jsonpath(path: str) -> bool:
       """Validate JSONPath expression syntax."""
       try:
           jsonpath_ng.parse(path)
           return True
       except JsonPathParserError:
           return False
   ```

2. **Subscription reference validation**
   ```python
   def validate_subscription_projection(
       projection: SubscriptionProjection,
       registry: PluginRegistry,
   ) -> list[str]:
       """Validate subscription projection references."""
       errors = []

       # Verify from_plugin exists
       if projection.from_plugin not in registry.specs:
           errors.append(f"Unknown plugin: {projection.from_plugin}")

       # Verify key is in produces
       spec = registry.specs.get(projection.from_plugin)
       if spec and projection.key not in [p.key for p in spec.produces]:
           errors.append(f"Key '{projection.key}' not produced by {projection.from_plugin}")

       # Verify projection syntax
       if not validate_jsonpath(projection.projection):
           errors.append(f"Invalid JSONPath: {projection.projection}")

       return errors
   ```

3. **Glob pattern validation**
   ```python
   def validate_glob_pattern(pattern: str) -> bool:
       """Validate glob pattern syntax."""
       try:
           fnmatch.translate(pattern)
           return True
       except Exception:
           return False
   ```

---

## Performance Considerations

### Memory Savings Estimation

| Data Source | Full Size | Filtered (Est.) | Savings |
|-------------|-----------|-----------------|---------|
| compiled_json | ~2MB | ~200KB | 90% |
| raw_yaml | ~500KB | 0 (if excluded) | 100% |
| object_map | ~100KB | ~20KB | 80% |
| subscribed_data | Variable | Variable | 30-50% |

**Total estimated savings:** 30-50% for focused plugins

### Caching Strategy

```python
class FilteredSnapshotCache:
    """Cache filtered snapshots by (plugin_id, input_view_hash)."""

    def __init__(self, max_size: int = 100):
        self._cache: dict[tuple[str, int], PluginInputSnapshot] = {}
        self._max_size = max_size

    def get_or_build(
        self,
        plugin_id: str,
        input_view: InputViewSpec,
        builder: Callable[[], PluginInputSnapshot],
    ) -> PluginInputSnapshot:
        key = (plugin_id, hash(input_view))
        if key not in self._cache:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            self._cache[key] = builder()
        return self._cache[key]
```

---

## Migration Strategy

### Phase 1: Schema and Validation (Current)

1. Define `InputViewSpec` dataclass in `plugin_base.py`
2. Add manifest schema extension for `input_view`
3. Implement validation in manifest loader
4. No runtime behavior change yet

### Phase 2: Runtime Implementation

1. Implement `build_filtered_snapshot()` in snapshot builder
2. Add JSONPath dependency (`jsonpath-ng`)
3. Enable filtering for plugins with `input_view` declarations
4. Measure memory reduction

### Phase 3: Gradual Rollout

1. Add `input_view` to high-memory validators first
2. Monitor performance and correctness
3. Document patterns in authoring guide
4. Consider auto-detection of minimal requirements

---

## Example Plugin Migrations

### Validator with Focused Data Needs

```yaml
# Before: Gets full 2MB compiled_json
- id: base.validator.network_ip_overlap
  consumes:
    - from_plugin: base.compiler.instance_rows
      key: normalized_rows

# After: Gets ~50KB filtered data
- id: base.validator.network_ip_overlap
  input_view:
    compiled_json:
      include:
        - "$.instances[?(@.object_ref=~/^network\\./)].network"
    raw_yaml: false
    subscriptions:
      - from_plugin: base.compiler.instance_rows
        key: normalized_rows
        projection: "$.rows[?(@.layer=='L2')]"
  consumes:
    - from_plugin: base.compiler.instance_rows
      key: normalized_rows
```

### Generator Excluding Raw YAML

```yaml
# Before: Gets raw_yaml even though unused
- id: base.generator.docs
  consumes:
    - from_plugin: base.compiler.effective_model
      key: effective_json

# After: Excludes raw_yaml
- id: base.generator.docs
  input_view:
    raw_yaml: false
  consumes:
    - from_plugin: base.compiler.effective_model
      key: effective_json
```

---

## Acceptance Criteria

- [ ] `InputViewSpec` dataclass defined in plugin_base.py
- [ ] Manifest schema extended with input_view key
- [ ] Validation errors for invalid JSONPath syntax
- [ ] Validation errors for invalid subscription references
- [ ] Backward compatible (plugins without input_view unchanged)
- [ ] At least 2 plugins migrated with input_view
- [ ] Snapshot size reduction measured (target: >30%)

---

## Related Documents

- [ADR 0097: Plugin Execution Model](../../adr/0097-plugin-execution-model.md)
- [PLUGIN-ENVELOPE-MODEL.md](./PLUGIN-ENVELOPE-MODEL.md)
- [PLUGIN_AUTHORING_GUIDE.md](../PLUGIN_AUTHORING_GUIDE.md)

---

## Implementation Status

| Task | Status | Notes |
|------|--------|-------|
| Design specification | Complete | This document |
| InputViewSpec dataclass | Complete | `kernel/plugin_base.py` |
| PluginSpec.input_view field | Complete | `kernel/plugin_registry.py` |
| Manifest parsing | Complete | `PluginSpec._parse_input_view()` |
| JSONPath validation | Pending | Runtime validation |
| Runtime filtering | Pending | `build_filtered_snapshot()` |
| Plugin migrations | Pending | Add input_view to manifests |

### Files Modified

- `topology-tools/kernel/plugin_base.py`
  - Added `SubscriptionProjection` dataclass
  - Added `CompiledJsonView` dataclass
  - Added `MapFilterView` dataclass
  - Added `InputViewSpec` dataclass with `has_filters` property

- `topology-tools/kernel/plugin_registry.py`
  - Added `input_view: InputViewSpec | None` field to `PluginSpec`
  - Added `_parse_input_view()` static method for manifest parsing

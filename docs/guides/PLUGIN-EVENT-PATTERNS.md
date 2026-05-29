# Plugin Event Patterns

**Date:** 2026-05-29
**Source:** ADR 0097, Phase 4 Plugin System Development Plan
**Purpose:** Document asynchronous plugin communication patterns via event plane

---

## Overview

The event plane provides loose coupling between plugins through topic-based pub/sub messaging. Unlike the data plane (publish/subscribe with depends_on), events are:
- **Transient** - consumed once, not persisted
- **Loosely Coupled** - no depends_on required
- **Topic-based** - multiple subscribers per topic

---

## API Reference

### Emitting Events

```python
def emit(self, topic: str, payload: Any) -> None:
    """Emit an event to a topic."""
```

### Subscribing to Topics

```python
def subscribe_topic(self, topic: str) -> None:
    """Subscribe to receive events on a topic."""
```

### Polling Events

```python
def poll_events(self, topic: str | None = None) -> list[EventMessage]:
    """Poll and consume pending events."""
```

### Event History (Debug)

```python
def get_event_history(self, topic: str | None = None) -> list[EventMessage]:
    """Get all emitted events (doesn't consume)."""
```

### EventMessage Structure

```python
@dataclass(frozen=True)
class EventMessage:
    topic: str
    payload: Any
    source_plugin: str
    stage: Stage
    phase: Phase
    timestamp_ns: int  # monotonic nanoseconds
```

---

## Pattern 1: Progress Reporting

Report execution progress for long-running plugins.

### Emitter (Generator)

```python
class LargeFileGenerator(PluginBase):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        files = self.get_files_to_generate()
        total = len(files)

        for i, file in enumerate(files):
            # Report progress
            ctx.emit("progress", {
                "plugin_id": self.id,
                "current": i + 1,
                "total": total,
                "percent": int((i + 1) / total * 100),
                "message": f"Generating {file.name}",
            })

            self.generate_file(file)

        return self.make_result()
```

### Consumer (Orchestrator/Monitor)

```python
class ProgressMonitor(PluginBase):
    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Subscribe to progress events
        ctx.subscribe_topic("progress")
        return PluginResult.success(self.id)

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Collect all progress events
        events = ctx.poll_events("progress")

        summary = {}
        for event in events:
            plugin_id = event.payload.get("plugin_id")
            summary[plugin_id] = event.payload.get("percent", 0)

        return self.make_result(output_data={"progress_summary": summary})
```

### Topic Convention

```
progress
progress.<plugin_id>  # For plugin-specific filtering
```

---

## Pattern 2: Artifact Notification

Notify downstream plugins when artifacts are generated.

### Emitter (Generator)

```python
class TerraformGenerator(PluginBase):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        output_dir = self.generate_terraform(ctx)

        # Notify artifact creation
        ctx.emit("artifact.generated", {
            "type": "terraform",
            "path": str(output_dir),
            "files": ["main.tf", "variables.tf", "outputs.tf"],
            "provider": "proxmox",
        })

        return self.make_result()
```

### Consumer (Assembler)

```python
class ArtifactCollector(PluginBase):
    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        ctx.subscribe_topic("artifact.generated")
        return PluginResult.success(self.id)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        artifacts = ctx.poll_events("artifact.generated")

        manifest = {
            "artifacts": [
                {
                    "type": event.payload["type"],
                    "path": event.payload["path"],
                    "source_plugin": event.source_plugin,
                }
                for event in artifacts
            ]
        }

        return self.make_result(output_data=manifest)
```

### Topic Convention

```
artifact.generated
artifact.generated.<type>  # e.g., artifact.generated.terraform
artifact.validated
artifact.packaged
```

---

## Pattern 3: Cross-Stage Notifications

Communicate between plugins in different stages.

### Emitter (Compiler)

```python
class SchemaCompiler(PluginBase):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        schemas = self.compile_schemas(ctx)

        # Notify validators that schemas are ready
        ctx.emit("schema.compiled", {
            "schema_count": len(schemas),
            "schema_ids": list(schemas.keys()),
        })

        ctx.publish("compiled_schemas", schemas)
        return self.make_result()
```

### Consumer (Validator - Different Stage)

```python
class SchemaValidator(PluginBase):
    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Subscribe early to catch cross-stage events
        ctx.subscribe_topic("schema.compiled")
        return PluginResult.success(self.id)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Check if schemas were compiled
        schema_events = ctx.poll_events("schema.compiled")

        if not schema_events:
            # Schemas not compiled - skip or warn
            return PluginResult.skipped(self.id)

        # Proceed with validation
        schemas = ctx.subscribe("compiler.schemas", "compiled_schemas")
        # ...
```

### Topic Convention

```
<stage>.<action>
compile.complete
validate.started
generate.complete
```

---

## Pattern 4: Diagnostic Aggregation

Collect diagnostics from multiple plugins.

### Emitter (Any Plugin)

```python
class NetworkValidator(PluginBase):
    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics = []

        for issue in self.find_issues(ctx):
            diag = self.emit_diagnostic(
                code=issue.code,
                severity=issue.severity,
                stage=stage,
                message=issue.message,
                path=issue.path,
            )
            diagnostics.append(diag)

            # Also emit as event for aggregation
            ctx.emit("diagnostic", {
                "code": issue.code,
                "severity": issue.severity,
                "plugin_id": self.id,
                "path": issue.path,
            })

        return self.make_result(diagnostics=diagnostics)
```

### Consumer (Aggregator)

```python
class DiagnosticAggregator(PluginBase):
    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        ctx.subscribe_topic("diagnostic")
        return PluginResult.success(self.id)

    def on_finalize(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        events = ctx.poll_events("diagnostic")

        # Group by severity
        by_severity = {"error": [], "warning": [], "info": []}
        for event in events:
            severity = event.payload.get("severity", "info")
            by_severity[severity].append(event.payload)

        summary = {
            "errors": len(by_severity["error"]),
            "warnings": len(by_severity["warning"]),
            "info": len(by_severity["info"]),
            "details": by_severity,
        }

        return self.make_result(output_data={"diagnostic_summary": summary})
```

### Topic Convention

```
diagnostic
diagnostic.error
diagnostic.warning
diagnostic.info
```

---

## Pattern 5: Plugin Coordination

Coordinate execution between parallel plugins.

### Coordinator

```python
class ResourceAllocator(PluginBase):
    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        ctx.subscribe_topic("resource.request")
        return PluginResult.success(self.id)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        requests = ctx.poll_events("resource.request")

        allocations = {}
        for request in requests:
            plugin_id = request.source_plugin
            resource_type = request.payload["type"]
            allocations[plugin_id] = self.allocate(resource_type)

            ctx.emit("resource.allocated", {
                "requester": plugin_id,
                "type": resource_type,
                "allocation": allocations[plugin_id],
            })

        return self.make_result()
```

### Requester

```python
class VMGenerator(PluginBase):
    def on_pre(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Request resources before main execution
        ctx.emit("resource.request", {
            "type": "ip_address",
            "count": 5,
        })
        ctx.subscribe_topic("resource.allocated")
        return PluginResult.success(self.id)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        # Wait for allocation
        allocations = ctx.poll_events("resource.allocated")
        my_allocation = next(
            (e for e in allocations if e.payload["requester"] == self.id),
            None
        )

        if my_allocation:
            ips = my_allocation.payload["allocation"]
            # Use allocated IPs
```

---

## Best Practices

### Topic Naming

```
# Pattern: <domain>.<action>
progress              # Generic progress
progress.file         # File-specific progress
artifact.generated    # Artifact lifecycle
artifact.validated
diagnostic            # All diagnostics
diagnostic.error      # Severity-specific
compile.started       # Stage lifecycle
compile.complete
```

### Event Payload Guidelines

1. **Keep payloads small** - avoid embedding large data
2. **Include source context** - plugin_id, stage, timestamp
3. **Use consistent schemas** - document expected fields
4. **Make payloads JSON-serializable** - for subinterpreter compatibility

### Subscription Timing

```python
# Subscribe in on_init (before main execution)
def on_init(self, ctx, stage):
    ctx.subscribe_topic("my.topic")
    return PluginResult.success(self.id)

# Poll in execute or on_finalize
def execute(self, ctx, stage):
    events = ctx.poll_events("my.topic")
```

### Error Handling

```python
events = ctx.poll_events("expected.topic")
if not events:
    # Handle missing events gracefully
    self.logger.warning("No events received for topic")
    # Either skip, use defaults, or emit warning diagnostic
```

---

## Comparison: Data Plane vs Event Plane

| Aspect | Data Plane | Event Plane |
|--------|------------|-------------|
| Coupling | Tight (depends_on) | Loose (topic-based) |
| Persistence | Yes (ctx storage) | No (transient) |
| Delivery | Guaranteed | Best-effort |
| Use Case | Required data flow | Optional notifications |
| Declaration | consumes/produces | subscribe_topic/emit |

### When to Use Data Plane

- Required input data for plugin execution
- Type-safe contracts between plugins
- Data that must persist across stages

### When to Use Event Plane

- Progress reporting
- Optional notifications
- Cross-plugin coordination
- Diagnostic aggregation
- Loose coupling scenarios

---

## Related Documents

- [ADR 0097: Plugin Execution Model](../../adr/0097-plugin-execution-model.md)
- [PLUGIN_AUTHORING_GUIDE.md](../PLUGIN_AUTHORING_GUIDE.md)
- [PLUGIN-ENVELOPE-MODEL.md](./PLUGIN-ENVELOPE-MODEL.md)

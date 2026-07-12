"""PipelineState <-> PluginContext bridge (ADR 0097 D13 compatibility shim).

Mirrors legacy context mutations into scheduler-owned PipelineState and
exposes committed pipeline state back through legacy context accessors.
Also applies main-interpreter-owned authoritative state (class/object maps,
compiled JSON candidate, assembly metadata) derived from committed outputs.

D13 quarantine note: this module exists only to keep the legacy
PluginContext data surface consistent while plugins migrate to the
envelope/snapshot model. It is scheduled for removal together with the
`thread_legacy` execution mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..pipeline_runtime import PipelineState

if TYPE_CHECKING:
    from ..plugin_base import PluginContext
    from ..specs import PluginSpec

__all__ = [
    "ensure_pipeline_state",
    "mirror_context_into_pipeline_state",
    "sync_pipeline_state_to_context",
    "apply_authoritative_commit_side_effects",
]


def ensure_pipeline_state(ctx: PluginContext) -> PipelineState:
    """Return main-interpreter pipeline state for the current execution context."""
    pipeline_state = getattr(ctx, "_pipeline_state", None)
    if isinstance(pipeline_state, PipelineState):
        return pipeline_state

    pipeline_state = PipelineState(
        committed_data=ctx.get_published_data(),
        published_meta=ctx._published_meta.copy(),
    )
    setattr(ctx, "_pipeline_state", pipeline_state)
    return pipeline_state


def mirror_context_into_pipeline_state(ctx: PluginContext, pipeline_state: PipelineState) -> None:
    """Refresh scheduler-owned state from legacy context mutations."""
    pipeline_state.committed_data = ctx.get_published_data()
    pipeline_state.published_meta = ctx._published_meta.copy()


def sync_pipeline_state_to_context(ctx: PluginContext, pipeline_state: PipelineState) -> None:
    """Expose committed pipeline state through legacy context accessors."""
    ctx._published_data = {
        plugin_id: payload.copy() for plugin_id, payload in pipeline_state.committed_data.items()
    }
    ctx._published_meta = pipeline_state.published_meta.copy()
    setattr(ctx, "_pipeline_state", pipeline_state)


def apply_authoritative_commit_side_effects(
    *,
    ctx: PluginContext,
    pipeline_state: PipelineState,
    spec: PluginSpec,
) -> None:
    """Apply main-interpreter-owned authoritative state derived from committed outputs."""
    plugin_payload = pipeline_state.committed_data.get(spec.id, {})
    if not isinstance(plugin_payload, dict):
        return

    class_map = plugin_payload.get("class_map")
    object_map = plugin_payload.get("object_map")
    if isinstance(class_map, dict):
        ctx.classes = {
            class_id: item["payload"]
            for class_id, item in class_map.items()
            if isinstance(class_id, str) and isinstance(item, dict) and isinstance(item.get("payload"), dict)
        }
    if isinstance(object_map, dict):
        ctx.objects = {
            object_id: item["payload"]
            for object_id, item in object_map.items()
            if isinstance(object_id, str) and isinstance(item, dict) and isinstance(item.get("payload"), dict)
        }

    if spec.compiled_json_owner:
        candidate = plugin_payload.get("effective_model_candidate")
        if isinstance(candidate, dict):
            ctx.compiled_json = candidate

    changed_input_scopes = plugin_payload.get("changed_input_scopes")
    if isinstance(changed_input_scopes, list):
        normalized = [item for item in changed_input_scopes if isinstance(item, str) and item]
        ctx.changed_input_scopes = normalized
        ctx.config["changed_input_scopes"] = normalized

    assembly_dir = plugin_payload.get("assembly_dir")
    if isinstance(assembly_dir, str) and assembly_dir.strip():
        ctx.workspace_root = assembly_dir

    assembly_manifest = plugin_payload.get("assembly_manifest")
    if isinstance(assembly_manifest, dict):
        ctx.assembly_manifest = assembly_manifest

    # ADR 0097 P4.1: Commit lock_payload to ctx.model_lock for subinterpreter compatibility.
    lock_payload = plugin_payload.get("lock_payload")
    if isinstance(lock_payload, dict):
        ctx.model_lock = lock_payload

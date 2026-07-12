"""Stage preflight gates: model-version and capability validation (S6).

Kernel-level gates evaluated before any plugin of a stage executes
(ADR 0063 decomposition, PLUGIN-REGISTRY-DECOMPOSITION-PLAN-2026-07-07 S6):

- model-version gate: E4011 (unsupported core_model_version, kernel-level
  or per-plugin) and E4012 (plugin declares model_versions but the lock
  provides no core_model_version)
- capability gate: E4010 (required capabilities not provided by any
  active plugin)

Predicate callables (`profile_allows`, `when_allows`) are passed in by the
caller so gate evaluation honors registry-instance patch points. This
surface is normalized in S9 together with the facade private delegates.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable, Optional

from ..plugin_base import Phase, PluginDiagnostic
from ..specs import MODEL_VERSIONS, PluginSpec

if TYPE_CHECKING:
    from ..plugin_base import PluginContext, Stage

__all__ = [
    "normalize_model_version",
    "is_model_version_compatible",
    "is_model_version_in_set",
    "validate_model_versions",
    "validate_required_capabilities",
]


def normalize_model_version(token: str) -> str | None:
    """Normalize a model version token to '<major>.<minor>' (None if invalid)."""
    if not isinstance(token, str):
        return None
    candidate = token.strip()
    if not candidate:
        return None
    match = re.search(r"(\d+)\.(\d+)", candidate)
    if not match:
        return None
    return f"{int(match.group(1))}.{int(match.group(2))}"


def is_model_version_compatible(core_model_version: str) -> bool:
    """Check core_model_version against kernel MODEL_VERSIONS."""
    normalized_core = normalize_model_version(core_model_version)
    if normalized_core is None:
        return False
    supported = {
        normalized
        for normalized in (normalize_model_version(item) for item in MODEL_VERSIONS)
        if normalized is not None
    }
    return normalized_core in supported


def is_model_version_in_set(core_model_version: str, allowed_versions: list[str]) -> bool:
    """Check core_model_version against a plugin's declared model_versions."""
    normalized_core = normalize_model_version(core_model_version)
    if normalized_core is None:
        return False
    normalized_allowed = {
        normalized
        for normalized in (normalize_model_version(item) for item in allowed_versions)
        if normalized is not None
    }
    return normalized_core in normalized_allowed


def validate_model_versions(
    *,
    stage: Stage,
    ctx: PluginContext,
    active_plugin_ids: list[str],
    specs: dict[str, PluginSpec],
) -> list[PluginDiagnostic]:
    """Validate model version compatibility for active plugins.

    Returns list of diagnostics (empty if all pass).
    """
    diagnostics: list[PluginDiagnostic] = []
    core_model_version = ctx.model_lock.get("core_model_version") if isinstance(ctx.model_lock, dict) else None

    # Check kernel supports this model version
    if isinstance(core_model_version, str) and core_model_version:
        if not is_model_version_compatible(core_model_version):
            diagnostics.append(
                PluginDiagnostic(
                    code="E4011",
                    severity="error",
                    stage=stage.value,
                    phase=Phase.RUN.value,
                    message=(
                        f"Unsupported core_model_version '{core_model_version}'. "
                        f"Kernel supports: {MODEL_VERSIONS}"
                    ),
                    path="model.lock:core_model_version",
                    plugin_id="kernel",
                )
            )
            return diagnostics  # Early return - kernel incompatibility

    # Check per-plugin model_versions declarations
    for plugin_id in active_plugin_ids:
        spec = specs.get(plugin_id)
        if not isinstance(spec, PluginSpec):
            continue
        declared_model_versions = [item for item in spec.model_versions if isinstance(item, str) and item.strip()]
        if not declared_model_versions:
            continue
        if not isinstance(core_model_version, str) or not core_model_version:
            diagnostics.append(
                PluginDiagnostic(
                    code="E4012",
                    severity="error",
                    stage=stage.value,
                    phase=Phase.RUN.value,
                    message=(
                        f"Plugin '{plugin_id}' declares model_versions={declared_model_versions}, "
                        "but model.lock core_model_version is unavailable."
                    ),
                    path=f"plugin:{plugin_id}",
                    plugin_id="kernel",
                )
            )
            continue
        if not is_model_version_in_set(core_model_version, declared_model_versions):
            diagnostics.append(
                PluginDiagnostic(
                    code="E4011",
                    severity="error",
                    stage=stage.value,
                    phase=Phase.RUN.value,
                    message=(
                        f"Plugin '{plugin_id}' does not support core_model_version "
                        f"'{core_model_version}'. Supported by plugin: {declared_model_versions}"
                    ),
                    path=f"plugin:{plugin_id}",
                    plugin_id="kernel",
                )
            )
    return diagnostics


def validate_required_capabilities(
    *,
    stage: Stage,
    ctx: PluginContext,
    profile: Optional[str],
    active_plugin_ids: list[str],
    specs: dict[str, PluginSpec],
    profile_allows: Callable[[PluginSpec, Optional[str]], bool],
    when_allows: Callable[[PluginSpec, PluginContext], bool],
) -> list[PluginDiagnostic]:
    """Validate that all required capabilities are available.

    Returns list of diagnostics (empty if all pass).
    """
    # Collect available capabilities from active plugins
    available_capabilities: set[str] = set()
    for spec in specs.values():
        if not profile_allows(spec, profile):
            continue
        if not when_allows(spec, ctx):
            continue
        for capability in spec.capabilities:
            if isinstance(capability, str) and capability:
                available_capabilities.add(capability)

    # Check each plugin's requires_capabilities
    diagnostics: list[PluginDiagnostic] = []
    for plugin_id in active_plugin_ids:
        spec = specs.get(plugin_id)
        if not isinstance(spec, PluginSpec):
            continue
        missing = sorted(
            capability
            for capability in spec.requires_capabilities
            if isinstance(capability, str) and capability and capability not in available_capabilities
        )
        if missing:
            diagnostics.append(
                PluginDiagnostic(
                    code="E4010",
                    severity="error",
                    stage=stage.value,
                    message=(
                        f"Plugin '{plugin_id}' requires missing capabilities: {missing}. "
                        "Provide capability-producing plugins or adjust requires_capabilities."
                    ),
                    path=f"plugin:{plugin_id}",
                    plugin_id="kernel",
                )
            )
    return diagnostics

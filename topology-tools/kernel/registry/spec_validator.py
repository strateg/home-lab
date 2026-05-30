"""Plugin specification validator (ADR 0063 registry decomposition).

This module validates plugin specifications against kernel contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..plugin_base import Phase, PluginKind, Stage

if TYPE_CHECKING:
    from ..plugin_registry import PluginSpec

__all__ = ["SpecValidator", "SpecValidationError"]

# Kernel version constants
SUPPORTED_API_VERSIONS = ["1.x"]

# Stage ordering
STAGE_ORDER: tuple[Stage, ...] = (
    Stage.DISCOVER,
    Stage.COMPILE,
    Stage.VALIDATE,
    Stage.GENERATE,
    Stage.ASSEMBLE,
    Stage.BUILD,
)

PHASE_ORDER: tuple[Phase, ...] = (
    Phase.INIT,
    Phase.PRE,
    Phase.RUN,
    Phase.POST,
    Phase.VERIFY,
    Phase.FINALIZE,
)

# Stage order ranges for validation
STAGE_ORDER_RANGES: dict[Stage, tuple[int, int]] = {
    Stage.DISCOVER: (10, 89),
    Stage.COMPILE: (30, 89),
    Stage.VALIDATE: (90, 189),
    Stage.GENERATE: (190, 399),
    Stage.ASSEMBLE: (400, 499),
    Stage.BUILD: (500, 599),
}

# Kind to stage affinity mapping
KIND_STAGE_AFFINITY: dict[PluginKind, set[Stage]] = {
    PluginKind.DISCOVERER: {Stage.DISCOVER},
    PluginKind.COMPILER: {Stage.COMPILE},
    PluginKind.VALIDATOR_YAML: {Stage.VALIDATE},
    PluginKind.VALIDATOR_JSON: {Stage.VALIDATE},
    PluginKind.GENERATOR: {Stage.GENERATE},
    PluginKind.ASSEMBLER: {Stage.ASSEMBLE},
    PluginKind.BUILDER: {Stage.BUILD},
}

# Kind to entry family mapping
KIND_ENTRY_FAMILY: dict[PluginKind, str] = {
    PluginKind.DISCOVERER: "discoverers",
    PluginKind.COMPILER: "compilers",
    PluginKind.VALIDATOR_YAML: "validators",
    PluginKind.VALIDATOR_JSON: "validators",
    PluginKind.GENERATOR: "generators",
    PluginKind.ASSEMBLER: "assemblers",
    PluginKind.BUILDER: "builders",
}

ENTRY_FAMILIES: set[str] = set(KIND_ENTRY_FAMILY.values())


class SpecValidationError(Exception):
    """Plugin specification validation error."""

    def __init__(self, plugin_id: str, message: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"Plugin '{plugin_id}': {message}")


class SpecValidator:
    """Validate plugin specifications against kernel contracts."""

    def __init__(self, existing_specs: dict[str, PluginSpec] | None = None) -> None:
        """Initialize validator.

        Args:
            existing_specs: Dictionary of already registered specs (for duplicate/conflict detection)
        """
        self._specs = existing_specs if existing_specs is not None else {}

    def validate(self, spec: PluginSpec) -> None:
        """Validate plugin specification.

        Raises:
            SpecValidationError: If validation fails
        """
        self._validate_api_version(spec)
        self._validate_stage_affinity(spec)
        self._validate_entry_family(spec)
        self._validate_order_range(spec)
        self._validate_compiled_json_owner(spec)

    def _validate_api_version(self, spec: PluginSpec) -> None:
        """Validate API version compatibility."""
        if not self._is_api_compatible(spec.api_version):
            raise SpecValidationError(
                spec.id,
                f"Incompatible API version {spec.api_version}, "
                f"kernel supports {SUPPORTED_API_VERSIONS}",
            )

    def _validate_stage_affinity(self, spec: PluginSpec) -> None:
        """Validate kind-stage affinity."""
        allowed_stages = KIND_STAGE_AFFINITY.get(spec.kind, set())
        for stage in spec.stages:
            if stage not in allowed_stages:
                raise SpecValidationError(
                    spec.id,
                    f"kind '{spec.kind.value}' cannot run in stage '{stage.value}' "
                    f"(allowed stages: {[s.value for s in sorted(allowed_stages, key=lambda x: x.value)]})",
                )

    def _validate_entry_family(self, spec: PluginSpec) -> None:
        """Validate entry path uses correct plugin family."""
        if self._entry_uses_plugins_prefix_without_family(spec.entry):
            raise SpecValidationError(
                spec.id,
                f"entry '{spec.entry}' must include plugin family segment "
                "(expected plugins/<family>/module.py:ClassName)",
            )

        entry_family = self._extract_entry_plugin_family(spec.entry)
        expected_family = KIND_ENTRY_FAMILY.get(spec.kind)
        if entry_family and expected_family and entry_family != expected_family:
            raise SpecValidationError(
                spec.id,
                f"entry '{spec.entry}' must use plugins/{expected_family}/ for kind "
                f"'{spec.kind.value}' (got plugins/{entry_family}/)",
            )

    def _validate_order_range(self, spec: PluginSpec) -> None:
        """Validate order is within allowed range for stages."""
        for stage in spec.stages:
            order_range = STAGE_ORDER_RANGES.get(stage)
            if order_range is None:
                continue
            min_order, max_order = order_range
            if not (min_order <= spec.order <= max_order):
                raise SpecValidationError(
                    spec.id,
                    f"order {spec.order} is outside allowed range {min_order}-{max_order} "
                    f"for stage '{stage.value}'",
                )

    def _validate_compiled_json_owner(self, spec: PluginSpec) -> None:
        """Validate no conflicts with compiled_json_owner."""
        if not spec.compiled_json_owner:
            return

        for existing in self._specs.values():
            if not existing.compiled_json_owner or existing.phase != spec.phase:
                continue
            overlapping_stages = sorted(
                {stage.value for stage in spec.stages if stage in existing.stages}
            )
            if overlapping_stages:
                raise SpecValidationError(
                    spec.id,
                    f"compiled_json_owner conflicts with '{existing.id}' "
                    f"for phase '{spec.phase.value}' and stages {overlapping_stages}",
                )

    @staticmethod
    def _is_api_compatible(plugin_api: str) -> bool:
        """Check if plugin API version is compatible with kernel."""
        plugin_major = plugin_api.split(".")[0]
        for supported in SUPPORTED_API_VERSIONS:
            kernel_major = supported.split(".")[0]
            if plugin_major == kernel_major:
                return True
        return False

    @staticmethod
    def _extract_entry_plugin_family(entry: str) -> str | None:
        """Return entry family for supported entry layouts, if present.

        Supported layouts:
        1. plugins/<family>/module.py
        2. <family>/module.py
        """
        entry_path = entry.split(":", 1)[0].replace("\\", "/")
        if "/plugins/" in entry_path:
            tail = entry_path.split("/plugins/", 1)[1]
        elif entry_path.startswith("plugins/"):
            tail = entry_path[len("plugins/") :]
        else:
            if "/" not in entry_path:
                return None
            head = entry_path.split("/", 1)[0].strip()
            return head if head in ENTRY_FAMILIES else None
        if "/" not in tail:
            return None
        family = tail.split("/", 1)[0].strip()
        return family or None

    @staticmethod
    def _entry_uses_plugins_prefix_without_family(entry: str) -> bool:
        """Detect deprecated flat plugins/<file>.py entries."""
        entry_path = entry.split(":", 1)[0].replace("\\", "/")
        if "/plugins/" in entry_path:
            tail = entry_path.split("/plugins/", 1)[1]
        elif entry_path.startswith("plugins/"):
            tail = entry_path[len("plugins/") :]
        else:
            return False
        return "/" not in tail

    @staticmethod
    def stage_rank(stage: Stage) -> int:
        """Return numeric rank for stage ordering."""
        return STAGE_ORDER.index(stage)

    @staticmethod
    def phase_rank(phase: Phase) -> int:
        """Return numeric rank for phase ordering."""
        return PHASE_ORDER.index(phase)

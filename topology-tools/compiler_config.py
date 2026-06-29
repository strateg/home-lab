"""Configuration dataclasses for V5Compiler.

Groups 48 constructor parameters into cohesive configuration objects
following the AiConfig pattern established in compiler_ai_sessions.py.

ADR Reference: ADR 0069 (thin orchestrator), ADR 0063 (SOLID principles)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel import Stage


@dataclass(frozen=True)
class PathsConfig:
    """Path-related configuration for the compiler."""

    manifest_path: Path
    output_json: Path
    diagnostics_json: Path
    diagnostics_txt: Path
    artifacts_root: Path
    error_catalog_path: Path
    workspace_root: Path
    dist_root: Path
    plugins_manifest_path: Path
    sbom_output_dir: Path | None = None


@dataclass(frozen=True)
class ModesConfig:
    """Runtime modes and flags for the compiler."""

    strict_model_lock: bool = False
    fail_on_warning: bool = False
    require_new_model: bool = False
    runtime_profile: str = "production"
    instance_source_mode: str = "auto"
    secrets_mode: str = "passthrough"
    secrets_root: str = ""
    pipeline_mode: str = "plugin-first"
    parity_gate: bool = False
    enable_plugins: bool = True
    parallel_plugins: bool = True
    trace_execution: bool = False
    plugin_contract_warnings: bool = False
    plugin_contract_errors: bool = True


@dataclass(frozen=True)
class ProjectConfig:
    """Project-related configuration."""

    project_override: str = ""


@dataclass(frozen=True)
class BuildConfig:
    """Build stage configuration."""

    signing_backend: str = "none"
    release_tag: str = ""


@dataclass
class CompilerConfig:
    """Unified configuration object for V5Compiler.

    Replaces 48 individual constructor parameters with a single
    cohesive configuration object containing domain-grouped settings.

    Usage:
        config = CompilerConfig(
            paths=PathsConfig(...),
            modes=ModesConfig(...),
            project=ProjectConfig(...),
            build=BuildConfig(...),
            ai=AiConfig(...),
            stages=[Stage.DISCOVER, Stage.COMPILE, ...],
        )
        compiler = V5Compiler(config)
    """

    paths: PathsConfig
    modes: ModesConfig
    project: ProjectConfig
    build: BuildConfig
    # AiConfig is imported from compiler_ai_sessions to avoid circular imports
    # and is stored as Any here, typed properly at runtime
    ai: object  # AiConfig from compiler_ai_sessions
    stages: list[Stage] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.modes.enable_plugins:
            raise ValueError(
                "--disable-plugins is retired; plugin-first runtime always enables plugins."
            )

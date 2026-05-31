"""Pipeline test harness for ADR 0097/0099 compliant integration tests.

This module provides a test harness that executes plugins using the
snapshot/envelope model without subprocess calls, ensuring deterministic
and isolated test execution.

Usage:
    harness = PipelineTestHarness(tmp_path)
    harness.load_topology()
    harness.run_stage(Stage.COMPILE)
    harness.run_stage(Stage.GENERATE)

    # Access results
    assert harness.generated_files("terraform/mikrotik")
    assert harness.get_published("base.compiler.instance_rows", "instance_rows")
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure topology-tools is in path
REPO_ROOT = Path(__file__).resolve().parents[2]
V5_TOOLS = REPO_ROOT / "topology-tools"
if str(V5_TOOLS) not in sys.path:
    sys.path.insert(0, str(V5_TOOLS))

from kernel.pipeline_runtime import PipelineState
from kernel.plugin_base import (
    Phase,
    PluginExecutionEnvelope,
    PluginInputSnapshot,
    PluginResult,
    PluginStatus,
    Stage,
)
from kernel.plugin_runner import run_plugin_once


@dataclass
class StageResult:
    """Aggregated result from executing a pipeline stage."""

    stage: Stage
    plugin_results: dict[str, PluginResult] = field(default_factory=dict)
    envelopes: dict[str, PluginExecutionEnvelope] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if all plugins succeeded."""
        return all(r.status == PluginStatus.SUCCESS for r in self.plugin_results.values())

    @property
    def failed_plugins(self) -> list[str]:
        """List of plugin IDs that failed."""
        return [pid for pid, r in self.plugin_results.items() if r.status == PluginStatus.FAILED]


class PipelineTestHarness:
    """Test harness for running pipeline stages with snapshot/envelope model.

    This harness provides a controlled environment for integration tests
    without subprocess calls, ensuring determinism and proper isolation.
    """

    def __init__(
        self,
        work_dir: Path,
        *,
        topology_path: str = "topology/topology.yaml",
        profile: str = "test",
        secrets_mode: str = "passthrough",
        deterministic_timestamp: str | None = "2026-01-01T00:00:00+00:00",
    ):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.topology_path = topology_path
        self.profile = profile
        self.secrets_mode = secrets_mode
        self.deterministic_timestamp = deterministic_timestamp

        # Pipeline state
        self.pipeline_state = PipelineState()
        self.stage_results: dict[Stage, StageResult] = {}

        # Directories
        self.generated_root = self.work_dir / "generated"
        self.output_json_path = self.work_dir / "effective.json"
        self.diagnostics_path = self.work_dir / "diagnostics.json"

        # Loaded data
        self.raw_yaml: dict[str, Any] = {}
        self.compiled_json: dict[str, Any] = {}
        self.model_lock: dict[str, Any] = {}
        self.classes: dict[str, Any] = {}
        self.objects: dict[str, Any] = {}
        self.instance_bindings: dict[str, Any] = {}

        # Plugin registry (lazy loaded)
        self._registry = None
        self._plugins_loaded = False

        # Set deterministic timestamp in environment
        if self.deterministic_timestamp:
            os.environ["COMPILE_DETERMINISTIC_TIMESTAMP"] = self.deterministic_timestamp

    def load_topology(self) -> None:
        """Load topology YAML files."""
        from yaml_loader import load_topology_yaml

        topology_full_path = REPO_ROOT / self.topology_path
        self.raw_yaml = load_topology_yaml(topology_full_path)

    def load_registry(self) -> None:
        """Load plugin registry."""
        if self._registry is not None:
            return

        from kernel.plugin_registry import PluginRegistry

        self._registry = PluginRegistry()
        self._registry.load_manifests(
            framework_manifest=V5_TOOLS / "plugins" / "plugins.yaml",
            class_manifests=list((REPO_ROOT / "topology" / "class-modules").glob("*/plugins.yaml")),
            object_manifests=list((REPO_ROOT / "topology" / "object-modules").glob("*/plugins.yaml")),
            project_manifests=[],
        )
        self._plugins_loaded = True

    def get_plugins_for_stage(self, stage: Stage) -> list[tuple[str, Any]]:
        """Get ordered list of (plugin_id, plugin_instance) for a stage."""
        if self._registry is None:
            self.load_registry()

        return self._registry.get_plugins_for_stage(stage)

    def build_snapshot(
        self,
        plugin_id: str,
        stage: Stage,
        phase: Phase = Phase.RUN,
        *,
        extra_config: dict[str, Any] | None = None,
    ) -> PluginInputSnapshot:
        """Build an immutable snapshot for plugin execution."""
        # Resolve subscriptions from pipeline state
        subscriptions = {}
        if self._registry is not None:
            spec = self._registry.get_spec(plugin_id)
            if spec is not None:
                for consume in spec.consumes:
                    from_plugin = consume.get("from_plugin", "")
                    key = consume.get("key", "")
                    if from_plugin and key:
                        try:
                            sub = self.pipeline_state.resolve_subscription(
                                from_plugin=from_plugin, key=key, stage=stage
                            )
                            subscriptions[(from_plugin, key)] = sub
                        except Exception:
                            pass  # Subscription not available yet

        config = {
            "generator_artifacts_root": str(self.generated_root),
            "secrets_mode": self.secrets_mode,
            **(extra_config or {}),
        }

        return PluginInputSnapshot(
            plugin_id=plugin_id,
            stage=stage,
            phase=phase,
            topology_path=self.topology_path,
            profile=self.profile,
            config=config,
            model_lock=self.model_lock,
            raw_yaml=self.raw_yaml,
            instance_bindings=self.instance_bindings,
            compiled_json=self.compiled_json,
            classes=self.classes,
            objects=self.objects,
            output_dir=str(self.work_dir),
            workspace_root=str(self.generated_root),
            subscriptions=subscriptions,
            legacy_published_data=dict(self.pipeline_state.committed_data),
            allowed_dependencies=frozenset(spec.depends_on if spec else []),
            produced_key_scopes={},
        )

    def run_plugin(
        self,
        plugin_id: str,
        plugin: Any,
        stage: Stage,
        phase: Phase = Phase.RUN,
        *,
        extra_config: dict[str, Any] | None = None,
    ) -> PluginExecutionEnvelope:
        """Execute a single plugin and commit its envelope."""
        snapshot = self.build_snapshot(plugin_id, stage, phase, extra_config=extra_config)
        envelope = run_plugin_once(snapshot=snapshot, plugin=plugin)

        # Commit envelope to pipeline state
        spec = self._registry.get_spec(plugin_id) if self._registry else None
        produces = spec.produces if spec else []

        self.pipeline_state.commit_envelope(
            plugin_id=plugin_id,
            stage=stage,
            phase=phase,
            produces=produces,
            envelope=envelope,
        )

        return envelope

    def run_stage(self, stage: Stage, *, phases: list[Phase] | None = None) -> StageResult:
        """Execute all plugins for a stage in order."""
        if phases is None:
            phases = [Phase.INIT, Phase.PRE, Phase.RUN, Phase.POST, Phase.VERIFY, Phase.FINALIZE]

        result = StageResult(stage=stage)

        for plugin_id, plugin in self.get_plugins_for_stage(stage):
            spec = self._registry.get_spec(plugin_id) if self._registry else None
            plugin_phase = Phase(spec.phase) if spec and spec.phase else Phase.RUN

            if plugin_phase not in phases:
                continue

            try:
                envelope = self.run_plugin(plugin_id, plugin, stage, plugin_phase)
                result.plugin_results[plugin_id] = envelope.result
                result.envelopes[plugin_id] = envelope

                # Update compiled_json if published
                for msg in envelope.published_messages:
                    if msg.key == "compiled_json":
                        self.compiled_json = msg.value
                    elif msg.key == "instance_rows":
                        # Merge instance rows into compiled_json
                        if "instances" not in self.compiled_json:
                            self.compiled_json["instances"] = {}
                        self.compiled_json["instances"].update(msg.value)

            except Exception as exc:
                result.errors.append(f"{plugin_id}: {exc}")

        self.stage_results[stage] = result

        # Invalidate stage-local data
        self.pipeline_state.invalidate_stage_local_data(stage)

        return result

    def run_full_pipeline(self) -> dict[Stage, StageResult]:
        """Run all stages in order."""
        self.load_topology()
        self.load_registry()

        for stage in [Stage.DISCOVER, Stage.COMPILE, Stage.VALIDATE, Stage.GENERATE, Stage.ASSEMBLE, Stage.BUILD]:
            self.run_stage(stage)

        return self.stage_results

    def get_published(self, plugin_id: str, key: str) -> Any:
        """Get a published value from pipeline state."""
        plugin_data = self.pipeline_state.committed_data.get(plugin_id, {})
        return plugin_data.get(key)

    def generated_files(self, subpath: str = "") -> list[Path]:
        """List generated files under a subpath."""
        root = self.generated_root / subpath if subpath else self.generated_root
        if not root.exists():
            return []
        return sorted(root.rglob("*") if root.is_dir() else [root])

    def read_generated(self, path: str) -> str:
        """Read a generated file."""
        full_path = self.generated_root / path
        return full_path.read_text(encoding="utf-8")

    def assert_generated_exists(self, *paths: str) -> None:
        """Assert that all specified generated files exist."""
        for path in paths:
            full_path = self.generated_root / path
            assert full_path.exists(), f"Expected generated file not found: {path}"

    def assert_stage_success(self, stage: Stage) -> None:
        """Assert that a stage completed successfully."""
        result = self.stage_results.get(stage)
        assert result is not None, f"Stage {stage.value} was not executed"
        assert result.success, f"Stage {stage.value} failed: {result.failed_plugins}"


__all__ = ["PipelineTestHarness", "StageResult"]

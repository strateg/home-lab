#!/usr/bin/env python3
"""Compile v5 topology manifest + modules + instance bindings into canonical JSON."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Add kernel to path for plugin imports
TOPOLOGY_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOPOLOGY_TOOLS))

from compiler_ai_sessions import AiConfig, AiSessionRunner
from compiler_config import BootstrapResult
from compiler_framework_lock import FrameworkLockManager
from compiler_cli import CompilerCliDependencies
from compiler_cli import build_parser as build_compiler_parser
from compiler_cli import run_cli
from compiler_contract import manifest_digest, validate_compiled_model_contract
from compiler_decisions import select_effective_payload
from compiler_diagnostics import CompilerDiagnostic
from compiler_ownership import artifact_owner, compilation_owner, validation_owner
from compiler_plugin_context import create_plugin_context
from compiler_reporting import write_diagnostics_report
from compiler_runtime import (
    apply_plugin_compile_outputs,
    emit_effective_artifact,
    load_core_compile_inputs,
    resolve_manifest_paths,
)
from kernel import (
    KERNEL_VERSION,
    STAGE_ORDER,
    Phase,
    PluginContext,
    PluginRegistry,
    PluginResult,
    PluginStatus,
    Stage,
)
from plugin_manifest_discovery import discover_plugin_manifest_paths, validate_module_index_consistency
from yaml_loader import load_yaml_file

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "topology" / "topology.yaml"
DEFAULT_TOPOLOGY_RELATIVE = str(DEFAULT_MANIFEST.relative_to(REPO_ROOT).as_posix())
DEFAULT_OUTPUT_JSON = REPO_ROOT / "build" / "effective-topology.json"
DEFAULT_DIAGNOSTICS_JSON = REPO_ROOT / "build" / "diagnostics" / "report.json"
DEFAULT_DIAGNOSTICS_TXT = REPO_ROOT / "build" / "diagnostics" / "report.txt"
DEFAULT_ARTIFACTS_ROOT = REPO_ROOT / "generated"
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / ".work" / "native"
DEFAULT_DIST_ROOT = REPO_ROOT / "dist"
DEFAULT_ERROR_CATALOG = TOPOLOGY_TOOLS / "data" / "error-catalog.yaml"
DEFAULT_PLUGINS_MANIFEST = TOPOLOGY_TOOLS / "plugins" / "plugins.yaml"

SUPPORTED_RUNTIME_PROFILES = ("production", "modeled", "test-real", "dev")
SUPPORTED_INSTANCE_SOURCE_MODES = ("auto", "sharded-only")
SUPPORTED_SECRETS_MODES = ("inject", "passthrough", "strict")
REQUIRED_FRAMEWORK_KEYS = (
    "class_modules_root",
    "object_modules_root",
    "model_lock",
    "layer_contract",
    "capability_catalog",
    "capability_packs",
)
REQUIRED_PROJECT_KEYS = ("active", "projects_root")
REQUIRED_PROJECT_MANIFEST_KEYS = ("instances_root", "secrets_root")
COMPILED_MODEL_VERSION = "1.0"
COMPILER_PIPELINE_VERSION = "adr0069-ws2"
SUPPORTED_COMPILED_MODEL_MAJOR = {"1"}
ADVISORY_STAGE_SET = {Stage.DISCOVER, Stage.COMPILE, Stage.VALIDATE}


class _DynamicStderrHandler(logging.Handler):
    """Logging handler that writes to the current stderr stream."""

    terminator = "\n"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            sys.stderr.write(message + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        try:
            sys.stderr.flush()
        except Exception:
            pass


def _configure_runtime_logger() -> logging.Logger:
    logger = logging.getLogger("home_lab.compile_topology")
    if not any(isinstance(handler, _DynamicStderrHandler) for handler in logger.handlers):
        handler = _DynamicStderrHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


LOGGER = _configure_runtime_logger()


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def resolve_topology_path(topology_arg: str) -> Path:
    """Resolve topology path with repo-layout-aware default fallback.

    For monorepo layout, default remains `topology/topology.yaml`.
    For standalone project repo roots, fallback to `topology.yaml` when
    the default monorepo relative path does not exist.
    """

    resolved = resolve_repo_path(topology_arg)
    if resolved.exists():
        return resolved

    if topology_arg == DEFAULT_TOPOLOGY_RELATIVE:
        standalone_candidate = REPO_ROOT / "topology.yaml"
        if standalone_candidate.exists():
            return standalone_candidate
    return resolved


def utc_now() -> str:
    """Return current UTC timestamp, or fixed timestamp for deterministic builds.

    Set COMPILE_DETERMINISTIC_TIMESTAMP env var to a fixed ISO timestamp
    for reproducible builds in tests.
    """
    fixed = os.environ.get("COMPILE_DETERMINISTIC_TIMESTAMP")
    if fixed:
        return fixed
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_stages_arg(raw: str) -> list[Stage]:
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise ValueError("stages list is empty")
    values = {stage.value: stage for stage in STAGE_ORDER}
    unknown = [token for token in tokens if token not in values]
    if unknown:
        raise ValueError(f"Unknown stages: {unknown}")
    seen: set[Stage] = set()
    ordered: list[Stage] = []
    for token in tokens:
        stage = values[token]
        if stage in seen:
            continue
        seen.add(stage)
        ordered.append(stage)
    return ordered


class V5Compiler:
    def __init__(
        self,
        *,
        manifest_path: Path,
        output_json: Path,
        diagnostics_json: Path,
        diagnostics_txt: Path,
        artifacts_root: Path | None = None,
        error_catalog_path: Path,
        project_override: str = "",
        strict_model_lock: bool,
        fail_on_warning: bool,
        require_new_model: bool,
        runtime_profile: str = "production",
        instance_source_mode: str = "auto",
        secrets_mode: str = "passthrough",
        secrets_root: str = "",
        pipeline_mode: str = "plugin-first",
        parity_gate: bool = False,
        enable_plugins: bool = True,
        plugins_manifest_path: Path | None = None,
        parallel_plugins: bool = True,
        trace_execution: bool = False,
        plugin_contract_warnings: bool = False,
        plugin_contract_errors: bool = True,
        workspace_root: Path | None = None,
        dist_root: Path | None = None,
        signing_backend: str = "none",
        release_tag: str = "",
        sbom_output_dir: Path | None = None,
        stages: list[Stage] | None = None,
        ai_advisory: bool = False,
        ai_assisted: bool = False,
        ai_output_json: Path | None = None,
        ai_audit_retention_days: int = 30,
        ai_sandbox_retention_days: int = 7,
        ai_sandbox_max_files: int = 128,
        ai_sandbox_max_bytes: int = 10 * 1024 * 1024,
        ai_promote_approved: bool = False,
        ai_approve_all: bool = False,
        ai_approve_paths: tuple[str, ...] = (),
        ai_rollback_all: bool = False,
        ai_rollback_paths: tuple[str, ...] = (),
        ai_rollback_ref: str = "HEAD",
        ai_ansible_lint: bool = False,
        ai_ansible_lint_cmd: str = "ansible-lint",
        ai_advisory_max_latency_seconds: float = 60.0,
        ai_assisted_max_latency_seconds: float = 300.0,
    ) -> None:
        if not enable_plugins:
            raise ValueError("--disable-plugins is retired; plugin-first runtime always enables plugins.")

        self.manifest_path = manifest_path
        self.output_json = output_json
        self.diagnostics_json = diagnostics_json
        self.diagnostics_txt = diagnostics_txt
        self.artifacts_root = artifacts_root or DEFAULT_ARTIFACTS_ROOT
        self.error_catalog_path = error_catalog_path
        self.project_override = project_override
        self.strict_model_lock = strict_model_lock
        self.fail_on_warning = fail_on_warning
        self.require_new_model = require_new_model
        self.runtime_profile = runtime_profile
        self.instance_source_mode = instance_source_mode
        self.secrets_mode = secrets_mode
        self.secrets_root = secrets_root
        self.pipeline_mode = pipeline_mode
        self.parity_gate = parity_gate
        self.enable_plugins = enable_plugins
        self.plugins_manifest_path = plugins_manifest_path or DEFAULT_PLUGINS_MANIFEST
        self.parallel_plugins = parallel_plugins
        self.trace_execution = trace_execution
        self.plugin_contract_warnings = plugin_contract_warnings
        self.plugin_contract_errors = plugin_contract_errors
        self.workspace_root = workspace_root or DEFAULT_WORKSPACE_ROOT
        self.dist_root = dist_root or DEFAULT_DIST_ROOT
        self.signing_backend = signing_backend
        self.release_tag = release_tag
        self.sbom_output_dir = sbom_output_dir
        self.ai_config = AiConfig(
            advisory=ai_advisory,
            assisted=ai_assisted,
            output_json=ai_output_json,
            audit_retention_days=ai_audit_retention_days,
            sandbox_retention_days=ai_sandbox_retention_days,
            sandbox_max_files=ai_sandbox_max_files,
            sandbox_max_bytes=ai_sandbox_max_bytes,
            promote_approved=ai_promote_approved,
            approve_all=ai_approve_all,
            approve_paths=ai_approve_paths,
            rollback_all=ai_rollback_all,
            rollback_paths=ai_rollback_paths,
            rollback_ref=ai_rollback_ref,
            ansible_lint=ai_ansible_lint,
            ansible_lint_cmd=ai_ansible_lint_cmd,
            advisory_max_latency_seconds=ai_advisory_max_latency_seconds,
            assisted_max_latency_seconds=ai_assisted_max_latency_seconds,
        )
        self.ai_advisory = self.ai_config.advisory
        self.ai_assisted = self.ai_config.assisted
        self.ai_output_json = self.ai_config.output_json
        self.ai_audit_retention_days = self.ai_config.audit_retention_days
        self.ai_sandbox_retention_days = self.ai_config.sandbox_retention_days
        self.ai_sandbox_max_files = self.ai_config.sandbox_max_files
        self.ai_sandbox_max_bytes = self.ai_config.sandbox_max_bytes
        self.ai_promote_approved = self.ai_config.promote_approved
        self.ai_approve_all = self.ai_config.approve_all
        self.ai_approve_paths = self.ai_config.approve_paths
        self.ai_rollback_all = self.ai_config.rollback_all
        self.ai_rollback_paths = self.ai_config.rollback_paths
        self.ai_rollback_ref = self.ai_config.rollback_ref
        self.ai_ansible_lint = self.ai_config.ansible_lint
        self.ai_ansible_lint_cmd = self.ai_config.ansible_lint_cmd
        self.ai_advisory_max_latency_seconds = self.ai_config.advisory_max_latency_seconds
        self.ai_assisted_max_latency_seconds = self.ai_config.assisted_max_latency_seconds
        requested_stages = set(stages) if isinstance(stages, list) and stages else set(STAGE_ORDER)
        self.stages: tuple[Stage, ...] = tuple(stage for stage in STAGE_ORDER if stage in requested_stages)

        self._diagnostics: list[CompilerDiagnostic] = []
        self._error_hints = self._load_error_hints(error_catalog_path)
        self._plugin_registry: PluginRegistry | None = None
        self._plugin_results: list[PluginResult] = []
        self._published_key_inventory: dict[str, list[str]] = {}
        self._run_generated_at: str | None = None
        self._base_manifest_loaded = False
        self._plugin_manifests_loaded = False
        self._discovered_manifest_paths: list[str] = []
        self._discovered_plugin_count = 0
        self._validation_owner = lambda rule_name: validation_owner(
            enable_plugins=self.enable_plugins,
            pipeline_mode=self.pipeline_mode,
            rule_name=rule_name,
        )
        self._compilation_owner = lambda rule_name: compilation_owner(
            enable_plugins=self.enable_plugins,
            pipeline_mode=self.pipeline_mode,
            rule_name=rule_name,
        )
        self._artifact_owner = lambda artifact_name: artifact_owner(
            enable_plugins=self.enable_plugins,
            pipeline_mode=self.pipeline_mode,
            artifact_name=artifact_name,
        )

        self._init_plugin_registry()

    def _load_error_hints(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        try:
            payload = load_yaml_file(path) or {}
        except yaml.YAMLError:
            return {}
        if not isinstance(payload, dict):
            return {}
        codes = payload.get("codes")
        if not isinstance(codes, dict):
            return {}
        hints: dict[str, str] = {}
        for code, item in codes.items():
            if not isinstance(code, str) or not isinstance(item, dict):
                continue
            hint = item.get("hint")
            if isinstance(hint, str) and hint:
                hints[code] = hint
        return hints

    def _init_plugin_registry(self) -> None:
        """Initialize empty plugin registry (manifests load in run())."""
        try:
            self._plugin_registry = PluginRegistry(TOPOLOGY_TOOLS)
        except Exception as exc:
            self.add_diag(
                code="E4001",
                severity="error",
                stage="load",
                message=f"Plugin registry initialization failed: {exc}",
                path="plugins.yaml",
            )
            self._plugin_registry = None

    def _path_for_diag(self, path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT).as_posix())
        except ValueError:
            return str(path.as_posix())

    @staticmethod
    def _project_scoped_root(root: Path, project_id: str) -> Path:
        if root.name == project_id:
            return root
        return root / project_id

    def _validate_stage_selection(self) -> bool:
        selected = set(self.stages)
        if not selected:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="No pipeline stages selected. Use --stages to select at least one stage.",
                path="pipeline:stages",
            )
            return False
        if Stage.VALIDATE in selected and Stage.COMPILE not in selected:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="validate stage requires compile stage in --stages selection.",
                path="pipeline:stages",
            )
            return False
        if Stage.GENERATE in selected and Stage.VALIDATE not in selected:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="generate stage requires validate stage in --stages selection.",
                path="pipeline:stages",
            )
            return False
        if Stage.ASSEMBLE in selected and Stage.GENERATE not in selected:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="assemble stage requires generate stage in --stages selection.",
                path="pipeline:stages",
            )
            return False
        if Stage.BUILD in selected and Stage.ASSEMBLE not in selected:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="build stage requires assemble stage in --stages selection.",
                path="pipeline:stages",
            )
            return False
        return True

    def _load_base_plugin_manifest(self) -> None:
        """Load only base plugin manifest required for discover-stage bootstrap."""
        if not self._plugin_registry or self._base_manifest_loaded:
            return

        manifest_path = self.plugins_manifest_path
        if not manifest_path.exists():
            self.add_diag(
                code="W4001",
                severity="warning",
                stage="load",
                message=f"Plugin manifest not found: {manifest_path}",
                path=self._path_for_diag(manifest_path),
            )
            self._base_manifest_loaded = True
            return

        errors_before = len(self._plugin_registry.get_load_errors())
        try:
            self._plugin_registry.load_manifest(manifest_path)
        except Exception as exc:
            self.add_diag(
                code="E4001",
                severity="error",
                stage="load",
                message=f"Plugin manifest load failed: {exc}",
                path=self._path_for_diag(manifest_path),
            )
            self._base_manifest_loaded = True
            return

        load_errors = self._plugin_registry.get_load_errors()
        for err in load_errors[errors_before:]:
            self.add_diag(
                code="E4001",
                severity="error",
                stage="load",
                message=f"Plugin load error: {err}",
                path=self._path_for_diag(manifest_path),
            )

        self._base_manifest_loaded = True
        self._discovered_manifest_paths = [self._path_for_diag(manifest_path)]
        self._discovered_plugin_count = len(self._plugin_registry.specs)

    def _load_module_plugin_manifests(
        self,
        *,
        class_modules_root: Path,
        object_modules_root: Path,
        project_plugins_root: Path | None = None,
        module_index_path: Path | None = None,
        emit_diagnostics: bool = True,
    ) -> dict[str, Any]:
        """Load module-level plugin manifests discovered under class/object module roots."""
        if not self._plugin_registry:
            return {
                "status": "error",
                "loaded_manifests": [],
                "discovered_manifests": [],
                "module_manifest_count": 0,
                "loaded_plugin_count": 0,
                "errors": ["plugin registry is not initialized"],
            }
        if self._plugin_manifests_loaded:
            return {
                "status": "ok",
                "loaded_manifests": [],
                "discovered_manifests": list(self._discovered_manifest_paths),
                "module_manifest_count": max(0, len(self._discovered_manifest_paths) - 1),
                "loaded_plugin_count": self._discovered_plugin_count,
                "errors": [],
                "already_loaded": True,
            }

        self._load_base_plugin_manifest()
        resolved_module_index_path = module_index_path
        if resolved_module_index_path is None:
            class_candidate = class_modules_root.parent / "module-index.yaml"
            object_candidate = object_modules_root.parent / "module-index.yaml"
            if class_candidate.parent == object_candidate.parent:
                resolved_module_index_path = class_candidate
            elif class_candidate.exists():
                resolved_module_index_path = class_candidate
            elif object_candidate.exists():
                resolved_module_index_path = object_candidate
            else:
                resolved_module_index_path = class_candidate

        ordered_manifests = discover_plugin_manifest_paths(
            base_manifest_path=self.plugins_manifest_path,
            class_modules_root=class_modules_root,
            object_modules_root=object_modules_root,
            project_plugins_root=project_plugins_root,
            module_index_path=resolved_module_index_path,
        )
        module_manifests = ordered_manifests[1:]

        loaded_module_paths: list[Path] = []
        load_errors: list[str] = []
        if resolved_module_index_path is not None:
            index_errors = validate_module_index_consistency(
                module_index_path=resolved_module_index_path,
                class_modules_root=class_modules_root,
                object_modules_root=object_modules_root,
            )
            for err in index_errors:
                load_errors.append(f"{self._path_for_diag(resolved_module_index_path)}: {err}")
                if emit_diagnostics:
                    self.add_diag(
                        code="E4001",
                        severity="error",
                        stage="load",
                        message=f"module-index consistency error: {err}",
                        path=self._path_for_diag(resolved_module_index_path),
                    )

        for manifest_path in module_manifests:
            if not manifest_path.exists():
                continue
            errors_before = len(self._plugin_registry.get_load_errors())
            try:
                self._plugin_registry.load_manifest(manifest_path)
            except Exception as exc:
                message = f"Plugin manifest load failed: {exc}"
                load_errors.append(f"{self._path_for_diag(manifest_path)}: {message}")
                if emit_diagnostics:
                    self.add_diag(
                        code="E4001",
                        severity="error",
                        stage="load",
                        message=message,
                        path=self._path_for_diag(manifest_path),
                    )
                continue
            loaded_module_paths.append(manifest_path)
            new_errors = self._plugin_registry.get_load_errors()[errors_before:]
            for err in new_errors:
                load_errors.append(f"{self._path_for_diag(manifest_path)}: {err}")
                if emit_diagnostics:
                    self.add_diag(
                        code="E4001",
                        severity="error",
                        stage="load",
                        message=f"Plugin load error: {err}",
                        path=self._path_for_diag(manifest_path),
                    )

        self._plugin_manifests_loaded = True
        self._discovered_manifest_paths = [self._path_for_diag(path) for path in ordered_manifests if path.exists()]
        self._discovered_plugin_count = len(self._plugin_registry.specs)

        module_manifest_count = len(self._discovered_manifest_paths) - 1 if self._discovered_manifest_paths else 0
        if emit_diagnostics:
            self.add_diag(
                code="I4001",
                severity="info",
                stage="load",
                message=(
                    f"Plugin kernel v{KERNEL_VERSION} initialized with {len(self._plugin_registry.specs)} plugins "
                    f"from {len(self._discovered_manifest_paths)} manifest(s), "
                    f"including {max(0, module_manifest_count)} module-level manifest(s)."
                ),
                path=self._path_for_diag(self.plugins_manifest_path),
                confidence=1.0,
            )

        return {
            "status": "ok",
            "loaded_manifests": [self._path_for_diag(path) for path in loaded_module_paths],
            "discovered_manifests": list(self._discovered_manifest_paths),
            "module_manifest_count": max(0, module_manifest_count),
            "loaded_plugin_count": self._discovered_plugin_count,
            "errors": load_errors,
        }

    def _load_plugin_manifests(
        self,
        *,
        class_modules_root: Path,
        object_modules_root: Path,
        project_plugins_root: Path | None = None,
        instance_manifests_root: Path | None = None,
        module_index_path: Path | None = None,
    ) -> None:
        """Compatibility wrapper that loads base + module manifests."""
        _ = instance_manifests_root
        self._load_base_plugin_manifest()
        self._load_module_plugin_manifests(
            class_modules_root=class_modules_root,
            object_modules_root=object_modules_root,
            project_plugins_root=project_plugins_root,
            module_index_path=module_index_path,
            emit_diagnostics=True,
        )

    def _record_plugin_results(self, *, stage: Stage, results: list[PluginResult]) -> None:
        """Store plugin results and project diagnostics into compiler report stream."""
        self._plugin_results.extend(results)
        for result in results:
            for plugin_diag in result.diagnostics:
                diag = CompilerDiagnostic.from_plugin_diagnostic(plugin_diag)
                self._diagnostics.append(diag)

            if result.status == PluginStatus.TIMEOUT:
                self.add_diag(
                    code="E4101",
                    severity="error",
                    stage=str(stage.value),
                    message=f"Plugin '{result.plugin_id}' timed out after {result.duration_ms:.0f}ms",
                    path=f"plugin:{result.plugin_id}",
                )
            elif result.status == PluginStatus.FAILED and result.error_traceback:
                tb_lines = [line for line in result.error_traceback.strip().split("\n") if line.strip()]
                error_msg = tb_lines[-1] if tb_lines else "unknown error"
                self.add_diag(
                    code="E4102",
                    severity="error",
                    stage=str(stage.value),
                    message=f"Plugin '{result.plugin_id}' crashed: {error_msg}",
                    path=f"plugin:{result.plugin_id}",
                )

    def _capture_published_key_inventory(self, ctx: PluginContext | None) -> None:
        if ctx is None:
            self._published_key_inventory = {}
            return
        published = ctx.get_published_data()
        inventory: dict[str, list[str]] = {}
        for plugin_id, payload in published.items():
            if not isinstance(plugin_id, str) or not plugin_id:
                continue
            if not isinstance(payload, dict):
                continue
            inventory[plugin_id] = sorted([key for key in payload.keys() if isinstance(key, str)])
        self._published_key_inventory = inventory

    def _bootstrap_discover_manifest_loader(self, *, ctx: PluginContext) -> None:
        """Execute discover/init loader plugin when discover stage is not selected."""
        if not self._plugin_registry or self._plugin_manifests_loaded:
            return
        result = self._plugin_registry.execute_plugin(
            "base.discover.manifest_loader",
            ctx,
            Stage.DISCOVER,
            phase=Phase.INIT,
            contract_warnings=self.plugin_contract_warnings,
            contract_errors=self.plugin_contract_errors,
        )
        self._record_plugin_results(stage=Stage.DISCOVER, results=[result])
        discovered_paths = ctx.config.get("discovered_plugin_manifests")
        if isinstance(discovered_paths, list):
            self._discovered_manifest_paths = [item for item in discovered_paths if isinstance(item, str)]
        discovered_count = ctx.config.get("discovered_plugin_count")
        if isinstance(discovered_count, int):
            self._discovered_plugin_count = discovered_count

    def _execute_plugins(
        self,
        *,
        stage: Stage,
        ctx: PluginContext,
    ) -> None:
        """Execute all plugins for a given stage.

        Args:
            stage: Pipeline stage to execute
            ctx: Shared plugin context (preserves published data across stages)
        """
        if not self._plugin_registry:
            return

        # Execute plugins for stage
        execute_kwargs: dict[str, Any] = {
            "profile": self.runtime_profile,
            "fail_fast": stage == Stage.COMPILE,
        }
        if self.parallel_plugins:
            execute_kwargs["parallel_plugins"] = True
        if self.trace_execution:
            execute_kwargs["trace_execution"] = True
        if self.plugin_contract_warnings:
            execute_kwargs["contract_warnings"] = True
        if self.plugin_contract_errors:
            execute_kwargs["contract_errors"] = True
        results = self._plugin_registry.execute_stage(stage, ctx, **execute_kwargs)
        self._record_plugin_results(stage=stage, results=results)

    def add_diag(
        self,
        *,
        code: str,
        severity: str,
        stage: str,
        message: str,
        path: str,
        hint: str | None = None,
        confidence: float = 0.95,
    ) -> None:
        if hint is None:
            hint = self._error_hints.get(code)
        self._diagnostics.append(
            CompilerDiagnostic(
                code=code,
                severity=severity,
                stage=stage,
                message=message,
                path=path,
                hint=hint,
                confidence=confidence,
            )
        )

    def _validate_compiled_model_contract(self, payload: dict[str, Any]) -> bool:
        return validate_compiled_model_contract(
            payload=payload,
            add_diag=self.add_diag,
            supported_compiled_model_major=SUPPORTED_COMPILED_MODEL_MAJOR,
        )

    def _load_yaml(self, path: Path, *, code_missing: str, code_parse: str, stage: str) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            self.add_diag(
                code=code_missing,
                severity="error",
                stage=stage,
                message=f"File does not exist: {path}",
                path=self._path_for_diag(path),
            )
            return None
        try:
            payload = load_yaml_file(path) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.add_diag(
                code=code_parse,
                severity="error",
                stage=stage,
                message=f"YAML parse error: {exc}",
                path=self._path_for_diag(path),
            )
            return None
        if not isinstance(payload, dict):
            self.add_diag(
                code="E1004",
                severity="error",
                stage=stage,
                message="Expected mapping/object at YAML root.",
                path=self._path_for_diag(path),
            )
            return None
        return payload

    def _write_diagnostics(self) -> tuple[int, int, int, int]:
        self._write_execution_trace()
        plugin_stats = self._plugin_registry.get_stats() if self._plugin_registry else None
        plugin_manifests = self._plugin_registry.manifests if self._plugin_registry else None
        return write_diagnostics_report(
            diagnostics=self._diagnostics,
            diagnostics_json=self.diagnostics_json,
            diagnostics_txt=self.diagnostics_txt,
            topology_path=self.manifest_path,
            error_catalog_path=self.error_catalog_path,
            output_json=self.output_json,
            repo_root=REPO_ROOT,
            now_iso=utc_now,
            plugin_stats=plugin_stats,
            plugin_manifests=plugin_manifests,
        )

    def _write_execution_trace(self) -> None:
        if not self.trace_execution or not self._plugin_registry:
            return
        trace_path = self.diagnostics_json.parent / "plugin-execution-trace.json"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_payload = self._plugin_registry.get_execution_trace()
        trace_path.write_text(json.dumps(trace_payload, ensure_ascii=True, indent=2), encoding="utf-8")
        published_keys_path = self.diagnostics_json.parent / "plugin-published-keys.json"
        published_keys_path.write_text(
            json.dumps(self._published_key_inventory, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        self.add_diag(
            code="I4002",
            severity="info",
            stage="load",
            message=f"Plugin execution trace written to {trace_path}",
            path=self._path_for_diag(trace_path),
            confidence=1.0,
        )

    def _print_summary(self, *, total: int, errors: int, warnings: int, infos: int, emit_effective: bool) -> None:
        print(f"Compile summary: total={total} errors={errors} warnings={warnings} infos={infos}")
        print(f"Diagnostics JSON: {self.diagnostics_json}")
        print(f"Diagnostics TXT:  {self.diagnostics_txt}")
        if emit_effective and errors == 0:
            print(f"Effective JSON:   {self.output_json}")

    def _fail_early(self) -> int:
        """Write diagnostics and return failure exit code (thin orchestrator helper)."""
        total, errors, warnings, infos = self._write_diagnostics()
        self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
        return 1

    def _finalize(self, *, emit_effective: bool = False) -> int:
        """Write final diagnostics and return appropriate exit code."""
        total, errors, warnings, infos = self._write_diagnostics()
        self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=emit_effective)
        if errors > 0:
            return 1
        if self.fail_on_warning and warnings > 0:
            return 2
        return 0

    def _has_errors(self) -> bool:
        """Check if any error diagnostics exist."""
        return any(item.severity == "error" for item in self._diagnostics)

    def _validate_topology_manifest(self, manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Validate topology manifest structure. Returns (framework_paths, project_section) or None on error."""
        legacy_paths = manifest.get("paths")
        if legacy_paths is not None:
            self.add_diag(
                code="E7808",
                severity="error",
                stage="validate",
                message="Legacy manifest contract section 'paths' is unsupported in strict-only mode.",
                path="topology/topology.yaml:paths",
            )
            return None

        framework_paths = manifest.get("framework")
        if not isinstance(framework_paths, dict):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="topology manifest must contain mapping key 'framework'.",
                path="topology/topology.yaml:framework",
            )
            return None

        project_section = manifest.get("project")
        if not isinstance(project_section, dict):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="topology manifest must contain mapping key 'project'.",
                path="topology/topology.yaml:project",
            )
            return None

        for key in REQUIRED_FRAMEWORK_KEYS:
            value = framework_paths.get(key)
            if not isinstance(value, str) or not value.strip():
                self.add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"framework.{key} must be non-empty string.",
                    path=f"topology/topology.yaml:framework.{key}",
                )
        semantic_keywords_raw = framework_paths.get("semantic_keywords")
        if semantic_keywords_raw is not None and (
            not isinstance(semantic_keywords_raw, str) or not semantic_keywords_raw.strip()
        ):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="framework.semantic_keywords must be non-empty string when provided.",
                path="topology/topology.yaml:framework.semantic_keywords",
            )

        for key in REQUIRED_PROJECT_KEYS:
            value = project_section.get(key)
            if not isinstance(value, str) or not value.strip():
                self.add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"project.{key} must be non-empty string.",
                    path=f"topology/topology.yaml:project.{key}",
                )

        if self._has_errors():
            return None

        return framework_paths, project_section

    def _validate_project_manifest(self, project_manifest: dict[str, Any], project_manifest_path: Path) -> bool:
        """Validate project manifest required keys. Returns True if valid."""
        for key in REQUIRED_PROJECT_MANIFEST_KEYS:
            value = project_manifest.get(key)
            if not isinstance(value, str) or not value.strip():
                self.add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"project manifest key '{key}' must be non-empty string.",
                    path=f"{self._path_for_diag(project_manifest_path)}:{key}",
                )
        return not self._has_errors()

    def _bootstrap_phase(self) -> BootstrapResult | None:
        """Execute bootstrap phase: validation, manifest loading, framework lock.

        Returns BootstrapResult on success, None on validation failure.
        Extracts Phases 1-4 from run() per ADR 0069 thin orchestrator.
        """
        # Phase 1: Pre-validation checks
        if not self._validate_stage_selection():
            return None
        if self.pipeline_mode != "plugin-first":
            self.add_diag(
                code="E6904",
                severity="error",
                stage="validate",
                message="pipeline_mode=legacy is retired after ADR0069 cutover; use --pipeline-mode plugin-first.",
                path="pipeline:mode",
            )
            return None
        if self.parity_gate:
            self.add_diag(
                code="E6905",
                severity="error",
                stage="validate",
                message="--parity-gate is not supported after plugin-first cutover.",
                path="pipeline:parity",
            )
            return None

        # Phase 2: Load and validate topology manifest
        manifest = self._load_yaml(self.manifest_path, code_missing="E1001", code_parse="E1003", stage="load")
        if manifest is None:
            return None

        manifest_result = self._validate_topology_manifest(manifest)
        if manifest_result is None:
            return None
        framework_paths, project_section = manifest_result

        # Phase 3: Load and validate project manifest
        project_id = self.project_override if self.project_override else str(project_section["active"]).strip()
        projects_root_path = resolve_repo_path(str(project_section["projects_root"]).strip())
        project_root = projects_root_path / project_id
        project_manifest_path = project_root / "project.yaml"
        root_level_project_manifest = projects_root_path / "project.yaml"
        if not project_manifest_path.exists() and root_level_project_manifest.exists():
            project_root = projects_root_path
            project_manifest_path = root_level_project_manifest
        project_manifest = self._load_yaml(
            project_manifest_path, code_missing="E1001", code_parse="E1003", stage="load"
        )
        if project_manifest is None:
            return None
        if not self._validate_project_manifest(project_manifest, project_manifest_path):
            return None

        # Phase 4: Verify framework lock
        framework_lock_mgr = FrameworkLockManager(
            repo_root=REPO_ROOT,
            manifest_path=self.manifest_path,
            runtime_profile=self.runtime_profile,
            add_diag=self.add_diag,
            path_for_diag=self._path_for_diag,
            resolve_repo_path=resolve_repo_path,
        )
        if not framework_lock_mgr.verify(
            project_id=project_id,
            project_root=project_root,
            project_manifest_path=project_manifest_path,
            framework_paths=framework_paths,
        ):
            return None

        manifest_bundle = resolve_manifest_paths(
            framework_paths=framework_paths,
            project_id=project_id,
            project_root=project_root,
            project_manifest=project_manifest,
            resolve_repo_path=resolve_repo_path,
        )

        # Resolve module index path
        framework_module_index_path: Path | None = None
        raw_module_index_path = framework_paths.get("module_index")
        if isinstance(raw_module_index_path, str) and raw_module_index_path.strip():
            framework_module_index_path = resolve_repo_path(raw_module_index_path.strip())
        else:
            default_module_index = manifest_bundle.class_modules_root.parent / "module-index.yaml"
            if default_module_index.exists():
                framework_module_index_path = default_module_index

        # Resolve secrets root
        if self.secrets_root.strip():
            configured_secrets_root = self.secrets_root.strip()
            secrets_root_value = self._path_for_diag(resolve_repo_path(configured_secrets_root))
        elif manifest_bundle.secrets_root_path is not None:
            secrets_root_value = self._path_for_diag(manifest_bundle.secrets_root_path)
        else:
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="project manifest must resolve non-empty secrets_root path.",
                path=f"{self._path_for_diag(project_manifest_path)}:secrets_root",
            )
            return None

        return BootstrapResult(
            manifest=manifest,
            framework_paths=framework_paths,
            project_id=project_id,
            project_root=project_root,
            project_manifest=project_manifest,
            project_manifest_path=project_manifest_path,
            manifest_bundle=manifest_bundle,
            framework_module_index_path=framework_module_index_path,
            secrets_root_value=secrets_root_value,
        )

    def run(self) -> int:
        self._run_generated_at = utc_now()
        if self.trace_execution and self._plugin_registry:
            self._plugin_registry.reset_execution_trace()

        # Phases 1-4: Bootstrap (validation, manifest loading, framework lock)
        bootstrap = self._bootstrap_phase()
        if bootstrap is None:
            return self._fail_early()

        # Unpack bootstrap results for use in subsequent phases
        manifest = bootstrap.manifest
        manifest_bundle = bootstrap.manifest_bundle
        framework_module_index_path = bootstrap.framework_module_index_path
        secrets_root_value = bootstrap.secrets_root_value

        # Phase 5: Setup plugin context and execute pipeline
        self._load_base_plugin_manifest()
        source_manifest_digest = manifest_digest(manifest)
        workspace_root_path = self._project_scoped_root(self.workspace_root, manifest_bundle.project_id)
        dist_root_path = self._project_scoped_root(self.dist_root, manifest_bundle.project_id)
        if self.sbom_output_dir is not None:
            sbom_output_dir_path = self._project_scoped_root(self.sbom_output_dir, manifest_bundle.project_id)
        else:
            sbom_output_dir_path = dist_root_path / "sbom"

        inputs = load_core_compile_inputs(
            paths=manifest_bundle,
            instances_mode=self.instance_source_mode,
            load_yaml=self._load_yaml,
            add_diag=self.add_diag,
            repo_root=REPO_ROOT,
        )

        # Create shared plugin context (ADR 0063 Phase 3)
        # Context persists across stages so publish/subscribe works
        plugin_ctx: PluginContext | None = None
        plugin_ctx = create_plugin_context(
            manifest_path=self.manifest_path,
            repo_root=REPO_ROOT,
            runtime_profile=self.runtime_profile,
            strict_model_lock=self.strict_model_lock,
            pipeline_mode=self.pipeline_mode,
            parity_gate=self.parity_gate,
            raw_manifest=manifest,
            run_generated_at=self._run_generated_at or utc_now(),
            compiled_model_version=COMPILED_MODEL_VERSION,
            compiler_pipeline_version=COMPILER_PIPELINE_VERSION,
            source_manifest_digest=source_manifest_digest,
            class_modules_root=manifest_bundle.class_modules_root,
            object_modules_root=manifest_bundle.object_modules_root,
            project_id=manifest_bundle.project_id,
            project_root=manifest_bundle.project_root,
            project_manifest_path=manifest_bundle.project_manifest_path,
            class_map=inputs.class_map,
            object_map=inputs.object_map,
            instance_bindings=inputs.instance_payload or {},
            capability_catalog_path=manifest_bundle.capability_catalog_path,
            capability_packs_path=manifest_bundle.capability_packs_path,
            semantic_keywords_path=manifest_bundle.semantic_keywords_path,
            model_lock_path=manifest_bundle.model_lock_path,
            lock_payload=inputs.lock_payload,
            output_dir=self.output_json.parent,
            generator_artifacts_root=self.artifacts_root,
            workspace_root=workspace_root_path,
            dist_root=dist_root_path,
            signing_backend=self.signing_backend,
            release_tag=self.release_tag,
            sbom_output_dir=sbom_output_dir_path,
            source_file=self.manifest_path,
            compiled_file=self.output_json,
            require_new_model=self.require_new_model,
            secrets_mode=self.secrets_mode,
            secrets_root=secrets_root_value,
            validation_owner=self._validation_owner,
            compilation_owner=self._compilation_owner,
            artifact_owner=self._artifact_owner,
        )
        plugin_ctx.config["instance_source_mode"] = inputs.instance_source_mode
        plugin_ctx.config["discovered_plugin_manifests"] = list(self._discovered_manifest_paths)
        plugin_ctx.config["discovered_plugin_count"] = self._discovered_plugin_count
        plugin_ctx.config["base_plugins_manifest_path"] = str(self.plugins_manifest_path)
        plugin_ctx.config["plugin_registry"] = self._plugin_registry
        plugin_ctx.config["discover_load_module_manifests"] = lambda: self._load_module_plugin_manifests(
            class_modules_root=manifest_bundle.class_modules_root,
            object_modules_root=manifest_bundle.object_modules_root,
            project_plugins_root=manifest_bundle.project_root / "plugins",
            module_index_path=framework_module_index_path,
            emit_diagnostics=False,
        )
        plugin_ctx.config["project_plugins_root"] = self._path_for_diag(manifest_bundle.project_root / "plugins")
        if framework_module_index_path is not None:
            plugin_ctx.config["module_index_path"] = self._path_for_diag(framework_module_index_path)
        # Execute discover-stage plugins before compile/validate/generate lifecycle.
        if Stage.DISCOVER in self.stages:
            self._execute_plugins(stage=Stage.DISCOVER, ctx=plugin_ctx)
            discovered_paths = plugin_ctx.config.get("discovered_plugin_manifests")
            if isinstance(discovered_paths, list):
                self._discovered_manifest_paths = [item for item in discovered_paths if isinstance(item, str)]
            discovered_count = plugin_ctx.config.get("discovered_plugin_count")
            if isinstance(discovered_count, int):
                self._discovered_plugin_count = discovered_count
        elif not self._plugin_manifests_loaded:
            self._bootstrap_discover_manifest_loader(ctx=plugin_ctx)
            plugin_ctx.config["discovered_plugin_manifests"] = list(self._discovered_manifest_paths)
            plugin_ctx.config["discovered_plugin_count"] = self._discovered_plugin_count
        self._capture_published_key_inventory(plugin_ctx)
        if self._has_errors():
            return self._fail_early()
        if Stage.COMPILE not in self.stages:
            return self._finalize()

        # Phase 6: Execute compiler plugins
        self._execute_plugins(stage=Stage.COMPILE, ctx=plugin_ctx)
        apply_plugin_compile_outputs(
            inputs=inputs,
            plugin_ctx=plugin_ctx,
            compilation_owner=self._compilation_owner,
            add_diag=self.add_diag,
        )

        plugin_effective_payload = (
            plugin_ctx.compiled_json
            if plugin_ctx is not None and isinstance(plugin_ctx.compiled_json, dict) and plugin_ctx.compiled_json
            else None
        )
        effective_payload = select_effective_payload(
            plugin_payload=plugin_effective_payload,
            add_diag=self.add_diag,
        )
        if plugin_ctx:
            plugin_ctx.compiled_json = effective_payload
        compiled_contract_ok = self._validate_compiled_model_contract(effective_payload)

        # Execute validator plugins (ADR 0063)
        # Uses same context so validators can subscribe to compiler outputs
        if compiled_contract_ok and plugin_ctx and Stage.VALIDATE in self.stages:
            self._execute_plugins(stage=Stage.VALIDATE, ctx=plugin_ctx)

        errors = sum(1 for item in self._diagnostics if item.severity == "error")
        emit_effective_artifact(
            errors=errors,
            compiled_contract_ok=compiled_contract_ok,
            enable_plugins=True,
            run_generate_stage=Stage.GENERATE in self.stages,
            plugin_ctx=plugin_ctx,
            execute_plugins=lambda *, stage, ctx: self._execute_plugins(stage=Stage(stage), ctx=ctx),
            artifact_owner=self._artifact_owner,
            output_json=self.output_json,
            effective_payload=effective_payload,
            add_diag=self.add_diag,
            repo_root=REPO_ROOT,
        )
        # Phase 7: AI sessions (optional)
        if (self.ai_advisory or self.ai_assisted) and plugin_ctx is not None and not self._has_errors():
            ai_runner = AiSessionRunner(
                ai_config=self.ai_config,
                repo_root=REPO_ROOT,
                stages=self.stages,
                add_diag=self.add_diag,
                path_for_diag=self._path_for_diag,
            )
            if self.ai_advisory:
                ai_runner.run_advisory_session(
                    effective_payload=effective_payload,
                    project_id=manifest_bundle.project_id,
                    plugin_ctx=plugin_ctx,
                )
            if self.ai_assisted:
                ai_runner.run_assisted_session(
                    effective_payload=effective_payload,
                    project_id=manifest_bundle.project_id,
                    plugin_ctx=plugin_ctx,
                )

        if plugin_ctx is not None and not self._has_errors():
            if Stage.ASSEMBLE in self.stages:
                self._execute_plugins(stage=Stage.ASSEMBLE, ctx=plugin_ctx)
            if Stage.BUILD in self.stages and not self._has_errors():
                self._execute_plugins(stage=Stage.BUILD, ctx=plugin_ctx)
        self._capture_published_key_inventory(plugin_ctx)

        # Phase 8: Finalize
        return self._finalize(emit_effective=True)


def _set_cli_repo_root(repo_root: Path) -> None:
    global REPO_ROOT
    REPO_ROOT = repo_root


def _build_cli_dependencies() -> CompilerCliDependencies:
    return CompilerCliDependencies(
        compiler_cls=V5Compiler,
        repo_root=REPO_ROOT,
        default_topology_relative=DEFAULT_TOPOLOGY_RELATIVE,
        default_output_json=DEFAULT_OUTPUT_JSON,
        default_diagnostics_json=DEFAULT_DIAGNOSTICS_JSON,
        default_diagnostics_txt=DEFAULT_DIAGNOSTICS_TXT,
        default_error_catalog=DEFAULT_ERROR_CATALOG,
        default_artifacts_root=DEFAULT_ARTIFACTS_ROOT,
        default_workspace_root=DEFAULT_WORKSPACE_ROOT,
        default_dist_root=DEFAULT_DIST_ROOT,
        default_plugins_manifest=DEFAULT_PLUGINS_MANIFEST,
        supported_runtime_profiles=SUPPORTED_RUNTIME_PROFILES,
        supported_instance_source_modes=SUPPORTED_INSTANCE_SOURCE_MODES,
        supported_secrets_modes=SUPPORTED_SECRETS_MODES,
        stage_order=STAGE_ORDER,
        advisory_stage_set=ADVISORY_STAGE_SET,
        parse_stages_arg=parse_stages_arg,
        resolve_repo_path=resolve_repo_path,
        resolve_topology_path=resolve_topology_path,
        set_repo_root=_set_cli_repo_root,
    )


def build_parser():
    return build_compiler_parser(_build_cli_dependencies())


def main() -> int:
    return run_cli(_build_cli_dependencies())


if __name__ == "__main__":
    raise SystemExit(main())

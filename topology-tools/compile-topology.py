#!/usr/bin/env python3
"""Compile v5 topology manifest + modules + instance bindings into canonical JSON."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Add kernel to path for plugin imports
TOPOLOGY_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOPOLOGY_TOOLS))

from compiler_ai_sessions import AiConfig, AiSessionPreparation, json_safe_payload, prepare_ai_session
from compiler_cli import CompilerCliDependencies, build_parser as build_compiler_parser, run_cli
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
from framework_lock import default_framework_manifest_path
from framework_lock import resolve_paths as resolve_framework_lock_paths
from framework_lock import verify_framework_lock
from kernel import (
    KERNEL_VERSION,
    Phase,
    PluginContext,
    PluginRegistry,
    PluginResult,
    PluginStatus,
    STAGE_ORDER,
    Stage,
)
from plugin_manifest_discovery import discover_plugin_manifest_paths, validate_module_index_consistency
from plugins.generators.ai_advisory_contract import parse_ai_output_payload, validate_ai_contract_payloads
from plugins.generators.ai_ansible import (
    parse_ansible_output_candidates,
    validate_ansible_candidates_with_lint,
)
from plugins.generators.ai_assisted import build_candidate_diff, materialize_candidate_artifacts
from plugins.generators.ai_promotion import promote_approved_candidates, resolve_approvals
from plugins.generators.ai_rollback import list_ai_promoted_artifacts, rollback_ai_promoted_artifacts
from plugins.generators.ai_sandbox import enforce_sandbox_resource_limits
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

SUPPORTED_RUNTIME_PROFILES = ("production", "modeled", "test-real")
SUPPORTED_INSTANCE_SOURCE_MODES = ("auto", "sharded-only")
SUPPORTED_SECRETS_MODES = ("inject", "passthrough", "strict")
FRAMEWORK_LOCK_LOAD_CODES = {"E7821", "E7822"}
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

    def _verify_framework_lock(
        self,
        *,
        project_id: str,
        project_root: Path,
        project_manifest_path: Path,
        framework_paths: dict[str, Any],
    ) -> bool:
        framework_root_value = framework_paths.get("root")
        if isinstance(framework_root_value, str) and framework_root_value.strip():
            lock_framework_root = resolve_repo_path(framework_root_value.strip())
        else:
            lock_framework_root = REPO_ROOT

        try:
            lock_paths = resolve_framework_lock_paths(
                repo_root=REPO_ROOT,
                topology_path=self.manifest_path,
                project_id=project_id,
                project_root=project_root,
                project_manifest_path=project_manifest_path,
                framework_root=lock_framework_root,
                framework_manifest_path=default_framework_manifest_path(lock_framework_root),
                lock_path=None,
            )
        except (OSError, ValueError) as exc:
            self.add_diag(
                code="E7827",
                severity="error",
                stage="load",
                message=f"framework lock path resolution failed: {exc}",
                path=self._path_for_diag(self.manifest_path),
            )
            return False

        try:
            verification = verify_framework_lock(paths=lock_paths, strict=True)
        except (OSError, ValueError) as exc:
            self.add_diag(
                code="E7827",
                severity="error",
                stage="validate",
                message=f"framework lock verification failed: {exc}",
                path=self._path_for_diag(lock_paths.lock_path),
            )
            return False

        for item in verification.diagnostics:
            stage = "load" if item.code in FRAMEWORK_LOCK_LOAD_CODES else "validate"
            self.add_diag(
                code=item.code,
                severity=item.severity,
                stage=stage,
                message=item.message,
                path=item.path,
            )
        return verification.ok

    @staticmethod
    def _advisory_payload_hash(payload: dict[str, Any]) -> str:
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")).hexdigest()
        return f"sha256-{digest}"

    @staticmethod
    def _json_safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return json_safe_payload(payload)

    @staticmethod
    def _extract_path_leaf_token(path: str) -> str:
        token = path.split(".")[-1].strip()
        token = re.sub(r"\[\d+\]", "", token)
        return token

    def _collect_annotation_redaction_patterns(self, plugin_ctx: PluginContext | None) -> tuple[re.Pattern[str], ...]:
        if plugin_ctx is None:
            return ()
        names: set[str] = set()
        published = plugin_ctx.get_published_data().get("base.compiler.annotation_resolver", {})
        for key in ("object_secret_annotations", "row_annotations_by_instance"):
            container = published.get(key)
            if not isinstance(container, dict):
                continue
            for _, annotations in container.items():
                if not isinstance(annotations, dict):
                    continue
                for path, spec in annotations.items():
                    if not isinstance(path, str) or not isinstance(spec, dict):
                        continue
                    if not bool(spec.get("secret")):
                        continue
                    leaf = self._extract_path_leaf_token(path)
                    if leaf:
                        names.add(leaf)
        return tuple(re.compile(re.escape(name), re.IGNORECASE) for name in sorted(names))

    def _collect_registry_redaction_patterns(self, plugin_ctx: PluginContext | None) -> tuple[re.Pattern[str], ...]:
        if plugin_ctx is None:
            return ()
        secrets_root_raw = plugin_ctx.config.get("secrets_root")
        if not isinstance(secrets_root_raw, str) or not secrets_root_raw.strip():
            return ()
        secrets_root = Path(secrets_root_raw.strip())
        if not secrets_root.is_absolute():
            secrets_root = (REPO_ROOT / secrets_root).resolve()
        instances_dir = secrets_root / "instances"
        if not instances_dir.exists() or not instances_dir.is_dir():
            return ()

        names: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if isinstance(key, str) and key not in {"sops", "instance"}:
                        names.add(key.strip())
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        for path in sorted(instances_dir.glob("*.yaml")):
            try:
                payload = load_yaml_file(path) or {}
            except Exception:
                continue
            walk(payload)
        names = {name for name in names if name}
        return tuple(re.compile(re.escape(name), re.IGNORECASE) for name in sorted(names))

    def _load_ai_output_payload(self) -> dict[str, Any] | None:
        if self.ai_output_json is None:
            return None
        path = self.ai_output_json
        if not path.exists() or not path.is_file():
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message=f"AI advisory output JSON does not exist: {path}",
                path=self._path_for_diag(path),
            )
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message=f"AI advisory output JSON parse error: {exc}",
                path=self._path_for_diag(path),
            )
            return None
        if not isinstance(payload, dict):
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message="AI advisory output JSON root must be an object.",
                path=self._path_for_diag(path),
            )
            return None
        return payload

    def _print_advisory_recommendations(self, parsed_output: dict[str, Any]) -> None:
        recommendations = parsed_output.get("recommendations", [])
        confidence_scores = parsed_output.get("confidence_scores", {})
        LOGGER.info("[ai-advisory] Recommendations:")
        if not isinstance(recommendations, list) or not recommendations:
            LOGGER.info("[ai-advisory] - No recommendations.")
            return
        for index, row in enumerate(recommendations, start=1):
            if not isinstance(row, dict):
                continue
            path = str(row.get("path", "<unknown>"))
            action = str(row.get("action", "suggest"))
            rationale = str(row.get("rationale", "")).strip()
            score = confidence_scores.get(path) if isinstance(confidence_scores, dict) else None
            score_token = f"{float(score):.2f}" if isinstance(score, (int, float)) else "n/a"
            LOGGER.info(f"[ai-advisory] {index}. {action} {path} (confidence={score_token})")
            if rationale:
                LOGGER.info(f"[ai-advisory]    rationale: {rationale}")

    def _prepare_ai_session(
        self,
        *,
        mode: str,
        effective_payload: dict[str, Any],
        project_id: str,
        plugin_ctx: PluginContext | None,
        plugin_id: str,
        enforce_initial_sandbox_limits: bool,
    ) -> AiSessionPreparation:
        return prepare_ai_session(
            ai_config=self.ai_config,
            repo_root=REPO_ROOT,
            mode=mode,
            effective_payload=effective_payload,
            project_id=project_id,
            plugin_id=plugin_id,
            stages=self.stages,
            enforce_initial_sandbox_limits=enforce_initial_sandbox_limits,
            annotation_patterns=self._collect_annotation_redaction_patterns(plugin_ctx),
            registry_patterns=self._collect_registry_redaction_patterns(plugin_ctx),
        )

    def _run_ai_advisory_session(
        self,
        *,
        effective_payload: dict[str, Any],
        project_id: str,
        plugin_ctx: PluginContext | None,
    ) -> None:
        start_ts = time.monotonic()
        session = self._prepare_ai_session(
            mode="advisory",
            effective_payload=effective_payload,
            project_id=project_id,
            plugin_ctx=plugin_ctx,
            plugin_id="base.compiler.ai_advisory",
            enforce_initial_sandbox_limits=True,
        )
        if session.cleaned_audit_logs:
            LOGGER.info(f"[ai-advisory] Cleaned {len(session.cleaned_audit_logs)} old audit day folders.")
        if session.cleaned_sandbox_sessions:
            LOGGER.info(f"[ai-advisory] Cleaned {len(session.cleaned_sandbox_sessions)} old sandbox sessions.")
        LOGGER.info(f"[ai-advisory] Sandbox session: {self._path_for_diag(session.sandbox_session)}")
        ai_input = session.ai_input
        ai_output = self._load_ai_output_payload()
        errors = validate_ai_contract_payloads(ai_input=ai_input, ai_output=ai_output, ctx=plugin_ctx)
        if errors:
            for message in errors:
                self.add_diag(
                    code="E8941",
                    severity="error",
                    stage="validate",
                    message=message,
                    path="ai-advisory:contract",
                )
            session.audit.log_event(
                event_type="candidate_validation_result",
                payload={"mode": "advisory", "status": "contract_error", "errors": errors},
                input_hash=str(ai_input.get("input_hash", "")),
            )
            return

        input_hash = str(ai_input.get("input_hash", ""))
        session.audit.log_event(
            event_type="ai_request_sent",
            payload={
                "mode": "advisory",
                "sandbox_session": self._path_for_diag(session.sandbox_session),
                "sandbox_usage": session.sandbox_usage,
                "sandbox_limits": {
                    "max_files": self.ai_config.sandbox_max_files,
                    "max_bytes": self.ai_config.sandbox_max_bytes,
                },
                "annotation_pattern_count": len(session.annotation_patterns),
                "registry_pattern_count": len(session.registry_patterns),
                "env_keys_forwarded": len(session.sanitized_env),
                "env_keys_removed": session.removed_env_keys,
            },
            input_hash=input_hash,
        )
        parsed: dict[str, Any] = {"recommendations": [], "confidence_scores": {}, "metadata": {}}
        output_hash = ""
        if ai_output is not None:
            output_hash = self._advisory_payload_hash(ai_output)
            parsed = parse_ai_output_payload(ai_output)
            session.audit.log_event(
                event_type="ai_response_received",
                payload={
                    "mode": "advisory",
                    "recommendation_count": len(parsed.get("recommendations", [])),
                },
                input_hash=input_hash,
                output_hash=output_hash,
            )
        self._print_advisory_recommendations(parsed)
        session.audit.log_event(
            event_type="candidate_validation_result",
            payload={
                "mode": "advisory",
                "status": "completed",
                "recommendation_count": len(parsed.get("recommendations", [])),
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )
        elapsed = time.monotonic() - start_ts
        if elapsed > self.ai_config.advisory_max_latency_seconds:
            self.add_diag(
                code="W8941",
                severity="warning",
                stage="validate",
                message=(
                    "AI advisory latency exceeded configured limit: "
                    f"{elapsed:.2f}s > {self.ai_config.advisory_max_latency_seconds:.2f}s"
                ),
                path="ai-advisory:latency",
            )
        LOGGER.info(f"[ai-advisory] Audit log: {self._path_for_diag(session.audit.log_path)}")

    def _run_ai_assisted_session(
        self,
        *,
        effective_payload: dict[str, Any],
        project_id: str,
        plugin_ctx: PluginContext | None,
    ) -> None:
        start_ts = time.monotonic()
        session = self._prepare_ai_session(
            mode="assisted",
            effective_payload=effective_payload,
            project_id=project_id,
            plugin_ctx=plugin_ctx,
            plugin_id="base.compiler.ai_assisted",
            enforce_initial_sandbox_limits=False,
        )
        if session.cleaned_audit_logs:
            LOGGER.info(f"[ai-assisted] Cleaned {len(session.cleaned_audit_logs)} old audit day folders.")
        if session.cleaned_sandbox_sessions:
            LOGGER.info(f"[ai-assisted] Cleaned {len(session.cleaned_sandbox_sessions)} old sandbox sessions.")
        LOGGER.info(f"[ai-assisted] Sandbox session: {self._path_for_diag(session.sandbox_session)}")

        ai_input = session.ai_input
        ai_output = self._load_ai_output_payload()
        errors = validate_ai_contract_payloads(ai_input=ai_input, ai_output=ai_output, ctx=plugin_ctx)
        if errors:
            for message in errors:
                self.add_diag(
                    code="E8941",
                    severity="error",
                    stage="validate",
                    message=message,
                    path="ai-assisted:contract",
                )
            session.audit.log_event(
                event_type="candidate_validation_result",
                payload={"mode": "assisted", "status": "contract_error", "errors": errors},
                input_hash=str(ai_input.get("input_hash", "")),
            )
            return

        input_hash = str(ai_input.get("input_hash", ""))
        session.audit.log_event(
            event_type="ai_request_sent",
            payload={
                "mode": "assisted",
                "sandbox_session": self._path_for_diag(session.sandbox_session),
                "annotation_pattern_count": len(session.annotation_patterns),
                "registry_pattern_count": len(session.registry_patterns),
                "env_keys_forwarded": len(session.sanitized_env),
                "env_keys_removed": session.removed_env_keys,
            },
            input_hash=input_hash,
        )
        rollback_requested = self.ai_config.rollback_all or bool(self.ai_config.rollback_paths)
        if rollback_requested:
            rollback_candidates = list_ai_promoted_artifacts(repo_root=REPO_ROOT, project_id=project_id)
            if self.ai_config.rollback_all:
                targets = rollback_candidates
            else:
                wanted = set(self.ai_config.rollback_paths)
                targets = [row for row in rollback_candidates if str(row.get("path", "")) in wanted]
            rollback = rollback_ai_promoted_artifacts(
                repo_root=REPO_ROOT,
                artifacts=targets,
                ref=self.ai_config.rollback_ref,
            )
            LOGGER.info(
                "[ai-assisted] rollback: "
                f"restored={len(rollback['restored'])} "
                f"deleted={len(rollback['deleted'])} "
                f"failed={len(rollback['failed'])} "
                f"duration={rollback['duration_seconds']:.3f}s"
            )
            session.audit.log_event(
                event_type="rollback_result",
                payload={
                    "mode": "assisted",
                    "ref": self.ai_config.rollback_ref,
                    "target_count": len(targets),
                    "restored": rollback["restored"],
                    "deleted": rollback["deleted"],
                    "failed": rollback["failed"],
                    "duration_seconds": rollback["duration_seconds"],
                },
                input_hash=input_hash,
            )
            LOGGER.info(f"[ai-assisted] Audit log: {self._path_for_diag(session.audit.log_path)}")
            return
        if ai_output is None:
            self.add_diag(
                code="E8941",
                severity="error",
                stage="validate",
                message="AI assisted mode requires --ai-output-json payload.",
                path="ai-assisted:output",
            )
            return

        output_hash = self._advisory_payload_hash(ai_output)
        parsed = parse_ai_output_payload(ai_output)
        raw_candidates = ai_output.get("candidate_artifacts")
        candidates = raw_candidates if isinstance(raw_candidates, list) else []
        accepted, rejected = materialize_candidate_artifacts(
            repo_root=REPO_ROOT,
            sandbox_session=session.sandbox_session,
            project_id=project_id,
            candidates=[row for row in candidates if isinstance(row, dict)],
        )
        for row in accepted:
            diff_payload = build_candidate_diff(
                baseline_path=Path(row["baseline_path"]),
                candidate_path=Path(row["candidate_path"]),
                logical_path=str(row["path"]),
            )
            LOGGER.info(
                f"[ai-assisted] {diff_payload['change_type']}: "
                f"{diff_payload['path']} (added_lines={diff_payload['added_lines']})"
            )
            confidence = parsed.get("confidence_scores", {}).get(str(row["path"]))
            if isinstance(confidence, (int, float)):
                LOGGER.info(f"[ai-assisted]   confidence: {float(confidence):.2f}")
        if rejected:
            for row in rejected:
                LOGGER.info(f"[ai-assisted] rejected: {row['path']} ({row['reason']})")
        ansible_candidates = parse_ansible_output_candidates(project_id=project_id, ai_output=ai_output)
        if self.ai_config.ansible_lint and ansible_candidates:
            lint_failures = validate_ansible_candidates_with_lint(
                candidates=accepted,
                lint_cmd=self.ai_config.ansible_lint_cmd,
            )
            if lint_failures:
                rejected.extend(lint_failures)
                accepted = [
                    row for row in accepted if str(row.get("path", "")) not in {f["path"] for f in lint_failures}
                ]
                for item in lint_failures:
                    LOGGER.info(f"[ai-assisted] lint-rejected: {item['path']} ({item['reason']})")

        enforce_sandbox_resource_limits(
            sandbox_session=session.sandbox_session,
            max_files=self.ai_config.sandbox_max_files,
            max_bytes=self.ai_config.sandbox_max_bytes,
        )
        approve_paths_set = set(self.ai_config.approve_paths)
        approved, approval_rejected = resolve_approvals(
            candidates=accepted,
            approve_all=self.ai_config.approve_all,
            approve_paths=approve_paths_set,
        )
        session.audit.log_event(
            event_type="human_approval_decision",
            payload={
                "mode": "assisted",
                "approve_all": self.ai_config.approve_all,
                "approved_count": len(approved),
                "rejected_count": len(approval_rejected),
                "approved_paths": [str(row.get("path", "")) for row in approved],
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )

        promoted: list[dict[str, str]] = []
        if self.ai_config.promote_approved:
            if not approved:
                LOGGER.info("[ai-assisted] promotion skipped: no approved candidates.")
            else:
                promoted = promote_approved_candidates(repo_root=REPO_ROOT, approved=approved)
                for row in promoted:
                    LOGGER.info(f"[ai-assisted] promoted: {row['path']}")
        else:
            LOGGER.info("[ai-assisted] promotion gate: disabled (use --ai-promote-approved).")

        session.audit.log_event(
            event_type="ai_response_received",
            payload={
                "mode": "assisted",
                "candidate_count": len(candidates),
                "accepted_candidates": len(accepted),
                "rejected_candidates": len(rejected),
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )
        session.audit.log_event(
            event_type="candidate_validation_result",
            payload={
                "mode": "assisted",
                "status": "completed",
                "accepted_candidates": len(accepted),
                "rejected_candidates": len(rejected),
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )
        session.audit.log_event(
            event_type="candidate_promotion_result",
            payload={
                "mode": "assisted",
                "promotion_enabled": self.ai_config.promote_approved,
                "promoted_count": len(promoted),
                "promoted_paths": [row["path"] for row in promoted],
            },
            input_hash=input_hash,
            output_hash=output_hash,
        )
        elapsed = time.monotonic() - start_ts
        if elapsed > self.ai_config.assisted_max_latency_seconds:
            self.add_diag(
                code="W8941",
                severity="warning",
                stage="validate",
                message=(
                    "AI assisted latency exceeded configured limit: "
                    f"{elapsed:.2f}s > {self.ai_config.assisted_max_latency_seconds:.2f}s"
                ),
                path="ai-assisted:latency",
            )
        LOGGER.info(f"[ai-assisted] Audit log: {self._path_for_diag(session.audit.log_path)}")

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

    def run(self) -> int:
        self._run_generated_at = utc_now()
        if self.trace_execution and self._plugin_registry:
            self._plugin_registry.reset_execution_trace()
        if not self._validate_stage_selection():
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1
        if self.pipeline_mode != "plugin-first":
            self.add_diag(
                code="E6904",
                severity="error",
                stage="validate",
                message=("pipeline_mode=legacy is retired after ADR0069 cutover; " "use --pipeline-mode plugin-first."),
                path="pipeline:mode",
            )
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        if self.parity_gate:
            self.add_diag(
                code="E6905",
                severity="error",
                stage="validate",
                message="--parity-gate is not supported after plugin-first cutover.",
                path="pipeline:parity",
            )
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        manifest = self._load_yaml(self.manifest_path, code_missing="E1001", code_parse="E1003", stage="load")
        if manifest is None:
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        legacy_paths = manifest.get("paths")
        if legacy_paths is not None:
            self.add_diag(
                code="E7808",
                severity="error",
                stage="validate",
                message="Legacy manifest contract section 'paths' is unsupported in strict-only mode.",
                path="topology/topology.yaml:paths",
            )
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        framework_paths = manifest.get("framework")
        if not isinstance(framework_paths, dict):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="topology manifest must contain mapping key 'framework'.",
                path="topology/topology.yaml:framework",
            )
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        project_section = manifest.get("project")
        if not isinstance(project_section, dict):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="topology manifest must contain mapping key 'project'.",
                path="topology/topology.yaml:project",
            )
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

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
        if any(item.severity == "error" for item in self._diagnostics):
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        project_id = str(project_section["active"]).strip()
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
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

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
        if any(item.severity == "error" for item in self._diagnostics):
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        if not self._verify_framework_lock(
            project_id=project_id,
            project_root=project_root,
            project_manifest_path=project_manifest_path,
            framework_paths=framework_paths,
        ):
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        manifest_bundle = resolve_manifest_paths(
            framework_paths=framework_paths,
            project_id=project_id,
            project_root=project_root,
            project_manifest=project_manifest,
            resolve_repo_path=resolve_repo_path,
        )
        framework_module_index_path: Path | None = None
        raw_module_index_path = framework_paths.get("module_index")
        if isinstance(raw_module_index_path, str) and raw_module_index_path.strip():
            framework_module_index_path = resolve_repo_path(raw_module_index_path.strip())
        else:
            default_module_index = manifest_bundle.class_modules_root.parent / "module-index.yaml"
            if default_module_index.exists():
                framework_module_index_path = default_module_index
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
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

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
        if any(item.severity == "error" for item in self._diagnostics):
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1
        if Stage.COMPILE not in self.stages:
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            if errors > 0:
                return 1
            if self.fail_on_warning and warnings > 0:
                return 2
            return 0
        # Execute compiler plugins first
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
        if (
            self.ai_advisory
            and plugin_ctx is not None
            and not any(item.severity == "error" for item in self._diagnostics)
        ):
            self._run_ai_advisory_session(
                effective_payload=effective_payload,
                project_id=manifest_bundle.project_id,
                plugin_ctx=plugin_ctx,
            )
        if (
            self.ai_assisted
            and plugin_ctx is not None
            and not any(item.severity == "error" for item in self._diagnostics)
        ):
            self._run_ai_assisted_session(
                effective_payload=effective_payload,
                project_id=manifest_bundle.project_id,
                plugin_ctx=plugin_ctx,
            )

        if plugin_ctx is not None and not any(item.severity == "error" for item in self._diagnostics):
            if Stage.ASSEMBLE in self.stages:
                self._execute_plugins(stage=Stage.ASSEMBLE, ctx=plugin_ctx)
            if Stage.BUILD in self.stages and not any(item.severity == "error" for item in self._diagnostics):
                self._execute_plugins(stage=Stage.BUILD, ctx=plugin_ctx)
        self._capture_published_key_inventory(plugin_ctx)

        total, errors, warnings, infos = self._write_diagnostics()
        self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=True)

        if errors > 0:
            return 1
        if self.fail_on_warning and warnings > 0:
            return 2
        return 0


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

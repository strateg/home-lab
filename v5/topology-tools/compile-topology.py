#!/usr/bin/env python3
"""Compile v5 topology manifest + modules + instance bindings into canonical JSON."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Add kernel to path for plugin imports
TOPOLOGY_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOPOLOGY_TOOLS))

from compiler_contract import manifest_digest, validate_compiled_model_contract
from compiler_decisions import select_effective_payload
from compiler_ownership import artifact_owner, compilation_owner, validation_owner
from compiler_plugin_context import create_plugin_context
from compiler_reporting import write_diagnostics_report
from compiler_runtime import (
    apply_plugin_compile_outputs,
    discover_plugin_manifests,
    emit_effective_artifact,
    load_core_compile_inputs,
    resolve_manifest_paths,
)
from kernel import KERNEL_VERSION, PluginContext, PluginDiagnostic, PluginRegistry, PluginResult, PluginStatus, Stage

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "v5" / "topology" / "topology.yaml"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "v5-build" / "effective-topology.json"
DEFAULT_DIAGNOSTICS_JSON = REPO_ROOT / "v5-build" / "diagnostics" / "report.json"
DEFAULT_DIAGNOSTICS_TXT = REPO_ROOT / "v5-build" / "diagnostics" / "report.txt"
DEFAULT_ARTIFACTS_ROOT = REPO_ROOT / "v5-generated"
DEFAULT_ERROR_CATALOG = REPO_ROOT / "v5" / "topology-tools" / "data" / "error-catalog.yaml"
DEFAULT_PLUGINS_MANIFEST = TOPOLOGY_TOOLS / "plugins" / "plugins.yaml"

SUPPORTED_RUNTIME_PROFILES = ("production", "modeled", "test-real")
SUPPORTED_INSTANCE_SOURCE_MODES = ("auto", "sharded-only")
SUPPORTED_SECRETS_MODES = ("inject", "passthrough", "strict")
COMPILED_MODEL_VERSION = "1.0"
COMPILER_PIPELINE_VERSION = "adr0069-ws2"
SUPPORTED_COMPILED_MODEL_MAJOR = {"1"}


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Diagnostic:
    code: str
    severity: str
    stage: str
    message: str
    path: str
    confidence: float = 0.95
    hint: str | None = None
    plugin_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "path": self.path,
            "confidence": self.confidence,
            "autofix": {"possible": False},
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.plugin_id:
            payload["plugin_id"] = self.plugin_id
        return payload

    @classmethod
    def from_plugin_diagnostic(cls, plugin_diag: PluginDiagnostic) -> "Diagnostic":
        """Convert a PluginDiagnostic to a Diagnostic."""
        return cls(
            code=plugin_diag.code,
            severity=plugin_diag.severity,
            stage=plugin_diag.stage,
            message=plugin_diag.message,
            path=plugin_diag.path,
            confidence=plugin_diag.confidence,
            hint=plugin_diag.hint,
            plugin_id=plugin_diag.plugin_id,
        )


class V5Compiler:
    def __init__(
        self,
        *,
        manifest_path: Path,
        output_json: Path,
        diagnostics_json: Path,
        diagnostics_txt: Path,
        artifacts_root: Path,
        error_catalog_path: Path,
        strict_model_lock: bool,
        fail_on_warning: bool,
        require_new_model: bool,
        runtime_profile: str = "production",
        instance_source_mode: str = "auto",
        secrets_mode: str = "passthrough",
        pipeline_mode: str = "plugin-first",
        parity_gate: bool = False,
        enable_plugins: bool = True,
        plugins_manifest_path: Path | None = None,
    ) -> None:
        if not enable_plugins:
            raise ValueError("--disable-plugins is retired; plugin-first runtime always enables plugins.")

        self.manifest_path = manifest_path
        self.output_json = output_json
        self.diagnostics_json = diagnostics_json
        self.diagnostics_txt = diagnostics_txt
        self.artifacts_root = artifacts_root
        self.error_catalog_path = error_catalog_path
        self.strict_model_lock = strict_model_lock
        self.fail_on_warning = fail_on_warning
        self.require_new_model = require_new_model
        self.runtime_profile = runtime_profile
        self.instance_source_mode = instance_source_mode
        self.secrets_mode = secrets_mode
        self.pipeline_mode = pipeline_mode
        self.parity_gate = parity_gate
        self.enable_plugins = enable_plugins
        self.plugins_manifest_path = plugins_manifest_path or DEFAULT_PLUGINS_MANIFEST

        self._diagnostics: list[Diagnostic] = []
        self._error_hints = self._load_error_hints(error_catalog_path)
        self._plugin_registry: PluginRegistry | None = None
        self._plugin_results: list[PluginResult] = []
        self._run_generated_at: str | None = None
        self._plugin_manifests_loaded = False
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
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
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

    def _load_plugin_manifests(self, *, class_modules_root: Path, object_modules_root: Path) -> None:
        """Load base + module plugin manifests in deterministic order."""
        if not self._plugin_registry or self._plugin_manifests_loaded:
            return

        ordered_manifests = discover_plugin_manifests(
            base_manifest_path=self.plugins_manifest_path,
            class_modules_root=class_modules_root,
            object_modules_root=object_modules_root,
        )

        loaded_count = 0
        module_manifest_count = 0

        for idx, manifest_path in enumerate(ordered_manifests):
            if not manifest_path.exists():
                if idx == 0:
                    self.add_diag(
                        code="W4001",
                        severity="warning",
                        stage="load",
                        message=f"Plugin manifest not found: {manifest_path}",
                        path=self._path_for_diag(manifest_path),
                    )
                continue

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
                continue
            loaded_count += 1
            if idx > 0:
                module_manifest_count += 1

            load_errors = self._plugin_registry.get_load_errors()
            for err in load_errors[errors_before:]:
                self.add_diag(
                    code="E4001",
                    severity="error",
                    stage="load",
                    message=f"Plugin load error: {err}",
                    path=self._path_for_diag(manifest_path),
                )

        self._plugin_manifests_loaded = True
        self.add_diag(
            code="I4001",
            severity="info",
            stage="load",
            message=(
                f"Plugin kernel v{KERNEL_VERSION} initialized with {len(self._plugin_registry.specs)} plugins "
                f"from {loaded_count} manifest(s), including {module_manifest_count} module-level manifest(s)."
            ),
            path=self._path_for_diag(self.plugins_manifest_path),
            confidence=1.0,
        )

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
        results = self._plugin_registry.execute_stage(
            stage,
            ctx,
            profile=self.runtime_profile,
            fail_fast=stage == Stage.COMPILE,
        )
        self._plugin_results.extend(results)

        # Convert plugin diagnostics to compiler diagnostics
        for result in results:
            for plugin_diag in result.diagnostics:
                diag = Diagnostic.from_plugin_diagnostic(plugin_diag)
                self._diagnostics.append(diag)

            # Add execution info diagnostic
            if result.status == PluginStatus.TIMEOUT:
                self.add_diag(
                    code="E4101",
                    severity="error",
                    stage=str(stage.value),
                    message=f"Plugin '{result.plugin_id}' timed out after {result.duration_ms:.0f}ms",
                    path=f"plugin:{result.plugin_id}",
                )
            elif result.status == PluginStatus.FAILED and result.error_traceback:
                # Extract last meaningful line from traceback
                tb_lines = [line for line in result.error_traceback.strip().split("\n") if line.strip()]
                error_msg = tb_lines[-1] if tb_lines else "unknown error"
                self.add_diag(
                    code="E4102",
                    severity="error",
                    stage=str(stage.value),
                    message=f"Plugin '{result.plugin_id}' crashed: {error_msg}",
                    path=f"plugin:{result.plugin_id}",
                )

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
            Diagnostic(
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
                path=str(path.relative_to(REPO_ROOT).as_posix()),
            )
            return None
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.add_diag(
                code=code_parse,
                severity="error",
                stage=stage,
                message=f"YAML parse error: {exc}",
                path=str(path.relative_to(REPO_ROOT).as_posix()),
            )
            return None
        if not isinstance(payload, dict):
            self.add_diag(
                code="E1004",
                severity="error",
                stage=stage,
                message="Expected mapping/object at YAML root.",
                path=str(path.relative_to(REPO_ROOT).as_posix()),
            )
            return None
        return payload

    def _write_diagnostics(self) -> tuple[int, int, int, int]:
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

    def _print_summary(self, *, total: int, errors: int, warnings: int, infos: int, emit_effective: bool) -> None:
        print(f"Compile summary: total={total} errors={errors} warnings={warnings} infos={infos}")
        print(f"Diagnostics JSON: {self.diagnostics_json}")
        print(f"Diagnostics TXT:  {self.diagnostics_txt}")
        if emit_effective and errors == 0:
            print(f"Effective JSON:   {self.output_json}")

    def run(self) -> int:
        self._run_generated_at = utc_now()
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

        manifest_paths = manifest.get("paths")
        if not isinstance(manifest_paths, dict):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="topology manifest must contain mapping key 'paths'.",
                path="v5/topology/topology.yaml",
            )
            total, errors, warnings, infos = self._write_diagnostics()
            self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=False)
            return 1

        manifest_bundle = resolve_manifest_paths(
            manifest_paths=manifest_paths,
            resolve_repo_path=resolve_repo_path,
        )
        self._load_plugin_manifests(
            class_modules_root=manifest_bundle.class_modules_root,
            object_modules_root=manifest_bundle.object_modules_root,
        )
        source_manifest_digest = manifest_digest(manifest)

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
            class_map=inputs.class_map,
            object_map=inputs.object_map,
            instance_bindings=inputs.instance_payload or {},
            capability_catalog_path=manifest_bundle.capability_catalog_path,
            capability_packs_path=manifest_bundle.capability_packs_path,
            model_lock_path=manifest_bundle.model_lock_path,
            lock_payload=inputs.lock_payload,
            output_dir=self.output_json.parent,
            generator_artifacts_root=self.artifacts_root,
            source_file=self.manifest_path,
            compiled_file=self.output_json,
            require_new_model=self.require_new_model,
            secrets_mode=self.secrets_mode,
            validation_owner=self._validation_owner,
            compilation_owner=self._compilation_owner,
            artifact_owner=self._artifact_owner,
        )
        plugin_ctx.config["instance_source_mode"] = inputs.instance_source_mode
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
        if compiled_contract_ok and plugin_ctx:
            self._execute_plugins(stage=Stage.VALIDATE, ctx=plugin_ctx)

        errors = sum(1 for item in self._diagnostics if item.severity == "error")
        emit_effective_artifact(
            errors=errors,
            compiled_contract_ok=compiled_contract_ok,
            enable_plugins=True,
            plugin_ctx=plugin_ctx,
            execute_plugins=lambda *, stage, ctx: self._execute_plugins(stage=Stage(stage), ctx=ctx),
            artifact_owner=self._artifact_owner,
            output_json=self.output_json,
            effective_payload=effective_payload,
            add_diag=self.add_diag,
            repo_root=REPO_ROOT,
        )

        total, errors, warnings, infos = self._write_diagnostics()
        self._print_summary(total=total, errors=errors, warnings=warnings, infos=infos, emit_effective=True)

        if errors > 0:
            return 1
        if self.fail_on_warning and warnings > 0:
            return 2
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile v5 topology manifest into canonical JSON.")
    parser.add_argument(
        "--topology",
        default=str(DEFAULT_MANIFEST.relative_to(REPO_ROOT).as_posix()),
        help="Path to v5 topology manifest YAML.",
    )
    parser.add_argument(
        "--output-json",
        default=str(DEFAULT_OUTPUT_JSON.relative_to(REPO_ROOT).as_posix()),
        help="Path to effective topology JSON output.",
    )
    parser.add_argument(
        "--diagnostics-json",
        default=str(DEFAULT_DIAGNOSTICS_JSON.relative_to(REPO_ROOT).as_posix()),
        help="Path to diagnostics JSON output.",
    )
    parser.add_argument(
        "--diagnostics-txt",
        default=str(DEFAULT_DIAGNOSTICS_TXT.relative_to(REPO_ROOT).as_posix()),
        help="Path to diagnostics TXT output.",
    )
    parser.add_argument(
        "--error-catalog",
        default=str(DEFAULT_ERROR_CATALOG.relative_to(REPO_ROOT).as_posix()),
        help="Path to error catalog YAML.",
    )
    parser.add_argument(
        "--artifacts-root",
        default=str(DEFAULT_ARTIFACTS_ROOT.relative_to(REPO_ROOT).as_posix()),
        help="Root directory for generator-produced deployable artifacts (for example terraform/ansible/bootstrap).",
    )
    parser.add_argument(
        "--strict-model-lock",
        action="store_true",
        help="Treat unpinned class/object references as errors.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Return non-zero exit code when warnings are present.",
    )
    parser.add_argument(
        "--require-new-model",
        action="store_true",
        help="Require ADR 0064 firmware_ref/os_refs model; legacy software.os fields are errors.",
    )
    parser.add_argument(
        "--profile",
        choices=list(SUPPORTED_RUNTIME_PROFILES),
        default="production",
        help="Runtime execution profile for plugin restrictions and diagnostics.",
    )
    parser.add_argument(
        "--instance-source-mode",
        choices=list(SUPPORTED_INSTANCE_SOURCE_MODES),
        default="auto",
        help=("Instance source mode: sharded-only or auto " "(auto resolves to sharded-only)."),
    )
    parser.add_argument(
        "--secrets-mode",
        choices=list(SUPPORTED_SECRETS_MODES),
        default="passthrough",
        help="Secrets resolution mode for instance fields: inject, passthrough, or strict.",
    )
    parser.add_argument(
        "--pipeline-mode",
        choices=["plugin-first"],
        default="plugin-first",
        help="Pipeline mode (plugin-first only).",
    )
    parser.add_argument(
        "--plugins-manifest",
        default=str(DEFAULT_PLUGINS_MANIFEST.relative_to(REPO_ROOT).as_posix()),
        help="Path to plugin manifest YAML.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    compiler = V5Compiler(
        manifest_path=resolve_repo_path(args.topology),
        output_json=resolve_repo_path(args.output_json),
        diagnostics_json=resolve_repo_path(args.diagnostics_json),
        diagnostics_txt=resolve_repo_path(args.diagnostics_txt),
        artifacts_root=resolve_repo_path(args.artifacts_root),
        error_catalog_path=resolve_repo_path(args.error_catalog),
        strict_model_lock=args.strict_model_lock,
        fail_on_warning=args.fail_on_warning,
        require_new_model=args.require_new_model,
        runtime_profile=args.profile,
        instance_source_mode=args.instance_source_mode,
        secrets_mode=args.secrets_mode,
        pipeline_mode=args.pipeline_mode,
        parity_gate=False,
        plugins_manifest_path=resolve_repo_path(args.plugins_manifest),
    )
    return compiler.run()


if __name__ == "__main__":
    raise SystemExit(main())

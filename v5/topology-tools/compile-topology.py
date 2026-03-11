#!/usr/bin/env python3
"""Compile v5 topology manifest + modules + instance bindings into canonical JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Add kernel to path for plugin imports
TOPOLOGY_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOPOLOGY_TOOLS))

from compiler_runtime import (
    apply_plugin_compile_outputs,
    emit_effective_artifact,
    load_core_compile_inputs,
    resolve_manifest_paths,
)
from kernel import KERNEL_VERSION, PluginContext, PluginDiagnostic, PluginRegistry, PluginResult, PluginStatus, Stage
from legacy_capabilities import default_firmware_policy as legacy_default_firmware_policy
from legacy_capabilities import derive_firmware_capabilities as legacy_derive_firmware_capabilities
from legacy_capabilities import derive_os_capabilities as legacy_derive_os_capabilities
from legacy_capabilities import extract_architecture as legacy_extract_architecture
from legacy_capabilities import extract_firmware_properties as legacy_extract_firmware_properties
from legacy_capabilities import extract_os_installation_model as legacy_extract_os_installation_model
from legacy_capabilities import extract_os_properties as legacy_extract_os_properties
from legacy_capabilities import normalize_release_token as legacy_normalize_release_token
from legacy_effective import build_effective, compute_object_capability_projections, compute_reference_projections
from legacy_loaders import load_capability_contract, load_instance_rows, load_module_map
from legacy_validators import validate_capability_contract, validate_embedded_in, validate_model_lock, validate_refs

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "v5" / "topology" / "topology.yaml"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "v5-build" / "effective-topology.json"
DEFAULT_DIAGNOSTICS_JSON = REPO_ROOT / "v5-build" / "diagnostics" / "report.json"
DEFAULT_DIAGNOSTICS_TXT = REPO_ROOT / "v5-build" / "diagnostics" / "report.txt"
DEFAULT_ERROR_CATALOG = REPO_ROOT / "v5" / "topology-tools" / "data" / "error-catalog.yaml"
DEFAULT_PLUGINS_MANIFEST = TOPOLOGY_TOOLS / "plugins" / "plugins.yaml"

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
SUPPORTED_RUNTIME_PROFILES = ("production", "modeled", "test-real")
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
        error_catalog_path: Path,
        strict_model_lock: bool,
        fail_on_warning: bool,
        require_new_model: bool,
        runtime_profile: str = "production",
        pipeline_mode: str = "legacy",
        parity_gate: bool = False,
        enable_plugins: bool = False,
        plugins_manifest_path: Path | None = None,
    ) -> None:
        self.manifest_path = manifest_path
        self.output_json = output_json
        self.diagnostics_json = diagnostics_json
        self.diagnostics_txt = diagnostics_txt
        self.error_catalog_path = error_catalog_path
        self.strict_model_lock = strict_model_lock
        self.fail_on_warning = fail_on_warning
        self.require_new_model = require_new_model
        self.runtime_profile = runtime_profile
        self.pipeline_mode = pipeline_mode
        self.parity_gate = parity_gate
        self.enable_plugins = enable_plugins
        self.plugins_manifest_path = plugins_manifest_path or DEFAULT_PLUGINS_MANIFEST

        self._diagnostics: list[Diagnostic] = []
        self._error_hints = self._load_error_hints(error_catalog_path)
        self._object_derived_caps: dict[str, list[str]] = {}
        self._object_effective_os: dict[str, dict[str, Any]] = {}
        self._instance_derived_caps: dict[str, list[str]] = {}
        self._instance_software_refs: dict[str, dict[str, Any]] = {}
        self._plugin_registry: PluginRegistry | None = None
        self._plugin_results: list[PluginResult] = []
        self._run_generated_at: str | None = None

        # Initialize plugin registry if enabled
        if self.enable_plugins:
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
        """Initialize the plugin registry from manifest."""
        try:
            self._plugin_registry = PluginRegistry(TOPOLOGY_TOOLS)
            if self.plugins_manifest_path.exists():
                self._plugin_registry.load_manifest(self.plugins_manifest_path)
                load_errors = self._plugin_registry.get_load_errors()
                for err in load_errors:
                    self.add_diag(
                        code="E4001",
                        severity="error",
                        stage="load",
                        message=f"Plugin load error: {err}",
                        path="plugins.yaml",
                    )
                self.add_diag(
                    code="I4001",
                    severity="info",
                    stage="load",
                    message=f"Plugin kernel v{KERNEL_VERSION} initialized with {len(self._plugin_registry.specs)} plugins",
                    path="plugins.yaml",
                    confidence=1.0,
                )
            else:
                self.add_diag(
                    code="W4001",
                    severity="warning",
                    stage="load",
                    message=f"Plugin manifest not found: {self.plugins_manifest_path}",
                    path="plugins.yaml",
                )
        except Exception as exc:
            self.add_diag(
                code="E4001",
                severity="error",
                stage="load",
                message=f"Plugin registry initialization failed: {exc}",
                path="plugins.yaml",
            )
            self._plugin_registry = None

    def _create_plugin_context(
        self,
        *,
        manifest: dict[str, Any],
        class_modules_root: Path,
        object_modules_root: Path,
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        instance_bindings: dict[str, Any],
        rows: list[dict[str, Any]],
        capability_catalog_ids: set[str],
        capability_packs: dict[str, dict[str, Any]],
        capability_catalog_path: Path,
        capability_packs_path: Path,
        model_lock_path: Path,
        lock_payload: dict[str, Any] | None,
        source_manifest_digest: str,
    ) -> PluginContext:
        """Create a plugin context that persists across stages."""
        embedded_in_owner = self._validation_owner("embedded_in")
        model_lock_owner = self._validation_owner("model_lock")
        references_owner = self._validation_owner("references")
        capability_contract_owner = self._validation_owner("capability_contract")
        instance_rows_owner = self._compilation_owner("instance_rows")
        capability_contract_data_owner = self._compilation_owner("capability_contract_data")
        effective_json_owner = self._artifact_owner("effective_json")
        class_module_paths = {
            class_id: str(item.get("path", "").relative_to(REPO_ROOT).as_posix())
            for class_id, item in class_map.items()
            if isinstance(item, dict) and isinstance(item.get("path"), Path)
        }
        object_module_paths = {
            object_id: str(item.get("path", "").relative_to(REPO_ROOT).as_posix())
            for object_id, item in object_map.items()
            if isinstance(item, dict) and isinstance(item.get("path"), Path)
        }
        return PluginContext(
            topology_path=str(self.manifest_path.relative_to(REPO_ROOT).as_posix()),
            profile=self.runtime_profile,
            model_lock=lock_payload or {},
            raw_yaml=manifest,
            classes={class_id: item["payload"] for class_id, item in class_map.items()},
            objects={object_id: item["payload"] for object_id, item in object_map.items()},
            instance_bindings=instance_bindings,
            config={
                "strict_mode": self.strict_model_lock,
                "pipeline_mode": self.pipeline_mode,
                "parity_gate": self.parity_gate,
                "compile_generated_at": self._run_generated_at or utc_now(),
                "compiled_model_version": COMPILED_MODEL_VERSION,
                "compiler_pipeline_version": COMPILER_PIPELINE_VERSION,
                "source_manifest_digest": source_manifest_digest,
                "runtime_profile": self.runtime_profile,
                "validation_owner_embedded_in": embedded_in_owner,
                "validation_owner_model_lock": model_lock_owner,
                "validation_owner_references": references_owner,
                "validation_owner_capability_contract": capability_contract_owner,
                "compilation_owner_instance_rows": instance_rows_owner,
                "compilation_owner_capability_contract_data": capability_contract_data_owner,
                "model_lock_loaded": lock_payload is not None,
                "generation_owner_effective_json": effective_json_owner,
                "compilation_owner_module_maps": self._compilation_owner("module_maps"),
                "compilation_owner_model_lock_data": self._compilation_owner("model_lock_data"),
                "normalized_rows": rows,
                "capability_catalog_ids": sorted(capability_catalog_ids),
                "capability_packs": capability_packs,
                "capability_catalog_path": str(capability_catalog_path),
                "capability_packs_path": str(capability_packs_path),
                "model_lock_path": str(model_lock_path),
                "class_modules_root": str(class_modules_root),
                "object_modules_root": str(object_modules_root),
                "class_module_paths": class_module_paths,
                "object_module_paths": object_module_paths,
                "require_new_model": self.require_new_model,
            },
            output_dir=str(self.output_json.parent),
            source_file=str(self.manifest_path),
            compiled_file=str(self.output_json),
        )

    def _validation_owner(self, rule_name: str) -> str:
        """Return validation ownership for a domain rule during migration.

        Ownership model:
        - `core`: legacy built-in validator remains source of truth
        - `plugin`: rule validated by plugin implementation
        """
        if not self.enable_plugins:
            return "core"
        if rule_name == "embedded_in" and self.pipeline_mode == "plugin-first":
            return "plugin"
        if rule_name == "model_lock" and self.pipeline_mode == "plugin-first":
            return "plugin"
        if rule_name == "references" and self.pipeline_mode == "plugin-first":
            return "plugin"
        if rule_name == "capability_contract" and self.pipeline_mode == "plugin-first":
            return "plugin"
        return "core"

    def _compilation_owner(self, rule_name: str) -> str:
        """Return compile-stage ownership for migration cutover."""
        if not self.enable_plugins:
            return "core"
        if rule_name == "module_maps" and self.pipeline_mode == "plugin-first":
            return "plugin"
        if rule_name == "model_lock_data" and self.pipeline_mode == "plugin-first":
            return "plugin"
        if rule_name == "instance_rows" and self.pipeline_mode == "plugin-first":
            return "plugin"
        if rule_name == "capability_contract_data" and self.pipeline_mode == "plugin-first":
            return "plugin"
        return "core"

    def _artifact_owner(self, artifact_name: str) -> str:
        """Return artifact emission ownership for migration cutover."""
        if not self.enable_plugins:
            return "core"
        if artifact_name == "effective_json" and self.pipeline_mode == "plugin-first":
            return "plugin"
        return "core"

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
        results = self._plugin_registry.execute_stage(stage, ctx, profile=self.runtime_profile)
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

    @staticmethod
    def _canonicalize_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)

    def _manifest_digest(self, manifest: dict[str, Any]) -> str:
        canonical = self._canonicalize_payload(manifest)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _validate_compiled_model_contract(self, payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            self.add_diag(
                code="E6903",
                severity="error",
                stage="validate",
                message="compiled_json payload must be an object.",
                path="compiled_json",
            )
            return False

        required_string_keys = (
            "compiled_model_version",
            "compiled_at",
            "compiler_pipeline_version",
            "source_manifest_digest",
        )
        has_errors = False
        for key in required_string_keys:
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                has_errors = True
                self.add_diag(
                    code="E6903",
                    severity="error",
                    stage="validate",
                    message=f"compiled model contract requires non-empty string key '{key}'.",
                    path=f"compiled_json.{key}",
                )

        version = payload.get("compiled_model_version")
        if isinstance(version, str) and version:
            major = version.split(".", 1)[0]
            if major not in SUPPORTED_COMPILED_MODEL_MAJOR:
                has_errors = True
                self.add_diag(
                    code="E6903",
                    severity="error",
                    stage="validate",
                    message=(
                        f"incompatible compiled_model_version '{version}'; "
                        f"supported majors: {sorted(SUPPORTED_COMPILED_MODEL_MAJOR)}."
                    ),
                    path="compiled_json.compiled_model_version",
                )

        return not has_errors

    def _select_effective_payload(
        self,
        *,
        legacy_payload: dict[str, Any],
        plugin_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        mode = self.pipeline_mode

        if self.parity_gate and not self.enable_plugins:
            self.add_diag(
                code="E6902",
                severity="error",
                stage="validate",
                message="--parity-gate requires --enable-plugins to compare legacy and plugin outputs.",
                path="pipeline:parity",
            )

        if mode == "legacy":
            if plugin_payload is not None:
                legacy_digest = self._canonicalize_payload(legacy_payload)
                plugin_digest = self._canonicalize_payload(plugin_payload)
                if legacy_digest != plugin_digest:
                    if self.parity_gate:
                        self.add_diag(
                            code="E6902",
                            severity="error",
                            stage="validate",
                            message="Parity gate failed: plugin effective model differs from legacy model.",
                            path="pipeline:parity",
                        )
                    else:
                        self.add_diag(
                            code="W6901",
                            severity="warning",
                            stage="validate",
                            message="Plugin effective model differs from legacy effective model (parity drift).",
                            path="pipeline:mode",
                        )
            return legacy_payload

        # plugin-first mode
        if not self.enable_plugins:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="pipeline_mode=plugin-first requires --enable-plugins.",
                path="pipeline:mode",
            )
            return legacy_payload

        if plugin_payload is None:
            self.add_diag(
                code="E6901",
                severity="error",
                stage="validate",
                message="pipeline_mode=plugin-first requires compiler plugins to publish ctx.compiled_json.",
                path="pipeline:mode",
            )
            return legacy_payload

        if self.parity_gate:
            legacy_digest = self._canonicalize_payload(legacy_payload)
            plugin_digest = self._canonicalize_payload(plugin_payload)
            if legacy_digest != plugin_digest:
                self.add_diag(
                    code="E6902",
                    severity="error",
                    stage="validate",
                    message="Parity gate failed in plugin-first mode: plugin model is not parity-equivalent to legacy.",
                    path="pipeline:parity",
                )

        self.add_diag(
            code="I6901",
            severity="info",
            stage="validate",
            message="Pipeline mode plugin-first is active; effective output source is plugin ctx.compiled_json.",
            path="pipeline:mode",
            confidence=1.0,
        )
        return plugin_payload

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

    def _load_module_map(self, *, directory: Path, module_type: str) -> dict[str, dict[str, Any]]:
        return load_module_map(
            directory=directory,
            module_type=module_type,
            load_yaml=lambda path, code_missing, code_parse, stage: self._load_yaml(
                path, code_missing=code_missing, code_parse=code_parse, stage=stage
            ),
            add_diag=self.add_diag,
            repo_root=REPO_ROOT,
        )

    def _load_capability_contract(
        self, *, catalog_path: Path, packs_path: Path
    ) -> tuple[set[str], dict[str, dict[str, Any]]]:
        return load_capability_contract(
            catalog_path=catalog_path,
            packs_path=packs_path,
            load_yaml=lambda path, code_missing, code_parse, stage: self._load_yaml(
                path, code_missing=code_missing, code_parse=code_parse, stage=stage
            ),
            add_diag=self.add_diag,
            repo_root=REPO_ROOT,
        )

    def _expand_capabilities(
        self,
        *,
        direct_caps: list[Any],
        pack_refs: list[Any],
        packs_map: dict[str, dict[str, Any]],
    ) -> set[str]:
        expanded: set[str] = set()
        for cap in direct_caps:
            if isinstance(cap, str):
                expanded.add(cap)
        for pack_ref in pack_refs:
            if not isinstance(pack_ref, str):
                continue
            pack = packs_map.get(pack_ref, {})
            for cap in pack.get("capabilities", []) or []:
                if isinstance(cap, str):
                    expanded.add(cap)
        return expanded

    @staticmethod
    def _normalize_release_token(value: str) -> str:
        return legacy_normalize_release_token(value)

    @staticmethod
    def _default_firmware_policy(class_id: str) -> str:
        return legacy_default_firmware_policy(class_id)

    @staticmethod
    def _extract_architecture(object_payload: dict[str, Any]) -> str | None:
        return legacy_extract_architecture(object_payload)

    @staticmethod
    def _extract_os_installation_model(object_payload: dict[str, Any]) -> str | None:
        return legacy_extract_os_installation_model(object_payload)

    @staticmethod
    def _extract_firmware_properties(object_payload: dict[str, Any]) -> dict[str, Any]:
        return legacy_extract_firmware_properties(object_payload)

    def _extract_os_properties(self, object_payload: dict[str, Any]) -> dict[str, Any] | None:
        _ = self
        return legacy_extract_os_properties(object_payload)

    def _derive_firmware_capabilities(
        self,
        *,
        object_id: str,
        object_payload: dict[str, Any],
        catalog_ids: set[str],
        path: str,
        emit_diagnostics: bool = True,
    ) -> tuple[set[str], dict[str, Any] | None]:
        return legacy_derive_firmware_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=path,
            add_diag=self.add_diag,
            emit_diagnostics=emit_diagnostics,
        )

    def _derive_os_capabilities(
        self,
        *,
        object_id: str,
        object_payload: dict[str, Any],
        catalog_ids: set[str],
        path: str,
        emit_diagnostics: bool = True,
    ) -> tuple[set[str], dict[str, Any] | None]:
        return legacy_derive_os_capabilities(
            object_id=object_id,
            object_payload=object_payload,
            catalog_ids=catalog_ids,
            path=path,
            add_diag=self.add_diag,
            emit_diagnostics=emit_diagnostics,
        )

    def _compute_reference_projections(
        self,
        *,
        rows: list[dict[str, Any]],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        catalog_ids: set[str],
    ) -> None:
        """Compute instance software/capability projections without diagnostics.

        Used in plugin-first mode where reference diagnostics are owned by plugin
        validator, while legacy effective payload still needs projection side effects.
        """
        _ = class_map
        self._instance_derived_caps, self._instance_software_refs = compute_reference_projections(
            rows=rows,
            object_map=object_map,
            catalog_ids=catalog_ids,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
        )

    def _compute_object_capability_projections(
        self,
        *,
        object_map: dict[str, dict[str, Any]],
        catalog_ids: set[str],
    ) -> None:
        """Compute object-level capability projections without diagnostics."""
        self._object_derived_caps, self._object_effective_os = compute_object_capability_projections(
            object_map=object_map,
            catalog_ids=catalog_ids,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
        )

    def _validate_capability_contract(
        self,
        *,
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        catalog_ids: set[str],
        packs_map: dict[str, dict[str, Any]],
    ) -> None:
        self._object_derived_caps, self._object_effective_os = validate_capability_contract(
            class_map=class_map,
            object_map=object_map,
            catalog_ids=catalog_ids,
            packs_map=packs_map,
            require_new_model=self.require_new_model,
            add_diag=self.add_diag,
            default_firmware_policy=self._default_firmware_policy,
            expand_capabilities=self._expand_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
        )

    def _load_instance_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return load_instance_rows(payload=payload, add_diag=self.add_diag)

    def _validate_refs(
        self,
        *,
        rows: list[dict[str, Any]],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        catalog_ids: set[str],
    ) -> None:
        self._instance_derived_caps, self._instance_software_refs = validate_refs(
            rows=rows,
            class_map=class_map,
            object_map=object_map,
            catalog_ids=catalog_ids,
            add_diag=self.add_diag,
            default_firmware_policy=self._default_firmware_policy,
            extract_architecture=self._extract_architecture,
            extract_os_installation_model=self._extract_os_installation_model,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
        )

    def _validate_embedded_in(
        self,
        *,
        rows: list[dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
    ) -> None:
        validate_embedded_in(
            rows=rows,
            object_map=object_map,
            add_diag=self.add_diag,
            extract_os_installation_model=self._extract_os_installation_model,
        )

    def _validate_model_lock(
        self,
        *,
        rows: list[dict[str, Any]],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        lock_payload: dict[str, Any] | None,
    ) -> None:
        validate_model_lock(
            rows=rows,
            class_map=class_map,
            object_map=object_map,
            lock_payload=lock_payload,
            strict_model_lock=self.strict_model_lock,
            add_diag=self.add_diag,
        )

    def _build_effective(
        self,
        *,
        manifest: dict[str, Any],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
        source_manifest_digest: str,
    ) -> dict[str, Any]:
        compiled_at = self._run_generated_at or utc_now()
        return build_effective(
            manifest=manifest,
            topology_manifest_path=str(self.manifest_path.relative_to(REPO_ROOT).as_posix()),
            generated_at=compiled_at,
            class_map=class_map,
            object_map=object_map,
            rows=rows,
            object_derived_caps=self._object_derived_caps,
            object_effective_os=self._object_effective_os,
            instance_derived_caps=self._instance_derived_caps,
            instance_software_refs=self._instance_software_refs,
            default_firmware_policy=self._default_firmware_policy,
            compiled_model_version=COMPILED_MODEL_VERSION,
            compiler_pipeline_version=COMPILER_PIPELINE_VERSION,
            source_manifest_digest=source_manifest_digest,
        )

    def _build_summary(self) -> tuple[dict[str, Any], int, int, int, int]:
        total = len(self._diagnostics)
        errors = sum(1 for item in self._diagnostics if item.severity == "error")
        warnings = sum(1 for item in self._diagnostics if item.severity == "warning")
        infos = sum(1 for item in self._diagnostics if item.severity == "info")
        by_stage: dict[str, int] = {}
        for item in self._diagnostics:
            by_stage[item.stage] = by_stage.get(item.stage, 0) + 1
        summary = {
            "total": total,
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "by_stage": by_stage,
        }
        return summary, total, errors, warnings, infos

    def _build_next_actions(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for diag in self._diagnostics:
            file_key = diag.path.split(":")[0]
            entry = grouped.setdefault(file_key, {"file": file_key, "errors": 0, "warnings": 0, "codes": []})
            if diag.severity == "error":
                entry["errors"] += 1
            elif diag.severity == "warning":
                entry["warnings"] += 1
            entry["codes"].append(diag.code)

        actions: list[dict[str, Any]] = []
        for _, entry in sorted(grouped.items(), key=lambda item: (-item[1]["errors"], -item[1]["warnings"], item[0])):
            primary_codes = sorted(set(entry["codes"]))[:3]
            actions.append(
                {
                    "file": entry["file"],
                    "errors": entry["errors"],
                    "warnings": entry["warnings"],
                    "primary_codes": primary_codes,
                }
            )
        return actions

    def _sort_diagnostics(self) -> None:
        self._diagnostics.sort(
            key=lambda item: (SEVERITY_ORDER.get(item.severity, 9), item.stage, item.code, item.path)
        )

    def _write_diagnostics(self) -> tuple[int, int, int, int]:
        self._sort_diagnostics()
        summary, total, errors, warnings, infos = self._build_summary()

        self.diagnostics_json.parent.mkdir(parents=True, exist_ok=True)
        self.diagnostics_txt.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "report_version": "1",
            "tool": "topology-v5-compiler",
            "generated_at": utc_now(),
            "inputs": {
                "topology": str(self.manifest_path.relative_to(REPO_ROOT).as_posix()),
                "schema": "v5/topology/topology.yaml",
                "error_catalog": str(self.error_catalog_path.relative_to(REPO_ROOT).as_posix()),
                "model_lock": "v5/topology/model.lock.yaml",
            },
            "outputs": {
                "effective_json": str(self.output_json.relative_to(REPO_ROOT).as_posix()),
                "diagnostics_json": str(self.diagnostics_json.relative_to(REPO_ROOT).as_posix()),
                "diagnostics_txt": str(self.diagnostics_txt.relative_to(REPO_ROOT).as_posix()),
            },
            "summary": summary,
            "next_actions": self._build_next_actions(),
            "diagnostics": [item.as_dict() for item in self._diagnostics],
        }
        self.diagnostics_json.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, default=str),
            encoding="utf-8",
        )

        txt_lines = [
            "Topology v5 Compiler Diagnostics",
            "================================",
            "",
            f"generated_at: {report['generated_at']}",
            f"total={total} errors={errors} warnings={warnings} infos={infos}",
            "",
        ]
        for item in self._diagnostics:
            txt_lines.append(f"[{item.severity.upper()}] {item.code} ({item.stage}) {item.path}: {item.message}")
            if item.hint:
                txt_lines.append(f"  hint: {item.hint}")
        self.diagnostics_txt.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

        return total, errors, warnings, infos

    def run(self) -> int:
        self._run_generated_at = utc_now()
        manifest = self._load_yaml(self.manifest_path, code_missing="E1001", code_parse="E1003", stage="load")
        if manifest is None:
            _, errors, warnings, infos = self._write_diagnostics()[0:4]
            print(f"Compile summary: total={len(self._diagnostics)} errors={errors} warnings={warnings} infos={infos}")
            print(f"Diagnostics JSON: {self.diagnostics_json}")
            print(f"Diagnostics TXT:  {self.diagnostics_txt}")
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
            self._write_diagnostics()
            print(
                f"Compile summary: total={len(self._diagnostics)} "
                f"errors={sum(1 for d in self._diagnostics if d.severity == 'error')} "
                f"warnings={sum(1 for d in self._diagnostics if d.severity == 'warning')} "
                f"infos={sum(1 for d in self._diagnostics if d.severity == 'info')}"
            )
            print(f"Diagnostics JSON: {self.diagnostics_json}")
            print(f"Diagnostics TXT:  {self.diagnostics_txt}")
            return 1

        manifest_bundle = resolve_manifest_paths(
            manifest_paths=manifest_paths,
            resolve_repo_path=resolve_repo_path,
        )
        source_manifest_digest = self._manifest_digest(manifest)
        inputs = load_core_compile_inputs(
            paths=manifest_bundle,
            compilation_owner=self._compilation_owner,
            load_module_map=self._load_module_map,
            load_capability_contract=self._load_capability_contract,
            load_yaml=self._load_yaml,
            load_instance_rows=self._load_instance_rows,
        )

        # Create shared plugin context (ADR 0063 Phase 3)
        # Context persists across stages so publish/subscribe works
        plugin_ctx: PluginContext | None = None
        if self.enable_plugins:
            plugin_ctx = self._create_plugin_context(
                manifest=manifest,
                class_modules_root=manifest_bundle.class_modules_root,
                object_modules_root=manifest_bundle.object_modules_root,
                class_map=inputs.class_map,
                object_map=inputs.object_map,
                instance_bindings=inputs.instance_payload or {},
                rows=inputs.rows,
                capability_catalog_ids=inputs.catalog_ids,
                capability_packs=inputs.packs_map,
                capability_catalog_path=manifest_bundle.capability_catalog_path,
                capability_packs_path=manifest_bundle.capability_packs_path,
                model_lock_path=manifest_bundle.model_lock_path,
                lock_payload=inputs.lock_payload,
                source_manifest_digest=source_manifest_digest,
            )
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
        legacy_effective_needed = self.pipeline_mode == "legacy" or self.parity_gate

        if self._validation_owner("references") == "core":
            self._validate_refs(
                rows=inputs.rows,
                class_map=inputs.class_map,
                object_map=inputs.object_map,
                catalog_ids=inputs.catalog_ids,
            )
        elif legacy_effective_needed:
            self._compute_reference_projections(
                rows=inputs.rows,
                class_map=inputs.class_map,
                object_map=inputs.object_map,
                catalog_ids=inputs.catalog_ids,
            )
        if self._validation_owner("embedded_in") == "core":
            self._validate_embedded_in(rows=inputs.rows, object_map=inputs.object_map)
        if inputs.catalog_ids:
            if self._validation_owner("capability_contract") == "core":
                self._validate_capability_contract(
                    class_map=inputs.class_map,
                    object_map=inputs.object_map,
                    catalog_ids=inputs.catalog_ids,
                    packs_map=inputs.packs_map,
                )
            elif legacy_effective_needed:
                self._compute_object_capability_projections(
                    object_map=inputs.object_map,
                    catalog_ids=inputs.catalog_ids,
                )
        if self._validation_owner("model_lock") == "core":
            self._validate_model_lock(
                rows=inputs.rows,
                class_map=inputs.class_map,
                object_map=inputs.object_map,
                lock_payload=inputs.lock_payload,
            )

        # Build effective payload before validator/generator stages so plugins
        # share one compiled model contract (ADR 0069 WS1).
        legacy_effective_payload: dict[str, Any] = {}
        if legacy_effective_needed:
            legacy_effective_payload = self._build_effective(
                manifest=manifest,
                class_map=inputs.class_map,
                object_map=inputs.object_map,
                rows=inputs.rows,
                source_manifest_digest=source_manifest_digest,
            )
        effective_payload = self._select_effective_payload(
            legacy_payload=legacy_effective_payload,
            plugin_payload=plugin_effective_payload,
        )
        if plugin_ctx:
            plugin_ctx.compiled_json = effective_payload
        compiled_contract_ok = self._validate_compiled_model_contract(effective_payload)

        # Execute validator plugins (ADR 0063)
        # Uses same context so validators can subscribe to compiler outputs
        if compiled_contract_ok and self.enable_plugins and plugin_ctx:
            self._execute_plugins(stage=Stage.VALIDATE, ctx=plugin_ctx)

        errors = sum(1 for item in self._diagnostics if item.severity == "error")
        emit_effective_artifact(
            errors=errors,
            compiled_contract_ok=compiled_contract_ok,
            enable_plugins=self.enable_plugins,
            plugin_ctx=plugin_ctx,
            execute_plugins=lambda *, stage, ctx: self._execute_plugins(stage=Stage(stage), ctx=ctx),
            artifact_owner=self._artifact_owner,
            output_json=self.output_json,
            effective_payload=effective_payload,
            add_diag=self.add_diag,
            repo_root=REPO_ROOT,
        )

        total, errors, warnings, infos = self._write_diagnostics()
        print(f"Compile summary: total={total} errors={errors} warnings={warnings} infos={infos}")
        print(f"Diagnostics JSON: {self.diagnostics_json}")
        print(f"Diagnostics TXT:  {self.diagnostics_txt}")
        if errors == 0:
            print(f"Effective JSON:   {self.output_json}")

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
        "--pipeline-mode",
        choices=["legacy", "plugin-first"],
        default="legacy",
        help="Pipeline source mode for effective model selection.",
    )
    parser.add_argument(
        "--parity-gate",
        action="store_true",
        help="Fail compilation when plugin and legacy effective models are not parity-equivalent.",
    )
    parser.add_argument(
        "--enable-plugins",
        action="store_true",
        help="Enable plugin execution (ADR 0063). Runs validator plugins after built-in validation.",
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
        error_catalog_path=resolve_repo_path(args.error_catalog),
        strict_model_lock=args.strict_model_lock,
        fail_on_warning=args.fail_on_warning,
        require_new_model=args.require_new_model,
        runtime_profile=args.profile,
        pipeline_mode=args.pipeline_mode,
        parity_gate=args.parity_gate,
        enable_plugins=args.enable_plugins,
        plugins_manifest_path=resolve_repo_path(args.plugins_manifest),
    )
    return compiler.run()


if __name__ == "__main__":
    raise SystemExit(main())

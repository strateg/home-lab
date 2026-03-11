"""Legacy-domain bridge used by compile-topology orchestrator during cutover."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from legacy_capabilities import default_firmware_policy as legacy_default_firmware_policy
from legacy_capabilities import derive_firmware_capabilities as legacy_derive_firmware_capabilities
from legacy_capabilities import derive_os_capabilities as legacy_derive_os_capabilities
from legacy_capabilities import extract_architecture as legacy_extract_architecture
from legacy_capabilities import extract_os_installation_model as legacy_extract_os_installation_model
from legacy_effective import build_effective, compute_object_capability_projections, compute_reference_projections
from legacy_loaders import load_capability_contract, load_instance_rows, load_module_map
from legacy_validators import validate_capability_contract, validate_embedded_in, validate_model_lock, validate_refs


class LegacyDomainBridge:
    """Encapsulates legacy loaders/validators/effective-builder state."""

    def __init__(
        self,
        *,
        add_diag: Callable[..., None],
        load_yaml: Callable[..., dict[str, Any] | None],
        repo_root: Path,
        manifest_path: Path,
        require_new_model: bool,
        strict_model_lock: bool,
        compiled_model_version: str,
        compiler_pipeline_version: str,
    ) -> None:
        self._add_diag = add_diag
        self._load_yaml = load_yaml
        self._repo_root = repo_root
        self._manifest_path = manifest_path
        self._require_new_model = require_new_model
        self._strict_model_lock = strict_model_lock
        self._compiled_model_version = compiled_model_version
        self._compiler_pipeline_version = compiler_pipeline_version
        self._object_derived_caps: dict[str, list[str]] = {}
        self._object_effective_os: dict[str, dict[str, Any]] = {}
        self._instance_derived_caps: dict[str, list[str]] = {}
        self._instance_software_refs: dict[str, dict[str, Any]] = {}

    def reset_state(self) -> None:
        self._object_derived_caps = {}
        self._object_effective_os = {}
        self._instance_derived_caps = {}
        self._instance_software_refs = {}

    def load_module_map(self, *, directory: Path, module_type: str) -> dict[str, dict[str, Any]]:
        return load_module_map(
            directory=directory,
            module_type=module_type,
            load_yaml=lambda path, code_missing, code_parse, stage: self._load_yaml(
                path, code_missing=code_missing, code_parse=code_parse, stage=stage
            ),
            add_diag=self._add_diag,
            repo_root=self._repo_root,
        )

    def load_capability_contract(
        self, *, catalog_path: Path, packs_path: Path
    ) -> tuple[set[str], dict[str, dict[str, Any]]]:
        return load_capability_contract(
            catalog_path=catalog_path,
            packs_path=packs_path,
            load_yaml=lambda path, code_missing, code_parse, stage: self._load_yaml(
                path, code_missing=code_missing, code_parse=code_parse, stage=stage
            ),
            add_diag=self._add_diag,
            repo_root=self._repo_root,
        )

    def load_instance_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return load_instance_rows(payload=payload, add_diag=self._add_diag)

    @staticmethod
    def _expand_capabilities(
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
            add_diag=self._add_diag,
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
            add_diag=self._add_diag,
            emit_diagnostics=emit_diagnostics,
        )

    def validate_refs(
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
            add_diag=self._add_diag,
            default_firmware_policy=legacy_default_firmware_policy,
            extract_architecture=legacy_extract_architecture,
            extract_os_installation_model=legacy_extract_os_installation_model,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
        )

    def compute_reference_projections(
        self,
        *,
        rows: list[dict[str, Any]],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        catalog_ids: set[str],
    ) -> None:
        _ = class_map
        self._instance_derived_caps, self._instance_software_refs = compute_reference_projections(
            rows=rows,
            object_map=object_map,
            catalog_ids=catalog_ids,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
        )

    def validate_embedded_in(
        self,
        *,
        rows: list[dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
    ) -> None:
        validate_embedded_in(
            rows=rows,
            object_map=object_map,
            add_diag=self._add_diag,
            extract_os_installation_model=legacy_extract_os_installation_model,
        )

    def validate_capability_contract(
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
            require_new_model=self._require_new_model,
            add_diag=self._add_diag,
            default_firmware_policy=legacy_default_firmware_policy,
            expand_capabilities=self._expand_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
        )

    def compute_object_capability_projections(
        self,
        *,
        object_map: dict[str, dict[str, Any]],
        catalog_ids: set[str],
    ) -> None:
        self._object_derived_caps, self._object_effective_os = compute_object_capability_projections(
            object_map=object_map,
            catalog_ids=catalog_ids,
            derive_firmware_capabilities=self._derive_firmware_capabilities,
            derive_os_capabilities=self._derive_os_capabilities,
        )

    def validate_model_lock(
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
            strict_model_lock=self._strict_model_lock,
            add_diag=self._add_diag,
        )

    def build_effective(
        self,
        *,
        manifest: dict[str, Any],
        generated_at: str,
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
        source_manifest_digest: str,
    ) -> dict[str, Any]:
        return build_effective(
            manifest=manifest,
            topology_manifest_path=str(self._manifest_path.relative_to(self._repo_root).as_posix()),
            generated_at=generated_at,
            class_map=class_map,
            object_map=object_map,
            rows=rows,
            object_derived_caps=self._object_derived_caps,
            object_effective_os=self._object_effective_os,
            instance_derived_caps=self._instance_derived_caps,
            instance_software_refs=self._instance_software_refs,
            default_firmware_policy=legacy_default_firmware_policy,
            compiled_model_version=self._compiled_model_version,
            compiler_pipeline_version=self._compiler_pipeline_version,
            source_manifest_digest=source_manifest_digest,
        )

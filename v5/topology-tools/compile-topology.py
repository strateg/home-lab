#!/usr/bin/env python3
"""Compile v5 topology manifest + modules + instance bindings into canonical JSON."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "v5" / "topology" / "topology.yaml"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "v5-build" / "effective-topology.json"
DEFAULT_DIAGNOSTICS_JSON = REPO_ROOT / "v5-build" / "diagnostics" / "report.json"
DEFAULT_DIAGNOSTICS_TXT = REPO_ROOT / "v5-build" / "diagnostics" / "report.txt"
DEFAULT_ERROR_CATALOG = REPO_ROOT / "v4" / "topology-tools" / "data" / "error-catalog.yaml"

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


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
        return payload


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
    ) -> None:
        self.manifest_path = manifest_path
        self.output_json = output_json
        self.diagnostics_json = diagnostics_json
        self.diagnostics_txt = diagnostics_txt
        self.error_catalog_path = error_catalog_path
        self.strict_model_lock = strict_model_lock
        self.fail_on_warning = fail_on_warning

        self._diagnostics: list[Diagnostic] = []
        self._error_hints = self._load_error_hints(error_catalog_path)

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

    def _load_yaml(self, path: Path, *, code_missing: str, code_parse: str, stage: str) -> dict[str, Any] | None:
        if not path.exists():
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
        except yaml.YAMLError as exc:
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

    @staticmethod
    def _iter_yaml_files(directory: Path) -> Iterable[Path]:
        if not directory.exists():
            return []
        return sorted(path for path in directory.rglob("*.yaml") if path.is_file())

    def _load_module_map(self, *, directory: Path, module_type: str) -> dict[str, dict[str, Any]]:
        module_map: dict[str, dict[str, Any]] = {}
        files = list(self._iter_yaml_files(directory))
        if not files:
            self.add_diag(
                code="E1001",
                severity="error",
                stage="load",
                message=f"No {module_type} YAML files found under {directory}",
                path=str(directory.relative_to(REPO_ROOT).as_posix()),
            )
            return module_map

        for path in files:
            payload = self._load_yaml(path, code_missing="E1001", code_parse="E1003", stage="load")
            if payload is None:
                continue
            item_id = payload.get("id")
            if not isinstance(item_id, str) or not item_id:
                self.add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"{module_type} module is missing 'id'.",
                    path=str(path.relative_to(REPO_ROOT).as_posix()),
                )
                continue
            if item_id in module_map:
                self.add_diag(
                    code="E2102",
                    severity="error",
                    stage="resolve",
                    message=f"Duplicate {module_type} id '{item_id}'.",
                    path=str(path.relative_to(REPO_ROOT).as_posix()),
                )
                continue
            module_map[item_id] = {"payload": payload, "path": path}
        return module_map

    def _load_instance_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        bindings = payload.get("instance_bindings")
        if not isinstance(bindings, dict):
            self.add_diag(
                code="E3201",
                severity="error",
                stage="validate",
                message="instance-bindings root must contain mapping 'instance_bindings'.",
                path="instance_bindings",
            )
            return []

        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for group_name, group_rows in bindings.items():
            if not isinstance(group_rows, list):
                self.add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message=f"instance_bindings.{group_name} must be a list.",
                    path=f"instance_bindings.{group_name}",
                )
                continue

            for idx, row in enumerate(group_rows):
                if not isinstance(row, dict):
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="Instance row must be an object.",
                        path=f"instance_bindings.{group_name}[{idx}]",
                    )
                    continue
                instance_id = row.get("id")
                layer = row.get("layer")
                class_ref = row.get("class_ref")
                object_ref = row.get("object_ref")

                if not isinstance(instance_id, str) or not instance_id:
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="Instance row must define non-empty 'id'.",
                        path=f"instance_bindings.{group_name}[{idx}].id",
                    )
                    continue
                if instance_id in seen_ids:
                    self.add_diag(
                        code="E2102",
                        severity="error",
                        stage="resolve",
                        message=f"Duplicate instance id '{instance_id}'.",
                        path=f"instance_bindings.{group_name}[{idx}]",
                    )
                    continue
                seen_ids.add(instance_id)

                if not isinstance(class_ref, str) or not class_ref:
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="Instance row must define non-empty 'class_ref'.",
                        path=f"instance_bindings.{group_name}[{idx}].class_ref",
                    )
                if not isinstance(object_ref, str) or not object_ref:
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="Instance row must define non-empty 'object_ref'.",
                        path=f"instance_bindings.{group_name}[{idx}].object_ref",
                    )
                if not isinstance(layer, str) or not layer:
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message="Instance row must define non-empty 'layer'.",
                        path=f"instance_bindings.{group_name}[{idx}].layer",
                    )

                rows.append(
                    {
                        "group": group_name,
                        "id": instance_id,
                        "layer": layer,
                        "source_id": row.get("source_id", instance_id),
                        "class_ref": class_ref,
                        "object_ref": object_ref,
                        "status": row.get("status", "pending"),
                        "notes": row.get("notes", ""),
                        "runtime": row.get("runtime"),
                    }
                )
        return rows

    def _validate_refs(
        self,
        *,
        rows: list[dict[str, Any]],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
    ) -> None:
        for row in rows:
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            path = f"instance:{row.get('group')}:{row.get('id')}"

            if not isinstance(class_ref, str) or not class_ref:
                continue
            if not isinstance(object_ref, str) or not object_ref:
                continue

            class_item = class_map.get(class_ref)
            object_item = object_map.get(object_ref)

            if class_item is None:
                self.add_diag(
                    code="E2101",
                    severity="error",
                    stage="resolve",
                    message=f"Instance references unknown class_ref '{class_ref}'.",
                    path=path,
                )
                continue
            if object_item is None:
                self.add_diag(
                    code="E2101",
                    severity="error",
                    stage="resolve",
                    message=f"Instance references unknown object_ref '{object_ref}'.",
                    path=path,
                )
                continue

            object_class_ref = object_item["payload"].get("class_ref")
            if object_class_ref != class_ref:
                self.add_diag(
                    code="E2403",
                    severity="error",
                    stage="validate",
                    message=(
                        f"object_ref '{object_ref}' requires class_ref '{object_class_ref}', " f"got '{class_ref}'."
                    ),
                    path=path,
                )

    def _validate_model_lock(
        self,
        *,
        rows: list[dict[str, Any]],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        lock_payload: dict[str, Any] | None,
    ) -> None:
        if lock_payload is None:
            if self.strict_model_lock:
                self.add_diag(
                    code="E3201",
                    severity="error",
                    stage="validate",
                    message="model.lock is required in strict mode.",
                    path="model.lock",
                )
            else:
                self.add_diag(
                    code="W2401",
                    severity="warning",
                    stage="load",
                    message="model.lock is missing; pinning checks skipped.",
                    path="model.lock",
                )
            return

        self.add_diag(
            code="I2401",
            severity="info",
            stage="load",
            message="model.lock loaded.",
            path="model.lock",
            confidence=1.0,
        )

        lock_classes = lock_payload.get("classes")
        lock_objects = lock_payload.get("objects")
        if not isinstance(lock_classes, dict) or not isinstance(lock_objects, dict):
            self.add_diag(
                code="E2402",
                severity="error",
                stage="load",
                message="model.lock must define mapping keys: classes and objects.",
                path="model.lock",
            )
            return

        for row in rows:
            class_ref = row.get("class_ref")
            object_ref = row.get("object_ref")
            path = f"instance:{row.get('group')}:{row.get('id')}"

            if not isinstance(class_ref, str) or not class_ref:
                continue
            if not isinstance(object_ref, str) or not object_ref:
                continue

            class_pin = lock_classes.get(class_ref)
            object_pin = lock_objects.get(object_ref)

            if class_pin is None:
                if self.strict_model_lock:
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                        path=path,
                    )
                else:
                    self.add_diag(
                        code="W2402",
                        severity="warning",
                        stage="validate",
                        message=f"class_ref '{class_ref}' is not pinned in model.lock.",
                        path=path,
                    )

            if object_pin is None:
                if self.strict_model_lock:
                    self.add_diag(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                        path=path,
                    )
                else:
                    self.add_diag(
                        code="W2403",
                        severity="warning",
                        stage="validate",
                        message=f"object_ref '{object_ref}' is not pinned in model.lock.",
                        path=path,
                    )

            if isinstance(object_pin, dict):
                pinned_class_ref = object_pin.get("class_ref")
                if isinstance(pinned_class_ref, str) and pinned_class_ref and pinned_class_ref != class_ref:
                    self.add_diag(
                        code="E2403",
                        severity="error",
                        stage="validate",
                        message=(
                            f"object_ref '{object_ref}' requires class_ref '{pinned_class_ref}' "
                            f"per model.lock, got '{class_ref}'."
                        ),
                        path=path,
                    )

            class_module_version = class_map.get(class_ref, {}).get("payload", {}).get("version")
            if isinstance(class_pin, dict):
                class_pin_version = class_pin.get("version")
                if (
                    isinstance(class_module_version, str)
                    and isinstance(class_pin_version, str)
                    and class_module_version != class_pin_version
                ):
                    self.add_diag(
                        code="W3201",
                        severity="warning",
                        stage="validate",
                        message=(
                            f"class_ref '{class_ref}' version mismatch: "
                            f"module='{class_module_version}' lock='{class_pin_version}'."
                        ),
                        path=path,
                    )

            object_module_version = object_map.get(object_ref, {}).get("payload", {}).get("version")
            if isinstance(object_pin, dict):
                object_pin_version = object_pin.get("version")
                if (
                    isinstance(object_module_version, str)
                    and isinstance(object_pin_version, str)
                    and object_module_version != object_pin_version
                ):
                    self.add_diag(
                        code="W3201",
                        severity="warning",
                        stage="validate",
                        message=(
                            f"object_ref '{object_ref}' version mismatch: "
                            f"module='{object_module_version}' lock='{object_pin_version}'."
                        ),
                        path=path,
                    )

    def _build_effective(
        self,
        *,
        manifest: dict[str, Any],
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        by_group: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            group = row["group"]
            class_ref = row["class_ref"]
            object_ref = row["object_ref"]
            class_payload = class_map.get(class_ref, {}).get("payload", {})
            object_payload = object_map.get(object_ref, {}).get("payload", {})

            effective_item = {
                "id": row["id"],
                "source_id": row.get("source_id", row["id"]),
                "layer": row.get("layer"),
                "class_ref": class_ref,
                "object_ref": object_ref,
                "status": row.get("status"),
                "notes": row.get("notes"),
                "runtime": row.get("runtime"),
                "class": {
                    "version": class_payload.get("version"),
                    "required_capabilities": class_payload.get("required_capabilities", []),
                    "optional_capabilities": class_payload.get("optional_capabilities", []),
                    "capability_packs": class_payload.get("capability_packs", []),
                },
                "object": {
                    "version": object_payload.get("version"),
                    "enabled_capabilities": object_payload.get("enabled_capabilities", []),
                    "enabled_packs": object_payload.get("enabled_packs", []),
                    "vendor": object_payload.get("vendor"),
                    "model": object_payload.get("model"),
                },
            }
            by_group.setdefault(group, []).append(effective_item)

        for group_rows in by_group.values():
            group_rows.sort(key=lambda item: str(item.get("id", "")))

        class_index = {
            class_id: class_item["payload"]
            for class_id, class_item in sorted(class_map.items(), key=lambda item: item[0])
        }
        object_index = {
            object_id: object_item["payload"]
            for object_id, object_item in sorted(object_map.items(), key=lambda item: item[0])
        }

        return {
            "version": manifest.get("version", "5.0.0"),
            "model": manifest.get("model", "class-object-instance"),
            "generated_at": utc_now(),
            "topology_manifest": str(self.manifest_path.relative_to(REPO_ROOT).as_posix()),
            "classes": class_index,
            "objects": object_index,
            "instances": by_group,
        }

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
        self.diagnostics_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

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

        class_modules_root = resolve_repo_path(str(manifest_paths.get("class_modules_root", "")))
        object_modules_root = resolve_repo_path(str(manifest_paths.get("object_modules_root", "")))
        instance_bindings_path = resolve_repo_path(str(manifest_paths.get("instance_bindings", "")))
        model_lock_path = resolve_repo_path(str(manifest_paths.get("model_lock", "")))

        class_map = self._load_module_map(directory=class_modules_root, module_type="class")
        object_map = self._load_module_map(directory=object_modules_root, module_type="object")

        instance_payload = self._load_yaml(
            instance_bindings_path,
            code_missing="E1001",
            code_parse="E1003",
            stage="load",
        )
        rows = self._load_instance_rows(instance_payload or {})

        lock_payload = None
        if model_lock_path.exists():
            lock_payload = self._load_yaml(model_lock_path, code_missing="E1001", code_parse="E2401", stage="load")

        self._validate_refs(rows=rows, class_map=class_map, object_map=object_map)
        self._validate_model_lock(rows=rows, class_map=class_map, object_map=object_map, lock_payload=lock_payload)

        errors = sum(1 for item in self._diagnostics if item.severity == "error")
        if errors == 0:
            effective_payload = self._build_effective(
                manifest=manifest,
                class_map=class_map,
                object_map=object_map,
                rows=rows,
            )
            self.output_json.parent.mkdir(parents=True, exist_ok=True)
            self.output_json.write_text(json.dumps(effective_payload, ensure_ascii=True, indent=2), encoding="utf-8")
            self.add_diag(
                code="I9001",
                severity="info",
                stage="emit",
                message="Compile success.",
                path=str(self.output_json.relative_to(REPO_ROOT).as_posix()),
                confidence=1.0,
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
    )
    return compiler.run()


if __name__ == "__main__":
    raise SystemExit(main())

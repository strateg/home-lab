"""Instance rows normalization compiler plugin (ADR 0069 WS2/WS3)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage


class InstanceRowsCompiler(CompilerPlugin):
    """Normalize instance_bindings rows and emit row-shape diagnostics."""

    _RESERVED_ROW_KEYS = {
        "instance",
        "group",
        "layer",
        "source_id",
        "class_ref",
        "object_ref",
        "status",
        "notes",
        "runtime",
        "firmware_ref",
        "os_refs",
        "embedded_in",
        "sops",
        "_source_file",
        "hardware_identity_secret_ref",
    }

    _TODO_MARKER_RE = re.compile(r"^<TODO_[A-Z0-9_]+>$")

    @classmethod
    def _extract_extensions(cls, row: dict[str, Any]) -> dict[str, Any]:
        extensions: dict[str, Any] = {}
        for key in sorted(row.keys()):
            if key in cls._RESERVED_ROW_KEYS:
                continue
            extensions[key] = row[key]
        return extensions

    @staticmethod
    def _resolve_secrets_mode(ctx: PluginContext) -> str:
        mode = ctx.config.get("secrets_mode", "passthrough")
        if not isinstance(mode, str):
            return "passthrough"
        normalized = mode.strip().lower()
        if normalized in {"inject", "passthrough", "strict"}:
            return normalized
        return "passthrough"

    def _collect_unresolved_hardware_identity_paths(self, row: dict[str, Any]) -> list[str]:
        hardware_identity = row.get("hardware_identity")
        if not isinstance(hardware_identity, dict):
            return []

        unresolved: list[str] = []

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    child_path = f"{path}.{key}" if path else str(key)
                    walk(value, child_path)
                return
            if isinstance(node, list):
                for idx, value in enumerate(node):
                    child_path = f"{path}[{idx}]"
                    walk(value, child_path)
                return
            if not isinstance(node, str):
                return
            if self._TODO_MARKER_RE.fullmatch(node):
                unresolved.append(path)

        walk(hardware_identity, "hardware_identity")
        return unresolved

    def _decrypt_row_from_source(
        self,
        *,
        source_path: Path,
        instance_id: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        path_hint: str,
    ) -> dict[str, Any] | None:
        if not source_path.exists() or not source_path.is_file():
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7202",
                    severity="error",
                    stage=stage,
                    message=f"Instance source file not found for secret decryption: {source_path}",
                    path=path_hint,
                )
            )
            return None

        command = ["sops", "-d", str(source_path)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7200",
                    severity="error",
                    stage=stage,
                    message=f"Failed to execute sops while decrypting in-place fields for '{instance_id}': {exc}",
                    path=path_hint,
                )
            )
            return None

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7201",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Failed to decrypt in-place fields for instance '{instance_id}'. "
                        f"sops exit={result.returncode}. {stderr}"
                    ),
                    path=path_hint,
                )
            )
            return None

        try:
            payload = yaml.safe_load(result.stdout) or {}
        except yaml.YAMLError as exc:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7203",
                    severity="error",
                    stage=stage,
                    message=f"Decrypted instance YAML parse failed for '{instance_id}': {exc}",
                    path=path_hint,
                )
            )
            return None

        if not isinstance(payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7203",
                    severity="error",
                    stage=stage,
                    message=f"Decrypted instance payload must be object/mapping for '{instance_id}'.",
                    path=path_hint,
                )
            )
            return None

        return payload

    def _resolve_inplace_secrets(
        self,
        *,
        row: dict[str, Any],
        instance_id: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
    ) -> dict[str, Any]:
        if mode == "passthrough":
            return row

        has_sops_metadata = isinstance(row.get("sops"), dict)
        if not has_sops_metadata:
            return row

        source_file = row.get("_source_file")
        if not isinstance(source_file, str) or not source_file:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7207",
                    severity="error",
                    stage=stage,
                    message=(
                        f"Cannot decrypt in-place fields for instance '{instance_id}': "
                        "source file path is missing."
                    ),
                    path=row_path,
                )
            )
            return row

        decrypted_payload = self._decrypt_row_from_source(
            source_path=Path(source_file),
            instance_id=instance_id,
            stage=stage,
            diagnostics=diagnostics,
            path_hint=row_path,
        )
        if decrypted_payload is None:
            return row

        payload_instance = decrypted_payload.get("instance")
        if isinstance(payload_instance, str) and payload_instance and payload_instance != instance_id:
            severity = "error" if mode == "strict" else "warning"
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7205",
                    severity=severity,
                    stage=stage,
                    message=(
                        f"Decrypted instance mismatch: row instance '{instance_id}' "
                        f"!= payload instance '{payload_instance}'."
                    ),
                    path=row_path,
                )
            )
            if mode == "strict":
                return row

        resolved_row = dict(decrypted_payload)
        resolved_row.pop("schema_version", None)
        resolved_row.pop("group", None)
        resolved_row.pop("sops", None)
        if not isinstance(resolved_row.get("class_ref"), str):
            resolved_row.pop("class_ref", None)
        resolved_row.pop("hardware_identity_secret_ref", None)
        resolved_row["_source_file"] = source_file
        return resolved_row

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("compilation_owner_instance_rows")
        if owner is not None and owner != "plugin":
            return self.make_result(diagnostics, output_data={"normalized_rows": []})

        bindings_root = ctx.instance_bindings.get("instance_bindings")
        if not isinstance(bindings_root, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="instance-bindings root must contain mapping 'instance_bindings'.",
                    path="instance_bindings",
                )
            )
            rows: list[dict[str, Any]] = []
            ctx.publish("normalized_rows", rows)
            return self.make_result(diagnostics, output_data={"normalized_rows": rows})

        rows = []
        seen_instances: set[str] = set()
        mode = self._resolve_secrets_mode(ctx)
        for group_name, group_rows in bindings_root.items():
            if not isinstance(group_rows, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code="E3201",
                        severity="error",
                        stage=stage,
                        message=f"instance_bindings.{group_name} must be a list.",
                        path=f"instance_bindings.{group_name}",
                    )
                )
                continue

            for idx, row in enumerate(group_rows):
                if not isinstance(row, dict):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must be an object.",
                            path=f"instance_bindings.{group_name}[{idx}]",
                        )
                    )
                    continue

                row_path = f"instance_bindings.{group_name}[{idx}]"
                instance_id = row.get("instance")

                if not isinstance(instance_id, str) or not instance_id:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must define non-empty 'instance'.",
                            path=f"instance_bindings.{group_name}[{idx}].instance",
                        )
                    )
                    continue
                if instance_id in seen_instances:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E2102",
                            severity="error",
                            stage="resolve",
                            message=f"Duplicate instance '{instance_id}'.",
                            path=f"instance_bindings.{group_name}[{idx}]",
                            plugin_id=self.plugin_id,
                        )
                    )
                    continue
                seen_instances.add(instance_id)

                row = self._resolve_inplace_secrets(
                    row=row,
                    instance_id=instance_id,
                    stage=stage,
                    diagnostics=diagnostics,
                    row_path=row_path,
                    mode=mode,
                )

                if mode == "strict":
                    unresolved_paths = self._collect_unresolved_hardware_identity_paths(row)
                    for unresolved_path in unresolved_paths:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7208",
                                severity="error",
                                stage=stage,
                                message=(
                                    "Strict secrets mode requires resolved hardware identity field: "
                                    f"'{unresolved_path}' in instance '{instance_id}'."
                                ),
                                path=row_path,
                            )
                        )

                layer = row.get("layer")
                class_ref = row.get("class_ref")
                object_ref = row.get("object_ref")
                firmware_ref = row.get("firmware_ref")
                os_refs = row.get("os_refs")
                derived_class_ref: str | None = None

                if not isinstance(object_ref, str) or not object_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must define non-empty 'object_ref'.",
                            path=f"instance_bindings.{group_name}[{idx}].object_ref",
                        )
                    )
                else:
                    object_payload = ctx.objects.get(object_ref)
                    if isinstance(object_payload, dict):
                        candidate_class_ref = object_payload.get("class_ref")
                        if isinstance(candidate_class_ref, str) and candidate_class_ref:
                            derived_class_ref = candidate_class_ref

                if not isinstance(class_ref, str) or not class_ref:
                    class_ref = derived_class_ref
                elif isinstance(derived_class_ref, str) and derived_class_ref and class_ref != derived_class_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E2403",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Instance class_ref '{class_ref}' does not match object_ref '{object_ref}' "
                                f"class_ref '{derived_class_ref}'."
                            ),
                            path=f"instance_bindings.{group_name}[{idx}].class_ref",
                        )
                    )

                if not isinstance(class_ref, str) or not class_ref:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                "Instance row must define non-empty 'class_ref' or provide "
                                "object_ref with resolvable class_ref."
                            ),
                            path=f"instance_bindings.{group_name}[{idx}].class_ref",
                        )
                    )
                if not isinstance(layer, str) or not layer:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="Instance row must define non-empty 'layer'.",
                            path=f"instance_bindings.{group_name}[{idx}].layer",
                        )
                    )
                if firmware_ref is not None and (not isinstance(firmware_ref, str) or not firmware_ref):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="firmware_ref must be non-empty string when set.",
                            path=f"instance_bindings.{group_name}[{idx}].firmware_ref",
                        )
                    )
                if os_refs is not None and not isinstance(os_refs, list):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="os_refs must be a list when set.",
                            path=f"instance_bindings.{group_name}[{idx}].os_refs",
                        )
                    )
                    os_refs = []

                embedded_in = row.get("embedded_in")
                if embedded_in is not None and (not isinstance(embedded_in, str) or not embedded_in):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message="embedded_in must be non-empty string when set.",
                            path=f"instance_bindings.{group_name}[{idx}].embedded_in",
                        )
                    )
                    embedded_in = None

                normalized_os_refs: list[str] = []
                if isinstance(os_refs, list):
                    for os_idx, os_ref in enumerate(os_refs):
                        if not isinstance(os_ref, str) or not os_ref:
                            diagnostics.append(
                                self.emit_diagnostic(
                                    code="E3201",
                                    severity="error",
                                    stage=stage,
                                    message="os_refs entries must be non-empty strings.",
                                    path=f"instance_bindings.{group_name}[{idx}].os_refs[{os_idx}]",
                                )
                            )
                            continue
                        normalized_os_refs.append(os_ref)

                source_id = row.get("source_id", instance_id)
                if not isinstance(source_id, str) or not source_id:
                    source_id = instance_id
                extensions = self._extract_extensions(row)

                rows.append(
                    {
                        "group": group_name,
                        "instance": instance_id,
                        "layer": layer,
                        "source_id": source_id,
                        "class_ref": class_ref,
                        "object_ref": object_ref,
                        "status": row.get("status", "pending"),
                        "notes": row.get("notes", ""),
                        "runtime": row.get("runtime"),
                        "firmware_ref": firmware_ref if isinstance(firmware_ref, str) and firmware_ref else None,
                        "os_refs": normalized_os_refs,
                        "embedded_in": embedded_in if isinstance(embedded_in, str) and embedded_in else None,
                        "extensions": extensions,
                    }
                )

        ctx.publish("normalized_rows", rows)
        return self.make_result(diagnostics, output_data={"normalized_rows": rows})

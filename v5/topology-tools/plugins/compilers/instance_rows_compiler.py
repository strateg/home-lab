"""Instance rows normalization compiler plugin (ADR 0069 WS2/WS3, ADR 0072 side-car secrets)."""

from __future__ import annotations

import copy
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from field_annotations import parse_field_annotation
from identifier_policy import contains_unsafe_identifier_chars
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

    @staticmethod
    def _resolve_require_unlock(ctx: PluginContext) -> bool:
        value = ctx.config.get("require_unlock", True)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
        return True

    def _collect_all_placeholder_paths(self, row: dict[str, Any]) -> list[str]:
        """Walk row and collect unresolved secret marker paths."""
        unresolved: list[str] = []

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    # Skip reserved/metadata keys
                    if key in ("sops", "_source_file"):
                        continue
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
                return
            annotation, annotation_error = parse_field_annotation(node)
            if annotation_error is None and annotation is not None and annotation.secret:
                unresolved.append(path)

        walk(row, "")
        return unresolved

    def _decrypt_sidecar_file(
        self,
        *,
        sidecar_path: Path,
        instance_id: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
        require_unlock: bool,
    ) -> dict[str, Any] | None:
        """Decrypt side-car secrets file using sops."""
        command = ["sops", "-d", str(sidecar_path)]
        fail_hard = mode == "strict" or require_unlock
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            severity = "error" if fail_hard else "warning"
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7200",
                    severity=severity,
                    stage=stage,
                    message=f"Failed to execute sops for side-car secrets '{instance_id}': {exc}",
                    path=row_path,
                )
            )
            return None

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            severity = "error" if fail_hard else "warning"
            code = "E7201" if fail_hard else "W7210"
            diagnostics.append(
                self.emit_diagnostic(
                    code=code,
                    severity=severity,
                    stage=stage,
                    message=(
                        f"Failed to decrypt side-car secrets for '{instance_id}'. "
                        f"sops exit={result.returncode}. {stderr}"
                    ),
                    path=row_path,
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
                    message=f"Side-car YAML parse failed for '{instance_id}': {exc}",
                    path=row_path,
                )
            )
            return None

        if not isinstance(payload, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7203",
                    severity="error",
                    stage=stage,
                    message=f"Side-car payload must be object/mapping for '{instance_id}'.",
                    path=row_path,
                )
            )
            return None

        return payload

    def _merge_placeholders(
        self,
        row: dict[str, Any],
        secrets: dict[str, Any],
        instance_id: str,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
    ) -> dict[str, Any]:
        """Deep merge: replace <TODO_*> placeholders with values from decrypted secrets."""
        result = copy.deepcopy(row)

        def walk_and_replace(target: Any, source: Any, path: str) -> Any:
            if isinstance(target, dict) and isinstance(source, dict):
                for key in target:
                    if key in source:
                        target[key] = walk_and_replace(target[key], source[key], f"{path}.{key}")
                return target

            if isinstance(target, list) and isinstance(source, list):
                for idx in range(min(len(target), len(source))):
                    target[idx] = walk_and_replace(target[idx], source[idx], f"{path}[{idx}]")
                return target

            if isinstance(target, str) and self._TODO_MARKER_RE.fullmatch(target):
                # Target is placeholder - replace with secret value if available
                if source is not None and not isinstance(source, dict):
                    return source
                elif mode == "strict":
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7211",
                            severity="error",
                            stage=stage,
                            message=f"Placeholder '{target}' at '{path}' has no matching secret value.",
                            path=row_path,
                        )
                    )
                return target

            if isinstance(target, str) and target.startswith("@"):
                annotation, annotation_error = parse_field_annotation(target)
                if annotation_error is not None:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=f"Invalid annotation '{target}' at '{path}': {annotation_error}.",
                            path=row_path,
                        )
                    )
                    return target
                if annotation is not None and annotation.secret:
                    if source is not None and not isinstance(source, dict):
                        return source
                    if mode == "strict":
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7211",
                                severity="error",
                                stage=stage,
                                message=f"Secret annotation '{target}' at '{path}' has no matching secret value.",
                                path=row_path,
                            )
                        )
                    return target

            if source is not None and not isinstance(source, dict) and not isinstance(source, list):
                if target is not None and target != source:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7212",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Secret conflict at '{path}' in instance '{instance_id}': "
                                "plaintext value differs from decrypted side-car value. "
                                "Use @secret/@*_secret marker or remove plaintext value."
                            ),
                            path=row_path,
                        )
                    )

            # Non-placeholder values are preserved unchanged
            return target

        for key in secrets:
            if key in ("instance", "sops"):
                continue
            if key in result:
                result[key] = walk_and_replace(result[key], secrets[key], key)

        return result

    def _resolve_sidecar_secrets(
        self,
        *,
        row: dict[str, Any],
        instance_id: str,
        secrets_root: Path,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        row_path: str,
        mode: str,
        require_unlock: bool,
    ) -> dict[str, Any]:
        """Merge decrypted side-car secrets into instance row, replacing placeholders only."""
        if mode == "passthrough":
            return row

        # Look for side-car file
        sidecar_path = secrets_root / "instances" / f"{instance_id}.yaml"
        if not sidecar_path.exists():
            # No side-car file - check if strict mode needs to fail on placeholders
            if mode == "strict":
                unresolved = self._collect_all_placeholder_paths(row)
                if unresolved:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E7210",
                            severity="error",
                            stage=stage,
                            message=(
                                f"Strict mode: instance '{instance_id}' has unresolved placeholders "
                                f"but no side-car secrets file at {sidecar_path.name}. "
                                f"Placeholders: {', '.join(unresolved[:5])}"
                                + (f" (+{len(unresolved) - 5} more)" if len(unresolved) > 5 else "")
                            ),
                            path=row_path,
                        )
                    )
            return row

        # Decrypt side-car file
        decrypted = self._decrypt_sidecar_file(
            sidecar_path=sidecar_path,
            instance_id=instance_id,
            stage=stage,
            diagnostics=diagnostics,
            row_path=row_path,
            mode=mode,
            require_unlock=require_unlock,
        )
        if decrypted is None:
            return row

        # Validate instance ID match
        sidecar_instance = decrypted.get("instance")
        if isinstance(sidecar_instance, str) and sidecar_instance and sidecar_instance != instance_id:
            mismatch_is_error = mode == "strict" or require_unlock
            severity = "error" if mismatch_is_error else "warning"
            diagnostics.append(
                self.emit_diagnostic(
                    code="E7205",
                    severity=severity,
                    stage=stage,
                    message=(
                        f"Side-car instance mismatch: row instance '{instance_id}' "
                        f"!= side-car instance '{sidecar_instance}'."
                    ),
                    path=row_path,
                )
            )
            # Mismatch means side-car cannot be trusted for this row in any mode.
            return row

        # Merge placeholders
        merged_row = self._merge_placeholders(
            row=row,
            secrets=decrypted,
            instance_id=instance_id,
            stage=stage,
            diagnostics=diagnostics,
            row_path=row_path,
            mode=mode,
        )

        return merged_row

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
        require_unlock = self._resolve_require_unlock(ctx)

        # Resolve secrets_root path (relative to repo_root)
        secrets_root_str = ctx.config.get("secrets_root", "secrets")
        repo_root = ctx.config.get("repo_root")
        if isinstance(repo_root, str) and repo_root:
            secrets_root = Path(repo_root) / secrets_root_str
        else:
            # Fallback: resolve relative to topology-tools parent
            secrets_root = Path(__file__).resolve().parents[4] / secrets_root_str

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
                if contains_unsafe_identifier_chars(instance_id):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"instance id '{instance_id}' contains filename-unsafe characters; "
                                "use only cross-platform filename-safe symbols."
                            ),
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

                if "hardware_identity_secret_ref" in row:
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                "Field 'hardware_identity_secret_ref' is deprecated and forbidden. "
                                "Store encrypted secret data adjacent to target fields."
                            ),
                            path=f"instance_bindings.{group_name}[{idx}].hardware_identity_secret_ref",
                        )
                    )

                row = self._resolve_sidecar_secrets(
                    row=row,
                    instance_id=instance_id,
                    secrets_root=secrets_root,
                    stage=stage,
                    diagnostics=diagnostics,
                    row_path=row_path,
                    mode=mode,
                    require_unlock=require_unlock,
                )

                if mode == "strict":
                    unresolved_paths = self._collect_all_placeholder_paths(row)
                    for unresolved_path in unresolved_paths:
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E7208",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"Strict secrets mode requires resolved placeholder: "
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

                if isinstance(class_ref, str) and class_ref and contains_unsafe_identifier_chars(class_ref):
                    diagnostics.append(
                        self.emit_diagnostic(
                            code="E3201",
                            severity="error",
                            stage=stage,
                            message=(
                                f"class_ref '{class_ref}' contains filename-unsafe characters; "
                                "use only cross-platform filename-safe symbols."
                            ),
                            path=f"instance_bindings.{group_name}[{idx}].class_ref",
                        )
                    )
                    class_ref = None

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
                    if contains_unsafe_identifier_chars(object_ref):
                        diagnostics.append(
                            self.emit_diagnostic(
                                code="E3201",
                                severity="error",
                                stage=stage,
                                message=(
                                    f"object_ref '{object_ref}' contains filename-unsafe characters; "
                                    "use only cross-platform filename-safe symbols."
                                ),
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

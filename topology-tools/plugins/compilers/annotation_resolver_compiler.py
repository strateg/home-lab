"""Centralized field-annotation resolver for compile stage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from field_annotations import FieldAnnotation, parse_field_annotation
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage
from yaml_loader import load_yaml_file

DEFAULT_FORMAT_REGISTRY = Path(__file__).resolve().parents[1] / "data" / "instance-field-formats.yaml"


class AnnotationResolverCompiler(CompilerPlugin):
    """Parse annotations once and publish normalized annotation indexes."""

    @staticmethod
    def _format_path(path: tuple[Any, ...]) -> str:
        if not path:
            return "<root>"
        parts: list[str] = []
        for token in path:
            if isinstance(token, int):
                parts.append(f"[{token}]")
            else:
                if parts:
                    parts.append(".")
                parts.append(str(token))
        return "".join(parts)

    def _load_format_registry(
        self,
        *,
        ctx: PluginContext,
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, dict[str, Any]]:
        configured = ctx.config.get("format_registry_path")
        registry_path = Path(configured) if isinstance(configured, str) and configured else DEFAULT_FORMAT_REGISTRY
        if not registry_path.is_absolute():
            registry_path = (Path(__file__).resolve().parents[1] / registry_path).resolve()
        try:
            payload = load_yaml_file(registry_path) or {}
        except Exception as exc:  # pragma: no cover - defensive path
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=f"Cannot load format registry '{registry_path}': {exc}",
                    path="plugin:base.compiler.annotation_resolver",
                )
            )
            return {}

        formats = payload.get("formats")
        if not isinstance(formats, dict):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message=f"Format registry '{registry_path}' must contain mapping 'formats'.",
                    path="plugin:base.compiler.annotation_resolver",
                )
            )
            return {}

        result: dict[str, dict[str, Any]] = {}
        for name, spec in formats.items():
            if isinstance(name, str) and isinstance(spec, dict):
                result[name] = spec
        return result

    @staticmethod
    def _annotation_payload(annotation: FieldAnnotation) -> dict[str, Any]:
        return {
            "name": annotation.name,
            "value_type": annotation.value_type,
            "required": annotation.required,
            "optional": annotation.optional,
            "secret": annotation.secret,
        }

    @staticmethod
    def _normalize_token(value: str) -> str:
        token = value.strip().lower()
        return "".join(ch if ch.isalnum() else "_" for ch in token).strip("_")

    def _derive_interface_mac_secret_annotations(
        self,
        *,
        object_payload: dict[str, Any],
        formats: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Project object interface MAC annotations into instance secret paths."""
        result: dict[str, dict[str, Any]] = {}
        hardware_specs = object_payload.get("hardware_specs")
        if not isinstance(hardware_specs, dict):
            return result
        interfaces = hardware_specs.get("interfaces")
        if not isinstance(interfaces, dict):
            return result
        for group_name, entries in interfaces.items():
            if not isinstance(group_name, str) or not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                mac_token = entry.get("mac")
                if not isinstance(mac_token, str):
                    continue
                annotation, annotation_error = parse_field_annotation(mac_token)
                if annotation_error is not None or annotation is None or not annotation.secret:
                    continue
                if isinstance(annotation.value_type, str) and annotation.value_type not in formats:
                    continue
                name = entry.get("name")
                if not isinstance(name, str) or not name.strip():
                    continue
                key = name.strip()
                band = entry.get("band")
                if isinstance(band, str) and band.strip():
                    key = f"{key}_{self._normalize_token(band)}"
                path = f"hardware_identity.mac_addresses.{key}"
                result[path] = self._annotation_payload(annotation)
        return result

    def _collect_annotations(
        self,
        *,
        node: Any,
        path: tuple[Any, ...],
        out: dict[str, dict[str, Any]],
        formats: dict[str, dict[str, Any]],
        stage: Stage,
        diagnostics: list[PluginDiagnostic],
        source_path: str,
    ) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                self._collect_annotations(
                    node=value,
                    path=path + (key,),
                    out=out,
                    formats=formats,
                    stage=stage,
                    diagnostics=diagnostics,
                    source_path=source_path,
                )
            return
        if isinstance(node, list):
            for idx, value in enumerate(node):
                self._collect_annotations(
                    node=value,
                    path=path + (idx,),
                    out=out,
                    formats=formats,
                    stage=stage,
                    diagnostics=diagnostics,
                    source_path=source_path,
                )
            return
        if not isinstance(node, str):
            return
        if node.startswith("@@"):
            return
        if not node.startswith("@"):
            return

        annotation, annotation_error = parse_field_annotation(node)
        if annotation_error is not None:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6801",
                    severity="error",
                    stage=stage,
                    message=f"Invalid annotation '{node}': {annotation_error}.",
                    path=f"{source_path}:{self._format_path(path)}",
                )
            )
            return
        if annotation is None:
            return
        if isinstance(annotation.value_type, str) and annotation.value_type not in formats:
            diagnostics.append(
                self.emit_diagnostic(
                    code="E6801",
                    severity="error",
                    stage=stage,
                    message=f"Annotation format '{annotation.value_type}' is not defined in registry.",
                    path=f"{source_path}:{self._format_path(path)}",
                )
            )
            return
        out[self._format_path(path)] = self._annotation_payload(annotation)

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

        owner = ctx.config.get("compilation_owner_annotation_resolver")
        if owner is not None and owner != "plugin":
            return self.make_result(
                diagnostics,
                output_data={
                    "object_annotations": {},
                    "object_secret_annotations": {},
                    "row_annotations_by_instance": {},
                    "annotation_formats": {},
                },
            )

        formats = self._load_format_registry(ctx=ctx, stage=stage, diagnostics=diagnostics)

        object_annotations: dict[str, dict[str, dict[str, Any]]] = {}
        object_secret_annotations: dict[str, dict[str, dict[str, Any]]] = {}
        for object_id, object_payload in ctx.objects.items():
            if not isinstance(object_id, str) or not isinstance(object_payload, dict):
                continue
            annotations: dict[str, dict[str, Any]] = {}
            self._collect_annotations(
                node=object_payload,
                path=(),
                out=annotations,
                formats=formats,
                stage=stage,
                diagnostics=diagnostics,
                source_path=f"object:{object_id}",
            )
            object_annotations[object_id] = annotations
            secret_annotations = {path: spec for path, spec in annotations.items() if bool(spec.get("secret"))}
            projected = self._derive_interface_mac_secret_annotations(object_payload=object_payload, formats=formats)
            secret_annotations.update(projected)
            object_secret_annotations[object_id] = secret_annotations

        row_annotations_by_instance: dict[str, dict[str, dict[str, Any]]] = {}
        bindings = ctx.instance_bindings.get("instance_bindings")
        if isinstance(bindings, dict):
            for group_name, group_rows in bindings.items():
                if not isinstance(group_rows, list):
                    continue
                for idx, row in enumerate(group_rows):
                    if not isinstance(row, dict):
                        continue
                    instance_id = row.get("instance")
                    row_id = instance_id if isinstance(instance_id, str) and instance_id else f"{group_name}[{idx}]"
                    row_annotations: dict[str, dict[str, Any]] = {}
                    self._collect_annotations(
                        node=row,
                        path=(),
                        out=row_annotations,
                        formats=formats,
                        stage=stage,
                        diagnostics=diagnostics,
                        source_path=f"instance:{group_name}:{row_id}",
                    )
                    row_annotations_by_instance[row_id] = row_annotations

        ctx.publish("object_annotations", object_annotations)
        ctx.publish("object_secret_annotations", object_secret_annotations)
        ctx.publish("row_annotations_by_instance", row_annotations_by_instance)
        ctx.publish("annotation_formats", formats)

        return self.make_result(
            diagnostics,
            output_data={
                "object_annotations": object_annotations,
                "object_secret_annotations": object_secret_annotations,
                "row_annotations_by_instance": row_annotations_by_instance,
                "annotation_formats": formats,
            },
        )

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

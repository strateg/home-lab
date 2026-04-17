"""Class/object module loader compiler plugin (ADR 0069 WS2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from identifier_policy import contains_unsafe_identifier_chars
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage
from semantic_keywords import load_semantic_keyword_registry, resolve_semantic_value
from yaml_loader import load_yaml_file

REPO_ROOT = Path(__file__).resolve().parents[4]


class ModuleLoaderCompiler(CompilerPlugin):
    """Load class/object module YAML files for plugin-first pipeline."""

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(REPO_ROOT).as_posix())
        except ValueError:
            return str(path)

    @staticmethod
    def _iter_yaml_files(directory: Path) -> Iterable[Path]:
        if not directory.exists():
            return []
        return sorted(path for path in directory.rglob("*.yaml") if path.is_file())

    @staticmethod
    def _is_module_file(path: Path, module_type: str) -> bool:
        if module_type == "class":
            return path.name.startswith("class.")
        if module_type == "object":
            return path.name.startswith("obj.")
        return True

    def _load_yaml(
        self,
        *,
        path: Path,
        code_missing: str,
        code_parse: str,
        stage_name: str,
        diagnostics: list[PluginDiagnostic],
    ) -> dict[str, Any] | None:
        if not path.exists() or not path.is_file():
            diagnostics.append(
                PluginDiagnostic(
                    code=code_missing,
                    severity="error",
                    stage=stage_name,
                    message=f"File does not exist: {path}",
                    path=self._rel(path),
                    plugin_id=self.plugin_id,
                )
            )
            return None
        try:
            payload = load_yaml_file(path) or {}
        except (OSError, yaml.YAMLError) as exc:
            diagnostics.append(
                PluginDiagnostic(
                    code=code_parse,
                    severity="error",
                    stage=stage_name,
                    message=f"YAML parse error: {exc}",
                    path=self._rel(path),
                    plugin_id=self.plugin_id,
                )
            )
            return None
        if not isinstance(payload, dict):
            diagnostics.append(
                PluginDiagnostic(
                    code="E1004",
                    severity="error",
                    stage=stage_name,
                    message="Expected mapping/object at YAML root.",
                    path=self._rel(path),
                    plugin_id=self.plugin_id,
                )
            )
            return None
        return payload

    def _load_module_map(
        self,
        *,
        directory: Path,
        module_type: str,
        semantic_keywords_path: Path | None,
        diagnostics: list[PluginDiagnostic],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        registry = load_semantic_keyword_registry(semantic_keywords_path)
        token = "class_id" if module_type == "class" else "object_id"
        module_map: dict[str, dict[str, Any]] = {}
        module_paths: dict[str, str] = {}
        files = [path for path in self._iter_yaml_files(directory) if self._is_module_file(path, module_type)]
        if not files:
            diagnostics.append(
                PluginDiagnostic(
                    code="E1001",
                    severity="error",
                    stage="load",
                    message=f"No {module_type} YAML files found under {directory}",
                    path=self._rel(directory),
                    plugin_id=self.plugin_id,
                )
            )
            return module_map, module_paths

        for path in files:
            payload = self._load_yaml(
                path=path,
                code_missing="E1001",
                code_parse="E1003",
                stage_name="load",
                diagnostics=diagnostics,
            )
            if payload is None:
                continue
            legacy_keys = (
                {"class", "extends", "version", "title", "summary", "description", "layer"}
                if module_type == "class"
                else {"object", "class_ref", "version", "title", "summary", "description", "layer"}
            )
            present_legacy = sorted(key for key in legacy_keys if key in payload)
            if present_legacy:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8801",
                        severity="error",
                        stage="validate",
                        message=(
                            f"{module_type} module uses legacy semantic keys: {', '.join(present_legacy)}. "
                            "Use canonical '@'-prefixed semantic keys only."
                        ),
                        path=self._rel(path),
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            key_resolution = resolve_semantic_value(
                payload,
                registry=registry,
                context="entity_manifest",
                token=token,
            )
            if key_resolution.has_collision:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8803",
                        severity="error",
                        stage="validate",
                        message=(
                            f"{module_type} module contains semantic-key collision for '{token}': "
                            f"{', '.join(key_resolution.present_keys)}."
                        ),
                        path=self._rel(path),
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            item_id = key_resolution.value
            if not isinstance(item_id, str) or not item_id:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8801",
                        severity="error",
                        stage="validate",
                        message=(
                            f"{module_type} module is missing required semantic key '{token}' "
                            f"('{registry.get(token).canonical}')."
                        ),
                        path=self._rel(path),
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if contains_unsafe_identifier_chars(item_id):
                diagnostics.append(
                    PluginDiagnostic(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message=(
                            f"{module_type} id '{item_id}' contains filename-unsafe characters; "
                            "use only cross-platform filename-safe symbols."
                        ),
                        path=f"{self._rel(path)}:{key_resolution.key or registry.get(token).canonical}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            normalized_payload = dict(payload)
            if module_type == "class":
                normalized_payload["class"] = item_id
                parent_resolution = resolve_semantic_value(
                    normalized_payload,
                    registry=registry,
                    context="entity_manifest",
                    token="parent_ref",
                )
                if parent_resolution.has_collision:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E8803",
                            severity="error",
                            stage="validate",
                            message=(
                                "class module contains semantic-key collision for parent_ref: "
                                f"{', '.join(parent_resolution.present_keys)}."
                            ),
                            path=self._rel(path),
                            plugin_id=self.plugin_id,
                        )
                    )
                    continue
                if parent_resolution.found:
                    normalized_payload["extends"] = parent_resolution.value
            else:
                normalized_payload["object"] = item_id
                parent_resolution = resolve_semantic_value(
                    normalized_payload,
                    registry=registry,
                    context="entity_manifest",
                    token="parent_ref",
                )
                if parent_resolution.has_collision:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E8803",
                            severity="error",
                            stage="validate",
                            message=(
                                "object module contains semantic-key collision for parent_ref: "
                                f"{', '.join(parent_resolution.present_keys)}."
                            ),
                            path=self._rel(path),
                            plugin_id=self.plugin_id,
                        )
                    )
                    continue
                if parent_resolution.found:
                    normalized_payload["class_ref"] = parent_resolution.value
            metadata_fields = (
                ("schema_version", "version"),
                ("entity_title", "title"),
                ("entity_summary", "summary"),
                ("entity_description", "description"),
                ("entity_layer", "layer"),
            )
            metadata_error = False
            for metadata_token, legacy_key in metadata_fields:
                metadata_resolution = resolve_semantic_value(
                    normalized_payload,
                    registry=registry,
                    context="entity_manifest",
                    token=metadata_token,
                )
                if metadata_resolution.has_collision:
                    diagnostics.append(
                        PluginDiagnostic(
                            code="E8803",
                            severity="error",
                            stage="validate",
                            message=(
                                f"{module_type} module contains semantic-key collision for {metadata_token}: "
                                f"{', '.join(metadata_resolution.present_keys)}."
                            ),
                            path=self._rel(path),
                            plugin_id=self.plugin_id,
                        )
                    )
                    metadata_error = True
                    break
                if metadata_resolution.found:
                    normalized_payload[legacy_key] = metadata_resolution.value
            if metadata_error:
                continue
            if item_id in module_map:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E2102",
                        severity="error",
                        stage="resolve",
                        message=f"Duplicate {module_type} '{item_id}'.",
                        path=self._rel(path),
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            module_map[item_id] = {"payload": normalized_payload, "path": self._rel(path)}
            module_paths[item_id] = self._rel(path)
        return module_map, module_paths

    def _validate_typed_extends(
        self,
        *,
        class_map: dict[str, dict[str, Any]],
        object_map: dict[str, dict[str, Any]],
        diagnostics: list[PluginDiagnostic],
    ) -> None:
        class_edges: dict[str, str] = {}
        for class_id, class_item in class_map.items():
            if not isinstance(class_item, dict):
                continue
            payload = class_item.get("payload")
            class_path = class_item.get("path")
            if not isinstance(payload, dict):
                continue
            extends_ref = payload.get("extends")
            if extends_ref is None:
                continue
            if not isinstance(extends_ref, str) or not extends_ref:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message="class module '@extends' must reference non-empty class id.",
                        path=class_path if isinstance(class_path, str) else f"class:{class_id}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if extends_ref == class_id:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message=f"class module '@extends' must not self-reference '{class_id}'.",
                        path=class_path if isinstance(class_path, str) else f"class:{class_id}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if extends_ref in object_map:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message=(
                            f"class module '@extends' target '{extends_ref}' is object id; "
                            "class inheritance requires class id."
                        ),
                        path=class_path if isinstance(class_path, str) else f"class:{class_id}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if extends_ref not in class_map:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message=(f"class module '@extends' target '{extends_ref}' does not exist in class registry."),
                        path=class_path if isinstance(class_path, str) else f"class:{class_id}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            class_edges[class_id] = extends_ref

        reported_cycles: set[frozenset[str]] = set()
        for start_class in class_edges:
            visited: dict[str, int] = {}
            chain: list[str] = []
            cursor = start_class
            while cursor in class_edges:
                if cursor in visited:
                    cycle_nodes = chain[visited[cursor] :] + [cursor]
                    cycle_members = frozenset(cycle_nodes[:-1])
                    if cycle_members and cycle_members not in reported_cycles:
                        reported_cycles.add(cycle_members)
                        cycle_path = " -> ".join(cycle_nodes)
                        class_item = class_map.get(cursor, {})
                        class_path = class_item.get("path") if isinstance(class_item, dict) else None
                        diagnostics.append(
                            PluginDiagnostic(
                                code="E8804",
                                severity="error",
                                stage="validate",
                                message=f"class inheritance cycle detected: {cycle_path}.",
                                path=class_path if isinstance(class_path, str) else f"class:{cursor}",
                                plugin_id=self.plugin_id,
                            )
                        )
                    break
                visited[cursor] = len(chain)
                chain.append(cursor)
                cursor = class_edges[cursor]

        for object_id, object_item in object_map.items():
            if not isinstance(object_item, dict):
                continue
            payload = object_item.get("payload")
            object_path = object_item.get("path")
            if not isinstance(payload, dict):
                continue
            class_ref = payload.get("class_ref")
            if not isinstance(class_ref, str) or not class_ref:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message="object module '@extends/class_ref' must reference non-empty class id.",
                        path=object_path if isinstance(object_path, str) else f"object:{object_id}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if class_ref in object_map:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message=(
                            f"object module '@extends/class_ref' target '{class_ref}' is object id; "
                            "object inheritance requires class id."
                        ),
                        path=object_path if isinstance(object_path, str) else f"object:{object_id}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if class_ref not in class_map:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E8804",
                        severity="error",
                        stage="validate",
                        message=(
                            f"object module '@extends/class_ref' target '{class_ref}' does not exist in class registry."
                        ),
                        path=object_path if isinstance(object_path, str) else f"object:{object_id}",
                        plugin_id=self.plugin_id,
                    )
                )

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        envelope_mode = getattr(ctx, "_snapshot", None) is not None

        owner = ctx.config.get("compilation_owner_module_maps")
        if owner is not None and owner != "plugin":
            class_map: dict[str, dict[str, Any]] = {}
            object_map: dict[str, dict[str, Any]] = {}
            for class_id, payload in ctx.classes.items():
                if isinstance(class_id, str) and isinstance(payload, dict):
                    class_map[class_id] = {"payload": payload, "path": ""}
            for object_id, payload in ctx.objects.items():
                if isinstance(object_id, str) and isinstance(payload, dict):
                    object_map[object_id] = {"payload": payload, "path": ""}
            return self.make_result(diagnostics, output_data={"class_map": class_map, "object_map": object_map})

        class_root_raw = ctx.config.get("class_modules_root")
        object_root_raw = ctx.config.get("object_modules_root")
        semantic_keywords_path_raw = ctx.config.get("semantic_keywords_path")
        if not isinstance(class_root_raw, str) or not isinstance(object_root_raw, str):
            diagnostics.append(
                self.emit_diagnostic(
                    code="E3201",
                    severity="error",
                    stage=stage,
                    message="Missing class/object module roots in plugin context config.",
                    path="pipeline:module_loader",
                )
            )
            return self.make_result(diagnostics, output_data={"class_map": {}, "object_map": {}})

        class_root = Path(class_root_raw)
        object_root = Path(object_root_raw)
        semantic_keywords_path = (
            Path(semantic_keywords_path_raw)
            if isinstance(semantic_keywords_path_raw, str) and semantic_keywords_path_raw
            else None
        )

        class_map, class_paths = self._load_module_map(
            directory=class_root,
            module_type="class",
            semantic_keywords_path=semantic_keywords_path,
            diagnostics=diagnostics,
        )
        object_map, object_paths = self._load_module_map(
            directory=object_root,
            module_type="object",
            semantic_keywords_path=semantic_keywords_path,
            diagnostics=diagnostics,
        )
        self._validate_typed_extends(class_map=class_map, object_map=object_map, diagnostics=diagnostics)

        if not envelope_mode:
            ctx.classes = {
                class_id: item["payload"]
                for class_id, item in class_map.items()
                if isinstance(item, dict) and isinstance(item.get("payload"), dict)
            }
            ctx.objects = {
                object_id: item["payload"]
                for object_id, item in object_map.items()
                if isinstance(item, dict) and isinstance(item.get("payload"), dict)
            }
        ctx.publish("class_map", class_map)
        ctx.publish("object_map", object_map)
        ctx.publish("class_module_paths", class_paths)
        ctx.publish("object_module_paths", object_paths)

        return self.make_result(
            diagnostics,
            output_data={
                "class_map": class_map,
                "object_map": object_map,
                "class_module_paths": class_paths,
                "object_module_paths": object_paths,
            },
        )

    def on_init(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        return self.execute(ctx, stage)

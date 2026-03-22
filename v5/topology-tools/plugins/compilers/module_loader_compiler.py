"""Class/object module loader compiler plugin (ADR 0069 WS2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml

from identifier_policy import contains_unsafe_identifier_chars
from kernel.plugin_base import CompilerPlugin, PluginContext, PluginDiagnostic, PluginResult, Stage

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
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
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
        diagnostics: list[PluginDiagnostic],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
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
            module_key = "class" if module_type == "class" else "object"
            item_id = payload.get(module_key)
            if not isinstance(item_id, str) or not item_id:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E3201",
                        severity="error",
                        stage="validate",
                        message=f"{module_type} module is missing '{module_key}'.",
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
                        path=f"{self._rel(path)}:{module_key}",
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            if item_id in module_map:
                diagnostics.append(
                    PluginDiagnostic(
                        code="E2102",
                        severity="error",
                        stage="resolve",
                        message=f"Duplicate {module_type} {module_key} '{item_id}'.",
                        path=self._rel(path),
                        plugin_id=self.plugin_id,
                    )
                )
                continue
            module_map[item_id] = {"payload": payload, "path": self._rel(path)}
            module_paths[item_id] = self._rel(path)
        return module_map, module_paths

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []

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

        class_map, class_paths = self._load_module_map(
            directory=class_root,
            module_type="class",
            diagnostics=diagnostics,
        )
        object_map, object_paths = self._load_module_map(
            directory=object_root,
            module_type="object",
            diagnostics=diagnostics,
        )

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

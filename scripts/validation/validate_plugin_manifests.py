#!/usr/bin/env python3
"""Validate plugin manifests against schema and entry module paths."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import jsonschema
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_schema(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _discover_manifests(repo_root: Path) -> list[Path]:
    manifests = [repo_root / "topology-tools" / "plugins" / "plugins.yaml"]
    manifests.extend(sorted((repo_root / "topology" / "class-modules").rglob("plugins.yaml")))
    manifests.extend(sorted((repo_root / "topology" / "object-modules").rglob("plugins.yaml")))
    return manifests


def _resolve_entry_manifest_relative(manifest_dir: Path, entry: str) -> Path | None:
    if ":" not in entry:
        return None
    module_path = entry.split(":", 1)[0].strip()
    if not module_path:
        return None
    return manifest_dir / module_path


RUNTIME_CONFIG_KEYS = {
    "base_plugins_manifest_path",
    "capability_catalog_path",
    "capability_packs_path",
    "changed_input_scopes",
    "class_modules_root",
    "compile_generated_at",
    "compiled_model_version",
    "compiler_pipeline_version",
    "discover_load_module_manifests",
    "discovered_plugin_count",
    "discovered_plugin_manifests",
    "dist_root",
    "generation_owner_effective_json",
    "generator_artifacts_root",
    "instance_source_mode",
    "model_lock_path",
    "module_index_path",
    "object_modules_root",
    "parity_gate",
    "pipeline_mode",
    "plugin_registry",
    "product_bundles_root",
    "product_profiles_root",
    "project_id",
    "project_manifest_path",
    "project_plugins_root",
    "project_root",
    "release_tag",
    "repo_root",
    "require_new_model",
    "runtime_profile",
    "sbom_output_dir",
    "secrets_mode",
    "secrets_root",
    "semantic_keywords_path",
    "signing_backend",
    "source_manifest_digest",
    "stage_failure_context",
    "strict_mode",
    "validation_owner_capability_contract",
    "validation_owner_embedded_in",
    "validation_owner_model_lock",
    "validation_owner_references",
    "workspace_root",
}
RUNTIME_CONFIG_PREFIXES = ("validation_owner_", "compilation_owner_", "generation_owner_")


class _CtxConfigKeyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.keys: set[str] = set()

    @staticmethod
    def _is_ctx_config(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "config"
            and isinstance(node.value, ast.Name)
            and node.value.id == "ctx"
        )

    @staticmethod
    def _literal_string(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and self._is_ctx_config(node.func.value)
            and node.args
        ):
            literal = self._literal_string(node.args[0])
            if literal:
                self.keys.add(literal)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._is_ctx_config(node.value):
            literal = self._literal_string(node.slice)
            if literal:
                self.keys.add(literal)
        self.generic_visit(node)


def _find_entry_node(module_tree: ast.Module, symbol_name: str) -> ast.AST | None:
    for node in module_tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol_name:
            return node
    return None


def _extract_ctx_config_keys(module_path: Path, entry_symbol: str | None) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    visitor = _CtxConfigKeyVisitor()
    target = _find_entry_node(tree, entry_symbol) if entry_symbol else None
    visitor.visit(target or tree)
    return visitor.keys


def _schema_property_names(plugin: dict) -> set[str]:
    schema = plugin.get("config_schema")
    if not isinstance(schema, dict):
        return set()
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return set()
    return {str(name) for name in properties}


def _is_runtime_config_key(key: str) -> bool:
    return key in RUNTIME_CONFIG_KEYS or key.startswith(RUNTIME_CONFIG_PREFIXES)


def _config_schema_warning(plugin: dict, manifest_dir: Path) -> str | None:
    entry = str(plugin.get("entry", ""))
    resolved = _resolve_entry_manifest_relative(manifest_dir, entry)
    if resolved is None or not resolved.exists():
        return None

    _, _, symbol_name = entry.partition(":")
    used_keys = {
        key
        for key in _extract_ctx_config_keys(resolved, symbol_name.strip() or None)
        if not _is_runtime_config_key(key)
    }
    if not used_keys:
        return None

    schema_keys = _schema_property_names(plugin)
    missing_keys = sorted(key for key in used_keys if key not in schema_keys)
    if not missing_keys:
        return None

    plugin_id = plugin.get("id", "<unknown>")
    return (
        f"{plugin_id}: entry consumes ctx.config keys without config_schema coverage: "
        + ", ".join(missing_keys)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate plugin manifests against schema and entry modules.")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Return a non-zero exit code when manifest config_schema warnings are detected.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = _repo_root()
    schema_path = repo_root / "topology-tools" / "schemas" / "plugin-manifest.schema.json"
    schema = _load_schema(schema_path)
    manifests = _discover_manifests(repo_root)
    warnings: list[str] = []

    if not manifests:
        print("ERROR: no plugin manifests discovered")
        return 1

    for manifest_path in manifests:
        if not manifest_path.exists():
            print(f"ERROR: missing manifest: {manifest_path}")
            return 1

        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = yaml.safe_load(handle) or {}

        try:
            jsonschema.validate(manifest, schema)
            print(f"OK schema: {manifest_path}")
        except jsonschema.ValidationError as exc:
            print(f"ERROR schema: {manifest_path}: {exc.message}")
            return 1

        manifest_dir = manifest_path.parent
        for plugin in manifest.get("plugins", []):
            plugin_id = plugin.get("id", "<unknown>")
            entry = str(plugin.get("entry", ""))
            resolved = _resolve_entry_manifest_relative(manifest_dir, entry)
            if resolved is None:
                continue
            if not resolved.exists():
                print(f"ERROR entry: {plugin_id}: {resolved} (from {manifest_path})")
                return 1
            print(f"OK entry: {plugin_id}")
            warning = _config_schema_warning(plugin, manifest_dir)
            if warning:
                warnings.append(warning)
                print(f"WARN config_schema: {warning}")

    print("All plugin manifests validated")
    if warnings and args.fail_on_warnings:
        print(f"ERROR: plugin manifest warnings detected: {len(warnings)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Contract checks for four-level plugin boundary rules."""

from __future__ import annotations

import ast
import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import yaml

V5_ROOT = Path(__file__).resolve().parents[2]

CLASS_MANIFEST_ROOT = V5_ROOT / "topology" / "class-modules"
OBJECT_MANIFEST_ROOT = V5_ROOT / "topology" / "object-modules"
PRIVATE_IP_LITERAL_RE = re.compile(
    r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})\b"
)
LOCAL_HOST_LITERAL_RE = re.compile(r"\b[a-z0-9][\w-]*\.(?:local|home|lan|internal)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PluginSource:
    path: Path
    kind: str


def _iter_manifests(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("plugins.yaml") if path.is_file())


def _iter_plugin_sources(manifest_path: Path) -> Iterable[PluginSource]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return []

    sources: list[PluginSource] = []
    for row in plugins:
        if not isinstance(row, dict):
            continue
        entry = row.get("entry")
        kind = row.get("kind")
        if not isinstance(entry, str) or ":" not in entry:
            continue
        if not isinstance(kind, str) or not kind:
            continue
        module_rel, _class_name = entry.rsplit(":", 1)
        if not module_rel.endswith(".py"):
            continue
        sources.append(PluginSource(path=(manifest_path.parent / module_rel).resolve(), kind=kind))
    return sources


def _collect_text_violations(files: Iterable[Path], *, forbidden_markers: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for file_path in files:
        if not file_path.exists():
            violations.append(f"missing plugin source: {file_path}")
            continue
        body = file_path.read_text(encoding="utf-8")
        leaked = [marker for marker in forbidden_markers if marker in body]
        if leaked:
            rel = file_path.relative_to(V5_ROOT).as_posix()
            violations.append(f"{rel}: forbidden markers {leaked}")
    return violations


def _iter_object_plugin_python_files() -> list[Path]:
    files: list[Path] = []
    for object_dir in sorted(path for path in OBJECT_MANIFEST_ROOT.iterdir() if path.is_dir()):
        plugins_dir = object_dir / "plugins"
        if not plugins_dir.exists():
            continue
        files.extend(sorted(path for path in plugins_dir.rglob("*.py") if path.is_file()))
    return files


def _find_instance_specific_literal(literal: str) -> str | None:
    stripped = literal.strip()
    if not stripped:
        return None

    if "://" in stripped:
        parsed = urlparse(stripped)
        host = (parsed.hostname or "").strip().lower()
        if host:
            try:
                if ipaddress.ip_address(host).is_private:
                    return stripped
            except ValueError:
                pass
            if LOCAL_HOST_LITERAL_RE.search(host):
                return stripped

    ip_match = PRIVATE_IP_LITERAL_RE.search(stripped)
    if ip_match:
        return ip_match.group(0)

    host_match = LOCAL_HOST_LITERAL_RE.search(stripped)
    if host_match:
        return host_match.group(0)

    return None


def test_class_level_plugins_do_not_reference_object_or_instance_ids() -> None:
    plugin_files: list[Path] = []
    for manifest_path in _iter_manifests(CLASS_MANIFEST_ROOT):
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))

    violations = _collect_text_violations(
        plugin_files,
        forbidden_markers=("obj.", "inst."),
    )
    assert violations == [], "Class-level plugins must not mention object or instance identifiers: " f"{violations}"


def test_object_level_plugins_do_not_reference_instance_ids() -> None:
    plugin_files: list[Path] = []
    for manifest_path in _iter_manifests(OBJECT_MANIFEST_ROOT):
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))

    violations = _collect_text_violations(
        plugin_files,
        forbidden_markers=("inst.",),
    )
    assert violations == [], "Object-level plugins must not mention instance identifiers: " f"{violations}"


def test_module_level_plugins_do_not_mutate_sys_path() -> None:
    plugin_files: list[Path] = []
    for manifest_path in _iter_manifests(CLASS_MANIFEST_ROOT):
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))
    for manifest_path in _iter_manifests(OBJECT_MANIFEST_ROOT):
        plugin_files.extend(source.path for source in _iter_plugin_sources(manifest_path))

    violations = _collect_text_violations(plugin_files, forbidden_markers=("sys.path.insert(",))
    assert violations == [], (
        "Class/object plugin modules must not mutate sys.path; import paths are kernel responsibility: " f"{violations}"
    )


def test_class_and_object_non_generator_plugins_are_specific_to_their_scope() -> None:
    class_violations: list[str] = []
    object_violations: list[str] = []

    for manifest_path in _iter_manifests(CLASS_MANIFEST_ROOT):
        for source in _iter_plugin_sources(manifest_path):
            if source.kind == "generator":
                continue
            if not source.path.exists():
                class_violations.append(f"missing plugin source: {source.path}")
                continue
            body = source.path.read_text(encoding="utf-8")
            if "class." not in body:
                rel = source.path.relative_to(V5_ROOT).as_posix()
                class_violations.append(rel)

    for manifest_path in _iter_manifests(OBJECT_MANIFEST_ROOT):
        for source in _iter_plugin_sources(manifest_path):
            if source.kind == "generator":
                continue
            if not source.path.exists():
                object_violations.append(f"missing plugin source: {source.path}")
                continue
            body = source.path.read_text(encoding="utf-8")
            if "obj." not in body:
                rel = source.path.relative_to(V5_ROOT).as_posix()
                object_violations.append(rel)

    assert class_violations == [], (
        "Class-level non-generator plugins without class-specific names should move to core/global level: "
        f"{class_violations}"
    )
    assert object_violations == [], (
        "Object-level non-generator plugins without object-specific names should move to core/global level: "
        f"{object_violations}"
    )


def test_object_modules_do_not_cross_import_other_object_modules() -> None:
    object_ids = {path.name for path in OBJECT_MANIFEST_ROOT.iterdir() if path.is_dir() and path.name != "_shared"}
    violations: list[str] = []

    for file_path in _iter_object_plugin_python_files():
        rel = file_path.relative_to(OBJECT_MANIFEST_ROOT).as_posix()
        owner = rel.split("/", 1)[0]
        if owner == "_shared":
            continue

        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        import_targets: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_targets.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and isinstance(node.module, str):
                import_targets.append(node.module)

        for target in import_targets:
            lowered = target.lower()
            if "object_modules" not in lowered and "object-modules" not in lowered:
                continue
            segments = {token for token in re.split(r"[^a-z0-9_]+", lowered) if token}
            referenced = sorted((segments & object_ids) - {owner})
            if referenced:
                violations.append(f"{rel}: imports {target} -> {referenced}")

    assert violations == [], f"Object modules must not import peer object modules directly: {violations}"


def test_object_plugin_python_files_do_not_hardcode_private_or_local_url_hosts() -> None:
    violations: list[str] = []
    for file_path in _iter_object_plugin_python_files():
        rel = file_path.relative_to(V5_ROOT).as_posix()
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            literal = node.value.strip()
            matched = _find_instance_specific_literal(literal)
            if matched is not None:
                violations.append(f"{rel}: hardcoded instance-specific literal '{matched}'")

    assert violations == [], (
        "Object-level plugin Python files must not hardcode deployment-specific IP/hostname literals: " f"{violations}"
    )


# ADR0078: Product/model names must not be hardcoded in projection logic
_FORBIDDEN_MODEL_PATTERNS = (
    "chateau",
    "hap ac",
    "hex",
    "routerboard",
    "ccr",  # Cloud Core Router
    "crs",  # Cloud Router Switch
)


def test_projection_files_do_not_hardcode_product_model_names() -> None:
    """ADR0078: Projection logic must derive capabilities from object definitions, not model names."""
    violations: list[str] = []
    for file_path in _iter_object_plugin_python_files():
        if "projection" not in file_path.name.lower():
            continue
        rel = file_path.relative_to(V5_ROOT).as_posix()
        body = file_path.read_text(encoding="utf-8").lower()
        for pattern in _FORBIDDEN_MODEL_PATTERNS:
            if pattern in body:
                violations.append(f"{rel}: hardcoded product/model name '{pattern}'")

    assert violations == [], (
        "Projection files must not hardcode product/model names for capability derivation (ADR0078): "
        f"{violations}"
    )

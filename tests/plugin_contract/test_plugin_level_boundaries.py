#!/usr/bin/env python3
"""Contract checks for plugin architecture boundaries and manifest hygiene."""

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
BASE_MANIFEST = V5_ROOT / "topology-tools" / "plugins" / "plugins.yaml"
ALLOWED_STAGES_BY_KIND: dict[str, set[str]] = {
    "discoverer": {"discover"},
    "compiler": {"compile"},
    "validator_yaml": {"validate"},
    "validator_json": {"validate"},
    "generator": {"generate"},
    "assembler": {"assemble"},
    "builder": {"build"},
}
STAGE_ORDER_RANGES: dict[str, tuple[int, int]] = {
    "discover": (10, 89),
    "compile": (30, 89),
    "validate": (90, 189),
    "generate": (190, 399),
    "assemble": (400, 499),
    "build": (500, 599),
}
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


def _iter_all_manifests() -> list[Path]:
    manifests: list[Path] = []
    if BASE_MANIFEST.exists():
        manifests.append(BASE_MANIFEST)
    manifests.extend(_iter_manifests(CLASS_MANIFEST_ROOT))
    manifests.extend(_iter_manifests(OBJECT_MANIFEST_ROOT))
    return manifests


def _load_manifest_plugins(manifest_path: Path) -> list[dict[str, object]]:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    plugins = payload.get("plugins", [])
    if not isinstance(plugins, list):
        return []
    return [item for item in plugins if isinstance(item, dict)]


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


def test_manifest_plugins_respect_kind_stage_affinity() -> None:
    violations: list[str] = []
    for manifest_path in _iter_all_manifests():
        rel = manifest_path.relative_to(V5_ROOT).as_posix()
        for row in _load_manifest_plugins(manifest_path):
            plugin_id = row.get("id")
            kind = row.get("kind")
            stages = row.get("stages")
            if not isinstance(plugin_id, str) or not isinstance(kind, str) or not isinstance(stages, list):
                continue
            allowed = ALLOWED_STAGES_BY_KIND.get(kind)
            if allowed is None:
                continue
            for stage in stages:
                if isinstance(stage, str) and stage in allowed:
                    continue
                violations.append(
                    f"{rel}:{plugin_id} kind '{kind}' cannot run in stage '{stage}' (allowed={sorted(allowed)})"
                )

    assert violations == [], f"Manifest kind/stage affinity violations: {violations}"


def test_manifest_plugins_respect_stage_order_ranges() -> None:
    violations: list[str] = []
    for manifest_path in _iter_all_manifests():
        rel = manifest_path.relative_to(V5_ROOT).as_posix()
        for row in _load_manifest_plugins(manifest_path):
            plugin_id = row.get("id")
            stages = row.get("stages")
            order = row.get("order")
            if not isinstance(plugin_id, str) or not isinstance(stages, list) or not isinstance(order, int):
                continue
            for stage in stages:
                if not isinstance(stage, str):
                    continue
                order_range = STAGE_ORDER_RANGES.get(stage)
                if order_range is None:
                    continue
                min_order, max_order = order_range
                if min_order <= order <= max_order:
                    continue
                violations.append(
                    f"{rel}:{plugin_id} order {order} outside {min_order}-{max_order} for stage '{stage}'"
                )

    assert violations == [], f"Manifest stage-order violations: {violations}"


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


def test_manifest_dependencies_reference_existing_plugins() -> None:
    known_ids: set[str] = set()
    manifest_rows: list[tuple[str, dict[str, object]]] = []

    for manifest_path in _iter_all_manifests():
        rel = manifest_path.relative_to(V5_ROOT).as_posix()
        for row in _load_manifest_plugins(manifest_path):
            plugin_id = row.get("id")
            if not isinstance(plugin_id, str) or not plugin_id:
                continue
            known_ids.add(plugin_id)
            manifest_rows.append((rel, row))

    violations: list[str] = []
    for rel, row in manifest_rows:
        plugin_id = row.get("id")
        depends_on = row.get("depends_on", [])
        if not isinstance(plugin_id, str) or not isinstance(depends_on, list):
            continue
        for dep in depends_on:
            if isinstance(dep, str) and dep in known_ids:
                continue
            violations.append(f"{rel}:{plugin_id} missing dependency '{dep}'")

    assert violations == [], f"Manifest dependency reference violations: {violations}"


def test_object_modules_do_not_cross_import_other_object_modules() -> None:
    object_ids = {path.name for path in OBJECT_MANIFEST_ROOT.iterdir() if path.is_dir()}
    violations: list[str] = []

    for file_path in _iter_object_plugin_python_files():
        rel = file_path.relative_to(OBJECT_MANIFEST_ROOT).as_posix()
        owner = rel.split("/", 1)[0]

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
        "Projection files must not hardcode product/model names for capability derivation (ADR0078): " f"{violations}"
    )

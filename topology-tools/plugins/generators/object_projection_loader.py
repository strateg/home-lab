#!/usr/bin/env python3
"""Lazy loader for object-module projection helpers (ADR0078 Wave 5)."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kernel.plugin_base import PluginContext


def _load_module(*, module_name: str, module_path: Path) -> ModuleType:
    if not module_path.exists():
        raise FileNotFoundError(f"Projection module not found: {module_path}")

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load projection module spec: {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _detect_object_modules_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "topology" / "object-modules"
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("Cannot auto-detect topology/object-modules root for projection loader.")


def _resolve_object_modules_root(
    *,
    ctx: PluginContext | None = None,
    object_modules_root: Path | str | None = None,
) -> Path:
    if isinstance(object_modules_root, Path):
        return object_modules_root.resolve()
    if isinstance(object_modules_root, str) and object_modules_root.strip():
        return Path(object_modules_root.strip()).resolve()
    if ctx is not None:
        raw = ctx.config.get("object_modules_root")
        if isinstance(raw, str) and raw.strip():
            return Path(raw.strip()).resolve()
    return _detect_object_modules_root()


def _resolve_framework_generators_root(
    *,
    framework_generators_root: Path | str | None = None,
) -> Path:
    if isinstance(framework_generators_root, Path):
        return framework_generators_root.resolve()
    if isinstance(framework_generators_root, str) and framework_generators_root.strip():
        return Path(framework_generators_root.strip()).resolve()
    return Path(__file__).resolve().parent


@lru_cache(maxsize=8)
def _discover_object_projection_paths(root: str) -> dict[str, Path]:
    object_modules_root = Path(root)
    paths: dict[str, Path] = {}
    if not object_modules_root.exists():
        return paths
    for object_dir in sorted(object_modules_root.iterdir(), key=lambda entry: entry.name):
        if not object_dir.is_dir():
            continue
        if object_dir.name.startswith("_"):
            continue
        candidate = object_dir / "plugins" / "projections.py"
        if candidate.exists():
            paths[object_dir.name] = candidate
    return paths


def discover_object_projection_paths(
    *,
    ctx: PluginContext | None = None,
    object_modules_root: Path | str | None = None,
) -> dict[str, Path]:
    root = _resolve_object_modules_root(ctx=ctx, object_modules_root=object_modules_root)
    return _discover_object_projection_paths(str(root))


@lru_cache(maxsize=64)
def _load_object_projection_module(root: str, object_id: str) -> ModuleType:
    paths = _discover_object_projection_paths(root)
    module_path = paths.get(object_id)
    if module_path is None:
        known = ", ".join(sorted(paths))
        raise ValueError(f"Unknown object projection module '{object_id}'. Known: {known}")
    return _load_module(module_name=f"_object_projection_{object_id}", module_path=module_path)


def load_object_projection_module(
    object_id: str,
    *,
    ctx: PluginContext | None = None,
    object_modules_root: Path | str | None = None,
) -> ModuleType:
    root = _resolve_object_modules_root(ctx=ctx, object_modules_root=object_modules_root)
    return _load_object_projection_module(str(root), object_id)


@lru_cache(maxsize=8)
def _load_bootstrap_projection_module(framework_generators_root: str) -> ModuleType:
    module_path = Path(framework_generators_root) / "bootstrap_projections.py"
    return _load_module(module_name="_object_projection_bootstrap", module_path=module_path)


def load_bootstrap_projection_module(
    *,
    ctx: PluginContext | None = None,
    framework_generators_root: Path | str | None = None,
    object_modules_root: Path | str | None = None,
) -> ModuleType:
    del ctx, object_modules_root  # Backward-compatible signature: shared bootstrap projection is framework-owned.
    root = _resolve_framework_generators_root(framework_generators_root=framework_generators_root)
    return _load_bootstrap_projection_module(str(root))

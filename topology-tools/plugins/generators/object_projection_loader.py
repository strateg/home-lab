#!/usr/bin/env python3
"""Lazy loader for object-module projection helpers (ADR0078 Wave 5)."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType

V5_ROOT = Path(__file__).resolve().parents[3]
OBJECT_MODULES_ROOT = V5_ROOT / "topology" / "object-modules"
BOOTSTRAP_PROJECTION_PATH = OBJECT_MODULES_ROOT / "_shared" / "plugins" / "bootstrap_projections.py"


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


def discover_object_projection_paths(*, object_modules_root: Path = OBJECT_MODULES_ROOT) -> dict[str, Path]:
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


@lru_cache(maxsize=1)
def _object_projection_paths() -> dict[str, Path]:
    return discover_object_projection_paths()


@lru_cache(maxsize=None)
def load_object_projection_module(object_id: str) -> ModuleType:
    paths = _object_projection_paths()
    module_path = paths.get(object_id)
    if module_path is None:
        known = ", ".join(sorted(paths))
        raise ValueError(f"Unknown object projection module '{object_id}'. Known: {known}")
    return _load_module(module_name=f"_object_projection_{object_id}", module_path=module_path)


@lru_cache(maxsize=1)
def load_bootstrap_projection_module() -> ModuleType:
    return _load_module(module_name="_object_projection_bootstrap", module_path=BOOTSTRAP_PROJECTION_PATH)

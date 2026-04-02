#!/usr/bin/env python3
"""Lazy loader for shared generator helpers.

Framework-owned shared helpers are resolved from `topology-tools/plugins/generators`.
Class helper loading continues to resolve from `class_modules_root`.
"""

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
    """Load a Python module from a file path."""
    if not module_path.exists():
        raise FileNotFoundError(f"Helper module not found: {module_path}")

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load helper module spec: {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _detect_topology_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "topology"
        if (candidate / "object-modules").exists() and (candidate / "class-modules").exists():
            return candidate
    raise FileNotFoundError("Cannot auto-detect topology root for shared helper loader.")


def _root_from_ctx(*, ctx: PluginContext | None, key: str) -> Path | None:
    if ctx is None:
        return None
    raw = ctx.config.get(key)
    if isinstance(raw, str) and raw.strip():
        return Path(raw.strip()).resolve()
    return None


def _resolve_class_modules_root(
    *,
    ctx: PluginContext | None = None,
    class_modules_root: Path | str | None = None,
) -> Path:
    if isinstance(class_modules_root, Path):
        return class_modules_root.resolve()
    if isinstance(class_modules_root, str) and class_modules_root.strip():
        return Path(class_modules_root.strip()).resolve()
    from_ctx = _root_from_ctx(ctx=ctx, key="class_modules_root")
    if from_ctx is not None:
        return from_ctx
    return (_detect_topology_root() / "class-modules").resolve()


def _resolve_framework_generators_root(
    *,
    framework_generators_root: Path | str | None = None,
) -> Path:
    if isinstance(framework_generators_root, Path):
        return framework_generators_root.resolve()
    if isinstance(framework_generators_root, str) and framework_generators_root.strip():
        return Path(framework_generators_root.strip()).resolve()
    return Path(__file__).resolve().parent


# =============================================================================
# Shared framework generator helpers (topology-tools/plugins/generators/)
# =============================================================================


@lru_cache(maxsize=8)
def _load_terraform_helpers(framework_generators_root: str) -> ModuleType:
    return _load_module(
        module_name="_framework_terraform_helpers",
        module_path=Path(framework_generators_root) / "terraform_helpers.py",
    )


def load_terraform_helpers(
    *,
    ctx: PluginContext | None = None,
    framework_generators_root: Path | str | None = None,
    object_modules_root: Path | str | None = None,
) -> ModuleType:
    del ctx, object_modules_root  # Backward-compatible signature: shared helpers are framework-owned.
    root = _resolve_framework_generators_root(framework_generators_root=framework_generators_root)
    return _load_terraform_helpers(str(root))


@lru_cache(maxsize=8)
def _load_capability_helpers(framework_generators_root: str) -> ModuleType:
    return _load_module(
        module_name="_framework_capability_helpers",
        module_path=Path(framework_generators_root) / "capability_helpers.py",
    )


def load_capability_helpers(
    *,
    ctx: PluginContext | None = None,
    framework_generators_root: Path | str | None = None,
    object_modules_root: Path | str | None = None,
) -> ModuleType:
    del ctx, object_modules_root  # Backward-compatible signature: shared helpers are framework-owned.
    root = _resolve_framework_generators_root(framework_generators_root=framework_generators_root)
    return _load_capability_helpers(str(root))


@lru_cache(maxsize=8)
def _load_bootstrap_helpers(framework_generators_root: str) -> ModuleType:
    return _load_module(
        module_name="_framework_bootstrap_helpers",
        module_path=Path(framework_generators_root) / "bootstrap_helpers.py",
    )


def load_bootstrap_helpers(
    *,
    ctx: PluginContext | None = None,
    framework_generators_root: Path | str | None = None,
    object_modules_root: Path | str | None = None,
) -> ModuleType:
    del ctx, object_modules_root  # Backward-compatible signature: shared helpers are framework-owned.
    root = _resolve_framework_generators_root(framework_generators_root=framework_generators_root)
    return _load_bootstrap_helpers(str(root))


# =============================================================================
# Class-module helpers (class-modules/*/plugins/)
# =============================================================================


@lru_cache(maxsize=32)
def _load_class_plugin_module_cached(*, class_modules_root: str, class_id: str, module_name: str) -> ModuleType:
    module_path = Path(class_modules_root) / class_id / "plugins" / f"{module_name}.py"
    return _load_module(
        module_name=f"_class_{class_id}_{module_name}",
        module_path=module_path,
    )


def load_class_plugin_module(
    class_id: str,
    module_name: str,
    *,
    ctx: PluginContext | None = None,
    class_modules_root: Path | str | None = None,
) -> ModuleType:
    """Load a plugin module from a class-module."""
    root = _resolve_class_modules_root(ctx=ctx, class_modules_root=class_modules_root)
    return _load_class_plugin_module_cached(
        class_modules_root=str(root.resolve()),
        class_id=class_id,
        module_name=module_name,
    )


def load_router_port_validator_base(
    *,
    ctx: PluginContext | None = None,
    class_modules_root: Path | str | None = None,
) -> ModuleType:
    """Load RouterPortValidatorBase from class-modules/router/plugins/."""
    return load_class_plugin_module(
        "router",
        "router_port_validator_base",
        ctx=ctx,
        class_modules_root=class_modules_root,
    )

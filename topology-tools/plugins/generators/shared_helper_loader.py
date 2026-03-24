#!/usr/bin/env python3
"""Lazy loader for shared plugin helpers (ADR0078 Phase 5).

Provides dynamic loading for shared helpers that live in:
- object-modules/_shared/plugins/ (terraform, capability, bootstrap helpers)
- class-modules/*/plugins/ (validator base classes)

This avoids Python import issues with hyphenated directory names.
"""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType

V5_ROOT = Path(__file__).resolve().parents[3]
OBJECT_MODULES_ROOT = V5_ROOT / "topology" / "object-modules"
CLASS_MODULES_ROOT = V5_ROOT / "topology" / "class-modules"
SHARED_PLUGINS_ROOT = OBJECT_MODULES_ROOT / "_shared" / "plugins"


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


# =============================================================================
# Shared object-module helpers (_shared/plugins/)
# =============================================================================


@lru_cache(maxsize=1)
def load_terraform_helpers() -> ModuleType:
    """Load terraform_helpers.py from _shared/plugins/."""
    return _load_module(
        module_name="_shared_terraform_helpers",
        module_path=SHARED_PLUGINS_ROOT / "terraform_helpers.py",
    )


@lru_cache(maxsize=1)
def load_capability_helpers() -> ModuleType:
    """Load capability_helpers.py from _shared/plugins/."""
    return _load_module(
        module_name="_shared_capability_helpers",
        module_path=SHARED_PLUGINS_ROOT / "capability_helpers.py",
    )


@lru_cache(maxsize=1)
def load_bootstrap_helpers() -> ModuleType:
    """Load bootstrap_helpers.py from _shared/plugins/."""
    return _load_module(
        module_name="_shared_bootstrap_helpers",
        module_path=SHARED_PLUGINS_ROOT / "bootstrap_helpers.py",
    )


# =============================================================================
# Class-module helpers (class-modules/*/plugins/)
# =============================================================================


@lru_cache(maxsize=None)
def load_class_plugin_module(class_id: str, module_name: str) -> ModuleType:
    """Load a plugin module from a class-module.

    Args:
        class_id: Class module directory name (e.g., "router")
        module_name: Python file name without .py (e.g., "router_port_validator_base")

    Returns:
        Loaded module
    """
    module_path = CLASS_MODULES_ROOT / class_id / "plugins" / f"{module_name}.py"
    return _load_module(
        module_name=f"_class_{class_id}_{module_name}",
        module_path=module_path,
    )


@lru_cache(maxsize=1)
def load_router_port_validator_base() -> ModuleType:
    """Load RouterPortValidatorBase from class-modules/router/plugins/."""
    return load_class_plugin_module("router", "router_port_validator_base")

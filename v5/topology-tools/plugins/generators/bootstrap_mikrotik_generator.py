"""Compatibility shim for MikroTik bootstrap generator location."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_generator_class():
    impl_path = (
        Path(__file__).resolve().parents[3]
        / "topology"
        / "object-modules"
        / "mikrotik"
        / "plugins"
        / "bootstrap_mikrotik_generator.py"
    )
    spec = importlib.util.spec_from_file_location("v5_object_mikrotik_bootstrap_generator", impl_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load generator implementation from {impl_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generator_class = getattr(module, "BootstrapMikroTikGenerator", None)
    if generator_class is None:
        raise ImportError(f"Class BootstrapMikroTikGenerator not found in {impl_path}")
    return generator_class


BootstrapMikroTikGenerator = _load_generator_class()

__all__ = ["BootstrapMikroTikGenerator"]

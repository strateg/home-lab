"""Compatibility shim for Proxmox Terraform generator location."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_generator_class():
    impl_path = (
        Path(__file__).resolve().parents[3]
        / "topology"
        / "object-modules"
        / "proxmox"
        / "plugins"
        / "terraform_proxmox_generator.py"
    )
    spec = importlib.util.spec_from_file_location("v5_object_proxmox_terraform_generator", impl_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load generator implementation from {impl_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generator_class = getattr(module, "TerraformProxmoxGenerator", None)
    if generator_class is None:
        raise ImportError(f"Class TerraformProxmoxGenerator not found in {impl_path}")
    return generator_class


TerraformProxmoxGenerator = _load_generator_class()

__all__ = ["TerraformProxmoxGenerator"]

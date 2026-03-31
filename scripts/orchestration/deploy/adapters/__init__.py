"""ADR 0083 scaffold: adapter factory."""

from __future__ import annotations

from .ansible_bootstrap import AnsibleBootstrapAdapter
from .base import (
    AdapterContext,
    AdapterStatus,
    BootstrapAdapter,
    BootstrapResult,
    HandoverCheckResult,
    NotImplementedBootstrapAdapter,
    PreflightCheck,
)
from .cloud_init import CloudInitAdapter
from .netinstall import NetinstallAdapter
from .unattended import UnattendedInstallAdapter

SUPPORTED_MECHANISMS = {
    "netinstall",
    "unattended_install",
    "cloud_init",
    "ansible_bootstrap",
}


def get_adapter(mechanism: str) -> BootstrapAdapter:
    key = mechanism.strip().lower()
    if key not in SUPPORTED_MECHANISMS:
        supported = ", ".join(sorted(SUPPORTED_MECHANISMS))
        raise ValueError(f"Unknown initialization mechanism: {mechanism}. Supported: {supported}")
    factories: dict[str, type[BootstrapAdapter]] = {
        "netinstall": NetinstallAdapter,
        "unattended_install": UnattendedInstallAdapter,
        "cloud_init": CloudInitAdapter,
        "ansible_bootstrap": AnsibleBootstrapAdapter,
    }
    factory = factories.get(key)
    if not factory:
        return NotImplementedBootstrapAdapter(key)
    return factory()


__all__ = [
    "AdapterContext",
    "AdapterStatus",
    "BootstrapAdapter",
    "BootstrapResult",
    "HandoverCheckResult",
    "AnsibleBootstrapAdapter",
    "CloudInitAdapter",
    "NetinstallAdapter",
    "NotImplementedBootstrapAdapter",
    "PreflightCheck",
    "SUPPORTED_MECHANISMS",
    "UnattendedInstallAdapter",
    "get_adapter",
]

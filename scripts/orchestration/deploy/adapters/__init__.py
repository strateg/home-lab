"""ADR 0083 scaffold: adapter factory."""

from __future__ import annotations

from .base import (
    AdapterContext,
    AdapterStatus,
    BootstrapAdapter,
    BootstrapResult,
    HandoverCheckResult,
    NotImplementedBootstrapAdapter,
    PreflightCheck,
)

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
    return NotImplementedBootstrapAdapter(key)


__all__ = [
    "AdapterContext",
    "AdapterStatus",
    "BootstrapAdapter",
    "BootstrapResult",
    "HandoverCheckResult",
    "NotImplementedBootstrapAdapter",
    "PreflightCheck",
    "SUPPORTED_MECHANISMS",
    "get_adapter",
]

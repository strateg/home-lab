"""
ADR 0083 scaffold: bootstrap adapter contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AdapterStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    ok: bool
    details: str = ""
    remediation_hint: str = ""


@dataclass(frozen=True)
class HandoverCheckResult:
    name: str
    ok: bool
    details: str = ""
    attempt: int = 1
    total_attempts: int = 1
    error_code: str = ""


@dataclass(frozen=True)
class BootstrapResult:
    status: AdapterStatus
    message: str = ""
    error_code: str = ""
    preflight_checks: list[PreflightCheck] = field(default_factory=list)
    handover_checks: list[HandoverCheckResult] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status == AdapterStatus.SUCCESS


@dataclass(frozen=True)
class AdapterContext:
    project_id: str
    bundle_path: Path
    workspace_ref: str


class BootstrapAdapter(ABC):
    """Common lifecycle contract for initialization mechanism adapters."""

    @property
    @abstractmethod
    def mechanism(self) -> str:
        pass

    @abstractmethod
    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        pass

    @abstractmethod
    def execute(self, node: dict[str, Any], context: AdapterContext) -> BootstrapResult:
        pass

    @abstractmethod
    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        pass

    def cleanup(self, node: dict[str, Any], context: AdapterContext) -> None:
        return None

    def validate_template(self, node: dict[str, Any], context: AdapterContext) -> bool:
        return True


class NotImplementedBootstrapAdapter(BootstrapAdapter):
    """Fallback adapter placeholder for recognized mechanisms not wired yet."""

    def __init__(self, mechanism: str):
        self._mechanism = mechanism

    @property
    def mechanism(self) -> str:
        return self._mechanism

    def preflight(self, node: dict[str, Any], context: AdapterContext) -> list[PreflightCheck]:
        return [
            PreflightCheck(
                name="adapter_implemented",
                ok=False,
                details=f"Adapter '{self.mechanism}' is not implemented yet.",
                remediation_hint="Implement mechanism adapter before non-plan init-node execution.",
            )
        ]

    def execute(self, node: dict[str, Any], context: AdapterContext) -> BootstrapResult:
        return BootstrapResult(
            status=AdapterStatus.FAILED,
            message=f"Adapter '{self.mechanism}' is not implemented.",
            error_code="E9730",
        )

    def handover(self, node: dict[str, Any], context: AdapterContext) -> list[HandoverCheckResult]:
        return []

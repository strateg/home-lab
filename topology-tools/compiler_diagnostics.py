"""Compiler diagnostic model and plugin diagnostic projection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel import PluginDiagnostic


@dataclass
class CompilerDiagnostic:
    """Diagnostic shape emitted by the compiler report writer.

    This model intentionally preserves the legacy compiler report payload:
    plugin diagnostics are projected into the compiler report fields consumed
    by diagnostics JSON/TXT downstream tooling.
    """

    code: str
    severity: str
    stage: str
    message: str
    path: str
    confidence: float = 0.95
    hint: str | None = None
    plugin_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "path": self.path,
            "confidence": self.confidence,
            "autofix": {"possible": False},
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.plugin_id:
            payload["plugin_id"] = self.plugin_id
        return payload

    @classmethod
    def from_plugin_diagnostic(cls, plugin_diag: PluginDiagnostic) -> "CompilerDiagnostic":
        """Convert a plugin diagnostic to the compiler report diagnostic shape."""
        return cls(
            code=plugin_diag.code,
            severity=plugin_diag.severity,
            stage=plugin_diag.stage,
            message=plugin_diag.message,
            path=plugin_diag.path,
            confidence=plugin_diag.confidence,
            hint=plugin_diag.hint,
            plugin_id=plugin_diag.plugin_id,
        )


# Backward-compatible name used by compile-topology imports and tests.
Diagnostic = CompilerDiagnostic

__all__ = ["CompilerDiagnostic", "Diagnostic"]

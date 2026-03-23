"""Base validator for router ethernet port inventory (ADR0078 WP-004).

This module provides shared validation logic for ethernet port inventory
across all router-class object modules. Object-level validators inherit
from this base and provide only the object-specific prefix and diagnostic code.
"""

from __future__ import annotations

from abc import abstractmethod

from kernel.plugin_base import PluginContext, PluginDiagnostic, PluginResult, Stage, ValidatorJsonPlugin


class RouterPortValidatorBase(ValidatorJsonPlugin):
    """Base class for router ethernet port validators.

    Subclasses must implement:
      - object_prefix: str property returning the object ID prefix (e.g., "obj.mikrotik.")
      - diagnostic_code: str property returning the error code (e.g., "E7302")
    """

    @property
    @abstractmethod
    def object_prefix(self) -> str:
        """Return the object ID prefix to filter (e.g., 'obj.mikrotik.')."""
        ...

    @property
    @abstractmethod
    def diagnostic_code(self) -> str:
        """Return the diagnostic code for errors (e.g., 'E7302')."""
        ...

    def execute(self, ctx: PluginContext, stage: Stage) -> PluginResult:
        diagnostics: list[PluginDiagnostic] = []
        prefix = self.object_prefix
        code = self.diagnostic_code

        for object_id, payload in ctx.objects.items():
            if not (isinstance(object_id, str) and object_id.startswith(prefix)):
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("class_ref") != "class.router":
                continue

            hardware_specs = payload.get("hardware_specs")
            if not isinstance(hardware_specs, dict):
                # Virtual router objects (e.g., CHR) may not expose hardware sections.
                continue
            interfaces = hardware_specs.get("interfaces")
            if not isinstance(interfaces, dict):
                continue
            ethernet = interfaces.get("ethernet")
            if ethernet is None:
                continue
            if not isinstance(ethernet, list):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message="hardware_specs.interfaces.ethernet must be a list when provided.",
                        path=f"object:{object_id}:hardware_specs.interfaces.ethernet",
                    )
                )
                continue

            self._validate_ports(diagnostics, object_id, ethernet, stage, code)

        return self.make_result(diagnostics)

    def _validate_ports(
        self,
        diagnostics: list[PluginDiagnostic],
        object_id: str,
        ethernet: list,
        stage: Stage,
        code: str,
    ) -> None:
        """Validate individual port entries in the ethernet list."""
        seen: set[str] = set()
        for index, port in enumerate(ethernet):
            if not isinstance(port, dict):
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message="Ethernet port entries must be objects.",
                        path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}]",
                    )
                )
                continue
            name = port.get("name")
            if not isinstance(name, str) or not name:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message="Ethernet port entry must define non-empty 'name'.",
                        path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}].name",
                    )
                )
                continue
            if name in seen:
                diagnostics.append(
                    self.emit_diagnostic(
                        code=code,
                        severity="error",
                        stage=stage,
                        message=f"Duplicate ethernet port name '{name}'.",
                        path=f"object:{object_id}:hardware_specs.interfaces.ethernet[{index}].name",
                    )
                )
            seen.add(name)

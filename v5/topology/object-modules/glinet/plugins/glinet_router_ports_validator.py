"""Module-level validator for GL.iNet router ethernet port inventory."""

from __future__ import annotations

# ADR0078 WP-004: Inherit common logic from class-level base
from topology.class_modules.router.plugins.router_port_validator_base import RouterPortValidatorBase


class GlinetRouterPortsValidator(RouterPortValidatorBase):
    """Validate ethernet list shape for router-class GL.iNet objects."""

    @property
    def object_prefix(self) -> str:
        return "obj.glinet."

    @property
    def diagnostic_code(self) -> str:
        return "E7303"

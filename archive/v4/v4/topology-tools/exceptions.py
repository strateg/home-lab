"""Custom exceptions for topology validation and generation."""

from typing import Any, Dict, Optional


class TopologyError(Exception):
    """Base exception for topology operations."""

    def __init__(
        self,
        message: str,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
    ):
        self.message = message
        self.code = code
        self.context = context or {}
        self.suggestion = suggestion
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = f"[{self.code}] {self.message}"
        if self.context:
            msg += f"\nContext: {self.context}"
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class ValidationError(TopologyError):
    """Topology validation failed."""

    pass


class SchemaError(ValidationError):
    """JSON Schema validation failed."""

    pass


class StorageError(ValidationError):
    """L1/L3 storage validation failed."""

    pass


class NetworkError(ValidationError):
    """L2 network validation failed."""

    pass


class ReferenceError(ValidationError):
    """Cross-layer reference validation failed."""

    pass


class GovernanceError(ValidationError):
    """L0 governance/metadata validation failed."""

    pass


class FoundationError(ValidationError):
    """L1 foundation validation failed."""

    pass


class GenerationError(TopologyError):
    """Code generation failed."""

    pass


class TerraformGenerationError(GenerationError):
    """Terraform code generation failed."""

    pass


class AnsibleGenerationError(GenerationError):
    """Ansible inventory generation failed."""

    pass


class DocumentationGenerationError(GenerationError):
    """Documentation generation failed."""

    pass


class IpResolutionError(GenerationError):
    """IP reference resolution failed (ADR-0044)."""

    pass

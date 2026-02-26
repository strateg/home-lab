"""Documentation generation package."""

from .cli import DocumentationCLI, main
from .diagrams import DiagramDocumentationGenerator
from .generator import DocumentationGenerator

__all__ = [
    "DiagramDocumentationGenerator",
    "DocumentationCLI",
    "DocumentationGenerator",
    "main",
]

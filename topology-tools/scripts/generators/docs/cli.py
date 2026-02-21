"""CLI entrypoint for topology documentation generation."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from scripts.generators.common import GeneratorCLI, Generator, run_cli
from .generator import DocumentationGenerator


class DocumentationCLI(GeneratorCLI):
    """CLI for documentation generator with Mermaid icon support."""

    description = "Generate documentation from topology v4.0"
    banner = "Documentation Generator (Topology v4.0)"
    default_output = "generated/docs"
    success_message = "Documentation generation completed successfully!"

    def add_extra_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Mermaid icon-related arguments."""
        parser.add_argument(
            "--mermaid-icons",
            action="store_true",
            dest="mermaid_icons",
            help="Enable Mermaid icon-node syntax (requires Mermaid renderer with icon-node support)",
        )
        parser.add_argument(
            "--no-mermaid-icons",
            action="store_false",
            dest="mermaid_icons",
            help="Disable Mermaid icon-node syntax and use plain Mermaid nodes",
        )
        parser.add_argument(
            "--mermaid-icon-nodes",
            action="store_true",
            dest="mermaid_icon_nodes",
            help="Emit raw Mermaid `@{ icon: ... }` node syntax (default; requires Mermaid with icon-node support)",
        )
        parser.add_argument(
            "--mermaid-icon-compat",
            action="store_false",
            dest="mermaid_icon_nodes",
            help="Use compatibility icon rendering: convert icon-nodes into standard nodes with inline icons",
        )
        parser.set_defaults(mermaid_icons=True, mermaid_icon_nodes=True)

    def create_generator(self, args: argparse.Namespace) -> Generator:
        """Create DocumentationGenerator with Mermaid options."""
        return DocumentationGenerator(
            args.topology,
            args.output,
            args.templates,
            mermaid_icons=args.mermaid_icons,
            mermaid_icon_nodes=args.mermaid_icon_nodes,
        )


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser (for backwards compatibility)."""
    return DocumentationCLI(DocumentationGenerator).build_parser()


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""
    return run_cli(DocumentationCLI(DocumentationGenerator), argv)


if __name__ == "__main__":
    sys.exit(main())

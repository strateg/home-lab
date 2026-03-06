"""CLI entrypoint for topology documentation generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

# Handle both direct script execution and module import
if __name__ == "__main__" and __package__ is None:
    # Add project root to path when running as script
    project_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(project_root))

from scripts.generators.common import Generator, GeneratorCLI, run_cli
from scripts.generators.docs.generator import DocumentationGenerator


class DocumentationCLI(GeneratorCLI):
    """CLI for documentation generator with Mermaid icon support."""

    description = "Generate documentation from topology v4.0"
    banner = "Documentation Generator (Topology v4.0)"
    default_output = "v4-generated/docs"
    success_message = "Documentation generation completed successfully!"

    def add_extra_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add documentation generator specific arguments."""
        # Version
        parser.add_argument(
            "--version",
            action="version",
            version="%(prog)s 4.0.0 (Topology Documentation Generator)",
        )

        # Output control
        parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Minimal output (only errors), useful for CI/CD",
        )

        # Component selection
        parser.add_argument(
            "--components",
            type=str,
            help="Generate only specific components (comma-separated): core,diagrams,phase1,phase2,phase3",
        )

        # Mermaid icon options
        parser.add_argument(
            "--mermaid-icons",
            action="store_true",
            dest="mermaid_icons",
            help="Enable Mermaid icon rendering",
        )
        parser.add_argument(
            "--no-mermaid-icons",
            action="store_false",
            dest="mermaid_icons",
            help="Disable Mermaid icon-node syntax and use plain Mermaid nodes (default)",
        )
        parser.add_argument(
            "--mermaid-icon-nodes",
            action="store_true",
            dest="mermaid_icon_nodes",
            help="Emit raw Mermaid `@{ icon: ... }` node syntax (requires Mermaid renderer with icon-node support)",
        )
        parser.add_argument(
            "--mermaid-icon-compat",
            action="store_false",
            dest="mermaid_icon_nodes",
            help="Use compatibility icon rendering: convert icon-nodes into standard nodes with inline icons (default)",
        )
        parser.set_defaults(mermaid_icons=True, mermaid_icon_nodes=False)

    def create_generator(self, args: argparse.Namespace) -> Generator:
        """Create DocumentationGenerator with Mermaid options and validate inputs."""
        # Validate topology file exists
        topology_path = Path(args.topology)
        if not topology_path.exists():
            print(f"ERROR: Topology file not found: {topology_path}")
            print(f"       Please check the path and try again.")
            sys.exit(1)

        if not topology_path.is_file():
            print(f"ERROR: Topology path is not a file: {topology_path}")
            sys.exit(1)

        # Validate topology file is readable
        try:
            with open(topology_path, "r", encoding="utf-8") as f:
                f.read(1)  # Try to read first byte
        except PermissionError:
            print(f"ERROR: Permission denied reading topology file: {topology_path}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Cannot read topology file: {topology_path}")
            print(f"       {type(e).__name__}: {e}")
            sys.exit(1)

        # Parse component selection
        selected_components = None
        if hasattr(args, "components") and args.components:
            selected_components = [c.strip() for c in args.components.split(",")]
            valid_components = {"core", "diagrams", "phase1", "phase2", "phase3", "all"}
            invalid = set(selected_components) - valid_components
            if invalid:
                print(f"ERROR: Invalid components: {', '.join(invalid)}")
                print(f"       Valid options: {', '.join(sorted(valid_components))}")
                sys.exit(1)

        generator = DocumentationGenerator(
            args.topology,
            args.output,
            args.templates,
            mermaid_icons=args.mermaid_icons,
            mermaid_icon_nodes=args.mermaid_icon_nodes,
        )

        # Set flags on generator
        if hasattr(args, "dry_run"):
            generator.dry_run = args.dry_run
        if hasattr(args, "quiet"):
            generator.quiet = args.quiet
        if selected_components:
            generator.selected_components = selected_components

        return generator


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser (for backwards compatibility)."""
    return DocumentationCLI(DocumentationGenerator).build_parser()


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point."""
    return run_cli(DocumentationCLI(DocumentationGenerator), argv)


if __name__ == "__main__":
    sys.exit(main())

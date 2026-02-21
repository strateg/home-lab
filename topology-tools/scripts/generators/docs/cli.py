"""CLI entrypoint for topology documentation generation."""

from __future__ import annotations

import argparse
import sys

from .generator import DocumentationGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate documentation from topology v4.0"
    )
    parser.add_argument(
        "--topology",
        default="topology.yaml",
        help="Path to topology YAML file"
    )
    parser.add_argument(
        "--output",
        default="generated/docs",
        help="Output directory for documentation (default: generated/docs/)"
    )
    parser.add_argument(
        "--templates",
        default="topology-tools/templates",
        help="Directory containing Jinja2 templates"
    )
    parser.add_argument(
        "--mermaid-icons",
        action="store_true",
        dest="mermaid_icons",
        help="Enable Mermaid icon-node syntax (requires Mermaid renderer with icon-node support)"
    )
    parser.add_argument(
        "--no-mermaid-icons",
        action="store_false",
        dest="mermaid_icons",
        help="Disable Mermaid icon-node syntax and use plain Mermaid nodes"
    )
    parser.add_argument(
        "--mermaid-icon-nodes",
        action="store_true",
        dest="mermaid_icon_nodes",
        help="Emit raw Mermaid `@{ icon: ... }` node syntax (default; requires Mermaid with icon-node support)"
    )
    parser.add_argument(
        "--mermaid-icon-compat",
        action="store_false",
        dest="mermaid_icon_nodes",
        help="Use compatibility icon rendering: convert icon-nodes into standard nodes with inline icons"
    )
    parser.set_defaults(mermaid_icons=True, mermaid_icon_nodes=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    generator = DocumentationGenerator(
        args.topology,
        args.output,
        args.templates,
        mermaid_icons=args.mermaid_icons,
        mermaid_icon_nodes=args.mermaid_icon_nodes,
    )

    print("=" * 70)
    print("Documentation Generator (Topology v4.0)")
    print("=" * 70)
    print()

    if not generator.load_topology():
        return 1

    print("\nGEN Generating documentation...\n")

    if not generator.generate_all():
        print("\nERROR Generation failed with errors")
        return 1

    generator.print_summary()
    print("\nOK Documentation generation completed successfully!\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

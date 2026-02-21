"""Base classes and protocols for topology generators."""

from __future__ import annotations

import argparse
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Protocol, Sequence, runtime_checkable

if TYPE_CHECKING:
    from typing import Callable, TypeVar

    GeneratorT = TypeVar("GeneratorT", bound="Generator")


@runtime_checkable
class Generator(Protocol):
    """Protocol defining the interface for all topology generators.

    All generators must implement these methods to ensure consistent
    behavior across the generation pipeline.
    """

    topology_path: Path
    output_dir: Path
    topology: Dict[str, Any]

    def load_topology(self) -> bool:
        """Load and validate the topology file.

        Returns:
            True if topology was loaded successfully, False otherwise.
        """
        ...

    def generate_all(self) -> bool:
        """Generate all output files.

        Returns:
            True if all files were generated successfully, False otherwise.
        """
        ...

    def print_summary(self) -> None:
        """Print a summary of the generation results."""
        ...


class GeneratorCLI:
    """Base class for generator CLI entrypoints.

    Provides common argument parsing and execution flow for all generators.
    Subclasses should override class attributes and optionally add_extra_arguments().
    """

    # Override in subclasses
    description: str = "Generate configuration from topology v4.0"
    banner: str = "Topology Generator (v4.0)"
    default_output: str = "generated/output"
    success_message: str = "Generation completed successfully!"

    def __init__(self, generator_class: type) -> None:
        """Initialize CLI with the generator class to use.

        Args:
            generator_class: The generator class that will be instantiated.
        """
        self.generator_class = generator_class

    def build_parser(self) -> argparse.ArgumentParser:
        """Build argument parser with standard arguments.

        Returns:
            Configured ArgumentParser instance.
        """
        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument(
            "--topology",
            default="topology.yaml",
            help="Path to topology YAML file",
        )
        parser.add_argument(
            "--output",
            default=self.default_output,
            help=f"Output directory (default: {self.default_output}/)",
        )
        parser.add_argument(
            "--templates",
            default="topology-tools/templates",
            help="Directory containing Jinja2 templates",
        )
        self.add_extra_arguments(parser)
        return parser

    def add_extra_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Override to add generator-specific arguments.

        Args:
            parser: The ArgumentParser to add arguments to.
        """
        pass

    def create_generator(self, args: argparse.Namespace) -> Generator:
        """Create generator instance from parsed arguments.

        Override this method if your generator needs special initialization.

        Args:
            args: Parsed command-line arguments.

        Returns:
            Initialized generator instance.
        """
        return self.generator_class(args.topology, args.output, args.templates)

    def run_generator(self, generator: Generator) -> bool:
        """Execute the generator workflow.

        Override this method to customize the generation flow.

        Args:
            generator: The generator instance to run.

        Returns:
            True if generation succeeded, False otherwise.
        """
        if not generator.load_topology():
            return False

        print("\nGEN Generating output files...\n")

        if not generator.generate_all():
            print("\nERROR Generation failed with errors")
            return False

        generator.print_summary()
        return True

    def main(self, argv: Sequence[str] | None = None) -> int:
        """Main entry point for the CLI.

        Args:
            argv: Command-line arguments (defaults to sys.argv[1:]).

        Returns:
            Exit code: 0 for success, 1 for failure.
        """
        args = self.build_parser().parse_args(argv)
        generator = self.create_generator(args)

        print("=" * 70)
        print(self.banner)
        print("=" * 70)
        print()

        if not self.run_generator(generator):
            return 1

        print(f"\nOK {self.success_message}\n")
        return 0


def run_cli(cli: GeneratorCLI, argv: Sequence[str] | None = None) -> int:
    """Convenience function to run a GeneratorCLI.

    Args:
        cli: The CLI instance to run.
        argv: Command-line arguments.

    Returns:
        Exit code from cli.main().
    """
    return cli.main(argv)

"""Unit tests for generators.common.base module."""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, Mock

import pytest

from scripts.generators.common.base import Generator, GeneratorCLI, run_cli


class MockGenerator:
    """Mock generator for testing."""

    def __init__(self, topology_path: str, output_dir: str, templates_dir: str = ""):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir) if templates_dir else Path("templates")
        self.topology: Dict[str, Any] = {}
        self.load_called = False
        self.generate_called = False
        self.summary_called = False

    def load_topology(self) -> bool:
        """Mock topology loading."""
        self.load_called = True
        self.topology = {"L0_meta": {"version": "4.0.0"}}
        return True

    def generate_all(self) -> bool:
        """Mock generation."""
        self.generate_called = True
        return True

    def print_summary(self) -> None:
        """Mock summary printing."""
        self.summary_called = True


class TestGeneratorProtocol:
    """Test the Generator protocol."""

    def test_mock_generator_implements_protocol(self, temp_topology_file, temp_output_dir):
        """Test that MockGenerator implements Generator protocol."""
        gen = MockGenerator(str(temp_topology_file), str(temp_output_dir))

        # Check protocol compliance
        assert isinstance(gen, Generator)
        assert hasattr(gen, "topology_path")
        assert hasattr(gen, "output_dir")
        assert hasattr(gen, "topology")
        assert hasattr(gen, "load_topology")
        assert hasattr(gen, "generate_all")
        assert hasattr(gen, "print_summary")

    def test_generator_workflow(self, temp_topology_file, temp_output_dir):
        """Test basic generator workflow."""
        gen = MockGenerator(str(temp_topology_file), str(temp_output_dir))

        # Execute workflow
        assert gen.load_topology() is True
        assert gen.load_called is True

        assert gen.generate_all() is True
        assert gen.generate_called is True

        gen.print_summary()
        assert gen.summary_called is True


class TestGeneratorCLI:
    """Test the GeneratorCLI base class."""

    def test_cli_initialization(self):
        """Test CLI initialization."""
        cli = GeneratorCLI(MockGenerator)

        assert cli.generator_class is MockGenerator
        assert cli.description == "Generate configuration from topology v4.0"
        assert cli.banner == "Topology Generator (v4.0)"

    def test_build_parser(self):
        """Test argument parser building."""
        cli = GeneratorCLI(MockGenerator)
        parser = cli.build_parser()

        # Parse minimal args
        args = parser.parse_args([])

        assert args.topology == "topology.yaml"
        assert args.output == "generated/output"
        assert args.templates == "topology-tools/templates"

    def test_build_parser_custom_args(self):
        """Test parser with custom arguments."""
        cli = GeneratorCLI(MockGenerator)
        parser = cli.build_parser()

        args = parser.parse_args(
            [
                "--topology",
                "test.yaml",
                "--output",
                "out",
                "--templates",
                "tpl",
            ]
        )

        assert args.topology == "test.yaml"
        assert args.output == "out"
        assert args.templates == "tpl"

    def test_create_generator(self, temp_topology_file, temp_output_dir):
        """Test generator creation from args."""
        cli = GeneratorCLI(MockGenerator)
        parser = cli.build_parser()

        args = parser.parse_args(
            [
                "--topology",
                str(temp_topology_file),
                "--output",
                str(temp_output_dir),
            ]
        )

        gen = cli.create_generator(args)

        assert isinstance(gen, MockGenerator)
        assert gen.topology_path == temp_topology_file
        assert gen.output_dir == temp_output_dir

    def test_run_generator_success(self, temp_topology_file, temp_output_dir):
        """Test successful generator run."""
        cli = GeneratorCLI(MockGenerator)
        gen = MockGenerator(str(temp_topology_file), str(temp_output_dir))

        result = cli.run_generator(gen)

        assert result is True
        assert gen.load_called is True
        assert gen.generate_called is True
        assert gen.summary_called is True

    def test_run_generator_load_failure(self, temp_topology_file, temp_output_dir):
        """Test generator run with load failure."""
        cli = GeneratorCLI(MockGenerator)
        gen = MockGenerator(str(temp_topology_file), str(temp_output_dir))

        # Make load fail
        gen.load_topology = lambda: False

        result = cli.run_generator(gen)

        assert result is False

    def test_run_generator_generate_failure(self, temp_topology_file, temp_output_dir):
        """Test generator run with generation failure."""
        cli = GeneratorCLI(MockGenerator)
        gen = MockGenerator(str(temp_topology_file), str(temp_output_dir))

        # Make generate fail
        gen.generate_all = lambda: False

        result = cli.run_generator(gen)

        assert result is False

    def test_main_success(self, temp_topology_file, temp_output_dir, capsys):
        """Test main method with successful generation."""
        cli = GeneratorCLI(MockGenerator)

        exit_code = cli.main(
            [
                "--topology",
                str(temp_topology_file),
                "--output",
                str(temp_output_dir),
            ]
        )

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Topology Generator (v4.0)" in captured.out
        assert "Generation completed successfully!" in captured.out

    def test_main_failure(self, temp_topology_file, temp_output_dir, capsys, monkeypatch):
        """Test main method with generation failure."""
        cli = GeneratorCLI(MockGenerator)

        # Mock run_generator to return False
        def mock_run_generator(self, gen):
            return False

        monkeypatch.setattr(GeneratorCLI, "run_generator", mock_run_generator)

        exit_code = cli.main(
            [
                "--topology",
                str(temp_topology_file),
                "--output",
                str(temp_output_dir),
            ]
        )

        assert exit_code == 1


class TestRunCLI:
    """Test the run_cli convenience function."""

    def test_run_cli_success(self, temp_topology_file, temp_output_dir):
        """Test run_cli with successful generation."""
        cli = GeneratorCLI(MockGenerator)

        exit_code = run_cli(
            cli,
            [
                "--topology",
                str(temp_topology_file),
                "--output",
                str(temp_output_dir),
            ],
        )

        assert exit_code == 0

    def test_run_cli_failure(self, temp_topology_file, temp_output_dir, monkeypatch):
        """Test run_cli with generation failure."""
        cli = GeneratorCLI(MockGenerator)

        # Mock main to return failure
        monkeypatch.setattr(cli, "main", lambda argv: 1)

        exit_code = run_cli(
            cli,
            [
                "--topology",
                str(temp_topology_file),
                "--output",
                str(temp_output_dir),
            ],
        )

        assert exit_code == 1


class TestCustomGeneratorCLI:
    """Test custom CLI subclass."""

    def test_custom_cli_attributes(self):
        """Test customizing CLI attributes."""

        class CustomCLI(GeneratorCLI):
            description = "Custom generator"
            banner = "Custom Banner"
            default_output = "custom/output"
            success_message = "Custom success!"

        cli = CustomCLI(MockGenerator)

        assert cli.description == "Custom generator"
        assert cli.banner == "Custom Banner"
        assert cli.default_output == "custom/output"
        assert cli.success_message == "Custom success!"

    def test_add_extra_arguments(self):
        """Test adding custom arguments."""

        class CustomCLI(GeneratorCLI):
            def add_extra_arguments(self, parser):
                parser.add_argument("--custom", default="value")

        cli = CustomCLI(MockGenerator)
        parser = cli.build_parser()

        args = parser.parse_args(["--custom", "test"])

        assert args.custom == "test"

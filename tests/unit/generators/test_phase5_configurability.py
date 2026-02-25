"""Unit tests for Phase 5 configurability features."""

import argparse
from pathlib import Path

import pytest

from scripts.generators.common import GeneratorCLI, ProgressTracker, StatusReporter


class DummyGenerator:
    """Dummy generator for testing CLI."""

    def __init__(self, topology_path, output_dir, templates_dir):
        self.topology_path = Path(topology_path)
        self.output_dir = Path(output_dir)
        self.templates_dir = Path(templates_dir)
        self.topology = {}

    def load_topology(self):
        return True

    def generate_all(self):
        return True

    def print_summary(self):
        print("Summary")


class TestGeneratorCLI:
    """Test Phase 5 CLI enhancements."""

    def test_verbose_flag(self):
        """Test --verbose flag is parsed."""
        cli = GeneratorCLI(DummyGenerator)
        parser = cli.build_parser()
        args = parser.parse_args(["--verbose"])

        assert args.verbose is True

    def test_dry_run_flag(self):
        """Test --dry-run flag is parsed."""
        cli = GeneratorCLI(DummyGenerator)
        parser = cli.build_parser()
        args = parser.parse_args(["--dry-run"])

        assert args.dry_run is True

    def test_no_cache_flag(self):
        """Test --no-cache flag is parsed."""
        cli = GeneratorCLI(DummyGenerator)
        parser = cli.build_parser()
        args = parser.parse_args(["--no-cache"])

        assert args.no_cache is True

    def test_config_file_flag(self):
        """Test --config flag is parsed."""
        cli = GeneratorCLI(DummyGenerator)
        parser = cli.build_parser()
        args = parser.parse_args(["--config", "my-config.yaml"])

        assert args.config == "my-config.yaml"

    def test_components_flag_when_supported(self):
        """Test --components flag when supported."""
        cli = GeneratorCLI(DummyGenerator)
        cli.supports_components = True
        parser = cli.build_parser()
        args = parser.parse_args(["--components", "bridges,vms"])

        assert args.components == "bridges,vms"

    def test_verbose_short_flag(self):
        """Test -v short flag for verbose."""
        cli = GeneratorCLI(DummyGenerator)
        parser = cli.build_parser()
        args = parser.parse_args(["-v"])

        assert args.verbose is True


class TestProgressTracker:
    """Test progress tracking."""

    def test_progress_tracker_creation(self):
        """Test creating progress tracker."""
        tracker = ProgressTracker(total_steps=5)
        assert tracker.total_steps == 5
        assert tracker.current_step == 0

    def test_progress_step_increments(self):
        """Test that step() increments counter."""
        tracker = ProgressTracker(total_steps=3, verbose=False)

        tracker.step("Step 1")
        assert tracker.current_step == 1

        tracker.step("Step 2")
        assert tracker.current_step == 2

    def test_progress_tracker_verbose_mode(self):
        """Test verbose mode adds descriptions."""
        tracker = ProgressTracker(total_steps=2, verbose=True)
        # Just verify it doesn't crash with verbose=True
        tracker.start("Starting")
        tracker.step("Test", "Description")
        tracker.step_complete(True, "Details")
        tracker.finish(True)

    def test_progress_tracker_dry_run_mode(self):
        """Test dry-run mode shows different prefix."""
        tracker = ProgressTracker(total_steps=2, dry_run=True)
        tracker.start("Dry run")
        tracker.step("Test")
        tracker.step_complete()
        tracker.finish()

    def test_progress_step_skip(self):
        """Test skipping steps."""
        tracker = ProgressTracker(total_steps=3)
        tracker.step("Test")
        tracker.step_skip("Not needed")
        assert tracker.current_step == 1


class TestStatusReporter:
    """Test status reporter."""

    def test_status_reporter_creation(self):
        """Test creating status reporter."""
        reporter = StatusReporter()
        assert reporter.verbose is False
        assert not reporter.has_errors()
        assert not reporter.has_warnings()

    def test_warning_tracking(self, capsys):
        """Test warnings are tracked."""
        reporter = StatusReporter()
        reporter.warn("Test warning")

        assert reporter.has_warnings()
        assert len(reporter.warnings) == 1
        assert reporter.warnings[0] == "Test warning"

        captured = capsys.readouterr()
        assert "WARN" in captured.out

    def test_error_tracking(self, capsys):
        """Test errors are tracked."""
        reporter = StatusReporter()
        reporter.error("Test error")

        assert reporter.has_errors()
        assert len(reporter.errors) == 1
        assert reporter.errors[0] == "Test error"

        captured = capsys.readouterr()
        assert "ERROR" in captured.out

    def test_verbose_info_respects_flag(self, capsys):
        """Test verbose info only shows when verbose=True."""
        reporter = StatusReporter(verbose=False)
        reporter.verbose_info("Should not show")

        captured = capsys.readouterr()
        assert captured.out == ""

        reporter_verbose = StatusReporter(verbose=True)
        reporter_verbose.verbose_info("Should show")

        captured = capsys.readouterr()
        assert "Should show" in captured.out

    def test_dry_run_info_respects_flag(self, capsys):
        """Test dry-run info only shows when dry_run=True."""
        reporter = StatusReporter(dry_run=False)
        reporter.dry_run_info("Should not show")

        captured = capsys.readouterr()
        assert captured.out == ""

        reporter_dry = StatusReporter(dry_run=True)
        reporter_dry.dry_run_info("Should show")

        captured = capsys.readouterr()
        assert "DRYRUN" in captured.out

    def test_summary_generation(self):
        """Test summary generation."""
        reporter = StatusReporter()
        assert "No issues" in reporter.get_summary()

        reporter.warn("Warning 1")
        reporter.warn("Warning 2")
        summary = reporter.get_summary()
        assert "Warnings: 2" in summary

        reporter.error("Error 1")
        summary = reporter.get_summary()
        assert "Errors: 1" in summary
        assert "Warnings: 2" in summary


class TestConfigFileLoading:
    """Test config file loading (unit level)."""

    def test_load_config_file_not_exists(self, tmp_path):
        """Test loading non-existent config file."""
        cli = GeneratorCLI(DummyGenerator)
        args = argparse.Namespace(config=str(tmp_path / "nonexistent.yaml"))

        # Should not crash, just warn
        cli._load_config_file(args)

    def test_load_config_file_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML config."""
        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("{ invalid yaml }", encoding="utf-8")

        cli = GeneratorCLI(DummyGenerator)
        args = argparse.Namespace(config=str(config_file))

        # Should not crash
        cli._load_config_file(args)

    def test_load_config_file_valid(self, tmp_path):
        """Test loading valid YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("verbose: true\noutput: custom-output\n", encoding="utf-8")

        cli = GeneratorCLI(DummyGenerator)
        args = argparse.Namespace(
            config=str(config_file),
            verbose=False,
            output=None,
        )

        cli._load_config_file(args)

        # Config should update args
        assert args.output == "custom-output"
        # verbose was False in CLI, should be overridden by config
        # (but CLI args take precedence, so it depends on implementation)

"""Unit tests for Phase 6 production features."""

from pathlib import Path

import pytest

from scripts.generators.common import (
    ErrorHandler,
    ErrorSeverity,
    PerformanceProfiler,
    TimingResult,
    safe_execute,
    validate_file_exists,
    validate_required_fields,
)


class TestPerformanceProfiler:
    """Test performance profiler."""

    def test_profiler_measure(self):
        """Test profiler measure context manager."""
        profiler = PerformanceProfiler(enabled=True)

        with profiler.measure("test_operation"):
            sum(range(1000))

        assert len(profiler.profile.timings) == 1
        assert profiler.profile.timings[0].name == "test_operation"
        assert profiler.profile.timings[0].duration_seconds > 0

    def test_profiler_disabled(self):
        """Test profiler when disabled."""
        profiler = PerformanceProfiler(enabled=False)

        with profiler.measure("test_operation"):
            sum(range(1000))

        assert len(profiler.profile.timings) == 0

    def test_profiler_summary(self):
        """Test profiler summary generation."""
        profiler = PerformanceProfiler(enabled=True)

        with profiler.measure("op1"):
            sum(range(100))

        with profiler.measure("op2"):
            sum(range(200))

        summary = profiler.get_summary()
        assert "op1" in summary
        assert "op2" in summary
        assert "Total:" in summary

    def test_timing_result_format(self):
        """Test timing result formatting."""
        result = TimingResult(
            name="test",
            duration_seconds=0.5,
            start_time=0,
            end_time=0.5,
        )

        assert result.duration_ms == 500
        assert "test" in str(result)
        assert "0.50s" in str(result)


class TestErrorHandler:
    """Test error handler."""

    def test_error_handler_creation(self):
        """Test creating error handler."""
        handler = ErrorHandler()
        assert not handler.has_errors()
        assert not handler.has_warnings()

    def test_handle_error(self):
        """Test handling errors."""
        handler = ErrorHandler()

        should_continue = handler.handle_error(
            ErrorSeverity.ERROR,
            "Test error",
            "test_component",
        )

        assert handler.has_errors()
        assert len(handler.errors) == 1
        # By default, should not continue on error
        assert not should_continue

    def test_handle_warning(self):
        """Test handling warnings."""
        handler = ErrorHandler()

        should_continue = handler.handle_error(
            ErrorSeverity.WARNING,
            "Test warning",
            "test_component",
        )

        assert handler.has_warnings()
        assert not handler.has_errors()
        # Should always continue on warnings
        assert should_continue

    def test_continue_on_error_mode(self):
        """Test continue_on_error mode."""
        handler = ErrorHandler(continue_on_error=True)

        should_continue = handler.handle_error(
            ErrorSeverity.ERROR,
            "Test error",
            "test_component",
        )

        assert handler.has_errors()
        # Should continue when continue_on_error=True
        assert should_continue

    def test_critical_error_always_stops(self):
        """Test that critical errors always stop execution."""
        handler = ErrorHandler(continue_on_error=True)

        should_continue = handler.handle_error(
            ErrorSeverity.CRITICAL,
            "Critical error",
            "test_component",
        )

        # Critical errors should stop even with continue_on_error=True
        assert not should_continue

    def test_error_summary(self):
        """Test error summary generation."""
        handler = ErrorHandler()

        handler.handle_error(ErrorSeverity.ERROR, "Error 1", "comp1")
        handler.handle_error(ErrorSeverity.WARNING, "Warning 1", "comp2")

        summary = handler.get_summary()
        assert "Errors: 1" in summary
        assert "Warnings: 1" in summary
        assert "comp1" in summary

    def test_raise_if_critical(self):
        """Test raising on critical errors."""
        handler = ErrorHandler()

        handler.handle_error(
            ErrorSeverity.CRITICAL,
            "Critical error",
            "test_component",
        )

        with pytest.raises(RuntimeError, match="Critical errors occurred"):
            handler.raise_if_critical()


class TestSafeExecute:
    """Test safe_execute wrapper."""

    def test_safe_execute_success(self):
        """Test safe_execute with successful function."""
        handler = ErrorHandler()

        def successful_func(x, y):
            return x + y

        success, result = safe_execute(successful_func, handler, "test", "Addition", 2, 3)

        assert success
        assert result == 5
        assert not handler.has_errors()

    def test_safe_execute_file_not_found(self):
        """Test safe_execute with FileNotFoundError."""
        handler = ErrorHandler()

        def failing_func():
            raise FileNotFoundError("test.txt")

        success, result = safe_execute(failing_func, handler, "test", "Load file")

        assert not success
        assert result is None
        assert handler.has_errors()

    def test_safe_execute_value_error(self):
        """Test safe_execute with ValueError."""
        handler = ErrorHandler(continue_on_error=True)

        def failing_func():
            raise ValueError("Invalid value")

        success, result = safe_execute(failing_func, handler, "test", "Validate")

        # Should continue because continue_on_error=True
        assert success  # Returns continue flag
        assert result is None
        assert handler.has_errors()


class TestValidation:
    """Test validation helpers."""

    def test_validate_required_fields_success(self):
        """Test validation with all required fields."""
        data = {"name": "test", "value": 123}
        handler = ErrorHandler()

        result = validate_required_fields(
            data,
            ["name", "value"],
            "test_component",
            handler,
        )

        assert result is True
        assert not handler.has_errors()

    def test_validate_required_fields_missing(self):
        """Test validation with missing fields."""
        data = {"name": "test"}
        handler = ErrorHandler()

        result = validate_required_fields(
            data,
            ["name", "value"],
            "test_component",
            handler,
        )

        assert result is False
        assert handler.has_errors()

    def test_validate_file_exists_success(self, tmp_path):
        """Test file validation with existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        handler = ErrorHandler()

        result = validate_file_exists(
            test_file,
            "test_component",
            handler,
        )

        assert result is True
        assert not handler.has_errors()

    def test_validate_file_exists_missing(self, tmp_path):
        """Test file validation with missing file."""
        test_file = tmp_path / "nonexistent.txt"
        handler = ErrorHandler()

        result = validate_file_exists(
            test_file,
            "test_component",
            handler,
        )

        assert result is False
        assert handler.has_errors()
